extends Node2D
## 地图视口渲染器 — Camera2D 跟随 + 视口裁剪 + 小地图 + hover 高亮 + 预排队移动
## 核心原则：
##   - 摄像机跟随主角，接近边缘时停住
##   - 只渲染可见区域内的瓦片
##   - 信号驱动，不依赖 get_parent()
##   - 小地图固定左上角
##   - hover 高亮跟随鼠标（屏幕锁定）
##   - 移动中点击预排队

signal tile_clicked(x: int, y: int)
signal npc_clicked(npc_id: String, npc_name: String)

const TILE_COLORS: Dictionary = {
	"#": Color(0.18, 0.16, 0.27), ".": Color(0.29, 0.26, 0.19),
	",": Color(0.16, 0.31, 0.19), "~": Color(0.08, 0.23, 0.37),
	"=": Color(0.12, 0.31, 0.43), "F": Color(0.10, 0.24, 0.12),
	"m": Color(0.35, 0.25, 0.19), "/": Color(0.29, 0.25, 0.21),
	";": Color(0.23, 0.21, 0.13), "T": Color(0.42, 0.31, 0.13),
	"Y": Color(0.23, 0.29, 0.44), "I": Color(0.29, 0.21, 0.27),
	"M": Color(0.42, 0.35, 0.13), "B": Color(0.42, 0.21, 0.21),
	"C": Color(0.55, 0.30, 0.55), "G": Color(0.24, 0.40, 0.20),
	"f": Color(0.10, 0.30, 0.50), "w": Color(0.20, 0.30, 0.40),
	"s": Color(0.24, 0.40, 0.40), "E": Color(0.40, 0.30, 0.20),
	"@": Color(0.35, 0.10, 0.17), "!": Color(0.23, 0.04, 0.04),
	"^": Color(0.29, 0.29, 0.35), "&": Color(0.10, 0.23, 0.23),
	"*": Color(0.50, 0.40, 0.00), " ": Color(0.02, 0.02, 0.05),
}
const TILE_SIZE: int = 20
const ACCENT: Color = Color(0.35, 0.78, 0.98)
const ACCENT2: Color = Color(1.0, 0.45, 0.28)
const DEFAULT_TILE: Color = Color(0.2, 0.2, 0.2)
const CAMERA_SMOOTHING: float = 8.0
const MINI_TILE: int = 3
const MINI_MARGIN: int = 8

var _camera: Camera2D
var _tile_container: Node2D
var _player_marker: ColorRect
var _player_glow: ColorRect
var _npc_markers: Node2D
var _location_labels: Node2D
var _hover_highlight: ColorRect
var _hover_cross_h: ColorRect
var _hover_cross_v: ColorRect

var _current_map_id: String = ""
var _map_rows: Array = []
var _map_cols: int = 0
var _tile_pool: Array[ColorRect] = []
var _visible_range: Dictionary = {"x0": 0, "y0": 0, "x1": 0, "y1": 0}
var _npc_at: Dictionary = {}

var _active_tiles: Dictionary = {}
var _last_player_pos := Vector2i(-1, -1)
var _dirty: bool = true

var _hover_x: int = -1
var _hover_y: int = -1
var _mouse_screen_pos := Vector2(-1, -1)
var _pending_move: Vector2i = Vector2i(-1, -1)

var _mini_canvas: Control
var _mini_bg: ColorRect
var _mini_border: PanelContainer
var _mini_player_dot: ColorRect
var _mini_dirty: bool = true
var _mini_image: Image
var _mini_texture: ImageTexture


func mark_dirty() -> void:
	_dirty = true
	_mini_dirty = true


