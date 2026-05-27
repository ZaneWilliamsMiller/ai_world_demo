extends Control
## 活纸 · 江湖行纪 — Godot 桌面版
## 单文件 UI，程序化构建全部界面元素。
## 布局对齐 Web 版：两栏（地图主视区 | 侧栏 360px）
## 依赖 Autoload: ApiClient, GameManager

# ═══════════════════════════════════════════════════════
#  Color Theme - 肉鸽游戏风格
# ═══════════════════════════════════════════════════════
const BG_DARK  := Color(0.04, 0.04, 0.08)
const BG_PANEL := Color(0.09, 0.09, 0.16)
const BG_CARD  := Color(0.10, 0.10, 0.18)
const BG_CARD_HOVER := Color(0.16, 0.16, 0.28)
const BORDER_GOLD := Color(0.83, 0.63, 0.34)
const BORDER_SILVER := Color(0.63, 0.63, 0.75)
const BORDER   := Color(0.63, 0.63, 0.75)
const BORDER_SUBTLE := Color(0.40, 0.40, 0.50)
const TEXT     := Color(0.97, 0.97, 1.0)
const DIM      := Color(0.63, 0.63, 0.78)
const ACCENT_BLUE := Color(0.38, 0.65, 0.98)
const ACCENT_RED := Color(0.94, 0.27, 0.27)
const ACCENT_GREEN := Color(0.13, 0.77, 0.37)
const ACCENT_YELLOW := Color(0.92, 0.70, 0.03)
const ACCENT_PURPLE := Color(0.66, 0.33, 0.97)
const ACCENT   := ACCENT_BLUE
const ACCENT2  := ACCENT_RED
const GREEN    := ACCENT_GREEN
const GOLD     := ACCENT_YELLOW
const RED      := ACCENT_RED

# ═══════════════════════════════════════════════════════
#  Node Refs (set in _ready / _build_game_ui)
# ═══════════════════════════════════════════════════════
var _login_overlay: Control
var _game_ui: Control

# Map
var _map_renderer: Node2D  # map_renderer.gd instance
var _map_sub_vp: SubViewportContainer
var _map_sub: SubViewport

# Dialogue
var _dialogue_label: RichTextLabel
var _chat_scroll: ScrollContainer
var _npc_select: OptionButton
var _msg_input: LineEdit
var _send_btn: Button
var _is_streaming: bool = false

# HUD — direct Label refs (no more _mini_panel indirection)
var _vigor_bar: ProgressBar ; var _vigor_label: Label
var _spirit_bar: ProgressBar ; var _spirit_label: Label
var _coins_label: Label
var _time_label: Label ; var _weather_label: Label ; var _map_name_label: Label
var _inventory_flow: HFlowContainer
var _favor_vbox: VBoxContainer
var _npc_list_container: VBoxContainer  # NPC list in sidebar
var _portal_list_container: VBoxContainer  # Portal list in sidebar
var _api_mode_indicator: Label  # API模式指示器

# Config Panel
var _config_overlay: Control
var _config_panel: Control
var _cfg_api_mode: OptionButton
var _cfg_backend_url: LineEdit
var _cfg_llm_url: LineEdit
var _cfg_llm_key: LineEdit
var _cfg_llm_model: LineEdit
var _backend_test_result: Label
var _llm_test_result: Label


func _ready() -> void:
	# Dark BG
	var bg := ColorRect.new(); bg.color = BG_DARK
	bg.set_anchors_preset(PRESET_FULL_RECT); add_child(bg)

	_build_login()
	_build_game_ui()
	_build_config_panel()

	# 如果已登录(从 login_screen 转场而来)，跳过登录遮罩
	if GameManager.player_id != "":
		_login_overlay.visible = false
		_game_ui.visible = true
		call_deferred("_logged_in_deferred")
	else:
		_login_overlay.visible = true
		_game_ui.visible = false

	GameManager.logged_in.connect(func():
		print("[Game] logged_in signal fired — switching UI")
		_login_overlay.visible = false
		_game_ui.visible = true
		call_deferred("_logged_in_deferred")
	)
	GameManager.logged_out.connect(func():
		_login_overlay.visible = true
		_game_ui.visible = false
	)
	GameManager.state_updated.connect(_refresh)
	GameManager.map_pos_changed.connect(_update_map_player)
	GameManager.chat_message.connect(_on_npc_reply)
	GameManager.system_message.connect(_on_sys_msg)


func _logged_in_deferred() -> void:
	await get_tree().process_frame
	await get_tree().process_frame
	# Apply split_offset after container has a real size
	for c in _game_ui.get_children():
		if c is HSplitContainer:
			c.split_offset = -340
			print("[Game] HSplitContainer size=%s children=%d" % [str(c.size), c.get_child_count()])
			for gc in c.get_children():
				print("[Game]   child name=%s size=%s cm=%s sf_h=%d sf_v=%d" % [gc.name, str(gc.size), str(gc.custom_minimum_size), gc.size_flags_horizontal, gc.size_flags_vertical])
	print("[Game] _logged_in_deferred — sizes: game_ui=%s, self=%s" % [str(_game_ui.size), str(size)])
	print("[Game] _npc_select is null: %s" % str(_npc_select == null))
	_update_api_mode_indicator()
	_refresh()


