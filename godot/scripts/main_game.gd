extends Control
## 活纸 · 江湖行纪 — Godot 桌面版
## 单文件 UI，程序化构建全部界面元素。
## 布局对齐 Web 版：两栏（地图主视区 | 侧栏 360px）
## 依赖 Autoload: ApiClient, GameManager

# ═══════════════════════════════════════════════════════
#  Color Theme
# ═══════════════════════════════════════════════════════
const BG_DARK  := Color(0.06, 0.06, 0.12)
const BG_PANEL := Color(0.09, 0.11, 0.20)
const BG_CARD  := Color(0.11, 0.14, 0.24)
const BG_CARD_HOVER := Color(0.14, 0.18, 0.30)
const BORDER   := Color(0.20, 0.24, 0.38)
const BORDER_SUBTLE := Color(0.15, 0.18, 0.28)
const TEXT     := Color(0.90, 0.90, 0.92)
const DIM      := Color(0.50, 0.52, 0.64)
const ACCENT   := Color(0.35, 0.78, 0.98)
const ACCENT2  := Color(1.0, 0.45, 0.28)
const GREEN    := Color(0.38, 0.78, 0.42)
const GOLD     := Color(1.0, 0.82, 0.08)
const RED      := Color(0.92, 0.32, 0.30)

# ═══════════════════════════════════════════════════════
#  Map Tile Colors
# ═══════════════════════════════════════════════════════
const TILE_COLORS := {
	"#": Color(0.15,0.12,0.10), ".": Color(0.25,0.24,0.22),
	"~": Color(0.10,0.30,0.50), "=": Color(0.35,0.30,0.20),
	"F": Color(0.10,0.35,0.15), "m": Color(0.30,0.25,0.15),
	";": Color(0.50,0.45,0.10), "/": Color(0.35,0.30,0.20),
	"T": Color(0.60,0.40,0.10), "Y": Color(0.10,0.50,0.60),
	"I": Color(0.40,0.15,0.30), "M": Color(0.60,0.50,0.10),
	"B": Color(0.50,0.20,0.20), "C": Color(0.55,0.30,0.55),
	" ": Color(0.04,0.04,0.07),
}
const TILE_SIZE := 14

# ═══════════════════════════════════════════════════════
#  Node Refs (set in _ready / _build_game_ui)
# ═══════════════════════════════════════════════════════
var _login_overlay: Control
var _game_ui: Control

# Map
var _map_scroll: ScrollContainer
var _map_container: Control
var _map_cells: Array[Dictionary] = []
var _current_map_id: String = ""
var _map_rows: Array = []
var _map_cols: int = 72

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