func _ready() -> void:
	print("[MapRenderer] _ready() called")

	_tile_container = Node2D.new()
	_tile_container.name = "TileContainer"
	add_child(_tile_container)

	_npc_markers = Node2D.new()
	_npc_markers.name = "NpcMarkers"
	add_child(_npc_markers)

	_location_labels = Node2D.new()
	_location_labels.name = "LocationLabels"
	add_child(_location_labels)

	_hover_highlight = ColorRect.new()
	_hover_highlight.color = Color(ACCENT.r, ACCENT.g, ACCENT.b, 0.25)
	_hover_highlight.size = Vector2(TILE_SIZE, TILE_SIZE)
	_hover_highlight.z_index = 8
	_hover_highlight.visible = false
	_hover_highlight.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_hover_highlight)

	_hover_cross_h = ColorRect.new()
	_hover_cross_h.color = Color(ACCENT.r, ACCENT.g, ACCENT.b, 0.08)
	_hover_cross_h.size = Vector2(TILE_SIZE, TILE_SIZE)
	_hover_cross_h.z_index = 7
	_hover_cross_h.visible = false
	_hover_cross_h.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_hover_cross_h)

	_hover_cross_v = ColorRect.new()
	_hover_cross_v.color = Color(ACCENT.r, ACCENT.g, ACCENT.b, 0.08)
	_hover_cross_v.size = Vector2(TILE_SIZE, TILE_SIZE)
	_hover_cross_v.z_index = 7
	_hover_cross_v.visible = false
	_hover_cross_v.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_hover_cross_v)

	_player_marker = ColorRect.new()
	_player_marker.color = ACCENT
	_player_marker.size = Vector2(TILE_SIZE, TILE_SIZE)
	_player_marker.z_index = 10
	_player_marker.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_player_marker)

	_player_glow = ColorRect.new()
	_player_glow.color = Color(ACCENT.r, ACCENT.g, ACCENT.b, 0.3)
	_player_glow.size = Vector2(TILE_SIZE * 2, TILE_SIZE * 2)
	_player_glow.z_index = 9
	_player_glow.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_player_glow)

	_camera = Camera2D.new()
	_camera.position_smoothing_enabled = true
	_camera.position_smoothing_speed = CAMERA_SMOOTHING
	_camera.zoom = Vector2(1, 1)
	add_child(_camera)

	call_deferred("_make_current")


func _exit_tree() -> void:
	for tile in _tile_pool:
		if is_instance_valid(tile):
			tile.queue_free()
	_tile_pool.clear()
	for key in _active_tiles:
		var tile: ColorRect = _active_tiles[key]
		if is_instance_valid(tile):
			tile.queue_free()
	_active_tiles.clear()


func _make_current() -> void:
	if _camera and is_instance_valid(_camera):
		_camera.make_current()


func _process(_delta: float) -> void:
	if not _current_map_id.is_empty() and not _map_rows.is_empty():
		_update_camera()
		_update_hover_from_screen()
		if _dirty:
			_update_visible_tiles()
			_update_player_marker()
			_dirty = false
		elif _last_player_pos != Vector2i(GameManager.player_px, GameManager.player_py):
			_update_player_marker()
		if _mini_dirty:
			_render_minimap()
			_mini_dirty = false
	elif _camera:
		var px: float = GameManager.player_px * TILE_SIZE + TILE_SIZE / 2.0
		var py: float = GameManager.player_py * TILE_SIZE + TILE_SIZE / 2.0
		_camera.position = Vector2(px, py)


func _update_camera() -> void:
	var px: float = GameManager.player_px * TILE_SIZE + TILE_SIZE / 2.0
	var py: float = GameManager.player_py * TILE_SIZE + TILE_SIZE / 2.0
	_camera.position = Vector2(px, py)

	var vp_size: Vector2
	var vp := get_viewport()
	if vp and vp.get_visible_rect().size.x > 0:
		vp_size = vp.get_visible_rect().size
	else:
		vp_size = Vector2(640, 480)

	var map_w: float = _map_cols * TILE_SIZE
	var map_h: float = _map_rows.size() * TILE_SIZE

	if map_w < vp_size.x:
		_camera.limit_left = -int((vp_size.x - map_w) / 2.0)
		_camera.limit_right = int(map_w + (vp_size.x - map_w) / 2.0)
	else:
		_camera.limit_left = int(vp_size.x / 2.0)
		_camera.limit_right = int(map_w - vp_size.x / 2.0)

	if map_h < vp_size.y:
		_camera.limit_top = -int((vp_size.y - map_h) / 2.0)
		_camera.limit_bottom = int(map_h + (vp_size.y - map_h) / 2.0)
	else:
		_camera.limit_top = int(vp_size.y / 2.0)
		_camera.limit_bottom = int(map_h - vp_size.y / 2.0)


