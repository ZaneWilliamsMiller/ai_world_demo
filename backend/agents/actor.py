"""NPC 行动执行引擎 —— Agent Loop 核心。

基于 NPC 当日计划，每步决定行动类型（移动/交谈/休息/空闲），
同步或异步执行，产出观察记忆写入记忆流。
"""
from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass
from enum import Enum

from backend import memory as mem
from backend.agents.brain import record_observation
from backend.data.npcs_data import NPCS
from backend.models.player import PlayerState
from backend.systems.time_weather import shichen_name

log = logging.getLogger("agent_actor")


class NpcAction(Enum):
    MOVE = "move"
    TALK = "talk"
    REST = "rest"
    IDLE = "idle"


@dataclass
class NpcActionResult:
    action_type: NpcAction
    description: str
    success: bool
    target_pos: tuple[str, int, int] | None = None
    raw_dialogue: list[dict] | None = None


_MOVE_KW = ("去", "往", "赴", "行", "走", "到", "回", "返")
_TALK_KW = ("见", "访", "谈", "聊", "问", "寻", "会", "商")
_REST_KW = ("歇", "息", "睡", "寐", "卧", "休", "憩")

_TALK_TEMPLATES = (
    "与{other}闲聊了几句{topic}",
    "向{other}打听了一下{topic}",
    "和{other}谈起了{topic}",
    "同{other}说起{topic}",
)

_TALK_TOPICS = (
    "近日的天气", "市面上的行情", "衙门的动静", "码头的消息",
    "江湖上的传闻", "书院的新论", "渡口的船期", "帮里的规矩",
    "驿路的消息", "厘卡的抽分",
)

_REST_TEMPLATES = (
    "找了个僻静处歇了歇脚",
    "靠在墙根闭目养神",
    "在檐下小坐片刻",
    "回房歇了一歇",
)

_NPC_TALK_SYSTEM = (
    "你是江湖世界中的NPC对话生成器。根据两个NPC的性格、关系和当前场景，"
    "生成一段简短自然的对话（2-4轮交流）。要求：\n"
    "1. 对话内容符合各自性格和说话风格\n"
    "2. 对话自然简短，像熟人碰面闲聊\n"
    "3. 可以涉及天气、市况、传闻、日常琐事\n"
    "4. 输出JSON格式：{\"dialogue\": [{\"speaker\": \"NPC简称\", \"line\": \"说的话\"}, ...]}\n"
    "5. 每人最多说2-3句，总共不超过6轮"
)


def _build_npc_talk_messages(
    npc_id: str,
    other_id: str,
    mind: mem.AgentMind,
    sh_name: str,
    world_day: int,
) -> list[dict[str, str]]:
    from backend.data.relationships import NPC_RELATIONSHIPS
    meta_a = NPCS.get(npc_id, {})
    meta_b = NPCS.get(other_id, {})
    name_a = meta_a.get("short", npc_id)
    name_b = meta_b.get("short", other_id)
    char_a = meta_a.get("character", {})
    char_b = meta_b.get("character", {})

    rel_note = ""
    rels = NPC_RELATIONSHIPS.get(npc_id, [])
    for r in rels:
        if r.get("target") == other_id:
            rel_note = f"关系：{r.get('attitude', '陌生')}——{r.get('note', '')}"
            break

    plan_text = mind.plan_by_shichen.get(sh_name, "")
    mood_text = ""
    if mind.affect_mood:
        mood_text = f"当前心境：{mind.affect_mood}"
        if mind.affect_cause:
            mood_text += f"（{mind.affect_cause}）"

    user_parts = [
        f"场景：{sh_name}，第{world_day}日",
        f"NPC甲【{name_a}】：{char_a.get('说话风格', meta_a.get('system', '')[:60])}",
        f"NPC乙【{name_b}】：{char_b.get('说话风格', meta_b.get('system', '')[:60])}",
    ]
    if rel_note:
        user_parts.append(rel_note)
    if plan_text:
        user_parts.append(f"{name_a}今日计划涉及：{plan_text[:40]}")
    if mood_text:
        user_parts.append(f"{name_a}{mood_text}")

    user_parts.append(f"请生成{name_a}与{name_b}的简短对话。")

    return [
        {"role": "system", "content": _NPC_TALK_SYSTEM},
        {"role": "user", "content": "\n".join(user_parts)},
    ]


def decide_next_action(mind: mem.AgentMind, p: PlayerState, npc_id: str) -> NpcAction:
    """读取当前时辰的计划项决定行动。"""
    from backend.systems.npc_state import _parse_plan_target

    sh_name = shichen_name(p.world_shichen)
    plan = mind.plan_by_shichen.get(sh_name, "")
    if not plan:
        return NpcAction.IDLE

    has_move = any(kw in plan for kw in _MOVE_KW)
    has_rest = any(kw in plan for kw in _REST_KW)
    has_talk = any(kw in plan for kw in _TALK_KW)

    if has_move:
        target = _parse_plan_target(plan)
        if target is not None:
            cur_pos = p.npc_positions.get(npc_id)
            if cur_pos and isinstance(cur_pos, (list, tuple)) and len(cur_pos) >= 3:
                cm, cx, cy = str(cur_pos[0]), int(cur_pos[1]), int(cur_pos[2])
                tm, tx, ty = target
                if cm == tm and abs(cx - tx) + abs(cy - ty) <= 2:
                    pass
                else:
                    return NpcAction.MOVE

    if has_rest:
        return NpcAction.REST
    if has_talk:
        return NpcAction.TALK
    return NpcAction.IDLE


