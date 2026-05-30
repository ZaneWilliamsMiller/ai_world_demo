# 🏮 活纸江湖 · Living Paper

> **AI-NPC 社会推演与开放叙事实验** —— 基于开源大模型 API 的文字 RPG

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![Godot](https://img.shields.io/badge/Godot-4.3+-blueviolet.svg)](https://godotengine.org)

---

## 快速开始

### 1. 克隆项目

```bash
git clone -b qclaw https://github.com/ZaneWilliamsMiller/living-paper.git
cd living-paper
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入你的 LLM API Key
```

必填项：
```env
LLM_BASE_URL=https://your-llm-api.example.com/v1
LLM_API_KEY=sk-your-api-key-here
LLM_MODEL=your-model-name
```

> 推荐模型：DeepSeek V3/V4、Qwen 系列、或任何兼容 OpenAI API 的模型

### 4. 启动

```bash
python start.py
```

浏览器访问 http://127.0.0.1:8765

**Godot 前端**：安装 [Godot 4.3+](https://godotengine.org/download)，打开 `godot/` 目录，按 F5 运行。

---

## 文档

| 文档 | 内容 |
|------|------|
| [项目文档](docs/overview.md) | 核心特色、架构、模块详解、世界设定、AI 系统、技术指标 |
| [迭代记录](docs/iterations/) | 开发历程与迭代产物归档 |

> 完整 API 文档可在启动后访问 http://127.0.0.1:8765/docs 查看（Swagger UI）
