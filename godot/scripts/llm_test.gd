extends Node
## LLM connection test script for Godot.
## Run from command line: godot --headless --script res://scripts/llm_test.gd

func _ready() -> void:
	print("=== Living Paper Godot LLM Test ===")
	print("")
	print("Testing backend connection...")
	var backend_ok: bool = await ApiClient.test_backend()
	print("Backend: %s" % ("OK" if backend_ok else "FAIL"))
	print("")
	print("Testing LLM direct connection...")
	var llm_ok: bool = await ApiClient.test_llm()
	print("LLM Direct: %s" % ("OK" if llm_ok else "FAIL"))
	print("")
	print("=== Test Complete ===")
	get_tree().quit()
