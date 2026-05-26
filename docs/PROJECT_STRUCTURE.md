# 青石江湖 · 项目结构说明

> 最后更新：2026-05-26 12:38 (+感知扫描系统)

## 顶层

| 路径 | 作用 |
|------|------|
| `README.md` | 项目说明 |
| `requirements.txt` | Python 依赖 |
| `.env` / `.env.example` | 环境变量（LLM API Key 等） |
| `.gitignore` | Git 忽略规则 |
| `tools/` | 辅助工具脚本 |
| `tests/` | 自动化测试 |
| `docs/` | 文档与迭代记录 |
| `saves/` | 角色存档（运行时生成） |
| `static/` | 前端静态文件 |
| `backend/` | Python 后端 |
| `resume/` | 简历与项目经验 |

---

## backend/ — Python 后端

### 入口与配置

| 文件 | 作用 |
|------|------|
| `app.py` | FastAPI 应用入口，挂载静态文件、注册路由 |
| `config.py` | 配置读取（`.env` → `Settings`） |
| `llm_client.py` | LLM 调用封装：chat_completion、缓存、重试 |

### API 路由

| 文件 | 作用 |
|------|------|
| `api/routes.py` | 所有 HTTP 端点（15 个，详见 README） |

### NPC 认知

| 文件 | 作用 |
|------|------|
| `agent_brain.py` | NPC 认知闭环核心：观察提取 → 反思生成 → 计划生成 → 记忆检索 |
| `memory.py` | NPC 记忆存储（观察、反思、计划） |

### 游戏状态

| 文件 | 作用 |
|------|------|
| `game_state.py` | 游戏全局状态管理 |

### 数据定义 `data/`

| 文件 | 作用 |
|------|------|
| `npcs_data.py` | NPC 角色卡：姓名/性格/背景/初始坐标/NPC_SEEDS/NPC_FACTION/STORY_ORDER |
| `maps_data.py` | 统一世界地图：单一 72×48「大地图」（青石江湖·万里图），含地形字符含义 |
| `factions.py` | 势力数据：衙门/镖局/漕帮/书院/绿林 |
| `prompts.py` | 提示词模板：SOCIETY_BIBLE、MACHINE_TAIL_RULE、AUTONOMY_RULE 等 |
| `atmosphere.py` | 场景氛围文字生成器（时间/天气驱动） |
| `relationships.py` | NPC 间预设关系（师徒、仇敌等） |

### 领域模型 `models/`

| 文件 | 作用 |
|------|------|
| `player.py` | PlayerState 数据类：属性/坐标/背包/声望/历史/NPC货柜/货柜补货追踪 |
| `npc.py` | NPC 角色卡格式化函数 |
| `llm_schema.py` | LLM JSON 响应 Schema（NpcResponseSchema 等） |

### 业务编排 `services/`

| 文件 | 作用 |
|------|------|
| `talk_service.py` | 对话服务：Prompt Cache 静态/动态分层构建、消息构建、回复应用 |
| `agent_service.py` | NPC 智能体：自动反思（含夜间保护）/ 计划生成 / 记忆凝结 |

### 会话管理 `session/`

| 文件 | 作用 |
|------|------|
| `session/store.py` | 内存会话管理（room 字典） |

### 核心系统 `systems/`

| 文件 | 作用 |
|------|------|
| `pathfinding.py` | 寻路：Dijkstra 安全路径 + Bresenham 直线 + 危险地形通行/受伤判定 |
| `time_weather.py` | 时辰天气：12 时辰制推进/日夜判定/天气轮换/氛围文字 |
| `core.py` | 核心逻辑：NPC 初始化/游走/移动触发际遇/精力精神/属性判定/感知扫描（危险直觉预警） |
| `economy.py` | 经济系统：NPC 货柜/补货/玩家背包 |
| `encounter.py` | 际遇系统：危险地形触发随机事件 + NPC 拦路遭遇 |
| `npc_gossip.py` | NPC 八卦：NPC 间非玩家驱动的信息传播 |
| `reputation.py` | 声望系统：势力好感/事件推送 |
| `save_system.py` | 存档系统：序列化/反序列化/读档/删档/复活点重生（respawn_at_supply_point） |

---

## static/ — 前端静态文件

| 文件 | 作用 |
|------|------|
| `index.html` | 页面入口 |
| `main.js` | 前端初始化与主流程 |
| `map.js` | Canvas 地图渲染与交互 |
| `scene.js` | 场景/氛围文字渲染 |
| `store.js` | 前端状态管理 |
| `api.js` | 后端 API 调用封装 |
| `game.css` | 全局样式 |
| `ui/dialogue.js` | 对话面板 |
| `ui/journal.js` | 江湖史册面板 |
| `ui/sidebar.js` | 侧栏控制 |
| `ui/utils.js` | UI 工具函数 |
| `assets/` | SVG 装饰资源 |

---

## tools/ — 辅助工具

| 文件 | 作用 |
|------|------|
| `gen_map.py` | 地图生成工具 |
| `check_map.py` | 地图校验工具 |
| `smoke_api.py` | API 烟雾测试 |

---

## tests/ — 自动化测试

| 文件 | 作用 |
|------|------|
| `conftest.py` | pytest fixtures |
| `_test_endpoints.py` | 端到端 API 测试 |
| `_test_pathfinding.py` | 寻路单元测试 |

---

## docs/ — 文档与迭代记录

| 路径 | 作用 |
|------|------|
| `PROJECT_STRUCTURE.md` | 本文件 |
| `iterations/` | 每日 CI 迭代产物归档（格式：YYYY-MM-DD_HHMM.md 或 task-artifact-*.md） |