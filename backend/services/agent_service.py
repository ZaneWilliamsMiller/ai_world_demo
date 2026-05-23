import logging

from backend import agent_brain
from backend.game_state import get_or_init_mind
from backend.data.npcs_data import NPCS
from backend.session.store import room
from backend.systems.time_weather import shichen_name

log = logging.getLogger("agent_service")

async def bg_reflect(player_id: str, npc_id: str) -> None:
    """后台反思任务（不阻塞玩家对话）。"""
    p = room.players.get(player_id)
    if not p:
        return
    npc = NPCS.get(npc_id)
    if not npc:
        return
    mind = get_or_init_mind(p, npc_id)
    if not mind.needs_reflect():
        return
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
    except Exception as e:  # noqa: BLE001
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
        except Exception as e:  # noqa: BLE001
            log.warning("bg_plan_for_npcs failed for npc=%s: %s", nid, e)
            continue
