class_name UIBuilder
## UIBuilder — 活纸 · 江湖行纪 UI 构建器
## UI Builder for Login Screen, Game Main UI, and Style Helpers
##
## 职责:
##   1. 构建登录界面 (Login Overlay)
##   2. 构建游戏主界面 (Two-column layout: Map | Sidebar)
##   3. 提供通用 UI 样式辅助工厂方法
##
## 使用方式:
##   var builder := UIBuilder.new()
##   var login_overlay = builder.build_login(on_start_pressed, on_load_pressed, on_config, on_test, on_shutdown)
##   var game_ui_refs = builder.build_game_ui(on_npc_clicked, on_send)
##
## 依赖: GameColors (Autoload 单例)

# ═══════════════════════════════════════════════════════
#  Public API — 构建入口
# ═══════════════════════════════════════════════════════

## 构建登录界面遮罩层
## [param parent] 父节点 (通常是根 Control)
## [param on_start] 踏入江湖按钮回调 Callable
## [param on_load] 载入旧档按钮回调 Callable
## [param on_config] 配置按钮回调 Callable
## [param on_test] 测试按钮回调 Callable
## [param on_shutdown] 关闭服务按钮回调 Callable
## returns 登录遮罩 Control 节点
func build_login(parent: Control, on_start: Callable, on_load: Callable,
		on_config: Callable, on_test: Callable, on_shutdown: Callable) -> Control:

	var overlay := Control.new()
	overlay.set_anchors_preset(PRESET_FULL_RECT)
	parent.add_child(overlay)

	var overlay_bg := ColorRect.new()
	overlay_bg.color = Color(0,0,0,0.85)
	overlay_bg.set_anchors_preset(PRESET_FULL_RECT)
	overlay_bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	overlay.add_child(overlay_bg)

	var box := Panel.new()
	box.custom_minimum_size = Vector2(340, 400)
	box.size = Vector2(340, 400)
	add_panel_style(box)
	box.set_anchors_and_offsets_preset(PRESET_CENTER, PRESET_MODE_KEEP_SIZE, 0)
	overlay.add_child(box)

	var vb := VBoxContainer.new()
	vb.set_anchors_preset(PRESET_FULL_RECT)
	vb.add_theme_constant_override("separation", 12)
	box.add_child(vb)

	vb.add_child(lbl("🏮 活纸 · 江湖行纪", 22, GameColors.ACCENT, HORIZONTAL_ALIGNMENT_CENTER))

	var name_input := make_input("江湖名号", "输入你的名号...")
	vb.add_child(name_input)

	var gs_vb := VBoxContainer.new()
	gs_vb.add_child(lbl("性别", 13, GameColors.DIM))
	var gender_sel := OptionButton.new()
	for g in ["男","女","不透露"]: gender_sel.add_item(g)
	gender_sel.add_theme_font_size_override("font_size", 14)
	gs_vb.add_child(gender_sel)
	vb.add_child(gs_vb)

	var pd_cb := CheckBox.new()
	pd_cb.text = " 真实江湖（永久死亡）"
	pd_cb.add_theme_color_override("font_color", GameColors.DIM)
	vb.add_child(pd_cb)

	var start_btn := btn("踏入江湖", GameColors.ACCENT)
	start_btn.pressed.connect(func():
		var nm: String = name_input.get_child(1).text.strip_edges()
		if nm == "": nm = "江湖客"
		var g: String = "未言"
		var sel: int = gender_sel.get_selected_id()
		if sel >= 0 and sel <= 2: g = ["男","女","未言"][sel]
		on_start.call(nm, g, pd_cb.button_pressed)
	)
	vb.add_child(start_btn)

	var load_btn := btn("载入旧档 →", Color(0.5,0.5,0.5))
	load_btn.pressed.connect(on_load)
	vb.add_child(load_btn)

	var tools_hb := HBoxContainer.new()
	tools_hb.add_theme_constant_override("separation", 8)
	vb.add_child(tools_hb)

	var config_btn := btn("⚙ 配置", Color(0.5,0.5,0.5))
	config_btn.pressed.connect(on_config)
	tools_hb.add_child(config_btn)

	var test_btn := btn("🧪 测试", Color(0.9,0.27,0.37))
	test_btn.pressed.connect(on_test)
	tools_hb.add_child(test_btn)

	var shutdown_btn := btn("⏻ 关闭服务", Color(0.94,0.27,0.27))
	shutdown_btn.pressed.connect(on_shutdown)
	tools_hb.add_child(shutdown_btn)

	return overlay


