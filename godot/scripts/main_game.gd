extends Control
## 活纸 · 江湖行纪 — Godot 桌面版 (模块化重构版)
## Main Game Controller — 核心游戏逻辑、事件处理、状态刷新
##
## 已拆分的模块:
##   - GameColors      → 颜色主题常量 (Autoload)
##   - UIBuilder       → UI 构建 + 样式辅助
##   - ConfigPanel     → API 配置面板
##   - TestCenter      → 测试中心
##   - ShutdownService → 关闭服务
##   - DialogManager   → 对话框/确认框
##   - MessageDisplay  → 消息显示系统
##
## 本文件保留:
##   - 节点引用管理
##   - _ready() 初始化与信号连接
##   - 登录/登出状态切换
##   - 地图渲染调度
##   - 对话发送/接收
##   - _refresh() 状态刷新主循环
##   - 模块间协调
##
## 依赖 Autoload: ApiClient, GameManager, GameColors

# ═══════════════════════════════════════════════════════
#  Module Instances — 模块实例
# ═══════════════════════════════════════════════════════
var _ui_builder: UIBuilder
var _config_panel: ConfigPanel
var _test_center: TestCenter
var _shutdown_service: ShutdownService
var _dialog_manager: DialogManager
var _msg_display: MessageDisplay

# ═══════════════════════════════════════════════════════
#  Node Refs — 节点引用 (由 UIBuilder.build_game_ui 返回)
# ═══════════════════════════════════════════════════════
var _login_overlay: Control
var _game_ui: Control
var _start_btn: Button

# Map
var _map_renderer: Node2D
var _map_sub_vp: SubViewportContainer
var _map_sub: SubViewport

# Dialogue
var _dialogue_label: RichTextLabel
var _chat_scroll: ScrollContainer
var _npc_select: OptionButton
var _msg_input: LineEdit
var _send_btn: Button
var _is_streaming: bool = false
var _stream_text: String = ""
var _stream_npc_msg_index: int = -1
var _stream_npc_name: String = ""

# HUD
var _vigor_bar: ProgressBar ; var _vigor_label: Label
var _spirit_bar: ProgressBar ; var _spirit_label: Label
var _coins_label: Label
var _time_label: Label ; var _weather_label: Label ; var _map_name_label: Label ; var _map_title_label: Label
var _inventory_flow: HFlowContainer
var _favor_vbox: VBoxContainer
var _npc_list_container: VBoxContainer
var _portal_list_container: VBoxContainer
var _api_mode_indicator: Label


func _ready() -> void:
	_init_modules()

	# Dark BG
	var bg := ColorRect.new(); bg.color = GameColors.BG_DARK
	bg.set_anchors_preset(PRESET_FULL_RECT); add_child(bg)

	_build_login()
	_build_game_ui()
	_config_panel.build(self, _on_api_mode_updated)

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
	ApiClient.stream_chunk.connect(_on_stream_chunk)
	ApiClient.stream_done.connect(_on_stream_done)


## 初始化所有子模块
func _init_modules() -> void:
	_ui_builder = UIBuilder.new()
	_config_panel = ConfigPanel.new()
	_test_center = TestCenter.new()
	_shutdown_service = ShutdownService.new()
	_dialog_manager = DialogManager.new()
	_msg_display = MessageDisplay.new()

	_shutdown_service.init(func(title, msg, on_confirm):
		_dialog_manager.show_confirm(self, title, msg, on_confirm)
	)


func _logged_in_deferred() -> void:
	await get_tree().process_frame
	await get_tree().process_frame
	for c in _game_ui.get_children():
		if c is VBoxContainer:
			for gc in c.get_children():
				if gc is HSplitContainer:
					gc.split_offset = -340
					print("[Game] HSplitContainer size=%s children=%d" % [str(gc.size), gc.get_child_count()])
					for hgc in gc.get_children():
						print("[Game]   child name=%s size=%s cm=%s sf_h=%d sf_v=%d" % [hgc.name, str(hgc.size), str(hgc.custom_minimum_size), hgc.size_flags_horizontal, hgc.size_flags_vertical])
	print("[Game] _logged_in_deferred — sizes: game_ui=%s, self=%s" % [str(_game_ui.size), str(size)])
	print("[Game] _npc_select is null: %s" % str(_npc_select == null))
	_update_api_mode_indicator()
	_refresh()


