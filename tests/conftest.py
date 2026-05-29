"""pytest 配置 — 让 `python -m pytest tests/` 自动发现测试文件

离线单元测试不依赖服务器，可直接运行。
E2E 测试需要先启动后端服务器。
"""
import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BASE_URL = os.environ.get("TESTS_BASE_URL", "http://127.0.0.1:8765")


def make_player(**overrides):
    """创建测试用 PlayerState 实例。"""
    from backend.models.player import PlayerState
    defaults = dict(
        player_id="test_player",
        display_name="测试侠客",
        gender="男",
        permadeath=False,
        map_id="world",
        px=25,
        py=28,
        vigor=80,
        vigor_max=100,
        spirit=70,
        spirit_max=100,
        coins=50,
        world_day=1,
        world_shichen=4,
        world_tick=0,
        weather="薄阴",
    )
    defaults.update(overrides)
    return PlayerState(**defaults)
