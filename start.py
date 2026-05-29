#!/usr/bin/env python3
"""
活纸江湖 · 统一启动脚本
自动确保后端运行，然后启动前端（Web 或 Godot）

用法:
  python start.py              # 启动后端 + Web 前端（默认）
  python start.py web          # 启动后端 + Web 前端
  python start.py godot        # 启动后端 + Godot 前端
  python start.py --serve-only # 仅启动 Web 静态服务器（不启动后端）
  python start.py --backend-port 8765   # 自定义后端端口
  python start.py --frontend-port 8766  # 自定义前端端口
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

# Windows GBK 编码修复：强制使用 UTF-8 输出
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
import contextlib
from http.server import HTTPServer, SimpleHTTPRequestHandler

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# 默认配置
DEFAULT_BACKEND_PORT = 8765
DEFAULT_WEB_PORT = 8766

# Web前端静态文件目录
STATIC_DIR = os.path.join(PROJECT_ROOT, "static")

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
    sys.exit(0)


class CORSRequestHandler(SimpleHTTPRequestHandler):
    """带CORS支持的静态文件请求处理器"""

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        """处理GET请求，支持特殊路径"""
        if self.path == '/__shutdown__':
            self.handle_shutdown_request()
        elif self.path == '/__ping__':
            self.handle_ping_request()
        else:
            super().do_GET()

    def handle_shutdown_request(self):
        """处理关闭请求 - 直接强制退出进程"""
        global _frontend_should_shutdown
        _frontend_should_shutdown = True

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()

        import json
        response = {
            "status": "shutting_down",
            "message": "前端服务器将在1秒后强制停止",
            "pid": os.getpid()
        }
        self.wfile.write(json.dumps(response).encode('utf-8'))

        import threading
        def force_exit():
            import time
            time.sleep(1.0)  # 给时间让响应发送完成
            print("\n⛔ 前端服务器已接收到关闭指令，正在退出...")
            os._exit(0)  # 强制退出，不执行清理代码

        t = threading.Thread(target=force_exit, daemon=True)
        t.start()

    def handle_ping_request(self):
        """处理健康检查请求"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()

        import json
        response = {
            "status": "running",
            "pid": os.getpid(),
            "port": self.server.server_address[1]  # type: ignore[index]
        }
        self.wfile.write(json.dumps(response).encode('utf-8'))