func _ready() -> void:
	# Dark BG
	var bg := ColorRect.new(); bg.color = BG_DARK
	bg.set_anchors_preset(PRESET_FULL_RECT); add_child(bg)

	_build_login()
	_build_game_ui()
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
	print("[Game] _logged_in_deferred — sizes: game_ui=%s, self=%s" % [str(_game_ui.size), str(size)])
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

	var box := Panel.new()
	box.set_anchors_preset(PRESET_FULL_RECT)
	_add_panel_style(box)
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
	_game_ui = Control.new()
	_game_ui.set_anchors_preset(PRESET_FULL_RECT)
	add_child(_game_ui)

	# ═══ Top Bar (fixed height 40px) ═══
	var topbar := Panel.new()
	topbar.set_anchors_and_offsets_preset(PRESET_TOP_WIDE, PRESET_MODE_MINSIZE, 0)
	topbar.custom_minimum_size = Vector2(0, 40)
	_add_panel_style(topbar)
	_game_ui.add_child(topbar)

	var top_hb := HBoxContainer.new()
	top_hb.add_theme_constant_override("separation", 16)
	top_hb.set_anchors_preset(PRESET_FULL_RECT)
	topbar.add_child(top_hb)
	top_hb.add_child(_lbl("🏮 活纸 · 江湖行纪", 16, ACCENT))
	top_hb.add_child(Control.new())  # spacer

	var save_btn := _btn("💾 存档", Color(0.4,0.6,0.3))
	save_btn.pressed.connect(func():
		await GameManager.save_game()
		_on_sys_msg("💾 存档已落纸")
	)
	top_hb.add_child(save_btn)

	var quit_btn := _btn("🚪 退出", Color(0.6,0.3,0.3))
	quit_btn.pressed.connect(func():
		await GameManager.save_game()
		GameManager.player_id = ""
		_game_ui.visible = false
		_login_overlay.visible = true
	)
	top_hb.add_child(quit_btn)

	# ═══ Main Area: 2-column HSplitContainer ═══
	var main_mc := MarginContainer.new()
	main_mc.set_anchors_and_offsets_preset(PRESET_FULL_RECT)
	main_mc.add_theme_constant_override("margin_top", 40)
	_game_ui.add_child(main_mc)

	var hsplit := HSplitContainer.new()
	hsplit.set_anchors_preset(PRESET_FULL_RECT)
	hsplit.dragger_visibility = HSplitContainer.DRAGGER_HIDDEN
	hsplit.split_offset = -360  # negative → right child gets ~360px
	main_mc.add_child(hsplit)

	# ═══ LEFT: Map Panel (flex:1, fills available space) ═══
	var map_panel := VBoxContainer.new()
	map_panel.size_flags_horizontal = SIZE_EXPAND_FILL
	map_panel.size_flags_vertical = SIZE_EXPAND_FILL
	hsplit.add_child(map_panel)

	# Map title bar
	var map_title := Panel.new()
	map_title.custom_minimum_size = Vector2(0, 28)
	var mt_sb := StyleBoxFlat.new()
	mt_sb.bg_color = BG_PANEL
	mt_sb.border_width_bottom = 1; mt_sb.border_color = BORDER
	mt_sb.content_margin_left = 12; mt_sb.content_margin_right = 12
	mt_sb.content_margin_top = 4; mt_sb.content_margin_bottom = 4
	map_title.add_theme_stylebox_override("panel", mt_sb)
	map_panel.add_child(map_title)
	var mt_hb := HBoxContainer.new()
	mt_hb.set_anchors_preset(PRESET_FULL_RECT); map_title.add_child(mt_hb)
	mt_hb.add_child(_lbl("🗺️ 地图", 13, ACCENT, HORIZONTAL_ALIGNMENT_LEFT))
	mt_hb.add_child(Control.new())
	_map_name_label = _lbl("--", 11, DIM)  # reuse as map name in title bar
	mt_hb.add_child(_map_name_label)

	# Map scroll container (fills remaining space)
	_map_scroll = ScrollContainer.new()
	_map_scroll.size_flags_horizontal = SIZE_EXPAND_FILL
	_map_scroll.size_flags_vertical = SIZE_EXPAND_FILL
	map_panel.add_child(_map_scroll)

	# Map content container (plain Control with dark bg)
	_map_container = Control.new()
	var map_bg := ColorRect.new()
	map_bg.name = "MapBackground"
	map_bg.color = BG_DARK
	map_bg.set_anchors_preset(PRESET_FULL_RECT)
	_map_container.add_child(map_bg)
	_map_scroll.add_child(_map_container)

	# ═══ RIGHT: Side Panel (card-based sections) ═══
	var side_panel := VBoxContainer.new()
	side_panel.custom_minimum_size = Vector2(340, 0)
	side_panel.add_theme_constant_override("separation", 6)
	side_panel.size_flags_vertical = SIZE_EXPAND_FILL
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
	var npc_card := _make_card("👥 身边人物")
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

	# ─── Card 5: Dialogue (bottom, fixed ~240px) ───
	var dlg_card := Panel.new()
	dlg_card.custom_minimum_size = Vector2(0, 240)
	dlg_card.size_flags_vertical = SIZE_SHRINK_END
	var dc_sb := StyleBoxFlat.new(); dc_sb.bg_color = BG_PANEL
	dc_sb.set_corner_radius_all(6)
	dc_sb.border_width_all = 1; dc_sb.border_color = BORDER
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
	for c in _map_cells: c["node"].queue_free()
	_map_cells.clear()

	_current_map_id = GameManager.player_map_id
	print("[Game] _build_map() — id=%s" % _current_map_id)
	var info = GameManager.maps_data.get(_current_map_id, {})
	_map_rows = info.get("rows", [])
	if _map_rows.is_empty():
		print("[Game] _build_map() — rows EMPTY!")
		return
	_map_cols = _map_rows[0].length()
	var total_w := _map_cols * TILE_SIZE
	var total_h := _map_rows.size() * TILE_SIZE
	print("[Game] _build_map() — %d×%d tiles, total=(%d,%d)" % [_map_rows.size(), _map_cols, total_w, total_h])

	# Set map container size directly (it's a plain Control)
	_map_container.set_size(Vector2(total_w, total_h))

	for y in _map_rows.size():
		var row: String = _map_rows[y]
		for x in _map_cols:
			var ch := " " if x >= row.length() else row[x]
			var tile := ColorRect.new()
			tile.color = TILE_COLORS.get(ch, Color(0.2,0.2,0.2))
			tile.set_position(Vector2(x * TILE_SIZE, y * TILE_SIZE))
			tile.set_size(Vector2(TILE_SIZE, TILE_SIZE))
			tile.mouse_filter = Control.MOUSE_FILTER_STOP
			tile.gui_input.connect(_on_tile_click.bind(x, y))
			_map_container.add_child(tile)
			_map_cells.append({"node":tile, "x":x, "y":y, "ch":ch})

	print("[Game] _build_map() — created %d tiles" % _map_cells.size())


