class_name ConfigPanel
## ConfigPanel — 活纸 · 江湖行纪 API 配置面板
## API Configuration Panel for backend/LLM settings
##
## 职责:
##   1. 构建配置面板 UI (API 模式、后端地址、LLM 配置)
##   2. 填充/读取当前配置值
##   3. 应用配置到 ApiClient
##   4. 执行后端/LLM 连接测试
##   5. 更新 API 模式指示器
##
## 使用方式:
##   var config := ConfigPanel.new()
##   config.build(parent, on_indicator_update_callback)
##   config.toggle()
##
## 依赖: GameColors (Autoload), ApiClient (Autoload), UIBuilder

var _overlay: Control
var _panel: Control
var _cfg_api_mode: OptionButton
var _cfg_backend_url: LineEdit
var _cfg_llm_url: LineEdit
var _cfg_llm_key: LineEdit
var _cfg_llm_model: LineEdit
var _backend_test_result: Label
var _llm_test_result: Label
var _on_indicator_updated: Callable


## 构建配置面板
## [param parent] 父节点 (通常是根 Control)
## [param on_indicator_updated] API模式指示器更新回调 Callable(new_text, new_color)
func build(parent: Control, on_indicator_updated: Callable) -> void:
	_on_indicator_updated = on_indicator_updated

	_overlay = Control.new()
	_overlay.set_anchors_preset(PRESET_FULL_RECT)
	_overlay.visible = false

	var overlay_bg := ColorRect.new()
	overlay_bg.color = Color(0,0,0,0.75)
	overlay_bg.set_anchors_preset(PRESET_FULL_RECT)
	overlay_bg.mouse_filter = Control.MOUSE_FILTER_STOP
	_overlay.add_child(overlay_bg)

	var panel_container := CenterContainer.new()
	panel_container.set_anchors_preset(PRESET_FULL_RECT)
	_overlay.add_child(panel_container)

	_panel = Panel.new()
	_panel.custom_minimum_size = Vector2(400, 500)
	UIBuilder.add_panel_style(_panel)
	panel_container.add_child(_panel)

	var vb := VBoxContainer.new()
	vb.set_anchors_preset(PRESET_FULL_RECT)
	vb.add_theme_constant_override("separation", 12)
	vb.offset_left = 16; vb.offset_top = 16; vb.offset_right = -16; vb.offset_bottom = -16
	_panel.add_child(vb)

	vb.add_child(UIBuilder.lbl("⚙ API 配置", 18, GameColors.ACCENT_YELLOW, HORIZONTAL_ALIGNMENT_CENTER))

	# API Mode
	var mode_vb := VBoxContainer.new()
	mode_vb.add_theme_constant_override("separation", 4)
	mode_vb.add_child(UIBuilder.lbl("运行模式", 13, GameColors.DIM))
	_cfg_api_mode = OptionButton.new()
	_cfg_api_mode.add_item("服务器模式（连接后端 API）")
	_cfg_api_mode.add_item("独立模式（直接 LLM API）")
	_cfg_api_mode.add_theme_font_size_override("font_size", 13)
	mode_vb.add_child(_cfg_api_mode)
	vb.add_child(mode_vb)

	# Backend URL
	var backend_vb := VBoxContainer.new()
	backend_vb.add_theme_constant_override("separation", 4)
	backend_vb.add_child(UIBuilder.lbl("后端 API 地址", 13, GameColors.DIM))
	_cfg_backend_url = LineEdit.new()
	_cfg_backend_url.placeholder_text = "http://localhost:8765"
	_cfg_backend_url.add_theme_font_size_override("font_size", 13)
	backend_vb.add_child(_cfg_backend_url)
	vb.add_child(backend_vb)

	# LLM URL
	var llm_url_vb := VBoxContainer.new()
	llm_url_vb.add_theme_constant_override("separation", 4)
	llm_url_vb.add_child(UIBuilder.lbl("LLM API 地址", 13, GameColors.DIM))
	_cfg_llm_url = LineEdit.new()
	_cfg_llm_url.placeholder_text = "https://api.example.com/v1"
	_cfg_llm_url.add_theme_font_size_override("font_size", 13)
	llm_url_vb.add_child(_cfg_llm_url)
	vb.add_child(llm_url_vb)

	# LLM Key
	var llm_key_vb := VBoxContainer.new()
	llm_key_vb.add_theme_constant_override("separation", 4)
	llm_key_vb.add_child(UIBuilder.lbl("LLM API Key", 13, GameColors.DIM))
	_cfg_llm_key = LineEdit.new()
	_cfg_llm_key.placeholder_text = "sk-..."
	_cfg_llm_key.secret = true
	_cfg_llm_key.add_theme_font_size_override("font_size", 13)
	llm_key_vb.add_child(_cfg_llm_key)
	vb.add_child(llm_key_vb)

	# LLM Model
	var llm_model_vb := VBoxContainer.new()
	llm_model_vb.add_theme_constant_override("separation", 4)
	llm_model_vb.add_child(UIBuilder.lbl("LLM 模型", 13, GameColors.DIM))
	_cfg_llm_model = LineEdit.new()
	_cfg_llm_model.placeholder_text = "your-model-name"
	_cfg_llm_model.add_theme_font_size_override("font_size", 13)
	llm_model_vb.add_child(_cfg_llm_model)
	vb.add_child(llm_model_vb)

	# Test section
	var test_section := VBoxContainer.new()
	test_section.add_theme_constant_override("separation", 8)
	test_section.add_child(UIBuilder.lbl("🔌 连接测试", 14, GameColors.ACCENT))

	var test_btn_hb := HBoxContainer.new()
	test_btn_hb.add_theme_constant_override("separation", 8)

	var test_backend_btn := UIBuilder.btn("测试后端", GameColors.BORDER_SILVER)
	test_backend_btn.pressed.connect(_test_backend)
	test_btn_hb.add_child(test_backend_btn)

	var test_llm_btn := UIBuilder.btn("测试 LLM", GameColors.BORDER_SILVER)
	test_llm_btn.pressed.connect(_test_llm)
	test_btn_hb.add_child(test_llm_btn)

	test_section.add_child(test_btn_hb)

	_backend_test_result = UIBuilder.lbl("", 11, GameColors.DIM)
	test_section.add_child(_backend_test_result)

	_llm_test_result = UIBuilder.lbl("", 11, GameColors.DIM)
	test_section.add_child(_llm_test_result)

	vb.add_child(test_section)

	vb.add_child(Control.new())

	# Buttons
	var btn_hb := HBoxContainer.new()
	btn_hb.add_theme_constant_override("separation", 8)
	btn_hb.size_flags_horizontal = SIZE_SHRINK_END

	var cancel_btn := UIBuilder.btn("取消", GameColors.BORDER_SILVER)
	cancel_btn.pressed.connect(toggle)
	btn_hb.add_child(cancel_btn)

	var save_btn := UIBuilder.btn("保存配置", GameColors.ACCENT_YELLOW)
	save_btn.pressed.connect(_apply_config)
	btn_hb.add_child(save_btn)

	vb.add_child(btn_hb)

	parent.add_child(_overlay)


