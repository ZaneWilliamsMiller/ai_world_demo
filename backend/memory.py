"""个人记忆流(参考斯坦福「Generative Agents」论文核心机制)

每个 NPC(按玩家分会话)持有一份自己的 MemoryStream:
- 每条记忆带 importance(重要性,1-10)、created_at(世界时辰)、last_accessed
- 类型:observation(观察 / 与玩家交互)、reflection(自我反思生成的洞察)、plan(当日计划条)、seed(人物初始世界观)
- 检索分数 = w_recency · 衰减(t-last_accessed) + w_importance · 重要性归一 + w_relevance · 相关度
- 相关度:引入基于词级别 Jaccard 相似度(使用结巴分词),提升语义召回率

设计取舍:
- 不持久化(与项目其它状态一致:进程内存)
- 不引入第三方向量库(保持依赖最少)
- 反思与规划放在 agent_brain.py,本模块只管「存与取」
"""
from __future__ import annotations

import logging
import math
import re
import time
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("memory")

# 尝试导入 jieba,如果失败则回退到字符 bigram
try:
    import jieba
    HAS_JIEBA = True
except ImportError:
    HAS_JIEBA = False

# ─── 检索权重(仿斯坦福小镇论文取近似) ─────────────────────
W_RECENCY = 0.55
W_IMPORTANCE = 0.25
W_RELEVANCE = 0.50  # 注意可超过 1,论文是三项各自归一相加,权重不强求和=1

# 重要性触发反思的阈值(demo 取 35:约 7~8 轮普通对话即可触发一次反思)
REFLECTION_IMPORTANCE_TRIGGER = 35.0
REFLECTION_MIN_INTERVAL_S = 30.0      # 两次反思的最小间隔(秒),避免重复反思

# ─── 工具:分词与相似度 ─────────────────────
_PUNCT_RE = re.compile(r"[\s,。、,.;;::!?!?\"'「」『』《》()()【】]+")

def _tokenize(text: str) -> set[str]:
    s = (_PUNCT_RE.sub("", text or "")).strip()
    if not s:
        return set()
    if HAS_JIEBA:
        # 使用 jieba 分词
        words = set(jieba.cut(s))
        # 移除单字停用词(简单处理)
        return {w for w in words if len(w) > 1 or w in ("死", "杀", "毒", "银", "钱", "仇", "救")}
    else:
        # 回退到字符 bigram
        if len(s) < 2:
            return set(s)
        return {s[i : i + 2] for i in range(len(s) - 1)}


def _generate_insight_text(old_text: str, new_text: str, old_importance: float) -> str:
    """A-Mem 记忆演化:基于新旧记忆的碰撞,生成「顿悟」文本。

    纯启发式实现(零 LLM 调用),采用模板+关键词匹配:
    - 如果旧记忆含「怀疑/传闻/某人」关键词 → 顿悟可能是「原来...」
    - 如果旧记忆含「约定/承诺/待办」关键词 → 顿悟可能是「此刻想起...」
    - 如果旧记忆含「物品/货物/买卖」关键词 → 顿悟可能是「这才明白...」
    - 如果旧记忆含「情感/恩怨」关键词 → 顿悟可能是「心头翻涌...」
    - 其他情况 → 泛化顿悟「忽然想到..."

    这种简化的语义匹配降低了 LLM 开销,同时保留了"旧事看懂了"的核心体验。
    2026-05-24 改进：新增情感/恩怨模式、泛化模板增至 5 种备选以增加多样性。
    """
    # 关键词模式匹配（5 类）
    suspicion_kw = ("怀疑", "传闻", "道听途说", "有人说", "似乎", "好像", "疑心", "可疑")
    promise_kw = ("约定", "承诺", "说过", "待办", "以后", "下次", "回头", "改日")
    goods_kw = ("物品", "货物", "买卖", "银子", "钱", "制钱", "货", "买", "卖", "价")
    person_kw = ("某人", "那人", "他", "她", "谁", "有人")
    emotion_kw = ("恨", "怨", "怒", "悲", "痛", "悔", "愧", "思念", "感激", "欢喜", "恩", "仇")

    old_lower = old_text.lower()
    snippet = old_text[:50].strip()

    import random
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
    # 泛化顿悟：旧事与新事的碰撞（5 种备选模板）
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

def text_relevance(query: str, doc: str) -> float:
    """基于词/字符二元组的 Jaccard 相似度。0..1。"""
    a, b = _tokenize(query), _tokenize(doc)
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0

def _decay_recency(seconds_since: float, half_life_s: float = 3600.0 * 6) -> float:
    """指数衰减;默认 6 小时半衰期。返回 0..1。"""
    if seconds_since <= 0:
        return 1.0
    return math.exp(-math.log(2.0) * seconds_since / max(1.0, half_life_s))

# ─── 数据结构 ─────────────────────
@dataclass
class Memory:
    id: str
    kind: str                    # observation | reflection | insight | plan | seed | anchor
    text: str
    importance: float            # 1..10
    created_day: int             # 世界第几日
    created_shichen: str         # 世界时辰名
    created_at: float            # epoch 秒
    last_accessed: float         # epoch 秒
    refs: list[str] = field(default_factory=list)  # 反思记忆引用的来源记忆 id
    is_anchor: bool = False      # 情感锚点:关键时刻永久写入

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "text": self.text,
            "importance": float(self.importance),
            "created_day": int(self.created_day),
            "created_shichen": self.created_shichen,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "refs": list(self.refs),
            "is_anchor": self.is_anchor,
        }

# ── NPC 情感状态(2025-2026 AI情感计算前沿落地)──
# 注:MOOD_LABELS 仅为参考常量,实际 mood 标签由 _mood_from_valence_arousal() 动态计算
MOOD_LABELS = ("欣悦", "平静", "疲惫", "烦躁", "忧悒", "警觉", "愤懑", "好奇", "感怀", "冷淡", "兴奋", "安然")

