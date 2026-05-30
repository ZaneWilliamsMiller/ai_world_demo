"""管理/监控 API 路由：LLM 指标、熔断器、玩家、NPC 状态。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.config import settings

router = APIRouter(prefix="/api/admin", tags=["admin"])


async def _verify_admin(request: Request) -> None:
    secret = request.headers.get("X-Admin-Secret", "")
    if not settings.shutdown_secret or secret != settings.shutdown_secret:
        raise HTTPException(status_code=403, detail="无效的 Admin Secret")


@router.get("/metrics", dependencies=[Depends(_verify_admin)])
async def metrics() -> dict:
    from backend.observability.tracker import get_tracker
    from backend.llm.circuit_breaker import get_circuit_breaker
    tracker = get_tracker()
    cb = get_circuit_breaker()
    result = tracker.summary()
    result["circuit_breaker"] = cb.stats
    return result


@router.get("/circuit_breaker", dependencies=[Depends(_verify_admin)])
async def circuit_breaker_status() -> dict:
    from backend.llm.circuit_breaker import get_circuit_breaker
    cb = get_circuit_breaker()
    return cb.stats


@router.get("/players", dependencies=[Depends(_verify_admin)])
async def players() -> dict:
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


@router.get("/npc_states", dependencies=[Depends(_verify_admin)])
async def npc_states() -> dict:
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
            if mind and hasattr(mind, "daily_plan"):
                plan = mind.daily_plan
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


@router.get("/eval", dependencies=[Depends(_verify_admin)])
async def eval_stats() -> dict:
    from backend.observability.tracker import get_tracker
    tracker = get_tracker()
    return tracker.eval_summary()


@router.get("/recent_calls", dependencies=[Depends(_verify_admin)])
async def recent_calls(n: int = 20) -> dict:
    from backend.observability.tracker import get_tracker
    tracker = get_tracker()
    return {"calls": tracker.recent_calls(n)}