## 切换配置面板显示/隐藏
func toggle() -> void:
	if _overlay.visible:
		_overlay.visible = false
	else:
		_fill_config_values()
		_overlay.visible = true


## 从 ApiClient 填充当前配置值到表单
func _fill_config_values() -> void:
	_cfg_api_mode.selected = 0 if ApiClient.api_mode == "backend" else 1
	_cfg_backend_url.text = ApiClient.backend_url
	_cfg_llm_url.text = ApiClient.llm_api_url
	_cfg_llm_key.text = ApiClient.llm_api_key
	_cfg_llm_model.text = ApiClient.llm_model


## 应用配置到 ApiClient 并更新指示器
func _apply_config() -> void:
	_cfg_backend_url.add_theme_color_override("font_color", Color(1, 1, 1))
	_cfg_llm_url.add_theme_color_override("font_color", Color(1, 1, 1))
	_cfg_llm_key.add_theme_color_override("font_color", Color(1, 1, 1))
	_cfg_llm_model.add_theme_color_override("font_color", Color(1, 1, 1))

	var new_mode := "backend" if _cfg_api_mode.selected == 0 else "direct"
	var new_backend_url := _cfg_backend_url.text.strip_edges()
	var new_llm_url := _cfg_llm_url.text.strip_edges()
	var new_llm_key := _cfg_llm_key.text.strip_edges()
	var new_llm_model := _cfg_llm_model.text.strip_edges()

	# 输入验证
	if new_mode == "backend" and new_backend_url == "":
		_cfg_backend_url.add_theme_color_override("font_color", GameColors.ACCENT_RED)
		return
	if new_mode == "direct" and new_llm_url == "":
		_cfg_llm_url.add_theme_color_override("font_color", GameColors.ACCENT_RED)
		return
	if new_mode == "direct" and new_llm_key == "":
		_cfg_llm_key.add_theme_color_override("font_color", GameColors.ACCENT_RED)
		return
	if new_mode == "direct" and new_llm_model == "":
		_cfg_llm_model.add_theme_color_override("font_color", GameColors.ACCENT_RED)
		return

	ApiClient.api_mode = new_mode
	ApiClient.backend_url = new_backend_url
	ApiClient.llm_api_url = new_llm_url
	ApiClient.llm_api_key = new_llm_key
	ApiClient.llm_model = new_llm_model

	if _on_indicator_updated.is_valid():
		var mode_text := "后端模式" if ApiClient.api_mode == "backend" else "独立模式"
		var mode_color := GameColors.BORDER_GOLD if ApiClient.api_mode == "backend" else GameColors.ACCENT_PURPLE
		_on_indicator_updated.call(mode_text, mode_color)

	toggle()


## 测试后端连接
func _test_backend() -> void:
	_backend_test_result.text = "⏳ 测试中..."
	_backend_test_result.add_theme_color_override("font_color", GameColors.DIM)

	var ok: bool = await ApiClient.test_backend()
	if ok:
		_backend_test_result.text = "✅ 后端连接成功"
		_backend_test_result.add_theme_color_override("font_color", GameColors.ACCENT_GREEN)
	else:
		_backend_test_result.text = "❌ 后端连接失败"
		_backend_test_result.add_theme_color_override("font_color", GameColors.ACCENT_RED)


## 测试 LLM 连接
func _test_llm() -> void:
	_llm_test_result.text = "⏳ 测试中..."
	_llm_test_result.add_theme_color_override("font_color", GameColors.DIM)

	var ok: bool = await ApiClient.test_llm()
	if ok:
		_llm_test_result.text = "✅ LLM连接成功"
		_llm_test_result.add_theme_color_override("font_color", GameColors.ACCENT_GREEN)
	else:
		_llm_test_result.text = "❌ LLM连接失败"
		_llm_test_result.add_theme_color_override("font_color", GameColors.ACCENT_RED)
