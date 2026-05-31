from __future__ import annotations

import asyncio
import uuid

from backend.models.player import PlayerState


class SessionStore:
    """管理全部活跃角色（内存缓存），支持 JSON 文件存档/读档。"""

    IDLE_EVICT_MINUTES = 30

    def __init__(self) -> None:
        self.players: dict[str, PlayerState] = {}
        self._lock = asyncio.Lock()
        self._last_access: dict[str, float] = {}

    def _touch(self, player_id: str) -> None:
        import time
        self._last_access[player_id] = time.time()

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
            self._touch(pid)

        return st

    async def remove_player(self, player_id: str) -> None:
        async with self._lock:
            self.players.pop(player_id, None)
            self._last_access.pop(player_id, None)

    async def set_player(self, player_id: str, player: PlayerState) -> None:
        async with self._lock:
            self.players[player_id] = player
            self._touch(player_id)

    async def pop_player(self, player_id: str) -> PlayerState | None:
        async with self._lock:
            self._last_access.pop(player_id, None)
            return self.players.pop(player_id, None)

    async def snapshot(self) -> list[tuple[str, PlayerState]]:
        async with self._lock:
            return list(self.players.items())

    async def evict_idle_players(self) -> int:
        """淘汰超过 IDLE_EVICT_MINUTES 无访问的玩家（存档后移除）。"""
        import time as _time
        from backend.systems.save_system import save_game

        now = _time.time()
        threshold = self.IDLE_EVICT_MINUTES * 60
        evicted = 0

        async with self._lock:
            to_evict = [
                pid for pid, last in self._last_access.items()
                if now - last > threshold and pid in self.players
            ]

        for pid in to_evict:
            p = self.players.get(pid)
            if p is None:
                continue
            try:
                async with p.lock:
                    await asyncio.to_thread(save_game, p)
                async with self._lock:
                    self.players.pop(pid, None)
                    self._last_access.pop(pid, None)
                evicted += 1
            except Exception:
                pass

        return evicted


room = SessionStore()
