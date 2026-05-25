# 活纸 · Living Paper

> 🎯 面向 AI-NPC 社会推演与开放叙事的创新 Demo，「基于开源大模型 API 的 AI 游戏」。

基于 LLM 的开放叙事文字游戏（MUD-like），玩家在 **单一 72×48 网格世界**中行走、与 **16 个 NPC** 自然语言互动。世界随时间辰（时辰制）与天气持续演化，**每个 NPC 拥有独立记忆、反思与日程规划能力**，形成去中心化的社会推演系统。

## 核心创新

- **🧠 智能 NPC 大脑**：每个角色基于斯坦福小镇 Generative Agents 架构，拥有 `observation → reflection → plan` 认知闭环。NPC 会从对话中提取重要记忆、定期反思生成抽象洞察、并根据身份与反思自动规划每日行程。
- **🗺️ 单一江湖地图**：72×48 统一大地图，河道自西北流向东南，裂隙与废墟散布险地（触发际遇/受伤）。
- **💬 自然语言驱动**：完全通过自由文本与 NPC 交互，对话结果影响制钱、背包、势力声望、风闻与全局事件。
- **⏳ 时辰推进系统**：采用中国传统 12 时辰制，日夜循环、天气变化，NPC 行为受时空上下文约束。
- **📜 江湖史册**：集中查看历史对话、风闻、事件与 NPC 心迹记录，形成可回溯的叙事档案。
- **⚔️ 真实江湖模式**：部分 NPC/地形可导致 permadeath（真死），增加沉浸感。

## 世界数据

| 类型 | 数量 | 详情 |
|------|------|------|
| 地图 | 1 | 72×48 统一大地图「青石江湖·万里图」 |
| NPC | 16 | 风闻子、沈掌柜、金算计、雷三、赵铁鹰、柳无眉、剪径匪、暗流、渔老七、阿泠、周里正、薛驿卒、慧尘知客、沙掌盘、陆文潜、钱卡吏 |
| 势力 | 5 | 衙门、镖局、漕帮、书院、绿林 |

## 技术栈

- 后端：`FastAPI` + `httpx` 异步 HTTP
- 前端：原生 `HTML/CSS/JavaScript` 静态页面（Canvas 地图 + 层级 UI）
- LLM：OpenAI 兼容 API（DeepSeek、Qwen、本地 Ollama 等均可）
- 数据组织：内存会话态（玩家独立实例）+ 规则驱动的世界状态更新

## 快速开始

```bash
cd living-paper
python3 -m pip install -r requirements.txt
cp .env.example .env
python3 -m uvicorn backend.app:app --host 127.0.0.1 --port 8765
```

