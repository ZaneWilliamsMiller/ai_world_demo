from __future__ import annotations

from backend.memory import AgentMind
from backend.models.player import PlayerState
from backend.systems.time_weather import shichen_name


def get_or_init_mind(p: PlayerState, npc_id: str) -> AgentMind:
    """惰性创建 NPC 心智，并植入 seed 记忆（人物本心切片）。"""
    mind = p.minds.get(npc_id)
    if mind is not None:
        return mind
    mind = AgentMind()
    from backend.data.npcs_data import NPC_SEEDS
    seeds = NPC_SEEDS.get(npc_id) or []
    if seeds:
        from backend.agents.brain import import_seeds
        import_seeds(
            mind,
            seeds,
            world_day=int(p.world_day),
            world_shichen=shichen_name(p.world_shichen),
        )
    p.minds[npc_id] = mind
    return mind
