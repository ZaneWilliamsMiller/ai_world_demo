class_name MessageDisplay
## MessageDisplay — 活纸 · 江湖行纪 消息显示系统
## Chat / System Message Display with error highlighting
##
## 职责:
##   1. 向对话区域追加聊天消息 (玩家发言 / NPC 回复)
##   2. 显示系统消息 (居中、灰色)
##   3. 错误消息高亮 (红色背景 + 闪烁效果)
##   4. 自动滚动到底部
##
## 使用方式:
##   var msg := MessageDisplay.new()
##   msg.init(dialogue_label, chat_scroll)
##   msg.add_chat(color, speaker, body)        # 聊天消息
##   msg.add_system_msg(text)                   # 系统消息
##   msg.add_system_msg(text, true)             # 错误消息
##
## 依赖: GameColors (Autoload)

var _dialogue_label: RichTextLabel
var _chat_scroll: ScrollContainer
var _error_style_applied := false


## 初始化消息显示系统
## [param dialogue_label] 对话文本 RichTextLabel 节点
## [param chat_scroll] 包含对话的 ScrollContainer 节点
func init(dialogue_label: RichTextLabel, chat_scroll: ScrollContainer) -> void:
	_dialogue_label = dialogue_label
	_chat_scroll = chat_scroll


## 追加聊天消息到对话框
## [param color] 发言者颜色
## [param speaker] 发言者名称 (空则不显示前缀)
## [param body] 消息内容 (支持 BBCode)
func add_chat(color: Color, speaker: String, body: String) -> void:
	if not is_instance_valid(_dialogue_label): return
	var bb := ""
	if speaker != "":
		bb += "[b][color=#%s]%s[/color][/b]\n" % [color.to_html(false), speaker]
	bb += body.replace("[", "[lb]")
	_dialogue_label.append_text(bb + "\n\n")
	await get_tree().process_frame
	_scroll_to_bottom()


## 显示系统消息 (居中显示)
## [param text] 消息文本
func add_system_msg(text: String) -> void:
	add_chat(GameColors.DIM, "", "[center]%s[/center]" % text)


## 显示系统/错误消息（支持自动错误检测 + 高亮）
## [param text] 消息文本
## [param is_error] 是否强制标记为错误
func add_system_msg_ex(text: String, is_error: bool = false) -> void:
	if not _dialogue_label: return

	var prefix := ""
	var suffix := ""

	if is_error:
		prefix = "[bgcolor=#2a1515][color=#ffcccc]"
		suffix = "[/color][/bgcolor]"
		_error_style_applied = true
	elif text.begins_with("🚫") or text.begins_with("⚠️") or text.contains("移动被锁定") or text.contains("昏迷"):
		prefix = "[bgcolor=#2a1515][color=#ffcccc]"
		suffix = "[/color][/bgcolor]"
		_error_style_applied = true
	else:
		_error_style_applied = false

	_dialogue_label.append_text("\n%s%s%s" % [prefix, text, suffix])
	_scroll_to_bottom()

	if is_error or _error_style_applied:
		_dialogue_label.modulate = Color(1.2, 0.9, 0.9)
		await get_tree().create_timer(0.3).timeout
		_dialogue_label.modulate = Color.WHITE


## 将聊天区域滚动到底部
func _scroll_to_bottom() -> void:
	if not is_instance_valid(_chat_scroll): return
	await get_tree().process_frame
	_chat_scroll.get_v_scroll_bar().value = _chat_scroll.get_v_scroll_bar().max_value
