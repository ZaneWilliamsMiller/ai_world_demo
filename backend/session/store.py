from __future__ import annotations

import asyncio
import uuid

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
            st._ensure_defaults()

        return st

    async def remove_player(self, player_id: str) -> None:
        async with self._lock:
            self.players.pop(player_id, None)

    async def set_player(self, player_id: str, player: PlayerState) -> None:
        async with self._lock:
            self.players[player_id] = player

    async def pop_player(self, player_id: str) -> PlayerState | None:
        async with self._lock:
            return self.players.pop(player_id, None)

    async def snapshot(self) -> list[tuple[str, PlayerState]]:
        async with self._lock:
            return list(self.players.items())


room = SessionStore()
