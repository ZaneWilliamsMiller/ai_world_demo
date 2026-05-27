extends Node
## HTTP client for the living-paper backend & direct LLM API.
## Autoload singleton — use ApiClient.request(...) anywhere.
##
## Supports two modes:
##   "backend"  — all requests go through Python backend
##   "direct"   — LLM calls go directly to Paratera API

# ── Config (exported for editor-time override) ──
@export var backend_url: String = "http://127.0.0.1:8765"
@export var llm_api_url: String = ""
@export var llm_api_key: String = ""
@export var llm_model: String = ""
@export var timeout_sec: float = 30.0

## Current API mode: "backend" or "direct"
var api_mode: String = "backend"

# ── Internal ──
var _req_id: int = 0

## Signal-based request — returns the parsed response Dictionary.
## Awaits the actual HTTPRequest completion signal.
func request(path: String, method: String = "GET", body: Dictionary = {}) -> Dictionary:
	var http := HTTPRequest.new()
	add_child(http)

	var full_url := backend_url.rstrip("/") + path
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

	var result_arr: Array = await http.request_completed
	http.queue_free()

	var response_code: int = int(result_arr[1])
	var body_bytes: PackedByteArray = result_arr[3] as PackedByteArray

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


## Direct LLM chat completion (bypasses backend).
func llm_chat(messages: Array[Dictionary], temperature: float = 0.7, max_tokens: int = 1024) -> Dictionary:
	var http := HTTPRequest.new()
	add_child(http)

	var full_url := llm_api_url.rstrip("/") + "/chat/completions"
	var headers := PackedStringArray([
		"Content-Type: application/json",
		"Authorization: Bearer " + llm_api_key,
	])
	var body_dict := {
		"model": llm_model,
		"messages": messages,
		"temperature": temperature,
		"max_tokens": max_tokens,
	}
	var json_body := JSON.stringify(body_dict)

	var err := http.request(full_url, headers, HTTPClient.METHOD_POST, json_body)
	if err != OK:
		http.queue_free()
		return {"error": "request_failed", "code": err}

	var result_arr: Array = await http.request_completed
	http.queue_free()

	var response_code: int = int(result_arr[1])
	var body_bytes: PackedByteArray = result_arr[3] as PackedByteArray

	if result_arr[0] != HTTPRequest.RESULT_SUCCESS:
		return {"error": "network_error", "code": result_arr[0]}

	var text := body_bytes.get_string_from_utf8()
	var json := JSON.new()
	if json.parse(text) != OK:
		return {"error": "parse_error", "_raw": text}

	var data: Dictionary = json.data as Dictionary if json.data is Dictionary else {}
	data["_status"] = response_code
	return data


## Talk to NPC with Server-Sent Events (streaming).
signal stream_chunk(chunk: String)
signal stream_done(data: Dictionary)

func talk_stream(player_id: String, npc_id: String, message: String) -> void:
	var http := HTTPRequest.new()
	add_child(http)

	var full_url := backend_url.rstrip("/") + "/api/npc/talk_stream"
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


## Test backend connection.
func test_backend() -> bool:
	var res: Dictionary = await request("/api/health", "GET", {})
	return res.get("_status", 0) == 200 and res.get("status", "") == "ok"


## Test LLM direct connection.
func test_llm() -> bool:
	var messages: Array[Dictionary] = [{"role": "user", "content": "hi"}]
	var res: Dictionary = await llm_chat(messages, 0.5, 20)
	return res.get("_status", 0) == 200 and res.has("choices")


## List available tests.
func list_tests() -> Dictionary:
	var res: Dictionary = await request("/api/tests/list", "GET", {})
	if res.get("_status", 0) == 200:
		res.erase("_status")
		return res
	return {"count": 0, "tests": []}


## Run a specific test.
func run_test(test_name: String) -> Dictionary:
	var res: Dictionary = await request("/api/tests/run/%s" % test_name, "POST", {})
	if res.get("_status", 0) == 200:
		res.erase("_status")
		return res
	return {"success": false, "output": "请求失败: HTTP %d" % res.get("_status", 0)}


## Shutdown backend server.
func shutdown_backend() -> Dictionary:
	var res: Dictionary = await request("/api/shutdown", "POST", {})
	return {"success": res.get("_status", 0) == 200, "_status": res.get("_status", 0)}
