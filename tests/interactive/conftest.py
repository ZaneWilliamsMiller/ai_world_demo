from __future__ import annotations

import contextlib
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any, ClassVar
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
import pytest
from backend.data.npcs_data import NPCS

_BASE_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8765")


_INTERACTIVE_DIR = str(Path(__file__).resolve().parent)


def pytest_collection_modifyitems(items):
    for item in items:
        if _INTERACTIVE_DIR in str(item.fspath):
            item.add_marker(pytest.mark.interactive)

_LOCK_FILE = None


def _acquire_lock(f):
    if sys.platform == "win32":
        import msvcrt
        msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
    else:
        import fcntl
        fcntl.flock(f, fcntl.LOCK_EX)


def _release_lock(f):
    if sys.platform == "win32":
        import msvcrt
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(f, fcntl.LOCK_UN)


@pytest.fixture(autouse=True, scope="session")
def _serial_lock():
    global _LOCK_FILE
    lock_path = Path(__file__).resolve().parent / ".interactive.lock"
    with open(lock_path, "w") as f:
        _LOCK_FILE = f
        _acquire_lock(_LOCK_FILE)
        yield
        _release_lock(_LOCK_FILE)
    with contextlib.suppress(Exception):
        lock_path.unlink(missing_ok=True)

_NPC_CELL_MAP: dict[str, tuple[int, int]] = {}
for _nid, _meta in NPCS.items():
    _cell = _meta.get("cell")
    if _cell and isinstance(_cell, (list, tuple)) and len(_cell) >= 3:
        _NPC_CELL_MAP[_nid] = (int(_cell[1]), int(_cell[2]))


class InteractiveClient:
    _global_dialogue_log: ClassVar[list[dict[str, Any]]] = []
    _on_dialogue: Any = None

    def __init__(self):
        self.client = httpx.Client(base_url=_BASE_URL, timeout=60.0)
        self.player_id: str = ""
        self._patches: list[Any] = []
        self._dialogue_log: list[dict[str, Any]] = []

    def setup(self, npc_id: str | None = None) -> None:
        self.player_id = f"itest_{uuid.uuid4().hex[:12]}"
        self._dialogue_log = []

        with contextlib.suppress(Exception):
            self.client.post("/api/tests/interactive/reset-circuit-breaker")

        resp = self.client.post("/api/hello", json={
            "player_id": self.player_id,
            "display_name": "测试侠客",
            "gender": "男",
            "permadeath": False,
        })
        assert resp.status_code == 200, f"hello failed: {resp.status_code} {resp.text}"

        if npc_id and npc_id in _NPC_CELL_MAP:
            tx, ty = _NPC_CELL_MAP[npc_id]
            self.client.post("/api/move", json={
                "player_id": self.player_id,
                "to_x": tx,
                "to_y": ty,
            })

        self._freeze_world()

    def _freeze_world(self) -> None:
        p1 = patch("backend.systems.time_weather.advance_clock", return_value=None)
        p2 = patch("backend.services.talk_service.advance_clock", return_value=None)
        p3 = patch("backend.systems.core.maybe_wander_npcs", return_value=None)
        p4 = patch("backend.api.player_routes.maybe_wander_npcs", return_value=None)
        for p in [p1, p2, p3, p4]:
            p.start()
            self._patches.append(p)

    def teardown(self) -> None:
        for p in self._patches:
            p.stop()
        self._patches.clear()
        InteractiveClient._global_dialogue_log = list(self._dialogue_log)
        with contextlib.suppress(Exception):
            self.client.post("/api/delete-save", json={"player_id": self.player_id})

    def talk(self, npc_id: str, message: str, timeout: float = 60.0) -> dict[str, Any]:
        t0 = time.time()
        max_retries = 3
        resp: httpx.Response | None = None
        for attempt in range(max_retries):
            try:
                resp = self.client.post("/api/npc/talk", json={
                    "player_id": self.player_id,
                    "npc_id": npc_id,
                    "message": message,
                }, timeout=timeout)
                if resp.status_code == 429 and attempt < max_retries - 1:
                    time.sleep(5 * (attempt + 1))
                    continue
            except Exception as e:
                elapsed = round(time.time() - t0, 1)
                entry = {"npc": npc_id, "player": message, "reply": "", "error": str(e), "elapsed": elapsed, "favor_delta": 0, "coin_delta": 0}
                self._dialogue_log.append(entry)
                return {"success": False, "error": str(e), "elapsed": elapsed}
        elapsed = round(time.time() - t0, 1)
        if resp is None or resp.status_code != 200:
            status_code = resp.status_code if resp is not None else 0
            resp_text = resp.text[:200] if resp is not None else "no response"
            entry = {"npc": npc_id, "player": message, "reply": "", "error": f"HTTP {status_code}", "elapsed": elapsed, "favor_delta": 0, "coin_delta": 0}
            self._dialogue_log.append(entry)
            return {"success": False, "error": f"HTTP {status_code}: {resp_text}", "elapsed": elapsed}
        data = resp.json()
        data["elapsed"] = elapsed
        data["success"] = True

        raw_reply = data.get("visible_text", "") or data.get("reply", "")
        if isinstance(raw_reply, dict):
            raw_reply = raw_reply.get("visible_text", "") or raw_reply.get("reply", "") or str(raw_reply)
        if not raw_reply:
            raw_reply = ""

        favor_delta = 0
        coin_delta = 0
        if isinstance(data.get("delta"), dict):
            favor_delta = data["delta"].get("favor", 0) or 0
            coin_delta = data["delta"].get("coins", 0) or 0
        if favor_delta == 0 and data.get("favor_delta"):
            favor_delta = data["favor_delta"]
        if coin_delta == 0 and data.get("coin_delta"):
            coin_delta = data["coin_delta"]

        entry = {
            "npc": npc_id,
            "npc_name": NPCS.get(npc_id, {}).get("name", npc_id),
            "player": message,
            "reply": raw_reply,
            "elapsed": elapsed,
            "favor_delta": favor_delta,
            "coin_delta": coin_delta,
        }
        self._dialogue_log.append(entry)
        if InteractiveClient._on_dialogue is not None:
            with contextlib.suppress(Exception):
                InteractiveClient._on_dialogue(entry)
        return data

    def dialogue(self, npc_id: str, messages: list[str], timeout: float = 60.0) -> list[dict[str, Any]]:
        results = []
        for msg in messages:
            r = self.talk(npc_id, msg, timeout=timeout)
            results.append(r)
            if not r.get("success"):
                break
        return results

    def get_mind(self, npc_id: str) -> dict[str, Any]:
        try:
            resp = self.client.get(f"/api/agent/{self.player_id}/{npc_id}/mind")
            if resp.status_code != 200:
                return {}
            return resp.json()
        except Exception:
            return {}

    @classmethod
    def get_dialogue_log(cls) -> list[dict[str, Any]]:
        return list(cls._global_dialogue_log)


