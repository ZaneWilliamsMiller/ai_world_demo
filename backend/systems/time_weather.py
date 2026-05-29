from __future__ import annotations
from backend.systems.constants import (
    SLEEP_DEBT_DIVISOR,
    COMA_RECOVER_SLEEP_DEBT,
    COMA_RECOVER_SPIRIT,
    COMA_RECOVER_VIGOR,
    WEATHER_CHANGE_PERIOD,
    WEATHER_CHANGE_PROB,
    RAIN_PROB,
)

SHICHEN: tuple[str, ...] = (
    "子时", "丑时", "寅时", "卯时", "辰时", "巳时",
    "午时", "未时", "申时", "酉时", "戌时", "亥时",
)

WEATHERS: tuple[str, ...] = (
    "晴", "薄阴", "云遮日", "小风", "风急", "骤雨",
    "闷热", "湿瘴", "薄雾", "重雾", "寒露", "夜霜",
)

# 天气大致按时令分组（演进时偏向就近）
WEATHER_DAY: tuple[str, ...] = ("晴", "薄阴", "云遮日", "小风", "风急", "闷热")
WEATHER_NIGHT: tuple[str, ...] = ("薄阴", "云遮日", "小风", "薄雾", "重雾", "寒露", "夜霜")
WEATHER_RAIN: tuple[str, ...] = ("骤雨", "湿瘴")


def shichen_name(idx: int) -> str:
    return SHICHEN[idx % 12]


def is_night(idx: int) -> bool:
    return idx % 12 in (0, 1, 10, 11)  # 子丑戌亥


def shichen_phase(idx: int) -> str:
    i = idx % 12
    if i in (0, 1):
        return "深夜"
    if i in (2, 3):
        return "凌晨"
    if i in (4, 5):
        return "上午"
    if i in (6, 7):
        return "正午"
    if i in (8, 9):
        return "傍晚"
    return "夜里"


def advance_clock(p: "PlayerState", ticks: int = 1) -> None:
    """推进世界时钟。每次 tick = 一时辰；溢出转入下一日；附带可能的天气演替。"""
    if ticks <= 0:
        return
    ticks = min(ticks, 24)
    import random
    old_day = int(p.world_day)
    for _ in range(ticks):
        # 昏迷计时（清醒前禁止行动）
        if int(getattr(p, "unconscious_ticks", 0) or 0) > 0:
            p.unconscious_ticks = int(getattr(p, "unconscious_ticks", 0)) - 1
        p.world_shichen = (int(p.world_shichen) + 1) % 12
        if p.world_shichen == 0:
            p.world_day = int(p.world_day) + 1
        # 每过 3 时辰 50% 概率换天气；夜晚偏雾/寒，白日偏晴/风
        p.world_tick = int(p.world_tick) + 1
        # 睡眠债：不睡会让心气衰减越来越快
        if hasattr(p, "sleep_debt"):
            p.sleep_debt = int(getattr(p, "sleep_debt", 0)) + 1
            spirit = int(getattr(p, "spirit", 80))
            spirit_max = int(getattr(p, "spirit_max", 100))
            drain = 1 + p.sleep_debt // SLEEP_DEBT_DIVISOR
            spirit = max(0, min(spirit_max, spirit - drain))
            p.spirit = spirit
            if spirit <= 0:
                p.unconscious_ticks = max(int(getattr(p, "unconscious_ticks", 0)), 2)
                p.sleep_debt = max(0, p.sleep_debt - COMA_RECOVER_SLEEP_DEBT)
                recover_spirit = min(spirit_max, int(getattr(p, "spirit", 0)) + COMA_RECOVER_SPIRIT)
                p.spirit = max(recover_spirit, spirit_max // 3)
                p.vigor = min(int(getattr(p, "vigor_max", 100)), int(getattr(p, "vigor", 0)) + COMA_RECOVER_VIGOR)
        # 生命燃烧读条：体力归零后倒计时，不进食则饿死
        if int(getattr(p, "life_burn_ticks", 0) or 0) > 0 and int(getattr(p, "vigor", 0) or 0) <= 0:
            p.life_burn_ticks = max(0, int(getattr(p, "life_burn_ticks", 0)) - 1)
            if p.life_burn_ticks <= 0 and not bool(getattr(p, "dead", False)):
                p.dead = True
                p.death_reason = "体力燃尽且未得进食，终至饿毙。"
        if p.world_tick % WEATHER_CHANGE_PERIOD == 0 and random.random() < WEATHER_CHANGE_PROB:
            cur = p.weather
            if random.random() < RAIN_PROB:
                pool = WEATHER_RAIN
            elif is_night(p.world_shichen):
                pool = WEATHER_NIGHT
            else:
                pool = WEATHER_DAY
            choices = [w for w in pool if w != cur] or list(pool)
            p.weather = random.choice(choices)
    # ── NPC 货柜自然补货：世界日翻篇时检测 ──
    if int(p.world_day) > old_day:
        import logging
        log = logging.getLogger("time_weather")
        try:
            from backend.systems.economy import restock_npc_inventories
            restock_logs = restock_npc_inventories(p)
            for msg in restock_logs:
                log.info("restock: %s", msg)
        except Exception as e:  # noqa: BLE001
            log.warning("restock check failed: %s", e)
