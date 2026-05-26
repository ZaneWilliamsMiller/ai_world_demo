extends Node
## HTTP client for the living-paper Python backend.
## Autoload singleton — use ApiClient.request(...) anywhere.

# ── Config ──
@export var base_url: String = "http://127.0.0.1:8765"
@export var timeout_sec: float = 30.0

# ── Internal ──
var _req_id: int = 0

## Signal-based request — returns the parsed response Dictionary.
## Awaits the actual HTTPRequest completion signal, no spin-wait.
func request(path: String, method: String = "GET", body: Dictionary = {}) -> Dictionary:
	var http := HTTPRequest.new()
	add_child(http)

	var full_url := base_url.rstrip("/") + path
	var headers := PackedStringArray([
		"Content-Type: application/json",
		"Accept: application/json",
	])
	var json_body := JSON.stringify(body) if not body.is_empty() else ""

	var err: Error
	match method:
		"GET":
			err = http.request(full_url, headers, HTTPClient.METHOD_GET)
		"POST":
			err = http.request(full_url, headers, HTTPClient.METHOD_POST, json_body)
		_:
			err = http.request(full_url, headers, HTTPClient.METHOD_POST, json_body)

	print("[API] request() err=%d url=%s" % [err, full_url])

	if err != OK:
		http.queue_free()
		return {"error": "request_failed", "code": err}

	# Await the real completion signal — no spin-wait race condition
	var result_arr := await http.request_completed
	http.queue_free()

	var response_code: int = result_arr[1]
	var body_bytes: PackedByteArray = result_arr[3]
	print("[API] request_completed status=%d body_len=%d" % [response_code, body_bytes.size()])

	if result_arr[0] != HTTPRequest.RESULT_SUCCESS:
		return {"error": "network_error", "code": result_arr[0]}

	var text := body_bytes.get_string_from_utf8()
	var data: Dictionary = {}
	if text.begins_with("{") or text.begins_with("["):
		var json := JSON.new()
		var parse_err := json.parse(text)
		if parse_err == OK:
			data = json.data as Dictionary if json.data is Dictionary else {}
		else:
			data = {"_raw": text}
	else:
		data = {"_raw": text}

	data["_status"] = response_code
	return data


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
				var d: Dictionary = json.data
				if d.has("chunk"):
					full_text += d["chunk"]
					stream_chunk.emit(d["chunk"])
				if d.get("done", false):
					done_data = d
				else:
					if not d.has("chunk") and d.has("visible_text"):
						full_text = d.get("visible_text", "")
						stream_chunk.emit(full_text)
						done_data = d

	stream_done.emit(done_data)
