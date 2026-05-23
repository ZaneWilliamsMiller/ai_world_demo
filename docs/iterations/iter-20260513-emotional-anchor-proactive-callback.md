# 迭代记录：2026-05-13 NPC情感锚点 + 主动回扣 + 对话题词线程

## 调研背景

### AI前沿调研（2026-05）

**搜索关键词**：
- "LLM agent memory emotional anchoring game NPC 2026"
- "AI NPC proactive callback dialogue coherence memory-driven storytelling 2026"

**关键发现**：

1. **SITS2026 三层协同架构**：LLM推理层 + 记忆增强模块 + 实时环境感知深度耦合，NPC具备上下文连贯对话、长期目标规划、基于玩家行为的动态关系演化
2. **Agent Memory层次化体系**：短期记忆→长期记忆→情节记忆→语义记忆，智能体从交互中自动提炼技能
3. **Latitude Voyage 平台**：NPC记忆+个性系统，解决NPC"失忆症"——每次触发都是同样的台词
4. **叙事连贯性(Coherence)**：AI生成内容需保持逻辑一致性，防止OOC(Out of Character)
5. **Fortnite AI对话系统**：角色可交谈、响应玩家操作、驱动游戏玩法
6. **Agent Memory vs LLM Memory**：Agent Memory解决"智能体如何积累经验、适应环境、持续成长"，而非"模型如何在长对话中不遗忘"

**落地思路**：上述发现指向同一个核心弱点——NPC对话太被动。需要三项关联增强：
- 情感锚点：关键时刻永久写入
- 主动回扣：从记忆中抽取未了之事主动提起
- 话题线程：保持正在谈的话题不跳题

## 迭代内容

### A. backend/memory.py 修改（5处）

1. **新增 `anchor` 记忆类型**
   - Memory.kind 新增 "anchor" 选项
   - Memory 新增 `is_anchor: bool = False` 字段
   - `to_dict()` 包含 is_anchor 字段

2. **情感锚点阈值常量**
   ```python
   ANCHOR_VALENCE_THRESHOLD = 4.0    # 效价变化超过此值 → 产生锚点
   ANCHOR_AROUSAL_THRESHOLD = 3.0   # 唤醒度变化超过此值 → 产生锚点
   ANCHOR_IMPORTANCE = 9.0          # 锚点记忆基础重要性（接近最高）
   ANCHOR_HALF_LIFE_S = 3600.0 * 48 # 锚点衰减极慢（48h vs 普通6h）
   ```

3. **retrieve() 锚点检索加成**
   - 锚点记忆获得 +0.35 检索加成（远高于 reflection/seed 的 +0.05）
   - 确保关键情感时刻高频被召回

4. **condense_old_observations() 跳过锚点**
   - `is_anchor=True` 的记忆不被凝结，保护长期情感印记

5. **新增 format_proactive_callbacks()**
   - 从记忆流中抽取NPC应主动回扣的关键细节
   - 情感锚点：最近3个重大时刻的残留影响
   - 未回扣的玩家细节：检测"喜欢/怕/想要/答应/改日/回头"等信号词
   - 输出自然语言提示注入prompt

6. **新增 format_topic_thread()**
   - 从最近3轮对话历史中提取话题线索
   - 检测未完结的问句（？?吗呢如何怎么可否能否）
   - 检测进行中的交易/请求（价/多少钱/买卖/换/抵押/典当）
   - 提取话题关键词（路引/信物/帖子/药/地图/船/马/镖/银/钱/毒/死/杀/逃/救/帮/找/见/等）
   - 纯启发式，零LLM调用

7. **update_mood() 返回锚点标记**
   - 返回类型从 None 改为 bool
   - 当 |valence_delta| ≥ 4 或 |arousal_delta| ≥ 3 时返回 True

8. **format_memories_for_prompt() 新增 anchor 标签**
   - 锚点记忆显示为"◆心锚"，视觉上与其他记忆区分

### B. backend/services/talk_service.py 修改（2处）

1. **build_npc_messages() 新增两个注入块**
   - `proactive_callbacks`：NPC主动回扣未了之事
   - `topic_thread`：话题连贯性线索

2. **_evolve_npc_mood() 情感锚点创建**
   - 当 `update_mood()` 返回 True 时，自动创建 anchor 记忆
   - 文本格式："{cause}——那一刻在我心里刻下了痕迹。"

## 设计理念

> NPC从"问才答"的被动角色，变为有记忆温度的活人——记得旧事、会主动提起、不会突然跳题。

这个设计直接呼应了2026年AI NPC前沿的核心诉求：
- **SITS2026**：NPC应具备"上下文连贯的对话能力"→ topic_thread
- **Latitude Voyage**：NPC不应有"失忆症"→ proactive_callbacks
- **Agent Memory研究**：智能体应"积累经验、适应环境"→ emotional anchor
- **叙事连贯性研究**：防止OOC → 话题线程保持一致

## 技术亮点

1. **零LLM调用**：proactive_callbacks 和 topic_thread 都是纯启发式，不增加推理开销
2. **记忆保护**：锚点记忆不被凝结，半衰期48h vs 普通6h
3. **渐进增强**：不影响现有功能，纯粹是"注入提示"层面的增强
4. **可调参数**：ANCHOR_VALENCE_THRESHOLD / ANCHOR_AROUSAL_THRESHOLD / ANCHOR_IMPORTANCE 可微调