func _update_hover_from_screen() -> void:
	if _mouse_screen_pos.x < 0 or _mouse_screen_pos.y < 0:
		return
	if not _camera or not is_instance_valid(_camera):
		return
	var cam_pos: Vector2 = _camera.position
	var vp := get_viewport()
	if not vp:
		return
	var vp_size: Vector2 = vp.get_visible_rect().size
	var new_x: int = int(floor((_mouse_screen_pos.x - vp_size.x / 2.0) / TILE_SIZE + cam_pos.x / TILE_SIZE))
	var new_y: int = int(floor((_mouse_screen_pos.y - vp_size.y / 2.0) / TILE_SIZE + cam_pos.y / TILE_SIZE))
	if new_x != _hover_x or new_y != _hover_y:
		_hover_x = new_x
		_hover_y = new_y
		_update_hover_visual()
		mark_dirty()


func _update_hover_visual() -> void:
	if _hover_x < 0 or _hover_y < 0 or _hover_x >= _map_cols or _hover_y >= _map_rows.size():
		_hover_highlight.visible = false
		_hover_cross_h.visible = false
		_hover_cross_v.visible = false
		return
	_hover_highlight.visible = true
	_hover_highlight.position = Vector2(_hover_x * TILE_SIZE, _hover_y * TILE_SIZE)
	_hover_cross_h.visible = true
	_hover_cross_h.position = Vector2(0, _hover_y * TILE_SIZE)
	_hover_cross_h.size = Vector2(_map_cols * TILE_SIZE, TILE_SIZE)
	_hover_cross_v.visible = true
	_hover_cross_v.position = Vector2(_hover_x * TILE_SIZE, 0)
	_hover_cross_v.size = Vector2(TILE_SIZE, _map_rows.size() * TILE_SIZE)


func _update_visible_tiles() -> void:
	var vp_rect: Rect2
	var vp := get_viewport()
	if vp:
		vp_rect = vp.get_visible_rect()
	else:
		return

	if vp_rect.size.x <= 0 or vp_rect.size.y <= 0:
		return

	var cam_pos: Vector2 = _camera.position
	var vp_half: Vector2 = vp_rect.size / 2.0

	var x0: int = int(max(0, (cam_pos.x - vp_half.x) / TILE_SIZE - 1))
	var y0: int = int(max(0, (cam_pos.y - vp_half.y) / TILE_SIZE - 1))
	var x1: int = int(min(_map_cols - 1, (cam_pos.x + vp_half.x) / TILE_SIZE + 1))
	var y1: int = int(min(_map_rows.size() - 1, (cam_pos.y + vp_half.y) / TILE_SIZE + 1))

	if x0 == _visible_range.x0 and y0 == _visible_range.y0 \
		and x1 == _visible_range.x1 and y1 == _visible_range.y1:
		return

	_visible_range = {"x0": x0, "y0": y0, "x1": x1, "y1": y1}

	var keys_to_remove: Array[String] = []
	for key in _active_tiles:
		var parts: PackedStringArray = key.split(",")
		var tx: int = int(parts[0])
		var ty: int = int(parts[1])
		if tx < x0 or tx > x1 or ty < y0 or ty > y1:
			var tile: ColorRect = _active_tiles[key]
			tile.visible = false
			_tile_pool.append(tile)
			keys_to_remove.append(key)
	for k in keys_to_remove:
		_active_tiles.erase(k)

	for y in range(y0, y1 + 1):
		if y < 0 or y >= _map_rows.size():
			continue
		var row: String = _map_rows[y]
		for x in range(x0, x1 + 1):
			if x < 0 or x >= _map_cols:
				continue
			var key: String = "%d,%d" % [x, y]
			if _active_tiles.has(key):
				continue

			var ch: String = " " if x >= row.length() else row[x]
			var tile: ColorRect = _get_tile_from_pool()
			tile.color = _get_tile_color(x, y, ch)
			tile.position = Vector2(x * TILE_SIZE, y * TILE_SIZE)
			tile.visible = true
			_active_tiles[key] = tile


func _get_tile_from_pool() -> ColorRect:
	if _tile_pool.size() > 0:
		return _tile_pool.pop_back()
	var tile := ColorRect.new()
	tile.size = Vector2(TILE_SIZE, TILE_SIZE)
	tile.mouse_filter = Control.MOUSE_FILTER_STOP
	tile.gui_input.connect(_on_tile_gui_input.bind(tile))
	_tile_container.add_child(tile)
	return tile


func _update_player_marker() -> void:
	var px: int = GameManager.player_px
	var py: int = GameManager.player_py
	_player_marker.position = Vector2(px * TILE_SIZE, py * TILE_SIZE)
	_player_glow.position = Vector2(px * TILE_SIZE - TILE_SIZE / 2.0, py * TILE_SIZE - TILE_SIZE / 2.0)
	_last_player_pos = Vector2i(px, py)