## 构建存档选择对话框
## [param parent] 父节点
## [param saves] 存档列表 Array
## [param on_select] 选择存档回调 Callable(player_id)
## [param on_close] 关闭回调 Callable
func build_load_dialog(parent: Control, saves: Array, on_select: Callable, on_close: Callable) -> Control:
	var popup := overlay(parent)
	var box := Panel.new()
	box.custom_minimum_size = Vector2(320, 300)
	box.size = Vector2(320, 300)
	add_panel_style(box)
	popup.add_child(box)
	popup.resized.connect(func():
		var ps: Vector2 = popup.size
		box.position = (ps - Vector2(320, 300)) / 2.0
	)
	var vb := VBoxContainer.new(); vb.add_theme_constant_override("separation", 6)
	vb.set_anchors_preset(PRESET_FULL_RECT); box.add_child(vb)

	vb.add_child(lbl("选择存档", 16, GameColors.ACCENT, HORIZONTAL_ALIGNMENT_CENTER))
	var list_ct := VBoxContainer.new(); list_ct.add_theme_constant_override("separation", 4)
	vb.add_child(list_ct)

	if saves.is_empty():
		list_ct.add_child(lbl("暂无存档", 14, GameColors.DIM))

	for s in saves:
		var pid: String = s.get("player_id","")
		var b := btn("%s 第%d日%s" % [
			s.get("display_name",pid), s.get("world_day",1),
			" 【亡】" if s.get("dead",false) else ""
		], GameColors.BG_CARD)
		b.alignment = HORIZONTAL_ALIGNMENT_LEFT
		b.pressed.connect(func(p=pid): on_select.call(p); popup.queue_free())
		list_ct.add_child(b)

	var close_btn := btn("返回", Color(0.4,0.4,0.5))
	close_btn.pressed.connect(func(): on_close.call(); popup.queue_free())
	vb.add_child(close_btn)

	return popup


## 游戏主UI构建结果引用字典
## 包含所有需要外部访问的节点引用
const GAME_UI_KEYS := [
	"game_ui", "map_renderer", "map_sub_vp", "map_sub",
	"dialogue_label", "chat_scroll", "npc_select", "msg_input", "send_btn",
	"vigor_bar", "vigor_label", "spirit_bar", "spirit_label",
	"coins_label", "time_label", "weather_label", "map_name_label", "map_title_label",
	"inventory_flow", "favor_vbox", "npc_list_container", "portal_list_container",
	"api_mode_indicator",
]

