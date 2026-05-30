class_name ConfigPanel
## ConfigPanel — 活纸 · 江湖行纪 API 配置面板
## API Configuration Panel for backend settings
##
## 职责:
##   1. 构建配置面板 UI (后端地址、关闭密钥)
##   2. 填充/读取当前配置值
##   3. 应用配置到 ApiClient
##   4. 执行后端连接测试
##   5. 配置持久化 (非敏感信息存 user://)
##
## 依赖: GameColors (Autoload), ApiClient (Autoload), UIBuilder

var _overlay: Control
var _panel: Control
var _cfg_backend_url: LineEdit
var _cfg_shutdown_secret: LineEdit
var _backend_test_result: Label

const CONFIG_PATH := "user://living_paper_config.json"


func build(parent: Control) -> void:
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
	_panel.custom_minimum_size = Vector2(400, 360)
	UIBuilder.add_panel_style(_panel)
	panel_container.add_child(_panel)

	var vb := VBoxContainer.new()
	vb.set_anchors_preset(PRESET_FULL_RECT)
	vb.add_theme_constant_override("separation", 12)
	vb.offset_left = 16; vb.offset_top = 16; vb.offset_right = -16; vb.offset_bottom = -16
	_panel.add_child(vb)

	vb.add_child(UIBuilder.lbl("⚙ API 配置", 18, GameColors.ACCENT_YELLOW, HORIZONTAL_ALIGNMENT_CENTER))

	var backend_vb := VBoxContainer.new()
	backend_vb.add_theme_constant_override("separation", 4)
	backend_vb.add_child(UIBuilder.lbl("后端 API 地址", 13, GameColors.DIM))
	_cfg_backend_url = LineEdit.new()
	_cfg_backend_url.placeholder_text = "http://localhost:8765"
	_cfg_backend_url.add_theme_font_size_override("font_size", 13)
	backend_vb.add_child(_cfg_backend_url)
	vb.add_child(backend_vb)

	var secret_vb := VBoxContainer.new()
	secret_vb.add_theme_constant_override("separation", 4)
	secret_vb.add_child(UIBuilder.lbl("关闭服务密钥 (SHUTDOWN_SECRET)", 13, GameColors.DIM))
	_cfg_shutdown_secret = LineEdit.new()
	_cfg_shutdown_secret.placeholder_text = "dev"
	_cfg_shutdown_secret.secret = true
	_cfg_shutdown_secret.add_theme_font_size_override("font_size", 13)
	secret_vb.add_child(_cfg_shutdown_secret)
	vb.add_child(secret_vb)

	var test_section := VBoxContainer.new()
	test_section.add_theme_constant_override("separation", 8)
	test_section.add_child(UIBuilder.lbl("🔌 连接测试", 14, GameColors.ACCENT))

	var test_backend_btn := UIBuilder.btn("测试后端", GameColors.BORDER_SILVER)
	test_backend_btn.pressed.connect(_test_backend)
	test_section.add_child(test_backend_btn)

	_backend_test_result = UIBuilder.lbl("", 11, GameColors.DIM)
	test_section.add_child(_backend_test_result)

	vb.add_child(test_section)

	vb.add_child(Control.new())

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
	_load_config()


func toggle() -> void:
	if _overlay.visible:
		_overlay.visible = false
	else:
		_fill_config_values()
		_overlay.visible = true


func _fill_config_values() -> void:
	_cfg_backend_url.text = ApiClient.backend_url
	_cfg_shutdown_secret.text = ApiClient.shutdown_secret


func _apply_config() -> void:
	_cfg_backend_url.add_theme_color_override("font_color", Color(1, 1, 1))

	var new_backend_url := _cfg_backend_url.text.strip_edges()
	var new_secret := _cfg_shutdown_secret.text.strip_edges()

	if new_backend_url == "":
		_cfg_backend_url.add_theme_color_override("font_color", GameColors.ACCENT_RED)
		return

	ApiClient.backend_url = new_backend_url
	ApiClient.shutdown_secret = new_secret

	_save_config()
	toggle()


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


func _save_config() -> void:
	var cfg := {
		"backend_url": ApiClient.backend_url,
		"shutdown_secret": ApiClient.shutdown_secret,
	}
	var file := FileAccess.open(CONFIG_PATH, FileAccess.WRITE)
	if file:
		file.store_string(JSON.stringify(cfg))
		file.close()


func _load_config() -> void:
	if not FileAccess.file_exists(CONFIG_PATH):
		return
	var file := FileAccess.open(CONFIG_PATH, FileAccess.READ)
	if not file:
		return
	var text := file.get_as_text()
	file.close()
	var json := JSON.new()
	if json.parse(text) != OK:
		return
	var data: Dictionary = json.data as Dictionary if json.data is Dictionary else {}
	if data.has("backend_url") and data.backend_url != "":
		ApiClient.backend_url = data.backend_url
	if data.has("shutdown_secret") and data.shutdown_secret != "":
		ApiClient.shutdown_secret = data.shutdown_secret