# ── 情感锚点阈值(2026 AI情感计算前沿:关键时刻永久写入)──
ANCHOR_VALENCE_THRESHOLD = 4.0    # 效价变化超过此值 → 产生锚点
ANCHOR_AROUSAL_THRESHOLD = 3.0   # 唤醒度变化超过此值 → 产生锚点
ANCHOR_IMPORTANCE = 9.0          # 锚点记忆的基础重要性(接近最高)
ANCHOR_HALF_LIFE_S = 3600.0 * 48 # 锚点衰减极慢(48小时半衰期 vs 普通记忆6小时)

def _mood_from_valence_arousal(valence: float, arousal: float) -> str:
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

@dataclass
class AgentMind:
    """单个 NPC(在某玩家会话下)的心智:记忆流 + 当日计划 + 情感状态。"""

    items: list[Memory] = field(default_factory=list)
    importance_since_reflect: float = 0.0  # 自上次反思以来累计的重要性
    last_reflect_at: float = 0.0
    plan_day: int | None = None              # 计划是为哪一日编的
    plan_by_shichen: dict[str, str] = field(default_factory=dict)  # shichen -> 一句话日程
    plan_summary: str = ""                   # 整日计划摘要(用于注入 system prompt)
    # ── 情感状态(AI情感计算)──
    affect_valence: float = 0.0      # 效价 -10..10(负→正情绪)
    affect_arousal: float = 5.0      # 唤醒度 0..10(平静→激动)
    affect_mood: str = "平静"        # 当前情绪标签
    affect_cause: str = ""           # 最近情绪变化缘由(一句白话)
    affect_updated_at: float = 0.0   # epoch 秒,最近一次情绪更新
    last_insight_at: float = 0.0      # epoch 秒,最近一次顿悟(A-Mem记忆演化)
    linked_memory_ids: set = field(default_factory=set)  # 已建立过链接的记忆ID集合(防重复链接)

    def add(self, mem: Memory, *, _skip_evolve: bool = False) -> None:
        self.items.append(mem)
        if mem.kind == "observation":
            self.importance_since_reflect += mem.importance
            # A-Mem 记忆演化:新观察与旧记忆碰撞时可能产生「顿悟」
            if not _skip_evolve:
                self._try_evolve_on_new_observation(mem)

    def _try_evolve_on_new_observation(self, new_obs: Memory) -> None:
        """A-Mem 记忆演化落地(NeurIPS 2025 A-Mem: Agentic Memory for LLM Agents)

        核心思想:当新观察与旧记忆产生语义链接时,NPC 对过去的理解可能深化--
        这不是"记住了新事",而是"旧事忽然看懂了"。

        实现策略(纯启发式,零 LLM 调用):
        1. 新观察与旧观察做关键词重叠检测(复用 jieba 分词)
        2. 找到语义关联最强的旧记忆
        3. 如果关联超过阈值且最近无顿悟,生成一条「顿悟」记忆
        4. 顿悟记忆是 reflection 的子类,text 格式为「想起{旧事},{新悟}」
        """
        import time as _time

        now = _time.time()
        # 冷却期内不触发顿悟
        if (now - self.last_insight_at) < INSIGHT_COOLDOWN_S:
            return

        new_tokens = _tokenize(new_obs.text)
        if len(new_tokens) < 2:
            return

        best_link: Memory | None = None
        best_score = 0.0

        for old in self.items:
            # 只与观察类旧记忆链接(反思/计划/种子不参与)
            if old.kind != "observation":
                continue
            # 不与自身链接
            if old.id == new_obs.id:
                continue
            # 已链接过的记忆不再重复链接
            if old.id in self.linked_memory_ids:
                continue
            # 只取7天内的旧记忆(太久的不太可能顿悟)
            if (now - old.created_at) > 7 * 86400:
                continue
            # 旧记忆的时辰必须在当前观察之前(因果方向)
            if old.created_at >= new_obs.created_at:
                continue

            old_tokens = _tokenize(old.text)
            if not old_tokens:
                continue

            # Jaccard 相似度
            overlap = len(new_tokens & old_tokens)
            union = len(new_tokens | old_tokens)
            score = overlap / union if union else 0.0

            # 重要性加权:旧记忆越重要,链接越有价值
            score *= (old.importance / 10.0)

            if score > best_score:
                best_score = score
                best_link = old

        if best_link is None or best_score < INSIGHT_LINK_THRESHOLD:
            return

        # 生成顿悟记忆
        old_summary = best_link.text[:60]
        new_summary = new_obs.text[:60]

        # 检查旧记忆文本中是否有因果关系线索(简化的语义模式匹配)
        insight_text = _generate_insight_text(old_summary, new_summary, best_link.importance)

        insight_mem = make_memory(
            kind="insight",  # 新记忆类型
            text=insight_text[:200],
            importance=min(10.0, best_link.importance + INSIGHT_IMPORTANCE_BOOST),
            world_day=new_obs.created_day,
            world_shichen=new_obs.created_shichen,
            refs=[best_link.id, new_obs.id],
        )

        # 标记旧记忆已链接,避免重复顿悟
        self.linked_memory_ids.add(best_link.id)
        self.last_insight_at = now

        # 写入顿悟(递归调用 add,但跳过演化以防止无限递归)
        self.add(insight_mem, _skip_evolve=True)

        log.info("记忆演化顿悟: [%s] ← [%s] → %s",
                 best_link.id[:8], new_obs.id[:8], insight_text[:60])

    def needs_reflect(self) -> bool:
        # 情绪驱动反思加速（2026 情感计算前沿）：极端情绪使阈值降低
        effective_threshold = self._emotion_adjusted_reflect_threshold()
        if self.importance_since_reflect < effective_threshold:
            return False
        if (time.time() - self.last_reflect_at) < REFLECTION_MIN_INTERVAL_S:
            return False
        return True

    def _emotion_adjusted_reflect_threshold(self) -> float:
        """情绪越极端，反思阈值越低——让 NPC 在激动时更容易自省。

        效价极值（大喜大悲）：阈值最多降至 18（从默认 35）
        唤醒度极值（激动/警觉）：阈值最多再降 5
        组合极端：阈值最低可降至 13"""
        threshold = REFLECTION_IMPORTANCE_TRIGGER  # 35.0
        # 效价削减：|valence| > 5 开始降低
        valence_impact = max(0.0, abs(self.affect_valence) - 5.0) * 2.5
        threshold -= valence_impact
        # 唤醒度削减：arousal > 6 开始降低
        arousal_impact = max(0.0, self.affect_arousal - 6.0) * 1.5
        threshold -= arousal_impact
        return max(13.0, threshold)

    def update_mood(self, valence_delta: float = 0.0, arousal_delta: float = 0.0, cause: str = "") -> bool:
        """演化 NPC 情绪:效价与唤醒度按 delta 滑动,再映射到标签。

        返回 True 表示产生了情感锚点(情绪巨变时刻)。"""
        old_valence = self.affect_valence
        old_arousal = self.affect_arousal
        self.affect_valence = max(-10.0, min(10.0, self.affect_valence + valence_delta))
        self.affect_arousal = max(0.0, min(10.0, self.affect_arousal + arousal_delta))
        self.affect_mood = _mood_from_valence_arousal(self.affect_valence, self.affect_arousal)
        if cause:
            self.affect_cause = cause[:80]
        self.affect_updated_at = time.time()

        # 情感锚点检测:效价或唤醒度有大幅变化时,标记为锚点时刻
        is_anchor = (
            abs(valence_delta) >= ANCHOR_VALENCE_THRESHOLD
            or abs(arousal_delta) >= ANCHOR_AROUSAL_THRESHOLD
        )
        return is_anchor

    def mood_decay_tick(self, world_shichen: str) -> None:
        """时辰推进时情绪的缓慢回归(向中性漂移)。只在对话/反思之外被调用。"""
        # 夜深时唤醒度自然下降;白日唤醒度微升
        night_shichen = {"子时", "丑时", "寅时", "戌时", "亥时"}
        if world_shichen in night_shichen:
            self.update_mood(arousal_delta=-0.6, cause="夜深人倦")
        else:
            self.update_mood(arousal_delta=+0.15, cause="白昼渐醒")
        # 效价缓慢回归中性
        if abs(self.affect_valence) > 1.0:
            drift = -0.3 if self.affect_valence > 0 else +0.3
            self.update_mood(valence_delta=drift, cause="情绪渐平")

    def recent_observations(self, k: int = 30) -> list[Memory]:
        """取最近若干条观察"""
        kinds = ("observation",)
        out = [m for m in self.items if m.kind in kinds]
        return out[-k:]

    def memory_stats(self) -> dict[str, int]:
        """统计各类记忆数量。"""
        counts: dict[str, int] = {}
        for m in self.items:
            counts[m.kind] = counts.get(m.kind, 0) + 1
        return counts

    def reflections(self) -> list[Memory]:
        return [m for m in self.items if m.kind == "reflection"]

    def seeds(self) -> list[Memory]:
        return [m for m in self.items if m.kind == "seed"]

    def insights(self) -> list[Memory]:
        """返回所有顿悟记忆(A-Mem 记忆演化产生)。"""
        return [m for m in self.items if m.kind == "insight"]

    def serialize(self) -> dict[str, Any]:
        return {
            "items": [m.to_dict() for m in self.items],
            "importance_since_reflect": float(self.importance_since_reflect),
            "last_reflect_at": float(self.last_reflect_at),
            "plan_day": self.plan_day,
            "plan_by_shichen": dict(self.plan_by_shichen),
            "plan_summary": self.plan_summary,
            "affect_valence": float(self.affect_valence),
            "affect_arousal": float(self.affect_arousal),
            "affect_mood": self.affect_mood,
            "affect_cause": self.affect_cause,
            "last_insight_at": float(self.last_insight_at),
            "linked_memory_ids": list(self.linked_memory_ids),  # set → list for JSON
        }

