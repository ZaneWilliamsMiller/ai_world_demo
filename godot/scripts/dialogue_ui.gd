extends Control
## 对话界面组件 — 支持 NPC 选择、消息输入、流式对话显示
## 信号驱动，不依赖 get_parent()

# ── 信号 ──
signal message_sent(npc_id: String, message: String)

# ── 颜色主题 ──
const TEXT: Color = Color(0.90, 0.90, 0.92)
const DIM: Color = Color(0.50, 0.52, 0.64)
const ACCENT: Color = Color(0.35, 0.78, 0.98)
const ACCENT2: Color = Color(1.0, 0.45, 0.28)
const BG_PANEL: Color = Color(0.09, 0.11, 0.20)
const BORDER: Color = Color(0.20, 0.24, 0.38)

# ── 节点引用 ──
var _chat_scroll: ScrollContainer
var _dialogue_label: RichTextLabel
var _npc_select: OptionButton
var _msg_input: LineEdit
var _send_btn: Button
var _is_streaming: bool = false


func _ready() -> void:
	_build_ui()

	# 连接 GameManager 信号
	GameManager.chat_message.connect(_on_chat_message)
	GameManager.system_message.connect(_on_system_message)

	# 连接流式信号
	ApiClient.stream_chunk.connect(_on_stream_chunk)
	ApiClient.stream_done.connect(_on_stream_done)


func _build_ui() -> void:
	# 主布局
	var vb: VBoxContainer = VBoxContainer.new()
	vb.set_anchors_preset(PRESET_FULL_RECT)
	vb.add_theme_constant_override("separation", 6)
	add_child(vb)

	# 聊天滚动区域
	_chat_scroll = ScrollContainer.new()
	_chat_scroll.size_flags_vertical = SIZE_EXPAND_FILL
	_chat_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	vb.add_child(_chat_scroll)

	_dialogue_label = RichTextLabel.new()
	_dialogue_label.bbcode_enabled = true
	_dialogue_label.fit_content = true
	_dialogue_label.selection_enabled = true
	_dialogue_label.size_flags_horizontal = SIZE_EXPAND
	_dialogue_label.scroll_following = false
	_dialogue_label.add_theme_font_size_override("normal_font_size", 13)
	_dialogue_label.add_theme_color_override("default_color", TEXT)
	_chat_scroll.add_child(_dialogue_label)

	# 输入栏
	var input_bar: HBoxContainer = HBoxContainer.new()
	input_bar.custom_minimum_size = Vector2(0, 36)
	input_bar.add_theme_constant_override("separation", 6)
	vb.add_child(input_bar)

	_npc_select = OptionButton.new()
	_npc_select.add_theme_font_size_override("font_size", 12)
	input_bar.add_child(_npc_select)

	_msg_input = LineEdit.new()
	_msg_input.placeholder_text = "对 TA 说些什么..."
	_msg_input.size_flags_horizontal = SIZE_EXPAND_FILL
	_msg_input.add_theme_font_size_override("font_size", 13)
	_msg_input.text_submitted.connect(func(_t: String) -> void:
		_on_send()
	)
	input_bar.add_child(_msg_input)

	_send_btn = Button.new()
	_send_btn.text = "发送"
	_send_btn.add_theme_font_size_override("font_size", 13)
	var sb: StyleBoxFlat = StyleBoxFlat.new()
	sb.bg_color = ACCENT
	sb.set_corner_radius_all(4)
	sb.content_margin_left = 14
	sb.content_margin_right = 14
	sb.content_margin_top = 6
	sb.content_margin_bottom = 6
	_send_btn.add_theme_stylebox_override("normal", sb)
	_send_btn.pressed.connect(_on_send)
	input_bar.add_child(_send_btn)


func _on_send() -> void:
	if _is_streaming:
		return
	var text: String = _msg_input.text.strip_edges()
	if text == "":
		return

	var idx: int = _npc_select.selected
	if idx < 0:
		return
	var npcs: Array = GameManager.npcs_here
	if idx >= npcs.size():
		return

	var npc_id: String = npcs[idx].get("id", "")
	var npc_name: String = npcs[idx].get("name", npc_id)

	_add_chat(TEXT, "你", "[right]%s[/right]" % text)
	_msg_input.clear()
	_is_streaming = true
	_send_btn.disabled = true

	# 发送信号给主游戏场景处理
	message_sent.emit(npc_id, text)


func _on_chat_message(speaker: String, message: String, _npc_id: String) -> void:
	_add_chat(ACCENT2, speaker, message)


func _on_system_message(text: String) -> void:
	_add_chat(DIM, "", "[center]%s[/center]" % text)


func _on_stream_chunk(_chunk: String) -> void:
	# 流式输出在 stream_done 后统一更新
	pass


func _on_stream_done(_data: Dictionary) -> void:
	_is_streaming = false
	_send_btn.disabled = false
	_msg_input.grab_focus()


func _add_chat(color: Color, speaker: String, body: String) -> void:
	if not is_instance_valid(_dialogue_label):
		return
	var bb: String = ""
	if speaker != "":
		bb += "[b][color=#%s]%s[/color][/b]\n" % [color.to_html(false), speaker]
	bb += body.replace("[", "[lb]")
	_dialogue_label.append_text(bb + "\n\n")
	await get_tree().process_frame
	if is_instance_valid(_chat_scroll):
		_chat_scroll.get_v_scroll_bar().value = _chat_scroll.get_v_scroll_bar().max_value


func refresh_npc_select() -> void:
	var cur_idx: int = _npc_select.selected
	_npc_select.clear()
	for n: Dictionary in GameManager.npcs_here:
		_npc_select.add_item(n.get("name", n.get("id", "?")))
	if cur_idx >= 0 and cur_idx < _npc_select.item_count:
		_npc_select.select(cur_idx)


func select_npc_by_name(npc_name: String) -> void:
	for idx: int in _npc_select.item_count:
		if _npc_select.get_item_text(idx) == npc_name:
			_npc_select.select(idx)
			_msg_input.grab_focus()
			return


func set_streaming(streaming: bool) -> void:
	_is_streaming = streaming
	_send_btn.disabled = streaming
