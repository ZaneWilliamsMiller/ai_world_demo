extends Node
## HTTP client for the living-paper backend.
## Autoload singleton — use ApiClient.request(...) anywhere.

@export var backend_url: String = ""
@export var timeout_sec: float = 30.0
var shutdown_secret: String = ""

var _req_id: int = 0
var _active_stream_http: HTTPClient = null
var _streaming: bool = false

## Signal-based request — returns the parsed response Dictionary.
## Awaits the actual HTTPRequest completion signal.
func request(path: String, method: String = "GET", body: Dictionary = {}, extra_headers: Dictionary = {}) -> Dictionary:
	var http := HTTPRequest.new()
	add_child(http)
	http.timeout = timeout_sec

	var full_url := backend_url.rstrip("/") + path
	var headers := PackedStringArray([
		"Content-Type: application/json",
		"Accept: application/json",
	])
	for key in extra_headers:
		headers.append(key + ": " + str(extra_headers[key]))
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
	if response_code >= 400:
		data["error"] = data.get("detail", "HTTP %d" % response_code)
	return data


## Talk to NPC with Server-Sent Events (streaming).
signal stream_chunk(chunk: String)
signal stream_done(data: Dictionary)

func _base_url() -> String:
	return backend_url.rstrip("/")


func _end_stream() -> void:
	_active_stream_http = null
	_streaming = false


func cancel_stream() -> void:
	if _active_stream_http:
		_active_stream_http.close()
	_end_stream()
	emit_signal("stream_done", {"done": true, "cancelled": true})


func talk_stream(npc_id: String, message: String, player_id: String = "") -> void:
	if _streaming:
		emit_signal("stream_done", {"error": "已有流式对话进行中，请等待完成或取消", "done": true})
		return
	_streaming = true
	var url_path := "/api/npc/talk_stream"
	var body_dict := {
		"player_id": player_id if player_id else GameManager.player_id,
		"npc_id": npc_id,
		"message": message,
	}

	var body_json := JSON.stringify(body_dict)
	var base_url := _base_url()
	if base_url.is_empty():
		emit_signal("stream_done", {"error": "后端地址未配置", "done": true})
		_streaming = false
		return
	var host := ""
	var port := 80
	var use_tls := false

	if base_url.begins_with("https://"):
		var parts := base_url.substr(8).split("/")
		var hostport := parts[0].split(":")
		host = hostport[0]
		if hostport.size() > 1:
			port = int(hostport[1])
		else:
			port = 443
		use_tls = true
	elif base_url.begins_with("http://"):
		var parts := base_url.substr(7).split("/")
		var hostport := parts[0].split(":")
		host = hostport[0]
		if hostport.size() > 1:
			port = int(hostport[1])

	var http := HTTPClient.new()

	_active_stream_http = http

	var tls_options: TLSOptions = TLSOptions.client() if use_tls else null
	var err := http.connect_to_host(host, port, tls_options)
	if err != OK:
		http.close()
		_end_stream()
		emit_signal("stream_done", {"error": "connect_failed", "done": true})
		return

	var _connect_start_msec := Time.get_ticks_msec()
	while http.get_status() == HTTPClient.STATUS_CONNECTING or http.get_status() == HTTPClient.STATUS_RESOLVING:
		http.poll()
		if (Time.get_ticks_msec() - _connect_start_msec) > 15000:
			http.close()
			_end_stream()
			emit_signal("stream_done", {"error": "连接超时(15s)", "done": true})
			return
		await get_tree().process_frame

	if http.get_status() != HTTPClient.STATUS_CONNECTED:
		http.close()
		_end_stream()
		emit_signal("stream_done", {"error": "connection_failed", "done": true})
		return

	var headers := PackedStringArray([
		"Content-Type: application/json",
		"Accept: text/event-stream",
	])

	err = http.request(HTTPClient.METHOD_POST, url_path, headers, body_json)
	if err != OK:
		http.close()
		_end_stream()
		emit_signal("stream_done", {"error": "request_failed", "done": true})
		return

	var _request_start_msec := Time.get_ticks_msec()
	while http.get_status() == HTTPClient.STATUS_REQUESTING:
		http.poll()
		if (Time.get_ticks_msec() - _request_start_msec) > 30000:
			http.close()
			_end_stream()
			emit_signal("stream_done", {"error": "请求超时(30s)", "done": true})
			return
		await get_tree().process_frame

	if http.get_status() != HTTPClient.STATUS_BODY:
		http.close()
		_end_stream()
		emit_signal("stream_done", {"error": "request_error", "done": true})
		return

	var buf := ""
	var response_code := http.get_response_code()
	if response_code != 200:
		var rb := PackedByteArray()
		while http.get_status() == HTTPClient.STATUS_BODY:
			http.poll()
			var chunk := http.read_response_body_chunk()
			if chunk.size() > 0:
				rb.append_array(chunk)
			await get_tree().process_frame
		http.close()
		_end_stream()
		var error_text := rb.get_string_from_utf8()
		emit_signal("stream_done", {"error": "HTTP %d: %s" % [response_code, error_text.left(200)], "done": true})
		return

	var frame_count := 0
	var max_frames := 60 * 60
	while http.get_status() == HTTPClient.STATUS_BODY:
		http.poll()
		frame_count += 1
		if frame_count > max_frames:
			http.close()
			_end_stream()
			emit_signal("stream_done", {"error": "流式响应超时", "done": true})
			return
		var chunk := http.read_response_body_chunk()
		if chunk.size() > 0:
			buf += chunk.get_string_from_utf8()
			var lines := buf.split("\n")
			buf = lines.pop_back()
			for line in lines:
				if not line.begins_with("data: "):
					continue
				var payload := line.substr(6).strip_edges()
				if payload == "":
					continue
				var json := JSON.new()
				if json.parse(payload) != OK:
					continue
				var d = json.data if json.data is Dictionary else {}
				if d.has("chunk"):
					emit_signal("stream_chunk", d.chunk)
				if d.has("error"):
					emit_signal("stream_chunk", "[错误] " + str(d.error))
				if d.has("done") and d.done:
					http.close()
					_end_stream()
					emit_signal("stream_done", d)
					return
		await get_tree().process_frame

	http.close()
	_end_stream()
	emit_signal("stream_done", {"done": true})


func _exit_tree() -> void:
	if _active_stream_http:
		_active_stream_http.close()
		_end_stream()


## Test backend connection.
func test_backend() -> bool:
	var res: Dictionary = await request("/api/health", "GET", {})
	if res.get("_status", 0) == 200 and res.get("status", "") == "ok":
		if res.get("shutdown_configured") == "true" and shutdown_secret == "":
			shutdown_secret = "dev"
		return true
	return false


## Shutdown backend server.
func shutdown_backend() -> Dictionary:
	var secret := shutdown_secret
	if secret == "":
		secret = OS.get_environment("SHUTDOWN_SECRET")
	var extra := {}
	if secret != "":
		extra["X-Shutdown-Secret"] = secret
	var res: Dictionary = await request("/api/shutdown", "POST", {}, extra)
	return {"success": res.get("_status", 0) == 200}


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