## 构建游戏主界面（两栏布局）
## [param parent] 父节点 (通常是根 Control)
## [param on_tile_click] 地图格子点击回调 Callable(x, y)
## [param on_npc_map_click] 地图上NPC点击回调 Callable(npc_id, npc_name)
## [param on_send] 发送消息回调 Callable
## [param on_save] 存档回调 Callable
## [param on_quit] 退出回调 Callable
## [param on_config] 配置面板切换回调 Callable
## returns Dictionary 包含所有节点引用 (见 GAME_UI_KEYS)
func build_game_ui(parent: Control, on_tile_click: Callable, on_npc_map_click: Callable,
		on_send: Callable, on_save: Callable, on_quit: Callable, on_config: Callable) -> Dictionary:

	print("[UIBuilder] build_game_ui() START")
	var refs := {}

	var game_ui := Control.new()
	game_ui.set_anchors_preset(PRESET_FULL_RECT)
	parent.add_child(game_ui)
	refs["game_ui"] = game_ui

	var root_vb := VBoxContainer.new()
	root_vb.set_anchors_preset(PRESET_FULL_RECT)
	root_vb.add_theme_constant_override("separation", 0)
	game_ui.add_child(root_vb)

	# ── Top Bar (固定高度 36px) ──
	var topbar := Panel.new()
	topbar.custom_minimum_size = Vector2(0, 36)
	topbar.size_flags_vertical = SIZE_SHRINK_CENTER
	add_panel_style(topbar)
	root_vb.add_child(topbar)

	var top_hb := HBoxContainer.new()
	top_hb.add_theme_constant_override("separation", 16)
	top_hb.set_anchors_preset(PRESET_FULL_RECT)
	topbar.add_child(top_hb)
	top_hb.add_child(lbl("🏮 活纸 · 江湖行纪", 15, GameColors.ACCENT_YELLOW))
	top_hb.add_child(Control.new())

	refs["api_mode_indicator"] = lbl("后端模式", 11, GameColors.DIM)
	refs["api_mode_indicator"].add_theme_color_override("font_color", GameColors.BORDER_GOLD)
	top_hb.add_child(refs["api_mode_indicator"])

	var config_btn := btn("⚙", GameColors.BORDER_SILVER)
	config_btn.pressed.connect(on_config)
	top_hb.add_child(config_btn)

	var save_btn := btn("💾 存档", GameColors.ACCENT_GREEN)
	save_btn.pressed.connect(func(): on_save.call())
	top_hb.add_child(save_btn)

	var quit_btn := btn("🚪 退出", GameColors.ACCENT_RED)
	quit_btn.pressed.connect(on_quit)
	top_hb.add_child(quit_btn)

	# ── Main Area: HSplitContainer ──
	var hsplit := HSplitContainer.new()
	hsplit.size_flags_horizontal = SIZE_EXPAND_FILL
	hsplit.size_flags_vertical = SIZE_EXPAND_FILL
	hsplit.dragger_visibility = SplitContainer.DRAGGER_HIDDEN
	hsplit.split_offset = -340
	root_vb.add_child(hsplit)

	# ── LEFT: Map Panel ──
	var map_panel := VBoxContainer.new()
	map_panel.size_flags_horizontal = SIZE_EXPAND_FILL
	map_panel.size_flags_vertical = SIZE_EXPAND_FILL
	map_panel.add_theme_constant_override("separation", 0)
	hsplit.add_child(map_panel)

	# Map title bar
	var map_title := Panel.new()
	map_title.custom_minimum_size = Vector2(0, 26)
	var mt_sb := StyleBoxFlat.new()
	mt_sb.bg_color = GameColors.BG_PANEL
	mt_sb.border_width_bottom = 1; mt_sb.border_color = GameColors.BORDER
	mt_sb.content_margin_left = 10; mt_sb.content_margin_right = 10
	mt_sb.content_margin_top = 3; mt_sb.content_margin_bottom = 3
	map_title.add_theme_stylebox_override("panel", mt_sb)
	map_title.size_flags_vertical = SIZE_SHRINK_CENTER
	map_panel.add_child(map_title)
	var mt_hb := HBoxContainer.new()
	mt_hb.set_anchors_preset(PRESET_FULL_RECT); map_title.add_child(mt_hb)
	mt_hb.add_child(lbl("🗺️ 地图", 12, GameColors.ACCENT, HORIZONTAL_ALIGNMENT_LEFT))
	mt_hb.add_child(Control.new())
	refs["map_title_label"] = lbl("--", 11, GameColors.DIM)
	mt_hb.add_child(refs["map_title_label"])

	# Map SubViewport container
	refs["map_sub_vp"] = SubViewportContainer.new()
	refs["map_sub_vp"].name = "MapSubVPContainer"
	refs["map_sub_vp"].size_flags_horizontal = SIZE_EXPAND_FILL
	refs["map_sub_vp"].size_flags_vertical = SIZE_EXPAND_FILL
	refs["map_sub_vp"].stretch = true
	map_panel.add_child(refs["map_sub_vp"])

	refs["map_sub"] = SubViewport.new()
	refs["map_sub"].name = "MapSubViewport"
	refs["map_sub"].render_target_update_mode = SubViewport.UPDATE_ALWAYS
	refs["map_sub"].transparent_bg = true
	refs["map_sub_vp"].add_child(refs["map_sub"])

	# Map renderer
	refs["map_renderer"] = preload("res://scripts/map_renderer.gd").new()
	refs["map_renderer"].name = "MapRenderer"
	refs["map_sub"].add_child(refs["map_renderer"])

	print("[UIBuilder] Map renderer added to SubViewport")

	# Connect map renderer signals
	refs["map_renderer"].tile_clicked.connect(on_tile_click)
	refs["map_renderer"].npc_clicked.connect(on_npc_map_click)

	# ── RIGHT: Side Panel (~360px) ──
	var side_panel := VBoxContainer.new()
	side_panel.custom_minimum_size = Vector2(330, 0)
	side_panel.add_theme_constant_override("separation", 6)
	side_panel.size_flags_horizontal = SIZE_SHRINK_BEGIN
	side_panel.size_flags_vertical = SIZE_EXPAND_FILL
	side_panel.name = "SidePanel"
	hsplit.add_child(side_panel)

	# Card 1: Player Status
	var stat_card := make_card("⚔ 角色状态")
	side_panel.add_child(stat_card)
	var stat_vb := card_content(stat_card)
	stat_vb.add_theme_constant_override("separation", 6)

	# Vigor bar
	refs["vigor_bar"] = ProgressBar.new(); refs["vigor_bar"].show_percentage = false
	refs["vigor_bar"].custom_minimum_size = Vector2(0, 8); refs["vigor_bar"].size_flags_horizontal = SIZE_EXPAND
	var vg_sb := StyleBoxFlat.new(); vg_sb.bg_color = GameColors.GREEN
	vg_sb.set_corner_radius_all(3)
	refs["vigor_bar"].add_theme_stylebox_override("fill", vg_sb)
	var vigor_row := HBoxContainer.new(); stat_vb.add_child(vigor_row)
	vigor_row.add_child(lbl("💪 体力", 11, GameColors.DIM)); vigor_row.add_child(Control.new())
	refs["vigor_label"] = lbl("--/--", 11, GameColors.TEXT); vigor_row.add_child(refs["vigor_label"])
	stat_vb.add_child(refs["vigor_bar"])

	# Spirit bar
	refs["spirit_bar"] = ProgressBar.new(); refs["spirit_bar"].show_percentage = false
	refs["spirit_bar"].custom_minimum_size = Vector2(0, 8); refs["spirit_bar"].size_flags_horizontal = SIZE_EXPAND
	var sp_sb := StyleBoxFlat.new(); sp_sb.bg_color = GameColors.ACCENT
	sp_sb.set_corner_radius_all(3)
	refs["spirit_bar"].add_theme_stylebox_override("fill", sp_sb)
	var spirit_row := HBoxContainer.new(); stat_vb.add_child(spirit_row)
	spirit_row.add_child(lbl("🧘 心气", 11, GameColors.DIM)); spirit_row.add_child(Control.new())
	refs["spirit_label"] = lbl("--/--", 11, GameColors.TEXT); spirit_row.add_child(refs["spirit_label"])
	stat_vb.add_child(refs["spirit_bar"])

	# Info grid
	var info_grid := GridContainer.new()
	info_grid.columns = 2
	info_grid.add_theme_constant_override("h_separation", 12)
	info_grid.add_theme_constant_override("v_separation", 4)
	stat_vb.add_child(info_grid)
	refs["coins_label"] = lbl("💰 0文", 11, GameColors.TEXT); info_grid.add_child(refs["coins_label"])
	refs["time_label"] = lbl("🧭 --", 11, GameColors.TEXT); info_grid.add_child(refs["time_label"])
	refs["weather_label"] = lbl("🌤 --", 11, GameColors.TEXT); info_grid.add_child(refs["weather_label"])
	refs["map_name_label"] = lbl("📍 --", 11, GameColors.DIM); info_grid.add_child(refs["map_name_label"])

	# Card 2: Inventory
	var inv_card := make_card("🎒 行囊")
	side_panel.add_child(inv_card)
	var inv_vb := card_content(inv_card)
	refs["inventory_flow"] = HFlowContainer.new()
	refs["inventory_flow"].add_theme_constant_override("h_separation", 6)
	refs["inventory_flow"].add_theme_constant_override("v_separation", 3)
	inv_vb.add_child(refs["inventory_flow"])

	# Card 3: Favor
	var fav_card := make_card("❤ 好感度")
	side_panel.add_child(fav_card)
	refs["favor_vbox"] = card_content(fav_card)
	refs["favor_vbox"].add_theme_constant_override("separation", 3)

	# Card 4: NPC List
	var npc_card := make_card("👥 此地图人物")
	npc_card.size_flags_vertical = SIZE_EXPAND_FILL
	side_panel.add_child(npc_card)
	var npc_inner := VBoxContainer.new()
	npc_inner.set_anchors_preset(PRESET_FULL_RECT)
	npc_card.add_child(npc_inner)

	var npc_scroll := ScrollContainer.new()
	npc_scroll.size_flags_vertical = SIZE_EXPAND_FILL
	npc_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	npc_inner.add_child(npc_scroll)
	refs["npc_list_container"] = VBoxContainer.new()
	refs["npc_list_container"].add_theme_constant_override("separation", 2)
	refs["npc_list_container"].size_flags_horizontal = SIZE_EXPAND
	npc_scroll.add_child(refs["npc_list_container"])

	# Card 5: Portals
	var portal_card := make_card("🚪 界门")
	side_panel.add_child(portal_card)
	var portal_inner := VBoxContainer.new()
	portal_inner.set_anchors_preset(PRESET_FULL_RECT)
	portal_card.add_child(portal_inner)

	refs["portal_list_container"] = VBoxContainer.new()
	refs["portal_list_container"].add_theme_constant_override("separation", 4)
	refs["portal_list_container"].size_flags_horizontal = SIZE_EXPAND
	portal_inner.add_child(refs["portal_list_container"])

	# Card 6: Dialogue (bottom ~240px)
	var dlg_card := Panel.new()
	dlg_card.custom_minimum_size = Vector2(0, 240)
	dlg_card.size_flags_vertical = SIZE_SHRINK_END
	var dc_sb := StyleBoxFlat.new(); dc_sb.bg_color = GameColors.BG_PANEL
	dc_sb.set_corner_radius_all(6)
	dc_sb.border_width_left = 1; dc_sb.border_width_right = 1; dc_sb.border_width_top = 1; dc_sb.border_width_bottom = 1; dc_sb.border_color = GameColors.BORDER
	dc_sb.content_margin_left = 10; dc_sb.content_margin_right = 10
	dc_sb.content_margin_top = 8; dc_sb.content_margin_bottom = 8
	dlg_card.add_theme_stylebox_override("panel", dc_sb)
	side_panel.add_child(dlg_card)

	var dlg_vb := VBoxContainer.new()
	dlg_vb.add_theme_constant_override("separation", 6)
	dlg_vb.set_anchors_preset(PRESET_FULL_RECT)
	dlg_card.add_child(dlg_vb)

	# Chat scroll area
	refs["chat_scroll"] = ScrollContainer.new()
	refs["chat_scroll"].size_flags_vertical = SIZE_EXPAND
	refs["chat_scroll"].horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	dlg_vb.add_child(refs["chat_scroll"])

	refs["dialogue_label"] = RichTextLabel.new()
	refs["dialogue_label"].bbcode_enabled = true
	refs["dialogue_label"].fit_content = true
	refs["dialogue_label"].selection_enabled = true
	refs["dialogue_label"].size_flags_horizontal = SIZE_EXPAND
	refs["dialogue_label"].scroll_following = false
	refs["dialogue_label"].add_theme_font_size_override("normal_font_size", 13)
	refs["dialogue_label"].add_theme_color_override("default_color", GameColors.TEXT)
	refs["chat_scroll"].add_child(refs["dialogue_label"])

	# Input bar
	var input_bar := HBoxContainer.new()
	input_bar.custom_minimum_size = Vector2(0, 36)
	input_bar.add_theme_constant_override("separation", 6)
	dlg_vb.add_child(input_bar)

	refs["npc_select"] = OptionButton.new(); refs["npc_select"].add_theme_font_size_override("font_size", 12)
	input_bar.add_child(refs["npc_select"])

	refs["msg_input"] = LineEdit.new()
	refs["msg_input"].placeholder_text = "对 TA 说些什么..."
	refs["msg_input"].size_flags_horizontal = SIZE_EXPAND
	refs["msg_input"].add_theme_font_size_override("font_size", 13)
	refs["msg_input"].text_submitted.connect(func(_t): on_send.call())
	input_bar.add_child(refs["msg_input"])

	refs["send_btn"] = btn("发送", GameColors.ACCENT)
	refs["send_btn"].pressed.connect(on_send)
	input_bar.add_child(refs["send_btn"])

	print("[UIBuilder] UI built — card-based sidebar layout")
	return refs


