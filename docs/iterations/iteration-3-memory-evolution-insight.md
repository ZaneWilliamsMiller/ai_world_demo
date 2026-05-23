# 迭代3：记忆演化顿悟系统（A-Mem NeurIPS 2025）

> 时间：2026-05-14 00:00 GMT+8
> 分支：qclaw
> 融入技术：A-Mem（NeurIPS 2025, arxiv 2502.12110）— Zettelkasten 式动态记忆演化

## 技术背景

A-Mem（Agentic Memory for LLM Agents）是 NeurIPS 2025 论文提出的记忆架构，借鉴卡片盒笔记法（Zettelkasten），核心思想：

1. **笔记构建**：每条记忆带关键词/标签/上下文/嵌入
2. **链接生成**：LLM 驱动语义关联，超越纯向量相似度
3. **记忆进化**：新记忆链接旧记忆时，更新旧记忆上下文/标签，产生「顿悟」

多跳推理 F1 达基线 2 倍+，token 使用减 85-93%。

## 落地方案

### 核心机制：纯启发式记忆演化（零 LLM 调用）

当 NPC 观察到新事物时，系统自动检测新观察与旧记忆之间的语义关联（基于 jieba 分词的 Jaccard 相似度），如果关联超过阈值且满足冷却期，则生成一条「顿悟」记忆。

**关键设计决策**：
- 不用 LLM 生成顿悟文本（零额外开销），采用模板+关键词匹配
- 冷却期 30 分钟（`INSIGHT_COOLDOWN_S = 1800.0`），防顿悟过频
- 每次添加观察最多触发 1 条顿悟
- 已链接的旧记忆不重复链接（`linked_memory_ids` 去重）
- 顿悟记忆重要性 = 源记忆重要性 + 1.5 加成
- 顿悟记忆检索时有 0.05 的类型加成（与反思/种子同级别）

### 模板系统

顿悟文本根据旧记忆关键词模式匹配选择模板：
- **怀疑/传闻** → 确信型顿悟（"原来如此"）
- **约定/承诺** → 回扣型顿悟（"此刻心头一动"）
- **物品/买卖** → 交易型顿悟（"才悟出其中门道"）
- **人物指代** → 人物型顿悟（"看清了那人的真意"）
- **其他/高重要** → 泛化顿悟（"悟出了些先前没想通的关窍"）
- **其他/低重要** → 轻度顿悟（"与新近所见似有暗合"）

### 对话注入

顿悟记忆通过 `format_insight_block()` 注入 NPC 对话 system prompt，语气为「隐约感悟」而非「全知宣言」：
- 只取最近 2 条顿悟
- 提示 NPC "点到为止，不必长篇大论——像想起一桩忽然通了的旧事"

## 代码改动

### backend/memory.py（主要改动）

1. **新增常量**：
   - `INSIGHT_LINK_THRESHOLD = 0.25`（两条记忆文本相关度阈值）
   - `INSIGHT_IMPORTANCE_BOOST = 1.5`（顿悟记忆重要性加成）
   - `INSIGHT_MAX_PER_ADD = 1`（每次观察最多触发1条顿悟）
   - `INSIGHT_COOLDOWN_S = 1800.0`（顿悟冷却期30分钟）

2. **新增字段**（AgentMind）：
   - `last_insight_at: float = 0.0`（最近一次顿悟时间戳）
   - `linked_memory_ids: set = field(default_factory=set)`（已链接记忆ID集合，防重复）

3. **新增函数**：
   - `_generate_insight_text(old_text, new_text, old_importance)` — 启发式顿悟文本生成
   - `format_insight_block(mind)` — 顿悟注入对话 system prompt
   - `AgentMind.insights()` — 返回所有顿悟记忆
   - `AgentMind._try_evolve_on_new_observation(new_obs)` — 核心演化逻辑

4. **修改函数**：
   - `AgentMind.add()` — 新增 `_skip_evolve` 参数，添加观察后触发演化
   - `AgentMind.serialize()` — 新增 `last_insight_at`、`linked_memory_ids`（set→list）
   - `Memory.kind` 注释 — 新增 `insight` 类型
   - `KIND_LABELS` — 新增 `"insight": "顿悟"`
   - 检索加成 — insight 类型获得 0.05 bonus
   - `condense_old_observations` — 凝结时传 `_skip_evolve=True`

### backend/services/talk_service.py（次要改动）

1. **新增导入**：`format_insight_block`
2. **build_npc_messages 注入**：在奇遇感知之后新增顿悟注入

## 注入顺序

build_npc_messages 现在的完整注入顺序：
1. 社会总览（SOCIETY_BIBLE）
2. 角色卡（format_npc_character_sheet）
3. 关系网
4. 氛围（scene_context）
5. 记忆流（format_memories_for_prompt）
6. 遭遇感知（format_encounter_perception_block）
7. 计划（format_plan_for_prompt）
8. 心绪（format_mood_for_prompt）
9. 主动回扣（format_proactive_callbacks）
10. 话题线程（format_topic_thread）
11. **顿悟注入（format_insight_block）**← 新增
12. 世界状态 + 体力状态
13. 陷阱锁定提示

## 性能影响

- **零 LLM 额外调用**：顿悟生成纯启发式
- **Jaccard 计算**：O(n) 遍历旧观察，n 通常 < 100（受凝结机制控制）
- **顿悟频率**：冷却 30 分钟 + 已链接去重 → 每个NPC每小时最多2条顿悟
- **对话 token 开销**：最多 2 条顿悟 × ~120 字 = ~240 字 ≈ 150 token

## 测试场景示例

NPC「铁掌帮·陈堂主」观察到：
- 旧记忆：「听说飞虎寨的人在暗中收购铁矿」（importance=7）
- 新观察：「码头卸了一批铁矿，发货人标注是青城商号」

顿悟触发：
- Jaccard 重叠：{铁矿} → score ≈ 0.33 × (7/10) = 0.23 → 接近阈值
- 顿悟文本：「想起之前听说飞虎寨的人在暗中收购铁矿——原来如此，这才明白其中缘由。」

NPC 在后续对话中可能自然流露出："铁矿的事……我倒是想通了几分。"
