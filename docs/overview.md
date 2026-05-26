# Living Paper 迭代项目 — 概述

## 项目信息
- **源仓库**: https://github.com/ZaneWilliamsMiller/living-paper/tree/qclaw
- **本地路径**: D:\linving\repo
- **配置日期**: 2026-05-27

## 架构

```
D:\linving\repo\
├── backend/           # Python FastAPI 后端 (port 8765)
├── static/            # 原始 Web 前端 (由后端服务)
├── godot/             # 原始 Godot 前端
├── web-standalone/    # ★ 独立 Web 前端 (不依赖后端运行)
├── godot-standalone/  # ★ 独立 Godot 前端 (不依赖 Web)
├── tools/             # 工具脚本
│   ├── auto_test.py   # 自动化测试
│   ├── start.sh       # 启动脚本
│   └── test_reports/  # 测试报告
├── .env               # API 配置
└── requirements.txt   # Python 依赖
```

## API 配置
- **LLM API**: https://llmapi.paratera.com/v1
- **模型**: DeepSeek-V4-Pro
- **后端端口**: 8765

## 双前端架构
两个前端互不依赖，可独立运行：

### Web 前端 (web-standalone/)
- 双模式切换：后端模式 / LLM 直连模式
- API 配置面板（URL、Key、Model 可在界面修改）
- 连接测试面板
- 配置持久化到 localStorage

### Godot 前端 (godot-standalone/)
- 严格 GDScript 2.0 静态类型
- 信号驱动架构
- 双模式切换（后端 / LLM 直连）
- 连接测试脚本

## 自动化测试
- 测试脚本: `tools/auto_test.py`
- 8 项测试全部通过（2026-05-27）：
  1. 后端健康检查
  2. Web 静态页面
  3. LLM 模型列表
  4. LLM 直连 (DeepSeek-V4-Pro)
  5. 角色创建 (/api/hello)
  6. NPC 对话 (LLM 链路)
  7. 角色移动 (/api/move)
  8. 存档/读档

## 定时任务
- 每日 09:00 自动运行测试
- 自动启动后端 → 运行测试 → 修复问题 → 关闭后端 → 汇报结果

## 启动方式
```bash
# 后端
cd D:\linving\repo && python -m uvicorn backend.app:app --host 127.0.0.1 --port 8765

# Web 独立版（需要后端运行或切换到独立模式）
cd D:\linving\repo\web-standalone && python -m http.server 8080

# 自动化测试
python D:\linving\repo\tools\auto_test.py
```