# ═══════════════════════════════════════════════════════
#  Login
# ═══════════════════════════════════════════════════════
func _build_login() -> void:
	_login_overlay = Control.new()
	_login_overlay.set_anchors_preset(PRESET_FULL_RECT)
	add_child(_login_overlay)

	var overlay_bg := ColorRect.new()
	overlay_bg.color = Color(0,0,0,0.85)
	overlay_bg.set_anchors_preset(PRESET_FULL_RECT)
	overlay_bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_login_overlay.add_child(overlay_bg)

	# 登录面板 - 使用固定大小并手动居中
	var box := Panel.new()
	box.custom_minimum_size = Vector2(340, 400)
	box.size = Vector2(340, 400)
	_add_panel_style(box)
	# 关键: 设置 anchors 为 center preset，让面板自动居中
	box.set_anchors_and_offsets_preset(PRESET_CENTER, PRESET_MODE_KEEP_SIZE, 0)
	_login_overlay.add_child(box)

	var vb := VBoxContainer.new()
	vb.set_anchors_preset(PRESET_FULL_RECT)
	vb.add_theme_constant_override("separation", 12)
	box.add_child(vb)

	vb.add_child(_lbl("🏮 活纸 · 江湖行纪", 22, ACCENT, HORIZONTAL_ALIGNMENT_CENTER))

	var name_input := _make_input("江湖名号", "输入你的名号...")
	vb.add_child(name_input)

	var gs_vb := VBoxContainer.new()
	gs_vb.add_child(_lbl("性别", 13, DIM))
	var gender_sel := OptionButton.new()
	for g in ["男","女","不透露"]: gender_sel.add_item(g)
	gender_sel.add_theme_font_size_override("font_size", 14)
	gs_vb.add_child(gender_sel)
	vb.add_child(gs_vb)

	var pd_cb := CheckBox.new()
	pd_cb.text = " 真实江湖（永久死亡）"
	pd_cb.add_theme_color_override("font_color", DIM)
	vb.add_child(pd_cb)

	var start_btn := _btn("踏入江湖", ACCENT)
	start_btn.pressed.connect(func():
		var nm: String = name_input.get_child(1).text.strip_edges()
		if nm == "": nm = "江湖客"
		var g: String = "未言"
		var sel: int = gender_sel.get_selected_id()
		if sel >= 0 and sel <= 2: g = ["男","女","未言"][sel]
		GameManager.hello(nm, g, pd_cb.button_pressed)
	)
	vb.add_child(start_btn)

	var load_btn := _btn("载入旧档 →", Color(0.5,0.5,0.5))
	load_btn.pressed.connect(_show_load_dialog)
	vb.add_child(load_btn)


func _show_load_dialog() -> void:
	var saves: Array = await GameManager.list_saves()
	var popup := _overlay()
	var box := Panel.new()
	box.custom_minimum_size = Vector2(320, 300)
	box.size = Vector2(320, 300)
	_add_panel_style(box)
	popup.add_child(box)
	popup.resized.connect(func():
		var ps: Vector2 = popup.size
		box.position = (ps - Vector2(320, 300)) / 2.0
	)
	var vb := VBoxContainer.new(); vb.add_theme_constant_override("separation", 6)
	vb.set_anchors_preset(PRESET_FULL_RECT); box.add_child(vb)

	vb.add_child(_lbl("选择存档", 16, ACCENT, HORIZONTAL_ALIGNMENT_CENTER))
	var list_ct := VBoxContainer.new(); list_ct.add_theme_constant_override("separation", 4)
	vb.add_child(list_ct)

	if saves.is_empty():
		list_ct.add_child(_lbl("暂无存档", 14, DIM))

	for s in saves:
		var pid: String = s.get("player_id","")
		var btn := _btn("%s 第%d日%s" % [
			s.get("display_name",pid), s.get("world_day",1),
			" 【亡】" if s.get("dead",false) else ""
		], BG_CARD)
		btn.alignment = HORIZONTAL_ALIGNMENT_LEFT
		btn.pressed.connect(func(p=pid): GameManager.load_player(p); popup.queue_free())
		list_ct.add_child(btn)

	var close_btn := _btn("返回", Color(0.4,0.4,0.5))
	close_btn.pressed.connect(func(): popup.queue_free())
	vb.add_child(close_btn)


func _overlay() -> ColorRect:
	var o := ColorRect.new(); o.color = Color(0,0,0,0.75)
	o.set_anchors_preset(PRESET_FULL_RECT)
	o.gui_input.connect(func(ev):
		if ev is InputEventMouseButton and ev.pressed and ev.button_index == MOUSE_BUTTON_RIGHT:
			o.queue_free()
	)
	add_child(o); return o


