# 青笺录·每日迭代 2026-05-23 05:51

## 迭代方向
🧠 NPC 大脑升级 - 计划对照反思 + 情绪驱动反思加速

## 改动内容

### 1. 计划对照反思 (Plan-Aware Reflection)
- `agent_brain.py`: `reflect()` 和 `cross_reflect()` 注入当天计划上下文
- `memory.py`: 新增 `format_plan_for_reflection()` 格式化计划供反思使用
- 效果：NPC 反思时对比「原计划」与「实际发生」，洞察更人性化

### 2. 情绪驱动反思加速 (Emotion-Driven Urgency)
- `memory.py`: `AgentMind._emotion_adjusted_reflect_threshold()` 动态调节阈值 (35 → 最低13)
- `talk_service.py`: `_evolve_npc_mood()` 锚点创建时直接加速 `importance_since_reflect`
- 效果：NPC 情绪巨变后更快自省，反思时机更符合人性

### 3. 架构保障
- 未修改 Prompt Cache 静态/动态分层结构
- `cached_system()` 标记的静态块不受影响

## 文件变更
- `backend/agent_brain.py` — 反思函数注入计划上下文
- `backend/memory.py` — 新增 format_plan_for_reflection + 情绪驱动阈值
- `backend/services/talk_service.py` — 锚点加速反思
- `docs/iterations/2026-05-23_0551.md` — 迭代记录（新增）
- `docs/PROJECT_STRUCTURE.md` — 更新模块描述

## API 测试
- `/api/hello` ✅ — 正常返回
- `/api/npc/talk` ✅ — 对话正常，favor 更新，server_ms ~13s
- App 启动无报错

## Commit
`304aed9` — auto: NPC反思计划对照+情绪驱动加速 | Plan-Aware Reflection & Emotion-Driven Urgency (🧠 NPC大脑升级)