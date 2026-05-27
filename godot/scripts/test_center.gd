class_name TestCenter
## TestCenter — 活纸 · 江湖行纪 测试中心
## Test Center for running backend API tests
##
## 职责:
##   1. 构建测试中心弹窗 UI
##   2. 从后端加载可用测试列表
##   3. 执行单个测试并显示结果输出
##   4. 管理测试运行状态 (防止并发)
##
## 使用方式:
##   var tc := TestCenter.new()
##   tc.show(parent, on_system_msg_callback)
##
## 依赖: GameColors (Autoload), ApiClient (Autoload), UIBuilder

var _overlay: Control
var _test_list_container: VBoxContainer
var _current_running_test: String = ""
var _on_system_msg: Callable


## 显示测试中心弹窗
## [param parent] 父节点 (通常是根 Control)
## [param on_system_msg] 系统消息回调 Callable(text, is_error=false)
func show_test_center(parent: Control, on_system_msg: Callable) -> void:
	_on_system_msg = on_system_msg

	if _overlay and is_instance_valid(_overlay):
		_overlay.queue_free()
		return

	_overlay = UIBuilder.overlay(parent)
	var panel := Panel.new()
	panel.custom_minimum_size = Vector2(700, 550)
	panel.size = Vector2(700, 550)
	UIBuilder.add_panel_style(panel, Color(0.15, 0.1, 0.18), Color(0.9, 0.27, 0.37))
	_overlay.add_child(panel)
	_overlay.resized.connect(func():
		var ps: Vector2 = _overlay.size
		panel.position = (ps - Vector2(700, 550)) / 2.0
	)

	var main_vb := VBoxContainer.new()
	main_vb.add_theme_constant_override("separation", 10)
	main_vb.set_anchors_preset(PRESET_FULL_RECT)
	main_vb.offset_left = 20; main_vb.offset_top = 20; main_vb.offset_right = -20; main_vb.offset_bottom = -20
	panel.add_child(main_vb)

	# Title bar
	var title_hb := HBoxContainer.new()
	title_hb.add_child(UIBuilder.lbl("🧪 测试中心", 20, GameColors.ACCENT_RED))
	var close_btn := UIBuilder.btn("✕", GameColors.ACCENT_RED)
	close_btn.pressed.connect(func(): _overlay.queue_free())
	title_hb.add_child(Control.new())
	title_hb.add_child(close_btn)
	main_vb.add_child(title_hb)

	# Stats bar
	var stats_hb := HBoxContainer.new()
	stats_hb.add_theme_constant_override("separation", 16)
	stats_hb.alignment = HORIZONTAL_ALIGNMENT_CENTER
	stats_hb.add_child(UIBuilder.lbl("可用测试: --", 14, GameColors.TEXT))
	stats_hb.add_child(UIBuilder.lbl("运行中: 0", 14, GameColors.ACCENT_YELLOW))
	stats_hb.add_child(UIBuilder.lbl("成功: 0", 14, GameColors.ACCENT_GREEN))
	stats_hb.add_child(UIBuilder.lbl("失败: 0", 14, GameColors.ACCENT_RED))
	main_vb.add_child(stats_hb)

	# Separator
	var sep := HSeparator.new()
	sep.modulate = Color(0.3, 0.3, 0.4)
	main_vb.add_child(sep)

	# Scrollable test list
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = SIZE_EXPAND
	main_vb.add_child(scroll)

	_test_list_container = VBoxContainer.new()
	_test_list_container.add_theme_constant_override("separation", 8)
	scroll.add_child(_test_list_container)

	_load_test_list(stats_hb)