# ─── 操作 ─────────────────────
def make_memory(
    *,
    kind: str,
    text: str,
    importance: float,
    world_day: int,
    world_shichen: str,
    refs: Iterable[str] | None = None,
) -> Memory:
    now = time.time()
    return Memory(
        id=uuid.uuid4().hex[:10],
        kind=kind,
        text=(text or "").strip()[:500],
        importance=max(1.0, min(10.0, float(importance))),
        created_day=int(world_day),
        created_shichen=str(world_shichen),
        created_at=now,
        last_accessed=now,
        refs=list(refs or []),
    )

def estimate_importance_heuristic(text: str) -> float:
    """轻量启发式:用关键词与长度估重要性。"""
    s = text or ""
    if not s:
        return 1.0
    base = 3.0
    # 长度越长越值得记
    base += min(2.0, len(s) / 80.0)
    # 重要关键词加权
    for kw, w in (
        ("死", 3.0), ("杀", 3.0), ("毒", 2.5), ("命", 1.5),
        ("贿", 1.5), ("银", 1.0), ("钱", 0.5), ("票", 1.0),
        ("信物", 2.0), ("信函", 1.5), ("路引", 1.5), ("帖子", 1.5),
        ("叛", 2.5), ("仇", 2.0), ("救", 1.5), ("赎身", 2.0),
        ("县衙", 1.0), ("漕口", 1.0), ("书院", 0.8), ("镖局", 1.0), ("绿林", 1.5),
    ):
        if kw in s:
            base += w
    return max(1.0, min(10.0, base))

# ── 心境一致性记忆检索（2026 情感计算前沿·情绪一致性偏差）──
# 当 NPC 情绪较强时（|valence| >= 3），检索记忆时会偏向与当前情绪
# 一致的旧忆——愤怒时更易记起旧怨，欣悦时更常想起好事。
# 这是对人类「心境一致性记忆」（mood-congruent memory）的落地。
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


