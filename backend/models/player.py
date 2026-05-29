from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from backend.data.factions import FACTIONS
from backend.memory import AgentMind
from backend.systems.constants import (
    INITIAL_PX,
    INITIAL_PY,
    INITIAL_COINS,
    INITIAL_VIGOR,
    INITIAL_VIGOR_MAX,
    INITIAL_SPIRIT,
    INITIAL_SPIRIT_MAX,
)


def _default_flags() -> dict[str, int]:
    return {"order": 0, "truth": 0, "hope": 0, "chaos": 0}


def _default_reputation() -> dict[str, int]:
    return {k: 0 for k in FACTIONS.keys()}


@dataclass
class PlayerState:
    player_id: str
    display_name: str
    gender: str = "未言"
    permadeath: bool = False
    dead: bool = False
    death_reason: str | None = None
    map_id: str = "world"
    px: int = INITIAL_PX
    py: int = INITIAL_PY
    coins: int = INITIAL_COINS
    flags: dict[str, int] = field(default_factory=_default_flags)
    history: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    favor: dict[str, int] = field(default_factory=dict)
    rumors: list[str] = field(default_factory=list)
    move_locked: bool = False
    move_lock_npc_id: str | None = None
    trap_reason: str | None = None
    trap_attempts: int = 0
    enslaved: bool = False
    enslaved_reason: str | None = None
    vigor: int = INITIAL_VIGOR
    vigor_max: int = INITIAL_VIGOR_MAX
    spirit: int = INITIAL_SPIRIT
    spirit_max: int = INITIAL_SPIRIT_MAX
    sleep_debt: int = 0
    unconscious_ticks: int = 0
    rescue_needed: bool = False
    life_burn_ticks: int = 0
    life_burn_max: int = 0
    allow_steep_next_move: bool = False
    ended: bool = False
    ending_label: str | None = None
    # 世界时钟与天气
    world_day: int = 1
    world_shichen: int = 4  # 默认从辰时开始（清晨）
    world_tick: int = 0
    weather: str = "薄阴"
    # 库存、声望、事件流
    inventory: dict[str, int] = field(default_factory=dict)
    reputation: dict[str, int] = field(default_factory=_default_reputation)
    events: list[dict[str, Any]] = field(default_factory=list)
    # 每个 NPC 在本玩家会话下的「心智」（记忆流 + 当日计划）
    minds: dict[str, AgentMind] = field(default_factory=dict)
    # 会话内 NPC 动态位置（允许有限游走）
    npc_positions: dict[str, tuple[str, int, int]] = field(default_factory=dict)
    # NPC 动态状态（基于时辰+习惯的自动切换：idle/resting/busy）
    npc_states: dict[str, str] = field(default_factory=dict)
    # NPC 随身货柜：npc_id → {物品名: 数量}（用于交易系统）
    npc_inventories: dict[str, dict[str, int]] = field(default_factory=dict)
    # NPC 货柜补货追踪：npc_id → 上次补货的世界日（避免同日重复补货）
    npc_inventory_restock_day: dict[str, int] = field(default_factory=dict)
    # 动态奇遇冷却时间戳
    last_dynamic_encounter_tick: int = -100
    # ── 悬赏榜（2026-05-26 新增）──
    bounties: list[dict[str, Any]] = field(default_factory=list)
    active_bounty: dict[str, Any] | None = None
    completed_bounties: list[str] = field(default_factory=list)
    last_bounty_refresh_day: int = 0
    # 悬赏进度追踪：记录最近一次对话及行进信息（用于 check_bounty_progress）
    last_talk_npc_id: str | None = None
    last_talk_message: str | None = None
    last_move_map_id: str | None = None
    last_move_px: int = 0
    last_move_py: int = 0
    # 物品每日用量追踪：{"_day": world_day, "干粮": 2, "金创药": 1}
    item_use_tracker: dict[str, int] = field(default_factory=dict)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False, compare=False)

    def __getstate__(self) -> dict[str, Any]:
        state = self.__dict__.copy()
        state.pop("lock", None)
        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        state["lock"] = asyncio.Lock()
        self.__dict__.update(state)
