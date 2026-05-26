# 活纸江湖 · 项目结构说明

> 最后更新：2026-05-27 (+双独立前端架构：web-standalone + godot-standalone，项目结构整理)

## 顶层

```
living-paper/
├── backend/              # Python 后端 (FastAPI 游戏引擎)
├── static/               # Web 前端 (后端内嵌版 SPA)
├── web-standalone/       # Web 前端 (独立版，双模式 API)
├── godot/                # Godot 前端 (后端内嵌版)
├── godot-standalone/     # Godot 前端 (独立版，严格类型 + 信号驱动)
├── tools/                # 开发辅助脚本
├── tests/                # 自动化测试
├── docs/                 # 文档与迭代记录
├── saves/                # 角色存档 (运行时生成, gitignore)
├── .env / .env.example   # 环境变量
├── requirements.txt      # Python 依赖
├── README.md             # 项目说明
└── .gitignore            # Git 忽略规则
```

| 路径 | 作用 |
|------|------|
| `README.md` | 项目说明 |
| `requirements.txt` | Python 依赖 |
| `.env` / `.env.example` | 环境变量（LLM API Key / 模型 / 熔断器 / 缓存等配置） |
| `.gitignore` | Git 忽略规则 |
| `backend/` | **Python 后端** — FastAPI 游戏引擎 |
| `static/` | **Web 前端（内嵌版）** — 由后端直接 serve 的 SPA |
| `web-standalone/` | **Web 前端（独立版）** — 双 API 模式，可独立运行 |
| `godot/` | **Godot 前端（内嵌版）** — 原始 Godot 4 客户端 |
| `godot-standalone/` | **Godot 前端（独立版）** — 严格类型 + 信号驱动架构 |
| `tools/` | 开发辅助脚本（测试、启动、调试、地图工具） |
| `tests/` | 自动化测试（E2E / 边界 / 综合 / 单元 + 测试报告） |
| `docs/` | 文档、迭代记录、历史归档 |
| `saves/` | 角色存档（运行时生成，JSON 格式，gitignore） |

---

## backend/ — Python 后端 (FastAPI)

### 入口与配置

| 文件 | 作用 |
|------|------|
| `app.py` | FastAPI 应用入口：挂载静态文件、注册路由、定期自动存档（5min）、shutdown 优雅关闭 |
| `config.py` | 配置读取（`.env` → `Settings`）：LLM/连接池/熔断/缓存/重试/Prompt Cache 开关 |

### LLM 调用层

| 文件 | 作用 |
|------|------|
| `llm_client.py` | LLM 调用封装：chat_completion、连接池复用（httpx AsyncClient 单例）、并发限速（Semaphore）、Prompt Cache 双模式 |
| `circuit_breaker.py` | LLM 熔断器：故障窗口内阈值触发 → 冷却期降级为 graceful fallback |
| `llm_cache.py` | LLM 响应缓存：TTL 过期 + LRU 淘汰，减少重复 API 调用 |

### API 路由

| 文件 | 作用 |
|------|------|
| `api/routes.py` | 所有 HTTP 端点（23 个）：hello/move/talk/talk_stream/state/agent/plan/reflect/save/load/saves/delete-save/finale/bounty 等 |

### NPC 认知（记忆系统）

| 文件 | 作用 |
|------|------|
| `agent_brain.py` | NPC 认知闭环：观察提取 → 反思生成 → 计划生成 → 记忆检索 |
| `memory.py` | NPC 记忆存储：观察/反思/计划/情感状态、A-Mem 顿悟演化 |
| `memory_index.py` | 倒排索引加速记忆检索（500 条 ~0.9ms） |

### 游戏状态

| 文件 | 作用 |
|------|------|
| `game_state.py` | 游戏全局状态管理 |

### 数据定义 `data/`

| 文件 | 作用 |
|------|------|
| `npcs_data.py` | NPC 角色卡：19 个 NPC（含玄真子/铁彀/金满堂等） |
| `maps_data.py` | 统一世界地图：72×48「活纸江湖·万里图」 |
| `factions.py` | 势力数据：衙门/镖局/漕帮/书院/绿林 |
| `prompts.py` | 提示词模板：SOCIETY_BIBLE、MACHINE_TAIL_RULE 等 |
| `atmosphere.py` | 场景氛围文字生成器（时间/天气驱动） |
| `relationships.py` | NPC 间预设关系（师徒、仇敌等） |