def _sentiment_hint(text: str) -> float:
    """启发式情感倾向估计：扫描记忆文本中的情感词，
    返回 -1.0（全负面）~ +1.0（全正面）的倾向值。

    用于心境一致性记忆检索——帮助 NPC 在愤怒时偏重记起负面往事，
    在欣悦时更容易浮现美好回忆。"""
    t = (text or "").lower()
    pos = sum(1 for kw in _POSITIVE_MEMORY_WORDS if kw in t)
    neg = sum(1 for kw in _NEGATIVE_MEMORY_WORDS if kw in t)
    total = pos + neg
    if total == 0:
        return 0.0  # 中性
    # 归一化到 -1..1
    ratio = (pos - neg) / total
    # 温和缩放：少量词命中时信号弱
    confidence = min(1.0, total / 4.0)  # 4个以上命中才算全信
    return ratio * confidence


def retrieve(
    mind: AgentMind,
    query: str,
    *,
    k: int = 6,
    half_life_s: float = 3600.0 * 6,
    player_name: str | None = None,
) -> list[Memory]:
    """按斯坦福式分数检索:recency × importance × relevance(线性加权)。

    2026-05-25 改进：融入心境一致性偏差（mood-congruent memory）。
    当 NPC 情绪较强时（|affect_valence| >= 3），与当前心境一致的
    记忆会得到微幅加成——愤怒者更易记起旧怨，欣悦者更常想起好事。
    这使 NPC 的回忆更符合人类的心理真实。

    2026-05-25 改进：熟人引航（acquaintance priming）。
    当提供 player_name 时，记忆文本中含玩家姓名的条项获得微幅加成，
    让 NPC 更自然地回忆起与此人的直接互动，而非泛泛记忆。
    加成幅度 0.06，约为反思/种子记忆加成 1.2 倍，温和但能引导优先序。"""
    if not mind.items:
        return []
    now = time.time()
    scored: list[tuple[float, Memory]] = []
    rel_max = 0.0
    rels: list[float] = []
    for m in mind.items:
        rel = text_relevance(query, m.text)
        rels.append(rel)
        if rel > rel_max:
            rel_max = rel
    # ── 心境一致性偏差：情绪较强时启用 ──
    mood_valence = float(getattr(mind, 'affect_valence', 0.0) or 0.0)
    apply_mood_bias = abs(mood_valence) >= _MOOD_BIAS_THRESHOLD
    for m, rel in zip(mind.items, rels):
        # 归一化:importance/10;recency 衰减;relevance/rel_max(避免一边倒)
        rec = _decay_recency(now - m.last_accessed, half_life_s)
        imp = m.importance / 10.0
        rel_norm = (rel / rel_max) if rel_max > 0 else 0.0
        # 反思与种子记忆给小幅加成;锚点记忆给大幅加成(关键时刻永不忘记)
        bonus = 0.05 if m.kind in ("reflection", "cross_reflection", "seed", "insight") else 0.0
        if m.is_anchor or m.kind == "anchor":
            bonus += 0.35   # 锚点记忆几乎总是被检索到
        # ── 熟人引航：与当前玩家直接相关的记忆轻微加成 ──
        if player_name and player_name in m.text:
            bonus += 0.06  # 温和加成，引导优先检索与当前玩家的互动记忆
        # ── 心境一致性偏差：情绪极性一致的记忆更容易浮起 ──
        if apply_mood_bias:
            sent = _sentiment_hint(m.text)  # -1..1
            # 心境一致：sent 符号与 mood_valence 符号相同 ⇒ 正值 ⇒ 加成
            mood_congruence = sent * (mood_valence / 10.0)
            bonus += mood_congruence * _MOOD_BIAS_WEIGHT
        score = (W_RECENCY * rec) + (W_IMPORTANCE * imp) + (W_RELEVANCE * rel_norm) + bonus
        scored.append((score, m))
    scored.sort(key=lambda kv: kv[0], reverse=True)
    top = [m for _, m in scored[: max(1, int(k))]]
    # 命中即视为「访问过」,刷新 recency
    for m in top:
        m.last_accessed = now
    return top

def format_memories_for_prompt(mems: list[Memory]) -> str:
    """把命中的记忆条整理为给 LLM 注入的文本。"""
    if not mems:
        return ""
    lines = ["【你的脑中浮起几条记忆(自语,不必复述)】"]
    for m in mems:
        tag = {
            "observation": "见闻",
            "reflection": "心得",
            "cross_reflection": "人事察觉",
            "insight": "顿悟",
            "condensation": "往事凝华",
            "plan": "计议",
            "seed": "本心",
            "anchor": "◆心锚",
        }.get(m.kind, "记")
        stamp = f"第{m.created_day}日·{m.created_shichen}"
        lines.append(f"· [{tag} · {stamp}] {m.text}")
    return "\n".join(lines)

def format_plan_for_prompt(mind: AgentMind, world_shichen: str) -> str:
    if not mind.plan_summary and not mind.plan_by_shichen:
        return ""
    lines = ["【今日你心里盘算的事】"]
    if mind.plan_summary:
        lines.append(f"· 总:{mind.plan_summary}")
    if mind.plan_by_shichen:
        cur = mind.plan_by_shichen.get(world_shichen, "")
        if cur:
            lines.append(f"· 此刻({world_shichen})该做:{cur}")
        else:
            # 给两条最临近的
            for sh, text in list(mind.plan_by_shichen.items())[:2]:
                lines.append(f"· {sh}:{text}")
    return "\n".join(lines)