# ═══════════════════════════════════════════════════════
#  Login — 登录界面 (委托给 UIBuilder)
# ═══════════════════════════════════════════════════════
func _build_login() -> void:
	_login_overlay = _ui_builder.build_login(
		self,
		func(nm, g, pd): _on_start_pressed(nm, g, pd),
		func(): _show_load_dialog(),
		func(): _config_panel.toggle(),
		func(): _test_center.show_test_center(self, func(text, err=false): _msg_display.add_system_msg_ex(text, err)),
		func(): _shutdown_service.confirm_and_execute(self)
	)
	_start_btn = _ui_builder.start_btn


func _on_start_pressed(nm: String, g: String, pd: bool) -> void:
	await GameManager.hello(nm, g, pd)
	if _login_overlay and _login_overlay.visible:
		if _start_btn and is_instance_valid(_start_btn):
			_start_btn.text = "踏入江湖"
			_start_btn.disabled = false


func _show_load_dialog() -> void:
	var saves: Array = await GameManager.list_saves()
	_ui_builder.build_load_dialog(self, saves,
		func(pid): GameManager.load_player(pid),
		func(): pass
	)


# ═══════════════════════════════════════════════════════
#  Game UI — 游戏主界面 (委托给 UIBuilder)
# ═══════════════════════════════════════════════════════
func _build_game_ui() -> void:
	var refs := _ui_builder.build_game_ui(
		self,
		func(x, y): GameManager.move_player(x, y),
		func(nid, nname):
			for idx in _npc_select.item_count:
				if _npc_select.get_item_text(idx) == nname:
					_npc_select.select(idx)
					_msg_input.grab_focus()
					return
		,
		func(): _on_send(),
		func():
			await GameManager.save_game()
			_msg_display.add_system_msg("💾 存档已落纸")
		,
		func():
			_dialog_manager.show_confirm(self,
				"退出游戏",
				"确定要退出游戏吗？\n\n[color=yellow]⚠️ 未存档的进度将丢失[/color]",
				func():
					await GameManager.save_game()
					GameManager.reset_state()
			)
		,
		func(): _config_panel.toggle()
	)

	# Unpack references from builder
	_game_ui = refs["game_ui"]
	_map_renderer = refs["map_renderer"]
	_map_sub_vp = refs["map_sub_vp"]
	_map_sub = refs["map_sub"]
	_dialogue_label = refs["dialogue_label"]
	_chat_scroll = refs["chat_scroll"]
	_npc_select = refs["npc_select"]
	_msg_input = refs["msg_input"]
	_send_btn = refs["send_btn"]
	_vigor_bar = refs["vigor_bar"]
	_vigor_label = refs["vigor_label"]
	_spirit_bar = refs["spirit_bar"]
	_spirit_label = refs["spirit_label"]
	_coins_label = refs["coins_label"]
	_time_label = refs["time_label"]
	_weather_label = refs["weather_label"]
	_map_name_label = refs["map_name_label"]
	_map_title_label = refs["map_title_label"]
	_inventory_flow = refs["inventory_flow"]
	_favor_vbox = refs["favor_vbox"]
	_npc_list_container = refs["npc_list_container"]
	_portal_list_container = refs["portal_list_container"]
	_api_mode_indicator = refs["api_mode_indicator"]

	# Initialize message display with dialogue nodes
	_msg_display.init(_dialogue_label, _chat_scroll)


# ═══════════════════════════════════════════════════════
#  Map Rendering — 地图渲染
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
#  Dialogue — 对话系统
# ═══════════════════════════════════════════════════════
var _stream_timeout_msec: int = 0
const STREAM_TIMEOUT_MSEC: int = 120000

