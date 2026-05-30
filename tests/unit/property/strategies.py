from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.models.player import PlayerState
from backend.systems.task_fsm import TaskState
from hypothesis import strategies as st

MAP_WIDTH = 150
MAP_HEIGHT = 100


def st_position():
    return st.tuples(st.integers(0, MAP_WIDTH - 1), st.integers(0, MAP_HEIGHT - 1))


@st.composite
def st_player_state(draw):
    vigor_max = draw(st.integers(1, 100))
    spirit_max = draw(st.integers(1, 100))
    return PlayerState(
        player_id="test_player",
        display_name="测试侠客",
        gender=draw(st.sampled_from(["男", "女", "未言"])),
        map_id="world",
        px=draw(st.integers(0, MAP_WIDTH - 1)),
        py=draw(st.integers(0, MAP_HEIGHT - 1)),
        coins=draw(st.integers(0, 9999)),
        vigor=draw(st.integers(0, vigor_max)),
        vigor_max=vigor_max,
        spirit=draw(st.integers(0, spirit_max)),
        spirit_max=spirit_max,
        sleep_debt=draw(st.integers(0, 50)),
        world_day=draw(st.integers(1, 999)),
        world_shichen=draw(st.integers(0, 11)),
        world_tick=draw(st.integers(0, 999)),
        weather=draw(st.sampled_from([
            "晴", "薄阴", "云遮日", "小风", "风急", "骤雨",
            "闷热", "湿瘴", "薄雾", "重雾", "寒露", "夜霜",
        ])),
    )


def st_inventory_item():
    return st.sampled_from([
        "干粮", "鲜鱼", "野果", "粗酒", "熟牛肉", "茶饼",
        "路引", "信函", "信物", "帖子", "缉文", "地图",
        "金创药", "解毒丸", "安神散", "蒙汗药",
        "火折", "草绳", "瓷瓶", "斗笠", "雨蓑",
        "柴刀", "短剑", "匕首", "铁护腕",
    ])


def st_shichen():
    return st.integers(0, 11)


def st_task_state():
    return st.sampled_from(list(TaskState))
