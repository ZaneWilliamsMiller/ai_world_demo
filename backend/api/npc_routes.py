"""NPC 对话 API 路由：npc_talk, npc_talk_stream, item/use, rest, agent, finale, bounty。"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.data.npcs_data import NPCS
from backend.data.factions import FACTIONS
from backend.data.prompts import WORLD_NAME, SOCIETY_BIBLE
from backend.systems.core import npc_ids_for_player, perception_scan, danger_sense_narrative
from backend.game_state import get_or_init_mind
from backend.services.talk_service import build_npc_messages, apply_npc_reply, build_graceful_fallback
from backend.services.agent_service import bg_reflect
from backend import agent_brain
from backend.llm_client import chat_completion, parse_finale, parse_npc_reply_json
from backend.views import player_public as _player_public, factions_public as _factions_public

router = APIRouter()


class TalkBody(BaseModel):
    player_id: str
    npc_id: str = Field(..., min_length=1, max_length=32)
    message: str = Field(..., min_length=1, max_length=2000)

class UseItemBody(BaseModel):
    player_id: str
    item: str = Field(..., min_length=1, max_length=20, description="物品名")

class RestBody(BaseModel):
    player_id: str

class FinaleBody(BaseModel):
    player_id: str
    closing_note: str | None = Field(None, max_length=600)

class AgentActBody(BaseModel):
    player_id: str
    npc_id: str = Field(..., min_length=1, max_length=32)


def _sse(obj: dict[str, Any]) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


@router.post("/api/item/use")
async def use_item(body: UseItemBody) -> dict[str, Any]:
    from backend.session.store import room
    p = room.players.get(body.player_id)
    if not p:
        raise HTTPException(404, f"未知 player_id: {body.player_id}")
    if getattr(p, "dead", False):
        raise HTTPException(400, "角色已故，物无所用。")

    from backend.systems.economy import use_player_item
    result = use_player_item(p, body.item)

    if result.get("success"):
        from backend.systems.reputation import push_event
        item_name = str(result.get("item_consumed", body.item))
        note = str(result.get("note", ""))
        if note:
            push_event(p, f"{p.display_name}用掉了{note}", scope="self", actor=p.display_name)

    return {
        **result,
        "player": _player_public(p),
    }


@router.post("/api/rest")
async def player_rest(body: RestBody) -> dict[str, Any]:
    from backend.session.store import room
    from backend.data.atmosphere import scene_context
    p = room.players.get(body.player_id)
    if not p:
        raise HTTPException(404, f"未知 player_id: {body.player_id}")
    if getattr(p, "dead", False):
        raise HTTPException(400, "魂已归西，无足歇矣。")
    if p.ended:
        raise HTTPException(400, "本局已收束")
    if int(getattr(p, "unconscious_ticks", 0) or 0) > 0:
        raise HTTPException(400, "昏迷之中，身不由己。")
    if getattr(p, "move_locked", False):
        raise HTTPException(409, "身陷险局，须先周旋脱身方可歇息。")

    from backend.systems.core import rest_at_location
    async with p.lock:
        result = rest_at_location(p)
        try:
            from backend.systems.save_system import save_game
            save_game(p)
        except Exception:
            pass

    scan = perception_scan(p)
    danger_sense = danger_sense_narrative(p, scan) if scan else None
    return {
        **result,
        "player": _player_public(p),
        "danger_sense": {
            "alert": danger_sense or None,
            "scan": scan,
        },
        "atmosphere": scene_context(p),
        "events": list(p.events[-5:]),
    }


@router.post("/api/npc/talk")
async def npc_talk(body: TalkBody, bg: BackgroundTasks) -> dict[str, Any]:
    from backend.session.store import room
    p = room.players.get(body.player_id)
    if not p:
        raise HTTPException(404, "未知 player_id")
    if p.ended:
        raise HTTPException(400, "本局已收束")
    if p.dead:
        raise HTTPException(400, "角色已身故,无法交谈")

    npc = NPCS.get(body.npc_id)
    if not npc:
        raise HTTPException(400, "未知 npc")

    allowed = set(npc_ids_for_player(p))
    if body.npc_id not in allowed:
        raise HTTPException(400, "此人不在你当前这一格(或不可交谈)。请先移动贴近。")

    async with p.lock:
        hist = p.history.setdefault(body.npc_id, [])
        hist_slice = list(hist[-14:])

    import backend.systems.prompt_compress as _pc
    if len(hist_slice) >= _pc.COMPRESS_THRESHOLD:
        hist_slice = await _pc.compress_conversation_history(
            hist_slice, npc_name=NPCS.get(body.npc_id, {}).get("name", ""))

    messages = build_npc_messages(p, body.npc_id, body.message, hist_slice)
    t0 = time.perf_counter()

    is_light_inquiry = body.message.startswith("[系统指令·问路")
    is_fallback = False
    try:
        raw = await chat_completion(
            messages,
            temperature=0.85,
            max_tokens=450 if is_light_inquiry else 800,
            response_format={"type": "json_object"}
        )
        parsed = parse_npc_reply_json(raw)
    except Exception as e:
        is_fallback = True
        fallback = build_graceful_fallback(body.npc_id, f"{type(e).__name__}: {e}")
        parsed = fallback["parsed"]
        import logging
        logging.getLogger("api.routes").warning(
            "LLM fallback for npc=%s player=%s: %s",
            body.npc_id, body.player_id, str(e)[:120]
        )

    async with p.lock:
        out, needs_reflect = apply_npc_reply(p, body.npc_id, body.message, parsed)
        p.last_talk_npc_id = body.npc_id
        p.last_talk_message = body.message

    if needs_reflect and not is_light_inquiry and not is_fallback:
        bg.add_task(bg_reflect, p.player_id, body.npc_id)

    out["server_ms"] = int((time.perf_counter() - t0) * 1000)
    if is_fallback:
        out["llm_fallback"] = True
    return out


@router.post("/api/npc/talk_stream")
async def npc_talk_stream(body: TalkBody, bg: BackgroundTasks) -> StreamingResponse:
    from backend.session.store import room
    p = room.players.get(body.player_id)
    if not p:
        raise HTTPException(404, "未知 player_id")
    if p.ended:
        raise HTTPException(400, "本局已收束")
    if p.dead:
        raise HTTPException(400, "角色已身故,无法交谈")
    npc = NPCS.get(body.npc_id)
    if not npc:
        raise HTTPException(400, "未知 npc")
    allowed = set(npc_ids_for_player(p))
    if body.npc_id not in allowed:
        raise HTTPException(400, "此人不在你当前这一格(或不可交谈)。请先移动贴近。")

    async with p.lock:
        hist = p.history.setdefault(body.npc_id, [])
        hist_slice = list(hist[-14:])

    import backend.systems.prompt_compress as _pc
    if len(hist_slice) >= _pc.COMPRESS_THRESHOLD:
        hist_slice = await _pc.compress_conversation_history(
            hist_slice, npc_name=NPCS.get(body.npc_id, {}).get("name", ""))

    messages = build_npc_messages(p, body.npc_id, body.message, hist_slice)

    async def event_gen():
        t0 = time.perf_counter()
        try:
            is_light = body.message.startswith("[系统指令·问路")
            raw = await chat_completion(
                messages,
                temperature=0.85,
                max_tokens=450 if is_light else 800,
                response_format={"type": "json_object"},
            )
            parsed = parse_npc_reply_json(raw)
        except Exception as e:
            fb = build_graceful_fallback(body.npc_id, str(e))
            parsed = fb["parsed"]
            import logging
            logging.getLogger("api.routes").warning(
                "LLM fallback (stream) for npc=%s player=%s: %s",
                body.npc_id, body.player_id, str(e)[:120]
            )
            vis = (parsed.visible_text or "").strip()
            if vis:
                for i in range(0, len(vis), 16):
                    yield _sse({"chunk": vis[i : i + 16]})
                    await asyncio.sleep(0.01)
            try:
                async with p.lock:
                    out, _ = apply_npc_reply(p, body.npc_id, body.message, parsed)
                    p.last_talk_npc_id = body.npc_id
                    p.last_talk_message = body.message
            except Exception:
                out = {}
            out["server_ms"] = int((time.perf_counter() - t0) * 1000)
            out["llm_fallback"] = True
            yield _sse({"done": True, **out})
            return

        vis = (parsed.visible_text or "").strip()
        if vis:
            chunk_size = 16
            for i in range(0, len(vis), chunk_size):
                yield _sse({"chunk": vis[i : i + chunk_size]})
                await asyncio.sleep(0.01)

        try:
            async with p.lock:
                out, needs_reflect = apply_npc_reply(p, body.npc_id, body.message, parsed)
                p.last_talk_npc_id = body.npc_id
                p.last_talk_message = body.message
        except Exception as e:
            yield _sse({"error": f"状态写入失败:{e}", "fatal": True})
            return

        if needs_reflect:
            bg.add_task(bg_reflect, p.player_id, body.npc_id)
        out["server_ms"] = int((time.perf_counter() - t0) * 1000)
        yield _sse({"done": True, **out})

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get("/api/agent/{player_id}/{npc_id}/mind")
async def agent_mind(player_id: str, npc_id: str) -> dict[str, Any]:
    from backend.session.store import room
    from backend.systems.time_weather import shichen_name
    p = room.players.get(player_id)
    if not p:
        raise HTTPException(404, "未知 player_id")
    if npc_id not in NPCS:
        raise HTTPException(404, "未知 npc_id")
    mind = p.minds.get(npc_id)
    if mind is None:
        return {
            "npc_id": npc_id,
            "npc_name": NPCS[npc_id]["name"],
            "items": [],
            "plan_day": None,
            "plan_summary": "",
            "plan_by_shichen": {},
            "affect_valence": 0.0,
            "affect_arousal": 5.0,
            "affect_mood": "平静",
            "affect_cause": "",
        }
    return {
        "npc_id": npc_id,
        "npc_name": NPCS[npc_id]["name"],
        "items": [m.to_dict() for m in mind.items],
        "importance_since_reflect": float(mind.importance_since_reflect),
        "plan_day": mind.plan_day,
        "plan_summary": mind.plan_summary,
        "plan_by_shichen": dict(mind.plan_by_shichen),
        "affect_valence": float(mind.affect_valence),
        "affect_arousal": float(mind.affect_arousal),
        "affect_mood": mind.affect_mood,
        "affect_cause": mind.affect_cause,
    }


@router.post("/api/agent/reflect")
async def agent_reflect(body: AgentActBody) -> dict[str, Any]:
    from backend.session.store import room
    from backend.systems.time_weather import shichen_name
    p = room.players.get(body.player_id)
    if not p:
        raise HTTPException(404, "未知 player_id")
    npc = NPCS.get(body.npc_id)
    if not npc:
        raise HTTPException(404, "未知 npc_id")
    mind = get_or_init_mind(p, body.npc_id)
    new_refls = await agent_brain.reflect(
        npc_id=body.npc_id,
        npc_name=npc["name"],
        npc_blurb=str(npc.get("short", "")),
        mind=mind,
        world_day=int(p.world_day),
        world_shichen=shichen_name(p.world_shichen),
    )
    return {
        "added": [m.to_dict() for m in new_refls],
        "count": len(new_refls),
    }


@router.post("/api/agent/plan")
async def agent_plan(body: AgentActBody) -> dict[str, Any]:
    from backend.session.store import room
    p = room.players.get(body.player_id)
    if not p:
        raise HTTPException(404, "未知 player_id")
    npc = NPCS.get(body.npc_id)
    if not npc:
        raise HTTPException(404, "未知 npc_id")
    mind = get_or_init_mind(p, body.npc_id)
    ok = await agent_brain.plan_day(
        npc_id=body.npc_id,
        npc_name=npc["name"],
        npc_blurb=str(npc.get("short", "")),
        mind=mind,
        world_day=int(p.world_day),
    )
    return {
        "ok": ok,
        "plan_day": mind.plan_day,
        "plan_summary": mind.plan_summary,
        "plan_by_shichen": dict(mind.plan_by_shichen),
    }


@router.post("/api/finale")
async def finale(body: FinaleBody) -> dict[str, Any]:
    from backend.session.store import room
    from backend.data.prompts import FIXED_INTRO
    p = room.players.get(body.player_id)
    if not p:
        raise HTTPException(404, "未知 player_id")
    if p.dead:
        raise HTTPException(400, "已身故,无法收束成文。请新开周目。")
    if p.ended:
        return {
            "ending_label": p.ending_label,
            "epilogue": None,
            "already": True,
            "server_ms": 0,
        }

    # 构建 story digest
    inv_line = "身无长物" if not p.inventory else "随身:" + "、".join(
        (f"{n}×{c}" if c > 1 else n) for n, c in sorted(p.inventory.items())
    )
    rep_line = " ".join(f"{FACTIONS[k]}{v:+d}" for k, v in p.reputation.items() if v != 0) or "声望未起"
    from backend.data.maps_data import MAPS
    lines = [
        FIXED_INTRO, "",
        f"玩家性别:{p.gender};真实江湖(永久死亡):{'开' if p.permadeath else '关'}。",
        f"终局前最后位置:地图「{MAPS[p.map_id]['name']}」坐标 ({p.px},{p.py});约 {p.coins} 文。",
        f"江湖行迹至第 {p.world_day} 日 · {shichen_name(p.world_shichen)}(天气「{p.weather}」)。",
        f"{inv_line}。{rep_line}", "",
        SOCIETY_BIBLE, "",
        "-- 本局对话摘录(按角色)--", "",
    ]
    from backend.data.npcs_data import STORY_ORDER
    any_talk = False
    for nid in STORY_ORDER:
        hist = p.history.get(nid)
        if not hist:
            continue
        any_talk = True
        name = NPCS[nid]["name"]
        for turn in hist:
            u = turn["user"][:1400]
            a = turn["assistant"][:1400]
            stamp = ""
            if turn.get("day") and turn.get("shichen"):
                stamp = f"〔第{turn['day']}日·{turn['shichen']}〕 "
            lines.append(f"{stamp}【{name}】玩家:{u}")
            lines.append(f"{stamp}【{name}】:{a}")
            lines.append("")
    if p.events:
        lines.append("-- 本局世界事件(节选)--")
        for e in p.events[-12:]:
            lines.append(f"〔第{e.get('day','?')}日·{e.get('shichen','?')}〕 {e.get('text','')}")
        lines.append("")
    if not any_talk:
        lines.append("(尚未产生对话;请据社会总览与开场写收束。)")
    lines.append(
        f"-- 叙事参考数值(勿在正文复述数字)--\n"
        f"秩序 {p.flags['order']}  求真 {p.flags['truth']}  "
        f"希望 {p.flags['hope']}  混乱 {p.flags['chaos']}"
    )
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
                "尊重社会总览、世界事件流与对话摘录;收束时世界仍可继续运转。\n"
                "正文 220~420 字,第二人称「你」;不要列出数值;不要出现 STATE_UPDATE / PERMADEATH / EVENT 等机读行。\n"
                "落笔时把【世态此刻】(时辰、天气)与玩家身上钱物落到环境笔触里,让结局有此地此夜的呼吸。\n"
                "正文结束后**另起一行**:ENDING_TITLE: 六字到十四字标题(无书名号)"
            ),
        },
        {"role": "user", "content": user_block},
    ]
    t0 = time.perf_counter()
    raw = await chat_completion(messages, temperature=0.95, max_tokens=900)
    epilogue, title = parse_finale(raw)
    if not title:
        title = "无名之夜"

    async with p.lock:
        p.ended = True
        p.ending_label = title

    server_ms = int((time.perf_counter() - t0) * 1000)
    return {
        "ending_label": title,
        "epilogue": epilogue.strip(),
        "flags": p.flags,
        "server_ms": server_ms,
    }


# ── 悬赏榜 API ──
from backend.systems.bounty_board import (
    generate_bounties,
    can_accept_bounty,
    accept_bounty,
    check_bounty_progress,
    complete_bounty,
    abandon_bounty,
    format_bounty_board,
    refresh_bounties,
)

class RefreshBountyBody(BaseModel):
    player_id: str

class AcceptBountyBody(BaseModel):
    player_id: str
    bounty_id: str

class CompleteBountyBody(BaseModel):
    player_id: str

class AbandonBountyBody(BaseModel):
    player_id: str


@router.post("/api/bounty/refresh")
async def bounty_refresh(body: RefreshBountyBody) -> dict[str, Any]:
    from backend.session.store import room
    p = room.players.get(body.player_id)
    if not p:
        raise HTTPException(404, "未知 player_id")
    refresh_bounties(p)
    if not p.bounties:
        p.bounties = generate_bounties(p, count=3)
    board_text = format_bounty_board(p)
    return {"bounties": p.bounties, "board_text": board_text}


@router.post("/api/bounty/accept")
async def bounty_accept(body: AcceptBountyBody) -> dict[str, Any]:
    from backend.session.store import room
    p = room.players.get(body.player_id)
    if not p:
        raise HTTPException(404, "未知 player_id")
    ok, msg = accept_bounty(p, body.bounty_id)
    return {"ok": ok, "message": msg}


@router.post("/api/bounty/check")
async def bounty_check(body: CompleteBountyBody) -> dict[str, Any]:
    from backend.session.store import room
    p = room.players.get(body.player_id)
    if not p:
        raise HTTPException(404, "未知 player_id")
    progress = check_bounty_progress(p)
    if progress is None:
        return {"has_active": False}
    return {"has_active": True, **progress}


@router.post("/api/bounty/complete")
async def bounty_complete(body: CompleteBountyBody) -> dict[str, Any]:
    from backend.session.store import room
    p = room.players.get(body.player_id)
    if not p:
        raise HTTPException(404, "未知 player_id")
    ok, msg, reward = complete_bounty(p)
    return {"ok": ok, "message": msg, "reward": reward}


@router.post("/api/bounty/abandon")
async def bounty_abandon(body: AbandonBountyBody) -> dict[str, Any]:
    from backend.session.store import room
    p = room.players.get(body.player_id)
    if not p:
        raise HTTPException(404, "未知 player_id")
    ok, msg = abandon_bounty(p)
    return {"ok": ok, "message": msg}