# ═══════════════════════════════════════════════════════
#  Static Style Helpers — 通用 UI 工厂方法
#  可被任何模块调用
# ═══════════════════════════════════════════════════════

## 创建半透明遮罩层 (右键关闭)
## [param parent] 父节点
## returns ColorRect 遮罩节点
static func overlay(parent: Control) -> ColorRect:
	var o := ColorRect.new(); o.color = Color(0,0,0,0.75)
	o.set_anchors_preset(PRESET_FULL_RECT)
	o.gui_input.connect(func(ev):
		if ev is InputEventMouseButton and ev.pressed and ev.button_index == MOUSE_BUTTON_RIGHT:
			o.queue_free()
	)
	parent.add_child(o); return o


## 为 Panel 添加默认面板样式
static func add_panel_style(p: Panel, bg_color: Color = GameColors.BG_PANEL,
		border_color: Color = GameColors.BORDER) -> void:
	var sb := StyleBoxFlat.new()
	sb.bg_color = bg_color
	sb.set_corner_radius_all(6)
	sb.border_width_left = 1; sb.border_width_right = 1
	sb.border_width_top = 1; sb.border_width_bottom = 1; sb.border_color = border_color
	sb.content_margin_left = 12; sb.content_margin_right = 12
	sb.content_margin_top = 8; sb.content_margin_bottom = 8
	p.add_theme_stylebox_override("panel", sb)


