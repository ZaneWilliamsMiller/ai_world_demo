# Task Artifact · 2026-05-23 05:45

## Objective
青笺录·每日迭代：对 `ai_world_demo` 项目进行有质量的改进。

## 选择的改进方向
**💬 对话体验 — 上下文感知的记忆检索**

## 问题分析
NPC 记忆检索（`mem.retrieve()`）仅用玩家**当前消息**作为查询词。多轮对话中，当玩家使用指代词（如「那件事后来怎样了」）时，检索无法关联之前谈论的话题，导致记忆命中率低、NPC 显得"健忘"。

## 解决方案
在 `backend/memory.py` 新增 `build_retrieval_query()` 函数：
- 从最近4轮对话历史中抽取 40+ 白名单实体关键词（人名/地名/物品/事件）
- 检测未完结提问中的核心词
- 将话题关键词拼接到当前消息，形成复合查询
- 检索数量从 k=5 提升到 k=8

在 `backend/services/talk_service.py` 中将检索调用从 `mem.retrieve(mind, user_message, k=5)` 替换为 `mem.retrieve(mind, mem.build_retrieval_query(user_message, hist_slice), k=8)`。

## 测试结果
- ✅ Server 启动无报错
- ✅ `/api/hello` 正常
- ✅ `/api/npc/talk` 风闻子对话正常（~20s）
- ✅ `build_retrieval_query` 向后兼容（无历史时回退为原始消息）
- ✅ Prompt Cache 架构未退化

## Commit
`91773ca` — auto: 上下文感知记忆检索——对话历史拼接富查询，k5→8 | Contextual Memory Retrieval (💬 对话体验)