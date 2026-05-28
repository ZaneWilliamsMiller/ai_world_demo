# 🏮 活纸江湖 · Living Paper

> **AI-NPC 社会推演与开放叙事实验** —— 基于开源大模型 API 的文字 RPG

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![Godot](https://img.shields.io/badge/Godot-4.3+-blueviolet.svg)](https://godotengine.org)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🎯 项目简介

**活纸江湖** 是一款基于大语言模型（LLM）的开放世界文字 RPG，采用 **MUD-like 架构**，玩家在 **150×100 网格的单一江湖世界** 中自由探索，与 **19 个拥有独立智能的 NPC** 进行自然语言交互。

### 核心特色

| 特性 | 描述 |
|------|------|
| 🧠 **AI NPC 大脑** | 基于 Stanford Generative Agents 架构，每个 NPC 拥有 `观察 → 反思 → 计划` 认知闭环 |
| 🗺️ **统一江湖地图** | 150×100「青石江湖·万里图」，河道自西北流向东南，裂隙与废墟散布险地 |
| 💬 **自然语言驱动** | 完全通过自由文本与 NPC 交互，对话影响制钱、背包、势力声望 |
| ⏰ **时辰推进系统** | 中国传统 12 时辰制，日夜循环、天气变化，NPC 行为受时空约束 |
| 📜 **江湖史册** | 集中查看历史对话、风闻、事件与 NPC 心迹记录，可回溯的叙事档案 |
| ☠️ **真实江湖模式** | 部分场景可导致 permadeath（真死），增加沉浸感 |
| 🧪 **测试中心** | Web/Godot 内置测试管理界面，一键运行诊断脚本 |
| ⏻ **服务管理** | 一键关闭前后端服务，优雅退出机制 |

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                        前端层 (Frontend)                    │
│                                                             │
│  ┌──────────────────┐    ┌──────────────────┐              │
│  │   Web 浏览器      │    │   Godot 桌面端   │              │
│  │   (原生 SPA)     │    │   (GDScript)     │              │
│  │                  │    │                  │              │
│  │ • CSS Grid 地图  │    │ • Node2D 渲染     │              │
│  │ • SSE 流式对话   │    │ • 信号驱动架构    │              │
│  │ • 测试中心       │    │ • 测试中心        │              │
│  │ • 关闭服务       │    │ • 关闭服务        │              │
│  └────────┬─────────┘    └────────┬─────────┘              │
│           │                       │                         │
│           └───────────┬───────────┘                         │
│                       ▼                                   │
│              ┌────────────────┐                             │
│              │  HTTP / SSE    │                             │
│              └────────┬───────┘                             │
└───────────────────────┼─────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                      后端层 (Backend)                       │
│                                                             │
│  ┌──────────────────────────────────────────────────┐       │
│  │              FastAPI 应用 (app.py)                 │       │
│  │                                                    │       │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐            │       │
│  │  │ API 路由 │ │ 业务服务 │ │ 游戏系统 │            │       │
│  │  │         │ │         │ │         │            │       │
│  │  │• player │ │• talk   │ │• core   │            │       │
│  │  │• npc    │ │• agent  │ │• time   │            │       │
│  │  │• save   │ │         │ │• econ   │            │       │
│  │  │• test   │ │         │ │• encoun │            │       │
│  │  │• shutdn │ │         │ │• reput │            │       │
│  │  └─────────┘ └─────────┘ └─────────┘            │       │
│  │                                                    │       │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐            │       │
│  │  │ 数据模型 │ │ 静态数据 │ │ 记忆系统 │            │       │
│  │  │         │ │         │ │         │            │       │
│  │  │• Player │ │• NPCs   │ │• entity │            │       │
│  │  │• NPC    │ │• Maps   │ │• format │            │       │
│  │  │• Schema │ │• Prompts│ │• retriev│            │       │
│  │  └─────────┘ └─────────┘ └─────────┘            │       │
│  └──────────────────────────────────────────────────┘       │
│                         │                                  │
│           ┌─────────────┼─────────────┐                  │
│           ▼             ▼             ▼                  │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐          │
│  │ LLM Client │ │ 存档系统   │ │ 配置管理   │          │
│  │ (httpx)    │ │ (JSON)     │ │ (.env)     │          │
│  └────────────┘ └────────────┘ └────────────┘          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 📂 目录结构

```
living-paper/
│
├── 📄 start.py                  # 统一启动脚本（一键启动前后端）
├── 📄 README.md                # 本文件
├── 📄 .env.example             # 环境变量模板
├── 📄 requirements.txt          # Python 依赖
│
├── 📁 backend/                 # Python 后端 (FastAPI)
│   ├── app.py                 # 主应用：路由注册、生命周期管理
│   ├── config.py              # 全局配置（LLM、端口、系统参数）
│   ├── llm_client.py          # LLM HTTP 客户端（连接池、熔断器）
│   ├── circuit_breaker.py     # 熔断器机制（防止级联故障）
│   ├── llm_cache.py           # Prompt Cache 缓存层
│   ├── memory_index.py        # 记忆索引管理
│   ├── game_state.py          # 全局游戏状态
│   ├── agent_brain.py         # NPC AI 大脑核心逻辑
│   │
│   ├── api/                   # HTTP 路由层
│   │   ├── routes.py          # 主路由注册（26个端点）
│   │   ├── player_routes.py   # 玩家接口（移动、状态、休息）
│   │   ├── npc_routes.py      # NPC 接口（对话、心迹、反思）
│   │   ├── save_routes.py     # 存档接口（保存、加载、删除）
│   │   └── test_routes.py     # 🔧 测试接口（新增）
│   │
│   ├── models/                # 领域模型
│   │   ├── player.py         # 玩家数据结构
│   │   ├── npc.py            # NPC 数据结构
│   │   └── llm_schema.py     # LLM JSON Schema 定义
│   │
│   ├── services/              # 业务编排层
│   │   ├── talk_service.py    # 对话服务（消息构建、LLM调用）
│   │   └── agent_service.py   # NPC 智能体服务
│   │
│   ├── systems/               # 核心游戏系统
│   │   ├── core.py            # 核心引擎（初始化、tick循环）
│   │   ├── time_weather.py    # 时间天气系统（12时辰制）
│   │   ├── economy.py         # 经济系统
│   │   ├── encounter.py       # 遭遇系统
│   │   ├── pathfinding.py     # 路径查找（A*算法）
│   │   ├── perception.py      # 感知系统
│   │   ├── reputation.py      # 声望系统
│   │   ├── bounty_board.py    # 悬赏榜系统
│   │   ├── trap.py           # 移动锁定陷阱系统
│   │   ├── prompt_compress.py # Prompt 压缩优化
│   │   ├── npc_state.py       # NPC 状态机
│   │   ├── npc_gossip.py      # NPC 八卦闲聊系统
│   │   └── save_system.py     # 存档系统
│   │
│   ├── data/                  # 静态游戏数据
│   │   ├── npcs_data.py       # 19个NPC定义
│   │   ├── maps_data.py      # 150×100地图数据
│   │   ├── factions.py        # 5大势力定义
│   │   ├── atmosphere.py      # 氛围描述库
│   │   ├── relationships.py   # 关系网络
│   │   └── prompts.py         # 系统提示词模板
│   │
│   ├── memory/                # 记忆系统
│   │   ├── entities.py        # 记忆实体定义
│   │   ├── format.py          # 记忆格式化
│   │   └── retrieval.py       # 记忆检索（倒排索引）
│   │
│   └── session/               # 会话管理
│       └── store.py           # 玩家会话存储
│
├── 📁 static/                  # Web 前端（原生 SPA）
│   ├── index.html             # 主页面（登录+游戏）
│   ├── tests.html             # 🔧 测试中心页面（新增）
│   │
│   ├── css/
│   │   └── game.css           # 暗色江湖主题 + 动画效果
│   │
│   └── js/
│       ├── main.js            # 主控制器（状态管理、事件监听）
│       ├── api.js             # API 封装（HTTP/SSE）
│       ├── map.js             # 地图渲染（CSS Grid）
│       ├── dialogue.js        # 对话 UI 管理
│       ├── ui.js              # UI 组件（确认对话框、提示框）
│       ├── store.js           # 本地存储
│       └── llm-test.js        # LLM 连接测试工具
│
├── 📁 godot/                   # Godot 桌面端
│   ├── project.godot          # Godot 项目文件
│   ├── scenes/                # 场景文件
│   │   ├── login.tscn         # 登录场景
│   │   └── game.tscn          # 游戏主场景
│   │
│   └── scripts/               # GDScript 脚本
│       ├── game_manager.gd    # 全局游戏管理器
│       ├── main_game.gd       # 主游戏逻辑（测试中心、关闭服务）
│       ├── login_screen.gd    # 登录界面
│       ├── api_client.gd      # HTTP 客户端（异步请求）
│       ├── map_renderer.gd    # 地图渲染器
│       ├── dialogue_ui.gd     # 对话界面
│       └── llm_test.gd        # LLM 连接测试
│
├── 📁 tests/                   # 自动化测试脚本
│   ├── conftest.py            # Pytest 配置
│   ├── test_backend.py        # 后端基础测试
│   ├── test_e2e.py            # 端到端测试
│   ├── test_diagnose_talk.py  # NPC 对话诊断
│   ├── test_500_error.py      # 500 错误排查
│   ├── test_direct_talk.py    # 直接对话测试
│   ├── test_llm_json.py       # LLM JSON 格式验证
│   ├── test_npc_talk.py       # NPC 对话 API 测试
│   └── ...                    # 更多测试脚本
│
├── 📁 tools/                   # 开发辅助工具
│   ├── auto_test.py           # 自动化连续测试
│   ├── debug_talk.py          # 对话调试工具
│   ├── gen_map.py             # 地图生成工具
│   ├── smoke_api.py           # API 冒烟测试
│   └── verify_all.py          # 全面验证脚本
│
├── 📁 docs/                    # 文档
│   ├── overview.md            # 项目概览
│   ├── PROJECT_STRUCTURE.md   # 详细架构说明
│   └── iterations/           # CI 迭代记录归档
│
├── 📁 third-party/             # 第三方依赖声明
│   └── THIRD_PARTY.md        # 许可证信息
│
└── 📁 .github/                 # GitHub Actions
    └── workflows/
        └── ci.yml            # CI/CD 配置
```

---

## 🚀 快速开始

### 1️⃣ 克隆项目

```bash
git clone -b qclaw https://github.com/ZaneWilliamsMiller/living-paper.git
cd living-paper
```

### 2️⃣ 安装依赖

```bash
pip install -r requirements.txt
```

**主要依赖**：
- `fastapi` - Web 框架
- `uvicorn` - ASGI 服务器
- `httpx` - 异步 HTTP 客户端
- `pydantic` - 数据验证
- `python-dotenv` - 环境变量管理
- `jieba` - 中文分词（记忆检索）

### 3️⃣ 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入你的 LLM API Key
```

**关键配置项**：
```env
# LLM 服务配置（必填）
LLM_BASE_URL=https://your-llm-api.example.com/v1
LLM_API_KEY=sk-your-api-key-here
LLM_MODEL=your-model-name

# 服务端口（可选，有默认值）
BACKEND_PORT=8765
FRONTEND_PORT=8766
```

> **推荐模型**：DeepSeek V3/V4、Qwen 系列、或任何兼容 OpenAI API 的模型

### 4️⃣ 启动游戏

#### 方式 A：一键启动（推荐）⭐

```bash
# 启动后端 + Web 前端
python start.py

# 启动后端 + Godot 前端
python start.py godot

# 自定义端口
python start.py --backend-port 8765 --frontend-port 8766

# 仅启动前端静态服务器（不启动后端）
python start.py --serve-only 8766
```

#### 方式 B：手动启动

**后端**：
```bash
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8765
```

**Web 前端**：
```bash
python start.py --serve-only 8766
# 浏览器访问 http://127.0.0.1:8766
```

**Godot 前端**：
1. 安装 [Godot 4.3+](https://godotengine.org/download)
2. 打开 Godot 编辑器 → 导入项目 → 选择 `godot/` 目录
3. 按 `F5` 运行

---

## 🎮 功能特性

### 🌐 Web 前端特性

| 功能 | 说明 |
|------|------|
| **响应式地图** | CSS Grid 150×100 实时渲染，支持点击移动 |
| **SSE 流式对话** | 打字机效果实时显示 NPC 回复 |
| **🧪 测试中心** | Web 界面管理测试脚本，一键运行诊断 |
| **⏻ 关闭服务** | 三重保障机制（重试+验证），安全停止所有服务 |
| **确认对话框** | 自定义模态框替代原生 confirm，防止误操作 |
| **错误高亮** | 409/500 错误详细提示 + 视觉强化 |
| **双 API 模式** | 后端模式 / 自定义 LLM Key 模式 |

### 🎮 Godot 前端特性

| 功能 | 说明 |
|------|------|
| **原生渲染** | Node2D Canvas 绘制地图与角色 |
| **信号驱动** | GDScript 信号槽机制解耦逻辑 |
| **🧪 测试中心** | 与 Web 版完全一致的测试管理 |
| **⏻ 关闭服务** | 可真正调用 `get_tree.quit()` 退出应用 |
| **确认对话框** | BBCode 富文本，动态 UI 构建 |
| **离线能力** | 可独立运行（需配置本地 LLM） |

### 🔧 后端 API

#### 核心 API

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| POST | `/api/hello` | 创建/恢复角色 |
| POST | `/api/move` | 移动（含锁定检测、遭遇、陷阱） |
| GET | `/api/state/{pid}` | 玩家完整状态 |
| GET | `/api/journal/{pid}` | 江湖史册查询 |

#### NPC 交互 API

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/npc/talk` | NPC 对话（非流式） |
| POST | `/api/npc/talk_stream` | NPC 对话（SSE 流式） |
| POST | `/api/item/use` | 使用背包物品 |
| POST | `/api/rest` | 休息恢复 |
| POST | `/api/finale` | 终局收束 |

#### 悬赏系统 API

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/bounty/refresh` | 刷新悬赏榜 |
| POST | `/api/bounty/accept` | 接受悬赏 |
| POST | `/api/bounty/check` | 检查悬赏进度 |
| POST | `/api/bounty/complete` | 完成悬赏 |
| POST | `/api/bounty/abandon` | 放弃悬赏 |

#### AI 调试 API

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/agent/{pid}/{npc}/mind` | NPC 心迹查询 |
| POST | `/api/agent/reflect` | 手动触发反思 |
| POST | `/api/agent/plan` | 手动触发计划 |

#### 存档 API

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/saves` | 存档列表 |
| POST | `/api/save` | 手动存档 |
| POST | `/api/load` | 读档恢复 |
| POST | `/api/delete-save` | 删除存档 |

#### 管理 API

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/tests/list` | 列出可用测试 |
| POST | `/api/tests/run/{name}` | 执行指定测试 |
| POST | `/api/shutdown` | 关闭后端服务 |

> 完整 API 文档可在启动后访问 `http://127.0.0.1:8765/docs` 查看（Swagger UI）

---

## 🧪 测试体系

### 测试分类

| 类别 | 文件 | 用途 |
|------|------|------|
| **后端健康** | `test_backend_health.py` | API 可用性验证 |
| **对话诊断** | `test_diagnose_talk.py` | NPC 对话完整流程诊断（6步） |
| **错误排查** | `test_500_error.py` | 500 错误定位 |
| **LLM 测试** | `test_llm_json.py` | LLM JSON 格式验证 |
| **直接对话** | `test_direct_talk.py` | 绕过 API 直接测试对话服务 |
| **E2E 测试** | `test_e2e.py` | 端到端流程测试 |
| **冒烟测试** | `test_startup.py` | 启动流程验证 |

### 使用方式

**方式 1：Web 测试中心**（推荐）
```
浏览器访问 http://127.0.0.1:8766/tests.html
→ 点击 "▶ 运行" 按钮
→ 查看实时输出和执行结果
```

**方式 2：Godot 测试中心**
```
登录界面点击 "🧪 测试" 按钮
→ 选择要运行的测试
→ 查看输出结果
```

**方式 3：命令行**
```bash
cd tests
python test_diagnose_talk.py
```

---

## 🛠️ 开发工具

### 工具脚本（tools/）

| 脚本 | 功能 |
|------|------|
| `auto_test.py` | 自动化连续 API 测试 |
| `debug_talk.py` | 交互式对话调试 |
| `gen_map.py` | 地图数据可视化生成 |
| `smoke_api.py` | API 冒烟测试（快速验证） |
| `verify_all.py` | 全面系统验证 |
| `check_map.py` | 地图数据完整性检查 |
| `check_url.py` | URL 配置验证 |
| `check_json.py` | JSON 格式校验 |

### CI/CD

项目配置了 GitHub Actions（`.github/workflows/ci.yml`），每次推送自动运行：
- 后端单元测试
- API 集成测试
- LLM 连通性验证

---

## 🌍 世界设定

### 地理环境

**青石江湖·万里图**（150×100 格）

- **水系**：主河道自西北向东南贯穿，沿岸分布城镇
- **地形**：平原、山地、裂隙、废墟、密林
- **城镇**：县城（中央）、同福栈、威远镖局、书院
- **险地**：裂隙地带（东北）、废弃矿坑（西南）

### NPC 名录（19位）

| 姓名 | 身份 | 所属势力 | 所在地 |
|------|------|---------|--------|
| 风闻子 (jiang) | 江湖纪事记者 | 无固定 | 街头巷尾 |
| 沈掌柜 (zhanggui) | 同福栈掌柜 | 商贾 | 同福栈 |
| 金算计 (jinsuanji) | 钱庄账房 | 商贾 | 钱庄 |
| 雷三 (bullya) | 皂隶 | 衙门 | 县衙附近 |
| 赵铁鹰 (biaotou) | 威远镖局镖头 | 镖局 | 威远镖局 |
| 柳无眉 (liuwumei) | 医馆郎中 | 无固定 | 医馆 |
| ... | ... | ... | ... |

### 五大势势

| 势力 | 代表人物 | 影响范围 |
|------|---------|---------|
| **衙门** | 雷三、钱卡吏 | 县城治安、税收 |
| **镖局** | 赵铁鹰 | 护运、保镖业务 |
| **漕帮** | 渔老七、薛驿卒 | 水运、码头 |
| **书院** | 慧尘知客 | 教育、舆论 |
| **绿林** | 剪径匪、暗流 | 山林、地下交易 |

---

## 🤖 AI 系统详解

### NPC 认知架构

```
┌─────────────────────────────────────────┐
│              NPC Agent Brain            │
│                                         │
│  ┌───────────┐    ┌───────────┐         │
│  │ Observe   │    │ Reflect   │         │
│  │ (感知)     │───▶│ (反思)     │         │
│  │            │    │            │         │
│  │ • 环境    │    │ • 记忆提取 │         │
│  │ • 对话    │    │ • 洞察分析 │         │
│  │ • 事件    │    │ • 洞察生成 │         │
│  └───────────┘    └─────┬─────┘         │
│                        │               │
│                        ▼               │
│  ┌───────────┐    ┌───────────┐         │
│  │ Plan      │◀───│ Memory    │         │
│  │ (计划)     │    │ (记忆)     │         │
│  │            │    │            │         │
│  │ • 日程规划 │    │ • 实体存储 │         │
│  │ • 目标设定 │    │ • 倒排索引 │         │
│  │ • 行动决策 │    │ • 向量检索 │         │
│  └───────────┘    └───────────┘         │
│                                         │
└─────────────────────────────────────────┘
```

### 记忆系统

- **存储格式**：实体-属性-值三元组
- **索引方式**：jieba 中文分词 + 倒排索引
- **检索策略**：向量相似度 + 时间衰减 + 重要性加权
- **容量限制**：每 NPC 最大 150 条记忆（自动淘汰旧记忆）

### 对话流程

```
用户输入 "你好"
    ↓
talk_service.build_messages()
    ├─ 加载 NPC 人设 System Prompt
    ├─ 加载近期对话历史（最近 10 轮）
    ├─ 注入时间/天气/位置上下文
    └─ 注入相关记忆（检索 Top-K 条）
    ↓
LLM Client.chat()
    ├─ 发送至 LLM API（OpenAI 兼容格式）
    ├─ Prompt Cache 命中率 ~80%
    └─ 熔断器保护（连续失败自动降级）
    ↓
解析 LLM 响应
    ├─ 成功 → 返回 visible_text + hidden_text
    └─ 失败 → Graceful Fallback（通用回复）
```

---

## 📊 技术指标

| 指标 | 数值 |
|------|------|
| **地图尺寸** | 150×100 = 15,000 格子 |
| **NPC 数量** | 19 个（各有独立 AI） |
| **API 端点数** | 25 个 |
| **测试脚本数** | 18+ 个 |
| **代码总量** | ~15,000 行 Python + ~5,000 行 GDScript + ~3,000 行 JS |
| **Prompt Cache 命中率** | ~80%（降低延迟 50%） |
| **平均对话延迟** | 2-5 秒（取决于 LLM） |
| **内存占用（后端）** | ~120 MB |
| **支持的 LLM** | DeepSeek/Qwen/Ollama/任意 OpenAI 兼容 API |

---

## 🔄 项目历史（精选）

| 日期 | 里程碑 |
|------|--------|
| **05-28** | 🎉 **本次更新**：测试中心 + 关闭服务 + 错误优化 + Godot同步 |
| **05-27** | 代词消解动态化 + 记忆摘要情感增强 + 双前端架构合并 |
| **05-26** | 后端架构优化：连接池/熔断器/缓存/记忆索引/悬赏榜/Prompt压缩 |
| **05-25** | 心境一致性记忆检索；夜间反思保护；复活清奴役终局 |
| **05-24** | 计划-观察偏差分析；反思情绪印迹回写；CMA 记忆凝结 |
| **05-23** | Prompt Cache 架构；存档系统；氛围注入；情感锚点 |
| **05-13** | 项目核心系统奠基：NPC 认知闭环/记忆演化/社交闲聊/际遇桥接 |
| **05-08** | 项目立项 |

> 完整迭代记录详见 [docs/iterations/](docs/iterations/)

---

## 📦 依赖清单

详见 [third-party/THIRD_PARTY.md](third-party/THIRD_PARTY.md)

### Python 核心依赖

```
fastapi>=0.100.0
uvicorn[standard]>=0.23.0
httpx>=0.25.0
pydantic>=2.0
python-dotenv>=1.0.0
jieba>=0.42.1
```

### Godot 要求

- **Godot Engine**: 4.3 或更高版本
- **GDScript**: 2.0（严格类型）

---

## 🤝 贡献指南

### 开发流程

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交改动 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

### 代码规范

- **Python**: 遵循 PEP 8，使用类型注解
- **GDScript**: 遵循 [GDScript Style Guide](https://docs.godotengine.org/en/stable/tutorials/scripting/gdscript/gdscript_styleguide.html)
- **JavaScript**: 使用 ES6+ 语法
- **注释**: 重要逻辑添加中文注释

### 测试要求

- 新增功能必须包含对应测试
- 通过 `pytest tests/` 全部测试
- 手动测试 Web 和 Godot 前端

---

## 📄 许可证

本项目遵循上游仓库的许可证约定。

第三方依赖的许可证详见 [third-party/THIRD_PARTY.md](third-party/THIRD_PARTY.md)。

---

## 🙏 致谢

- **Stanford University** - Generative Agents 论文与架构
- **DeepSeek Team** - 高性能开源 LLM
- **Godot Engine Community** - 卓越的开源游戏引擎
- **FastAPI/Tiangolo** - 现代 Python Web 框架

---

## 📞 联系方式

- **GitHub Issues**: [提交问题](https://github.com/ZaneWilliamsMiller/living-paper/issues)
- ** Discussions**: [参与讨论](https://github.com/ZaneWilliamsMiller/living-paper/discussions)

---

<div align="center">

**⭐ 如果这个项目对你有帮助，请给一个 Star！⭐**

*让 AI NPC 在数字世界中自由呼吸*

</div>
