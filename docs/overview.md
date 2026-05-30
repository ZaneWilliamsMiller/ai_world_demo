# 活纸江湖 · 项目文档

> 最后更新：2026-05-31

## 项目信息

- **源仓库**: https://github.com/ZaneWilliamsMiller/living-paper/tree/qclaw
- **定位**: AI-NPC 社会推演与开放叙事实验 —— 基于开源大模型 API 的文字 RPG

---

## 核心特色

| 特性 | 描述 |
|------|------|
| 🧠 **AI NPC 大脑** | 基于 Stanford Generative Agents 架构，每个 NPC 拥有 `观察 → 反思 → 计划` 认知闭环 |
| 🗺️ **统一江湖地图** | 150×100「青石江湖·万里图」，河道自西北流向东南，裂隙与废墟散布险地 |
| 💬 **自然语言驱动** | 完全通过自由文本与 NPC 交互，对话影响制钱、背包、势力声望 |
| ⏰ **时辰推进系统** | 中国传统 12 时辰制，日夜循环、天气变化，NPC 行为受时空约束 |
| ☠️ **真实江湖模式** | 部分场景可导致 permadeath（真死），增加沉浸感 |

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                        前端层 (Frontend)                    │
│                                                             │
│  ┌──────────────────┐    ┌──────────────────┐              │
│  │   Web 浏览器      │    │   Godot 桌面端   │              │
│  │   (原生 SPA)     │    │   (GDScript)     │              │
│  └────────┬─────────┘    └────────┬─────────┘              │
│           └───────────┬───────────┘                         │
│                       ▼                                   │
│              HTTP / SSE                                   │
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
│  │  │• player │ │• talk   │ │• core   │            │       │
│  │  │• npc    │ │• agent  │ │• time   │            │       │
│  │  │• save   │ │         │ │• econ   │            │       │
│  │  │• admin  │ │         │ │• reput  │            │       │
│  │  └─────────┘ └─────────┘ └─────────┘            │       │
│  │                                                    │       │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐            │       │
│  │  │ 数据模型 │ │ 静态数据 │ │ 记忆系统 │            │       │
│  │  │• Player │ │• NPCs   │ │• entity │            │       │
│  │  │• NPC    │ │• Maps   │ │• format │            │       │
│  │  └─────────┘ └─────────┘ └─────────┘            │       │
│  │                                                    │       │
│  │  ┌─────────────────────────────────────────┐      │       │
│  │  │       API Schema 契约层                   │      │       │
│  │  │  Pydantic 响应模型 · OpenAPI · TS 类型   │      │       │
│  │  └─────────────────────────────────────────┘      │       │
│  └──────────────────────────────────────────────────┘       │
│           ┌─────────────┼─────────────┐                  │
│           ▼             ▼             ▼                  │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐          │
│  │ LLM Client │ │ 存档系统   │ │ 配置管理   │          │
│  └────────────┘ └────────────┘ └────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

---

## 目录结构

```
living-paper/
├── backend/              # Python 后端 (FastAPI)
│   ├── app.py            # 应用入口：路由注册、生命周期管理
│   ├── config.py         # 全局配置（LLM/连接池/熔断/缓存/重试）
│   ├── api/              # API 路由层（44 个端点 + Pydantic Schema 契约）
│   ├── agents/           # NPC 认知闭环（观察/反思/计划/行动）
│   ├── llm/              # LLM 客户端（连接池/熔断器/缓存/压缩）
│   ├── memory/           # 记忆系统（实体/格式/索引/检索）
│   ├── models/           # 领域模型（Player/NPC/LLM Schema）
│   ├── services/         # 业务编排（对话/智能体）
│   ├── systems/          # 游戏系统（核心/经济/遭遇/感知/寻路/声望/悬赏/陷阱/存档...）
│   ├── data/             # 静态数据（NPC/地图/阵营/氛围/关系/区域/提示词）
│   ├── session/          # 会话存储
│   └── observability/    # 可观测性（LLM 调用追踪）
├── static/               # Web 前端（原生 SPA + TypeScript 类型定义）
├── godot/                # Godot 前端（GDScript + API Schema 参考）
│   └── api-schema/       # JSON Schema 文件
├── third-party/          # 第三方依赖声明
├── tools/                # 工具脚本（含 Schema 生成）
├── tests/                # 自动化测试（1320+ 用例）
│   ├── unit/             # 单元测试
│   ├── integration/      # 集成测试
│   └── interactive/      # 交互测试
├── docs/                 # 文档与迭代记录
├── saves/                # 角色存档（运行时生成, gitignore）
├── .env / .env.example   # 环境变量
├── start.py              # 一键启动脚本
└── requirements.txt      # Python 依赖
```

