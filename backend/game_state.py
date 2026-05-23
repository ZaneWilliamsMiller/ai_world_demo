from __future__ import annotations

import asyncio
from typing import Any

from backend.data.maps_data import MAPS, MAP_AMBUSH_MARKERS
from backend.data.npcs_data import NPCS, NPC_FACTION, STORY_ORDER
from backend.data.factions import FACTIONS
from backend.data.prompts import WORLD_NAME, SOCIETY_BIBLE, AUTONOMY_RULE, PERMADEATH_RULE, MACHINE_TAIL_RULE, FIXED_INTRO
from backend.models.player import PlayerState
from backend.models.npc import format_npc_character_sheet
from backend.memory import AgentMind
from backend.systems.pathfinding import find_path, apply_portal, path_cost, cost_to_ticks, tile_at, walkable
from backend.systems.time_weather import advance_clock, shichen_name, shichen_phase, is_night
from backend.systems.economy import apply_coin_delta, add_items, remove_items
from backend.systems.reputation import apply_rep_delta, push_event
from backend.systems.core import (
    clamp_delta, apply_favor, push_rumor, npc_ids_for_player,
    move_should_fire_encounter, try_clear_move_lock, tile_forced_encounter,
    hazard_roll_death, world_status_block, recent_events_block
)
from backend.session.store import room

def get_or_init_mind(p: PlayerState, npc_id: str) -> AgentMind:
    """惰性创建 NPC 心智，并植入 seed 记忆（人物本心切片）。"""
    mind = p.minds.get(npc_id)
    if mind is not None:
        return mind
    mind = AgentMind()
    from backend.data.npcs_data import NPC_SEEDS
    seeds = NPC_SEEDS.get(npc_id) or []
    if seeds:
        from backend.agent_brain import import_seeds
        import_seeds(
            mind,
            seeds,
            world_day=int(p.world_day),
            world_shichen=shichen_name(p.world_shichen),
        )
    p.minds[npc_id] = mind
    return mind