def format_mood_for_prompt(mind: AgentMind) -> str:
    """将 NPC 当前情绪状态注入 system prompt(AI情感计算落地)。"""
    mood = mind.affect_mood or "平静"
    valence = mind.affect_valence
    arousal = mind.affect_arousal
    # 情绪强度描述
    if arousal >= 7.0:
        intensity = "情绪翻涌"
    elif arousal >= 4.5:
        intensity = "心绪浮动"
    elif arousal >= 2.0:
        intensity = "心神尚定"
    else:
        intensity = "心如止水"
    # 效价语气指引
    if valence >= 6:
        tone_hint = "言谈间自然流露出温煦、宽容、好说话的神色"
    elif valence >= 2:
        tone_hint = "语气比平日和缓,遇事多往好处想"
    elif valence <= -6:
        tone_hint = "话里带刺、易恼、不肯轻易通融--但也别写成歇斯底里"
    elif valence <= -2:
        tone_hint = "比起往常多了几分不耐与冷淡"
    else:
        tone_hint = "神情话语皆在常度"

    lines = [
        f"【你此刻的心绪】{mood}({intensity})。",
        f"· {tone_hint}。",
    ]
    if mind.affect_cause:
        lines.append(f"· 心绪由来:{mind.affect_cause}")
    lines.append("· 请据心绪自然写出语气、用词、耐心多寡;但不要原句复述此块内容。")
    return "\n".join(lines)


def format_plan_for_reflection(mind: AgentMind, world_shichen: str) -> str:
    """将 NPC 当日计划格式化为反思用上下文（2026 计划-现实对照反思）。

    让 NPC 在反思时能对照「原本打算做什么」与「实际发生了什么」，
    产生更丰富、更人性化的洞察——比如懊悔未完成、庆幸意外发现、调整剩余日程。

    仅返回 1~3 句，简洁，不喧宾夺主。"""
    if not mind.plan_summary and not mind.plan_by_shichen:
        return ""

    lines = ["【你今日原定的计划】"]
    if mind.plan_summary:
        lines.append(f"· 总：{mind.plan_summary}")
    # 当前时辰及之后的计划（已过的就不提了）
    shichen_order = ["子时", "丑时", "寅时", "卯时", "辰时", "巳时",
                     "午时", "未时", "申时", "酉时", "戌时", "亥时"]
    try:
        cur_idx = shichen_order.index(world_shichen)
    except ValueError:
        cur_idx = 0
    remaining = []
    for sh in shichen_order[cur_idx:]:
        plan = mind.plan_by_shichen.get(sh)
        if plan:
            remaining.append(f"{sh} {plan}")
    for sh in shichen_order[:cur_idx]:
        plan = mind.plan_by_shichen.get(sh)
        if plan:
            remaining.append(f"{sh}(已过) {plan}")
    if remaining:
        for r in remaining[:4]:  # 最多展示4条
            lines.append(f"· {r}")
    lines.append("· 对照所见，若计划未竟或形势有变，心里怎么想——可融入洞察。")
    return "\n".join(lines)


def format_mood_for_reflection(mind: AgentMind) -> str:
    """将 NPC 情绪状态格式化为反思用内部描述（用于反思/cross_reflect 的 prompt 注入）。
    
    与 format_mood_for_prompt 不同，这个版本更简洁，专为内部推理设计：
    - 不给出语气指引（反思是内心活动）
    - 强调情绪如何扭曲/染色记忆检索与洞察生成
    """
    mood = mind.affect_mood or "平静"
    v = mind.affect_valence
    a = mind.affect_arousal
    
    # 情绪对反思的染色描述
    if v >= 6 and a >= 6:
        tint = "你此刻心境欣悦而激动，容易对人事往好处想，对善意格外敏感"
    elif v >= 4 and a >= 4:
        tint = "你心情不错，精神亢奋，反思时更容易联想到积极的可能"
    elif v >= 2:
        tint = "你心气平和偏暖，反思时倾向宽容与理解"
    elif v <= -6 and a >= 6:
        tint = "你又怒又痛，此刻的反思容易被愤懑染色——对得罪过你的人印象会更恶"
    elif v <= -4 and a >= 4:
        tint = "你心头有气，反思时容易往阴谋、恶意的方向揣测"
    elif v <= -2:
        tint = "你心情低落或戒备，反思时更难信任他人"
    elif a >= 7:
        tint = "你情绪激动，反思时思绪跳跃，容易从一件小事牵扯出很多旧事"
    elif a <= 2:
        tint = "你心如止水，反思时格外冷静，像个旁观者"
    else:
        tint = "你情绪平稳，反思时较为中立"
    
    lines = [
        f"【反思时的心境】{mood}（效价{v:+.1f}，唤醒度{a:.1f}）。",
        f"· {tint}。",
    ]
    if mind.affect_cause:
        lines.append(f"· 这份心绪因何而起：{mind.affect_cause}")
    return "\n".join(lines)


def format_proactive_callbacks(mind: AgentMind, player_name: str) -> str:
    """NPC 主动回扣(2026 AI NPC Proactive Callback 前沿落地)。

    从记忆流中抽取 NPC 应该主动提及的关键细节:
    - 情感锚点:过往重大时刻的残留影响
    - 未完成约定:玩家曾答应但未兑现的事
    - 玩家提及的关键偏好/秘密:NPC 记住了但未回扣的细节
    - 好感关联事件:好感大幅变化时的因果

    让 NPC 不再是"问才答"的被动角色,而是有记忆温度的活人。"""
    anchors = [m for m in mind.items if m.is_anchor or m.kind == "anchor"]
    # 取最近的观察,寻找可回扣的细节
    recent_obs = [m for m in mind.items if m.kind == "observation"][-10:]

    callback_lines: list[str] = []

    # 1) 情感锚点回扣:最近3个锚点时刻
    if anchors:
        callback_lines.append("【你心里过不去的坎/放不下的时刻】")
        for a in anchors[-3:]:
            stamp = f"第{a.created_day}日·{a.created_shichen}"
            callback_lines.append(f"· [{stamp}] {a.text[:120]}")
        callback_lines.append("· 在对话中可以自然提起这些旧事--不必生硬,像人想起旧事那样。")

    # 2) 未回扣的玩家细节:从观察中寻找玩家曾提到但尚未回应的线索
    unattended: list[str] = []
    for m in recent_obs:
        t = m.text
        # 检测玩家曾提及的偏好/请求/承诺
        for kw in ("喜欢", "怕", "想要", "答应", "改日", "回头", "下次", "等我", "一定"):
            if kw in t and player_name in t:
                unattended.append(t[:80])
                break
    if unattended:
        callback_lines.append("【此人曾对你说过但尚未回扣的话】")
        for u in unattended[-3:]:
            callback_lines.append(f"· {u}")
        callback_lines.append("· 如果合适,可以自然地提起--像记得朋友说过的话那样。")

    if not callback_lines:
        return ""

    return "\n".join(callback_lines)


