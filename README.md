# 活纸 · Living Paper

> 🎯 面向 AI-NPC 社会推演与开放叙事的创新 Demo，「基于开源大模型 API 的 AI 游戏」。

基于 LLM 的开放叙事文字游戏（MUD-like），玩家在 11 张地图的网格世界中行走、与 12 个 NPC 自然语言互动。世界随时间辰（时辰制）与天气持续演化，**每个 NPC 拥有独立记忆、反思与日程规划能力**，形成去中心化的社会推演系统。

## 核心创新

- **🧠 智能 NPC 大脑**：每个角色基于斯坦福小镇 Generative Agents 架构，拥有 `observation → reflection → plan` 认知闭环。NPC 会从对话中提取重要记忆、定期反思生成抽象洞察、并根据身份与反思自动规划每日行程。
- **🗺️ 网格地图世界**：11 张地图（县衙、野径、渡口、书院、寺庙等）通过界门（portal）连接，地形影响移动成本（Dijkstra 寻路）。
- **💬 自然语言驱动**：完全通过自由文本与 NPC 交互，对话结果影响制钱、背包、势力声望、风闻与全局事件。
- **⏳ 时辰推进系统**：采用中国传统 12 时辰制，日夜循环、天气变化，NPC 行为受时空上下文约束。
- **📜 江湖史册**：集中查看历史对话、风闻、事件与 NPC 心迹记录，形成可回溯的叙事档案。

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

| 路径 | 说明 |
|------|------|
| `backend/app.py` | FastAPI 应用入口 |
| `backend/api/` | HTTP 路由层 |
| `backend/services/` | 业务编排层（对话、智能体等） |
| `backend/systems/` | 核心系统（时间天气、寻路、经济、声望等） |
| `backend/data/` | 地图、NPC、势力与提示词等静态数据 |
| `backend/models/` | 领域数据模型 |
| `backend/session/` | 会话态存储与管理 |
| `backend/llm_client.py` | 模型调用封装 |
| `tools/` | 辅助工具（地图生成、校验等） |
| `tests/` | 自动化测试 |
| `docs/` | 文档与迭代记录 |
| `saves/` | 角色存档（运行时生成） |
| `static/index.html` | 前端页面入口 |
| `static/main.js` | 前端初始化与主流程 |
| `static/map.js` | 地图渲染与交互 |
| `static/ui/` | 侧栏、对话、史册等 UI 模块 |
| `static/game.css` | 全局样式 |

## 迭代记录

详见 [docs/iterations/](docs/iterations/)。
