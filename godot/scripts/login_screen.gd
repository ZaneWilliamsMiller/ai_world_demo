extends Control
## Login screen — standalone Godot client.
## Creates character or loads save, then transitions to game scene.

var _name_input: LineEdit
var _gender_sel: OptionButton
var _pd_cb: CheckBox


func _ready() -> void:
	var bg := ColorRect.new()
	bg.color = GameColors.BG_DARK
	bg.set_anchors_preset(PRESET_FULL_RECT)
	add_child(bg)

	var box := Panel.new()
	box.custom_minimum_size = Vector2(360, 380)
	box.size = Vector2(360, 380)
	UIBuilder.add_panel_style(box)
	var screen_size := get_viewport().get_visible_rect().size
	box.position = (screen_size - box.size) / 2.0
	add_child(box)

	var vb := VBoxContainer.new()
	vb.set_anchors_preset(PRESET_FULL_RECT)
	vb.add_theme_constant_override("separation", 12)
	box.add_child(vb)

	vb.add_child(UIBuilder.lbl("🏮 活纸 · 江湖行纪", 22, GameColors.ACCENT_YELLOW, HORIZONTAL_ALIGNMENT_CENTER))
	vb.add_child(UIBuilder.lbl("Godot 独立版 — 后端 / LLM 直连双模式", 11, GameColors.DIM, HORIZONTAL_ALIGNMENT_CENTER))

	var name_vb := VBoxContainer.new()
	name_vb.add_child(UIBuilder.lbl("江湖名号", 13, GameColors.DIM))
	_name_input = LineEdit.new()
	_name_input.placeholder_text = "输入你的名号..."
	_name_input.max_length = 24
	_name_input.add_theme_font_size_override("font_size", 14)
	name_vb.add_child(_name_input)
	vb.add_child(name_vb)

	var gs_vb := VBoxContainer.new()
	gs_vb.add_child(UIBuilder.lbl("性别", 13, GameColors.DIM))
	_gender_sel = OptionButton.new()
	for g: String in ["男", "女", "不透露"]:
		_gender_sel.add_item(g)
	_gender_sel.add_theme_font_size_override("font_size", 14)
	gs_vb.add_child(_gender_sel)
	vb.add_child(gs_vb)

	_pd_cb = CheckBox.new()
	_pd_cb.text = " 真实江湖（永久死亡）"
	_pd_cb.add_theme_color_override("font_color", GameColors.DIM)
	vb.add_child(_pd_cb)

	var start_btn := UIBuilder.btn("踏入江湖", GameColors.ACCENT_YELLOW)
	start_btn.pressed.connect(_on_start)
	vb.add_child(start_btn)

	var mode_btn := UIBuilder.btn("切换到 LLM 直连模式", Color(0.5, 0.5, 0.5))
	mode_btn.pressed.connect(_toggle_mode)
	vb.add_child(mode_btn)

	var test_btn := UIBuilder.btn("测试连接", Color(0.4, 0.5, 0.6))
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

	await GameManager.hello(nm, g, _pd_cb.button_pressed)
	if GameManager.player_id == "":
		return
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
