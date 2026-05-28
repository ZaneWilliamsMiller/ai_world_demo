from __future__ import annotations

"""
运行（在 ai_world_demo 目录下）:
  python -m uvicorn backend.app:app --host 127.0.0.1 --port 8765
"""
import asyncio
import logging
import time as _time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.data.prompts import WORLD_NAME
from backend.api.routes import router as api_router
from backend.session.store import room
from backend.systems.save_system import save_game

_log = logging.getLogger("app")

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"

def _cors_allow_origins() -> tuple[list[str], bool]:
    """返回 (origins, allow_credentials)。origins 为 * 时凭证必须为 False（浏览器规范）。"""
    raw = (settings.cors_allow_origins or "").strip()
    if not raw or raw == "*":
        return ["*"], False
    origins = [x.strip() for x in raw.split(",") if x.strip()]
    if not origins:
        return ["*"], False
    return origins, True

_origins, _creds = _cors_allow_origins()

app = FastAPI(title=f"{WORLD_NAME} · 江湖行纪")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=_creds,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = _time.perf_counter()
    response = await call_next(request)
    duration_ms = int((_time.perf_counter() - start) * 1000)

    if request.url.path.startswith("/api/"):
        _log.info(
            "%s %s → %d (%dms)",
            request.method, request.url.path,
            response.status_code, duration_ms,
        )

    return response

# 真正的前后端分离：后端只提供API，不提供静态文件
# if STATIC.exists():
#     app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


# 定期自动存档（后台任务）
_auto_save_task = None

@app.on_event("startup")
async def _startup():
    """启动后台定期存档任务 + 初始化实体关键词缓存。"""
    global _auto_save_task
    _auto_save_task = asyncio.create_task(_auto_save_loop())
    # 初始化代词消解用的实体关键词缓存（从 NPCS/MAPS 数据动态构建）
    from backend.memory import init_entity_keywords
    init_entity_keywords()

async def _auto_save_loop():
    """每 5 分钟自动存档所有活跃玩家。"""
    _save_log = logging.getLogger("auto_save")
    while True:
        await asyncio.sleep(300)  # 5 分钟
        saved = 0
        for pid, p in list(room.players.items()):
            if p.dead or p.ended:
                continue
            try:
                save_game(p)
                saved += 1
            except Exception as e:
                _save_log.error("auto-save failed %s: %s", pid, e)
        if saved:
            _save_log.info("auto-saved %d player(s)", saved)

@app.on_event("shutdown")
async def _shutdown():
    """优雅关闭：取消自动存档任务 + 自动存档所有活跃玩家 + 释放 httpx 连接池。

    修复 Major #9：区分异常类型，对连接超时等瞬态错误增加重试机制。
    """
    # 取消定期存档任务
    global _auto_save_task
    if _auto_save_task and not _auto_save_task.done():
        _auto_save_task.cancel()

    saved = 0
    for pid, p in list(room.players.items()):
        if p.dead or p.ended:
            continue
        # 修复 Major #9：对存档操作增加重试机制，最多重试 2 次
        max_save_retries = 2
        for save_attempt in range(max_save_retries):
            try:
                save_game(p)
                saved += 1
                break
            except (ConnectionError, TimeoutError, OSError) as transient_err:
                # 连接类瞬态错误：可重试
                if save_attempt < max_save_retries - 1:
                    _log.warning(
                        f"auto-save transient error for {pid} (attempt {save_attempt + 1}/{max_save_retries}): "
                        f"{type(transient_err).__name__}: {transient_err}"
                    )
                    await asyncio.sleep(0.5 * (save_attempt + 1))
                    continue
                _log.error(f"auto-save failed after retries for {pid}: {transient_err}")
            except Exception as e:
                # 非瞬态错误（如数据损坏、权限问题）：不重试，直接记录
                _log.error(f"auto-save non-retryable error for {pid}: {type(e).__name__}: {e}")
                break

    if saved:
        _log.info(f"shutdown auto-saved {saved} active player(s)")

    # 修复 Major #9：关闭 LLM 客户端时增加异常分类处理
    from backend.llm_client import _close_client
    try:
        await _close_client()
    except (ConnectionError, TimeoutError, OSError) as close_err:
        # 连接关闭时的瞬态错误（如连接超时），仅警告不中断关闭流程
        _log.warning(f"LLM client close transient error (ignored): {type(close_err).__name__}: {close_err}")
    except Exception as close_err:
        # 其他未知错误，记录但不阻止 shutdown 流程
        _log.error(f"LLM client close unexpected error: {type(close_err).__name__}: {close_err}")