---

## 后端模块详解

### 入口与配置

| 文件 | 作用 |
|------|------|
| `app.py` | FastAPI 应用入口：挂载静态文件、注册路由、定期自动存档、shutdown 优雅关闭 |
| `config.py` | 配置读取（`.env` → `Settings`）：LLM/连接池/熔断/缓存/重试/Prompt Cache 开关 |

### API 路由

| 文件 | 作用 |
|------|------|
| `api/routes.py` | 核心 HTTP 端点：health/shutdown 等 |
| `api/schema.py` | API 响应模型定义：42 个 Pydantic Response 模型 + 12 个组件模型 |
| `api/player_routes.py` | 玩家接口：hello/move/state/journal |
| `api/npc_routes.py` | NPC 接口：对话/心迹/反思/计划/行动/悬赏/终局 |
| `api/save_routes.py` | 存档接口：保存/加载/删除 |
| `api/admin_routes.py` | 管理接口：指标/熔断器/玩家列表/NPC 状态 |
| `api/views.py` | 共享视图函数：player_public/build_init_response |
| `api/dev.py` | 开发端点：测试中心/交互测试/熔断器重置 |

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

### 可观测性

| 文件 | 作用 |
|------|------|
| `observability/tracker.py` | LLM 调用追踪器 |

### 数据定义

| 文件 | 作用 |
|------|------|
| `data/npcs_data.py` | NPC 角色卡数据 |
| `data/maps_data.py` | 统一世界地图数据 |
| `data/factions.py` | 势力数据 |
| `data/prompts.py` | 提示词模板 |
| `data/atmosphere.py` | 场景氛围文字生成器（时间/天气驱动） |
| `data/relationships.py` | NPC 间预设关系 |
| `data/zones.py` | 地图区域定义 |

### 领域模型

| 文件 | 作用 |
|------|------|
| `models/player.py` | PlayerState：属性/坐标/背包/声望/历史/悬赏榜 |
| `models/npc.py` | NPC 角色卡格式化函数 |
| `models/llm_schema.py` | LLM JSON 响应 Schema |

### 业务编排

| 文件 | 作用 |
|------|------|
| `services/talk_service.py` | 对话服务：Prompt Cache 分层构建 / 消息构建 / 回复应用 / 优雅降级 |
| `services/agent_service.py` | NPC 智能体：自动反思 / 计划生成 / 记忆凝结 |

### 会话与持久化

| 文件 | 作用 |
|------|------|
| `session/store.py` | 内存会话管理 + 启动时自动从 saves/ 恢复活跃玩家 |

### 核心系统

| 文件 | 作用 |
|------|------|
| `systems/core.py` | 核心逻辑：NPC 游走/移动触发际遇/体力心气/感知扫描 |
| `systems/constants.py` | 游戏常量定义 |
| `systems/pathfinding.py` | 寻路：Dijkstra 安全路径 + 危险地形判定 |
| `systems/time_weather.py` | 时辰天气：12 时辰制推进/日夜判定/天气轮换 |
| `systems/economy.py` | 经济系统：NPC 货柜/补货/玩家背包 |
| `systems/encounter.py` | 际遇系统：危险地形事件 + NPC 拦路 + 动态奇遇叙事 |
| `systems/npc_gossip.py` | NPC 八卦：NPC 间非玩家驱动的信息传播 |
| `systems/npc_state.py` | NPC 状态管理：作息/游走/情绪 |
| `systems/perception.py` | 感知系统 |
| `systems/reputation.py` | 声望系统：势力好感/事件推送 |
| `systems/save_system.py` | 存档系统：序列化/反序列化/读档/删档 |
| `systems/bounty_board.py` | 悬赏榜系统 |
| `systems/trap.py` | 陷阱系统 |
| `systems/task_fsm.py` | 任务 FSM 状态机 |
| `systems/consistency.py` | 一致性检查 |

