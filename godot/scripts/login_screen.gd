extends Control
## Login screen — standalone Godot client.
## Creates character or loads save, then transitions to game scene.

const BG_DARK := Color(0.04, 0.04, 0.08)
const BG_PANEL := Color(0.09, 0.09, 0.16)
const TEXT := Color(0.97, 0.97, 1.0)
const DIM := Color(0.63, 0.63, 0.78)
const ACCENT_YELLOW := Color(0.92, 0.70, 0.03)
const ACCENT := ACCENT_YELLOW

var _name_input: LineEdit
var _gender_sel: OptionButton
var _pd_cb: CheckBox


func _ready() -> void:
	# Dark background
	var bg := ColorRect.new()
	bg.color = BG_DARK
	bg.set_anchors_preset(PRESET_FULL_RECT)
	add_child(bg)

	# Centered panel - 强制居中方式
	var box := Panel.new()
	box.custom_minimum_size = Vector2(360, 380)
	box.size = Vector2(360, 380)
	_add_panel_style(box)
	# 关键：手动计算居中位置
	var screen_size := get_viewport().get_visible_rect().size
	box.position = (screen_size - box.size) / 2.0
	add_child(box)

	var vb := VBoxContainer.new()
	vb.set_anchors_preset(PRESET_FULL_RECT)
	vb.add_theme_constant_override("separation", 12)
	box.add_child(vb)

	vb.add_child(_lbl("🏮 活纸 · 江湖行纪", 22, ACCENT, HORIZONTAL_ALIGNMENT_CENTER))
	vb.add_child(_lbl("Godot 独立版 — 后端 / LLM 直连双模式", 11, DIM, HORIZONTAL_ALIGNMENT_CENTER))

	# Name input
	var name_vb := VBoxContainer.new()
	name_vb.add_child(_lbl("江湖名号", 13, DIM))
	_name_input = LineEdit.new()
	_name_input.placeholder_text = "输入你的名号..."
	_name_input.max_length = 24
	_name_input.add_theme_font_size_override("font_size", 14)
	name_vb.add_child(_name_input)
	vb.add_child(name_vb)

	# Gender select
	var gs_vb := VBoxContainer.new()
	gs_vb.add_child(_lbl("性别", 13, DIM))
	_gender_sel = OptionButton.new()
	for g: String in ["男", "女", "不透露"]:
		_gender_sel.add_item(g)
	_gender_sel.add_theme_font_size_override("font_size", 14)
	gs_vb.add_child(_gender_sel)
	vb.add_child(gs_vb)

	# Permadeath checkbox
	_pd_cb = CheckBox.new()
	_pd_cb.text = " 真实江湖（永久死亡）"
	_pd_cb.add_theme_color_override("font_color", DIM)
	vb.add_child(_pd_cb)

	# Start button
	var start_btn := _btn("踏入江湖", ACCENT)
	start_btn.pressed.connect(_on_start)
	vb.add_child(start_btn)

	# API mode toggle
	var mode_btn := _btn("切换到 LLM 直连模式", Color(0.5, 0.5, 0.5))
	mode_btn.pressed.connect(_toggle_mode)
	vb.add_child(mode_btn)

	# Connection test
	var test_btn := _btn("测试连接", Color(0.4, 0.5, 0.6))
	test_btn.pressed.connect(_test_connection)
	vb.add_child(test_btn)


func _on_start() -> void:
	var nm: String = _name_input.text.strip_edges()
	if nm == "":
		nm = "江湖客"
	var g: String = "未言"
	var sel: int = _gender_sel.get_selected_id()
	if sel >= 0 and sel <= 2:
		g = ["男", "女", "未言"][sel]
	
	# 禁用按钮防止重复点击
	var start_btn: Button = get_node_or_null("")  # 找不到就跳过
	
	# 先等待 hello 完成，再切换场景！
	await GameManager.hello(nm, g, _pd_cb.button_pressed)
	get_tree().change_scene_to_file("res://scenes/game.tscn")


func _toggle_mode() -> void:
	if ApiClient.api_mode == "backend":
		ApiClient.api_mode = "direct"
		system_message("已切换到 LLM 直连模式")
	else:
		ApiClient.api_mode = "backend"
		system_message("已切换到后端模式")


func _test_connection() -> void:
	var backend_ok: bool = await ApiClient.test_backend()
	var llm_ok: bool = await ApiClient.test_llm()
	var msg: String = "后端: %s | LLM: %s" % [
		"OK" if backend_ok else "FAIL",
		"OK" if llm_ok else "FAIL"
	]
	system_message(msg)


func system_message(text: String) -> void:
	print("[Login] %s" % text)


func _lbl(text: String, size: int, color: Color, align := HORIZONTAL_ALIGNMENT_LEFT) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_color_override("font_color", color)
	l.add_theme_font_size_override("font_size", size)
	l.horizontal_alignment = align
	return l


func _btn(text: String, bg: Color) -> Button:
	var b := Button.new()
	b.text = text
	b.add_theme_font_size_override("font_size", 13)
	var sb := StyleBoxFlat.new()
	sb.bg_color = bg
	sb.corner_radius_top_left = 4
	sb.corner_radius_top_right = 4
	sb.corner_radius_bottom_left = 4
	sb.corner_radius_bottom_right = 4
	sb.content_margin_left = 14
	sb.content_margin_right = 14
	sb.content_margin_top = 6
	sb.content_margin_bottom = 6
	b.add_theme_stylebox_override("normal", sb)
	return b


func _add_panel_style(p: Panel) -> void:
	var sb := StyleBoxFlat.new()
	sb.bg_color = BG_PANEL
	sb.set_corner_radius_all(6)
	sb.border_width_left = 1
	sb.border_width_right = 1
	sb.border_width_top = 1
	sb.border_width_bottom = 1
	sb.border_color = Color(0.20, 0.24, 0.38)
	sb.content_margin_left = 12
	sb.content_margin_right = 12
	sb.content_margin_top = 8
	sb.content_margin_bottom = 8
	p.add_theme_stylebox_override("panel", sb)
