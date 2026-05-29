from __future__ import annotations

import logging

from backend.agents import brain as agent_brain
from backend.agents.game_state import get_or_init_mind
from backend.data.npcs_data import NPCS
from backend.session.store import room
from backend.systems.time_weather import shichen_name

log = logging.getLogger("agent_service")

# ── 夜间反思门禁 ──
# 子时（0）至寅时（2）为深度休眠时段，自动反思跳过，避免在 NPC
# 应当休息时浪费 LLM 调用并产生「深夜自我检讨」的违和输出。
NIGHT_REFLECT_BLOCKED_SHICHEN = {0, 1, 2}  # 子时=0, 丑时=1, 寅时=2

async def bg_reflect(player_id: str, npc_id: str) -> None:
    """后台反思任务（不阻塞玩家对话）。

    夜间门禁（2026-05-25）：子时-寅时跳过反思。NPC 在深夜应当休息，
    此时触发 LLM 反思既浪费 token，又会产出不合时宜的「失眠自省」。
    例外：极端的情绪唤醒度（≥8.0）即使在夜间也允许反思，模拟失眠/夜不能寐。
    """
    p = room.players.get(player_id)
    if not p:
        return
    npc = NPCS.get(npc_id)
    if not npc:
        return
    mind = get_or_init_mind(p, npc_id)
    if not mind.needs_reflect():
        return
    # ── 夜间门禁 ──
    if int(p.world_shichen) in NIGHT_REFLECT_BLOCKED_SHICHEN and getattr(mind, "affect_arousal", 5.0) < 8.0:
        log.debug("bg_reflect skipped for npc=%s: night shichen=%s",
                  npc_id, shichen_name(p.world_shichen))
        return  # NPC 安睡中，不打扰
        # 极端唤醒度（>=8.0）= 失眠/夜不能寐，允许反思
    try:
        await agent_brain.reflect(
            npc_id=npc_id,
            npc_name=npc["name"],
            npc_blurb=str(npc.get("short", "")),
            mind=mind,
            world_day=int(p.world_day),
            world_shichen=shichen_name(p.world_shichen),
        )
        # Multi-Agent Cross-Reflection: 反思后进一步反思对熟人的社交洞察
        await agent_brain.cross_reflect(
            npc_id=npc_id,
            npc_name=npc["name"],
            npc_blurb=str(npc.get("short", "")),
            mind=mind,
            world_day=int(p.world_day),
            world_shichen=shichen_name(p.world_shichen),
        )
    except Exception as e:
        log.warning("bg_reflect failed for npc=%s: %s", npc_id, e)

async def bg_plan_for_npcs(player_id: str, npc_ids: list[str], world_day: int) -> None:
    p = room.players.get(player_id)
    if not p:
        return
    for nid in npc_ids:
        npc = NPCS.get(nid)
        if not npc:
            continue
        mind = get_or_init_mind(p, nid)
        if mind.plan_day == world_day:
            continue
        try:
            await agent_brain.plan_day(
                npc_id=nid,
                npc_name=npc["name"],
                npc_blurb=str(npc.get("short", "")),
                mind=mind,
                world_day=world_day,
            )
        except Exception as e:
            log.warning("bg_plan_for_npcs failed for npc=%s: %s", nid, e)
            continue
