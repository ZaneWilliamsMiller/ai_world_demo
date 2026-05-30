# 活纸江湖 · Godot GDScript 交叉检查修复报告

## 时间
2026-05-28 下午

## 修复概览
基于交叉检查报告，共修复 11 个问题（HIGH 4个 + MEDIUM 7个），另有 LOW 5个。

---

## 🔴 HIGH 修复 (4个)

### #1 — 启动场景指向不存在的 login.tscn
**文件**: `godot/project.godot`
**问题**: `run/main_scene="res://scenes/login.tscn"`，但游戏入口应为主界面
**修复**: 改为 `run/main_scene="res://scenes/game.tscn"`（game.tscn 和 login.tscn 都已存在）

### #3/#8 — chat_message 信号语义混淆
**文件**: `godot/scripts/game_manager.gd`
**问题**: 信号声明 `npc_name`，但 emit 时传入 `npc_id`
**修复**: 将信号声明改为 `signal chat_message(speaker: String, message: String, npc_id: String)`

### #7 — npc_states 永远为空
**文件**: `godot/scripts/game_manager.gd`
**问题**: 从后端响应**顶层**取 `npc_states`，但后端实际在 `player` 对象内
**修复**: 改为 `npc_states = player_data.get("npc_states", {})`，从 `data.get("player", {})` 中提取

### #11 — /api/shutdown 缺少认证 header
**文件**: `godot/scripts/api_client.gd`
**问题**: 后端要求 `X-Shutdown-Secret` header，客户端不传
**修复**: `shutdown_backend()` 改为直接构造 HTTPRequest，手动追加 `X-Shutdown-Secret`（从环境变量读取）

---

## 🟡 MEDIUM 修复 (7个)

### #4 — talk_stream() 不支持 https://
**文件**: `godot/scripts/api_client.gd`
**问题**: 只解析 `http://`，`https://` 会被忽略导致连接失败
**修复**: 增加 `https://` 解析分支，设置 `use_tls = true`，`connect_to_host` 时传入 `TLSOptions.client()`

### #5 — _on_stream_done 部分接收后错误不显示
**文件**: `godot/scripts/main_game.gd`
**问题**: 只在 `_stream_text == ""` 时显示错误，部分接收后的错误被忽略
**修复**: 无论 `_stream_text` 是否为空，只要有 `data.has("error")` 就追加错误提示

### #12 — talk_stream() HTTPClient 未显式 close
**文件**: `godot/scripts/api_client.gd`
**问题**: 流结束后 HTTPClient 未关闭，资源泄露
**修复**: 在所有退出路径（正常结束、错误、各分支）都调用 `http.close()`

### #15 — login_screen.gd system_message() 仅打印到控制台
**文件**: `godot/scripts/login_screen.gd`
**问题**: `system_message()` 只 `print()` 不显示 UI，用户无法看到反馈
**修复**: 添加 `_system_label` Label 节点，`system_message()` 写入 label 并 3 秒后清除

### #14 — login_screen.gd 标记为废弃
**文件**: `godot/scripts/login_screen.gd`
**问题**: 独立登录界面与 main_game.gd 功能重复
**修复**: 文件头部加 `## ⚠ DEPRECATED` 注释；project.godot 已指向 game.tscn 作为唯一入口

### #18 — make_input() 通过索引访问子节点脆弱
**文件**: `godot/scripts/ui_builder.gd`
**问题**: `name_input.get_child(1)` 如果内部结构调整会崩溃
**修复**: 给 `LineEdit` 设置 `name = "InputField"`，改为 `name_input.get_node("InputField")`

### #22 — MessageDisplay.init() 无重复调用保护
**文件**: `godot/scripts/message_display.gd`
**问题**: 如果 `init()` 被调用两次，第二次会 free 已释放的节点
**修复**: 添加 `_initialized` 标志，函数入口检查并直接返回

---

## 🟢 LOW 修复 (5个)

### #2 — btn() 未设置 hover/pressed/disabled 样式
**文件**: `godot/scripts/ui_builder.gd`
**修复**: btn() 添加 hover（+15%亮度）、pressed（-15%亮度）、disabled（灰色）、focus（边框高亮）样式

### #6 — _update_npc_markers() 重复清除子节点
**文件**: `godot/scripts/map_renderer.gd`
**修复**: `_build_npc_markers()` 内部已清除，此处移除重复的 `queue_free()` 循环

### #19 — shutdown 失败分支无强制退出按钮
**文件**: `godot/scripts/shutdown_service.gd`
**修复**: 在后端关闭失败的 else 分支添加 `强制退出前端` 按钮

### #20 — _apply_config() 缺少输入验证
**文件**: `godot/scripts/config_panel.gd`
**修复**: 各字段增加非空检查，验证失败时标红输入框

### 未处理 — #9 talk_to_npc() 和 #10 fetch_state() 死代码
**决策**: 保留作为备用路径（如未来需要非流式对话或轮询模式）

### 未处理 — #17 _process() 每帧更新
**决策**: 地图较小，性能可接受；后续可优化为仅在 camera 移动时更新

---

## 未修改文件（确认无问题）
- `game_colors.gd` — 颜色常量，无问题
- `test_center.gd` — 信号/路径/异步均正确
- `dialog_manager.gd` — BBCode/信号/内存均正确
- `game_manager.gd talk_to_npc/fetch_state` — 保留作为备用

---

## API 路径一致性
全部 13 条路由检查通过，无路径不匹配。

## 关键后端字段解析
`/api/hello` 和 `/api/load` 响应中，`npc_states` 在 `player` 对象内，已修复 Godot 端的提取逻辑。