func build_map() -> void:
	print("[MapRenderer] build_map() called")
	_clear_map()

	_current_map_id = GameManager.player_map_id
	var info: Dictionary = GameManager.maps_data.get(_current_map_id, {})
	_map_rows = info.get("rows", [])

	if _map_rows.is_empty():
		print("[MapRenderer] build_map: rows is EMPTY for map '%s'!" % _current_map_id)
		return

	_map_cols = _map_rows[0].length()

	print("[MapRenderer] build_map: map=%s cols=%d rows=%d" % [_current_map_id, _map_cols, _map_rows.size()])

	_camera.limit_left = -100000
	_camera.limit_right = 100000
	_camera.limit_top = -100000
	_camera.limit_bottom = 100000

	_visible_range = {"x0": -1, "y0": -1, "x1": -1, "y1": -1}
	_dirty = true
	_mini_dirty = true

	_build_npc_index()
	_build_npc_markers()
	_build_location_labels()

	_update_visible_tiles()
	_update_player_marker()

	print("[MapRenderer] build_map complete, active tiles: %d" % _active_tiles.size())


func update_player_position() -> void:
	var new_pos := Vector2i(GameManager.player_px, GameManager.player_py)
	if _last_player_pos != Vector2i(-1, -1) and _last_player_pos != new_pos:
		_refresh_tile_at(_last_player_pos.x, _last_player_pos.y)
	_refresh_tile_at(new_pos.x, new_pos.y)
	_last_player_pos = new_pos
	_update_npc_markers()
	_mini_dirty = true


func _refresh_tile_at(x: int, y: int) -> void:
	var key := "%d,%d" % [x, y]
	if not _active_tiles.has(key):
		return
	var tile: ColorRect = _active_tiles[key]
	if y < 0 or y >= _map_rows.size() or x < 0 or x >= _map_rows[y].length():
		return
	var ch: String = _map_rows[y][x]
	tile.color = _get_tile_color(x, y, ch)


func _build_npc_index() -> void:
	_npc_at.clear()
	for n: Dictionary in GameManager.npc_catalog:
		if n.get("map", "") == _current_map_id:
			var pos: Vector2i = Vector2i(n.get("x", -1), n.get("y", -1))
			_npc_at[pos] = n


func _build_npc_markers() -> void:
	var current_ids: Dictionary = {}
	for pos: Vector2i in _npc_at:
		var npc: Dictionary = _npc_at[pos]
		current_ids[npc.get("id", "")] = {"pos": pos, "npc": npc}
	var existing_ids: Dictionary = {}
	for c in _npc_markers.get_children():
		var id_str: String = c.name.replace("NpcGlow_", "").replace("NpcMarker_", "")
		existing_ids[id_str] = c
	var to_remove: Array = []
	for id_str in existing_ids:
		if not current_ids.has(id_str):
			to_remove.append(existing_ids[id_str])
	for c in to_remove:
		if is_instance_valid(c):
			var id_str2: String = c.name.replace("NpcGlow_", "").replace("NpcMarker_", "")
			var marker_node = _npc_markers.get_node_or_null("NpcMarker_" + id_str2)
			if marker_node and is_instance_valid(marker_node):
				marker_node.queue_free()
			c.queue_free()
	for id_str in current_ids:
		if existing_ids.has(id_str):
			var pos: Vector2i = current_ids[id_str]["pos"]
			var glow_node = _npc_markers.get_node_or_null("NpcGlow_" + id_str)
			var marker_node = _npc_markers.get_node_or_null("NpcMarker_" + id_str)
			if glow_node and is_instance_valid(glow_node):
				glow_node.position = Vector2(pos.x * TILE_SIZE + TILE_SIZE / 2.0 - 10, pos.y * TILE_SIZE + TILE_SIZE / 2.0 - 10)
			if marker_node and is_instance_valid(marker_node):
				marker_node.position = Vector2(pos.x * TILE_SIZE + TILE_SIZE / 2.0 - 5, pos.y * TILE_SIZE + TILE_SIZE / 2.0 - 5)
		else:
			var pos: Vector2i = current_ids[id_str]["pos"]
			var npc: Dictionary = current_ids[id_str]["npc"]
			var glow := PanelContainer.new()
			var glow_sb := StyleBoxFlat.new()
			glow_sb.bg_color = Color(ACCENT2.r, ACCENT2.g, ACCENT2.b, 0.25)
			glow_sb.set_corner_radius_all(10)
			glow.add_theme_stylebox_override("panel", glow_sb)
			glow.custom_minimum_size = Vector2(20, 20)
			glow.size = Vector2(20, 20)
			glow.position = Vector2(pos.x * TILE_SIZE + TILE_SIZE / 2.0 - 10, pos.y * TILE_SIZE + TILE_SIZE / 2.0 - 10)
			glow.z_index = 4
			glow.name = "NpcGlow_%s" % npc.get("id", "")
			glow.mouse_filter = Control.MOUSE_FILTER_IGNORE
			_npc_markers.add_child(glow)
			var marker := PanelContainer.new()
			var marker_sb := StyleBoxFlat.new()
			marker_sb.bg_color = ACCENT2
			marker_sb.set_corner_radius_all(5)
			marker.add_theme_stylebox_override("panel", marker_sb)
			marker.custom_minimum_size = Vector2(10, 10)
			marker.size = Vector2(10, 10)
			marker.position = Vector2(pos.x * TILE_SIZE + TILE_SIZE / 2.0 - 5, pos.y * TILE_SIZE + TILE_SIZE / 2.0 - 5)
			marker.z_index = 5
			marker.name = "NpcMarker_%s" % npc.get("id", "")
			marker.mouse_filter = Control.MOUSE_FILTER_IGNORE
			_npc_markers.add_child(marker)


