# 活纸江湖 · 项目结构说明

> 最后更新：2026-05-31

## 顶层

```
living-paper/
├── backend/              # Python 后端 (FastAPI 游戏引擎)
├── static/               # Web 前端 (原生 SPA，同端口部署)
├── godot/                # Godot 前端 (GDScript 2.0 严格类型 + 信号驱动)
├── third-party/          # 第三方依赖声明与许可证
├── tools/                # 开发辅助脚本
├── tests/                # 自动化测试
├── docs/                 # 文档与迭代记录
├── saves/                # 角色存档 (运行时生成, gitignore)
├── .env / .env.example   # 环境变量
├── start.py              # 一键启动脚本
├── requirements.txt      # Python 依赖
├── pyproject.toml        # Python 项目配置
├── README.md             # 项目说明
└── .gitignore            # Git 忽略规则
```

---

## backend/ — Python 后端 (FastAPI)

### 入口与配置

| 文件 | 作用 |
|------|------|
| `app.py` | FastAPI 应用入口：挂载静态文件、注册路由、定期自动存档、shutdown 优雅关闭 |
| `config.py` | 配置读取（`.env` → `Settings`）：LLM/连接池/熔断/缓存/重试/Prompt Cache 开关 |

### API 路由

| 文件 | 作用 |
|------|------|
| `api/routes.py` | 核心 HTTP 端点：hello/move/talk/talk_stream/state/agent/plan/reflect/save/load 等 |
| `api/schema.py` | API 响应模型定义：42 个 Pydantic Response 模型 + 12 个组件模型 |
| `api/npc_routes.py` | NPC 相关端点 |
| `api/player_routes.py` | 玩家相关端点 |
| `api/save_routes.py` | 存档相关端点 |
| `api/views.py` | 视图/页面端点 |
| `api/dev.py` | 开发/测试端点：测试中心 API、交互测试 SSE 流式端点、熔断器重置 |
| `api/admin_routes.py` | 管理/监控 API 路由 |

### NPC 认知（智能体）

| 文件 | 作用 |
|------|------|
| `agents/brain.py` | NPC 认知闭环：观察提取 → 反思生成 → 计划生成 → 记忆检索 |
| `agents/actor.py` | NPC 行动执行器 |
| `agents/game_state.py` | 游戏全局状态管理 |

### 记忆系统

| 文件 | 作用 |
|------|------|
| `memory/entities.py` | 实体关键词提取与代词消解 |
| `memory/format.py` | 记忆格式化 |
| `memory/index.py` | 倒排索引加速记忆检索 |
| `memory/retrieval.py` | 记忆检索逻辑 |

### LLM 调用层

| 文件 | 作用 |
|------|------|
| `llm/client.py` | LLM 调用封装：chat_completion、连接池复用、并发限速、Prompt Cache 双模式 |
| `llm/circuit_breaker.py` | LLM 熔断器：故障窗口内阈值触发 → 冷却期降级为 graceful fallback |
| `llm/cache.py` | LLM 响应缓存：TTL 过期 + LRU 淘汰 |
| `llm/params.py` | LLM 参数配置 |
| `llm/prompt_compress.py` | 长对话压缩：历史过长时摘要化 |

### 可观测性 `observability/`

| 文件 | 作用 |
|------|------|
| `observability/tracker.py` | LLM 调用追踪器 |

### 数据定义 `data/`

| 文件 | 作用 |
|------|------|
| `npcs_data.py` | NPC 角色卡数据 |
| `maps_data.py` | 统一世界地图数据 |
| `factions.py` | 势力数据 |
| `prompts.py` | 提示词模板 |
| `atmosphere.py` | 场景氛围文字生成器（时间/天气驱动） |
| `relationships.py` | NPC 间预设关系 |
| `zones.py` | 地图区域定义 |

### 领域模型 `models/`

| 文件 | 作用 |
|------|------|
| `player.py` | PlayerState：属性/坐标/背包/声望/历史/悬赏榜 |
| `npc.py` | NPC 角色卡格式化函数 |
| `llm_schema.py` | LLM JSON 响应 Schema |

### 业务编排 `services/`

| 文件 | 作用 |
|------|------|
| `talk_service.py` | 对话服务：Prompt Cache 分层构建 / 消息构建 / 回复应用 / 优雅降级 |
| `agent_service.py` | NPC 智能体：自动反思 / 计划生成 / 记忆凝结 |

### 会话与持久化 `session/`

| 文件 | 作用 |
|------|------|
| `store.py` | 内存会话管理 + 启动时自动从 saves/ 恢复活跃玩家 |

### 核心系统 `systems/`

| 文件 | 作用 |
|------|------|
| `core.py` | 核心逻辑：NPC 游走/移动触发际遇/体力心气/感知扫描 |
| `constants.py` | 游戏常量定义 |
| `pathfinding.py` | 寻路：Dijkstra 安全路径 + 危险地形判定 |
| `time_weather.py` | 时辰天气：12 时辰制推进/日夜判定/天气轮换 |
| `economy.py` | 经济系统：NPC 货柜/补货/玩家背包 |
| `encounter.py` | 际遇系统：危险地形事件 + NPC 拦路 + 动态奇遇叙事 |
| `npc_gossip.py` | NPC 八卦：NPC 间非玩家驱动的信息传播 |
| `npc_state.py` | NPC 状态管理：作息/游走/情绪 |
| `perception.py` | 感知系统 |
| `reputation.py` | 声望系统：势力好感/事件推送 |
| `save_system.py` | 存档系统：序列化/反序列化/读档/删档 |
| `bounty_board.py` | 悬赏榜系统 |
| `trap.py` | 陷阱系统 |
| `task_fsm.py` | 任务 FSM 状态机 |
| `consistency.py` | 一致性检查 |