func _on_send() -> void:
	if _is_streaming: return
	var text := _msg_input.text.strip_edges()
	if text == "": return

	var idx := _npc_select.selected
	if idx < 0:
		_msg_display.add_system_msg("请先选择一位人物")
		return
	var npcs := GameManager.npcs_here
	if idx >= npcs.size(): return

	var npc_id: String = npcs[idx].get("id","")
	var npc_name: String = npcs[idx].get("name", npc_id)

	_msg_display.add_chat(GameColors.TEXT, "", "[right]%s[/right]" % text)
	_msg_input.clear()
	_is_streaming = true
	_send_btn.disabled = true
	GameManager.is_streaming = true
	_stream_timeout_msec = Time.get_ticks_msec()

	_msg_display.add_chat(GameColors.ACCENT2, npc_name, "...")
	var npc_msg_index: int = _msg_display.msg_count() - 1

	_stream_text = ""
	_stream_npc_msg_index = npc_msg_index
	_stream_npc_name = npc_name

	ApiClient.talk_stream(npc_id, text)


func _on_stream_chunk(text: String) -> void:
	if not _is_streaming: return
	if _stream_timeout_msec > 0 and (Time.get_ticks_msec() - _stream_timeout_msec) > STREAM_TIMEOUT_MSEC:
		_on_stream_done({"error": "对话超时，请重试"})
		return
	_stream_text += text
	var bb := "[b][color=#%s]%s[/color][/b]\n%s" % [GameColors.ACCENT2.to_html(false), _stream_npc_name.replace("[", "[lb]"), _stream_text.replace("[", "[lb]")]
	_msg_display.update_msg(_stream_npc_msg_index, bb)


func _on_stream_done(data: Dictionary) -> void:
	if not _is_streaming: return

	if data.has("error"):
		_stream_text += "\n[错误] " + str(data.error)
		var bb := "[b][color=#%s]%s[/color][/b]\n%s" % [GameColors.ACCENT2.to_html(false), _stream_npc_name.replace("[", "[lb]"), _stream_text.replace("[", "[lb]")]
		_msg_display.update_msg(_stream_npc_msg_index, bb)
	elif _stream_text == "":
		_msg_display.update_msg(_stream_npc_msg_index, "[b][color=#%s]%s[/color][/b]\n（无回复）" % [GameColors.ACCENT2.to_html(false), _stream_npc_name.replace("[", "[lb]")])

	_is_streaming = false
	_send_btn.disabled = false
	_msg_input.grab_focus()
	GameManager.is_streaming = false

	GameManager.apply_stream_result(data)

	if not data.has("player"):
		GameManager.fetch_state()


func _on_npc_reply(speaker: String, message: String, _npc_id: String) -> void:
	_msg_display.add_chat(GameColors.ACCENT2, speaker, message)


func _on_sys_msg(text: String) -> void:
	_msg_display.add_system_msg(text)