## 从后端加载测试列表并渲染
## [param stats_hb] 统计栏 HBoxContainer，用于更新计数
func _load_test_list(stats_hb: HBoxContainer) -> void:
	for child in _test_list_container.get_children():
		child.queue_free()

	var result: Dictionary = await ApiClient.list_tests()
	var tests: Array = result.get("tests", [])
	var count: int = result.get("count", 0)

	if stats_hb.get_child_count() >= 4:
		stats_hb.get_child(0).text = "可用测试: %d" % count

	if tests.is_empty():
		_test_list_container.add_child(UIBuilder.lbl("⚠️ 无法连接后端或没有可用测试", 14, GameColors.DIM))
		return

	for test_data in tests:
		var test_name: String = test_data.get("name", "")
		var test_desc: String = test_data.get("description", "")

		var card := Panel.new()
		card.custom_minimum_size = Vector2(0, 70)
		UIBuilder.add_panel_style(card, Color(0.12, 0.1, 0.15), Color(0.25, 0.2, 0.3))

		var card_vb := VBoxContainer.new()
		card_vb.add_theme_constant_override("separation", 4)
		card_vb.set_anchors_preset(PRESET_FULL_RECT)
		card_vb.offset_left = 12; card_vb.offset_top = 8; card_vb.offset_right = -12; card_vb.offset_bottom = -8
		card.add_child(card_vb)

		# Header row
		var header_hb := HBoxContainer.new()
		header_hb.add_child(UIBuilder.lbl("📋 %s" % test_name, 14, GameColors.TEXT))
		var run_btn := UIBuilder.btn("▶ 运行", GameColors.ACCENT_RED)
		run_btn.pressed.connect(_run_test.bind(test_name, card_vb))
		header_hb.add_child(Control.new())
		header_hb.add_child(run_btn)
		card_vb.add_child(header_hb)

		# Description
		card_vb.add_child(UIBuilder.lbl(test_desc, 11, GameColors.DIM))

		# Output area (initially hidden)
		var output_box := RichTextLabel.new()
		output_box.name = "output_box"
		output_box.bbcode_enabled = true
		output_box.fit_content = true
		output_box.custom_minimum_size = Vector2(0, 80)
		output_box.scroll_active = true
		output_box.visible = false
		output_box.add_theme_font_size_override("normal_font_size", 11)
		output_box.add_theme_color_override("default_color", Color(0.8, 0.8, 0.85))
		var output_bg := StyleBoxFlat.new()
		output_bg.bg_color = Color(0.08, 0.06, 0.1)
		output_bg.border_width_left = 1; output_bg.border_width_right = 1
		output_bg.border_width_top = 1; output_bg.border_width_bottom = 1
		output_bg.border_color = Color(0.15, 0.15, 0.2)
		output_box.add_theme_stylebox_override("normal", output_bg)
		card_vb.add_child(output_box)

		_test_list_container.add_child(card)


## 执行单个测试
## [param test_name] 测试名称
## [param card_vb] 测试卡片的内容容器 (用于显示输出)
func _run_test(test_name: String, card_vb: VBoxContainer) -> void:
	if _current_running_test != "":
		if _on_system_msg.is_valid():
			_on_system_msg.call("⚠️ 请等待当前测试完成", true)
		return

	_current_running_test = test_name

	# Find output box and show it
	var output_box: RichTextLabel = null
	for child in card_vb.get_children():
		if child.name == "output_box":
			output_box = child
			output_box.visible = true
			output_box.text = "[color=yellow]⏳ 正在执行测试: %s...[/color]" % test_name
			break

	# Disable all run buttons
	_set_run_buttons_disabled(true)

	var result: Dictionary = await ApiClient.run_test(test_name)

	# Re-enable buttons
	_set_run_buttons_disabled(false)

	# Show result
	if output_box:
		var success: bool = result.get("success", false)
		var output: String = result.get("output", "").strip_edges()
		var exit_code = result.get("exit_code")

		if success:
			output_box.text = "[color=green]✅ 测试成功[/color]\n\n[color=white]%s[/color]" % output
		else:
			var exit_str = "" if exit_code == null else " [退出码: %s]" % str(exit_code)
			output_box.text = "[color=red]❌ 测试失败%s[/color]\n\n[color=white]%s[/color]" % [exit_str, output]

	_current_running_test = ""


## 设置所有运行按钮的禁用状态
## [param disabled] 是否禁用
func _set_run_buttons_disabled(disabled: bool) -> void:
	for card in _test_list_container.get_children():
		for child in card.get_children():
			if child is VBoxContainer:
				for sub in child.get_children():
					if sub is HBoxContainer:
						for btn in sub.get_children():
							if btn is Button and btn.text.begins_with("▶"):
								btn.disabled = disabled