def execute_plan_step(p: PlayerState, npc_id: str, mind: mem.AgentMind) -> NpcActionResult:
    """同步执行一步计划。"""
    action = decide_next_action(mind, p, npc_id)
    sh_name = shichen_name(p.world_shichen)
    world_day = int(p.world_day)
    meta = NPCS.get(npc_id, {})
    npc_short = meta.get("short", npc_id)

    if action == NpcAction.IDLE:
        return NpcActionResult(
            action_type=NpcAction.IDLE,
            description=f"{npc_short}无事可做",
            success=True,
        )

    pos_snapshot = p.npc_positions.get(npc_id)
    old_pos = pos_snapshot
    try:
        if action == NpcAction.MOVE:
            return _execute_move(p, npc_id, mind, sh_name, world_day, npc_short)
        if action == NpcAction.TALK:
            return _execute_talk(p, npc_id, mind, sh_name, world_day, npc_short)
        if action == NpcAction.REST:
            return _execute_rest(mind, sh_name, world_day, npc_short)
    except Exception as e:
        if old_pos is not None:
            p.npc_positions[npc_id] = old_pos
        log.warning("action rollback for npc=%s: %s", npc_id, e)
        try:
            from backend.observability.tracker import get_tracker, CallRecord
            import time as _time
            awaitable = get_tracker().record(CallRecord(
                timestamp=_time.time(),
                operation="npc_action_rollback",
                model="",
                player_id=p.player_id,
                npc_id=npc_id,
                parse_success=False,
                schema_violations=["action_rollback"],
                latency_ms=0,
                status="error",
            ))
            import asyncio
            asyncio.get_event_loop().create_task(awaitable)
        except Exception:
            pass
        return NpcActionResult(
            action_type=action,
            description=f"{npc_short}行动异常",
            success=False,
        )

    return NpcActionResult(action_type=NpcAction.IDLE, description="未知行动", success=False)


def _execute_move(
    p: PlayerState,
    npc_id: str,
    mind: mem.AgentMind,
    sh_name: str,
    world_day: int,
    npc_short: str,
) -> NpcActionResult:
    """执行移动行动：向计划中的目标地点移动一步。"""
    from backend.systems.npc_state import plan_driven_step

    new_pos = plan_driven_step(p, npc_id, mind)
    if new_pos is None:
        desc = f"{npc_short}已在目的地附近"
        record_observation(mind, desc, world_day=world_day, world_shichen=sh_name, importance=2.0)
        return NpcActionResult(
            action_type=NpcAction.MOVE,
            description=desc,
            success=False,
        )

    p.npc_positions[npc_id] = new_pos
    desc = f"{npc_short}向计划地点移动了一步"
    record_observation(mind, desc, world_day=world_day, world_shichen=sh_name, importance=2.5)
    return NpcActionResult(
        action_type=NpcAction.MOVE,
        description=desc,
        success=True,
        target_pos=new_pos,
    )


def _execute_talk(
    p: PlayerState,
    npc_id: str,
    mind: mem.AgentMind,
    sh_name: str,
    world_day: int,
    npc_short: str,
) -> NpcActionResult:
    try:
        return asyncio.run(_execute_talk_async(p, npc_id, mind, sh_name, world_day, npc_short))
    except RuntimeError:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(
                asyncio.run,
                _execute_talk_async(p, npc_id, mind, sh_name, world_day, npc_short)
            ).result()