# ═══════════════════════════════════════════════════════
#  Refresh — 状态刷新主循环
# ═══════════════════════════════════════════════════════
func _refresh() -> void:
	if not _game_ui.visible:
		return
	var gm = GameManager

	var current_renderer_map: String = _map_renderer.get_current_map_id() if _map_renderer else ""
	if gm.player_map_id != current_renderer_map:
		_build_map()
	_update_map_player()
	elif gm.maps_data.is_empty():
		pass
	else:
		_update_map_player()

	# NPC select dropdown — 仅在列表变化时重建
	if _npc_select:
		var need_rebuild := false
		if _npc_select.item_count != gm.npcs_here.size():
			need_rebuild = true
		else:
			for i in gm.npcs_here.size():
				if _npc_select.get_item_text(i) != gm.npcs_here[i].get("name", gm.npcs_here[i].get("id","?")):
					need_rebuild = true
					break
		if need_rebuild:
			var cur_idx := _npc_select.selected
			_npc_select.clear()
			for n in gm.npcs_here:
				_npc_select.add_item(n.get("name", n.get("id","?")))
			if cur_idx >= 0 and cur_idx < _npc_select.item_count:
				_npc_select.select(cur_idx)

	# NPC list in sidebar — 增量 diff
	if _npc_list_container:
		var existing_names: Dictionary = {}
		for c in _npc_list_container.get_children():
			if is_instance_valid(c):
				existing_names[c.name] = c
		var desired_names: Dictionary = {}
		var npc_idx := 0
		for n in gm.npcs_here:
			var npc_id := n.get("id", "")
			var node_name := "NpcEntry_%s" % npc_id
			desired_names[node_name] = true
			if not existing_names.has(node_name):
				var idx := npc_idx
				var entry := UIBuilder.npc_entry(n.get("name", n.get("id","?")), npc_id, func():
					if idx < _npc_select.item_count:
						_npc_select.select(idx)
						gm.selected_npc_id = npc_id
						_msg_input.grab_focus()
				)
				entry.name = node_name
				_npc_list_container.add_child(entry)
			npc_idx += 1
		for node_name in existing_names:
			if not desired_names.has(node_name):
				existing_names[node_name].queue_free()

	# HUD bars & labels
	_vigor_bar.max_value = gm.player_vigor_max; _animate_bar(_vigor_bar, gm.player_vigor)
	_vigor_label.text = "%d/%d" % [gm.player_vigor, gm.player_vigor_max]
	_spirit_bar.max_value = gm.player_spirit_max; _animate_bar(_spirit_bar, gm.player_spirit)
	_spirit_label.text = "%d/%d" % [gm.player_spirit, gm.player_spirit_max]
	_coins_label.text = "💰 %d文" % gm.player_coins
	var time_icon := "🌙" if gm.player_world_is_night else "☀️"
	_time_label.text = "%s %s · 第%d天" % [time_icon, gm.player_world_shichen, gm.player_world_day]
	_weather_label.text = "🌤 %s" % gm.player_weather
	var mname = gm.maps_data.get(gm.player_map_id,{}).get("name", gm.player_map_id)
	_map_name_label.text = "📍 %s(%d,%d)" % [mname, gm.player_px, gm.player_py]
	_map_title_label.text = mname

	# Inventory — 增量 diff
	if _inventory_flow:
		var existing_inv: Dictionary = {}
		for c in _inventory_flow.get_children():
			if is_instance_valid(c):
				existing_inv[c.name] = c
		if gm.player_inventory.is_empty():
			if not existing_inv.has("InvEmpty"):
				for c_name in existing_inv:
					existing_inv[c_name].queue_free()
				var l := UIBuilder.lbl("身无长物", 12, Color(0.4,0.4,0.4))
				l.name = "InvEmpty"
				_inventory_flow.add_child(l)
		else:
			if existing_inv.has("InvEmpty"):
				existing_inv["InvEmpty"].queue_free()
				existing_inv.erase("InvEmpty")
			var desired_inv: Dictionary = {}
			for item in gm.player_inventory:
				var node_name := "Inv_%s" % item
				desired_inv[node_name] = true
				if existing_inv.has(node_name):
					var lbl: Label = existing_inv[node_name]
					if is_instance_valid(lbl):
						lbl.text = "%s×%d" % [item, gm.player_inventory[item]]
				else:
					var lbl := UIBuilder.lbl("%s×%d" % [item, gm.player_inventory[item]], 12, GameColors.GOLD)
					lbl.name = node_name
					_inventory_flow.add_child(lbl)
			for c_name in existing_inv:
				if not desired_inv.has(c_name):
					existing_inv[c_name].queue_free()

	# Favor — 增量 diff
	if _favor_vbox:
		var existing_fav: Dictionary = {}
		for c in _favor_vbox.get_children():
			if is_instance_valid(c):
				existing_fav[c.name] = c
		if gm.player_favor.is_empty():
			for c_name in existing_fav:
				existing_fav[c_name].queue_free()
		else:
			var desired_fav: Dictionary = {}
			for nid in gm.player_favor:
				var val: int = gm.player_favor[nid]
				var nm: String = gm.npc_labels.get(nid, nid)
				var node_name := "Fav_%s" % nid
				desired_fav[node_name] = true
				if existing_fav.has(node_name):
					var lbl: Label = existing_fav[node_name]
					if is_instance_valid(lbl):
						lbl.text = "%s: %+d" % [nm, val]
						lbl.add_theme_color_override("font_color", GameColors.GREEN if val >= 0 else GameColors.RED)
				else:
					var lbl := UIBuilder.lbl("%s: %+d" % [nm, val], 11, GameColors.GREEN if val >= 0 else GameColors.RED)
					lbl.name = node_name
					_favor_vbox.add_child(lbl)
			for c_name in existing_fav:
				if not desired_fav.has(c_name):
					existing_fav[c_name].queue_free()

	# Portals — 仅在地图变化时重建（界门与地图绑定）
	if _portal_list_container and (gm.player_map_id != current_renderer_map or _portal_list_container.get_child_count() == 0):
		for c in _portal_list_container.get_children():
			c.queue_free()
		var map_info: Dictionary = gm.maps_data.get(gm.player_map_id, {})
		var portals: Array = map_info.get("portals", [])
		if portals.is_empty():
			var empty_label := UIBuilder.lbl("此地图无界门", 11, GameColors.DIM)
			_portal_list_container.add_child(empty_label)
		else:
			for pt in portals:
				var target_map_id: String = pt.get("target_map_id", "")
				var target_map_info: Dictionary = gm.maps_data.get(target_map_id, {})
				var target_name: String = target_map_info.get("name", target_map_id)
				var to_x: int = pt.get("to_x", 0)
				var to_y: int = pt.get("to_y", 0)

				var portal_btn := UIBuilder.btn("↗ 往【%s】(%d,%d)" % [target_name, to_x, to_y], GameColors.ACCENT_BLUE)
				portal_btn.pressed.connect(func(x=to_x, y=to_y): gm.move_player(x, y))
				_portal_list_container.add_child(portal_btn)


