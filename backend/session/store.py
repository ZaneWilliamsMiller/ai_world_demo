from __future__ import annotations
import asyncio
import uuid
from typing import Any

from backend.data.factions import FACTIONS
from backend.models.player import PlayerState


class SessionStore:
    """管理全部活跃角色（内存缓存），支持 JSON 文件存档/读档。"""

    def __init__(self) -> None:
        self.players: dict[str, PlayerState] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(
        self,
        player_id: str | None,
        display_name: str | None,
        gender: str,
        permadeath: bool,
    ) -> PlayerState:

        from backend.systems.save_system import load_game
        pid = player_id or str(uuid.uuid4())
        async with self._lock:
            if pid not in self.players:
                loaded = await asyncio.to_thread(load_game, pid) if player_id else None
                if loaded:
                    self.players[pid] = loaded
                else:
                    self.players[pid] = PlayerState(
                        player_id=pid,
                        display_name=(display_name or f"江湖客{pid[:6]}").strip()[:24]
                        or f"江湖客{pid[:6]}",
                        gender=gender if gender in ("男", "女", "未言") else "未言",
                        permadeath=bool(permadeath),
                    )

            st = self.players[pid]

            defaults: dict[str, Any] = {
                "favor": dict,
                "rumors": list,
                "move_locked": False,
                "move_lock_npc_id": None,
                "trap_reason": None,
                "trap_attempts": 0,
                "enslaved": False,
                "enslaved_reason": None,
                "vigor": 80,
                "vigor_max": 100,
                "spirit": 80,
                "spirit_max": 100,
                "sleep_debt": 0,
                "unconscious_ticks": 0,
                "rescue_needed": False,
                "life_burn_ticks": 0,
                "life_burn_max": 0,
                "allow_steep_next_move": False,
                "world_day": 1,
                "world_shichen": 4,
                "world_tick": 0,
                "weather": "薄阴",
                "inventory": dict,
                "events": list,
                "minds": dict,
                "npc_positions": dict,
                "npc_inventories": dict,
                "npc_inventory_restock_day": dict,
                "npc_states": dict,
            }
            for attr, default in defaults.items():
                if not hasattr(st, attr):
                    setattr(st, attr, default() if isinstance(default, type) else default)

            if int(getattr(st, "vigor", 0)) <= 0:
                st.vigor = 80
            if int(getattr(st, "spirit", 0)) <= 0:
                st.spirit = 80

            if not hasattr(st, "reputation") or not isinstance(getattr(st, "reputation", None), dict):
                st.reputation = {k: 0 for k in FACTIONS.keys()}
            else:
                for k in FACTIONS.keys():
                    st.reputation.setdefault(k, 0)

        return st

    async def remove_player(self, player_id: str) -> None:
        async with self._lock:
            self.players.pop(player_id, None)


room = SessionStore()