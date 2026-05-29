#!/usr/bin/env python3
"""
活纸江湖 · 统一启动脚本
后端同时提供 API 和静态文件服务（同端口）

用法:
  python start.py              # 前台启动（默认端口 8765）
  python start.py godot        # 启动服务 + Godot 前端
  python start.py --port 8765  # 自定义端口
  python start.py --bg         # 后台启动（无命令行窗口，自动打开浏览器）
  python start.py --stop       # 停止后台服务
"""

import atexit
import io
import os
import platform
import signal
import socket
import subprocess
import sys
import time

_CREATE_NO_WINDOW: int = getattr(subprocess, "CREATE_NO_WINDOW", 0)

if sys.platform == "win32" and sys.stdout and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
import contextlib

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PORT = 8765
PID_FILE = os.path.join(PROJECT_ROOT, ".server.pid")

_child_processes = []


def _cleanup_children():
    for proc in _child_processes:
        if proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                with contextlib.suppress(Exception):
                    proc.kill()


def _signal_handler(signum, frame):
    print("\n🛑 收到退出信号，正在清理...")
    _cleanup_children()
    _remove_pid_file()
    sys.exit(0)


def _write_pid_file(pid: int, port: int) -> None:
    try:
        with open(PID_FILE, "w", encoding="utf-8") as f:
            f.write(f"{pid}\n{port}\n")
    except Exception:
        pass


def _read_pid_file() -> tuple[int, int] | None:
    try:
        with open(PID_FILE, "r", encoding="utf-8") as f:
            lines = f.read().strip().splitlines()
            return int(lines[0]), int(lines[1])
    except Exception:
        return None


def _remove_pid_file() -> None:
    try:
        os.remove(PID_FILE)
    except Exception:
        pass


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.connect((host, port))
            return True
        except (ConnectionRefusedError, OSError):
            return False


def is_backend_running(host: str = "127.0.0.1", port: int = DEFAULT_PORT) -> bool:
    if not is_port_in_use(port, host):
        return False
    import urllib.request
    try:
        req = urllib.request.Request(f"http://{host}:{port}/api/health", method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


def kill_port_process(port: int) -> bool:
    if platform.system() != "Windows":
        return False
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True, timeout=5, check=False
        )
        for line in result.stdout.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                parts = line.split()
                pid = int(parts[-1])
                if pid > 0:
                    subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                                   capture_output=True, timeout=5, check=False)
                    time.sleep(1)
                    return True
    except Exception:
        pass
    return False


def stop_background_server() -> None:
    info = _read_pid_file()
    if info:
        pid, port = info
        print(f"🛑 停止后台服务 (PID: {pid}, 端口: {port})...")
        try:
            if platform.system() == "Windows":
                subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                               capture_output=True, timeout=5, check=False)
            else:
                import signal as sig
                os.kill(pid, sig.SIGTERM)
            time.sleep(1)
            if not is_backend_running(port=port):
                print("✅ 服务已停止")
            else:
                print("⚠️ 服务可能仍在运行，尝试强制清理端口...")
                kill_port_process(port)
                print("✅ 已清理")
        except ProcessLookupError:
            print("⚠️ 进程已不存在")
        except Exception as e:
            print(f"❌ 停止失败: {e}")
        _remove_pid_file()
        return

    if is_backend_running():
        print("🛑 检测到服务在运行，尝试停止...")
        if kill_port_process(DEFAULT_PORT):
            print("✅ 服务已停止")
        else:
            print("❌ 无法自动停止，请手动关闭")
    else:
        print("ℹ️ 没有检测到运行中的服务")