class ResponseEvaluator:
    NPC_VOICE_KEYWORDS: ClassVar[dict[str, list[str]]] = {
        "zhanggui": ["客官", "小店", "好说", "可议", "掌柜", "栈房", "房", "店", "住"],
        "yaren": ["行价", "例规", "秤尾", "金某", "牙行", "价", "货", "买卖", "利"],
        "bullya": ["按例", "规费", "凡事", "衙门", "皂隶", "公事", "告", "状"],
        "biaotou": ["压镖", "亮青", "平趟", "镖局", "镖头", "镖", "护", "路"],
        "seng": ["施主", "随喜", "缘法", "贫僧", "佛", "善", "慈悲", "寺", "签"],
        "jiang": ["风闻", "江湖", "倒也", "说书", "消息", "传闻", "听闻"],
        "yulaog": ["渡口", "摇橹", "潮头", "船家", "渡", "船"],
        "aling": ["画舫", "曲", "赎身", "唱", "琴"],
        "lizheng": ["乡约", "鱼鳞册", "里正", "丁口", "村", "庄"],
        "yizu": ["驿", "火漆", "公文", "脚程", "信", "马"],
        "bangzhang": ["漕", "帮", "抽头", "护", "码头"],
        "shusheng": ["策论", "书院", "清议", "书生", "学", "文"],
        "lika": ["厘卡", "例", "抽分", "引", "税"],
        "xuanzhen": ["丹", "道", "贫道", "药", "炉"],
        "tiegu": ["猎", "弓", "兽", "山", "皮"],
        "jintang": ["赌", "骰", "牌", "局"],
    }

    FALLBACK_PATTERNS: ClassVar[list[str]] = [
        "一阵风吹过",
        "灯火摇曳",
        "那人低头想着心事",
        "远处忽然起了喧哗",
        "夜色沉沉",
        "欲言又止",
        "没听清",
        "没能回话",
        "神游天外",
        "倦极",
        "旁人打断",
    ]

    WORLD_LOCATIONS: ClassVar[list[str]] = [
        "青石县", "同福栈", "牙行", "衙前", "镖局", "黑店",
        "野径", "渡头", "画舫", "芦花墟", "驿舍", "寺廊",
        "帮坞", "书院", "厘卡", "桥口", "码口", "山门",
        "青石", "县", "栈", "寺", "渡", "驿",
    ]

    FACTION_NAMES: ClassVar[list[str]] = [
        "衙门", "镖局", "绿林", "漕帮", "书院",
        "官", "帮", "匪", "盗", "学",
    ]

    @classmethod
    def is_fallback(cls, text: str) -> bool:
        return any(p in text for p in cls.FALLBACK_PATTERNS)

    @classmethod
    def check_voice(cls, npc_id: str, text: str) -> bool:
        if cls.is_fallback(text):
            return False
        keywords = cls.NPC_VOICE_KEYWORDS.get(npc_id, [])
        if not keywords:
            return True
        return any(kw in text for kw in keywords)

    @classmethod
    def check_world_locations(cls, text: str, min_count: int = 1) -> bool:
        if cls.is_fallback(text):
            return False
        found = sum(1 for loc in cls.WORLD_LOCATIONS if loc in text)
        return found >= min_count

    @classmethod
    def check_faction_knowledge(cls, text: str) -> bool:
        if cls.is_fallback(text):
            return False
        return any(f in text for f in cls.FACTION_NAMES)

    @classmethod
    def check_self_identity(cls, npc_id: str, text: str) -> bool:
        if cls.is_fallback(text):
            return False
        npc = NPCS.get(npc_id, {})
        name = npc.get("name", "")
        short = npc.get("short", "")
        keywords = [k for k in [name, short] if k and len(k) >= 2]
        return any(k in text for k in keywords)

    @classmethod
    def check_favor_direction(cls, response: dict, expected_positive: bool) -> bool:
        delta = response.get("delta", {}).get("favor", 0)
        if expected_positive:
            return delta > 0
        return delta < 0

    @classmethod
    def check_nonempty_reply(cls, response: dict) -> bool:
        text = response.get("visible_text", "") or response.get("reply", "")
        return len(text.strip()) >= 10 and not cls.is_fallback(text)

    @classmethod
    def check_coin_change(cls, response: dict) -> bool:
        delta = response.get("delta", {}).get("coins", 0)
        return delta != 0
