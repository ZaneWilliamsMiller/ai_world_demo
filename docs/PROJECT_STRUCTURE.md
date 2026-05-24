# AI 文字世界 · 项目结构说明

> 最后更新：2026-05-24 12:02

## 顶层

| 路径 | 作用 |
|------|------|
| `README.md` | 项目说明 |
| `requirements.txt` | Python 依赖 |
| `.env` / `.env.example` | 环境变量（LLM API Key 等） |
| `_test_endpoints.py` | API 测试脚本 |
| `gen_map.py` | 地图生成器（72×48 拼接脚本） |
| `check_map.py` | 地图连通性校验 |
| `test_api.py` | 快速 API 冒烟测试 |
| `fix_npc.py` | NPC 数据修复脚本 |

---

## backend/ — Python 后端

### 入口与配置

| 文件 | 作用 |
|------|------|
| `app.py` | FastAPI 应用入口，挂载静态文件、注册路由 |
| `config.py` | 配置读取（`.env` → `Settings`） |
| `llm_client.py` | LLM 调用封装（chat_completion、缓存、重试） |

### API 路由

| 文件 | 作用 |
|------|------|
| `api/routes.py` | 所有 HTTP 端点：`/hello` `/move` `/npc/talk` `/agent/mind` `/finale` 等 |

### 数据定义

| 文件 | 作用 |
|------|------|
| `data/npcs_data.py` | NPC 角色卡：姓名、性格、背景、初始坐标、标签 |
| `data/maps_data.py` | 统一世界地图：单一 72×48 大地图，含河流/裂隙/废墟等危险地形 |
| `data/factions.py` | 势力数据：门派、帮会、朝廷等的声望分级 |
| `data/prompts.py` | 提示词模板：SOCIETY_BIBLE、MACHINE_TAIL_RULE 等 |
| `data/atmosphere.py` | 场景氛围文字生成器（时间/天气驱动） |
| `data/relationships.py` | NPC 间预设关系（师徒、仇敌等） |

### 模型

| 文件 | 作用 |
|------|------|
| `models/player.py` | PlayerState 数据类：属性、坐标、背包、声望、历史、NPC货柜、货柜补货追踪 |
| `models/npc.py` | NPC 角色卡格式化函数 |
| `models/llm_schema.py` | LLM JSON 响应 Schema（NpcResponseSchema 等） |

### 系统（核心玩法逻辑）

| 文件 | 作用 |
|------|------|
| `systems/pathfinding.py` | 寻路：Dijkstra 安全路径 + Bresenham 直线 + 危险地形通行/受伤判定 |
| `systems/core.py` | 核心数值操作：好感度、体力/心气计算、世界状态块、拘束状态 |
| `systems/economy.py` | 经济系统：铜钱变动、物品增减、物价表（25种物品/5类/6图溢价/天气波动）、行情查询、NPC货柜初始化/交易同步、NPC货柜自然补货（按周期回补） |
| `systems/save_system.py` | 存档系统：JSON 文件持久化（每角色独立文件）、序列化/反序列化、存档列表、死亡处理（真实江湖删档/非真实江湖复活至补给点） |
| `systems/encounter.py` | 动态奇遇系统：触发判定、LLM 生成、效果应用 |
| `systems/npc_gossip.py` | MAS 涌现：同格 NPC 社交闲聊、八卦传播 |
| `systems/reputation.py` | 声望系统：事件推送、声望数值计算 |
| `systems/time_weather.py` | 时间系统：时辰推进、昼夜判定、天气变化、世界日跨日触发NPC货柜补货 |

### 服务

| 文件 | 作用 |
|------|------|
| `services/talk_service.py` | 对话引擎：构建 NPC 消息、解析 LLM 回复、应用效果 |
| `services/agent_service.py` | Agent 自治：NPC 计划、反思、状态更新；后台任务异常日志 |

### 会话存储

