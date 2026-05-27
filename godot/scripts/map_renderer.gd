extends Node2D
## 地图视口渲染器 — Camera2D 跟随 + 视口裁剪 + 小地图
## 核心原则：
##   - 摄像机跟随主角，接近边缘时停住
##   - 只渲染可见区域内的瓦片
##   - 信号驱动，不依赖 get_parent()

# ── 信号 ──
signal tile_clicked(x: int, y: int)
signal npc_clicked(npc_id: String, npc_name: String)

# ── 瓦片颜色 ──
const TILE_COLORS: Dictionary = {
	"#": Color(0.15, 0.12, 0.10), ".": Color(0.25, 0.24, 0.22),
	"~": Color(0.10, 0.30, 0.50), "=": Color(0.35, 0.30, 0.20),
	"F": Color(0.10, 0.35, 0.15), "m": Color(0.30, 0.25, 0.15),
	";": Color(0.50, 0.45, 0.10), "/": Color(0.35, 0.30, 0.20),
	"T": Color(0.60, 0.40, 0.10), "Y": Color(0.10, 0.50, 0.60),
	"I": Color(0.40, 0.15, 0.30), "M": Color(0.60, 0.50, 0.10),
	"B": Color(0.50, 0.20, 0.20), "C": Color(0.55, 0.30, 0.55),
	"G": Color(0.24, 0.40, 0.20), "f": Color(0.10, 0.30, 0.50),
	"w": Color(0.20, 0.30, 0.40), "s": Color(0.24, 0.40, 0.40),
	"E": Color(0.40, 0.30, 0.20), "*": Color(0.50, 0.40, 0.00),
	" ": Color(0.04, 0.04, 0.07),
}
const TILE_SIZE: int = 20
const ACCENT: Color = Color(0.35, 0.78, 0.98)
const ACCENT2: Color = Color(1.0, 0.45, 0.28)
const DEFAULT_TILE: Color = Color(0.2, 0.2, 0.2)
const CAMERA_SMOOTHING: float = 6.0

# ── 节点 ──
var _camera: Camera2D
var _tile_container: Node2D
var _player_marker: ColorRect
var _player_glow: ColorRect
var _npc_markers: Node2D
var _location_labels: Node2D

# ── 小地图 ──
var _minimap: SubViewportContainer
var _minimap_vp: SubViewport
var _minimap_canvas: Node2D
var _minimap_viewport_rect: ColorRect

# ── 状态 ──
var _current_map_id: String = ""
var _map_rows: Array = []
var _map_cols: int = 0
var _tile_pool: Array[ColorRect] = []
var _visible_range: Dictionary = {"x0": 0, "y0": 0, "x1": 0, "y1": 0}
var _npc_at: Dictionary = {}

# ── 缓存瓦片 ──
# 使用二维数组存储所有可见瓦片的 ColorRect 引用
var _active_tiles: Dictionary = {}  # key = "x,y" -> ColorRect


func _ready() -> void:
	# 创建节点树
	_tile_container = Node2D.new()
	_tile_container.name = "TileContainer"
	add_child(_tile_container)

	_npc_markers = Node2D.new()
	_npc_markers.name = "NpcMarkers"
	add_child(_npc_markers)

	_location_labels = Node2D.new()
	_location_labels.name = "LocationLabels"
	add_child(_location_labels)

	# 玩家标记
	_player_marker = ColorRect.new()
	_player_marker.color = ACCENT
	_player_marker.size = Vector2(TILE_SIZE, TILE_SIZE)
	_player_marker.z_index = 10
	add_child(_player_marker)

	# 玩家光晕
	_player_glow = ColorRect.new()
	_player_glow.color = Color(ACCENT.r, ACCENT.g, ACCENT.b, 0.3)
	_player_glow.size = Vector2(TILE_SIZE * 2, TILE_SIZE * 2)
	_player_glow.z_index = 9
	add_child(_player_glow)

	# 摄像机
	_camera = Camera2D.new()
	_camera.position_smoothing_enabled = true
	_camera.position_smoothing_speed = CAMERA_SMOOTHING
	_camera.zoom = Vector2(1, 1)
	add_child(_camera)
	_camera.make_current()

	# 构建小地图
	_build_minimap()


func _process(_delta: float) -> void:
	if _current_map_id.is_empty() or _map_rows.is_empty():
		return
	_update_camera()
	_update_visible_tiles()
	_update_player_marker()
	_update_minimap()