def _resolve_deictic(user_message: str, hist_slice: list[dict[str, str]]) -> str:
    """中文代词/指示词消解（2026 AI对话连贯性前沿落地）。

    当玩家说「他后来怎样了」「那件事呢」「此人可否信任」时，
    代词/指示词（他/她/它/这/那/此人/那个/这种）无法命中记忆检索。

    本函数检测玩家消息中的指代词，从最近对话历史中提取最可能的
    实体名/话题词替换指代词，让检索查询变成具体可检索的短语。

    设计策略：
    1. 检测中文人称代词（他/她/它/他们/她们）、指示代词（这/那/此/该）
    2. 从最近2轮对话中提取出现过的具体人名/实体
    3. 将指代词替换为最可能的具体实体，生成富查询

    Returns:
        消解后的增强查询字符串。若无需消解则返回空字符串。
    """
    if not hist_slice or len(hist_slice) < 1:
        return ""

    msg = user_message.strip()
    if not msg:
        return ""

    # ── 中文指代词检测 ──
    PERSON_PRONOUNS = {"他", "她", "它", "他们", "她们", "它们", "其"}
    DEICTIC_NOUNS = {"这人", "那人", "此人", "彼", "这位", "那位", "该人"}
    DEICTIC_PREFIX = {"这", "那", "此", "该"}
    DEICTIC_THINGS = {"这事", "那事", "那件事", "这件事", "此", "这个", "那个", "这种", "那种"}

    has_person_pronoun = any(p in msg for p in PERSON_PRONOUNS)
    has_deictic_noun = any(d in msg for d in DEICTIC_NOUNS)
    has_deictic_thing = any(d in msg for d in DEICTIC_THINGS)

    # 扩展：检测「这/那/此 + 实体名」模式（如「那帖子」「这笔买卖」「此路引」）
    # 这些应和代词/指示词一样触发消解——之前因常量定义顺序导致此检测为死代码
    ALL_ENTITIES = ALL_ENTITY_KEYWORDS
    has_deictic_entity = False
    for ent in ALL_ENTITIES:
        for prefix in ("这", "那", "此"):
            if f"{prefix}{ent}" in msg:
                has_deictic_entity = True
                break
        if has_deictic_entity:
            break

    if not (has_person_pronoun or has_deictic_noun or has_deictic_thing or has_deictic_entity):
        return ""

    # ── 从最近2轮对话中提取所有命中的实体（使用模块级共享常量）──
    recent = hist_slice[-2:]
    found_persons: list[str] = []
    found_places: list[str] = []
    found_things: list[str] = []
    seen: set[str] = set()

    for turn in recent:
        # NPC回复中的人名往往是当前讨论焦点
        assistant_text = (turn.get("assistant", "") or "").lower()
        user_text = (turn.get("user", "") or "").lower()
        combined = assistant_text + " " + user_text

        for pn in PERSON_NAMES:
            if pn.lower() in combined and pn not in seen:
                found_persons.append(pn)
                seen.add(pn)
        for pl in PLACE_NAMES:
            if pl.lower() in combined and pl not in seen:
                found_places.append(pl)
                seen.add(pl)
        for tk in THING_KEYWORDS:
            if tk.lower() in combined and tk not in seen:
                found_things.append(tk)
                seen.add(tk)

    # 构建消解词：按指代类型选择最可能的实体
    resolved_terms: list[str] = []

    if has_person_pronoun or has_deictic_noun or has_deictic_entity:
        # 代词指人/指实体 → 取最近出现的人名或事物（优先NPC回复中的，因为那更可能是话题焦点）
        for turn in reversed(recent):
            assistant_text = (turn.get("assistant", "") or "").lower()
            for pn in PERSON_NAMES:
                if pn.lower() in assistant_text:
                    if pn not in resolved_terms:
                        resolved_terms.append(pn)
                    break
            if resolved_terms:
                break
        # 如果NPC回复没有，从玩家消息中找
        if not resolved_terms:
            for pn in reversed(found_persons[:2]):
                resolved_terms.append(pn)

    if has_deictic_thing or has_deictic_entity:
        # 指示事物/实体 → 取最近出现的事物关键词
        for turn in reversed(recent):
            assistant_text = (turn.get("assistant", "") or "").lower()
            for tk in THING_KEYWORDS:
                if tk.lower() in assistant_text:
                    if tk not in resolved_terms:
                        resolved_terms.append(tk)
                    break
            if any(t in THING_KEYWORDS for t in resolved_terms):
                break
        if not any(t in THING_KEYWORDS for t in resolved_terms):
            for tk in reversed(found_things[:2]):
                if tk not in resolved_terms:
                    resolved_terms.append(tk)

    # 如果什么都没消解出来（白名单无命中），回退到原查询
    if not resolved_terms:
        return ""

    # 生成消解短语：原消息 + 具体实体
    resolved_phrase = " ".join(resolved_terms[:3])
    return f"{user_message} {resolved_phrase}"