func _update_npc_markers() -> void:
	_build_npc_index()
	_build_npc_markers()


func _build_location_labels() -> void:
	for c in _location_labels.get_children():
		c.queue_free()
	var locs: Dictionary = GameManager.map_locations.get(_current_map_id, {})
	for name: String in locs:
		var pos_arr: Array = locs[name]
		if pos_arr.size() < 2:
			continue
		var label := Label.new()
		label.text = name
		label.add_theme_color_override("font_color", Color(0.88, 0.88, 0.90, 0.9))
		label.add_theme_font_size_override("font_size", 9)
		label.position = Vector2(pos_arr[0] * TILE_SIZE - 10, pos_arr[1] * TILE_SIZE - 12)
		label.z_index = 3
		label.mouse_filter = Control.MOUSE_FILTER_IGNORE
		var bg := ColorRect.new()
		bg.color = Color(0, 0, 0, 0.55)
		bg.position = label.position - Vector2(3, 1)
		var char_count := 0
		for ch in name:
			char_count += 2 if ch.unicode_at(0) > 0x7F else 1
		bg.size = Vector2(char_count * 5 + 6, 13)
		bg.z_index = 2
		bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
		_location_labels.add_child(bg)
		_location_labels.add_child(label)


func _get_tile_color(x: int, y: int, ch: String) -> Color:
	if x == GameManager.player_px and y == GameManager.player_py:
		return ACCENT
	var pos: Vector2i = Vector2i(x, y)
	if _npc_at.has(pos):
		return Color(ACCENT2.r, ACCENT2.g, ACCENT2.b, 0.7)
	var base := TILE_COLORS.get(ch, DEFAULT_TILE)
	var brightness_adj := 0.015 if (x + y) % 2 == 0 else -0.015
	base = Color(
		clampf(base.r + brightness_adj, 0, 1),
		clampf(base.g + brightness_adj, 0, 1),
		clampf(base.b + brightness_adj, 0, 1)
	)
	return base


func _clear_map() -> void:
	for key in _active_tiles:
		var tile: ColorRect = _active_tiles[key]
		tile.visible = false
		_tile_pool.append(tile)
	_active_tiles.clear()
	for c in _npc_markers.get_children():
		c.queue_free()
	for c in _location_labels.get_children():
		c.queue_free()


func _on_tile_gui_input(ev: InputEvent, tile: ColorRect) -> void:
	if ev is InputEventMouseButton and ev.pressed:
		if ev.button_index == MOUSE_BUTTON_LEFT:
			var tx: int = int(tile.position.x) / TILE_SIZE
			var ty: int = int(tile.position.y) / TILE_SIZE
			var pos: Vector2i = Vector2i(tx, ty)
			if _npc_at.has(pos):
				var npc: Dictionary = _npc_at[pos]
				npc_clicked.emit(npc.get("id", ""), npc.get("name", ""))
			else:
				tile_clicked.emit(tx, ty)
	elif ev is InputEventScreenTouch and ev.pressed:
		var tx: int = int(tile.position.x) / TILE_SIZE
		var ty: int = int(tile.position.y) / TILE_SIZE
		var pos: Vector2i = Vector2i(tx, ty)
		if _npc_at.has(pos):
			var npc: Dictionary = _npc_at[pos]
			npc_clicked.emit(npc.get("id", ""), npc.get("name", ""))
		else:
			tile_clicked.emit(tx, ty)