| 文件 | 作用 |
|------|------|
| `session/store.py` | 玩家房间管理（内存缓存），get_or_create 优先从 JSON 文件加载已有存档 |

### 其他

| 文件 | 作用 |
|------|------|
| `agent_brain.py` | NPC 心智：反思（计划对照+情绪驱动）、交叉反思、每日规划 |
| `memory.py` | 记忆系统：AgentMind（计划、记忆、情感锚点、上下文感知检索、CMA凝结、情绪反馈思加速） |
| `game_state.py` | 游戏状态初始化与心智获取 |

---

## saves/ — 角色存档（运行时生成）

| 路径 | 作用 |
|------|------|
| `saves/<player_id>.json` | 每个角色一个独立 JSON 存档，包含完整 PlayerState（坐标/背包/声望/记忆流等） |

---

## tests/ — 自动化测试

| 路径 | 作用 |
|------|------|
| `tests/__init__.py` | Python 包标记 |
| `tests/conftest.py` | pytest 配置（路径注入） |
| `tests/_test_endpoints.py` | API 端点回归测试：角色创建/移动/对话/经济 |
| `tests/_test_pathfinding.py` | 寻路深度测试：全网可达性/cost-to-tick 折算 |

---

## static/ — 前端（纯 JS/CSS/HTML，无框架）

### 入口

| 文件 | 作用 |
|------|------|
| `index.html` | 主页面 HTML 结构：顶部栏、左侧栏（地图+场景）、右侧栏（NPC 对话） |
| `main.js` | 主控逻辑：游戏初始化、移动处理、WASD、格子菜单、状态同步 |
| `store.js` | 全局状态管理（发布/订阅模式），localStorage 持久化 playerId |

### 模块

| 文件 | 作用 |
|------|------|
| `api.js` | 后端 API 封装：pingModel、startGame、movePlayer、talkToNpc 等 |
| `map.js` | 地图渲染：canvas 滚动视口（角色居中）、瓦片网格、路线叠加、NPC 标记 |
| `scene.js` | 场景绘板：canvas 动态雾气/粒子效果 |
| `game.css` | 全局样式：古代江湖主题色、瓦片皮肤、响应式布局 |

### UI 组件

| 文件 | 作用 |
|------|------|
| `ui/dialogue.js` | 对话面板：NPC 选项卡、消息气泡、流式渲染、快捷动作 |
| `ui/sidebar.js` | 左侧栏：地图面板、氛围文、属性条、快捷操作 |
| `ui/journal.js` | 史册抽屉：对话回溯、状态变化、事件记录 |
| `ui/utils.js` | 通用工具：DOM 查询、HTML 转义 |

### 静态资源

| 路径 | 作用 |
|------|------|
| `assets/corner-cloud.svg` | 角落装饰云纹 |
| `assets/seal-mark.svg` | 印章标记 |
| `assets/wave-divider.svg` | 波纹分隔线 |

---

## docs/ — 文档与迭代记录

| 路径 | 作用 |
|------|------|
| `docs/PROJECT_STRUCTURE.md` | 本文件：项目结构说明 |
| `docs/iterations/` | 迭代记录文件夹，包含会话任务产物与迭代笔记 |

---

## 工作流

1. **启动**：`python -m uvicorn backend.app:app` → 访问 `http://127.0.0.1:8765`
2. **游玩**：输入姓名/性别 → 开始游戏 → 点击/键盘移动 → 与 NPC 对话
3. **存档**：playerId 存 localStorage，后端自动将角色存档写入 `saves/<player_id>.json`（每次移动/对话后自动保存）
4. **多角色**：`GET /api/saves` 列出全部角色 → `POST /api/load` 切换角色
5. **真实江湖**：死亡后存档自动删除，不可再入；非真实江湖：重伤后复活至最近补给点（50%体力）
4. **迭代记录**：每次迭代完成后在 `docs/iterations/` 下写入 `.md` 文件