extends Node
## Central game state — autoload singleton.
## Holds player data, map data, NPC info, and coordinates UI updates.

# ── Player State ──
var player_id: String = ""
var display_name: String = ""

var player_map_id: String = "world"
var player_px: int = 16
var player_py: int = 30
var player_coins: int = 120
var player_vigor: int = 80
var player_vigor_max: int = 100
var player_spirit: int = 80
var player_spirit_max: int = 100
var player_gender: String = ""
var player_permadeath: bool = false
var player_dead: bool = false
var player_ended: bool = false
var player_ending_label: String = ""
var player_inventory: Dictionary = {}
var player_reputation: Dictionary = {}
var player_flags: Dictionary = {}
var player_favor: Dictionary = {}
var player_world_day: int = 1
var player_world_shichen: String = "午时"
var player_world_is_night: bool = false
var player_weather: String = "薄阴"
var player_move_locked: bool = false
var player_trap_reason: String = ""
var player_enslaved: bool = false
var player_death_reason: String = ""
var player_unconscious_ticks: int = 0
var player_bounties: Array = []
var _is_moving: bool = false
var selected_npc_id: String = ""
var is_streaming: bool = false

# ── World Data ──
var maps_data: Dictionary = {}
var map_locations: Dictionary = {}
var npcs_here: Array = []
var npc_labels: Dictionary = {}
var npc_catalog: Array = []
var npc_states: Dictionary = {}
var intro_text: String = ""

# ── UI Signals ──
signal state_updated()
signal map_pos_changed()
signal chat_message(speaker: String, message: String, npc_id: String)
signal system_message(text: String)
signal logged_in()
signal logged_out()

# ── Config ──
@export var backend_url: String = ""

var _poll_timer: Timer = null

func _ready() -> void:
	_poll_timer = Timer.new()
	_poll_timer.wait_time = 30.0
	_poll_timer.one_shot = false
	_poll_timer.timeout.connect(_on_poll_timeout)
	add_child(_poll_timer)
	_poll_timer.start()

func _on_poll_timeout() -> void:
	if player_id.is_empty() or _is_moving or is_streaming:
		return
	fetch_state()


func hello(p_name: String, p_gender: String, p_permadeath: bool) -> void:
	## Start a new game.
	print("[GM] hello() called: name=%s gender=%s permadeath=%s" % [p_name, p_gender, p_permadeath])
	player_id = "godot_%d_%d" % [Time.get_unix_time_from_system(), Time.get_ticks_usec() % 100000]
	display_name = p_name

	var body := {
		"player_id": player_id,
		"display_name": display_name,
		"gender": p_gender,
		"permadeath": p_permadeath,
	}
	print("[GM] sending /api/hello request...")
	var res: Dictionary = await ApiClient.request("/api/hello", "POST", body)
	print("[GM] /api/hello response: %s" % JSON.stringify(res))

	if res.has("error"):
		print("[GM] hello() ERROR: %s" % res.get("error", "?"))
		system_message.emit("连接后端失败: %s" % res.get("error", "?"))
		return

	_apply_hello_response(res)
	logged_in.emit()


func load_player(save_pid: String) -> void:
	## Load an existing save.
	player_id = save_pid
	var body := {"player_id": save_pid}
	var res: Dictionary = await ApiClient.request("/api/load", "POST", body)

	if res.has("error") or res.get("_status", 0) != 200:
		system_message.emit("加载存档失败")
		return

	_apply_hello_response(res)
	logged_in.emit()


func _apply_hello_response(data: Dictionary) -> void:
	## Parse /api/hello or /api/load response into game state.
	display_name = data.get("display_name", display_name)
	maps_data = data.get("maps", {})
	map_locations = data.get("map_locations", {})
	npcs_here = data.get("npcs_here", [])
	npc_labels = data.get("npc_labels", {})
	npc_catalog = data.get("npc_catalog", [])
	var player_data := data.get("player", {})
	npc_states = player_data.get("npc_states", {})
	intro_text = data.get("intro", "")
	player_flags = data.get("flags", player_flags)
	player_favor = data.get("favor", player_favor)
	_apply_player(data.get("player", {}))

	system_message.emit("踏入江湖。%s" % intro_text)
	state_updated.emit()


