from __future__ import annotations

"""
运行:
  python start.py
  或
  python -m uvicorn backend.app:app --host 127.0.0.1 --port 8765
"""
import asyncio
import hmac
import logging
import os
import threading
import time as _time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api.routes import router as api_router
from backend.config import settings
from backend.data.prompts import WORLD_NAME
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

_auto_save_task = None

async def _auto_save_loop():
    """每 5 分钟自动存档所有活跃玩家。"""
    _save_log = logging.getLogger("auto_save")
    while True:
        try:
            await asyncio.sleep(settings.auto_save_interval_s)
            saved = 0
            snapshot = await room.snapshot()
            for pid, p in snapshot:
                if p.dead or p.ended:
                    continue
                try:
                    async with p.lock:
                        await asyncio.to_thread(save_game, p)
                    saved += 1
                except Exception as e:
                    _save_log.error("auto-save failed %s: %s", pid, e)
            if saved:
                _save_log.info("auto-saved %d player(s)", saved)
        except Exception as e:
            _save_log.error("auto-save loop error: %s", e, exc_info=True)

_shutdown_requested = False

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _auto_save_task
    _auto_save_task = asyncio.create_task(_auto_save_loop())
    from backend.memory import init_entity_keywords
    init_entity_keywords()
    yield
    if _auto_save_task and not _auto_save_task.done():
        _auto_save_task.cancel()
        try:
            await _auto_save_task
        except asyncio.CancelledError:
            pass
    if _shutdown_requested:
        _log.info("shutdown already saved by shutdown endpoint, skipping lifespan save")
    else:
        saved = 0
        snapshot = await room.snapshot()
        for pid, p in snapshot:
            if p.dead or p.ended:
                continue
            max_save_retries = 2
            for save_attempt in range(max_save_retries):
                try:
                    async with p.lock:
                        await asyncio.to_thread(save_game, p)
                    saved += 1
                    break
                except (ConnectionError, TimeoutError, OSError) as transient_err:
                    if save_attempt < max_save_retries - 1:
                        _log.warning(
                            "auto-save transient error for %s (attempt %d/%d): %s: %s",
                            pid, save_attempt + 1, max_save_retries,
                            type(transient_err).__name__, transient_err,
                        )
                        await asyncio.sleep(0.5 * (save_attempt + 1))
                        continue
                    _log.error("auto-save failed after retries for %s: %s", pid, transient_err)
                except Exception as e:
                    _log.error("auto-save non-retryable error for %s: %s: %s", pid, type(e).__name__, e)
                    break
        if saved:
            _log.info("shutdown auto-saved %d active player(s)", saved)
    from backend.llm.client import _close_client
    try:
        await _close_client()
    except (ConnectionError, TimeoutError, OSError) as close_err:
        _log.warning("LLM client close transient error (ignored): %s: %s", type(close_err).__name__, close_err)
    except Exception as close_err:
        _log.error("LLM client close unexpected error: %s: %s", type(close_err).__name__, close_err)

app = FastAPI(title=f"{WORLD_NAME} · 江湖行纪", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=_creds,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Shutdown-Secret", "X-Admin-Secret"],
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

@app.post("/api/shutdown")
async def shutdown_server(request: Request):
    secret = request.headers.get("X-Shutdown-Secret", "")
    expected = settings.shutdown_secret
    if not expected:
        raise HTTPException(403, "未配置 SHUTDOWN_SECRET，拒绝远程关闭")
    if not hmac.compare_digest(secret, expected):
        raise HTTPException(403, "无权关闭服务")

    shutdown_log = _log.getChild("shutdown")
    shutdown_log.info("收到关闭请求")
    global _shutdown_requested
    _shutdown_requested = True

    snapshot = await room.snapshot()

    def delayed_shutdown(players_snapshot):
        _time.sleep(3.0)
        _log.info("进程即将退出...")

        shutdown_marker = str(Path(__file__).resolve().parent.parent / ".shutdown_requested")
        try:
            with open(shutdown_marker, "w") as f:
                f.write("1")
        except Exception:
            pass

        try:
            saved = 0
            for pid, p in players_snapshot:
                if p.dead or p.ended:
                    continue
                try:
                    save_game(p)
                    saved += 1
                except Exception as e:
                    _log.error("shutdown save failed %s: %s", pid, e)
            if saved:
                _log.info("shutdown saved %d active player(s)", saved)

            from backend.llm.client import _close_client_sync
            try:
                _close_client_sync()
            except Exception as e:
                _log.error("LLM client close error: %s", e)
        except Exception as e:
            _log.error("shutdown error: %s", e)

        os._exit(0)

    thread = threading.Thread(target=delayed_shutdown, args=(snapshot,), daemon=True)
    thread.start()

    return {
        "status": "shutting_down",
        "message": "服务正在关闭",
        "hint": "检查终端窗口查看详细日志"
    }

if STATIC.is_dir():
    @app.get("/")
    async def _index():
        index_path = STATIC / "index.html"
        if not index_path.is_file():
            raise HTTPException(500, "缺少 static/index.html")
        return FileResponse(index_path)

    @app.get("/tests.html")
    async def _tests():
        tests_path = STATIC / "tests.html"
        if not tests_path.is_file():
            raise HTTPException(404)
        return FileResponse(tests_path)

    app.mount("/", StaticFiles(directory=str(STATIC)), name="static")