# ═══════════════════════════════════════════
#  摄像机跟随 + 边缘限制
# ═══════════════════════════════════════════
func _update_camera() -> void:
	var px: float = GameManager.player_px * TILE_SIZE + TILE_SIZE / 2.0
	var py: float = GameManager.player_py * TILE_SIZE + TILE_SIZE / 2.0
	_camera.position = Vector2(px, py)

	# 设置摄像机限制，防止看到地图外
	var vp_size: Vector2 = get_viewport().get_visible_rect().size
	var map_w: float = _map_cols * TILE_SIZE
	var map_h: float = _map_rows.size() * TILE_SIZE

	# 如果地图小于视口，居中
	if map_w < vp_size.x:
		_camera.limit_left = -(vp_size.x - map_w) / 2.0
		_camera.limit_right = map_w + (vp_size.x - map_w) / 2.0
	else:
		_camera.limit_left = vp_size.x / 2.0
		_camera.limit_right = map_w - vp_size.x / 2.0

	if map_h < vp_size.y:
		_camera.limit_top = -(vp_size.y - map_h) / 2.0
		_camera.limit_bottom = map_h + (vp_size.y - map_h) / 2.0
	else:
		_camera.limit_top = vp_size.y / 2.0
		_camera.limit_bottom = map_h - vp_size.y / 2.0


# ═══════════════════════════════════════════
#  视口裁剪渲染
# ═══════════════════════════════════════════
func _update_visible_tiles() -> void:
	var vp_rect: Rect2 = get_viewport().get_visible_rect()
	var cam_pos: Vector2 = _camera.position
	var vp_half: Vector2 = vp_rect.size / 2.0

	# 计算可见瓦片范围
	var x0: int = int(max(0, (cam_pos.x - vp_half.x) / TILE_SIZE - 1))
	var y0: int = int(max(0, (cam_pos.y - vp_half.y) / TILE_SIZE - 1))
	var x1: int = int(min(_map_cols - 1, (cam_pos.x + vp_half.x) / TILE_SIZE + 1))
	var y1: int = int(min(_map_rows.size() - 1, (cam_pos.y + vp_half.y) / TILE_SIZE + 1))

	# 范围未变化则跳过
	if x0 == _visible_range.x0 and y0 == _visible_range.y0 \
		and x1 == _visible_range.x1 and y1 == _visible_range.y1:
		return

	_visible_range = {"x0": x0, "y0": y0, "x1": x1, "y1": y1}

	# 回收超出范围的瓦片
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

	# 创建/显示可见范围内的瓦片
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


# ═══════════════════════════════════════════
#  构建地图
# ═══════════════════════════════════════════
func build_map() -> void:
	_clear_map()

	_current_map_id = GameManager.player_map_id
	var info: Dictionary = GameManager.maps_data.get(_current_map_id, {})
	_map_rows = info.get("rows", [])
	if _map_rows.is_empty():
		return
	_map_cols = _map_rows[0].length()

	# 重置摄像机限制
	_camera.limit_left = -10000
	_camera.limit_right = 10000
	_camera.limit_top = -10000
	_camera.limit_bottom = 10000

	# 重置可见范围，强制刷新
	_visible_range = {"x0": -1, "y0": -1, "x1": -1, "y1": -1}

	# 构建 NPC 标记
	_build_npc_markers()

	# 构建地点标签
	_build_location_labels()

	# 更新小地图
	_render_minimap_full()


func update_player_position() -> void:
	# 刷新瓦片颜色（玩家位置高亮）
	_build_npc_index()
	for key in _active_tiles:
		var tile: ColorRect = _active_tiles[key]
		var parts: PackedStringArray = key.split(",")
		var x: int = int(parts[0])
		var y: int = int(parts[1])
		var ch: String = " " if x >= _map_rows[y].length() else _map_rows[y][x]
		tile.color = _get_tile_color(x, y, ch)
	_update_npc_markers()


# ═══════════════════════════════════════════
#  NPC 标记
# ═══════════════════════════════════════════
func _build_npc_index() -> void:
	_npc_at.clear()
	for n: Dictionary in GameManager.npc_catalog:
		if n.get("map", "") == _current_map_id:
			var pos: Vector2i = Vector2i(n.get("x", -1), n.get("y", -1))
			_npc_at[pos] = n


func _build_npc_markers() -> void:
	for c in _npc_markers.get_children():
		c.queue_free()
	_build_npc_index()
	for pos: Vector2i in _npc_at:
		var npc: Dictionary = _npc_at[pos]
		var marker := ColorRect.new()
		marker.color = ACCENT2
		marker.size = Vector2(6, 6)
		marker.position = Vector2(pos.x * TILE_SIZE + TILE_SIZE - 6, pos.y * TILE_SIZE + TILE_SIZE - 6)
		marker.z_index = 5
		marker.name = "NpcMarker_%s" % npc.get("id", "")
		_npc_markers.add_child(marker)


func _update_npc_markers() -> void:
	_build_npc_index()
	for c in _npc_markers.get_children():
		c.queue_free()
	_build_npc_markers()


# ═══════════════════════════════════════════
#  地点标签
# ═══════════════════════════════════════════
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
		# 背景
		var bg := ColorRect.new()
		bg.color = Color(0, 0, 0, 0.55)
		bg.position = label.position - Vector2(3, 1)
		bg.size = Vector2(name.length() * 9 + 6, 13)
		bg.z_index = 2
		_location_labels.add_child(bg)
		_location_labels.add_child(label)


