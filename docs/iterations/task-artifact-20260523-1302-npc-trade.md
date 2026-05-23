# Task Artifact: 活纸·每日迭代 2026-05-23 13:02

## 目标
对 living-paper 项目执行一次有质量的自动迭代改进

## 执行过程

1. **拉取代码**: `git pull origin qclaw` → Already up to date (commit f0833a7)
2. **分析近期 commit**: 最近 10 次提交涵盖 NPC 状态感知对话、后台任务日志、经济系统、UI 修复、反思/情绪、记忆检索等方向
3. **选择改进方向**: 🎮 游戏性 — 将经济系统（上轮建好的 25 种物品定价表/6 地图溢价）接入 NPC 对话，使商贩 NPC 能真正进行买卖。

## 改动内容

| 文件 | 变更 |
|------|------|
| `backend/models/player.py` | +1 字段 `npc_inventories: dict[str, dict[str, int]]` |
| `backend/systems/economy.py` | +3 函数：`init_npc_inventories` / `format_npc_inventory` / `apply_npc_trade`；+1 常量 `NPC_INVENTORY_SEEDS`（7 名商贩起始货柜） |
| `backend/services/talk_service.py` | 注入 `format_npc_inventory()` 到 `build_npc_messages()` 动态层；`apply_npc_reply()` 后调用 `apply_npc_trade()` 同步货柜 |
| `backend/api/routes.py` | `/api/hello` 新增 `init_npc_inventories(p)` 调用 |
| `backend/systems/core.py` | 附带：上轮未提交的 `npc_weather_awareness_block()` + 标点规范化 |

## 测试结果
- ✅ `python -m uvicorn backend.app:app` 启动无报错
- ✅ `POST /api/hello` → 200，初始化正常
- ✅ `POST /api/npc/talk` (zhanggui) → 200，NPC 正常回复

## Push 状态
- ✅ Local commit: `28d7004`
- ⚠️ Push 失败：GitHub 网络不通（connect timeout），下次迭代重试

## 关键设计决策
- NPC 货柜存于 `PlayerState.npc_inventories`（每玩家沙箱独立）
- 仅启用 7 名商贩型 NPC（掌柜、牙人、船家、里正、卡吏、知客、驿卒），其他 NPC 无货柜
- 交易由 LLM 自主驱动（通过 `items_gain`/`items_lose`/`coin_delta` 结构化字段），基础设施就位后 LLM 可自然使用
- 货柜上下文注入到动态层（不在 static cached 层），每次对话刷新