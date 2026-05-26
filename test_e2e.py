"""Comprehensive end-to-end test for living-paper backend."""
import httpx, asyncio, time, json, sys

BASE = "http://127.0.0.1:8766"
OK, FAIL = 0, 0

def report(name, cond, detail=""):
    global OK, FAIL
    if cond:
        OK += 1
        sys.stdout.write(f"  [PASS] {name} {detail}\n")
    else:
        FAIL += 1
        sys.stdout.write(f"  [FAIL] {name} {detail}\n")

async def test():
    player_id = f"e2e_{int(time.time())}"
    async with httpx.AsyncClient(timeout=60.0) as c:
        
        # === Health ===
        sys.stdout.write("=== Health Check ===\n")
        r = await c.get(f"{BASE}/api/health")
        data = r.json()
        report("200 status", r.status_code == 200)
        report("model field", data.get("model") == "DeepSeek-V4-Pro")
        
        # === Hello ===
        sys.stdout.write("=== Hello ===\n")
        r = await c.post(f"{BASE}/api/hello", json={
            "player_id": player_id, "display_name": "E2E测试者",
            "gender": "男", "permadeath": False,
        })
        data = r.json()
        report("200 status", r.status_code == 200)
        report("player_id match", data["player_id"] == player_id)
        report("has npcs_here", len(data.get("npcs_here", [])) > 0)
        report("player vigor exists", data["player"]["vigor"] >= 0)
        
        npc_id = data["npcs_here"][0]["id"]
        
        # === Talk (non-stream) ===
        sys.stdout.write("=== Talk (non-stream) ===\n")
        r = await c.post(f"{BASE}/api/npc/talk", json={
            "player_id": player_id, "npc_id": npc_id,
            "message": "你好，请做自我介绍。",
        })
        data = r.json()
        report("200 status", r.status_code == 200)
        report("visible_text present", "visible_text" in data)
        report("visible_text non-empty", len(data.get("visible_text","")) > 10)
        report("reply present (backward compat)", "reply" in data)
        report("llm_fallback is False", not data.get("llm_fallback", False))
        report(f"server_ms present ({data.get('server_ms', 0)}ms)", data.get("server_ms", 0) > 0)
        sys.stdout.write(f"  [INFO] visible_text[:80]: {(data.get('visible_text',''))[:80]}\n")
        
        # === Talk (streaming) ===
        sys.stdout.write("=== Talk (streaming) ===\n")
        r = await c.post(f"{BASE}/api/npc/talk_stream", json={
            "player_id": player_id, "npc_id": npc_id,
            "message": "再聊聊这个江湖的趣闻吧。",
        })
        report("200 status", r.status_code == 200)
        chunks = []
        done_data = {}
        async for line in r.aiter_lines():
            if line.startswith("data: "):
                try:
                    chunk_data = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue
                if chunk_data.get("done"):
                    done_data = chunk_data
                    break
                if "chunk" in chunk_data:
                    chunks.append(chunk_data["chunk"])
        full_text = "".join(chunks)
        report("stream has chunks", len(chunks) > 0)
        report("stream text non-empty", len(full_text) > 10)
        if done_data:
            report("done has visible_text", "visible_text" in done_data or "reply" in done_data)
            report("done has server_ms", done_data.get("server_ms", 0) > 0)
        else:
            report("done received", False)
        
        # === Talk x3 more (build memory importance) ===
        sys.stdout.write("=== Multi-Talk (importance buildup) ===\n")
        for i in range(3):
            r = await c.post(f"{BASE}/api/npc/talk", json={
                "player_id": player_id, "npc_id": npc_id,
                "message": f"第{i+1}次对话：继续聊聊。",
            })
            report(f"talk {i+4}/4 OK", r.status_code == 200)
            data = r.json()
            report(f"talk {i+4}/4 has visible_text", "visible_text" in data)
        
        # === State ===
        sys.stdout.write("=== State ===\n")
        r = await c.get(f"{BASE}/api/state/{player_id}")
        data = r.json()
        report("200 status", r.status_code == 200)
        report("player info present", "player" in data)
        
        # === Move ===
        sys.stdout.write("=== Move ===\n")
        r = await c.post(f"{BASE}/api/move", json={
            "player_id": player_id, "to_x": 5, "to_y": 5,
        })
        data = r.json()
        report("200 status", r.status_code == 200)
        report("path returned", len(data.get("path", [])) > 0)
        
        # === Agent Mind (after talk) ===
        sys.stdout.write("=== Agent Mind ===\n")
        r = await c.get(f"{BASE}/api/agent/{player_id}/{npc_id}/mind")
        data = r.json()
        report("200 status", r.status_code == 200)
        report("mind has items", len(data.get("items", [])) > 0)
        report("has mood info", "affect_mood" in data)
        
        # === Agent Reflect ===
        sys.stdout.write("=== Agent Reflect ===\n")
        r = await c.post(f"{BASE}/api/agent/reflect", json={
            "player_id": player_id, "npc_id": npc_id,
        })
        data = r.json()
        report("200 status", r.status_code == 200)
        
        # === Summary ===
        sys.stdout.write(f"\n=== Results: {OK} passed, {FAIL} failed ===\n")
        return FAIL == 0

if __name__ == "__main__":
    success = asyncio.run(test())
    sys.exit(0 if success else 1)