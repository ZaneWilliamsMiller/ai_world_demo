# task-artifact: 活纸每日迭代 2026-05-23 07:02

## 目标
日常自动迭代：在 ai_world_demo 项目中选择一个方向进行有质量的改进。

## 方向选择：🐛 Bug修复 — 后台异步任务异常可见性

**选择理由**：
- 近期已覆盖：经济系统（最新）、NPC大脑升级（反思+情绪）、对话体验（记忆检索）、结构整理
- 未被覆盖的方向：后台 3 处 `try/except: pass` 使运行时异常完全不可追踪
- 影响：NPC 反思失败、每日计划失败、动态奇遇失败时没有任何日志线索，生产环境定位极难

## 改动内容

| 文件 | 改动 |
|------|------|
| `backend/services/agent_service.py` | 新增 logging logger；`bg_reflect` 异常补全 `log.warning`；`bg_plan_for_npcs` 异常补全 `log.warning` |
| `backend/api/routes.py` | `_bg_encounter` 异常补全 `logging.getLogger("routes").warning` |
| `docs/iterations/2026-05-23_0702.md` | 新增迭代记录 |
| `docs/PROJECT_STRUCTURE.md` | 更新 agent_service 模块描述 + 时间戳 |

## 验证

- `/api/hello` ✅
- `/api/npc/talk` ✅（server_ms ~12s）
- `python -m uvicorn backend.app:app` 启动无报错
- git push origin qclaw ✅（fa00483..6983d28）

## 设计原则

- 后台任务保持 fire-and-forget 语义，不因异常阻断主流程
- 日志级别 `warning`（非 `error`）——单次 LLM 超时非致命
- 不违反 Prompt Cache 架构（未改动 talk_service.py）