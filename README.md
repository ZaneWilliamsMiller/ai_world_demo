# 活纸 · Living Paper

> AI-NPC 社会推演与开放叙事实验 —— 基于开源大模型 API 的文字 RPG。

基于 LLM 的开放叙事文字游戏（MUD-like），玩家在 **单一 72×48 网格世界**中行走、与 **19 个 NPC** 自然语言互动。世界随时辰与天气持续演化，**每个 NPC 拥有独立记忆、反思与日程规划能力**，形成去中心化的社会推演系统。

## 核心创新

- **智能 NPC 大脑**：每个角色基于斯坦福 Generative Agents 架构，拥有 `observation → reflection → plan` 认知闭环。NPC 从对话中提取重要记忆、定期反思生成抽象洞察、根据身份与反思自动规划行程。
- **单一江湖地图**：72×48 统一大地图「青石江湖·万里图」，河道自西北流向东南，裂隙与废墟散布险地。
- **自然语言驱动**：完全通过自由文本与 NPC 交互，对话结果影响制钱、背包、势力声望、风闻与全局事件。
- **时辰推进系统**：中国传统 12 时辰制，日夜循环、天气变化，NPC 行为受时空上下文约束。
- **江湖史册**：集中查看历史对话、风闻、事件与 NPC 心迹记录，形成可回溯的叙事档案。
- **真实江湖模式**：部分 NPC/地形可导致 permadeath（真死），增加沉浸感。

## 世界数据

| 类型 | 数量 | 详情 |
|------|------|------|
| 地图 | 1 | 72×48 统一大地图「青石江湖·万里图」 |
| NPC | 19 | 风闻子、沈掌柜、金算计、雷三、赵铁鹰、柳无眉、剪径匪、暗流、渔老七、阿泠、周里正、薛驿卒、慧尘知客、沙掌盘、陆文潜、钱卡吏、玄真子、铁彀、金满堂 |
| 势力 | 5 | 衙门、镖局、漕帮、书院、绿林 |

## 技术栈

- **后端**：FastAPI + httpx 异步 HTTP（连接池复用、熔断器、LLM 缓存、智能重试、Prompt Cache）
- **Web 前端**：原生 SPA（CSS Grid 地图 + SSE 流式对话，无框架依赖）
- **Godot 桌面端**：Godot 4.3 原生客户端（GDScript 2.0 严格类型 + 信号驱动）
- **LLM**：OpenAI 兼容 API（DeepSeek、Qwen、本地 Ollama 等均可）
- **持久化**：JSON 文件存档（三层防护：定期自动存档 + 关闭自动存档 + 手动存档）
- **分词**：jieba 中文分词（记忆倒排索引）

## 快速开始

```bash
# 克隆项目
git clone -b qclaw git@github.com:ZaneWilliamsMiller/living-paper.git
cd living-paper

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入 LLM API Key 和模型名称

# 启动后端
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8765
```

