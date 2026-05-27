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

# HUD
var _vigor_bar: ProgressBar ; var _vigor_label: Label
var _spirit_bar: ProgressBar ; var _spirit_label: Label
var _coins_label: Label
var _time_label: Label ; var _weather_label: Label ; var _map_name_label: Label
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
	_config_panel.build(self, _on_api_indicator_updated)

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
#  Login — 登录界面 (委托给 UIBuilder)
# ═══════════════════════════════════════════════════════
func _build_login() -> void:
	_login_overlay = _ui_builder.build_login(
		self,
		func(nm, g, pd): GameManager.hello(nm, g, pd),
		func(): _show_load_dialog(),
		func(): _config_panel.toggle(),
		func(): _test_center.show_test_center(self, func(text, err=false): _msg_display.add_system_msg_ex(text, err)),
		func(): _shutdown_service.confirm_and_execute(self)
	)


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
					GameManager.player_id = ""
					_game_ui.visible = false
					_login_overlay.visible = true
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

	_msg_display.add_chat(GameColors.TEXT, "", "[right]%s[/right]" % text)
	_msg_input.clear()
	_is_streaming = true
	_send_btn.disabled = true

	var ok: bool = await GameManager.talk_to_npc(npc_id, text)
	_is_streaming = false
	_send_btn.disabled = false
	_msg_input.grab_focus()


func _on_npc_reply(speaker: String, message: String, _npc_id: String) -> void:
	_msg_display.add_chat(GameColors.ACCENT2, speaker, message)


func _on_sys_msg(text: String) -> void:
	_msg_display.add_system_msg(text)


# ═══════════════════════════════════════════════════════
#  Refresh — 状态刷新主循环
# ═══════════════════════════════════════════════════════
func _refresh() -> void:
	if not _game_ui.visible:
		print("[Game] _refresh() — _game_ui NOT visible, returning")
		return
	var gm = GameManager
	print("[Game] _refresh() — map_id: %s, maps_data keys: %s" % [gm.player_map_id, str(gm.maps_data.keys())])

	# Map - detect change or first load
	var current_renderer_map: String = _map_renderer.get_current_map_id() if _map_renderer else ""
	if gm.player_map_id != current_renderer_map:
		print("[Game] _refresh() — building map (changed from '%s' to '%s')" % [current_renderer_map, gm.player_map_id])
		_build_map()
	_update_map_player()
	elif gm.maps_data.is_empty():
		print("[Game] _refresh() — maps_data is EMPTY, skipping map build")
	else:
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
			var entry := UIBuilder.npc_entry(n.get("name", n.get("id","?")), n.get("id",""))
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
		var l := UIBuilder.lbl("身无长物", 12, Color(0.4,0.4,0.4)); _inventory_flow.add_child(l)
	else:
		for item in gm.player_inventory:
			_inventory_flow.add_child(UIBuilder.lbl("%s×%d" % [item, gm.player_inventory[item]], 12, GameColors.GOLD))

	# Favor
	for c in _favor_vbox.get_children(): c.queue_free()
	if not gm.player_favor.is_empty():
		for nid in gm.player_favor:
			var val: int = gm.player_favor[nid]
			var nm: String = gm.npc_labels.get(nid, nid)
			_favor_vbox.add_child(UIBuilder.lbl("%s: %+d" % [nm, val], 11,
				GameColors.GREEN if val >= 0 else GameColors.RED))

	# Portals
	for c in _portal_list_container.get_children(): c.queue_free()
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