# ═══════════════════════════════════════════════════════
#  Game UI — 两栏布局（对齐 Web 版）
#  ┌─────────────────────────────────┬──────────┐
#  │         Top Bar (40px)          │          │
#  ├─────────────────────────────────┤  Side    │
#  │                                 │  Panel   │
#  │       Map Panel (flex:1)        │  (360px) │
#  │                                 │          │
#  │                                 ├──────────┤
#  │                                 │ Dialogue │
#  └─────────────────────────────────┴──────────┘
# ═══════════════════════════════════════════════════════
func _build_game_ui() -> void:
	print("[Game] _build_game_ui() START")
	_game_ui = Control.new()
	_game_ui.set_anchors_preset(PRESET_FULL_RECT)
	add_child(_game_ui)

	# ═══ 根容器: VBoxContainer (垂直布局) ═══
	var root_vb := VBoxContainer.new()
	root_vb.set_anchors_preset(PRESET_FULL_RECT)
	root_vb.add_theme_constant_override("separation", 0)
	_game_ui.add_child(root_vb)

	# ═══ Top Bar (固定高度 36px) ═══
	var topbar := Panel.new()
	topbar.custom_minimum_size = Vector2(0, 36)
	topbar.size_flags_vertical = SIZE_SHRINK_CENTER
	_add_panel_style(topbar)
	root_vb.add_child(topbar)

	var top_hb := HBoxContainer.new()
	top_hb.add_theme_constant_override("separation", 16)
	top_hb.set_anchors_preset(PRESET_FULL_RECT)
	topbar.add_child(top_hb)
	top_hb.add_child(_lbl("🏮 活纸 · 江湖行纪", 15, ACCENT_YELLOW))
	top_hb.add_child(Control.new())  # spacer

	# API模式指示器
	_api_mode_indicator = _lbl("后端模式", 11, DIM)
	_api_mode_indicator.add_theme_color_override("font_color", BORDER_GOLD)
	top_hb.add_child(_api_mode_indicator)

	var config_btn := _btn("⚙", BORDER_SILVER)
	config_btn.pressed.connect(_toggle_config_panel)
	top_hb.add_child(config_btn)

	var save_btn := _btn("💾 存档", ACCENT_GREEN)
	save_btn.pressed.connect(func():
		await GameManager.save_game()
		_on_sys_msg("💾 存档已落纸")
	)
	top_hb.add_child(save_btn)

	var quit_btn := _btn("🚪 退出", ACCENT_RED)
	quit_btn.pressed.connect(func():
		await GameManager.save_game()
		GameManager.player_id = ""
		_game_ui.visible = false
		_login_overlay.visible = true
	)
	top_hb.add_child(quit_btn)

	# ═══ Main Area: HSplitContainer (填充剩余空间) ═══
	var hsplit := HSplitContainer.new()
	hsplit.size_flags_horizontal = SIZE_EXPAND_FILL
	hsplit.size_flags_vertical = SIZE_EXPAND_FILL
	hsplit.dragger_visibility = SplitContainer.DRAGGER_HIDDEN
	hsplit.split_offset = -340  # 右侧面板固定宽度
	root_vb.add_child(hsplit)

	# ═══ LEFT: Map Panel (填充剩余空间) ═══
	var map_panel := VBoxContainer.new()
	map_panel.size_flags_horizontal = SIZE_EXPAND_FILL
	map_panel.size_flags_vertical = SIZE_EXPAND_FILL
	map_panel.add_theme_constant_override("separation", 0)
	hsplit.add_child(map_panel)

	# Map title bar
	var map_title := Panel.new()
	map_title.custom_minimum_size = Vector2(0, 26)
	var mt_sb := StyleBoxFlat.new()
	mt_sb.bg_color = BG_PANEL
	mt_sb.border_width_bottom = 1; mt_sb.border_color = BORDER
	mt_sb.content_margin_left = 10; mt_sb.content_margin_right = 10
	mt_sb.content_margin_top = 3; mt_sb.content_margin_bottom = 3
	map_title.add_theme_stylebox_override("panel", mt_sb)
	map_title.size_flags_vertical = SIZE_SHRINK_CENTER
	map_panel.add_child(map_title)
	var mt_hb := HBoxContainer.new()
	mt_hb.set_anchors_preset(PRESET_FULL_RECT); map_title.add_child(mt_hb)
	mt_hb.add_child(_lbl("🗺️ 地图", 12, ACCENT, HORIZONTAL_ALIGNMENT_LEFT))
	mt_hb.add_child(Control.new())
	_map_name_label = _lbl("--", 11, DIM)  # reuse as map name in title bar
	mt_hb.add_child(_map_name_label)

	# Map SubViewport container (填充剩余空间)
	_map_sub_vp = SubViewportContainer.new()
	_map_sub_vp.name = "MapSubVPContainer"
	_map_sub_vp.size_flags_horizontal = SIZE_EXPAND_FILL
	_map_sub_vp.size_flags_vertical = SIZE_EXPAND_FILL
	_map_sub_vp.stretch = true
	map_panel.add_child(_map_sub_vp)

	_map_sub = SubViewport.new()
	_map_sub.name = "MapSubViewport"
	_map_sub.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	_map_sub.transparent_bg = true
	_map_sub_vp.add_child(_map_sub)

	# Map renderer (Node2D with Camera2D)
	_map_renderer = preload("res://scripts/map_renderer.gd").new()
	_map_renderer.name = "MapRenderer"
	_map_sub.add_child(_map_renderer)
	
	print("[Game] Map renderer added to SubViewport")

	# Connect map renderer signals
	_map_renderer.tile_clicked.connect(func(x, y): GameManager.move_player(x, y))
	_map_renderer.npc_clicked.connect(func(nid, nname):
		for idx in _npc_select.item_count:
			if _npc_select.get_item_text(idx) == nname:
				_npc_select.select(idx)
				_msg_input.grab_focus()
				return
	)

	# ═══ RIGHT: Side Panel (固定宽度 ~360px) ═══
	var side_panel := VBoxContainer.new()
	side_panel.custom_minimum_size = Vector2(330, 0)
	side_panel.add_theme_constant_override("separation", 6)
	side_panel.size_flags_horizontal = SIZE_SHRINK_BEGIN
	side_panel.size_flags_vertical = SIZE_EXPAND_FILL
	side_panel.name = "SidePanel"
	hsplit.add_child(side_panel)

	# ─── Card 1: Player Status ───
	var stat_card := _make_card("⚔ 角色状态")
	side_panel.add_child(stat_card)
	var stat_vb := _card_content(stat_card)
	stat_vb.add_theme_constant_override("separation", 6)

	# Vigor bar row
	_vigor_bar = ProgressBar.new(); _vigor_bar.show_percentage = false
	_vigor_bar.custom_minimum_size = Vector2(0, 8); _vigor_bar.size_flags_horizontal = SIZE_EXPAND
	var vg_sb := StyleBoxFlat.new(); vg_sb.bg_color = GREEN
	vg_sb.set_corner_radius_all(3)
	_vigor_bar.add_theme_stylebox_override("fill", vg_sb)
	var vigor_row := HBoxContainer.new(); stat_vb.add_child(vigor_row)
	vigor_row.add_child(_lbl("💪 体力", 11, DIM)); vigor_row.add_child(Control.new())
	_vigor_label = _lbl("--/--", 11, TEXT); vigor_row.add_child(_vigor_label)
	stat_vb.add_child(_vigor_bar)

	# Spirit bar row
	_spirit_bar = ProgressBar.new(); _spirit_bar.show_percentage = false
	_spirit_bar.custom_minimum_size = Vector2(0, 8); _spirit_bar.size_flags_horizontal = SIZE_EXPAND
	var sp_sb := StyleBoxFlat.new(); sp_sb.bg_color = ACCENT
	sp_sb.set_corner_radius_all(3)
	_spirit_bar.add_theme_stylebox_override("fill", sp_sb)
	var spirit_row := HBoxContainer.new(); stat_vb.add_child(spirit_row)
	spirit_row.add_child(_lbl("🧘 心气", 11, DIM)); spirit_row.add_child(Control.new())
	_spirit_label = _lbl("--/--", 11, TEXT); spirit_row.add_child(_spirit_label)
	stat_vb.add_child(_spirit_bar)

	# Info grid (2 columns)
	var info_grid := GridContainer.new()
	info_grid.columns = 2
	info_grid.add_theme_constant_override("h_separation", 12)
	info_grid.add_theme_constant_override("v_separation", 4)
	stat_vb.add_child(info_grid)
	_coins_label = _lbl("💰 0文", 11, TEXT); info_grid.add_child(_coins_label)
	_time_label = _lbl("🧭 --", 11, TEXT); info_grid.add_child(_time_label)
	_weather_label = _lbl("🌤 --", 11, TEXT); info_grid.add_child(_weather_label)
	_map_name_label = _lbl("📍 --", 11, DIM); info_grid.add_child(_map_name_label)

	# ─── Card 2: Inventory ───
	var inv_card := _make_card("🎒 行囊")
	side_panel.add_child(inv_card)
	var inv_vb := _card_content(inv_card)
	_inventory_flow = HFlowContainer.new()
	_inventory_flow.add_theme_constant_override("h_separation", 6)
	_inventory_flow.add_theme_constant_override("v_separation", 3)
	inv_vb.add_child(_inventory_flow)

	# ─── Card 3: Favor ───
	var fav_card := _make_card("❤ 好感度")
	side_panel.add_child(fav_card)
	_favor_vbox = _card_content(fav_card)
	_favor_vbox.add_theme_constant_override("separation", 3)

	# ─── Card 4: NPC List (flexible height) ───
	var npc_card := _make_card("👥 此地图人物")
	npc_card.size_flags_vertical = SIZE_EXPAND_FILL
	side_panel.add_child(npc_card)
	var npc_inner := VBoxContainer.new()
	npc_inner.set_anchors_preset(PRESET_FULL_RECT)
	npc_card.add_child(npc_inner)

	var npc_scroll := ScrollContainer.new()
	npc_scroll.size_flags_vertical = SIZE_EXPAND_FILL
	npc_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	npc_inner.add_child(npc_scroll)
	_npc_list_container = VBoxContainer.new()
	_npc_list_container.add_theme_constant_override("separation", 2)
	_npc_list_container.size_flags_horizontal = SIZE_EXPAND
	npc_scroll.add_child(_npc_list_container)

	# ─── Card 5: Portals ───
	var portal_card := _make_card("🚪 界门")
	side_panel.add_child(portal_card)
	var portal_inner := VBoxContainer.new()
	portal_inner.set_anchors_preset(PRESET_FULL_RECT)
	portal_card.add_child(portal_inner)

	_portal_list_container = VBoxContainer.new()
	_portal_list_container.add_theme_constant_override("separation", 4)
	_portal_list_container.size_flags_horizontal = SIZE_EXPAND
	portal_inner.add_child(_portal_list_container)

	# ─── Card 6: Dialogue (bottom, fixed ~240px) ───
	var dlg_card := Panel.new()
	dlg_card.custom_minimum_size = Vector2(0, 240)
	dlg_card.size_flags_vertical = SIZE_SHRINK_END
	var dc_sb := StyleBoxFlat.new(); dc_sb.bg_color = BG_PANEL
	dc_sb.set_corner_radius_all(6)
	dc_sb.border_width_left = 1; dc_sb.border_width_right = 1; dc_sb.border_width_top = 1; dc_sb.border_width_bottom = 1; dc_sb.border_color = BORDER
	dc_sb.content_margin_left = 10; dc_sb.content_margin_right = 10
	dc_sb.content_margin_top = 8; dc_sb.content_margin_bottom = 8
	dlg_card.add_theme_stylebox_override("panel", dc_sb)
	side_panel.add_child(dlg_card)

	var dlg_vb := VBoxContainer.new()
	dlg_vb.add_theme_constant_override("separation", 6)
	dlg_vb.set_anchors_preset(PRESET_FULL_RECT)
	dlg_card.add_child(dlg_vb)

	# Chat scroll area
	_chat_scroll = ScrollContainer.new()
	_chat_scroll.size_flags_vertical = SIZE_EXPAND
	_chat_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	dlg_vb.add_child(_chat_scroll)

	_dialogue_label = RichTextLabel.new()
	_dialogue_label.bbcode_enabled = true
	_dialogue_label.fit_content = true
	_dialogue_label.selection_enabled = true
	_dialogue_label.size_flags_horizontal = SIZE_EXPAND
	_dialogue_label.scroll_active = false
	_dialogue_label.add_theme_font_size_override("normal_font_size", 13)
	_dialogue_label.add_theme_color_override("default_color", TEXT)
	_chat_scroll.add_child(_dialogue_label)

	# Input bar
	var input_bar := HBoxContainer.new()
	input_bar.custom_minimum_size = Vector2(0, 36)
	input_bar.add_theme_constant_override("separation", 6)
	dlg_vb.add_child(input_bar)

	_npc_select = OptionButton.new(); _npc_select.add_theme_font_size_override("font_size", 12)
	input_bar.add_child(_npc_select)

	_msg_input = LineEdit.new()
	_msg_input.placeholder_text = "对 TA 说些什么..."
	_msg_input.size_flags_horizontal = SIZE_EXPAND
	_msg_input.add_theme_font_size_override("font_size", 13)
	_msg_input.text_submitted.connect(func(_t): _on_send())
	input_bar.add_child(_msg_input)

	_send_btn = _btn("发送", ACCENT)
	_send_btn.pressed.connect(_on_send)
	input_bar.add_child(_send_btn)

	print("[Game] UI built — card-based sidebar layout")