def start_server(port: int = DEFAULT_PORT, background: bool = False) -> subprocess.Popen | None:
    if not background:
        print(f"🔧 启动服务 (端口 {port})...")

    if is_port_in_use(port) and not is_backend_running(port=port):
        if not background:
            print(f"⚠️ 端口 {port} 被占用但不是有效服务，尝试清理...")
        kill_port_process(port)

    os.chdir(PROJECT_ROOT)

    cmd = [sys.executable, "-m", "uvicorn", "backend.app:app",
           "--host", "127.0.0.1", "--port", str(port)]

    if background:
        proc = subprocess.Popen(
            cmd,
            cwd=PROJECT_ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=_CREATE_NO_WINDOW if platform.system() == "Windows" else 0,
        )
    else:
        proc = subprocess.Popen(
            cmd,
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        def _forward_output(p: subprocess.Popen) -> None:
            try:
                for line in p.stdout:
                    if line:
                        print(line.decode(errors="replace"), end="", flush=True)
            except Exception:
                pass

        import threading
        t = threading.Thread(target=_forward_output, args=(proc,), daemon=True)
        t.start()

    _child_processes.append(proc)

    max_wait = 15
    for i in range(max_wait):
        time.sleep(1)
        if is_backend_running(port=port):
            if not background:
                print(f"✅ 服务已就绪 (http://127.0.0.1:{port})")
            return proc
        if proc.poll() is not None:
            if not background:
                print(f"❌ 服务启动失败，退出码: {proc.returncode}")
            return None

    if not background:
        print(f"⚠️ 服务启动超时 ({max_wait}s)，请手动检查")
    return proc


def open_browser(url: str) -> None:
    import webbrowser
    webbrowser.open(url)


def find_godot() -> str | None:
    possible_paths = []

    if platform.system() == "Windows":
        appdata_local = os.environ.get("LOCALAPPDATA", "")
        program_files = os.environ.get("ProgramFiles(x86)", os.environ.get("ProgramFiles", ""))

        possible_paths.extend([
            os.path.join(appdata_local, "Programs", "Godot", "Godot_v4.3-stable_win64.exe"),
            os.path.join(appdata_local, "Programs", "Godot", "Godot_v4.2-stable_win64.exe"),
            os.path.join(program_files, "Godot", "Godot_v4.3-stable_win64.exe"),
            os.path.join(appdata_local, "Programs", "godot", "Godot_v4.3-stable_win64.exe"),
        ])

        for p in os.environ.get("PATH", "").split(os.pathsep):
            for name in ["Godot_v4.3-stable_win64.exe", "Godot.exe"]:
                candidate = os.path.join(p, name)
                if os.path.isfile(candidate):
                    possible_paths.append(candidate)

    elif platform.system() == "Darwin":
        possible_paths.extend([
            "/Applications/Godot.app/Contents/MacOS/Godot",
            os.path.expanduser("~/Applications/Godot.app/Contents/MacOS/Godot"),
        ])
    else:
        possible_paths.extend([
            "/usr/bin/godot",
            "/usr/local/bin/godot",
            os.path.expanduser("~/.local/bin/godot"),
        ])

    for path in possible_paths:
        if path and os.path.isfile(path):
            return path

    return None


def start_godot_frontend(godot_path: str | None = None) -> None:
    godot_path = godot_path or find_godot()
    if not godot_path:
        print("❌ 未找到Godot，请先安装Godot 4.x")
        print("   下载地址: https://godotengine.org/download")
        return

    godot_project = os.path.join(PROJECT_ROOT, "godot")
    if not os.path.isdir(godot_project):
        print(f"❌ Godot项目目录不存在: {godot_project}")
        return

    print(f"🎮 启动Godot前端 ({godot_path})...")

    cmd = [godot_path, "--path", godot_project]
    creationflags = _CREATE_NO_WINDOW if platform.system() == "Windows" else 0

    subprocess.Popen(cmd, cwd=PROJECT_ROOT, creationflags=creationflags)
    print(f"✅ Godot已启动 → 项目: {godot_project}")


def main():
    args = sys.argv[1:]

    port = DEFAULT_PORT
    frontend_mode = "web"
    godot_path = None
    background = False
    do_stop = False

    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("--port", "-p", "--backend-port", "-b"):
            i += 1
            if i < len(args):
                port = int(args[i])
        elif arg in ("--godot", "-g"):
            i += 1
            if i < len(args):
                godot_path = args[i]
        elif arg == "web":
            frontend_mode = "web"
        elif arg == "godot":
            frontend_mode = "godot"
        elif arg in ("--bg", "--background"):
            background = True
        elif arg in ("--stop", "--shutdown"):
            do_stop = True
        elif arg in ("-h", "--help"):
            print(__doc__)
            sys.exit(0)
        i += 1

    if do_stop:
        stop_background_server()
        return

    atexit.register(_cleanup_children)
    signal.signal(signal.SIGINT, _signal_handler)
    if platform.system() != "Windows":
        signal.signal(signal.SIGTERM, _signal_handler)

    if is_backend_running(port=port):
        if background:
            open_browser(f"http://127.0.0.1:{port}")
            return
        print(f"✅ 服务已在运行 (http://127.0.0.1:{port})")
    else:
        server_proc = start_server(port, background=background)
        if not server_proc and not is_backend_running(port=port):
            if not background:
                print("\n❌ 无法启动服务，请检查Python依赖:")
                print("   pip install fastapi uvicorn httpx pydantic dotenv")
            sys.exit(1)

        if background:
            _write_pid_file(server_proc.pid, port)
            time.sleep(1)
            open_browser(f"http://127.0.0.1:{port}")
            return

    time.sleep(0.5)

    if frontend_mode == "godot":
        start_godot_frontend(godot_path)

    print()
    print("=" * 50)
    print("🚀 服务已启动！")
    print("=" * 50)
    print(f"📍 打开浏览器访问: http://127.0.0.1:{port}")
    print()

    print("📡 监控服务运行中 (Ctrl+C 退出)...")
    restart_count = 0
    max_restarts = 5
    try:
        while True:
            time.sleep(10)
            if not is_backend_running(port=port):
                restart_count += 1
                if restart_count > max_restarts:
                    print(f"❌ 服务已连续重启 {max_restarts} 次失败，放弃重启")
                    print("   请检查后端日志排查问题")
                    break
                delay = min(10 * restart_count, 60)
                print(f"⚠️ 服务已停止，{delay}秒后尝试重启 ({restart_count}/{max_restarts})...")
                time.sleep(delay)
                new_proc = start_server(port)
                if new_proc:
                    print("✅ 服务已重启")
                else:
                    print("❌ 服务重启失败")
    except KeyboardInterrupt:
        print("\n👋 正在停止所有服务...")
        _cleanup_children()
        _remove_pid_file()


if __name__ == "__main__":
    main()