### 领域模型 `models/`

| 文件 | 作用 |
|------|------|
| `player.py` | PlayerState：属性/坐标/背包/声望/历史/悬赏榜 |
| `npc.py` | NPC 角色卡格式化函数 |
| `llm_schema.py` | LLM JSON 响应 Schema（NpcResponseSchema 等） |

### 业务编排 `services/`

| 文件 | 作用 |
|------|------|
| `talk_service.py` | 对话服务：Prompt Cache 分层构建 / 消息构建 / 回复应用 / 优雅降级（visible_text + reply 双字段） |
| `agent_service.py` | NPC 智能体：自动反思（夜间保护）/ 计划生成 / 记忆凝结 |

### 会话与持久化 `session/`

| 文件 | 作用 |
|------|------|
| `store.py` | 内存会话管理 + 启动时自动从 saves/ 恢复活跃玩家 |

### 核心系统 `systems/`

| 文件 | 作用 |
|------|------|
| `core.py` | 核心逻辑：NPC 游走/移动触发际遇/体力心气/感知扫描 |
| `pathfinding.py` | 寻路：Dijkstra 安全路径 + 危险地形判定 |
| `time_weather.py` | 时辰天气：12 时辰制推进/日夜判定/天气轮换 |
| `economy.py` | 经济系统：NPC 货柜/补货/玩家背包 |
| `encounter.py` | 际遇系统：危险地形事件 + NPC 拦路 + 动态奇遇叙事 |
| `npc_gossip.py` | NPC 八卦：NPC 间非玩家驱动的信息传播 |
| `reputation.py` | 声望系统：势力好感/事件推送 |
| `save_system.py` | 存档系统：序列化/反序列化/读档/删档 |
| `bounty_board.py` | 悬赏榜系统：缉拿/押送/打探/寻回 4 种任务 |
| `prompt_compress.py` | 长对话压缩：历史 >14 轮时摘要化，省 40-60% token |

---

## static/ — Web 前端（后端内嵌版）

```
static/
├── index.html          ← SPA 入口
├── css/game.css        ← 暗色江湖主题
└── js/
    ├── api.js          ← API 通信层（/api 前缀）
    ├── store.js        ← 状态管理
    ├── map.js          ← 地图渲染（CSS Grid 16px 瓦片）
    ├── ui.js           ← UI 更新
    ├── dialogue.js     ← 对话系统（SSE 流式）
    └── main.js         ← 入口逻辑
```

由 `backend/app.py` 通过 `StaticFiles` 中间件直接 serve，需要后端运行。

---

## web-standalone/ — Web 前端（独立版）

```
web-standalone/
├── index.html          ← SPA 入口（含 API 配置面板）
├── css/game.css        ← 暗色江湖主题
└── js/
    ├── api.js          ← 双模式 API 层（后端模式 / LLM 直连模式）
    ├── store.js        ← 状态管理（API_URL / BASE_URL 可切换）
    ├── map.js          ← 地图渲染
    ├── ui.js           ← UI 更新
    ├── dialogue.js     ← 对话系统
    ├── llm-test.js     ← LLM 连接测试模块
    └── main.js         ← 入口逻辑
```

**与 `static/` 的区别**：
- 可独立打开或通过任意 HTTP 服务器运行
- 双 API 模式：后端模式（BASE_URL → 后端 API）/ 独立模式（API_URL → 直连 LLM API）
- API 配置面板：URL / Key / Model 可在界面修改
- 连接测试功能：验证后端或 LLM API 可用性
- 配置持久化到 localStorage

---

## godot/ — Godot 前端（后端内嵌版）

```
godot/
├── project.godot       ← 项目配置（Autoload: ApiClient + GameManager）
├── README.md           ← 使用说明
├── scenes/
│   └── game.tscn       ← 主场景
└── scripts/
    ├── main_game.gd    ← 程序化构建全部 UI（登录/地图/对话/HUD）
    ├── api_client.gd   ← HTTP 客户端 Autoload
    └── game_manager.gd ← 游戏状态 Autoload
```

需配合后端运行，API 通信通过 `api_client.gd` 的 `@export var base_url` 配置。

---

## godot-standalone/ — Godot 前端（独立版）

