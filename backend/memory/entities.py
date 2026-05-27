"""动态实体关键词构建、情感计算、CMA凝结、A-Mem顿悟生成。

从 memory.py 拆分而来，职责：
- 从 NPCS/MAPS 数据动态构建实体关键词白名单
- 情感计算（效价-唤醒度映射、心境一致性偏差、情感词库）
- CMA式记忆凝结
- A-Mem 顿悟记忆生成
"""
from __future__ import annotations

import logging
import random
import re
import time
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("memory.entities")

# ── A-Mem 记忆演化(NeurIPS 2025 A-Mem: Agentic Memory 落地)───
INSIGHT_LINK_THRESHOLD = 0.25     # 两条记忆的文本相关度超过此阈值视为可链接
INSIGHT_IMPORTANCE_BOOST = 1.5    # 顿悟记忆的重要性加成
INSIGHT_MAX_PER_ADD = 1           # 每次添加观察最多触发1条顿悟(控制开销)
INSIGHT_COOLDOWN_S = 1800.0       # 同一NPC两次顿悟间至少30分钟(防过频)

# ─── CMA·认知记忆凝结(2026前沿:LinkedIn CMA范式落地)───
OBS_CONDENSE_THRESHOLD = 60       # 当 observation 条数超过此阈值时触发凝结
OBS_CONDENSE_BATCH = 20            # 每次凝结处理最旧的约20条
OBS_KEEP_RECENT = 30               # 至少保留最近30条不凝结

# ── NPC 情感状态(2025-2026 AI情感计算前沿落地)──
MOOD_LABELS = ("欣悦", "平静", "疲惫", "烦躁", "忧悒", "警觉", "愤懑", "好奇", "感怀", "冷淡", "兴奋", "安然")

# ── 情感锚点阈值(2026 AI情感计算前沿:关键时刻永久写入)──
ANCHOR_VALENCE_THRESHOLD = 4.0    # 效价变化超过此值 → 产生锚点
ANCHOR_AROUSAL_THRESHOLD = 3.0   # 唤醒度变化超过此值 → 产生锚点
ANCHOR_IMPORTANCE = 9.0          # 锚点记忆的基础重要性(接近最高)
ANCHOR_HALF_LIFE_S = 3600.0 * 48 # 锚点衰减极慢(48小时半衰期 vs 普通记忆6小时)

# ── 心境一致性记忆检索（2026 情感计算前沿·情绪一致性偏差）──
_MOOD_BIAS_THRESHOLD = 3.0          # 效价绝对值超过此阈值才启用偏差
_MOOD_BIAS_WEIGHT = 0.18            # 心境偏差在检索总分中的最大权重

# 正向情感词（回忆起来让人欣悦）
_POSITIVE_MEMORY_WORDS = {
    "宽慰", "释然", "庆幸", "感激", "欣喜", "有望", "转机", "得利", "可靠",
    "放心", "信得过", "有缘", "仗义", "成事", "顺遂", "可交", "厚道", "稳妥",
    "帮衬", "照应", "结纳", "援手", "化解", "平息", "和睦", "坦荡", "进账",
    "收入", "赚钱", "获利", "赏", "赠", "酬", "谢礼", "结交", "相识",
    "欢喜", "笑声", "宴", "欢", "畅", "幸", "福", "佑",
}
# 负向情感词（回忆起来令人烦忧）
_NEGATIVE_MEMORY_WORDS = {
    "失望", "愤怒", "危险", "背叛", "陷阱", "算计", "提防", "戒备", "凶险",
    "无可挽回", "走投无路", "出卖", "辜负", "寒心", "阴险", "刁难", "逼迫",
    "暗算", "勾结", "图谋", "杀意", "灾祸", "绝路", "蒙冤", "受辱", "被迫",
    "亏", "赔", "失", "罚", "扣", "夺", "劫", "偷", "骗", "讹",
    "痛", "伤", "残", "亡", "恨", "仇", "怨", "苦", "泣",
}


# ─── 动态实体关键词构建（从 NPCS/MAPS 数据自动同步）───
_DYNAMIC_ENTITIES_CACHED: dict[str, tuple] | None = None


