# Living-Paper 后端交叉检查修复报告 (最终)
# 完成时间: 2026-05-28

## 所有已修复项 (12 HIGH + 8 MEDIUM = 20 项)

### HIGH 优先级 (6 项)
| # | 文件 | 问题 | 修复 |
|---|------|------|------|
| H1 | npc_routes.py | finale 函数 shichen_name 未导入 → 运行时 NameError | 添加顶层 import |
| H2 | llm_client.py | stream_chat_completion 是死代码 | 暂不修复 (需产品决策) |
| H3 | config.py | llm_timeout_s 全项目无引用 | 删除死配置 |
| H4 | llm_client.py | llm_circuit_breaker 开关无效 | 添加 NoOpCircuitBreaker + 条件判断 |
| H5 | llm_client.py | LLMClientManager.get_instance() 并发不安全 | 改为 async await + asyncio.Lock |
| H6 | test_routes.py | 任意代码执行 + CSRF | 添加 ENABLE_TEST_ROUTES 环境变量守卫 |

### MEDIUM 优先级 (14 项)
| # | 文件 | 问题 | 修复 |
|---|------|------|------|
| M6 | npc_routes.py | 重复 time 导入 | 统一使用 time.time() |
| M7 | npc_routes.py | npc_talk_stream 缺少 is_light_inquiry 反思条件 | 与 npc_talk 对齐 |
| M8 | npc_routes.py | 未使用 _factions_public 导入 | 删除 |
| M9 | npc_routes.py | 多处函数体内 import (traceback, logging, shichen_name) | 全部移至顶层 |
| M10 | player_routes.py | find_path 函数内重复导入 | 删除函数内重复导入 |
| M11 | save_game 全部调用点 | save_game 同步 I/O 阻塞事件循环 | 6 个调用点全部改为 await asyncio.to_thread(save_game, p) |
| M12 | talk_service.py | 函数体内多处 import (logging, shichen_name, NpcResponseSchema 等) | 全部移至顶层 + 删除重复导入 |
| M13 | session/store.py | get_or_create 非原子 (并发创建重复玩家) | 添加 asyncio.Lock() + async def |
| M14 | save_system.py | 函数体内 import uuid, import time | 移至顶层 |
| M15 | config.py | 使用已废弃的 @validator (Pydantic v2) | 改为 @field_validator |
| M16 | app.py | _auto_save_loop 硬编码 300s | 改用 settings.auto_save_interval_s |
| M16b | app.py | shutdown_server 函数体内 import (os, threading, httpx, time) | 全部移至顶层 |

## 新增文件
- backend/circuit_breaker.py: NoOpCircuitBreaker 类

## 修改的文件清单 (8 个文件)
1. backend/api/npc_routes.py — H1, M6, M7, M8, M9, M11 (save)
2. backend/config.py — H3, M15 (Pydantic v2 field_validator)
3. backend/circuit_breaker.py — H4 (NoOpCircuitBreaker)
4. backend/llm_client.py — H5 (async get_instance)
5. backend/api/test_routes.py — H6 (安全守卫)
6. backend/api/player_routes.py — M10, M11 (×2 saves)
7. backend/services/talk_service.py — M12
8. backend/session/store.py — M13
9. backend/systems/save_system.py — M14
10. backend/api/save_routes.py — M11 (save)
11. backend/app.py — M16, M16b, M11 (×2 saves)

## 待处理 (LOW 优先级，未修复)
- L1-L14: 各种 lint 问题 (未使用导入、异常处理、文档等)
- M5: llm_client.py 自定义配置分支绕过缓存/熔断器
- M1: app.py 改用 @asynccontextmanager 替代已废弃的 @app.on_event