# ═══════════════════════════════════════════════════════
#  Map Rendering
# ═══════════════════════════════════════════════════════
func _build_map() -> void:
	if not _map_renderer:
		return
	_map_renderer.build_map()


func _update_map_player() -> void:
	if not _map_renderer:
		return
	_map_renderer.update_player_position()


# ═══════════════════════════════════════════════════════
#  Dialogue
# ═══════════════════════════════════════════════════════
func _on_send() -> void:
	if _is_streaming: return
	var text := _msg_input.text.strip_edges()
	if text == "": return

	var idx := _npc_select.selected
	if idx < 0: return
	var npcs := GameManager.npcs_here
	if idx >= npcs.size(): return

	var npc_id: String = npcs[idx].get("id","")
	var npc_name: String = npcs[idx].get("name", npc_id)

	_add_chat(TEXT, "", "[right]%s[/right]" % text)
	_msg_input.clear()
	_is_streaming = true
	_send_btn.disabled = true

	var ok: bool = await GameManager.talk_to_npc(npc_id, text)
	_is_streaming = false
	_send_btn.disabled = false
	_msg_input.grab_focus()


func _on_npc_reply(speaker: String, message: String, _npc_id: String) -> void:
	_add_chat(ACCENT2, speaker, message)


func _on_sys_msg(text: String) -> void:
	_add_chat(DIM, "", "[center]%s[/center]" % text)