---

## 前端

### Web（static/）

| 文件 | 作用 |
|------|------|
| `index.html` | SPA 入口 |
| `tests.html` | 测试中心页面 |
| `css/game.css` | 暗色江湖主题 |
| `js/api.js` | API 封装（HTTP/SSE） |
| `js/main.js` | 主控制器 |
| `js/map.js` | 地图渲染（CSS Grid 16px 瓦片） |
| `js/dialogue.js` | 对话系统（SSE 流式） |
| `js/ui.js` | UI 组件 |
| `js/store.js` | 状态管理 |
| `js/api-types.d.ts` | 自动生成的 TypeScript 类型定义 |
| `js/tests.js` | 测试中心逻辑 |

部署方式：由 FastAPI 挂载 StaticFiles，前后端同端口部署。

### Godot（godot/）

| 文件 | 作用 |
|------|------|
| `scripts/api_client.gd` | HTTP 客户端（异步请求） |
| `scripts/game_manager.gd` | 全局游戏管理器（信号驱动） |
| `scripts/main_game.gd` | 主游戏逻辑 |
| `scripts/map_renderer.gd` | 地图渲染组件 |
| `scripts/dialog_manager.gd` | 对话管理 |
| `scripts/config_panel.gd` | 配置面板 |
| `scripts/ui_builder.gd` | 动态 UI 构建 |
| `scripts/game_colors.gd` | 游戏色彩常量 |
| `scripts/shutdown_service.gd` | 关闭服务管理 |
| `scripts/test_center.gd` | 测试中心 |
| `scripts/llm_test.gd` | LLM 连接测试 |
| `scripts/message_display.gd` | 消息显示 |
| `api-schema/` | JSON Schema 文件供 Godot 参考 |

---

## API 契约层

项目建立了完整的 API Schema 契约层：
- **Pydantic 响应模型** — 42 个 Response 模型 + 12 个组件模型（`backend/api/schema.py`）
- **OpenAPI 自动文档** — FastAPI `response_model` 自动生成（访问 `/docs`）
- **TypeScript 类型** — 自动生成 `static/js/api-types.d.ts`
- **JSON Schema** — 自动生成 `godot/api-schema/` 供 Godot 参考
- **契约测试** — 8 个测试确保 Schema 完整性
- **CI 检查** — 自动验证 Schema 文件是否最新

---

## 工具脚本（tools/）

| 文件 | 作用 |
|------|------|
| `gen_ts_schema.py` | 从 Pydantic 模型生成 TypeScript 类型定义 |
| `gen_json_schema.py` | 从 Pydantic 模型生成 JSON Schema 文件 |
| `check_arch.py` | 架构检查 |
| `check_map.py` | 地图校验工具 |
| `diagnose_500.py` | 500 错误诊断 |
| `diagnose_talk.py` | 对话调试（观察 LLM 原始响应） |
| `gen_map.py` | 地图生成工具 |
| `show_maps.py` | 地图数据展示 |
| `smoke_api.py` | API 烟雾测试 |
| `verify_all.py` | 全量快速验证 |

---

## 测试体系

### 单元测试（tests/unit/）

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
| systems | `test_core.py`, `test_economy.py`, `test_npc_state.py`, `test_path.py`, `test_perception.py`, `test_save.py`, `test_time_weather.py`, `test_trap.py`, `test_world.py` 等 |
| config | `test_config.py` |

### 集成测试（tests/integration/）

| 文件 | 作用 |
|------|------|
| `test_api.py` | API 集成测试 |

### 交互测试（tests/interactive/）

| 文件 | 作用 |
|------|------|
| `test_dialogue_coherence.py` | 对话连贯性测试 |
| `test_emotional_response.py` | 情感响应测试 |
| `test_npc_personality.py` | NPC 个性一致性测试 |
| `test_world_knowledge.py` | 世界观知识测试 |

---

## 世界设定

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

### 五大势势

| 势力 | 代表人物 | 影响范围 |
|------|---------|---------|
| **衙门** | 雷三、钱卡吏 | 县城治安、税收 |
| **镖局** | 赵铁鹰 | 护运、保镖业务 |
| **漕帮** | 渔老七、薛驿卒 | 水运、码头 |
| **书院** | 慧尘知客 | 教育、舆论 |
| **绿林** | 剪径匪、暗流 | 山林、地下交易 |