@app.post("/api/shutdown")
async def shutdown_server(request: Request):
    """关闭后端服务（仅用于开发环境）"""
    import os
    import threading
    import httpx

    secret = request.headers.get("X-Shutdown-Secret", "")
    expected = os.environ.get("SHUTDOWN_SECRET", "")
    if expected and secret != expected:
        raise HTTPException(403, "无权关闭服务")

    frontend_port = os.environ.get("FRONTEND_PORT")

    shutdown_log = _log.getChild("shutdown")
    shutdown_log.info("=" * 60)
    shutdown_log.info("🛑 收到关闭请求")
    print("\n" + "=" * 60)
    print("🛑 [SHUTDOWN] 收到关闭请求")
    print(f"   前端端口: {frontend_port}")
    print("=" * 60)

    # 通知前端服务器关闭
    if frontend_port:
        try:
            frontend_url = f"http://127.0.0.1:{frontend_port}/__shutdown__"
            shutdown_log.info(f"通知前端服务器关闭: {frontend_url}")
            print(f"   📤 准备通知前端: {frontend_url}")

            def notify_frontend():
                import time
                time.sleep(0.5)  # 让后端先返回响应给浏览器
                print(f"   ⏳ 等待500ms后发送通知...")
                try:
                    with httpx.Client(timeout=5.0) as client:
                        resp = client.get(frontend_url)
                        status_text = resp.text[:150] if resp.text else "(空)"
                        shutdown_log.info(f"✅ 前端响应: {resp.status_code}")
                        print(f"   ✅ [SUCCESS] 前端已接收关闭指令!")
                        print(f"      HTTP状态码: {resp.status_code}")
                        print(f"      响应内容: {status_text}")
                        print(f"   ⏳ 前端将在1秒后自动退出 (os._exit)...")
                except Exception as e:
                    shutdown_log.warning(f"❌ 通知前端失败: {e}")
                    print(f"   ❌ [ERROR] 无法连接前端!")
                    print(f"      错误类型: {type(e).__name__}")
                    print(f"      错误详情: {str(e)}")

            notifier = threading.Thread(target=notify_frontend, daemon=True)
            notifier.start()
        except Exception as e:
            shutdown_log.warning(f"准备通知前端时出错: {e}")
            print(f"   ❌ [ERROR] 准备通知时异常: {e}")

    else:
        print("   ⚠️ 未设置 FRONTEND_PORT 环境变量，跳过前端通知")

    def delayed_shutdown():
        import time
        import os
        time.sleep(3.0)
        print(f"\n   💀 后端进程即将退出 (os._exit)...")
        os._exit(0)

    thread = threading.Thread(target=delayed_shutdown, daemon=True)
    thread.start()

    return {
        "status": "shutting_down",
        "message": "服务正在关闭",
        "frontend_port": frontend_port,
        "method": "http_notification",
        "hint": "检查后端终端窗口查看详细日志"
    }


# 真正的前后端分离：后端只提供API，不提供静态文件
# @app.get("/")
# async def index() -> FileResponse:
#     index_path = STATIC / "index.html"
#     if not index_path.is_file():
#         raise HTTPException(500, "缺少 static/index.html")
#     return FileResponse(index_path)
