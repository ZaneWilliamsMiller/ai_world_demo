class_name DialogManager
## DialogManager — 活纸 · 江湖行纪 通用对话框管理器
## Universal Confirmation / Alert Dialog Manager
##
## 职责:
##   1. 显示通用确认对话框 (标题 + 消息 + 取消/确定)
##   2. 支持 BBCode 富文本消息
##   3. 自动居中 + 响应式尺寸
##
## 使用方式 (推荐作为 Autoload 单例):
##   DialogManager.show_confirm(parent, "标题", "消息内容", on_confirm_callable)
##
## 或者实例化使用:
##   var dm := DialogManager.new()
##   dm.show_confirm(parent, "标题", "消息", callback)
##
## 依赖: GameColors (Autoload), UIBuilder


## 显示确认对话框
## [param parent] 父节点 (通常是根 Control)
## [param title] 对话框标题
## [param message] 对话框消息内容 (支持 BBCode)
## [param on_confirm] 点击确定后的回调 Callable
## [param border_color] 边框强调色 (默认红色警告风格)
## [param border_width] 边框宽度 (默认 3.0)
func show_confirm(parent: Control, title: String, message: String, on_confirm: Callable,
		border_color: Color = GameColors.ACCENT_RED, border_width: float = 3.0) -> void:

	var popup := UIBuilder.overlay(parent)
	var panel := Panel.new()
	panel.custom_minimum_size = Vector2(460, 240)
	panel.size = Vector2(460, 240)

	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.12, 0.08, 0.12)
	sb.set_corner_radius_all(6)
	sb.border_width_left = border_width; sb.border_width_right = border_width
	sb.border_width_top = border_width; sb.border_width_bottom = border_width
	sb.border_color = border_color
	sb.content_margin_left = 12; sb.content_margin_right = 12
	sb.content_margin_top = 8; sb.content_margin_bottom = 8
	panel.add_theme_stylebox_override("panel", sb)

	popup.add_child(panel)
	popup.resized.connect(func():
		UIBuilder.center_in_parent(panel, popup.size, Vector2(460, 240))
	)

	var vb := VBoxContainer.new()
	vb.add_theme_constant_override("separation", 16)
	vb.set_anchors_preset(PRESET_FULL_RECT)
	vb.offset_left = 32; vb.offset_top = 28; vb.offset_right = -32; vb.offset_bottom = -28
	panel.add_child(vb)

	vb.add_child(UIBuilder.lbl("⚠️", 40, GameColors.ACCENT_RED, HORIZONTAL_ALIGNMENT_CENTER))
	vb.add_child(UIBuilder.lbl(title, 18, GameColors.TEXT, HORIZONTAL_ALIGNMENT_CENTER))

	var msg_lbl := RichTextLabel.new()
	msg_lbl.bbcode_enabled = true
	msg_lbl.fit_content = true
	msg_lbl.add_theme_font_size_override("normal_font_size", 14)
	msg_lbl.add_theme_color_override("default_color", Color(0.7, 0.7, 0.75))
	msg_lbl.text = message
	vb.add_child(msg_lbl)

	var btn_hb := HBoxContainer.new()
	btn_hb.add_theme_constant_override("separation", 12)
	btn_hb.alignment = HORIZONTAL_ALIGNMENT_CENTER
	vb.add_child(btn_hb)

	var cancel_btn := UIBuilder.btn("取消", Color(0.4, 0.4, 0.5))
	cancel_btn.pressed.connect(func(): popup.queue_free())
	btn_hb.add_child(cancel_btn)

	var ok_btn := UIBuilder.btn("确定", Color(0.85, 0.2, 0.2))
	ok_btn.pressed.connect(func():
		popup.queue_free()
		on_confirm.call()
	)
	btn_hb.add_child(ok_btn)


## 显示简单提示/警告对话框 (无取消按钮，点击任意位置或按钮关闭)
## [param parent] 父节点
## [param title] 标题
## [param message] 消息内容
## [param icon_text] 图标文字 (默认 "ℹ️")
## [param accent_color] 强调色
func show_alert(parent: Control, title: String, message: String,
		icon_text: String = "ℹ️", accent_color: Color = GameColors.ACCENT_BLUE) -> void:

	var popup := UIBuilder.overlay(parent)
	var panel := Panel.new()
	panel.custom_minimum_size = Vector2(400, 200)
	panel.size = Vector2(400, 200)

	var sb := StyleBoxFlat.new()
	sb.bg_color = GameColors.BG_PANEL
	sb.set_corner_radius_all(6)
	sb.border_width_left = 1; sb.border_width_right = 1
	sb.border_width_top = 1; sb.border_width_bottom = 1
	sb.border_color = accent_color
	sb.content_margin_left = 16; sb.content_margin_right = 16
	sb.content_margin_top = 12; sb.content_margin_bottom = 12
	panel.add_theme_stylebox_override("panel", sb)

	popup.add_child(panel)
	popup.resized.connect(func():
		UIBuilder.center_in_parent(panel, popup.size, Vector2(400, 200))
	)

	var vb := VBoxContainer.new()
	vb.add_theme_constant_override("separation", 12)
	vb.set_anchors_preset(PRESET_FULL_RECT)
	vb.offset_left = 24; vb.offset_top = 20; vb.offset_right = -24; vb.offset_bottom = -20
	panel.add_child(vb)

	vb.add_child(UIBuilder.lbl(icon_text, 36, accent_color, HORIZONTAL_ALIGNMENT_CENTER))
	vb.add_child(UIBuilder.lbl(title, 16, GameColors.TEXT, HORIZONTAL_ALIGNMENT_CENTER))

	var msg_lbl := RichTextLabel.new()
	msg_lbl.bbcode_enabled = true
	msg_lbl.fit_content = true
	msg_lbl.add_theme_font_size_override("normal_font_size", 13)
	msg_lbl.add_theme_color_override("default_color", GameColors.DIM)
	msg_lbl.text = message
	vb.add_child(msg_lbl)

	var ok_btn := UIBuilder.btn("确定", accent_color)
	ok_btn.pressed.connect(func(): popup.queue_free())
	var btn_center := HBoxContainer.new()
	btn_center.alignment = HORIZONTAL_ALIGNMENT_CENTER
	btn_center.add_child(ok_btn)
	vb.add_child(btn_center)