---

## static/ — Web 前端

```
static/
├── index.html          ← SPA 入口
├── tests.html          ← 测试中心页面
├── css/
│   ├── base.css        ← 基础样式
│   ├── game.css        ← 暗色江湖主题
│   └── tests.css       ← 测试中心样式
└── js/
    ├── api.js          ← API 层
    ├── store.js        ← 状态管理（同源自动检测，API_URL 可配置）
    ├── map.js          ← 地图渲染（CSS Grid 16px 瓦片）
    ├── ui.js           ← UI 更新
    ├── dialogue.js     ← 对话系统（SSE 流式）
    ├── main.js         ← 入口逻辑
    ├── html-utils.js   ← HTML 工具函数
    ├── api-types.d.ts   ← 自动生成的 TypeScript 类型定义
    └── tests.js        ← 测试中心逻辑
```

**部署方式**：由 FastAPI 挂载 StaticFiles，前后端同端口部署。

---

## godot/ — Godot 前端 (Godot 4)

```
godot/
├── project.godot       ← 项目配置
├── .gdextension_ignore
├── api-schema/         ← JSON Schema 文件供 Godot 参考
├── scenes/
│   └── game.tscn       ← 游戏主场景
└── scripts/
    ├── api_client.gd       ← HTTP 客户端
    ├── config_panel.gd     ← 配置面板
    ├── dialog_manager.gd   ← 对话管理
    ├── game_colors.gd      ← 颜色定义
    ├── game_manager.gd     ← 游戏状态管理（信号驱动）
    ├── llm_test.gd         ← LLM 连接测试
    ├── main_game.gd        ← 游戏主场景脚本
    ├── map_renderer.gd     ← 地图渲染组件
    ├── message_display.gd  ← 消息显示
    ├── shutdown_service.gd ← 关闭服务
    ├── test_center.gd      ← 测试中心
    └── ui_builder.gd       ← UI 构建
```

---

## third-party/ — 第三方依赖

| 文件 | 作用 |
|------|------|
| `THIRD_PARTY.md` | 第三方依赖清单及许可证声明 |

---

## tools/ — 开发辅助脚本

| 文件 | 作用 |
|------|------|
| `check_arch.py` | 架构检查（ESLint 规则验证） |
| `check_map.py` | 地图校验工具 |
| `diagnose_500.py` | 500 错误诊断 |
| `diagnose_talk.py` | 对话调试（观察 LLM 原始响应） |
| `gen_map.py` | 地图生成工具 |
| `show_maps.py` | 地图数据展示 |
| `smoke_api.py` | API 烟雾测试 |
| `verify_all.py` | 全量快速验证 |
| `gen_ts_schema.py` | 从 Pydantic 模型生成 TypeScript 类型定义 |
| `gen_json_schema.py` | 从 Pydantic 模型生成 JSON Schema 文件 |

---

## tests/ — 自动化测试

### 功能测试 `unit/`

| 模块 | 测试文件 |
|------|----------|
| agents | `test_brain.py`, `test_game_state.py` |
| api | `test_api_routes.py`, `test_views.py`, `test_schema_contract.py` |
| data | `test_data_integrity.py` |
| llm | `test_circuit_breaker.py`, `test_llm_cache.py`, `test_llm_client.py`, `test_llm_params.py` |
| memory | `test_entities.py`, `test_format.py`, `test_index.py`, `test_retrieval.py` |
| models | `test_models.py`, `test_player.py` |
| observability | `test_tracker.py` |
| services | `test_agent_service.py`, `test_talk_service.py` |
| session | `test_session_store.py` |
| systems | `test_core.py`, `test_economy.py`, `test_economy_extended.py`, `test_npc_state.py`, `test_path.py`, `test_perception.py`, `test_save.py`, `test_systems_extended.py`, `test_time_weather.py`, `test_talk.py`, `test_trap.py`, `test_world.py` |
| config | `test_config.py` |

### 集成测试 `integration/`

| 文件 | 作用 |
|------|------|
| `test_api.py` | API 集成测试 |

### 交互测试 `interactive/`

| 文件 | 作用 |
|------|------|
| `conftest.py` | 交互测试客户端（httpx 直连 + 对话日志 + 回调机制） |
| `test_dialogue_coherence.py` | 对话连贯性测试 |
| `test_emotional_response.py` | 情感响应测试 |
| `test_npc_personality.py` | NPC 个性一致性测试 |
| `test_world_knowledge.py` | 世界观知识测试 |

---

## docs/ — 文档与迭代记录

| 路径 | 作用 |
|------|------|
| `PROJECT_STRUCTURE.md` | 本文件（项目结构总览） |
| `overview.md` | 项目迭代概述 |
| `iterations/` | 迭代产物归档 |

---

## 持久化流程

```
玩家开始     → SessionStore.get_or_create(pid)
              → 优先从 saves/<pid>.json 恢复，无则新建

游戏进行     → 每 5 分钟 autosave_all() → saves/<pid>.json
              → 手动 POST /api/save → saves/<pid>.json

游戏结束     → FastAPI shutdown hook → autosave_all() + httpx 连接池释放
```