func _add_chat(color: Color, speaker: String, body: String) -> void:
	if not is_instance_valid(_dialogue_label): return
	var bb := ""
	if speaker != "":
		bb += "[b][color=#%s]%s[/color][/b]\n" % [color.to_html(false), speaker]
	bb += body.replace("[", "[lb]")
	_dialogue_label.append_text(bb + "\n\n")
	await get_tree().process_frame
	_chat_scroll.get_v_scroll_bar().value = _chat_scroll.get_v_scroll_bar().max_value


# ═══════════════════════════════════════════════════════
#  Refresh
# ═══════════════════════════════════════════════════════
func _refresh() -> void:
	if not _game_ui.visible:
		print("[Game] _refresh() — _game_ui NOT visible, returning")
		return
	var gm = GameManager
	print("[Game] _refresh() — map_id: %s, maps_data keys: %s" % [gm.player_map_id, str(gm.maps_data.keys())])

	# Map - 检测地图变化或首次加载
	var current_renderer_map: String = _map_renderer.get_current_map_id() if _map_renderer else ""
	if gm.player_map_id != current_renderer_map:
		print("[Game] _refresh() — building map (changed from '%s' to '%s')" % [current_renderer_map, gm.player_map_id])
		_build_map()
	_update_map_player()
	elif gm.maps_data.is_empty():
		print("[Game] _refresh() — maps_data is EMPTY, skipping map build")
	else:
		# 即使地图ID相同，也更新玩家位置
		_update_map_player()

	# NPC select dropdown
	if _npc_select:
		var cur_idx := _npc_select.selected
		_npc_select.clear()
		for n in gm.npcs_here:
			_npc_select.add_item(n.get("name", n.get("id","?")))
		if cur_idx >= 0 and cur_idx < _npc_select.item_count:
			_npc_select.select(cur_idx)

	# NPC list in sidebar
	if _npc_list_container:
		for c in _npc_list_container.get_children(): c.queue_free()
		for n in gm.npcs_here:
			var entry := _npc_entry(n.get("name", n.get("id","?")), n.get("id",""))
			_npc_list_container.add_child(entry)

	# HUD bars & labels
	_vigor_bar.max_value = gm.player_vigor_max; _vigor_bar.value = gm.player_vigor
	_vigor_label.text = "%d/%d" % [gm.player_vigor, gm.player_vigor_max]
	_spirit_bar.max_value = gm.player_spirit_max; _spirit_bar.value = gm.player_spirit
	_spirit_label.text = "%d/%d" % [gm.player_spirit, gm.player_spirit_max]
	_coins_label.text = "💰 %d文" % gm.player_coins
	_time_label.text = "🧭 第%d日·%s" % [gm.player_world_day, gm.player_world_shichen]
	_weather_label.text = "🌤 %s" % gm.player_weather
	var mname = gm.maps_data.get(gm.player_map_id,{}).get("name", gm.player_map_id)
	_map_name_label.text = "📍 %s(%d,%d)" % [mname, gm.player_px, gm.player_py]

	# Inventory
	for c in _inventory_flow.get_children(): c.queue_free()
	if gm.player_inventory.is_empty():
		var l := _lbl("身无长物", 12, Color(0.4,0.4,0.4)); _inventory_flow.add_child(l)
	else:
		for item in gm.player_inventory:
			_inventory_flow.add_child(_lbl("%s×%d" % [item, gm.player_inventory[item]], 12, GOLD))

	# Favor
	for c in _favor_vbox.get_children(): c.queue_free()
	if not gm.player_favor.is_empty():
		for nid in gm.player_favor:
			var val: int = gm.player_favor[nid]
			var nm: String = gm.npc_labels.get(nid, nid)
			_favor_vbox.add_child(_lbl("%s: %+d" % [nm, val], 11,
				GREEN if val >= 0 else RED))

	# Portals
	for c in _portal_list_container.get_children(): c.queue_free()
	var map_info: Dictionary = gm.maps_data.get(gm.player_map_id, {})
	var portals: Array = map_info.get("portals", [])
	if portals.is_empty():
		var empty_label := _lbl("此地图无界门", 11, DIM)
		_portal_list_container.add_child(empty_label)
	else:
		for pt in portals:
			var target_map_id: String = pt.get("target_map_id", "")
			var target_map_info: Dictionary = gm.maps_data.get(target_map_id, {})
			var target_name: String = target_map_info.get("name", target_map_id)
			var to_x: int = pt.get("to_x", 0)
			var to_y: int = pt.get("to_y", 0)
			
			var portal_btn := _btn("↗ 往【%s】(%d,%d)" % [target_name, to_x, to_y], ACCENT_BLUE)
			portal_btn.pressed.connect(func(x=to_x, y=to_y): gm.move_player(x, y))
			_portal_list_container.add_child(portal_btn)