浏览器访问 [http://127.0.0.1:8765](http://127.0.0.1:8765)。

## 环境配置

克隆后复制 `.env.example` 为 `.env`，填入 LLM API Key：

```bash
cp .env.example .env
# 编辑 .env，设置：
# LLM_BASE_URL=https://api.deepseek.com/v1
# LLM_API_KEY=你的 API 密钥
# LLM_MODEL=deepseek-chat
```

> 💡 推荐使用 DeepSeek V3 或兼容 OpenAI 的任意模型。

## 目录结构

### 后端 `backend/`

| 路径 | 说明 |
|------|------|
| `app.py` | FastAPI 应用入口，挂载静态文件、注册路由 |
| `config.py` | 配置读取（`.env` → `Settings`） |
| `llm_client.py` | LLM 调用封装（chat_completion、缓存、重试） |
| `memory.py` | NPC 记忆存储 |
| `agent_brain.py` | NPC 认知闭环（观察/反思/计划/搜索） |
| `game_state.py` | 游戏全局状态 |
| `api/routes.py` | 所有 HTTP 端点（15 个） |
| `data/` | 静态数据 |
| `data/npcs_data.py` | NPC 角色卡：姓名、性格、背景、初始坐标、标签 |
| `data/maps_data.py` | 统一世界地图：单一 72×48 大地图，含河道/裂隙/废墟等危险地形 |
| `data/factions.py` | 势力数据：门派、帮会、朝廷等的声望分级 |
| `data/prompts.py` | 提示词模板：SOCIETY_BIBLE、MACHINE_TAIL_RULE 等 |
| `data/atmosphere.py` | 场景氛围文字生成器（时间/天气驱动） |
| `data/relationships.py` | NPC 间预设关系（师徒、仇敌等） |
| `models/` | 领域数据模型 |
| `models/player.py` | PlayerState 数据类：属性、坐标、背包、声望、历史、NPC货柜、货柜补货追踪 |
| `models/npc.py` | NPC 角色卡格式化函数 |
| `models/llm_schema.py` | LLM JSON 响应 Schema（NpcResponseSchema 等） |
| `services/` | 业务编排层 |
| `services/talk_service.py` | 对话服务：Prompt Cache 静态/动态分层 + 消息构建 |
| `services/agent_service.py` | NPC 智能体：自动反思（含夜间保护）、计划生成 |
| `session/` | 会话态存储 |
| `session/store.py` | 内存会话管理 |
| `systems/` | 核心玩法系统 |
| `systems/pathfinding.py` | 寻路：Dijkstra 安全路径 + Bresenham 直线 + 危险地形通行/受伤判定 |
| `systems/time_weather.py` | 时辰天气：12 时辰推进、日夜判定、天气轮换 |
| `systems/core.py` | 核心逻辑：NPC 初始化、游走、移动触发际遇、精力精神 |
| `systems/economy.py` | 经济系统：NPC 货柜、补货、玩家背包 |
| `systems/encounter.py` | 际遇系统：危险地形触发随机事件 + NPC 拦路 |
| `systems/npc_gossip.py` | NPC 八卦：NPC 间非玩家驱动的信息传播 |
| `systems/reputation.py` | 声望系统：势力好感、事件推送 |
| `systems/save_system.py` | 存档系统：手动/自动存档、读档、删档、复活点重生 |

### 前端 `static/`

| 路径 | 说明 |
|------|------|
| `index.html` | 前端页面入口 |
| `main.js` | 前端初始化与主流程 |
| `map.js` | 地图渲染与交互 |
| `scene.js` | 场景/氛围文字渲染 |
| `store.js` | 前端状态管理 |
| `api.js` | 后端 API 调用封装 |
| `game.css` | 全局样式 |
| `ui/` | UI 模块 |
| `ui/dialogue.js` | 对话面板 |
| `ui/journal.js` | 江湖史册面板 |
| `ui/sidebar.js` | 侧栏控制 |
| `ui/utils.js` | UI 工具函数 |
| `assets/` | 静态资源（SVG 装饰） |

### 其他

| 路径 | 说明 |
|------|------|
| `tools/` | 辅助工具（地图生成/校验/API 烟雾测试） |
| `tests/` | 自动化测试（端点到端到端检测） |
| `docs/` | 文档与迭代记录 |
| `docs/iterations/` | 每日 CI 迭代产物归档 |
| `saves/` | 角色存档（运行时生成） |

## API 端点

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| POST | `/api/hello` | 创建/恢复角色 |
| POST | `/api/move` | 移动 |
| GET | `/api/state/{player_id}` | 玩家状态查询 |
| POST | `/api/npc/talk` | NPC 对话（非流式） |
| POST | `/api/npc/talk_stream` | NPC 对话（流式/SSE） |
| GET | `/api/agent/{player_id}/{npc_id}/mind` | NPC 心迹查询（记忆/反思/计划） |
| POST | `/api/agent/reflect` | 手动触发 NPC 反思 |
| POST | `/api/agent/plan` | 手动触发 NPC 计划 |
| GET | `/api/saves` | 存档列表 |
| POST | `/api/save` | 手动存档 |
| POST | `/api/load` | 读档 |
| POST | `/api/delete-save` | 删档 |
| GET | `/api/journal/{player_id}` | 江湖史册 |
| POST | `/api/finale` | 终局判定 |

## 项目历史（精选）

近期关键迭代：

| 日期 | 主题 |
|------|------|
| 05-25 | 复活清奴役终局：respawn 清除 enslaved/ended 防死锁 |
| 05-25 | 心境一致性记忆检索：NPC 检索记忆时融入情绪偏差 |
| 05-25 | 夜间反思保护：子时-寅时跳过自动反思 |
| 05-24 | 计划-观察偏差分析：启发式对比计划与观察覆盖 |
| 05-24 | 反思情绪印迹回写：规则式情感分析反馈到 NPC 情绪 |
| 05-24 | 不可通行格子打探/交谈 NPC |
| 05-24 | CMA 记忆凝结：实际删除旧观察、摘要锚点保留 |
| 05-23 | Prompt Cache 架构：talk_service 拆分静态/动态层 |
| 05-23 | 存档系统：序列化/反序列化、角色复活 |
| 05-08 | 项目立项 |

完整迭代记录详见 [docs/iterations/](docs/iterations/)。