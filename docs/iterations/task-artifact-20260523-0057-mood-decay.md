# 青笺录·每日迭代 — 2026-05-23 00:57

## 本次改进：NPC情绪自然衰减（Mood Decay Integration）

### 问题
`memory.py` 中定义了 `AgentMind.mood_decay_tick()` —— 让 NPC 的情绪（效价/唤醒度）随时间自然向中性回归——但此方法**从未被接入游戏循环**。

后果：NPC 在对话中通过 `_evolve_npc_mood()` 积累的情绪（如一次激怒后 `valence=-8`）会**永久保留**，后续所有对话都带着那张黑脸，丧失了"气消了"的自然感。

### 解决方案
在 `systems/core.py` 的 `update_npc_states_from_habits()` 末尾新增情绪衰减调用：
- 每次时钟推进（玩家移动触发），遍历所有已初始化的 NPC 心智
- 调用 `mind.mood_decay_tick(shichen_name)` 执行衰减
- 深夜（子丑寅戌亥时）唤醒度下降 -0.6，白昼微升 +0.15
- 效价偏离中性时，以 ±0.3 漂移回零

### 测试
- `uvicorn backend.app:app` 启动无报错 ✓
- `/api/hello` 正常返回玩家状态 ✓
- `/api/npc/talk` 正常返回 NPC 对话（风闻子，186字，9362ms）✓
- Prompt Cache 架构（cached_system / uncached）未退化 ✓

### 提交
- `401d2bf` — Prompt Cache架构落地（收束之前未提交的改动）
- `d1c25f3` — NPC情绪自然衰减（本次主要改进）
- push 因网络问题失败（Connection reset），已本地保留

### 方向
🧠 NPC大脑升级 — 情感计算闭环：演化↔衰减形成完整情绪生命周期