# ═══════════════════════════════════════════════════════
#  Style Helpers
# ═══════════════════════════════════════════════════════
func _add_panel_style(p: Panel) -> void:
	var sb := StyleBoxFlat.new()
	sb.bg_color = BG_PANEL
	sb.set_corner_radius_all(6)
	sb.border_width_left = 1; sb.border_width_right = 1; sb.border_width_top = 1; sb.border_width_bottom = 1; sb.border_color = BORDER
	sb.content_margin_left = 12; sb.content_margin_right = 12
	sb.content_margin_top = 8; sb.content_margin_bottom = 8
	p.add_theme_stylebox_override("panel", sb)


func _make_card(title_text: String) -> Panel:
	"""Create a styled card Panel with a header label and return it.
	   Caller should use _card_content() to get the inner VBoxContainer."""
	var p := Panel.new()
	var sb := StyleBoxFlat.new()
	sb.bg_color = BG_CARD
	sb.set_corner_radius_all(6)
	sb.border_width_left = 1; sb.border_width_right = 1; sb.border_width_top = 1; sb.border_width_bottom = 1; sb.border_color = BORDER_SUBTLE
	sb.content_margin_left = 10; sb.content_margin_right = 10
	sb.content_margin_top = 6; sb.content_margin_bottom = 6
	p.add_theme_stylebox_override("panel", sb)

	# Header row inside the panel
	var header_hb := HBoxContainer.new()
	header_hb.set_anchors_preset(PRESET_FULL_RECT)
	p.add_child(header_hb)
	header_hb.add_child(_lbl(title_text, 11, ACCENT, HORIZONTAL_ALIGNMENT_LEFT))
	return p


func _card_content(card: Panel) -> VBoxContainer:
	"""Get or create the content VBoxContainer inside a card Panel."""
	# The first child is the header HBoxContainer; add a VBox after it
	var vb := VBoxContainer.new()
	vb.set_anchors_and_offsets_preset(PRESET_FULL_RECT, PRESET_MODE_MINSIZE, 0)
	# Offset below the header (~20px for header text)
	vb.offset_top = 20
	card.add_child(vb)
	return vb