async def _execute_talk_async(
    p: PlayerState,
    npc_id: str,
    mind: mem.AgentMind,
    sh_name: str,
    world_day: int,
    npc_short: str,
) -> NpcActionResult:
    cur_pos = p.npc_positions.get(npc_id)
    if not cur_pos or not isinstance(cur_pos, (list, tuple)) or len(cur_pos) < 3:
        return NpcActionResult(
            action_type=NpcAction.TALK,
            description=f"{npc_short}无处可谈",
            success=False,
        )

    mid, cx, cy = str(cur_pos[0]), int(cur_pos[1]), int(cur_pos[2])
    others: list[str] = []
    for oid, opos in p.npc_positions.items():
        if oid == npc_id:
            continue
        if not isinstance(opos, (list, tuple)) or len(opos) < 3:
            continue
        if str(opos[0]) == mid and int(opos[1]) == cx and int(opos[2]) == cy:
            others.append(oid)

    if not others:
        desc = f"{npc_short}四下无人，无人可谈"
        record_observation(mind, desc, world_day=world_day, world_shichen=sh_name, importance=1.5)
        return NpcActionResult(
            action_type=NpcAction.TALK,
            description=desc,
            success=False,
        )

    other_id = random.choice(others)
    other_name = NPCS.get(other_id, {}).get("short", other_id)
    topic = random.choice(_TALK_TOPICS)
    template = random.choice(_TALK_TEMPLATES)
    fallback_desc = template.format(other=other_name, topic=topic)

    dialogue_lines: list[str] = []
    raw_dialogue: list[dict] = []
    try:
        from backend.llm.client import chat_completion
        import json as _json
        messages = _build_npc_talk_messages(npc_id, other_id, mind, sh_name, world_day)
        raw = await chat_completion(
            messages,
            temperature=0.7,
            max_tokens=256,
            response_format={"type": "json_object"},
        )
        parsed = _json.loads(raw)
        for entry in parsed.get("dialogue", []):
            speaker = entry.get("speaker", "")
            line = entry.get("line", "")
            if speaker and line:
                dialogue_lines.append(f"{speaker}：「{line}」")
                raw_dialogue.append({"speaker": speaker, "line": line})
    except Exception as e:
        log.warning("NPC talk LLM failed for %s->%s: %s, using template", npc_id, other_id, e)
        dialogue_lines = []
        raw_dialogue = []

    if dialogue_lines:
        desc = "\n".join(dialogue_lines)
    else:
        desc = fallback_desc

    record_observation(mind, desc, world_day=world_day, world_shichen=sh_name, importance=3.0)
    return NpcActionResult(
        action_type=NpcAction.TALK,
        description=desc,
        success=True,
        target_pos=None,
        raw_dialogue=raw_dialogue if raw_dialogue else None,
    )


def _execute_rest(
    mind: mem.AgentMind,
    sh_name: str,
    world_day: int,
    npc_short: str,
) -> NpcActionResult:
    """执行休息行动：生成休息记忆。"""
    desc = f"{npc_short}{random.choice(_REST_TEMPLATES)}"
    record_observation(mind, desc, world_day=world_day, world_shichen=sh_name, importance=2.0)
    return NpcActionResult(
        action_type=NpcAction.REST,
        description=desc,
        success=True,
    )


async def execute_plan_step_async(
    p: PlayerState, npc_id: str, mind: mem.AgentMind,
) -> NpcActionResult:
    action = decide_next_action(mind, p, npc_id)
    sh_name = shichen_name(p.world_shichen)
    world_day = int(p.world_day)
    meta = NPCS.get(npc_id, {})
    npc_short = meta.get("short", npc_id)

    if action == NpcAction.IDLE:
        return NpcActionResult(
            action_type=NpcAction.IDLE,
            description=f"{npc_short}无事可做",
            success=True,
        )

    pos_snapshot = p.npc_positions.get(npc_id)
    old_pos = pos_snapshot
    try:
        if action == NpcAction.MOVE:
            return _execute_move(p, npc_id, mind, sh_name, world_day, npc_short)
        if action == NpcAction.TALK:
            return await _execute_talk_async(p, npc_id, mind, sh_name, world_day, npc_short)
        if action == NpcAction.REST:
            return _execute_rest(mind, sh_name, world_day, npc_short)
    except Exception as e:
        if old_pos is not None:
            p.npc_positions[npc_id] = old_pos
        log.warning("action rollback for npc=%s: %s", npc_id, e)
        try:
            from backend.observability.tracker import get_tracker, CallRecord
            import time as _time
            awaitable = get_tracker().record(CallRecord(
                timestamp=_time.time(),
                operation="npc_action_rollback",
                model="",
                player_id=p.player_id,
                npc_id=npc_id,
                parse_success=False,
                schema_violations=["action_rollback"],
                latency_ms=0,
                status="error",
            ))
            asyncio.get_event_loop().create_task(awaitable)
        except Exception:
            pass
        return NpcActionResult(
            action_type=action,
            description=f"{npc_short}行动异常",
            success=False,
        )

    return NpcActionResult(action_type=NpcAction.IDLE, description="未知行动", success=False)


async def act_loop(
    p: PlayerState,
    npc_id: str,
    mind: mem.AgentMind,
    max_steps: int = 3,
) -> list[NpcActionResult]:
    """多步循环：decide → execute → observe。"""
    results: list[NpcActionResult] = []
    for _ in range(max_steps):
        action = decide_next_action(mind, p, npc_id)
        if action == NpcAction.IDLE:
            break
        result = await execute_plan_step_async(p, npc_id, mind)
        results.append(result)
        if mind.needs_reflect():
            try:
                from backend.agents import brain as agent_brain

                npc = NPCS.get(npc_id, {})
                await agent_brain.reflect(
                    npc_id=npc_id,
                    npc_name=npc.get("name", npc_id),
                    npc_blurb=str(npc.get("short", "")),
                    mind=mind,
                    world_day=int(p.world_day),
                    world_shichen=shichen_name(p.world_shichen),
                )
            except Exception as e:
                log.warning("act_loop reflect failed for %s: %s", npc_id, e)
        await asyncio.sleep(0.3)
    return results