def build_retrieval_query(user_message: str, hist_slice: list[dict[str, str]]) -> str:
    """上下文感知的记忆检索查询构建（2026 AI对话连贯性前沿落地）。

    单纯用 user_message 检索记忆会丢失对话语境——
    玩家若说「那件事后来怎么样了」，检索词「那件事」命中率极低。

    本函数从最近几轮对话历史中提取关键词/实体/话题线，
    与当前消息拼接成更丰富的检索查询，大幅提升记忆召回精度。

    设计策略：
    1. 中文代词/指示词消解：「他」→「掌柜」,「那件事」→「路引 那件事」
    2. 从最近3轮对话中提取关键名词（人名、地名、物品名）
    3. 检出玩家最近的提问未完结话题
    4. 将话题链拼入 user_message 形成复合检索词
    """
    # ── 第0步：中文代词/指示词消解（2026-05-24 新增）──
    pronoun_resolved = _resolve_deictic(user_message, hist_slice)

    if len(hist_slice) < 2:
        return pronoun_resolved or user_message

    recent = hist_slice[-4:]  # 取最近4轮
    topic_words: list[str] = []

    # 1) 从对话历史中抽取实体关键词（使用模块级共享常量）
    seen_words: set[str] = set()
    for turn in recent:
        combined = (turn.get("user", "") + " " + turn.get("assistant", "")).lower()
        for kw in ALL_ENTITY_KEYWORDS:
            if kw in combined and kw not in seen_words:
                topic_words.append(kw)
                seen_words.add(kw)

    # 2) 检测玩家最近的提问（未完结话题信号）
    for turn in recent:
        user_msg = (turn.get("user") or "").lower()
        for q_marker in ("?", "？", "吗", "呢", "如何", "怎么", "可否"):
            if q_marker in user_msg:
                # 取问句核心词（问号附近的词）
                q_idx = max(0, user_msg.index(q_marker) - 20)
                snippet = user_msg[q_idx:q_idx + 30]
                for kw in ALL_ENTITY_KEYWORDS:
                    if kw in snippet and kw not in seen_words:
                        topic_words.append(kw)
                        seen_words.add(kw)
                break

    # ── 优先使用代词消解结果（更精准），话题链作为补充 ──
    if pronoun_resolved:
        if topic_words:
            topic_chain = " ".join(topic_words[:4])
            return f"{pronoun_resolved} {topic_chain}"
        return pronoun_resolved

    if not topic_words:
        return user_message

    # 构建复合检索查询：当前消息 + 话题链关键词
    topic_chain = " ".join(topic_words[:6])  # 最多6个关键词
    return f"{user_message} {topic_chain}"


def format_topic_thread(hist_slice: list[dict[str, str]]) -> str:
    """对话话题线程跟踪(2026 AI对话连贯性前沿落地)。

    从最近几轮对话历史中提取当前正在讨论的话题线索,
    让 NPC 不会在连续对话中突然跳题或遗忘正在谈的事。

    设计思路:
    - 不需要 LLM 调用,纯本地启发式
    - 追踪关键词、未完结的问句、进行中的交易/请求
    - 注入 system prompt 提醒 NPC 保持话题连贯
    """
    if len(hist_slice) < 2:
        return ""

    # 取最近3轮
    recent = hist_slice[-3:]

    # 提取未完结话题的信号词
    pending_signals: list[str] = []
    topic_keywords: set[str] = set()

    for turn in recent:
        user_msg = (turn.get("user") or "").lower()
        # 检测未完结的提问
        for q_marker in ("?", "?", "吗", "呢", "如何", "怎么", "可否", "能否"):
            if q_marker in user_msg:
                # 截取问句
                q_idx = user_msg.index(q_marker)
                start = max(0, q_idx - 15)
                pending_signals.append(f"待答之问:...{user_msg[start:q_idx+2]}")
                break
        # 检测进行中的交易/请求
        for tx_marker in ("价", "多少钱", "多少文", "买", "卖", "换", "抵押", "典当"):
            if tx_marker in user_msg:
                pending_signals.append(f"待定买卖:{user_msg[:30]}")
                break
        # 提取话题关键词
        for kw in ("路引", "信物", "帖子", "信函", "药", "地图", "船", "马", "镖", "银", "钱",
                   "毒", "死", "杀", "逃", "救", "帮", "找", "见", "等"):
            if kw in user_msg and kw not in topic_keywords:
                topic_keywords.add(kw)

    if not pending_signals and not topic_keywords:
        return ""

    lines = ["【对话线程·保持连贯】"]
    if topic_keywords:
        kws = "、".join(list(topic_keywords)[:5])
        lines.append(f"· 你们正在谈论:{kws}--请围绕这些事回话,不要突然跳题。")
    if pending_signals:
        for ps in pending_signals[-3:]:
            lines.append(f"· {ps}--如果你还没正面回答,请先回应。")
    lines.append("· 如果玩家追问同一件事,说明他在意--别岔开,给出进展或新信息。")

    return "\n".join(lines)

def affective_memory_importance(base_importance: float, mind: AgentMind) -> float:
    """情感记忆加权(2026 AI Memory 前沿):情绪越强烈,记忆越深。

    效价极值(大喜大悲)和唤醒度峰值均为记忆加成。
    对平静期的琐碎事件不做额外提权。"""
    arousal_bonus = max(0.0, (mind.affect_arousal - 5.0) * 0.4)  # 高于5唤醒度才有加成
    valence_bonus = abs(mind.affect_valence) * 0.15             # 极端情绪(无论正负)加深记忆
    bonus = arousal_bonus + valence_bonus
    return min(10.0, base_importance + bonus)


# ─── 共享实体关键词（中文代词/指示词消解 & 检索查询构建共用）───
# 保持各处一致，避免独立维护导致白名单不一致

PERSON_NAMES = (
    "掌柜", "牙人", "皂隶", "镖头", "黑店", "匪首", "船家", "阿泠",
    "里正", "驿卒", "知客", "帮掌", "书生", "卡吏", "风闻", "江",
)

PLACE_NAMES = (
    "同福", "牙行", "镖局", "县衙", "渡头", "画舫", "野径",
    "芦花", "佛寺", "书院", "厘卡", "漕口", "驿舍", "碾坊",
)

THING_KEYWORDS = (
    "路引", "信物", "帖子", "信函", "银子", "制钱", "药", "毒",
    "镖", "船", "马", "刀", "剑", "赎身", "缉文", "帮规",
    "鲜鱼", "干粮", "野果",
)

