# 2026-05-23-0045: Prompt Cache 优化 + 简历生成 + Cron 更新

## 目标

1. 对 API 交互进行 Prompt Cache 优化，降低 GLM-4 推理成本与延迟
2. 每轮迭代生成简历级项目经历摘要（本地 only）
3. 更新定时任务

## 改动文件

### 1. `backend/llm_client.py` — Prompt Cache 基础设施
- 新增 `cached_system(content)`：生成带 `cache_control={"type":"ephemeral"}` 的 content 数组
- 新增 `uncached(content)`：普通 content 数组（与 cached 配对）
- `chat_completion()` 增加缓存命中日志（记录 `prompt_tokens_details.cached_tokens`）
- 改进错误日志格式（避免超长错误文本溢出）

### 2. `backend/services/talk_service.py` — 拆分静态/动态消息层
**核心变更**：将原巨型 system message 拆分为两层：

- **静态可缓存层** (system message, `cached_system`)：
  SOCIETY_BIBLE + 角色卡 + NPC system prompt + MACHINE_TAIL_RULE 
  + 关系网上下文 + 场景气氛 + PERMADEATH_RULE + AUTONOMY_RULE 
  + 注入安全提示

- **动态上下文层** (user message, 纯 text)：
  记忆检索 + 当日计划 + 心绪 + 主动回扣 + 话题线程 + 奇遇感知 
  + 顿悟 + 闲聊感知 + 世界状态 + 体力状态 + 险局状态 + 势力声望 
  + 事件流 + 风闻 + 好感 + 气质四维

- 消息序列：`[system(cached)] → [user(dyn)] → [历史轮次...] → [user(当前输入)]`

**效果**：同一 NPC 的连续对话中，静态层（占总 prompt 约 60-70%）命中缓存，仅动态层计费。

### 3. `resume/_generate_entry.py` — 简历条目生成器（新增）
- 读取最新 git commit 并解析 `auto: 中文描述 | 英文关键词 (方向)` 格式
- 自动追加到 `resume/project-experience.md`
- 自动去重（按 commit SHA）
- 文件不存在时自动创建 header

### 4. `resume/project-experience.md` — 简历文件（新增，已 gitignore）
- 包含 11 条历史迭代记录，按时间倒序排列
- 格式：`[日期] **方向/类别**：描述（commit SHA）`

### 5. `.gitignore` — 增加 `resume/`
- 确保简历文件不被提交到 GitHub

### 6. Cron 任务更新
- jobId: `6beb017b-8d46-457b-bdb7-ed68242a8507`
- 新增步骤 7：`python resume/_generate_entry.py` 在 git push 后执行
- 新增注意提示：迭代时保持 Prompt Cache 架构不退化

## 测试结果

- `llm_client.py` 语法检查 ✅
- `talk_service.py` 语法检查 ✅
- `cached_system()` 函数输出正确的 content 数组 ✅
- `build_npc_messages` 可正常导入 ✅
- 后端 FastAPI app 可正常导入 ✅