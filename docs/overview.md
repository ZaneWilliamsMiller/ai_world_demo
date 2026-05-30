# Living Paper 迭代项目 — 概述

## 项目信息
- **源仓库**: https://github.com/ZaneWilliamsMiller/living-paper/tree/qclaw
- **配置日期**: 2026-05-31

## 架构

```
living-paper/
├── backend/           # Python FastAPI 后端
│   ├── api/           # API 路由层（44 个端点 + Pydantic Schema 契约）
│   ├── agents/        # NPC 认知闭环（观察/反思/计划/行动）
│   ├── llm/           # LLM 客户端（连接池/熔断器/缓存/压缩）
│   ├── memory/        # 记忆系统（实体/格式/索引/检索）
│   ├── models/        # 领域模型（Player/NPC/LLM Schema）
│   ├── services/      # 业务编排（对话/智能体）
│   ├── systems/       # 游戏系统（核心/经济/遭遇/感知/寻路/声望/悬赏/陷阱/存档...）
│   ├── data/          # 静态数据（NPC/地图/阵营/氛围/关系/区域/提示词）
│   ├── session/       # 会话存储
│   └── observability/ # 可观测性（LLM 调用追踪）
├── static/            # Web 前端（原生 SPA + TypeScript 类型定义）
├── godot/             # Godot 前端（GDScript + API Schema 参考）
│   └── api-schema/    # JSON Schema 文件
├── third-party/       # 第三方依赖声明
├── tools/             # 工具脚本（含 Schema 生成）
├── tests/             # 自动化测试（1320+ 用例）
│   ├── unit/          # 单元测试
│   ├── integration/   # 集成测试
│   └── interactive/   # 交互测试
├── docs/              # 文档与迭代记录
├── .env / .env.example
└── requirements.txt
```

## API 契约层

项目建立了完整的 API Schema 契约层：
- **Pydantic 响应模型** — 42 个 Response 模型 + 12 个组件模型（`backend/api/schema.py`）
- **OpenAPI 自动文档** — FastAPI `response_model` 自动生成（访问 `/docs`）
- **TypeScript 类型** — 自动生成 `static/js/api-types.d.ts`
- **JSON Schema** — 自动生成 `godot/api-schema/` 供 Godot 参考
- **契约测试** — 8 个测试确保 Schema 完整性
- **CI 检查** — 自动验证 Schema 文件是否最新

## API 配置
- **LLM API**: 参见 .env.example
- **模型**: 参见 .env.example
- **后端端口**: 参见 .env.example

## 启动方式
```bash
# 一键启动（前后端同端口）
python start.py

# 后台启动
python start.py --bg

# 关闭服务
python start.py --stop
```

## 代码质量工具
- **ruff** — Python 代码规范检查
- **pyright** — Python 类型检查（basic 模式）
- **pytest** — 1320+ 单元测试 + 8 个契约测试
- **CI** — GitHub Actions 自动运行测试 + Schema 检查
