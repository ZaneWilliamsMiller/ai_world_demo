# 第三方依赖声明

> 本文件记录活纸 · 江湖行纪项目使用的所有第三方依赖及其许可证信息。
> 最后更新：2026-05-27

## Python 后端依赖

| 包名 | 版本 | 许可证 | 用途 |
|------|------|--------|------|
| [FastAPI](https://github.com/fastapi/fastapi) | 0.115.6 | MIT | Web 框架，路由与异步 API |
| [Uvicorn](https://github.com/encode/uvicorn) | 0.32.1 | BSD-3-Clause | ASGI 服务器，含 standard 扩展 |
| [httpx](https://github.com/encode/httpx) | 0.28.1 | BSD-3-Clause | 异步 HTTP 客户端，LLM API 调用与连接池 |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | 1.0.1 | BSD-3-Clause | .env 环境变量加载 |
| [Pydantic](https://github.com/pydantic/pydantic) | 2.10.3 | MIT | 数据模型校验与序列化 |
| [pydantic-settings](https://github.com/pydantic/pydantic-settings) | 2.6.1 | MIT | Settings 配置管理（BaseSettings） |
| [jieba](https://github.com/fxsjy/jieba) | >=0.42.1 | MIT | 中文分词，记忆检索倒排索引 |

## 前端依赖

本项目 Web 前端（`static/`）和 Godot 前端（`godot/`）均为纯原生实现，**不依赖任何第三方 JS/CSS 框架或 GDScript 插件**。

- Web 前端：原生 HTML5 + CSS3 + Vanilla JS，无 npm/CDN 依赖
- Godot 前端：Godot 4.3 原生 GDScript 2.0，无外部插件

## LLM 服务

本项目通过 OpenAI 兼容 API 调用大语言模型，不包含模型权重或本地推理引擎。

| 服务 | 说明 |
|------|------|
| [DeepSeek](https://platform.deepseek.com/) | 推荐 LLM 提供商（DeepSeek-V3 / DeepSeek-V4-Pro） |
| [Paratera](https://llmapi.paratera.com/) | LLM API 代理（OpenAI 兼容接口） |
| [Ollama](https://ollama.ai/) | 本地 LLM 运行时（可选，支持离线部署） |

## 许可证归档

各依赖的完整许可证文本可通过其官方仓库获取。本项目自身遵循上游仓库的许可证约定。

---

## 致谢

- **斯坦福 Generative Agents**：NPC 认知架构（observation → reflection → plan）的设计灵感来源
- **FastAPI** 及其生态：高效异步 Web 框架
- **jieba**：优秀的中文分词库
