extends Node
## HTTP client for the living-paper Python backend.
## Autoload singleton — use ApiClient.request(...) anywhere.

# ── Config ──
@export var base_url: String = "http://127.0.0.1:8765"
@export var timeout_sec: float = 30.0

# ── Internal ──
var _pending: Dictionary = {}   # request_id → Callable(result)
var _req_id: int = 0


func request(path: String, method: String = "GET", body: Dictionary = {}) -> Dictionary:
	"""Synchronous wrapper — blocks until response arrives.  Use in UI code."""
	var done := false
	var result: Dictionary = {}

	_send(path, method, body, func(r: Dictionary):
		result = r
		done = true
	)

	# Spin-wait (only used from UI buttons, so this is fine)
	var t0 := Time.get_ticks_msec()
	while not done and (Time.get_ticks_msec() - t0) < timeout_sec * 1000:
		await get_tree().process_frame

	if not done:
		result = {"error": "timeout"}
	return result


func _send(path: String, method: String, body: Dictionary, callback: Callable) -> void:
	var http := HTTPRequest.new()
	add_child(http)

	var full_url := base_url.rstrip("/") + path
	var headers := PackedStringArray([
		"Content-Type: application/json",
		"Accept: application/json",
	])
	var json_body := JSON.stringify(body) if not body.is_empty() else ""

	_req_id += 1
	var rid := _req_id
	_pending[rid] = callback

	http.request_completed.connect(_on_complete.bind(rid, http))

	var err: Error
	match method:
		"GET":
			err = http.request(full_url, headers, HTTPClient.METHOD_GET)
		"POST":
			err = http.request(full_url, headers, HTTPClient.METHOD_POST, json_body)
		_:
			err = http.request(full_url, headers, HTTPClient.METHOD_POST, json_body)

	if err != OK:
		_pending.erase(rid)
		callback.call({"error": "request_failed", "code": err})


func _on_complete(result: int, response_code: int, headers: PackedStringArray, body: PackedByteArray, rid: int, http: HTTPRequest) -> void:
	var cb = _pending.get(rid)
	_pending.erase(rid)
	http.queue_free()

	if result != HTTPRequest.RESULT_SUCCESS:
		if cb.is_valid():
			cb.call({"error": "network_error", "code": result})
		return

	var text := body.get_string_from_utf8()
	var data: Dictionary = {}
	if text.begins_with("{") or text.begins_with("["):
		var json := JSON.new()
		var err := json.parse(text)
		if err == OK:
			data = json.data as Dictionary
		else:
			data = {"_raw": text}
	else:
		data = {"_raw": text}

	data["_status"] = response_code
	if cb.is_valid():
		cb.call(data)


## Talk to NPC with Server-Sent Events (streaming).
## Yields chunks as the server responds.
signal stream_chunk(chunk: String)
signal stream_done(data: Dictionary)

func talk_stream(player_id: String, npc_id: String, message: String) -> void:
	var http := HTTPRequest.new()
	add_child(http)

	var full_url := base_url.rstrip("/") + "/api/npc/talk_stream"
	var headers := PackedStringArray([
		"Content-Type: application/json",
		"Accept: text/event-stream",
	])
	var json_body := JSON.stringify({
		"player_id": player_id,
		"npc_id": npc_id,
		"message": message
	})

	# For SSE, we use a blocking-style HTTP request; Godot's HTTPRequest
	# doesn't natively support streaming, so we fall back to polling.
	# We send the request and when it completes, we parse the SSE body.
	http.request_completed.connect(_on_stream_complete.bind(http))
	http.request(full_url, headers, HTTPClient.METHOD_POST, json_body)


func _on_stream_complete(result: int, response_code: int, headers: PackedStringArray, body: PackedByteArray, http: HTTPRequest) -> void:
	http.queue_free()

	var text := body.get_string_from_utf8()
	var lines := text.split("\n")
	var full_text := ""
	var done_data: Dictionary = {}

	for line in lines:
		if line.begins_with("data: "):
			var payload := line.substr(6)
			var json := JSON.new()
			if json.parse(payload) == OK:
				var d := json.data
				if d.has("chunk"):
					full_text += d["chunk"]
					stream_chunk.emit(d["chunk"])
				if d.get("done", false):
					done_data = d
				else:
					# non-stream fallback: the whole response is in done chunk
					if not d.has("chunk") and d.has("visible_text"):
						full_text = d.get("visible_text", "")
						stream_chunk.emit(full_text)
						done_data = d

	stream_done.emit(done_data)