func _lbl(text: String, size: int, color: Color, align := HORIZONTAL_ALIGNMENT_LEFT) -> Label:
	var l := Label.new(); l.text = text
	l.add_theme_color_override("font_color", color)
	l.add_theme_font_size_override("font_size", size)
	l.horizontal_alignment = align
	return l


func _make_input(label: String, placeholder: String) -> VBoxContainer:
	var vb := VBoxContainer.new()
	vb.add_child(_lbl(label, 13, DIM))
	var le := LineEdit.new()
	le.placeholder_text = placeholder; le.max_length = 24
	le.add_theme_font_size_override("font_size", 14)
	vb.add_child(le)
	return vb


func _btn(text: String, bg: Color) -> Button:
	var b := Button.new(); b.text = text
	b.add_theme_font_size_override("font_size", 13)
	var sb := StyleBoxFlat.new(); sb.bg_color = bg
	sb.corner_radius_top_left = 4; sb.corner_radius_top_right = 4
	sb.corner_radius_bottom_left = 4; sb.corner_radius_bottom_right = 4
	sb.content_margin_left = 14; sb.content_margin_right = 14
	sb.content_margin_top = 6; sb.content_margin_bottom = 6
	b.add_theme_stylebox_override("normal", sb)
	return b


func _npc_entry(name: String, _id: String) -> Panel:
	"""Create a single NPC list entry for the sidebar."""
	var p := Panel.new()
	p.custom_minimum_size = Vector2(0, 30)
	var esb := StyleBoxFlat.new()
	esb.bg_color = Color(0,0,0,0)  # transparent
	esb.set_corner_radius_all(4)
	esb.content_margin_left = 6; esb.content_margin_right = 6
	esb.content_margin_top = 4; esb.content_margin_bottom = 4
	p.add_theme_stylebox_override("panel", esb)

	var hb := HBoxContainer.new()
	hb.set_anchors_preset(PRESET_FULL_RECT)
	p.add_child(hb)

	# NPC dot indicator
	var dot := ColorRect.new()
	dot.custom_minimum_size = Vector2(7, 7)
	dot.position.y = 5  # center vertically in 30px height
	dot.color = ACCENT2
	hb.add_child(dot)

	hb.add_child(_lbl(name, 12, TEXT))
	return p


# ═══════════════════════════════════════════════════════
#  Config Panel
# ═══════════════════════════════════════════════════════
func _build_config_panel() -> void:
	_config_overlay = Control.new()
	_config_overlay.set_anchors_preset(PRESET_FULL_RECT)
	_config_overlay.visible = false
	
	# Overlay background
	var overlay_bg := ColorRect.new()
	overlay_bg.color = Color(0,0,0,0.75)
	overlay_bg.set_anchors_preset(PRESET_FULL_RECT)
	overlay_bg.mouse_filter = Control.MOUSE_FILTER_STOP
	_config_overlay.add_child(overlay_bg)

	# Config panel container
	var panel_container := CenterContainer.new()
	panel_container.set_anchors_preset(PRESET_FULL_RECT)
	_config_overlay.add_child(panel_container)

	var panel := Panel.new()
	panel.custom_minimum_size = Vector2(400, 500)
	_add_panel_style(panel)
	panel_container.add_child(panel)

	var vb := VBoxContainer.new()
	vb.set_anchors_preset(PRESET_FULL_RECT)
	vb.add_theme_constant_override("separation", 12)
	vb.offset_left = 16; vb.offset_top = 16; vb.offset_right = -16; vb.offset_bottom = -16
	panel.add_child(vb)

	# Title
	vb.add_child(_lbl("⚙ API 配置", 18, ACCENT_YELLOW, HORIZONTAL_ALIGNMENT_CENTER))

	# API Mode
	var mode_vb := VBoxContainer.new()
	mode_vb.add_theme_constant_override("separation", 4)
	mode_vb.add_child(_lbl("运行模式", 13, DIM))
	_cfg_api_mode = OptionButton.new()
	_cfg_api_mode.add_item("服务器模式（连接后端 API）")
	_cfg_api_mode.add_item("独立模式（直接 LLM API）")
	_cfg_api_mode.add_theme_font_size_override("font_size", 13)
	mode_vb.add_child(_cfg_api_mode)
	vb.add_child(mode_vb)

	# Backend URL
	var backend_vb := VBoxContainer.new()
	backend_vb.add_theme_constant_override("separation", 4)
	backend_vb.add_child(_lbl("后端 API 地址", 13, DIM))
	_cfg_backend_url = LineEdit.new()
	_cfg_backend_url.placeholder_text = "http://127.0.0.1:8765"
	_cfg_backend_url.add_theme_font_size_override("font_size", 13)
	backend_vb.add_child(_cfg_backend_url)
	vb.add_child(backend_vb)

	# LLM URL
	var llm_url_vb := VBoxContainer.new()
	llm_url_vb.add_theme_constant_override("separation", 4)
	llm_url_vb.add_child(_lbl("LLM API 地址", 13, DIM))
	_cfg_llm_url = LineEdit.new()
	_cfg_llm_url.placeholder_text = "https://llmapi.paratera.com/v1"
	_cfg_llm_url.add_theme_font_size_override("font_size", 13)
	llm_url_vb.add_child(_cfg_llm_url)
	vb.add_child(llm_url_vb)

	# LLM Key
	var llm_key_vb := VBoxContainer.new()
	llm_key_vb.add_theme_constant_override("separation", 4)
	llm_key_vb.add_child(_lbl("LLM API Key", 13, DIM))
	_cfg_llm_key = LineEdit.new()
	_cfg_llm_key.placeholder_text = "sk-..."
	_cfg_llm_key.secret = true
	_cfg_llm_key.add_theme_font_size_override("font_size", 13)
	llm_key_vb.add_child(_cfg_llm_key)
	vb.add_child(llm_key_vb)

	# LLM Model
	var llm_model_vb := VBoxContainer.new()
	llm_model_vb.add_theme_constant_override("separation", 4)
	llm_model_vb.add_child(_lbl("LLM 模型", 13, DIM))
	_cfg_llm_model = LineEdit.new()
	_cfg_llm_model.placeholder_text = "DeepSeek-V4-Pro"
	_cfg_llm_model.add_theme_font_size_override("font_size", 13)
	llm_model_vb.add_child(_cfg_llm_model)
	vb.add_child(llm_model_vb)

	# Test section
	var test_section := VBoxContainer.new()
	test_section.add_theme_constant_override("separation", 8)
	test_section.add_child(_lbl("🔌 连接测试", 14, ACCENT))
	
	var test_btn_hb := HBoxContainer.new()
	test_btn_hb.add_theme_constant_override("separation", 8)
	
	var test_backend_btn := _btn("测试后端", BORDER_SILVER)
	test_backend_btn.pressed.connect(_test_backend)
	test_btn_hb.add_child(test_backend_btn)
	
	var test_llm_btn := _btn("测试 LLM", BORDER_SILVER)
	test_llm_btn.pressed.connect(_test_llm)
	test_btn_hb.add_child(test_llm_btn)
	
	test_section.add_child(test_btn_hb)
	
	_backend_test_result = _lbl("", 11, DIM)
	test_section.add_child(_backend_test_result)
	
	_llm_test_result = _lbl("", 11, DIM)
	test_section.add_child(_llm_test_result)
	
	vb.add_child(test_section)

	# Spacer
	vb.add_child(Control.new())

	# Buttons
	var btn_hb := HBoxContainer.new()
	btn_hb.add_theme_constant_override("separation", 8)
	btn_hb.size_flags_horizontal = SIZE_SHRINK_END
	
	var cancel_btn := _btn("取消", BORDER_SILVER)
	cancel_btn.pressed.connect(_toggle_config_panel)
	btn_hb.add_child(cancel_btn)
	
	var save_btn := _btn("保存配置", ACCENT_YELLOW)
	save_btn.pressed.connect(_apply_config)
	btn_hb.add_child(save_btn)
	
	vb.add_child(btn_hb)

	add_child(_config_overlay)