func _update_map_player() -> void:
	var px := GameManager.player_px; var py := GameManager.player_py

	# NPC 坐标索引
	var npc_at := {}
	for n in GameManager.npc_catalog:
		if n.get("map", "") == _current_map_id:
			npc_at[Vector2i(n.get("x", -1), n.get("y", -1))] = n

	for e in _map_cells:
		var tile: ColorRect = e["node"]
		var ex: int = e["x"]; var ey: int = e["y"]
		if ex == px and ey == py:
			tile.color = ACCENT
		elif npc_at.has(Vector2i(ex, ey)):
			tile.color = ACCENT2
		else:
			tile.color = TILE_COLORS.get(e["ch"], Color(0.2,0.2,0.2))


func _on_tile_click(ev: InputEvent, x: int, y: int) -> void:
	if ev is InputEventMouseButton and ev.pressed:
		if ev.button_index == MOUSE_BUTTON_LEFT:
			for n in GameManager.npc_catalog:
				if n.get("map", "") == _current_map_id and n.get("x", -1) == x and n.get("y", -1) == y:
					for idx in _npc_select.item_count:
						if _npc_select.get_item_text(idx) == n.get("name", ""):
							_npc_select.select(idx)
							_msg_input.grab_focus()
							return
			GameManager.move_player(x, y)


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
	print("[Game] _refresh() — map_id: cur=%s gm=%s" % [_current_map_id, gm.player_map_id])

	# Map
	if gm.player_map_id != _current_map_id:
		_build_map()
	_update_map_player()

	# NPC select dropdown
	var cur_idx := _npc_select.selected
	_npc_select.clear()
	for n in gm.npcs_here:
		_npc_select.add_item(n.get("name", n.get("id","?")))
	if cur_idx >= 0 and cur_idx < _npc_select.item_count:
		_npc_select.select(cur_idx)

	# NPC list in sidebar
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


# ═══════════════════════════════════════════════════════
#  Style Helpers
# ═══════════════════════════════════════════════════════
func _add_panel_style(p: Panel) -> void:
	var sb := StyleBoxFlat.new()
	sb.bg_color = BG_PANEL
	sb.set_corner_radius_all(6)
	sb.border_width_all = 1; sb.border_color = BORDER
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
	sb.border_width_all = 1; sb.border_color = BORDER_SUBTLE
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
