"""NPC 对话 API 路由：npc_talk, npc_talk_stream, item/use, rest, agent, finale, bounty榜"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import time
import traceback
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Path
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.agents import brain as agent_brain
from backend.agents.actor import act_loop, execute_plan_step_async
from backend.agents.game_state import get_or_init_mind
from backend.api.schema import (
    AgentActLoopResponse,
    AgentActResponse,
    AgentMindResponse,
    AgentPlanResponse,
    AgentReflectResponse,
    BountyAbandonResponse,
    BountyAcceptResponse,
    BountyCheckResponse,
    BountyCompleteResponse,
    BountyRefreshResponse,
    BountyStateResponse,
    FinaleResponse,
    ItemUseResponse,
    RestResponse,
    TalkResponse,
    WaitResponse,
)
from backend.api.views import npcs_here as _npcs_here
from backend.api.views import player_public as _player_public
from backend.data.factions import FACTIONS
from backend.data.npcs_data import NPCS
from backend.data.prompts import SOCIETY_BIBLE, WORLD_NAME
from backend.llm.client import chat_completion, parse_finale, parse_npc_reply_json
from backend.llm.params import (
    FINALE_MAX_TOKENS,
    FINALE_TEMPERATURE,
    TALK_FULL_MAX_TOKENS,
    TALK_LIGHT_MAX_TOKENS,
    TALK_TEMPERATURE,
)
from backend.models.player import PlayerState
from backend.observability.tracker import CallRecord, get_tracker
from backend.services.agent_service import bg_reflect
from backend.services.talk_service import apply_npc_reply, build_graceful_fallback, build_npc_messages
from backend.systems.core import danger_sense_narrative, npc_ids_for_player, perception_scan, update_npc_state_dynamic
from backend.systems.time_weather import shichen_name


class _RateLimiter:
    def __init__(self, max_requests: int = 10, window_s: float = 60.0, max_keys: int = 500):
        self._max = max_requests
        self._window = window_s
        self._max_keys = max_keys
        self._requests: dict[str, list[float]] = defaultdict(list)

    def is_limited(self, key: str) -> bool:
        now = time.time()
        timestamps = self._requests[key]
        self._requests[key] = [t for t in timestamps if now - t < self._window]
        if len(self._requests) > self._max_keys:
            expired = [k for k, v in self._requests.items() if not v or now - v[-1] >= self._window]
            for k in expired:
                del self._requests[k]
        if len(self._requests[key]) >= self._max:
            return True
        self._requests[key].append(now)
        return False

_talk_limiter = _RateLimiter(max_requests=10, window_s=60.0)

router = APIRouter()


def _get_active_player(player_id: str) -> PlayerState:
    from backend.session.store import room
    p = room.players.get(player_id)
    if not p:
        raise HTTPException(404, "未知 player_id")
    if p.dead:
        raise HTTPException(400, "角色已故，无法操作")
    if p.ended:
        raise HTTPException(400, "本局已收束，无法操作")
    if int(getattr(p, "unconscious_ticks", 0) or 0) > 0:
        raise HTTPException(409, "你正处于昏迷状态，无法操作")
    if getattr(p, "enslaved", False):
        raise HTTPException(403, "你正被奴役，无法操作")
    return p


_PID = Field(..., min_length=1, max_length=64, pattern=r'^[A-Za-z0-9_-]+$')

class TalkBody(BaseModel):
    player_id: str = _PID
    npc_id: str = Field(..., min_length=1, max_length=32)
    message: str = Field(..., min_length=1, max_length=2000)

class UseItemBody(BaseModel):
    player_id: str = _PID
    item: str = Field(..., min_length=1, max_length=20, description="物品名")

class RestBody(BaseModel):
    player_id: str = _PID

class FinaleBody(BaseModel):
    player_id: str = _PID
    closing_note: str | None = Field(None, max_length=600)

class AgentActBody(BaseModel):
    player_id: str = _PID
    npc_id: str = Field(..., min_length=1, max_length=32)

class AgentActLoopBody(BaseModel):
    player_id: str = _PID
    npc_id: str = Field(..., min_length=1, max_length=32)
    max_steps: int = Field(3, ge=1, le=10)

class AgentActLoopStreamBody(BaseModel):
    player_id: str = _PID
    npc_id: str = Field(..., min_length=1, max_length=32)
    max_steps: int = Field(3, ge=1, le=10)


def _sse(obj: dict[str, Any]) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def _validate_talk_request(body: TalkBody):
    from backend.session.store import room
    p = room.players.get(body.player_id)
    if not p:
        raise HTTPException(404, "未知 player_id")
    if p.ended:
        raise HTTPException(400, "本局已收束")
    if p.dead:
        raise HTTPException(400, "角色已身亡，无法交谈")
    if int(getattr(p, "unconscious_ticks", 0) or 0) > 0:
        raise HTTPException(409, "你正处于昏迷状态，无法开口交谈")
    if getattr(p, "enslaved", False):
        raise HTTPException(403, "你正被奴役，无法自由交谈")
    npc = NPCS.get(body.npc_id)
    if not npc:
        raise HTTPException(400, "未知 npc")
    allowed = set(npc_ids_for_player(p))
    if body.npc_id not in allowed:
        raise HTTPException(400, "此人不在你当前这一格，或不可交谈。请先移动贴近")
    return p, npc


@router.post("/api/item/use", response_model=ItemUseResponse)
async def use_item(body: UseItemBody):
    from backend.session.store import room
    p = room.players.get(body.player_id)
    if not p:
        raise HTTPException(404, f"未知 player_id: {body.player_id}")
    if getattr(p, "dead", False):
        raise HTTPException(400, "角色已故，物无所用")
    if p.ended:
        raise HTTPException(400, "本局已收束")
    if int(getattr(p, "unconscious_ticks", 0) or 0) > 0:
        raise HTTPException(409, "角色处于昏迷状态")
    if getattr(p, "enslaved", False):
        raise HTTPException(403, "你正被奴役，无法使用物品")

    from backend.systems.economy import use_player_item
    async with p.lock:
        result = use_player_item(p, body.item)

    if result.get("success"):
        from backend.systems.reputation import push_event
        note = str(result.get("note", ""))
        if note:
            push_event(p, f"{p.display_name}用掉了{note}", scope="self", actor=p.display_name)

    return {
        **result,
        "player": _player_public(p),
    }


@router.post("/api/rest", response_model=RestResponse)
async def player_rest(body: RestBody):
    from backend.data.atmosphere import scene_context
    from backend.session.store import room
    p = room.players.get(body.player_id)
    if not p:
        raise HTTPException(404, f"未知 player_id: {body.player_id}")
    if getattr(p, "dead", False):
        raise HTTPException(400, "魂已归西，无足歇矣")
    if p.ended:
        raise HTTPException(400, "本局已收束")
    if int(getattr(p, "unconscious_ticks", 0) or 0) > 0:
        raise HTTPException(409, "角色处于昏迷状态")
    if getattr(p, "enslaved", False):
        raise HTTPException(403, "你正被奴役，无法歇息")
    if getattr(p, "move_locked", False):
        raise HTTPException(409, "身陷险局，须先周旋脱身方可歇息")

    from backend.systems.core import rest_at_location
    async with p.lock:
        result = rest_at_location(p)
        try:
            from backend.systems.save_system import save_game
            await asyncio.to_thread(save_game, p)
        except Exception as e:
            logging.getLogger('rest').error('save failed for %s: %s', p.player_id, e)

    scan = perception_scan(p)
    danger_sense = danger_sense_narrative(p, scan) if scan else None
    return {
        **result,
        "player": _player_public(p),
        "npcs_here": _npcs_here(p),
        "danger_sense": {
            "alert": danger_sense or None,
            "scan": scan,
        },
        "atmosphere": scene_context(p),
        "events": list(p.events[-5:]),
    }


class WaitBody(BaseModel):
    player_id: str = _PID

@router.post("/api/wait", response_model=WaitResponse)
async def player_wait(body: WaitBody):
    from backend.data.atmosphere import scene_context
    from backend.session.store import room
    from backend.systems.time_weather import advance_clock
    p = room.players.get(body.player_id)
    if not p:
        raise HTTPException(404, f"未知 player_id: {body.player_id}")
    if getattr(p, "dead", False):
        raise HTTPException(400, "魂已归西，再无等待")
    if p.ended:
        raise HTTPException(400, "本局已收束")
    if getattr(p, "enslaved", False):
        raise HTTPException(403, "你正被奴役，无法自主等待")

    was_unconscious = int(getattr(p, "unconscious_ticks", 0) or 0) > 0

    async with p.lock:
        advance_clock(p, 1)

    scan = perception_scan(p)
    danger_sense = danger_sense_narrative(p, scan) if scan else None

    still_unconscious = int(getattr(p, "unconscious_ticks", 0) or 0) > 0
    if was_unconscious and not still_unconscious:
        note = "你缓缓睁开双眼，意识逐渐清明……"
    elif was_unconscious:
        remaining = int(getattr(p, "unconscious_ticks", 0) or 0)
        note = f"昏迷之中，时光流逝……约{remaining}个时辰后可苏醒"
    else:
        note = "你驻足片刻，静静等待。"

    return {
        "ok": True,
        "note": note,
        "ticks_passed": 1,
        "unconscious": still_unconscious,
        "player": _player_public(p),
        "npcs_here": _npcs_here(p),
        "danger_sense": {
            "alert": danger_sense or None,
            "scan": scan,
        },
        "atmosphere": scene_context(p),
        "events": list(p.events[-5:]),
    }


@router.post("/api/npc/talk", response_model=TalkResponse)
async def npc_talk(body: TalkBody, bg: BackgroundTasks):
    if _talk_limiter.is_limited(body.player_id):
        raise HTTPException(429, "对话过于频繁，请稍后再试")
    try:
        p, _npc = _validate_talk_request(body)

        async with p.lock:
            update_npc_state_dynamic(p, body.npc_id)
            hist = p.history.setdefault(body.npc_id, [])
            hist_slice = list(hist[-14:])

        import backend.llm.prompt_compress as _pc
        if len(hist_slice) >= _pc.COMPRESS_THRESHOLD:
            hist_slice = await _pc.compress_conversation_history(
                hist_slice, npc_name=NPCS.get(body.npc_id, {}).get("name", "")
            )

        messages = build_npc_messages(p, body.npc_id, body.message, hist_slice)
        t0 = time.perf_counter()

        is_light_inquiry = body.message.startswith("[系统指令·问路")
        is_fallback = False
        try:
            raw = await chat_completion(
                messages,
                temperature=TALK_TEMPERATURE,
                max_tokens=TALK_LIGHT_MAX_TOKENS if is_light_inquiry else TALK_FULL_MAX_TOKENS,
                response_format={"type": "json_object"},
            )
            parsed = parse_npc_reply_json(raw)
        except Exception as e:
            is_fallback = True
            fallback = build_graceful_fallback(body.npc_id, f"{type(e).__name__}: {e}")
            parsed = fallback["parsed"]

            logging.getLogger("api.routes").warning(
                "LLM fallback for npc=%s player=%s: %s",
                body.npc_id, body.player_id, str(e)[:120]
            )

        # eval 埋点
        get_tracker().record(CallRecord(
            timestamp=time.time(),
            operation="npc_talk",
            model="",
            player_id=body.player_id,
            npc_id=body.npc_id,
            parse_success=not is_fallback,
            schema_violations=["parse_error"] if is_fallback else [],
            latency_ms=int((time.perf_counter() - t0) * 1000),
            status="error" if is_fallback else "success",
        ))

        async with p.lock:
            out, needs_reflect = apply_npc_reply(p, body.npc_id, body.message, parsed, is_fallback=is_fallback)
            p.last_talk_npc_id = body.npc_id
            p.last_talk_message = body.message

        if needs_reflect and not is_light_inquiry and not is_fallback:
            bg.add_task(bg_reflect, p.player_id, body.npc_id)

        out["server_ms"] = int((time.perf_counter() - t0) * 1000)
        if is_fallback:
            out["llm_fallback"] = True
        return out
    except HTTPException:
        raise
    except Exception:
        logging.getLogger("api.routes").error(
            "npc_talk UNHANDLED ERROR for npc=%s player=%s:\n%s",
            body.npc_id, body.player_id, traceback.format_exc()
        )
        raise HTTPException(500, "NPC对话处理失败，请稍后重试") from None


@router.post("/api/npc/talk_stream")
async def npc_talk_stream(body: TalkBody, bg: BackgroundTasks) -> StreamingResponse:
    if _talk_limiter.is_limited(body.player_id):
        raise HTTPException(429, "对话过于频繁，请稍后再试")
    p, _npc = _validate_talk_request(body)

    async def event_gen():
        try:
            async with p.lock:
                update_npc_state_dynamic(p, body.npc_id)
                hist = p.history.setdefault(body.npc_id, [])
                hist_slice = list(hist[-14:])

            import backend.llm.prompt_compress as _pc
            if len(hist_slice) >= _pc.COMPRESS_THRESHOLD:
                hist_slice = await _pc.compress_conversation_history(
                    hist_slice, npc_name=NPCS.get(body.npc_id, {}).get("name", ""))

            messages = build_npc_messages(p, body.npc_id, body.message, hist_slice)
        except asyncio.CancelledError:
            logging.getLogger("api.routes").info("SSE stream cancelled during prep for npc=%s player=%s", body.npc_id, body.player_id)
            yield _sse({"done": True, "interrupted": True})
            return
        except Exception as e:
            logging.getLogger("api.routes").warning("Pre-processing error (stream) for npc=%s player=%s: %s", body.npc_id, body.player_id, str(e)[:120])
            yield _sse({"done": True, "error": "预处理失败，请重试", "interrupted": True})
            return

        t0 = time.perf_counter()
        is_fallback = False
        is_light_inquiry = False
        parsed = None

        try:
            is_light_inquiry = body.message.startswith("[系统指令·问路")
            raw = await asyncio.wait_for(
                chat_completion(
                    messages,
                    temperature=TALK_TEMPERATURE,
                    max_tokens=TALK_LIGHT_MAX_TOKENS if is_light_inquiry else TALK_FULL_MAX_TOKENS,
                    response_format={"type": "json_object"},
                ),
                timeout=60.0,
            )
            parsed = parse_npc_reply_json(raw)
        except asyncio.CancelledError:
            logging.getLogger("api.routes").info("SSE stream cancelled for npc=%s player=%s", body.npc_id, body.player_id)
            yield _sse({"done": True, "interrupted": True})
            return
        except TimeoutError:
            is_fallback = True
            fb = build_graceful_fallback(body.npc_id, "LLM 响应超时")
            parsed = fb["parsed"]
            logging.getLogger("api.routes").warning(
                "LLM timeout (stream) for npc=%s player=%s", body.npc_id, body.player_id
            )
        except Exception as e:
            is_fallback = True
            fb = build_graceful_fallback(body.npc_id, str(e))
            parsed = fb["parsed"]

            logging.getLogger("api.routes").warning(
                "LLM fallback (stream) for npc=%s player=%s: %s",
                body.npc_id, body.player_id, str(e)[:120]
            )
            yield _sse({"done": True, "interrupted": True, "error": str(e)[:100]})
            return

        # eval 埋点
        get_tracker().record(CallRecord(
            timestamp=time.time(),
            operation="npc_talk",
            model="",
            player_id=body.player_id,
            npc_id=body.npc_id,
            parse_success=not is_fallback,
            schema_violations=["parse_error"] if is_fallback else [],
            latency_ms=int((time.perf_counter() - t0) * 1000),
            status="error" if is_fallback else "success",
        ))

        out = {}
        needs_reflect = False
        try:
            async with p.lock:
                out, needs_reflect = apply_npc_reply(p, body.npc_id, body.message, parsed, is_fallback=is_fallback)
                p.last_talk_npc_id = body.npc_id
                p.last_talk_message = body.message
        except asyncio.CancelledError:
            logging.getLogger("api.routes").info("SSE stream cancelled during state write for npc=%s player=%s", body.npc_id, body.player_id)
            yield _sse({"done": True, "interrupted": True})
            return
        except Exception:
            out = {"error": "状态写入失败，请重试"}
            yield _sse({"done": True, **out})
            return

        try:
            vis = (parsed.visible_text or "").strip() if parsed else ""
            if vis:
                chunk_size = 16
                for i in range(0, len(vis), chunk_size):
                    yield _sse({"chunk": vis[i : i + chunk_size]})
                    await asyncio.sleep(0.01)

            if needs_reflect and not is_light_inquiry and not is_fallback:
                bg.add_task(bg_reflect, p.player_id, body.npc_id)

            out["server_ms"] = int((time.perf_counter() - t0) * 1000)
            if is_fallback:
                out["llm_fallback"] = True
            yield _sse({"done": True, **out})
        except asyncio.CancelledError:
            logging.getLogger("api.routes").info("SSE stream cancelled during output for npc=%s player=%s", body.npc_id, body.player_id)
            yield _sse({"done": True, "interrupted": True})
            return

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get("/api/agent/{player_id}/{npc_id}/mind", response_model=AgentMindResponse)
async def agent_mind(player_id: str = Path(..., min_length=1, max_length=64), npc_id: str = Path(..., min_length=1, max_length=64)):
    from backend.session.store import room
    p = room.players.get(player_id)
    if not p:
        raise HTTPException(404, "未知 player_id")
    if p.dead:
        raise HTTPException(400, "角色已故")
    if p.ended:
        raise HTTPException(400, "本局已收束")
    if npc_id not in NPCS:
        raise HTTPException(404, "未知 npc_id")
    async with p.lock:
        mind = p.minds.get(npc_id)
        if mind is None:
            return {
                "npc_id": npc_id,
                "npc_name": NPCS.get(npc_id, {}).get("name", npc_id),
                "items": [],
                "plan_day": None,
                "plan_summary": "",
                "plan_by_shichen": {},
                "affect_valence": 0.0,
                "affect_arousal": 5.0,
                "affect_mood": "平静",
                "affect_cause": "",
            }
        items_snapshot = [m.to_dict() for m in mind.items]
        plan_day = mind.plan_day
        plan_summary = mind.plan_summary
        plan_by_shichen = dict(mind.plan_by_shichen)
        affect_valence = float(mind.affect_valence)
        affect_arousal = float(mind.affect_arousal)
        affect_mood = mind.affect_mood
        affect_cause = mind.affect_cause
    return {
        "npc_id": npc_id,
        "npc_name": NPCS.get(npc_id, {}).get("name", npc_id),
        "items": items_snapshot,
        "importance_since_reflect": float(mind.importance_since_reflect),
        "plan_day": plan_day,
        "plan_summary": plan_summary,
        "plan_by_shichen": plan_by_shichen,
        "affect_valence": affect_valence,
        "affect_arousal": affect_arousal,
        "affect_mood": affect_mood,
        "affect_cause": affect_cause,
    }


@router.post("/api/agent/reflect", response_model=AgentReflectResponse)
async def agent_reflect(body: AgentActBody):
    from backend.session.store import room
    p = room.players.get(body.player_id)
    if not p:
        raise HTTPException(404, "未知 player_id")
    if p.dead:
        raise HTTPException(400, "角色已故，无法进行反思")
    if p.ended:
        raise HTTPException(400, "本局已收束，无法操作")
    if int(getattr(p, "unconscious_ticks", 0) or 0) > 0:
        raise HTTPException(409, "你正处于昏迷状态，无法进行反思")
    if getattr(p, "enslaved", False):
        raise HTTPException(403, "你正被奴役，无法自由反思")
    npc = NPCS.get(body.npc_id)
    if not npc:
        raise HTTPException(404, "未知 npc_id")
    async with p.lock:
        mind = get_or_init_mind(p, body.npc_id)
    new_refls = await agent_brain.reflect(
        npc_id=body.npc_id,
        npc_name=npc.get("name", body.npc_id),
        npc_blurb=str(npc.get("short", "")),
        mind=mind,
        world_day=int(p.world_day),
        world_shichen=shichen_name(p.world_shichen),
    )
    return {
        "added": [m.to_dict() for m in new_refls],
        "count": len(new_refls),
        "player": _player_public(p),
    }


@router.post("/api/agent/plan", response_model=AgentPlanResponse)
async def agent_plan(body: AgentActBody):
    from backend.session.store import room
    p = room.players.get(body.player_id)
    if not p:
        raise HTTPException(404, "未知 player_id")
    if p.dead:
        raise HTTPException(400, "角色已故，无法制定计划")
    if p.ended:
        raise HTTPException(400, "本局已收束，无法操作")
    if int(getattr(p, "unconscious_ticks", 0) or 0) > 0:
        raise HTTPException(409, "你正处于昏迷状态，无法制定计划")
    if getattr(p, "enslaved", False):
        raise HTTPException(403, "你正被奴役，无法自由规划")
    npc = NPCS.get(body.npc_id)
    if not npc:
        raise HTTPException(404, "未知 npc_id")
    async with p.lock:
        mind = get_or_init_mind(p, body.npc_id)
    ok = await agent_brain.plan_day(
        npc_id=body.npc_id,
        npc_name=npc.get("name", body.npc_id),
        npc_blurb=str(npc.get("short", "")),
        mind=mind,
        world_day=int(p.world_day),
    )
    return {
        "ok": ok,
        "plan_day": mind.plan_day,
        "plan_summary": mind.plan_summary,
        "plan_by_shichen": dict(mind.plan_by_shichen),
        "player": _player_public(p),
    }


@router.post("/api/agent/act", response_model=AgentActResponse)
async def agent_act(body: AgentActBody):
    from backend.session.store import room
    p = room.players.get(body.player_id)
    if not p:
        raise HTTPException(404, "未知 player_id")
    if p.dead:
        raise HTTPException(400, "角色已故，无法行动")
    if p.ended:
        raise HTTPException(400, "本局已收束，无法操作")
    npc = NPCS.get(body.npc_id)
    if not npc:
        raise HTTPException(404, "未知 npc_id")
    async with p.lock:
        mind = get_or_init_mind(p, body.npc_id)
        result = await execute_plan_step_async(p, body.npc_id, mind)
    return {
        "action": result.action_type.value,
        "description": result.description,
        "success": result.success,
        "mind_summary": mind.plan_summary,
        "player": _player_public(p),
        "npcs_here": _npcs_here(p),
    }


@router.post("/api/agent/act_loop", response_model=AgentActLoopResponse)
async def agent_act_loop(body: AgentActLoopBody):
    from backend.session.store import room
    p = room.players.get(body.player_id)
    if not p:
        raise HTTPException(404, "未知 player_id")
    if p.dead:
        raise HTTPException(400, "角色已故，无法行动")
    if p.ended:
        raise HTTPException(400, "本局已收束，无法操作")
    npc = NPCS.get(body.npc_id)
    if not npc:
        raise HTTPException(404, "未知 npc_id")
    async with p.lock:
        mind = get_or_init_mind(p, body.npc_id)
        before_reflect_at = mind.last_reflect_at
        results = await act_loop(p, body.npc_id, mind, max_steps=body.max_steps)
        reflected = mind.last_reflect_at != before_reflect_at
    return {
        "steps": [
            {"action": r.action_type.value, "description": r.description, "success": r.success}
            for r in results
        ],
        "total_steps": len(results),
        "reflected": reflected,
        "player": _player_public(p),
    }


@router.post("/api/agent/act_loop_stream")
async def agent_act_loop_stream(body: AgentActLoopStreamBody) -> StreamingResponse:
    from backend.session.store import room
    p = room.players.get(body.player_id)
    if not p:
        raise HTTPException(404, "未知 player_id")
    if p.dead:
        raise HTTPException(400, "角色已故，无法行动")
    if p.ended:
        raise HTTPException(400, "本局已收束，无法操作")
    npc = NPCS.get(body.npc_id)
    if not npc:
        raise HTTPException(404, "未知 npc_id")

    async def event_gen():
        from backend.agents.actor import NpcAction, decide_next_action, execute_plan_step_async
        from backend.agents.game_state import get_or_init_mind
        from backend.observability.tracker import CallRecord
        from backend.observability.tracker import get_tracker as _get_tracker

        t0 = time.perf_counter()
        total_steps = 0
        reflected = False

        async with p.lock:
            mind = get_or_init_mind(p, body.npc_id)
            before_reflect_at = mind.last_reflect_at

            for step_i in range(body.max_steps):
                action = decide_next_action(mind, p, body.npc_id)
                if action == NpcAction.IDLE:
                    yield _sse({"step": total_steps, "action": "idle", "description": "无事可做", "success": True, "done": False})
                    break

                result = await execute_plan_step_async(p, body.npc_id, mind)
                total_steps += 1

                if result.action_type == NpcAction.TALK and result.success and result.description:
                    lines = result.description.split("\n")
                    for line in lines:
                        if line.strip():
                            yield _sse({"step": total_steps, "action": "talk_chunk", "chunk": line.strip(), "done": False})
                            await asyncio.sleep(0.02)
                    yield _sse({"step": total_steps, "action": "talk", "description": result.description, "success": result.success, "done": False})
                else:
                    yield _sse({
                        "step": total_steps,
                        "action": result.action_type.value,
                        "description": result.description,
                        "success": result.success,
                        "done": False,
                    })

                if mind.needs_reflect():
                    try:
                        from backend.agents import brain as agent_brain
                        npc_meta = NPCS.get(body.npc_id, {})
                        await agent_brain.reflect(
                            npc_id=body.npc_id,
                            npc_name=npc_meta.get("name", body.npc_id),
                            npc_blurb=str(npc_meta.get("short", "")),
                            mind=mind,
                            world_day=int(p.world_day),
                            world_shichen=shichen_name(p.world_shichen),
                        )
                        reflected = True
                        yield _sse({"step": total_steps, "action": "reflect", "done": False})
                    except Exception as e:
                        logging.getLogger("agent_actor").warning("stream reflect failed for %s: %s", body.npc_id, e)

                await asyncio.sleep(0.3)

            reflected = mind.last_reflect_at != before_reflect_at

        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        _get_tracker().record(CallRecord(
            timestamp=time.time(),
            operation="act_loop_stream",
            model="",
            player_id=body.player_id,
            npc_id=body.npc_id,
            latency_ms=elapsed_ms,
            status="success",
            parse_success=True,
        ))

        yield _sse({
            "done": True,
            "total_steps": total_steps,
            "reflected": reflected,
            "player": _player_public(p),
            "npcs_here": _npcs_here(p),
        })

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/api/finale", response_model=FinaleResponse)
async def finale(body: FinaleBody):
    from backend.data.prompts import FIXED_INTRO
    from backend.session.store import room
    p = room.players.get(body.player_id)
    if not p:
        raise HTTPException(404, "未知 player_id")
    if p.dead:
        raise HTTPException(400, "已身亡，无法收束成文。请新开周目")
    if getattr(p, "enslaved", False):
        raise HTTPException(403, "你正被奴役，无法自主收束")
    if p.ended:
        return {
            "ending_label": p.ending_label,
            "epilogue": None,
            "already": True,
            "player": _player_public(p),
            "server_ms": 0,
        }

    # 构建 story digest
    inv_line = "身无长物" if not p.inventory else "随身:" + "、".join(
        (f"{n}×{c}" if c > 1 else n) for n, c in sorted(p.inventory.items())
    )
    rep_line = " ".join(f"{FACTIONS.get(k, k)}{v:+d}" for k, v in p.reputation.items() if v != 0) or "声望未起"
    from backend.data.maps_data import MAPS
    lines = [
        FIXED_INTRO, "",
        f"玩家性别:{p.gender};真实江湖(永久死亡):{'开' if p.permadeath else '关'}，",
        f"终局前最后位置，地图「{MAPS.get(p.map_id, {}).get('name', '未知之地')}」坐标({p.px},{p.py});持{p.coins} 文钱",
        f"江湖行迹至第 {p.world_day} 日· {shichen_name(p.world_shichen)}(天气「{p.weather}」)",
        f"{inv_line}。{rep_line}", "",
        SOCIETY_BIBLE, "",
        "-- 本局对话摘录(按角色) --", "",
    ]
    from backend.data.npcs_data import STORY_ORDER
    any_talk = False
    for nid in STORY_ORDER:
        hist = p.history.get(nid)
        if not hist:
            continue
        any_talk = True
        name = NPCS.get(nid, {}).get("name", nid)
        for turn in hist:
            u = str(turn.get("user", ""))[:1400]
            a = str(turn.get("assistant", ""))[:1400]
            stamp = ""
            if turn.get("day") and turn.get("shichen"):
                stamp = f"〔第{turn['day']}日·{turn['shichen']}〕"  # type: ignore[index]
            lines.append(f"{stamp}【{name}】玩家：{u}")
            lines.append(f"{stamp}【{name}】：{a}")
            lines.append("")
    if p.events:
        lines.append("-- 本局世界事件(节选) --")
        for e in p.events[-12:]:
            lines.append(f"〔第{e.get('day','?')}日·{e.get('shichen','?')}〕{e.get('text','')}")
        lines.append("")
    if not any_talk:
        lines.append("(尚未产生对话;请据社会总览与开场写收束文)")
    lines.append(
        f"-- 叙事参考数据(勿在正文复述数字)--\n"
        f"秩序 {p.flags.get('order', 0)}  求真 {p.flags.get('truth', 0)}  "
        f"希望 {p.flags.get('hope', 0)}  混乱 {p.flags.get('chaos', 0)}"
    )
    unconscious_ticks = int(getattr(p, "unconscious_ticks", 0) or 0)
    if unconscious_ticks > 0:
        lines.append(f"\n-- 此刻玩家正处于昏迷状态(剩余约{unconscious_ticks}时辰) --")
        lines.append("请据此写出一个与昏迷相关的结局：可能是在昏迷中离世、被路人救起后醒转、或在梦境中走完最后一程。")
    if getattr(p, "move_locked", False):
        trap_reason = getattr(p, "trap_reason", None)
        trap_type = getattr(p, "trap_type", "npc") or "npc"
        if trap_type == "environment" and trap_reason:
            lines.append(f"\n-- 此刻玩家身陷环境险境：{trap_reason} --")
            lines.append("请据此写出结局：可能是在险境中丧生、侥幸脱困、或被他人搭救。")
    digest = "\n".join(lines)

    extra = (body.closing_note or "").strip()
    user_block = digest
    if extra:
        user_block += f"\n\n-- 玩家对收束的额外说明 --\n{extra}"

    messages = [
        {
            "role": "system",
            "content": (
                f"你是「{WORLD_NAME}」江湖的终局叙事者。\n"
                "尊重社会总览、世界事件流与对话摘要，收束时世界仍可继续运转。\n"
                "正文 220~420 字，第二人称「你」，不要列出数字，不要出现 STATE_UPDATE / PERMADEATH / EVENT 等机读行。\n"
                "落笔时把【世态此刻】、时辰、天气与玩家身上钱物落到环境笔触里,让结局有此地此夜的呼吸。\n"
                "正文结束后，*另起一行*:ENDING_TITLE: 六字到十四字标题(无书名号)"
            ),
        },
        {"role": "user", "content": user_block},
    ]
    t0 = time.perf_counter()
    try:
        raw = await asyncio.wait_for(
            chat_completion(messages, temperature=FINALE_TEMPERATURE, max_tokens=FINALE_MAX_TOKENS),
            timeout=90.0,
        )
    except TimeoutError:
        raise HTTPException(504, "终局叙事超时，请稍后重试") from None
    epilogue, title = parse_finale(raw)
    if not title:
        title = "无名之夜"

    async with p.lock:
        p.ended = True
        p.ending_label = title
        player_data = _player_public(p)

    server_ms = int((time.perf_counter() - t0) * 1000)
    return {
        "ending_label": title,
        "epilogue": epilogue.strip(),
        "flags": p.flags,
        "player": player_data,
        "server_ms": server_ms,
    }


# ── 悬赏榜 API ──
from backend.systems.bounty_board import (
    abandon_bounty,
    accept_bounty,
    check_bounty_progress,
    complete_bounty,
    format_bounty_board,
    generate_bounties,
    refresh_bounties,
)
from backend.systems.constants import BOUNTY_COUNT_RANGE
from backend.systems.task_fsm import TaskFSM


class RefreshBountyBody(BaseModel):
    player_id: str = _PID

class AcceptBountyBody(BaseModel):
    player_id: str = _PID
    bounty_id: str = Field(..., min_length=1, max_length=32)

class CompleteBountyBody(BaseModel):
    player_id: str = _PID

class AbandonBountyBody(BaseModel):
    player_id: str = _PID


@router.post("/api/bounty/refresh", response_model=BountyRefreshResponse)
async def bounty_refresh(body: RefreshBountyBody):
    p = _get_active_player(body.player_id)
    async with p.lock:
        refresh_bounties(p)
        if not p.bounties:
            p.bounties = generate_bounties(p, count=random.randint(*BOUNTY_COUNT_RANGE))
        board_text = format_bounty_board(p)
        return {"bounties": p.bounties, "board_text": board_text, "player": _player_public(p)}


@router.post("/api/bounty/accept", response_model=BountyAcceptResponse)
async def bounty_accept(body: AcceptBountyBody):
    p = _get_active_player(body.player_id)
    async with p.lock:
        ok, msg = accept_bounty(p, body.bounty_id)
        return {"ok": ok, "message": msg, "player": _player_public(p)}


@router.post("/api/bounty/check", response_model=BountyCheckResponse)
async def bounty_check(body: CompleteBountyBody):
    p = _get_active_player(body.player_id)
    async with p.lock:
        progress = check_bounty_progress(p)
        if progress is None:
            return {"has_active": False, "player": _player_public(p)}
        return {"has_active": True, **progress, "player": _player_public(p)}


@router.post("/api/bounty/complete", response_model=BountyCompleteResponse)
async def bounty_complete(body: CompleteBountyBody):
    p = _get_active_player(body.player_id)
    async with p.lock:
        ok, msg, reward = complete_bounty(p)
        return {"ok": ok, "message": msg, "reward": reward, "player": _player_public(p)}


@router.post("/api/bounty/abandon", response_model=BountyAbandonResponse)
async def bounty_abandon(body: AbandonBountyBody):
    p = _get_active_player(body.player_id)
    async with p.lock:
        ok, msg = abandon_bounty(p)
        return {"ok": ok, "message": msg, "player": _player_public(p)}


@router.get("/api/bounty/{player_id}/{bounty_id}/state", response_model=BountyStateResponse)
async def bounty_state(
    player_id: str = Path(..., min_length=1, max_length=64),
    bounty_id: str = Path(..., min_length=1, max_length=64),
):
    p = _get_active_player(player_id)
    bounty = None
    if p.active_bounty and p.active_bounty.get("id") == bounty_id:
        bounty = p.active_bounty
    if not bounty:
        bounty = next((b for b in (p.bounties or []) if b["id"] == bounty_id), None)
    if not bounty:
        raise HTTPException(404, "悬赏不存在")

    fsm_data = bounty.get("task_fsm")
    if not fsm_data:
        raise HTTPException(400, "该悬赏无 FSM 状态")

    fsm = TaskFSM.from_dict(fsm_data)
    return {
        "bounty_id": bounty_id,
        "state": fsm.current_state.value,
        "sub_steps": fsm.sub_steps,
        "completed_steps": fsm.completed_steps,
        "transition_log": fsm.transition_log,
    }
