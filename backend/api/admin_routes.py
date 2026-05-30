"""管理/监控 API 路由：LLM 指标、熔断器、玩家、NPC 状态、关闭服务。"""
from __future__ import annotations

import hmac
import logging
import os
import threading
import time as _time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.api.schema import (
    AdminCircuitBreakerResponse,
    AdminEvalResponse,
    AdminMetricsResponse,
    AdminNpcStatesResponse,
    AdminPlayersResponse,
    AdminRecentCallsResponse,
    ShutdownResponse,
)
from backend.config import settings

router = APIRouter(prefix="/api/admin", tags=["admin"])

_shutdown_log = logging.getLogger("shutdown")


async def _verify_admin(request: Request) -> None:
    secret = request.headers.get("X-Admin-Secret", "")
    if not settings.shutdown_secret or not hmac.compare_digest(secret, settings.shutdown_secret):
        raise HTTPException(status_code=403, detail="无效的 Admin Secret")


@router.get("/metrics", dependencies=[Depends(_verify_admin)], response_model=AdminMetricsResponse)
async def metrics():
    from backend.llm.circuit_breaker import get_circuit_breaker
    from backend.observability.tracker import get_tracker
    tracker = get_tracker()
    cb = get_circuit_breaker()
    result = tracker.summary()
    result["circuit_breaker"] = cb.stats
    return result


@router.get("/circuit_breaker", dependencies=[Depends(_verify_admin)], response_model=AdminCircuitBreakerResponse)
async def circuit_breaker_status():
    from backend.llm.circuit_breaker import get_circuit_breaker
    cb = get_circuit_breaker()
    return cb.stats


@router.get("/players", dependencies=[Depends(_verify_admin)], response_model=AdminPlayersResponse)
async def players():
    from backend.session.store import room
    result = []
    for pid, p in room.players.items():
        result.append({
            "player_id": pid,
            "display_name": p.display_name,
            "map_id": p.map_id,
            "px": p.px,
            "py": p.py,
            "dead": p.dead,
            "ended": p.ended,
        })
    return {"players": result}


@router.get("/npc_states", dependencies=[Depends(_verify_admin)], response_model=AdminNpcStatesResponse)
async def npc_states():
    from backend.session.store import room
    result: dict = {}
    for pid, p in room.players.items():
        npc_info: dict = {}
        positions = getattr(p, "npc_positions", {})
        states = getattr(p, "npc_states", {})
        minds = getattr(p, "minds", {})
        for npc_id, pos in positions.items():
            plan_summary = ""
            mind = minds.get(npc_id)
            if mind and hasattr(mind, "plan_summary"):
                plan = mind.plan_summary
                if plan:
                    plan_summary = str(plan)[:80]
            npc_info[npc_id] = {
                "pos": list(pos) if isinstance(pos, (list, tuple)) else pos,
                "state": states.get(npc_id, "idle"),
                "plan_summary": plan_summary,
            }
        if npc_info:
            result[pid] = npc_info
    return result


@router.get("/eval", dependencies=[Depends(_verify_admin)], response_model=AdminEvalResponse)
async def eval_stats():
    from backend.observability.tracker import get_tracker
    tracker = get_tracker()
    return tracker.eval_summary()


@router.get("/recent_calls", dependencies=[Depends(_verify_admin)], response_model=AdminRecentCallsResponse)
async def recent_calls(n: int = 20):
    from backend.observability.tracker import get_tracker
    tracker = get_tracker()
    return {"calls": tracker.recent_calls(n)}


@router.post("/shutdown", response_model=ShutdownResponse)
async def shutdown_server(request: Request):
    client_host = request.client.host if request.client else ""
    is_local = client_host in ("127.0.0.1", "::1", "localhost")
    secret = request.headers.get("X-Shutdown-Secret", "")
    expected = settings.shutdown_secret
    if not is_local:
        if not expected:
            raise HTTPException(403, "未配置 SHUTDOWN_SECRET，拒绝远程关闭")
        if not hmac.compare_digest(secret, expected):
            raise HTTPException(403, "无权关闭服务")

    _shutdown_log.info("收到关闭请求")

    from backend.app import mark_shutdown_requested
    from backend.session.store import room
    from backend.systems.save_system import save_game
    mark_shutdown_requested()

    snapshot = await room.snapshot()

    def delayed_shutdown(players_snapshot):
        _time.sleep(3.0)
        _shutdown_log.info("进程即将退出...")

        shutdown_marker = str(Path(__file__).resolve().parent.parent.parent / ".shutdown_requested")
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
                    _shutdown_log.error("shutdown save failed %s: %s", pid, e)
            if saved:
                _shutdown_log.info("shutdown saved %d active player(s)", saved)

            from backend.llm.client import _close_client_sync
            try:
                _close_client_sync()
            except Exception as e:
                _shutdown_log.error("LLM client close error: %s", e)
        except Exception as e:
            _shutdown_log.error("shutdown error: %s", e)

        os._exit(0)

    thread = threading.Thread(target=delayed_shutdown, args=(snapshot,), daemon=True)
    thread.start()

    return {
        "status": "shutting_down",
        "message": "服务正在关闭",
        "hint": "检查终端窗口查看详细日志",
    }
