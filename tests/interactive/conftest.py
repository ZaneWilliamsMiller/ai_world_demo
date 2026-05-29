from __future__ import annotations

import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

from backend.data.npcs_data import NPCS

_BASE_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8765")

_NPC_CELL_MAP: dict[str, tuple[int, int]] = {}
for _nid, _meta in NPCS.items():
    _cell = _meta.get("cell")
    if _cell and isinstance(_cell, (list, tuple)) and len(_cell) >= 3:
        _NPC_CELL_MAP[_nid] = (int(_cell[1]), int(_cell[2]))


class InteractiveClient:
    def __init__(self):
        self.client = httpx.Client(base_url=_BASE_URL, timeout=60.0)
        self.player_id: str = ""
        self._patches: list[Any] = []

    def setup(self, npc_id: str | None = None) -> None:
        self.player_id = f"itest_{uuid.uuid4().hex[:12]}"

        try:
            self.client.post("/api/tests/interactive/reset-circuit-breaker")
        except Exception:
            pass

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
        try:
            self.client.post("/api/delete-save", json={"player_id": self.player_id})
        except Exception:
            pass

    def talk(self, npc_id: str, message: str, timeout: float = 60.0) -> dict[str, Any]:
        t0 = time.time()
        try:
            resp = self.client.post("/api/npc/talk", json={
                "player_id": self.player_id,
                "npc_id": npc_id,
                "message": message,
            }, timeout=timeout)
        except Exception as e:
            elapsed = round(time.time() - t0, 1)
            return {
                "success": False,
                "error": str(e),
                "elapsed": elapsed,
            }
        elapsed = round(time.time() - t0, 1)
        if resp.status_code != 200:
            return {
                "success": False,
                "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
                "elapsed": elapsed,
            }
        data = resp.json()
        data["elapsed"] = elapsed
        data["success"] = True
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


class ResponseEvaluator:
    NPC_VOICE_KEYWORDS: dict[str, list[str]] = {
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

    FALLBACK_PATTERNS: list[str] = [
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
    ]

    WORLD_LOCATIONS: list[str] = [
        "青石县", "同福栈", "牙行", "衙前", "镖局", "黑店",
        "野径", "渡头", "画舫", "芦花墟", "驿舍", "寺廊",
        "帮坞", "书院", "厘卡", "桥口", "码口", "山门",
        "青石", "县", "栈", "寺", "渡", "驿",
    ]

    FACTION_NAMES: list[str] = [
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
