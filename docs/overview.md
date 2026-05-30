# Living Paper 迭代项目 — 概述

## 项目信息
- **源仓库**: https://github.com/ZaneWilliamsMiller/living-paper/tree/qclaw
- **配置日期**: 2026-05-27

## 架构

```
living-paper/
├── backend/           # Python FastAPI 后端
├── static/            # Web 前端 (由后端 serve)
├── godot/             # Godot 前端
├── third-party/       # 第三方依赖声明
├── tools/             # 工具脚本
├── tests/             # 自动化测试
├── docs/              # 文档与迭代记录
├── .env / .env.example
└── requirements.txt
```

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