EVENT_KEYWORDS = (
    "杀", "仇", "逃", "救", "帮", "买卖", "赊欠", "火并",
    "走私", "偷渡", "贿赂", "典当", "盘店", "搭股",
)

# 用于 build_retrieval_query 话题链抽取的全量白名单
ALL_ENTITY_KEYWORDS = PERSON_NAMES + PLACE_NAMES + THING_KEYWORDS + EVENT_KEYWORDS

# ─── CMA·认知记忆凝结(2026前沿:LinkedIn CMA范式落地)───
OBS_CONDENSE_THRESHOLD = 60       # 当 observation 条数超过此阈值时触发凝结
OBS_CONDENSE_BATCH = 20            # 每次凝结处理最旧的约20条
OBS_KEEP_RECENT = 30               # 至少保留最近30条不凝结

# ─── A-Mem 记忆演化(NeurIPS 2025 A-Mem: Agentic Memory 落地)───
INSIGHT_LINK_THRESHOLD = 0.25     # 两条记忆的文本相关度超过此阈值视为可链接
INSIGHT_IMPORTANCE_BOOST = 1.5    # 顿悟记忆的重要性加成
INSIGHT_MAX_PER_ADD = 1           # 每次添加观察最多触发1条顿悟(控制开销)
INSIGHT_COOLDOWN_S = 1800.0       # 同一NPC两次顿悟间至少30分钟(防过频)

def condense_old_observations(mind: AgentMind, world_day: int, world_shichen: str) -> int:
    """CMA式记忆凝结(2026 LinkedIn Cognitive Memory Agent落地)。

    当 NPC 的 observation 记忆超过阈值时,将最旧的若干条压缩为
    一条「冷凝摘要」,人工語義精簡,減少冗餘但保留關鍵因果線索。

    设计取舍:
    - 本地启发式压缩(规则+关键词+聚类),零 LLM 调用开销
    - 旧观察不删除,而是打上 "condensed" 标记在 text 前缀
    - 生成一条新的 condensation 类记忆作为摘要锚点

    返回:凝结条数(被压缩的观察数)。"""
    obs = [m for m in mind.items if m.kind == "observation" and not m.is_anchor]
    if len(obs) <= OBS_CONDENSE_THRESHOLD:
        return 0

    # 取最旧的 OBS_CONDENSE_BATCH 条(保留最近 OBS_KEEP_RECENT 条不碰)
    if len(obs) <= OBS_KEEP_RECENT:
        return 0
    to_condense = obs[: min(OBS_CONDENSE_BATCH, len(obs) - OBS_KEEP_RECENT)]
    if not to_condense:
        return 0

    # 何分组:按提及的势力/角色/主题聚类
    groups: dict[str, list[str]] = {}
    ungrouped: list[str] = []

    KW_GROUPS = {
        "银钱往来": {"银", "钱", "制钱", "铜板", "佣金", "抽头", "孝敬", "赊欠", "进账", "盘店", "搭股"},
        "江湖恩怨": {"杀", "仇", "刀", "血", "命案", "火并", "伏", "截", "绑"},
        "官府事务": {"县衙", "皂隶", "缉文", "班头", "案", "例", "引", "册"},
        "行旅见闻": {"渡", "驿", "马", "镖", "路", "卡", "哨", "桥"},
        "人情往来": {"谢", "求", "托", "帮", "恩", "情", "面", "荐"},
        "货物交易": {"货", "米", "粮", "铜", "瓷", "布", "盐", "茶", "药"},
    }

    for m in to_condense:
        t = m.text
        matched = False
        for grp, kws in KW_GROUPS.items():
            if any(kw in t for kw in kws):
                groups.setdefault(grp, []).append(t)
                matched = True
                break
        if not matched:
            groups.setdefault("日常琐碎", []).append(t)

    # 为每组生成一句冷凝摘要
    summaries: list[str] = []
    for grp, texts in groups.items():
        n = len(texts)
        # 取关键人名/时间
        sample = texts[0][:80] + ("..." if len(texts[0]) > 80 else "")
        summaries.append(f"{grp}约{n}事。如:{sample}")

    # 标记被凝结的观察：从记忆流中移除（不再参与检索）
    # condensation 类记忆作为摘要锚点保留关键信息
    to_condense_ids = {m.id for m in to_condense}
    mind.items = [m for m in mind.items if m.id not in to_condense_ids]

    # 写入一条 condensation 记忆作为摘要锚点
    summary_text = f"记忆凝结：回想往昔，" + ";".join(summaries)[:400]
    mind.add(make_memory(
        kind="condensation",
        text=summary_text,
        importance=7.5,  # 冷凝摘要本身很重要，是长期记忆锚点
        world_day=world_day,
        world_shichen=world_shichen,
    ), _skip_evolve=True)  # 凝结记忆不触发顿悟

    return len(to_condense)


def format_insight_block(mind: AgentMind) -> str:
    """A-Mem 记忆演化顿悟注入（NeurIPS 2025 A-Mem: Agentic Memory 落地）。

    当 NPC 的记忆流中存在「顿悟」记忆时，将其注入对话 system prompt，
    让 NPC 在对话中自然流露出对旧事的新理解——
    不是"我知道了什么"，而是"我忽然想通了什么"。

    设计要点：
    - 只取最近2条顿悟（防止淹没其他上下文）
    - 语气是「隐约感悟」，不是「全知宣言」
    - 顿悟记忆的 refs 指向源观察，但注入时只显示顿悟本身
    """
    all_insights = mind.insights()
    if not all_insights:
        return ""

    # 只取最近2条顿悟
    recent = sorted(all_insights, key=lambda m: m.created_at, reverse=True)[:2]

    lines = ["【你近日的感悟（若话题触发，可自然流露——像不轻意间想通了一桩旧事）】"]
    for m in recent:
        lines.append(f"· {m.text[:120]}")
    lines.append("· 提及时点到为止，不必长篇大论——像想起一桩忽然通了的旧事。")

    return "\n".join(lines)