def _build_dynamic_entities() -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """从 NPCS 和 MAPS 数据动态构建实体关键词白名单。

    返回 (PERSON_NAMES, PLACE_NAMES, THING_KEYWORDS, ALL_ENTITY_KEYWORDS)
    首次调用后缓存，后续调用直接返回缓存。
    """
    global _DYNAMIC_ENTITIES_CACHED
    if _DYNAMIC_ENTITIES_CACHED is not None:
        return _DYNAMIC_ENTITIES_CACHED

    persons: set[str] = set()
    places: set[str] = set()

    try:
        from backend.data.npcs_data import NPCS, NPC_HABITS
        from backend.data.maps_data import MAPS

        for nid, meta in NPCS.items():
            name = (meta.get("name") or "").strip()
            short = (meta.get("short") or "").strip()
            if name:
                import re as _re
                name_clean = _re.sub(r"[（(][^）)]*[）)]", "", name).strip()
                if "·" in name_clean:
                    parts = [p.strip() for p in name_clean.split("·") if p.strip()]
                    for p in parts:
                        if len(p) <= 6:
                            persons.add(p)
                        if len(p) >= 2:
                            persons.add(p[-2:])
                        if len(p) >= 3:
                            persons.add(p[-3:])
                else:
                    persons.add(name_clean)
                    if len(name_clean) >= 2:
                        persons.add(name_clean[-2:])
                    if len(name_clean) >= 3:
                        persons.add(name_clean[-3:])
            if short:
                persons.add(short)
                if len(short) >= 2:
                    persons.add(short[-2:])

            habits = NPC_HABITS.get(nid, {})
            for _m, loc_name in habits.get("frequent", []):
                if loc_name and len(loc_name) >= 2:
                    places.add(loc_name)

        for mid, m in MAPS.items():
            map_name = m.get("name", "")
            if map_name and len(map_name) >= 2:
                places.add(map_name)
            for portal in m.get("portals", []):
                target = portal.get("target_name", "") or portal.get("name", "")
                if target and len(target) >= 2:
                    places.add(target)
    except Exception:
        pass

    _HARDCODED_PERSONS = (
        "掌柜", "牙人", "皂隶", "镖头", "黑店", "匪首", "船家", "阿泠",
        "里正", "驿卒", "知客", "帮掌", "书生", "卡吏", "风闻", "江",
    )
    _HARDCODED_PLACES = (
        "同福", "牙行", "镖局", "县衙", "渡头", "画舫", "野径",
        "芦花", "佛寺", "书院", "厘卡", "漕口", "驿舍", "碾坊",
    )

    persons.update(_HARDCODED_PERSONS)
    places.update(_HARDCODED_PLACES)

    persons = {p for p in persons if 2 <= len(p) <= 8}
    places = {p for p in places if 2 <= len(p) <= 8}

    things: tuple[str, ...] = (
        "路引", "信物", "帖子", "信函", "银子", "制钱", "药", "毒",
        "镖", "船", "马", "刀", "剑", "赎身", "缉文", "帮规",
        "鲜鱼", "干粮", "野果",
    )
    events: tuple[str, ...] = (
        "杀", "仇", "逃", "救", "帮", "买卖", "赊欠", "火并",
        "走私", "偷渡", "贿赂", "典当", "盘店", "搭股",
    )

    all_kw = tuple(persons) + tuple(places) + things + events
    result = (tuple(sorted(persons)), tuple(sorted(places)), things, all_kw)
    _DYNAMIC_ENTITIES_CACHED = result
    return result


def _get_person_names() -> tuple[str, ...]:
    return _build_dynamic_entities()[0]

def _get_place_names() -> tuple[str, ...]:
    return _build_dynamic_entities()[1]

def _get_thing_keywords() -> tuple[str, ...]:
    return _build_dynamic_entities()[2]

def _get_all_entity_keywords() -> tuple[str, ...]:
    return _build_dynamic_entities()[3]


# ─── 模块级向后兼容常量 ───
PERSON_NAMES: tuple[str, ...] = ()
PLACE_NAMES: tuple[str, ...] = ()
THING_KEYWORDS: tuple[str, ...] = ()
EVENT_KEYWORDS: tuple[str, ...] = ()
ALL_ENTITY_KEYWORDS: tuple[str, ...] = ()


def init_entity_keywords() -> None:
    """在应用启动时调用，从 NPCS/MAPS 数据构建实体关键词并缓存到模块级常量。"""
    global PERSON_NAMES, PLACE_NAMES, THING_KEYWORDS, EVENT_KEYWORDS, ALL_ENTITY_KEYWORDS
    global _DYNAMIC_ENTITIES_CACHED
    _DYNAMIC_ENTITIES_CACHED = None
    result = _build_dynamic_entities()
    PERSON_NAMES = result[0]
    PLACE_NAMES = result[1]
    THING_KEYWORDS = result[2]
    EVENT_KEYWORDS = (
        "杀", "仇", "逃", "救", "帮", "买卖", "赊欠", "火并",
        "走私", "偷渡", "贿赂", "典当", "盘店", "搭股",
    )
    ALL_ENTITY_KEYWORDS = result[3]
    log.info(
        "Entity keywords initialized: %d persons, %d places, %d things, %d total",
        len(PERSON_NAMES), len(PLACE_NAMES), len(THING_KEYWORDS), len(ALL_ENTITY_KEYWORDS),
    )


