# 活纸·每日迭代任务产物

**时间**: 2026-05-23 11:05 CST
**Commit**: fa977fb
**类别**: 🧠 NPC大脑升级

## 本轮改动

**NPC状态感知注入对话（State-Aware Dialogue Behavior）**

将已实现但未启用的 `npc_state_for_dialogue()` 正式接入 `build_npc_messages()` 动态上下文层，使 NPC 的作息状态（resting/busy/alert/hostile）能直接影响其对话语气、耐心和话语长短。

此前 `update_npc_states_from_habits()` 在每次移动后更新 NPC 状态，且 `npc_state_for_dialogue()` 已写好详细行为指引并在 talk_service.py 头部 import，但从未被调用——形成"状态已计算、对话未感知"的断层。

## 选择此方向的原因

- 近期改进集中在后台任务日志、经济系统、前端 bug——对话体验方向最近一次是四轮前（contextual retrieval）
- 这是一个"投入极小、收益极大"的改进：只需加3行调用代码，但让所有NPC的作息时间真正影响对话
- 不与 Prompt Cache 架构冲突（状态块在动态层）
- 补全了"状态计算→对话注入"的闭环

## 验证

- 服务启动无报错 ✅
- /api/hello ✅  
- /api/npc/talk 正常（预期错误，非崩溃）✅