浏览器访问 [http://127.0.0.1:8765](http://127.0.0.1:8765)（Web 前端由后端自动 serve）。

Godot 桌面端：用 Godot 4.3+ 打开 `godot/project.godot` → F5 运行。

## 环境配置

复制 `.env.example` 为 `.env`，填入 LLM API Key：

```bash
cp .env.example .env
# 编辑 .env，设置：
# LLM_BASE_URL=https://api.deepseek.com/v1
# LLM_API_KEY=你的 API 密钥
# LLM_MODEL=deepseek-chat
```

> 推荐使用 DeepSeek V3/V4 或兼容 OpenAI 的任意模型。详见 [third-party/THIRD_PARTY.md](third-party/THIRD_PARTY.md)。

## 目录结构

```
living-paper/
├── backend/              # Python 后端 (FastAPI 游戏引擎)
│   ├── api/              #   HTTP 路由 (23 个端点)
│   ├── data/             #   静态数据 (NPC/地图/势力/提示词)
│   ├── models/           #   领域模型 (Player/NPC/LLM Schema)
│   ├── services/         #   业务编排 (对话/NPC 智能体)
│   ├── session/          #   会话存储 + 存档恢复
│   └── systems/          #   核心玩法 (寻路/时辰/经济/际遇/八卦/声望/悬赏/Prompt 压缩)
├── static/               # Web 前端 (原生 SPA，双模式 API)
│   ├── css/              #   暗色江湖主题
│   └── js/               #   API/状态/地图/对话/入口
├── godot/                # Godot 桌面端 (GDScript 2.0)
│   ├── scenes/           #   登录 + 游戏场景
│   └── scripts/           #   API 客户端/状态/地图/对话
├── third-party/          # 第三方依赖声明与许可证
├── tools/                # 开发辅助脚本
├── tests/                # 自动化测试
├── docs/                 # 文档与迭代记录
│   └── iterations/       #   每日 CI 迭代产物归档
├── saves/                # 角色存档 (运行时生成, gitignore)
├── .env / .env.example   # 环境变量
├── requirements.txt      # Python 依赖
└── README.md             # 本文件
```

> 详见 [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md)。

## API 端点

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| POST | `/api/hello` | 创建/恢复角色 |
| POST | `/api/move` | 移动 |
| GET | `/api/state/{player_id}` | 玩家状态查询 |
| POST | `/api/npc/talk` | NPC 对话（非流式） |
| POST | `/api/npc/talk_stream` | NPC 对话（SSE 流式） |
| GET | `/api/agent/{pid}/{npc}/mind` | NPC 心迹查询 |
| POST | `/api/agent/reflect` | 手动触发 NPC 反思 |
| POST | `/api/agent/plan` | 手动触发 NPC 计划 |
| GET | `/api/saves` | 存档列表 |
| POST | `/api/save` | 手动存档 |
| POST | `/api/load` | 读档 |
| POST | `/api/delete-save` | 删档 |
| GET | `/api/journal/{player_id}` | 江湖史册 |
| POST | `/api/finale` | 终局判定 |
| GET | `/api/bounty/{player_id}` | 悬赏榜列表 |
| POST | `/api/bounty/accept` | 接受悬赏 |
| POST | `/api/bounty/bounty` | 完成悬赏 |
| POST | `/api/bounty/abandon` | 放弃悬赏 |
| POST | `/api/rest` | 休息/回复 |

## 前端双模式

两个前端均支持双 API 模式：

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| **后端模式**（默认） | 通过后端 API 通信，完整游戏系统 | 正常游戏 |
| **LLM 直连模式** | 直接调用 LLM API，跳过后端 | API 调试 |

Web 前端自动检测同源环境：后端 serve 时用相对路径 `/api`，独立打开时用完整 URL。

## 项目历史（精选）

| 日期 | 主题 |
|------|------|
| 05-27 | 代词消解动态化 + 记忆摘要情感增强 + 双前端架构合并 |
| 05-26 | 后端架构优化：连接池/熔断器/缓存/记忆索引/悬赏榜/Prompt 压缩 |
| 05-25 | 心境一致性记忆检索；夜间反思保护；复活清奴役终局 |
| 05-24 | 计划-观察偏差分析；反思情绪印迹回写；CMA 记忆凝结 |
| 05-23 | Prompt Cache 架构；存档系统；氛围注入；情感锚点 |
| 05-13 | 项目核心系统奠基：NPC 认知闭环/记忆演化/社交闲聊/际遇桥接 |
| 05-08 | 项目立项 |

完整迭代记录详见 [docs/iterations/](docs/iterations/)。

## 第三方依赖

详见 [third-party/THIRD_PARTY.md](third-party/THIRD_PARTY.md)。

## 许可证

本项目遵循上游仓库的许可证约定。第三方依赖的许可证详见 [third-party/THIRD_PARTY.md](third-party/THIRD_PARTY.md)。
