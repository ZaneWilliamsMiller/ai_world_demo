# 2026-05-23 02:25 — API Key 配置 & 行走/对话 Bug 修复

## 任务目标
解决前端每次点击地图都弹出 Internal Server Error 的问题。

## 问题排查

### 根因 1：LLM API Key 失效（Internal Server Error）
- 旧 `.env` 使用智谱 API (`open.bigmodel.cn`) + Key `4918df...`
- 该 Key 返回 401 Unauthorized，导致所有 LLM 调用（NPC 对话等）全部 500
- 用户提供了新 Key `sk-o5exptybwJAro8OfIqqmjQ` 和大模型列表
- 经过 30+ 个 API 平台尝试（智谱、SiliconFlow、DeepSeek、DashScope、MiniMax、百川、PPIO、OpenAI Proxy、gptgod 等），最终确定 base URL 为 `https://ai.paratera.com/v1`

### 根因 2：core.py 中 `any()` 误用（Move 500）
- `backend/systems/core.py` 第 435 行：
  ```python
  in_active = any(
      val_in_range(sh_raw, a0, a1) if a0 <= a1 else
      (sh_raw >= a0 or sh_raw <= a1 % 24)
  )
  ```
- `any()` 需要一个 iterable，但传入的是单个布尔值 → `TypeError: 'bool' object is not iterable`
- 修复：去掉 `any()` 直接赋布尔值

## 修复内容

### 1. `.env` 更新
```
LLM_BASE_URL=https://ai.paratera.com/v1
LLM_API_KEY=sk-o5exptybwJAro8OfIqqmjQ
LLM_MODEL=DeepSeek-V4-Pro
```

### 2. `backend/systems/core.py` 第 435 行
- 去掉 `any()` 包装，直接使用三元表达式结果

## 验证结果
- ✅ `/api/hello` — 正常初始化玩家
- ✅ `/api/move` — 行走成功（px=4, py=3）
- ✅ `/api/npc/talk` — NPC 对话正常（风闻子返回了完整的江湖对话）
- ✅ 前端 `data.reply` 与后端 `"reply": visible` 格式匹配

## 服务器状态
- 进程：`python -m uvicorn backend.app:app --host 127.0.0.1 --port 8765`
- 访问：http://127.0.0.1:8765