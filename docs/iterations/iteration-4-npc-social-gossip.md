# 迭代4：NPC 社交闲聊系统（Multi-Agent Social Gossip）

> 时间：2026-05-14 04:00 GMT+8
> 分支：qclaw
> 融入技术：Multi-Agent Social Simulation（多智能体社会模拟涌现行为 2026）

## 技术背景

2026 年 Multi-Agent Social Simulation 成为 AI 前沿热点：
- **AgentScope 分布式架构**（CSDN 2026-05-10）：数百 Agent 实例在多台服务器间协同，涌现式社会行为
- **Multi-Agent 社会模拟**（CSDN 2026-05-06）：从市场博弈到组织演化的涌现行为实验场，强化学习+博弈论
- **百度文心多 Agent 群聊**（2026-01）：AI 能理解群聊上下文、识别成员意图，根据讨论氛围判断介入时机

核心洞察：**社会模拟的涌现不是单个 Agent 的智能，而是 Agent 之间的交互产生的集体行为**。

## 落地方案

### 核心机制：NPC 间自主社交闲聊（零 LLM 调用）

当两个有关系的 NPC 在同一地图格子时，小概率产生「闲聊」——生成对话摘要写入双方记忆流。

**关键设计决策**：
- 不用 LLM 生成闲聊文本（零额外开销），纯启发式拼接
- 每次移动最多触发 1 次闲聊（控制频率）
- 冷却期 20 分钟（`GOSSIP_COOLDOWN_S = 1200.0`）
- 关系态度影响触发概率（挚交 2.5x → 势同水火 0.1x）
- 闲聊内容来自双方最近观察记忆 + 关系备注

### 关系态度 → 触发概率倍率

| 态度 | 倍率 | 说明 |
|------|------|------|
| 挚交 | 2.5x | 最亲密，闲聊频繁 |
| 暧昧线人 | 2.2x | 秘密交换 |
| 交好 | 2.0x | 友好 |
| 旧交 | 1.8x | 老友重逢 |
| 老主顾 | 1.3x | 生意关系 |
| 生意往来 | 1.2x | 利益交换 |
| 面上客气 | 0.8x | 表面功夫 |
| 心存芥蒂 | 0.5x | 勉强搭话 |
| 互不招惹 | 0.3x | 尽量回避 |
| 势同水火 | 0.1x | 极少搭理 |

### 闲聊记忆示例

NPC「掌柜」与 NPC「牙人」在同福栈闲聊：
- 写入掌柜记忆：`与牙人（生意往来）闲聊，牙人提到：听说东边来了批铜器，价格倒是便宜……（心中暗想：给牙人抽过水，嫌他算盘太精但不敢得罪）`
- 写入牙人记忆：`与掌柜（生意往来）闲聊，掌柜提到：近日来住店的镖局多了几拨……`

### 对话注入

通过 `format_gossip_awareness_block()` 注入 NPC 对话 system prompt：
- 只取最近 1 条闲聊记忆（2 小时内）
- 语气提示：「点到为止」
- NPC 可能自然说出「刚跟 XXX 聊过……」「XXX 那边听说……」

## 代码改动

### backend/systems/npc_gossip.py（新建）

1. **常量**：
   - `GOSSIP_PROB_BASE = 0.08`（基础闲聊概率）
   - `GOSSIP_COOLDOWN_S = 1200.0`（20 分钟冷却）
   - `GOSSIP_MAX_OBS_SNIPPET = 60`（观察截取字数）
   - `GOSSIP_IMPORTANCE = 5.0`（闲聊记忆重要性）
   - `ATTITUDE_MULT`（9 种态度的触发倍率映射）

2. **函数**：
   - `_gossip_key(a, b)` — 两个 NPC 间的唯一闲聊键（排序保证对称）
   - `_get_attitude(npc_id, target_id)` — 查态度和倍率
   - `_get_relation_note(npc_id, target_id)` — 查关系备注
   - `_pick_recent_snippet(mind, about)` — 从记忆流选观察摘要
   - `_generate_gossip_text(a, b, mind_a, mind_b)` — 纯启发式生成闲聊文本
   - `maybe_npc_gossip(p, ticks)` — 主入口：遍历同格子 NPC 对，判定并触发闲聊
   - `format_gossip_awareness_block(mind, npc_id)` — 闲聊感知注入对话

### backend/api/routes.py（修改）

- `/api/move` 后新增 `maybe_npc_gossip(p, ticks=ticks)` 调用（在 `update_npc_states_from_habits` 之后）

### backend/services/talk_service.py（修改）

- 新增 `format_gossip_awareness_block` 导入
- `build_npc_messages` 新增闲聊感知注入（顿悟注入之后、世界状态之前）

## 注入顺序

build_npc_messages 完整注入顺序：
1. 社会总览（SOCIETY_BIBLE）
2. 角色卡 + 人设 + 规则尾
3. 关系网
4. 氛围
5. 记忆流
6. 计划
7. 心绪
8. 主动回扣
9. 话题线程
10. 遭遇感知
11. 顿悟注入
12. **闲聊感知（format_gossip_awareness_block）**← 新增
13. 世界状态 + 体力状态
14. 险局/自由状态
15. 风闻/规则

## 性能影响

- **零 LLM 额外调用**：闲聊生成纯启发式
- **每次移动**：O(n²) 检查同格子 NPC 对，n 通常 < 10
- **闲聊频率**：基础 8% × 态度倍率 × tick 数 → 挚交 NPC 每次移动约 20% 概率
- **对话 token 开销**：最多 1 条闲聊 × ~120 字 ≈ 75 token

## 涌现行为前景

这个系统为后续涌现行为奠定基础：
1. **信息传播链**：A 告诉 B，B 告诉 C → 玩家可能从 C 口中得知 A 的秘密
2. **派系信息流**：同势力 NPC 闲聊概率高，形成内圈信息网络
3. **敌对情报泄漏**：势同水火的 NPC 也可能闲聊（极低概率），产生意外信息流
4. **记忆演化联动**：闲聊写入的观察记忆可能触发顿悟系统 → NPC 对旧事产生新理解
