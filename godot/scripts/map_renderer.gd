extends Control
## 地图渲染组件 — 使用 ColorRect 网格渲染地图
## 支持 NPC 标记、玩家位置高亮、点击移动/选择 NPC
## 信号驱动，不依赖 get_parent()

# ── 信号 ──
signal tile_clicked(x: int, y: int)
signal npc_clicked(npc_id: String, npc_name: String)

# ── 地图瓦片颜色 ──
const TILE_COLORS: Dictionary = {
	"#": Color(0.15, 0.12, 0.10),
	".": Color(0.25, 0.24, 0.22),
	"~": Color(0.10, 0.30, 0.50),
	"=": Color(0.35, 0.30, 0.20),
	"F": Color(0.10, 0.35, 0.15),
	"m": Color(0.30, 0.25, 0.15),
	";": Color(0.50, 0.45, 0.10),
	"/": Color(0.35, 0.30, 0.20),
	"T": Color(0.60, 0.40, 0.10),
	"Y": Color(0.10, 0.50, 0.60),
	"I": Color(0.40, 0.15, 0.30),
	"M": Color(0.60, 0.50, 0.10),
	"B": Color(0.50, 0.20, 0.20),
	"C": Color(0.55, 0.30, 0.55),
	" ": Color(0.04, 0.04, 0.07),
}
const TILE_SIZE: int = 14
const ACCENT: Color = Color(0.35, 0.78, 0.98)
const ACCENT2: Color = Color(1.0, 0.45, 0.28)
const DEFAULT_TILE: Color = Color(0.2, 0.2, 0.2)

# ── 状态 ──
var _current_map_id: String = ""
var _map_rows: Array = []
var _map_cols: int = 72
var _map_cells: Array[Dictionary] = []
var _map_container: Control
var _map_scroll: ScrollContainer
var _npc_at: Dictionary = {}


func setup(scroll: ScrollContainer, container: Control) -> void:
	_map_scroll = scroll
	_map_container = container


func build_map() -> void:
	_clear_map()

	_current_map_id = GameManager.player_map_id
	var info: Dictionary = GameManager.maps_data.get(_current_map_id, {})
	_map_rows = info.get("rows", [])
	if _map_rows.is_empty():
		return
	_map_cols = _map_rows[0].length()

	var total_w: int = _map_cols * TILE_SIZE
	var total_h: int = _map_rows.size() * TILE_SIZE

	_map_container.set_size(Vector2(total_w, total_h))

	# 构建 NPC 坐标索引
	_build_npc_index()

	# 渲染瓦片
	for y: int in _map_rows.size():
		var row: String = _map_rows[y]
		for x: int in _map_cols:
			var ch: String = " " if x >= row.length() else row[x]
			var tile: ColorRect = ColorRect.new()
			tile.color = _get_tile_color(x, y, ch)
			tile.set_position(Vector2(x * TILE_SIZE, y * TILE_SIZE))
			tile.set_size(Vector2(TILE_SIZE, TILE_SIZE))
			tile.mouse_filter = Control.MOUSE_FILTER_STOP
			tile.gui_input.connect(_on_tile_gui_input.bind(x, y))
			_map_container.add_child(tile)
			_map_cells.append({"node": tile, "x": x, "y": y, "ch": ch})


func update_player_position() -> void:
	_build_npc_index()
	for e: Dictionary in _map_cells:
		var tile: ColorRect = e["node"]
		var ex: int = e["x"]
		var ey: int = e["y"]
		tile.color = _get_tile_color(ex, ey, e["ch"])


func _clear_map() -> void:
	for e: Dictionary in _map_cells:
		var node: ColorRect = e["node"]
		if is_instance_valid(node):
			node.queue_free()
	_map_cells.clear()


func _build_npc_index() -> void:
	_npc_at.clear()
	for n: Dictionary in GameManager.npc_catalog:
		if n.get("map", "") == _current_map_id:
			var pos: Vector2i = Vector2i(n.get("x", -1), n.get("y", -1))
			_npc_at[pos] = n


func _get_tile_color(x: int, y: int, ch: String) -> Color:
	if x == GameManager.player_px and y == GameManager.player_py:
		return ACCENT
	var pos: Vector2i = Vector2i(x, y)
	if _npc_at.has(pos):
		return ACCENT2
	return TILE_COLORS.get(ch, DEFAULT_TILE)


func _on_tile_gui_input(ev: InputEvent, x: int, y: int) -> void:
	if ev is InputEventMouseButton and ev.pressed:
		if ev.button_index == MOUSE_BUTTON_LEFT:
			# 检查是否点击了 NPC
			var pos: Vector2i = Vector2i(x, y)
			if _npc_at.has(pos):
				var npc: Dictionary = _npc_at[pos]
				npc_clicked.emit(npc.get("id", ""), npc.get("name", ""))
			else:
				tile_clicked.emit(x, y)


func get_current_map_id() -> String:
	return _current_map_id


func is_map_loaded() -> bool:
	return _current_map_id != "" and not _map_rows.is_empty()