## 创建带标题的卡片 Panel
## [param title_text] 卡片标题文字
## returns Panel 节点 (使用 card_content() 获取内部容器)
static func make_card(title_text: String) -> Panel:
	var p := Panel.new()
	var sb := StyleBoxFlat.new()
	sb.bg_color = GameColors.BG_CARD
	sb.set_corner_radius_all(6)
	sb.border_width_left = 1; sb.border_width_right = 1
	sb.border_width_top = 1; sb.border_width_bottom = 1; sb.border_color = GameColors.BORDER_SUBTLE
	sb.content_margin_left = 10; sb.content_margin_right = 10
	sb.content_margin_top = 6; sb.content_margin_bottom = 6
	p.add_theme_stylebox_override("panel", sb)

	var header_hb := HBoxContainer.new()
	header_hb.set_anchors_preset(PRESET_FULL_RECT)
	p.add_child(header_hb)
	header_hb.add_child(lbl(title_text, 11, GameColors.ACCENT, HORIZONTAL_ALIGNMENT_LEFT))
	return p


## 获取/创建卡片内部的 VBoxContainer 内容区
## [param card] make_card() 返回的 Panel
## returns 内部 VBoxContainer
static func card_content(card: Panel) -> VBoxContainer:
	var vb := VBoxContainer.new()
	vb.set_anchors_and_offsets_preset(PRESET_FULL_RECT, PRESET_MODE_MINSIZE, 0)
	vb.offset_top = 20
	card.add_child(vb)
	return vb


