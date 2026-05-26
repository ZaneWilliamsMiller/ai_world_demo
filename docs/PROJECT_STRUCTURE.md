# 青石江湖 · 项目结构说明

> 最后更新：2026-05-26 22:29 (+后端架构优化：LLM缓存/熔断/记忆索引/悬赏榜/Prompt压缩/新NPC)

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

### LLM 调用优化（新增）

| 文件 | 作用 |
|------|------|
| `circuit_breaker.py` | **新增**：LLM 调用熔断器，失败时自动降级为 graceful fallback |
| `llm_cache.py` | **新增**：system prompt 静态缓存 + 语义查询去重缓存 |

### API 路由

| 文件 | 作用 |
|------|------|
| `api/routes.py` | 所有 HTTP 端点（**23 个**，含基础 18 个 + 悬赏榜 5 个）|

### NPC 认知（记忆系统）

| 文件 | 作用 |
|------|------|
| `agent_brain.py` | NPC 认知闭环核心：观察提取 → 反思生成 → 计划生成 → 记忆检索 |
| `memory.py` | NPC 记忆存储（观察、反思、计划、情感状态、A-Mem 顿悟演化） |
| `memory_index.py` | **新增**：倒排索引加速记忆检索，500 条记忆 0.9ms（优化前 ~50ms） |

### 游戏状态

| 文件 | 作用 |
|------|------|
| `game_state.py` | 游戏全局状态管理 |

### 数据定义 `data/`

| 文件 | 作用 |
|------|------|
| `npcs_data.py` | NPC 角色卡：19 个 NPC（新增 3 个：玄真子/铁彀/金满堂）|
| `maps_data.py` | 统一世界地图：单一 72×48「大地图」（青石江湖·万里图）|
| `factions.py` | 势力数据：衙门/镖局/漕帮/书院/**绿林（新增）** |
| `prompts.py` | 提示词模板：SOCIETY_BIBLE、MACHINE_TAIL_RULE 等 |
| `atmosphere.py` | 场景氛围文字生成器（时间/天气驱动） |
| `relationships.py` | NPC 间预设关系（师徒、仇敌等） |

### 领域模型 `models/`

| 文件 | 作用 |
|------|------|
| `player.py` | PlayerState：属性/坐标/背包/声望/历史/**悬赏榜**（新增） |
| `npc.py` | NPC 角色卡格式化函数 |
| `llm_schema.py` | LLM JSON 响应 Schema（NpcResponseSchema 等） |

### 业务编排 `services/`

| 文件 | 作用 |
|------|------|
| `talk_service.py` | 对话服务：Prompt Cache 分层构建 / 消息构建 / 回复应用 / 优雅降级 |
| `agent_service.py` | NPC 智能体：自动反思（夜间保护）/ 计划生成 / 记忆凝结 |

### 会话管理 `session/`

| 文件 | 作用 |
|------|------|
| `session/store.py` | 内存会话管理（room 字典） |

### 核心系统 `systems/`

| 文件 | 作用 |
|------|------|
| `pathfinding.py` | 寻路：Dijkstra 安全路径 + 危险地形判定 |
| `time_weather.py` | 时辰天气：12 时辰制推进/日夜判定/天气轮换 |
| `core.py` | 核心逻辑：NPC 游走/移动触发际遇/体力心气/感知扫描 |
| `economy.py` | 经济系统：NPC 货柜/补货/玩家背包 |
| `encounter.py` | 际遇系统：危险地形事件 + NPC 拦路 + 动态奇遇叙事 |
| `npc_gossip.py` | NPC 八卦：NPC 间非玩家驱动的信息传播 |
| `reputation.py` | 声望系统：势力好感/事件推送 |
| `save_system.py` | 存档系统：序列化/反序列化/读档/删档 |
| `bounty_board.py` | **新增**：悬赏榜系统 — 缉拿/押送/打探/寻回 4 种任务 |
| `prompt_compress.py` | **新增**：长对话压缩 — 历史 >14 轮时摘要化，省 40-60% token |

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
| `PROJECT_STRUCTURE.md` | 本文件（项目结构总览）|
| `iterations/` | 迭代产物归档（task-artifact-*.md） |