```
godot-standalone/
├── project.godot       ← 项目配置（Autoload: ApiClient + GameManager）
├── .gdextension_ignore
├── scenes/
│   ├── game.tscn       ← 游戏主场景
│   └── login.tscn      ← 登录场景（可 F6 独立运行）
└── scripts/
    ├── api_client.gd   ← 双模式 HTTP 客户端（后端 / LLM 直连）
    ├── game_manager.gd ← 游戏状态管理（信号驱动）
    ├── main_game.gd    ← 游戏主场景脚本
    ├── login_screen.gd ← 登录界面脚本
    ├── map_renderer.gd ← 地图渲染组件
    ├── dialogue_ui.gd  ← 对话界面组件
    └── llm_test.gd     ← LLM 连接测试脚本
```

**与 `godot/` 的区别**：
- **GDScript 2.0 严格静态类型**：所有变量、参数、返回值显式类型
- **信号驱动架构**：组件间通过信号通信，不用 `get_parent()`
- **双 API 模式**：后端模式 / LLM 直连模式，可在游戏内切换
- **独立场景**：`login.tscn` 和 `game.tscn` 可 F6 独立运行
- **连接测试**：`llm_test.gd` 验证后端和 LLM API

---

## tools/ — 开发辅助脚本

| 文件 | 作用 |
|------|------|
| `auto_test.py` | 自动化集成测试（8 项：健康检查/静态页面/LLM列表/LLM直连/角色创建/NPC对话/移动/存档） |
| `start.sh` | 开发启动脚本（一键启动后端） |
| `gen_map.py` | 地图生成工具 |
| `check_map.py` | 地图校验工具 |
| `smoke_api.py` | API 烟雾测试 |
| `verify_all.py` | 全量快速验证（Health + Static + Hello + Save + Load + List + Delete） |
| `debug_talk.py` | 对话调试（观察 LLM 原始响应） |
| `check_json.py` | JSON 响应格式检查 |
| `check_url.py` | API URL 连通性检查 |
| `show_maps.py` | 地图数据展示 |

---

## tests/ — 自动化测试

| 文件 | 作用 |
|------|------|
| `conftest.py` | pytest fixtures |
| `_test_endpoints.py` | 端到端 API 测试（原有） |
| `_test_pathfinding.py` | 寻路单元测试（原有） |
| `test_e2e.py` | 全链路 E2E（Hello→Talk→MultiTalk→State→Move→Mind→Reflect，31 项） |
| `test_edge.py` | 边界覆盖测试（23 项） |
| `test_final.py` | 综合回归测试（23 项） |
| `test_fixes.py` | 修复专项测试 |
| `test_backend.py` | 后端基础测试 |
| `test_debug_llm.py` | LLM 调试测试 |
| `test_deep.py` | 深度对话测试 |
| `test_reports/` | 自动化测试报告（JSON，gitignore） |

---

## docs/ — 文档与迭代记录

| 路径 | 作用 |
|------|------|
| `PROJECT_STRUCTURE.md` | 本文件（项目结构总览） |
| `overview.md` | 项目迭代概述 |
| `iterations/` | 迭代产物归档（task-artifact-*.md / 2026-*-*.md） |
| `static_legacy/` | 旧版 Web 前端归档（仅供历史参考） |

---

## 持久化流程

```
玩家开始     → SessionStore.get_or_create(pid)
              → 优先从 saves/<pid>.json 恢复，无则新建

游戏进行     → 每 5 分钟 autosave_all() → saves/<pid>.json
              → 手动 POST /api/save → saves/<pid>.json

游戏结束     → FastAPI shutdown hook → autosave_all() + httpx 连接池释放
```

---

## 前端版本对照

| 特性 | `static/` | `web-standalone/` | `godot/` | `godot-standalone/` |
|------|-----------|-------------------|----------|---------------------|
| 后端依赖 | 必须 | 可选 | 必须 | 可选 |
| LLM 直连 | 不支持 | 支持 | 不支持 | 支持 |
| API 配置面板 | 无 | 有 | 无 | 有 |
| 连接测试 | 无 | 有 | 无 | 有 |
| 严格静态类型 | N/A | N/A | 部分 | 全部 |
| 信号驱动 | N/A | N/A | 部分 | 完整 |
| 独立运行 | 不可以 | 可以 | 不可以 | 可以 |
