# 活纸江湖 (Living Paper) — AI Agent 上下文

## 项目概述

AI-NPC 社会推演与开放叙事实验，基于开源大模型 API 的文字 RPG。

## 技术栈

- 后端：Python FastAPI + Pydantic + asyncio
- Web 前端：纯 JS（无框架），Canvas 地图渲染，SSE 流式对话
- Godot 4 客户端：GDScript
- LLM：通过 chat_completion() 调用，支持超时保护和断路器

## 关键目录

- `backend/` — Python 后端（API路由、NPC认知、记忆系统、LLM调用层、可观测性、数据定义、领域模型、业务编排）
- `static/` — Web 前端（JS/CSS/HTML）
- `godot/` — Godot 4 客户端（GDScript）
- `tests/` — 自动化测试（1425+ 用例）
- `docs/` — 项目文档与迭代记录

## 架构文档

完整架构文档见 `docs/overview.md`（459 行）。

## 编码规范

- Python：ruff lint + pyright 类型检查，不添加注释
- 前端 JS：ESLint，不添加注释，使用 replaceChildren() 替代 innerHTML = ""
- 测试：pytest，使用 `tests/unit/conftest.make_player()` 工厂函数

## 常用命令

```bash
python -m pytest tests/unit/ -x --tb=short -q   # 运行单元测试
ruff check backend/                                # Python lint
pyright backend/                                   # 类型检查
npm run lint                                       # 前端 lint
python start.py                                    # 启动服务器
```

## 重要架构决策

- NPC 认知：Brain→Plan→Act→Reflect 循环
- 记忆系统：记忆流 + 检索 + 反思（斯坦福式）
- 悬赏系统：故事事件驱动（LLM 生成故事事件 → 派生悬赏）
- 世界演进：新建角色时 5 天 NPC 交互推演（70% 模板对话 + 30% LLM）
- 双前端架构：Web + Godot 共享同一后端 API
- NPC 总数：30 个（含 11 个 2026-05-31 新增）

---

## 迭代记录规范

**每次迭代完成后，必须在 `docs/iterations/` 目录下创建迭代记录文件。**

### 文件命名

`docs/iterations/YYYY-MM-DD_HHMM.md`

示例：`docs/iterations/2026-05-31_1430.md`

### 格式模板

```markdown
# 迭代记录 — YYYY-MM-DD HH:MM

## 概述
[一句话描述本次迭代的目标]

## 变更明细

| 文件 | 操作 | 说明 |
|---|---|---|
| `path/to/file.py` | 新建/修改/删除 | 具体变更内容 |

## 修复项

| ID | 严重程度 | 问题 | 修复方式 |
|---|---|---|---|
| C1 | 严重/中等/低 | 问题描述 | 修复方式 |

## 新增项

| ID | 模块 | 功能 | 说明 |
|---|---|---|---|
| F1 | 模块名 | 功能描述 | 详细说明 |

## 测试

| 指标 | 变更前 | 变更后 |
|---|---|---|
| 通过数 | — | — |
| 失败数 | — | — |

## 备注
[其他需要记录的信息]
```

### 填写要求

1. **概述**：一句话概括本次迭代的核心目标
2. **变更明细**：列出所有新建/修改/删除的文件，说明具体变更内容
3. **修复项**：列出所有 Bug 修复，按严重程度分类（严重/中等/低）
4. **新增项**：列出所有新增功能，标注所属模块
5. **测试**：记录测试通过数和失败数的变更前后对比
6. **备注**：架构决策、已知问题、后续计划等

### 迭代历史索引

详见 `docs/iterations/` 目录。关键迭代：

- 2026-05-25: 核心系统奠基（NPC认知、记忆系统、对话流程）
- 2026-05-26: 后端优化（缓存、并发、断路器）
- 2026-05-27: 悬赏系统重构（故事事件驱动）、UI修复、代词消解动态化
- 2026-05-28: Godot 交叉检查修复
- 2026-05-31: 世界演进功能、NPC扩充到30个、Bug修复、测试覆盖提升
