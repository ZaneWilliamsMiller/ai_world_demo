extends Node
## Central game state — autoload singleton.
## Holds player data, map data, NPC info, and coordinates UI updates.

# ── Player State ──
var player_id: String = ""
var display_name: String = ""

var player_map_id: String = "world"
var player_px: int = 16
var player_py: int = 30
var player_coins: int = 0
var player_vigor: int = 80
var player_vigor_max: int = 100
var player_spirit: int = 80
var player_spirit_max: int = 100
var player_gender: String = ""
var player_permadeath: bool = false
var player_dead: bool = false
var player_inventory: Dictionary = {}
var player_reputation: Dictionary = {}
var player_flags: Dictionary = {}
var player_favor: Dictionary = {}
var player_world_day: int = 1
var player_world_shichen: String = "午时"
var player_weather: String = "薄阴"

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
signal chat_message(speaker: String, message: String, npc_name: String)
signal system_message(text: String)
signal logged_in()
signal logged_out()

# ── Config ──
@export var backend_url: String = ""


func hello(p_name: String, p_gender: String, p_permadeath: bool) -> void:
	"""Start a new game."""
	print("[GM] hello() called: name=%s gender=%s permadeath=%s" % [p_name, p_gender, p_permadeath])
	player_id = "godot_%d" % (Time.get_unix_time_from_system())
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
	"""Load an existing save."""
	player_id = save_pid
	var body := {"player_id": save_pid}
	var res: Dictionary = await ApiClient.request("/api/load", "POST", body)

	if res.has("error") or res.get("_status", 0) != 200:
		system_message.emit("加载存档失败")
		return

	_apply_hello_response(res)
	logged_in.emit()


func _apply_hello_response(data: Dictionary) -> void:
	"""Parse /api/hello or /api/load response into game state."""
	display_name = data.get("display_name", display_name)
	maps_data = data.get("maps", {})
	map_locations = data.get("map_locations", {})
	npcs_here = data.get("npcs_here", [])
	npc_labels = data.get("npc_labels", {})
	npc_catalog = data.get("npc_catalog", [])
	npc_states = data.get("npc_states", {})
	intro_text = data.get("intro", "")
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
	player_inventory = p.get("inventory", {})
	player_reputation = p.get("reputation", {})
	player_flags = p.get("flags", {})
	player_favor = p.get("favor", {})
	player_world_day = p.get("world_day", player_world_day)
	player_world_shichen = p.get("world_shichen", player_world_shichen)
	player_weather = p.get("weather", player_weather)


func move_player(tx: int, ty: int) -> void:
	"""Move to target tile."""
	var body := {"player_id": player_id, "to_x": tx, "to_y": ty}
	var res: Dictionary = await ApiClient.request("/api/move", "POST", body)

	if res.has("error"):
		system_message.emit("移动失败")
		return

	var path_data: Array = res.get("path", [])
	if path_data.is_empty():
		system_message.emit("此路不通")
		return

	for step in path_data:
		player_px = step[0]
		player_py = step[1]
		map_pos_changed.emit()
		await get_tree().create_timer(0.08).timeout

	var p: Dictionary = res.get("player", {})
	if not p.is_empty():
		_apply_player(p)

	var encounter = res.get("encounter")
	if encounter and not encounter.is_empty():
		system_message.emit(str(encounter))

	npcs_here = res.get("npcs_here", npcs_here)
	state_updated.emit()


func talk_to_npc(npc_id: String, message: String) -> bool:
	"""Send message to NPC. Returns true if LLM fallback was NOT used."""
	# 所有模式都连接后端，自定义LLM Key模式只是传递额外参数
	var body := {"player_id": player_id, "npc_id": npc_id, "message": message}
	
	# 如果是自定义LLM Key模式，添加自定义配置
	if ApiClient.api_mode == "direct":
		if not ApiClient.llm_api_url.is_empty():
			body["llm_base_url"] = ApiClient.llm_api_url
		if not ApiClient.llm_api_key.is_empty():
			body["llm_api_key"] = ApiClient.llm_api_key
		if not ApiClient.llm_model.is_empty():
			body["llm_model"] = ApiClient.llm_model
	
	var res: Dictionary = await ApiClient.request("/api/npc/talk", "POST", body)

	if res.has("error"):
		system_message.emit("对话失败")
		return false

	var visible: String = res.get("visible_text", res.get("reply", ""))
	var npc_name: String = npc_labels.get(npc_id, npc_id)
	chat_message.emit(npc_name, visible, npc_id)

	var p: Dictionary = res.get("player", {})
	if not p.is_empty():
		_apply_player(p)
	npcs_here = res.get("npcs_here", npcs_here)
	state_updated.emit()

	var fallback: bool = res.get("llm_fallback", false)
	return not fallback


func save_game() -> bool:
	"""Persist current game to disk."""
	var body := {"player_id": player_id}
	var res: Dictionary = await ApiClient.request("/api/save", "POST", body)
	return res.get("ok", false)


func list_saves() -> Array:
	"""Get all saved games."""
	var res: Dictionary = await ApiClient.request("/api/saves", "GET", {})
	return res.get("saves", [])


func fetch_state() -> void:
	"""Poll server for latest player state."""
	var res: Dictionary = await ApiClient.request("/api/state/" + player_id, "GET", {})
	if not res.has("error"):
		_apply_player(res.get("player", {}))
		npcs_here = res.get("npcs_here", npcs_here)
		state_updated.emit()