def mood_from_valence_arousal(valence: float, arousal: float) -> str:
    """基于效价-唤醒度二维模型映射到情绪标签(参考 Russell 情绪环状模型)。"""
    v = max(-10.0, min(10.0, valence))
    a = max(0.0, min(10.0, arousal))
    if a >= 7.0:
        return "欣悦" if v >= 3 else "愤懑" if v <= -3 else "警觉"
    if a >= 4.5:
        return "兴奋" if v >= 3 else "烦躁" if v <= -3 else "好奇"
    if a >= 2.0:
        return "感怀" if v >= 3 else "忧悒" if v <= -3 else "平静"
    return "安然" if v >= 2 else "冷淡" if v <= -3 else "疲惫"


def sentiment_hint(text: str) -> float:
    """启发式情感倾向估计：-1.0（全负面）~ +1.0（全正面）。"""
    t = (text or "").lower()
    pos = sum(1 for kw in _POSITIVE_MEMORY_WORDS if kw in t)
    neg = sum(1 for kw in _NEGATIVE_MEMORY_WORDS if kw in t)
    total = pos + neg
    if total == 0:
        return 0.0
    ratio = (pos - neg) / total
    confidence = min(1.0, total / 4.0)
    return ratio * confidence


def affective_memory_importance(base_importance: float, valence: float, arousal: float) -> float:
    """情感记忆加权:情绪越强烈,记忆越深。"""
    arousal_bonus = max(0.0, (arousal - 5.0) * 0.4)
    valence_bonus = abs(valence) * 0.15
    bonus = arousal_bonus + valence_bonus
    return min(10.0, base_importance + bonus)


def generate_insight_text(old_text: str, new_text: str, old_importance: float) -> str:
    """A-Mem 记忆演化:基于新旧记忆的碰撞,生成「顿悟」文本。

    纯启发式实现(零 LLM 调用),采用模板+关键词匹配。
    """
    suspicion_kw = ("怀疑", "传闻", "道听途说", "有人说", "似乎", "好像", "疑心", "可疑")
    promise_kw = ("约定", "承诺", "说过", "待办", "以后", "下次", "回头", "改日")
    goods_kw = ("物品", "货物", "买卖", "银子", "钱", "制钱", "货", "买", "卖", "价")
    person_kw = ("某人", "那人", "他", "她", "谁", "有人")
    emotion_kw = ("恨", "怨", "怒", "悲", "痛", "悔", "愧", "思念", "感激", "欢喜", "恩", "仇")

    old_lower = old_text.lower()
    snippet = old_text[:50].strip()

    if any(kw in old_lower for kw in suspicion_kw):
        variants = [
            f"想起之前{snippet}——原来如此，这才明白其中缘由。",
            f"旧疑云忽散：{snippet}——与新见之事暗合，疑团豁然开朗。",
            f"之前{snippet}如今有了答案，心头一块石头落了地。",
        ]
        return random.choice(variants)
    if any(kw in old_lower for kw in emotion_kw):
        variants = [
            f"心头翻涌：{snippet}——今日回想，滋味又与当初不同。",
            f"想起{snippet}——那股情绪至今还在心头打转。",
            f"旧事重上心头：{snippet}，像是昨日才发生的一般。",
        ]
        return random.choice(variants)
    if any(kw in old_lower for kw in promise_kw):
        variants = [
            f"忽然想起之前{snippet}，此刻心头一动，或许有了眉目。",
            f"念及{snippet}——是时候去赴那个约了。",
            f"旧约未践：{snippet}，心里忽然惦了起来。",
        ]
        return random.choice(variants)
    if any(kw in old_lower for kw in goods_kw):
        variants = [
            f"想起之前的{snippet}——如今才悟出其中门道。",
            f"生意经忽转：{snippet}，原来利在别处。",
        ]
        return random.choice(variants)
    if any(kw in old_lower for kw in person_kw):
        variants = [
            f"想起{snippet}——此刻忽然看清了那人的真意。",
            f"人物旧影：{snippet}，重新掂量，或许当初看走了眼。",
            f"那人{snippet}的事，今天想来倒另有一层意思。",
        ]
        return random.choice(variants)
    if old_importance >= 7.0:
        variants = [
            f"想起{snippet}——心头忽然一动，悟出了些先前没想通的关窍。",
            f"旧事重提：{snippet}，此刻才看清其中关节。",
        ]
    else:
        variants = [
            f"忽忆旧事：{snippet}——与新近所见似有暗合。",
            f"不经意间想起{snippet}，与新事两厢对照，多了层理解。",
            f"记忆泛起：{snippet}，此刻的背景让它显出另一番味道。",
        ]
    return random.choice(variants)
