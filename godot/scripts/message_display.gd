class_name MessageDisplay
## MessageDisplay — 活纸 · 江湖行纪 消息显示系统
## Chat / System Message Display with error highlighting
##
## 职责:
##   1. 向对话区域追加聊天消息 (玩家发言 / NPC 回复)
##   2. 显示系统消息 (居中、灰色)
##   3. 错误消息高亮 (红色背景 + 闪烁效果)
##   4. 自动滚动到底部
##   5. 支持流式对话：按索引更新单条消息
##
## 使用方式:
##   var msg := MessageDisplay.new()
##   msg.init(dialogue_label, chat_scroll)
##   msg.add_chat(color, speaker, body)        # 聊天消息
##   msg.add_system_msg(text)                   # 系统消息
##   msg.add_system_msg(text, true)             # 错误消息
##   msg.update_msg(index, text)                # 流式更新指定消息
##   msg.msg_count()                            # 消息条数
##
## 依赖: GameColors (Autoload)

var _chat_scroll: ScrollContainer
var _messages: VBoxContainer
var _error_style_applied := false
var _initialized := false
var _max_messages: int = 200


func init(dialogue_label: RichTextLabel, chat_scroll: ScrollContainer) -> void:
	if _initialized:
		return
	_initialized = true
	_chat_scroll = chat_scroll
	_messages = VBoxContainer.new()
	_messages.add_theme_constant_override("separation", 4)
	_messages.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	if dialogue_label.get_parent():
		dialogue_label.get_parent().remove_child(dialogue_label)
	dialogue_label.queue_free()
	_chat_scroll.add_child(_messages)


func _create_msg_label() -> RichTextLabel:
	var label := RichTextLabel.new()
	label.bbcode_enabled = true
	label.fit_content = true
	label.selection_enabled = true
	label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	label.scroll_following = false
	label.add_theme_font_size_override("normal_font_size", 13)
	label.add_theme_color_override("default_color", Color(0.90, 0.90, 0.92))
	return label


func add_chat(color: Color, speaker: String, body: String) -> void:
	if not is_instance_valid(_messages): return
	_prune_messages()
	var label := _create_msg_label()
	var bb := ""
	if speaker != "":
		bb += "[b][color=#%s]%s[/color][/b]\n" % [color.to_html(false), speaker]
	bb += body.replace("[", "[lb]")
	label.bbcode_text = bb
	_messages.add_child(label)
	await get_tree().process_frame
	_scroll_to_bottom()


func add_system_msg(text: String) -> void:
	add_chat(GameColors.DIM, "", "[center]%s[/center]" % text)


func add_system_msg_ex(text: String, is_error: bool = false) -> void:
	if not is_instance_valid(_messages): return

	var label := _create_msg_label()
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

	label.bbcode_text = "%s%s%s" % [prefix, text, suffix]
	_messages.add_child(label)
	_scroll_to_bottom()

	if is_error or _error_style_applied:
		label.modulate = Color(1.2, 0.9, 0.9)
		await get_tree().create_timer(0.3).timeout
		label.modulate = Color.WHITE


func msg_count() -> int:
	if not is_instance_valid(_messages): return 0
	return _messages.get_child_count()


func update_msg(index: int, text: String) -> void:
	if not is_instance_valid(_messages): return
	if index < 0 or index >= _messages.get_child_count():
		return
	var label: RichTextLabel = _messages.get_child(index)
	if label:
		label.bbcode_text = text
		_scroll_to_bottom()


func _scroll_to_bottom() -> void:
	if not is_instance_valid(_chat_scroll): return
	await get_tree().process_frame
	_chat_scroll.get_v_scroll_bar().value = _chat_scroll.get_v_scroll_bar().max_value


func _prune_messages() -> void:
	if not is_instance_valid(_messages): return
	while _messages.get_child_count() >= _max_messages:
		var oldest: Node = _messages.get_child(0)
		oldest.queue_free()