# ═══════════════════════════════════════════
#  瓦片颜色
# ═══════════════════════════════════════════
func _get_tile_color(x: int, y: int, ch: String) -> Color:
	if x == GameManager.player_px and y == GameManager.player_py:
		return ACCENT
	var pos: Vector2i = Vector2i(x, y)
	if _npc_at.has(pos):
		return Color(ACCENT2.r, ACCENT2.g, ACCENT2.b, 0.7)
	return TILE_COLORS.get(ch, DEFAULT_TILE)


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


# ═══════════════════════════════════════════
#  小地图
# ═══════════════════════════════════════════
func _build_minimap() -> void:
	_minimap = SubViewportContainer.new()
	_minimap.name = "Minimap"
	_minimap.position = Vector2(10, 10)  # 相对于 SubViewport 的左上角
	_minimap.stretch = true
	# 在 Godot 4 中，SubViewportContainer 需要 SubViewport 作为子节点
	_minimap_vp = SubViewport.new()
	_minimap_vp.name = "MinimapViewport"
	_minimap_vp.render_target_update_mode = SubViewport.UPDATE_WHEN_VISIBLE
	_minimap.add_child(_minimap_vp)

	_minimap_canvas = Node2D.new()
	_minimap_canvas.name = "MinimapCanvas"
	_minimap_vp.add_child(_minimap_canvas)

	_minimap_viewport_rect = ColorRect.new()
	_minimap_viewport_rect.color = Color(ACCENT.r, ACCENT.g, ACCENT.b, 0.4)
	_minimap_viewport_rect.z_index = 5
	_minimap_canvas.add_child(_minimap_viewport_rect)


func _render_minimap_full() -> void:
	if _map_rows.is_empty():
		return

	var mini_tile: float = 2.0
	var map_w: float = _map_cols * mini_tile
	var map_h: float = _map_rows.size() * mini_tile

	_minimap_vp.size = Vector2(map_w, map_h)
	_minimap.custom_minimum_size = Vector2(map_w, map_h)
	_minimap.size = Vector2(map_w, map_h)

	# 清除旧内容
	for c in _minimap_canvas.get_children():
		if c != _minimap_viewport_rect:
			c.queue_free()

	# 绘制小地图瓦片（用 ColorRect，只画一次）
	for y: int in _map_rows.size():
		var row: String = _map_rows[y]
		for x: int in _map_cols:
			var ch: String = " " if x >= row.length() else row[x]
			var cr := ColorRect.new()
			cr.color = TILE_COLORS.get(ch, DEFAULT_TILE)
			cr.position = Vector2(x * mini_tile, y * mini_tile)
			cr.size = Vector2(mini_tile, mini_tile)
			_minimap_canvas.add_child(cr)

	# NPC 点
	for n: Dictionary in GameManager.npc_catalog:
		if n.get("map", "") == _current_map_id:
			var npc_x: int = n.get("x", -1)
			var npc_y: int = n.get("y", -1)
			if npc_x >= 0 and npc_y >= 0:
				var dot := ColorRect.new()
				dot.color = ACCENT2
				dot.position = Vector2(npc_x * mini_tile, npc_y * mini_tile)
				dot.size = Vector2(mini_tile, mini_tile)
				dot.z_index = 3
				_minimap_canvas.add_child(dot)

	# 玩家点
	var player_dot := ColorRect.new()
	player_dot.color = ACCENT
	player_dot.position = Vector2(GameManager.player_px * mini_tile - 1, GameManager.player_py * mini_tile - 1)
	player_dot.size = Vector2(mini_tile + 2, mini_tile + 2)
	player_dot.z_index = 4
	player_dot.name = "PlayerDot"
	_minimap_canvas.add_child(player_dot)


func _update_minimap() -> void:
	if not _minimap_viewport_rect:
		return
	var mini_tile: float = 2.0
	var vp_rect: Rect2 = get_viewport().get_visible_rect()
	var cam_pos: Vector2 = _camera.position
	var vp_half: Vector2 = vp_rect.size / 2.0

	# 视口矩形
	var vx: float = (cam_pos.x - vp_half.x) / TILE_SIZE * mini_tile
	var vy: float = (cam_pos.y - vp_half.y) / TILE_SIZE * mini_tile
	var vw: float = vp_rect.size.x / TILE_SIZE * mini_tile
	var vh: float = vp_rect.size.y / TILE_SIZE * mini_tile
	_minimap_viewport_rect.position = Vector2(vx, vy)
	_minimap_viewport_rect.size = Vector2(vw, vh)

	# 更新玩家点
	var player_dot: Node = _minimap_canvas.get_node_or_null("PlayerDot")
	if player_dot:
		player_dot.position = Vector2(GameManager.player_px * mini_tile - 1, GameManager.player_py * mini_tile - 1)


# ═══════════════════════════════════════════
#  输入处理
# ═══════════════════════════════════════════
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


func get_current_map_id() -> String:
	return _current_map_id


func is_map_loaded() -> bool:
	return _current_map_id != "" and not _map_rows.is_empty()
