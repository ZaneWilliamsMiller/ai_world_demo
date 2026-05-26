# 活纸 · Living Paper

> 🎯 面向 AI-NPC 社会推演与开放叙事的创新 Demo，「基于开源大模型 API 的 AI 游戏」。

基于 LLM 的开放叙事文字游戏（MUD-like），玩家在 **单一 72×48 网格世界**中行走、与 **19 个 NPC** 自然语言互动。世界随时间辰（时辰制）与天气持续演化，**每个 NPC 拥有独立记忆、反思与日程规划能力**，形成去中心化的社会推演系统。

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
| NPC | 19 | 风闻子、沈掌柜、金算计、雷三、赵铁鹰、柳无眉、剪径匪、暗流、渔老七、阿泠、周里正、薛驿卒、慧尘知客、沙掌盘、陆文潜、钱卡吏、玄真子、铁彀、金满堂 |
| 势力 | 5 | 衙门、镖局、漕帮、书院、绿林 |

## 技术栈

- 后端：`FastAPI` + `httpx` 异步 HTTP（连接池复用、熔断器、LLM 缓存、智能重试）
- Web 前端：单文件 SPA（CSS Grid 地图 + SSE 流式对话）
- Godot 桌面端：Godot 4.3 原生客户端（Autoload 单例架构）
- LLM：OpenAI 兼容 API（DeepSeek、Qwen、本地 Ollama 等均可）
- 持久化：JSON 文件存档（三层防护：定期自动存档 + 关闭自动存档 + 手动存档）

## 快速开始

```bash
cd living-paper
python -m pip install -r requirements.txt
cp .env.example .env   # 编辑 .env，填入 LLM API Key
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8766
```

浏览器访问 [http://127.0.0.1:8766](http://127.0.0.1:8766)（Web 前端）。

Godot 桌面端：用 Godot 4.3+ 打开 `godot/project.godot` → F5 运行。

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

详见 [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md) 完整项目结构文档。

### 后端 `backend/`

| 路径 | 说明 |
|------|------|
| `app.py` | FastAPI 应用入口，挂载静态文件、注册路由、自动存档、优雅关闭 |
| `config.py` | 配置读取（`.env` → `Settings`），含 LLM/连接池/熔断/缓存/Prompt Cache 开关 |
| `llm_client.py` | LLM 调用封装（chat_completion、连接池复用、并发限速、Prompt Cache 双模式） |
| `circuit_breaker.py` | LLM 熔断器（故障窗口阈值触发 → 冷却期降级） |
| `llm_cache.py` | LLM 响应缓存（TTL 过期 + LRU 淘汰） |
| `memory.py` | NPC 记忆存储（观察/反思/计划/种子/情感锚/A-Mem 顿悟演化） |
| `memory_index.py` | 倒排索引加速记忆检索（500 条 ~0.9ms） |
| `agent_brain.py` | NPC 认知闭环（观察提取/反思生成/计划生成/搜索/多智能体交叉反思） |
| `game_state.py` | 游戏全局状态 |
| `api/routes.py` | 所有 HTTP 端点（23 个，含悬赏榜 5 个） |
| `data/` | 静态数据（NPC/地图/势力/提示词/氛围/关系） |
| `models/` | 领域数据模型（PlayerState/NPC/LLM Schema） |
| `services/` | 业务编排层（对话服务/NPC 智能体） |
| `session/` | 会话存储（内存管理 + saves/ 恢复） |
| `systems/` | 核心玩法系统（寻路/时辰/核心逻辑/经济/际遇/八卦/声望/存档/悬赏榜/Prompt 压缩） |

### 前端

| 路径 | 说明 |
|------|------|
| `static/index.html` | Web 前端 — 25KB 单文件 SPA（CSS Grid 地图 + SSE 打字机流式对话 + HUD 面板） |
| `godot/` | Godot 桌面端 — Godot 4.3 项目（程序化 UI + Autoload 单例 + 全 API 封装） |

### 其他

| 路径 | 说明 |
|------|------|
| `tools/` | 辅助工具（地图生成/校验/验证/调试/API 测试） |
| `tests/` | 自动化测试（E2E/边界/综合/单元，31+23+23 项） |
| `docs/` | 文档与迭代记录 |
| `docs/iterations/` | 每日 CI 迭代产物归档 |
| `saves/` | 角色存档（运行时生成，JSON 格式） |

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
| GET | `/api/bounty/{player_id}` | 悬赏榜列表 |
| POST | `/api/bounty/accept` | 接受悬赏 |
| POST | `/api/bounty/complete` | 完成悬赏 |
| POST | `/api/bounty/abandon` | 放弃悬赏 |
| POST | `/api/rest` | 休息/回复 |

## 项目历史（精选）

近期关键迭代：

| 日期 | 主题 |
|------|------|
| 05-27 | 双前端架构（Web SPA + Godot 桌面端）+ 持久化三层防护 + 9 项 Bug 修复 |
| 05-27 | 工具/测试文件归位 + 项目结构文档更新 |
| 05-26 | 后端架构优化：连接池/熔断器/缓存/记忆索引/悬赏榜/Prompt 压缩 |
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