func _toggle_config_panel() -> void:
	if _config_overlay.visible:
		_config_overlay.visible = false
	else:
		_fill_config_values()
		_config_overlay.visible = true


func _fill_config_values() -> void:
	_cfg_api_mode.selected = 0 if ApiClient.api_mode == "backend" else 1
	_cfg_backend_url.text = ApiClient.backend_url
	_cfg_llm_url.text = ApiClient.llm_api_url
	_cfg_llm_key.text = ApiClient.llm_api_key
	_cfg_llm_model.text = ApiClient.llm_model


func _apply_config() -> void:
	ApiClient.api_mode = "backend" if _cfg_api_mode.selected == 0 else "direct"
	ApiClient.backend_url = _cfg_backend_url.text.strip_edges()
	ApiClient.llm_api_url = _cfg_llm_url.text.strip_edges()
	ApiClient.llm_api_key = _cfg_llm_key.text.strip_edges()
	ApiClient.llm_model = _cfg_llm_model.text.strip_edges()
	
	# Update indicator
	_api_mode_indicator.text = "后端模式" if ApiClient.api_mode == "backend" else "独立模式"
	_api_mode_indicator.add_theme_color_override("font_color", BORDER_GOLD if ApiClient.api_mode == "backend" else ACCENT_PURPLE)
	
	_toggle_config_panel()


func _test_backend() -> void:
	_backend_test_result.text = "⏳ 测试中..."
	_backend_test_result.add_theme_color_override("font_color", DIM)
	
	var ok: bool = await ApiClient.test_backend()
	if ok:
		_backend_test_result.text = "✅ 后端连接成功"
		_backend_test_result.add_theme_color_override("font_color", ACCENT_GREEN)
	else:
		_backend_test_result.text = "❌ 后端连接失败"
		_backend_test_result.add_theme_color_override("font_color", ACCENT_RED)


func _test_llm() -> void:
	_llm_test_result.text = "⏳ 测试中..."
	_llm_test_result.add_theme_color_override("font_color", DIM)
	
	var ok: bool = await ApiClient.test_llm()
	if ok:
		_llm_test_result.text = "✅ LLM连接成功"
		_llm_test_result.add_theme_color_override("font_color", ACCENT_GREEN)
	else:
		_llm_test_result.text = "❌ LLM连接失败"
		_llm_test_result.add_theme_color_override("font_color", ACCENT_RED)


func _update_api_mode_indicator() -> void:
	_api_mode_indicator.text = "后端模式" if ApiClient.api_mode == "backend" else "独立模式"
	_api_mode_indicator.add_theme_color_override("font_color", BORDER_GOLD if ApiClient.api_mode == "backend" else ACCENT_PURPLE)