func _apply_player(p: Dictionary) -> void:
	if p.is_empty(): return
	player_map_id = p.get("map_id", player_map_id)
	player_px = p.get("px", player_px)
	player_py = p.get("py", player_py)
	player_coins = p.get("coins", player_coins)
	player_vigor = p.get("vigor", player_vigor)
	player_vigor_max = p.get("vigor_max", player_vigor_max)
	player_spirit = p.get("spirit", player_spirit)
	player_spirit_max = p.get("spirit_max", player_spirit_max)
	player_gender = p.get("gender", player_gender)
	player_permadeath = p.get("permadeath", player_permadeath)
	player_dead = p.get("dead", player_dead)
	player_ended = p.get("ended", player_ended)
	player_ending_label = p.get("ending_label", player_ending_label)
	player_inventory = p.get("inventory", {})
	player_reputation = p.get("reputation", {})
	player_flags = p.get("flags", {})
	player_favor = p.get("favor", {})
	player_world_day = p.get("world_day", player_world_day)
	player_world_shichen = p.get("world_shichen", player_world_shichen)
	player_world_is_night = p.get("world_is_night", player_world_is_night)
	player_weather = p.get("weather", player_weather)
	npc_states = p.get("npc_states", npc_states)
	player_move_locked = p.get("move_locked", player_move_locked)
	player_trap_reason = p.get("trap_reason", player_trap_reason)
	player_enslaved = p.get("enslaved", player_enslaved)
	player_death_reason = p.get("death_reason", player_death_reason)
	player_unconscious_ticks = p.get("unconscious_ticks", player_unconscious_ticks)
	player_bounties = p.get("bounties", player_bounties)


func move_player(tx: int, ty: int) -> void:
	## Move to target tile.
	if _is_moving: return
	_is_moving = true
	var body := {"player_id": player_id, "to_x": tx, "to_y": ty}
	var res: Dictionary = await ApiClient.request("/api/move", "POST", body)

	if res.has("error"):
		_is_moving = false
		system_message.emit("移动失败")
		return

	var path_data: Array = res.get("path", [])
	if path_data.is_empty():
		_is_moving = false
		system_message.emit("此路不通")
		return

	for step in path_data:
		if not step is Array and not step is PackedInt32Array:
			continue
		if step.size() < 2:
			continue
		player_px = int(step[0])
		player_py = int(step[1])
		map_pos_changed.emit()
		await get_tree().create_timer(0.08).timeout

	var p: Dictionary = res.get("player", {})
	if not p.is_empty():
		_apply_player(p)

	var encounter = res.get("forced_encounter")
	if encounter and not encounter.is_empty():
		system_message.emit(str(encounter))

	var trap = res.get("trap_state", {})
	if trap.get("active", false):
		player_move_locked = true
		player_trap_reason = str(trap.get("reason", ""))
		system_message.emit("🚫 移动被锁定: %s" % player_trap_reason)

	var injuries_data: Array = res.get("injuries", [])
	for inj in injuries_data:
		system_message.emit("⚠️ 受伤: %s" % str(inj))

	var danger = res.get("danger_sense", {})
	if danger.get("alert"):
		system_message.emit("👁️ 感知: %s" % str(danger.get("alert")))

	var atmo: String = res.get("atmosphere", "")
	if not atmo.is_empty():
		system_message.emit(atmo)

	var respawn_msg: String = res.get("respawn_msg", "")
	if not respawn_msg.is_empty():
		system_message.emit(respawn_msg)

	npcs_here = res.get("npcs_here", npcs_here)
	_is_moving = false
	state_updated.emit()


func save_game() -> bool:
	## Persist current game to disk.
	var body := {"player_id": player_id}
	var res: Dictionary = await ApiClient.request("/api/save", "POST", body)
	return res.get("ok", false)


func list_saves() -> Array:
	## Get all saved games.
	var res: Dictionary = await ApiClient.request("/api/saves", "GET", {})
	return res.get("saves", [])


func fetch_state() -> void:
	var res: Dictionary = await ApiClient.request("/api/state/" + player_id, "GET", {})
	if not res.has("error"):
		_apply_player(res.get("player", {}))
		npcs_here = res.get("npcs_here", npcs_here)
		player_ended = res.get("ended", player_ended)
		player_ending_label = res.get("ending_label", player_ending_label)
		player_flags = res.get("flags", player_flags)
		player_favor = res.get("favor", player_favor)
		state_updated.emit()


func reset_state() -> void:
	player_id = ""
	display_name = ""
	player_map_id = "world"
	player_px = 16
	player_py = 30
	player_coins = 120
	player_vigor = 80
	player_vigor_max = 100
	player_spirit = 80
	player_spirit_max = 100
	player_gender = ""
	player_permadeath = false
	player_dead = false
	player_ended = false
	player_ending_label = ""
	player_inventory = {}
	player_reputation = {}
	player_flags = {}
	player_favor = {}
	player_world_day = 1
	player_world_shichen = "午时"
	player_world_is_night = false
	player_weather = "薄阴"
	player_move_locked = false
	player_trap_reason = ""
	player_enslaved = false
	player_death_reason = ""
	player_unconscious_ticks = 0
	player_bounties = []
	maps_data = {}
	map_locations = {}
	npcs_here = []
	npc_labels = {}
	npc_catalog = []
	npc_states = {}
	intro_text = ""
	_is_moving = false
	is_streaming = false
	selected_npc_id = ""
	logged_out.emit()


func apply_stream_result(data: Dictionary) -> void:
	if data.has("player"):
		_apply_player(data.player)
	if data.has("npcs_here"):
		npcs_here = data.npcs_here
	if data.has("player") or data.has("npcs_here"):
		state_updated.emit()