# ═══════════════════════════════════════════════════════
#  API Mode Indicator — API模式指示器更新回调
# ═══════════════════════════════════════════════════════
func _unhandled_input(event: InputEvent) -> void:
	if not _game_ui.visible or _is_streaming or GameManager._is_moving:
		return
	if _msg_input and _msg_input.has_focus():
		return
	if _npc_select and _npc_select.has_focus():
		return
	var dx := 0
	var dy := 0
	if event.is_action_pressed("ui_up"):
		dy = -1
	elif event.is_action_pressed("ui_down"):
		dy = 1
	elif event.is_action_pressed("ui_left"):
		dx = -1
	elif event.is_action_pressed("ui_right"):
		dx = 1
	else:
		return
	get_viewport().set_input_as_handled()
	GameManager.move_player(GameManager.player_px + dx, GameManager.player_py + dy)


var _bar_tweens: Dictionary = {}

func _animate_bar(bar: ProgressBar, new_value: float) -> void:
	if absf(bar.value - new_value) < 0.5:
		bar.value = new_value
		return
	var bar_id := bar.name
	if _bar_tweens.has(bar_id) and is_instance_valid(_bar_tweens[bar_id]):
		_bar_tweens[bar_id].kill()
	var tween := create_tween()
	_bar_tweens[bar_id] = tween
	tween.tween_property(bar, "value", new_value, 0.3).set_trans(Tween.TRANS_SINE)


func _on_api_mode_updated(new_text: String, new_color: Color) -> void:
	_api_mode_indicator.text = new_text
	_api_mode_indicator.add_theme_color_override("font_color", new_color)


func _update_api_mode_indicator() -> void:
	_api_mode_indicator.text = "后端模式" if ApiClient.api_mode == "backend" else "独立模式"
	_api_mode_indicator.add_theme_color_override("font_color",
		GameColors.BORDER_GOLD if ApiClient.api_mode == "backend" else GameColors.ACCENT_PURPLE)


# ═══════════════════════════════════════════════════════
#  Public API — 供外部模块调用的接口
# ═══════════════════════════════════════════════════════

## 兼容旧接口：显示确认对话框 (委托给 DialogManager)
func show_confirm(title: String, message: String, on_confirm: Callable) -> void:
	_dialog_manager.show_confirm(self, title, message, on_confirm)


## 兼容旧接口：添加系统消息 (委托给 MessageDisplay)
func add_system_msg(text: String, is_error: bool = false) -> void:
	_msg_display.add_system_msg_ex(text, is_error)