---

## AI 系统详解

### NPC 认知架构

```
┌─────────────────────────────────────────┐
│              NPC Agent Brain            │
│                                         │
│  ┌───────────┐    ┌───────────┐         │
│  │ Observe   │    │ Reflect   │         │
│  │ (感知)     │───▶│ (反思)     │         │
│  │ • 环境    │    │ • 记忆提取 │         │
│  │ • 对话    │    │ • 洞察分析 │         │
│  │ • 事件    │    │ • 洞察生成 │         │
│  └───────────┘    └─────┬─────┘         │
│                        ▼               │
│  ┌───────────┐    ┌───────────┐         │
│  │ Plan      │◀───│ Memory    │         │
│  │ (计划)     │    │ (记忆)     │         │
│  │ • 日程规划 │    │ • 实体存储 │         │
│  │ • 目标设定 │    │ • 倒排索引 │         │
│  │ • 行动决策 │    │ • 向量检索 │         │
│  └───────────┘    └───────────┘         │
└─────────────────────────────────────────┘
```

### 记忆系统

- **存储格式**：实体-属性-值三元组
- **索引方式**：jieba 中文分词 + 倒排索引
- **检索策略**：向量相似度 + 时间衰减 + 重要性加权
- **容量限制**：每 NPC 最大 150 条记忆（自动淘汰旧记忆）

### 对话流程

```
用户输入 → talk_service.build_messages()
  ├─ 加载 NPC 人设 System Prompt
  ├─ 加载近期对话历史（最近 10 轮）
  ├─ 注入时间/天气/位置上下文
  └─ 注入相关记忆（检索 Top-K 条）
→ LLM Client.chat()
  ├─ 发送至 LLM API（OpenAI 兼容格式）
  ├─ Prompt Cache 命中率 ~80%
  └─ 熔断器保护（连续失败自动降级）
→ 解析 LLM 响应
  ├─ 成功 → 返回 visible_text + hidden_text
  └─ 失败 → Graceful Fallback（通用回复）
```

---

## 持久化流程

```
玩家开始 → SessionStore.get_or_create(pid)
         → 优先从 saves/<pid>.json 恢复，无则新建

游戏进行 → 每 5 分钟 autosave_all() → saves/<pid>.json
         → 手动 POST /api/save → saves/<pid>.json

游戏结束 → FastAPI shutdown hook → autosave_all() + httpx 连接池释放
```

---

## 技术指标

| 指标 | 数值 |
|------|------|
| 地图尺寸 | 150×100 = 15,000 格子 |
| NPC 数量 | 19 个（各有独立 AI） |
| API 端点数 | 44 个 |
| 测试用例数 | 1,320+ 个 |
| 代码总量 | ~15,000 行 Python + ~5,000 行 GDScript + ~3,000 行 JS |
| Prompt Cache 命中率 | ~80%（降低延迟 50%） |
| 平均对话延迟 | 2-5 秒（取决于 LLM） |
| 支持的 LLM | DeepSeek/Qwen/Ollama/任意 OpenAI 兼容 API |

---

## 代码质量工具

- **ruff** — Python 代码规范检查
- **pyright** — Python 类型检查（basic 模式）
- **pytest** — 1320+ 单元测试 + 8 个契约测试
- **CI** — GitHub Actions 自动运行测试 + Schema 检查

---

## 项目历史

| 日期 | 里程碑 |
|------|--------|
| **05-31** | API Schema 契约层建立 + 全项目交叉检查修复 |
| **05-28** | 测试中心 + 关闭服务 + 错误优化 + Godot 同步 |
| **05-27** | 代词消解动态化 + 记忆摘要情感增强 + 双前端架构合并 |
| **05-26** | 后端架构优化：连接池/熔断器/缓存/记忆索引/悬赏榜/Prompt 压缩 |
| **05-25** | 心境一致性记忆检索；夜间反思保护；复活清奴役终局 |
| **05-13** | 项目核心系统奠基：NPC 认知闭环/记忆演化/社交闲聊/际遇桥接 |
| **05-08** | 项目立项 |

> 完整迭代记录详见 [iterations/](iterations/)