## 创建 Label
## [param text] 显示文本
## [param size] 字体大小
## [param color] 文字颜色
## [param align] 对齐方式 (默认左对齐)
## returns Label 节点
static func lbl(text: String, size: int, color: Color,
		align := HORIZONTAL_ALIGNMENT_LEFT) -> Label:
	var l := Label.new(); l.text = text
	l.add_theme_color_override("font_color", color)
	l.add_theme_font_size_override("font_size", size)
	l.horizontal_alignment = align
	return l


## 创建带标签的输入框组
## [param label] 标签文字
## [param placeholder] 占位符文字
## returns VBoxContainer (包含 Label + LineEdit)
static func make_input(label: String, placeholder: String) -> VBoxContainer:
	var vb := VBoxContainer.new()
	vb.add_child(lbl(label, 13, GameColors.DIM))
	var le := LineEdit.new()
	le.placeholder_text = placeholder; le.max_length = 24
	le.add_theme_font_size_override("font_size", 14)
	vb.add_child(le)
	return vb


## 创建带样式的 Button
## [param text] 按钮文字
## [param bg] 背景色
## returns Button 节点
static func btn(text: String, bg: Color) -> Button:
	var b := Button.new(); b.text = text
	b.add_theme_font_size_override("font_size", 13)
	var sb := StyleBoxFlat.new(); sb.bg_color = bg
	sb.corner_radius_top_left = 4; sb.corner_radius_top_right = 4
	sb.corner_radius_bottom_left = 4; sb.corner_radius_bottom_right = 4
	sb.content_margin_left = 14; sb.content_margin_right = 14
	sb.content_margin_top = 6; sb.content_margin_bottom = 6
	b.add_theme_stylebox_override("normal", sb)
	return b


## 创建 NPC 列表条目
## [param name] NPC 名称
## [param _id] NPC ID (预留)
## returns Panel 条目节点
static func npc_entry(name: String, _id: String) -> Panel:
	var p := Panel.new()
	p.custom_minimum_size = Vector2(0, 30)
	var esb := StyleBoxFlat.new()
	esb.bg_color = Color(0,0,0,0)
	esb.set_corner_radius_all(4)
	esb.content_margin_left = 6; esb.content_margin_right = 6
	esb.content_margin_top = 4; esb.content_margin_bottom = 4
	p.add_theme_stylebox_override("panel", esb)

	var hb := HBoxContainer.new()
	hb.set_anchors_preset(PRESET_FULL_RECT)
	p.add_child(hb)

	var dot := ColorRect.new()
	dot.custom_minimum_size = Vector2(7, 7)
	dot.position.y = 5
	dot.color = GameColors.ACCENT2
	hb.add_child(dot)

	hb.add_child(lbl(name, 12, GameColors.TEXT))
	return p