func on_mouse_moved(screen_pos: Vector2) -> void:
	_mouse_screen_pos = screen_pos
	_update_hover_from_screen()


func on_mouse_exited() -> void:
	_mouse_screen_pos = Vector2(-1, -1)
	_hover_x = -1
	_hover_y = -1
	_hover_highlight.visible = false
	_hover_cross_h.visible = false
	_hover_cross_v.visible = false


func get_pending_move() -> Vector2i:
	var pm := _pending_move
	_pending_move = Vector2i(-1, -1)
	return pm


func set_pending_move(x: int, y: int) -> void:
	_pending_move = Vector2i(x, y)


func has_pending_move() -> bool:
	return _pending_move.x >= 0 and _pending_move.y >= 0


func get_current_map_id() -> String:
	return _current_map_id


func is_map_loaded() -> bool:
	return _current_map_id != "" and not _map_rows.is_empty()


func setup_minimap(parent: Control) -> void:
	var vp := get_viewport()
	var vp_size := Vector2(640, 480)
	if vp:
		vp_size = vp.get_visible_rect().size

	_mini_border = PanelContainer.new()
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0, 0, 0, 0.6)
	sb.set_corner_radius_all(4)
	sb.border_width_left = 1; sb.border_width_right = 1
	sb.border_width_top = 1; sb.border_width_bottom = 1
	sb.border_color = Color(0.5, 0.5, 0.6, 0.5)
	_mini_border.add_theme_stylebox_override("panel", sb)
	_mini_border.position = Vector2(MINI_MARGIN, MINI_MARGIN)
	_mini_border.z_index = 100
	parent.add_child(_mini_border)

	_mini_canvas = Control.new()
	_mini_canvas.name = "MiniMapCanvas"
	_mini_canvas.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_mini_border.add_child(_mini_canvas)

	_mini_player_dot = ColorRect.new()
	_mini_player_dot.color = ACCENT
	_mini_player_dot.size = Vector2(3, 3)
	_mini_player_dot.z_index = 102
	_mini_player_dot.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_mini_border.add_child(_mini_player_dot)

	_mini_dirty = true


func _render_minimap() -> void:
	if _map_rows.is_empty():
		return

	var mini_w: int = _map_cols * MINI_TILE
	var mini_h: int = _map_rows.size() * MINI_TILE

	if mini_w <= 0 or mini_h <= 0:
		return

	if not _mini_image or _mini_image.get_width() != mini_w or _mini_image.get_height() != mini_h:
		_mini_image = Image.create(mini_w, mini_h, false, Image.FORMAT_RGBA8)

	_mini_image.fill(Color(0.04, 0.04, 0.07))

	for y in _map_rows.size():
		var row: String = _map_rows[y]
		for x in row.length():
			var ch: String = row[x]
			var col: Color = TILE_COLORS.get(ch, DEFAULT_TILE)
			if x == GameManager.player_px and y == GameManager.player_py:
				col = ACCENT
			elif _npc_at.has(Vector2i(x, y)):
				col = ACCENT2
			for dy in MINI_TILE:
				for dx in MINI_TILE:
					_mini_image.set_pixel(x * MINI_TILE + dx, y * MINI_TILE + dy, col)

	if _mini_texture:
		_mini_texture.update(_mini_image)
	else:
		_mini_texture = ImageTexture.create_from_image(_mini_image)

	if _mini_border:
		_mini_border.custom_minimum_size = Vector2(mini_w + 4, mini_h + 4)
		_mini_border.size = Vector2(mini_w + 4, mini_h + 4)

	if _mini_canvas:
		_mini_canvas.queue_redraw()
		_mini_canvas.draw.connect(func():
			_mini_canvas.draw_texture(_mini_texture, Vector2(2, 2))
		, CONNECT_ONE_SHOT)

	if _mini_player_dot:
		_mini_player_dot.position = Vector2(
			2 + GameManager.player_px * MINI_TILE,
			2 + GameManager.player_py * MINI_TILE
		)