# ════════════════════════════════════════════════
#  工具函数
# ════════════════════════════════════════════════


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """检查端口是否被占用"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.connect((host, port))
            return True
        except (ConnectionRefusedError, OSError):
            return False


def is_backend_running(host: str = "127.0.0.1", port: int = DEFAULT_BACKEND_PORT) -> bool:
    """检查后端是否在运行"""
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
                    print(f"   已终止占用端口 {port} 的进程 (PID: {pid})")
                    time.sleep(1)
                    return True
    except Exception:
        pass
    return False


# ════════════════════════════════════════════════
#  后端启动
# ════════════════════════════════════════════════


def start_backend(port: int = DEFAULT_BACKEND_PORT, frontend_port: int | None = None) -> subprocess.Popen | None:
    """启动后端服务"""
    print(f"🔧 启动后端服务 (端口 {port})...")

    if is_port_in_use(port) and not is_backend_running(port=port):
        print(f"⚠️ 端口 {port} 被占用但不是有效后端，尝试清理...")
        kill_port_process(port)

    os.chdir(PROJECT_ROOT)

    env = os.environ.copy()
    if frontend_port:
        env["FRONTEND_PORT"] = str(frontend_port)

    cmd = [sys.executable, "-m", "uvicorn", "backend.app:app",
           "--host", "127.0.0.1", "--port", str(port)]

    creationflags = 0
    if platform.system() == "Windows":
        creationflags = subprocess.CREATE_NEW_CONSOLE

    proc = subprocess.Popen(
        cmd,
        cwd=PROJECT_ROOT,
        env=env,
        creationflags=creationflags,
        stdout=None,
        stderr=None,
    )

    _child_processes.append(proc)

    max_wait = 15
    for i in range(max_wait):
        time.sleep(1)
        if is_backend_running(port=port):
            print(f"✅ 后端已就绪 (http://127.0.0.1:{port})")
            return proc
        if proc.poll() is not None:
            print(f"❌ 后端启动失败，退出码: {proc.returncode}")
            return None

    print(f"⚠️ 后端启动超时 ({max_wait}s)，请手动检查")
    return proc


# ════════════════════════════════════════════════
#  Web 前端（内嵌静态服务器）
# ════════════════════════════════════════════════

# 全局标志：用于控制前端服务器是否应该关闭
_frontend_should_shutdown = False


class StoppableHTTPServer(HTTPServer):
    """可被远程关闭的HTTP服务器"""

    def service_actions(self):
        """每次处理完请求后调用，检查是否需要关闭"""
        global _frontend_should_shutdown
        if _frontend_should_shutdown:
            self._do_shutdown()

    def _do_shutdown(self):
        """实际执行关闭操作"""
        import threading
        def _shutdown():
            import time
            time.sleep(0.5)  # 让当前响应完成
            with contextlib.suppress(Exception):
                HTTPServer.shutdown(self)

        t = threading.Thread(target=_shutdown, daemon=True)
        t.start()


def run_web_server(port: int = DEFAULT_WEB_PORT, block: bool = True) -> subprocess.Popen | None:
    """启动 Web 静态文件服务器（内嵌，替代原 serve_frontend.py）"""
    os.chdir(STATIC_DIR)

    server_address = ("127.0.0.1", port)
    httpd = StoppableHTTPServer(server_address, CORSRequestHandler)

    print("🌐 Web 前端服务器")
    print(f"📍 服务目录: {STATIC_DIR}")
    print(f"🔗 访问地址: http://127.0.0.1:{port}")
    print("🚀 按 Ctrl+C 停止\n")

    if block:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n👋 服务器已停止")
            sys.exit(0)
    else:
        creationflags = 0
        if platform.system() == "Windows":
            creationflags = subprocess.CREATE_NEW_CONSOLE

        proc = subprocess.Popen(
            [sys.executable, __file__, "--serve-only", str(port)],
            cwd=PROJECT_ROOT,
            creationflags=creationflags,
        )
        return proc


def trigger_frontend_shutdown():
    """触发前端服务器关闭（由后端或内部调用）"""
    global _frontend_should_shutdown
    _frontend_should_shutdown = True


def start_web_frontend(port: int = DEFAULT_WEB_PORT) -> subprocess.Popen | None:
    """启动Web前端（非阻塞，在子进程中运行）"""
    print(f"🌐 启动Web前端 (端口 {port})...")
    proc = run_web_server(port, block=False)
    if proc:
        _child_processes.append(proc)
        print(f"✅ Web前端已启动 → http://127.0.0.1:{port}")
    return proc


# ════════════════════════════════════════════════
#  Godot 前端
# ════════════════════════════════════════════════


def find_godot() -> str | None:
    """查找Godot可执行文件"""
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
    """启动Godot前端"""
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
    creationflags = 0
    if platform.system() == "Windows":
        creationflags = subprocess.CREATE_NO_WINDOW

    subprocess.Popen(cmd, cwd=PROJECT_ROOT, creationflags=creationflags)
    print(f"✅ Godot已启动 → 项目: {godot_project}")


# ════════════════════════════════════════════════
#  主入口
# ════════════════════════════════════════════════


def main():
    args = sys.argv[1:]

    backend_port = DEFAULT_BACKEND_PORT
    web_port = DEFAULT_WEB_PORT
    frontend_mode = "web"
    godot_path = None
    serve_only = False

    # 解析参数
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("--backend-port", "-b"):
            i += 1
            if i < len(args):
                backend_port = int(args[i])
        elif arg in ("--frontend-port", "-f"):
            i += 1
            if i < len(args):
                web_port = int(args[i])
        elif arg in ("--godot", "-g"):
            i += 1
            if i < len(args):
                godot_path = args[i]
        elif arg == "web":
            frontend_mode = "web"
        elif arg == "godot":
            frontend_mode = "godot"
        elif arg == "--serve-only":
            serve_only = True
            # 如果有额外参数作为端口
            if i + 1 < len(args) and args[i+1].isdigit():
                i += 1
                web_port = int(args[i])
        elif arg in ("-h", "--help"):
            print(__doc__)
            sys.exit(0)
        i += 1

    # ── 纯静态服务器模式（不启动后端）──
    if serve_only:
        run_web_server(port=web_port, block=True)
        return

    # ── 正常启动流程 ──
    atexit.register(_cleanup_children)
    signal.signal(signal.SIGINT, _signal_handler)
    if platform.system() != "Windows":
        signal.signal(signal.SIGTERM, _signal_handler)

    print("=" * 50)
    print("🏮 活纸江湖 · 统一启动器")
    print("=" * 50)
    print(f"  后端端口: {backend_port}")
    print(f"  前端模式: {frontend_mode}")
    if frontend_mode == "web":
        print(f"  Web端口:  {web_port}")
    print()

    # 1. 确保后端运行
    if not is_backend_running(port=backend_port):
        backend_proc = start_backend(
            backend_port,
            frontend_port=web_port
        )
        if not backend_proc and not is_backend_running(port=backend_port):
            print("\n❌ 无法启动后端，请检查Python依赖:")
            print("   pip install fastapi uvicorn httpx pydantic dotenv")
            sys.exit(1)
    else:
        print(f"✅ 后端已在运行 (http://127.0.0.1:{backend_port})")

    time.sleep(0.5)

    # 2. 启动前端
    if frontend_mode == "godot":
        start_godot_frontend(godot_path)
    else:
        start_web_frontend(web_port)

    print()
    print("=" * 50)
    print("🚀 所有服务已启动！")
    print("=" * 50)
    if frontend_mode == "web":
        print(f"📍 打开浏览器访问: http://127.0.0.1:{web_port}")
    else:
        print("📍 Godot编辑器已打开，按 F5 运行游戏")
    print()

    # 3. 监控循环（仅 web 模式）
    if frontend_mode == "web":
        print("📡 监控服务运行中 (Ctrl+C 退出)...")
        restart_count = 0
        max_restarts = 5
        try:
            while True:
                time.sleep(10)
                if not is_backend_running(port=backend_port):
                    restart_count += 1
                    if restart_count > max_restarts:
                        print(f"❌ 后端已连续重启 {max_restarts} 次失败，放弃重启")
                        print("   请检查后端日志排查问题")
                        break
                    delay = min(10 * restart_count, 60)
                    print(f"⚠️ 后端已停止，{delay}秒后尝试重启 ({restart_count}/{max_restarts})...")
                    time.sleep(delay)
                    new_proc = start_backend(backend_port, frontend_port=web_port)
                    if new_proc:
                        print("✅ 后端已重启")
                    else:
                        print("❌ 后端重启失败")
        except KeyboardInterrupt:
            print("\n👋 正在停止所有服务...")
            _cleanup_children()


if __name__ == "__main__":
    main()
