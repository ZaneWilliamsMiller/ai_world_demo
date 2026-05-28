"""Edge-case E2E test for living-paper backend."""
import httpx, asyncio, os, time, json, sys

BASE = os.environ.get("BACKEND_URL", "http://127.0.0.1:8765")
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
    player_id = f"edge_{int(time.time())}"
    async with httpx.AsyncClient(timeout=60.0) as c:
        
        # Hello
        r = await c.post(f"{BASE}/api/hello", json={
            "player_id": player_id, "display_name": "边界测试者",
            "gender": "女", "permadeath": False,
        })
        data = r.json()
        npc_id = data["npcs_here"][0]["id"]
        
        # === Talk with special characters ===
        sys.stdout.write("=== Special char Talk ===\n")
        r = await c.post(f"{BASE}/api/npc/talk", json={
            "player_id": player_id, "npc_id": npc_id,
            "message": "你好！我需要「路引」和'银票'。价格如何？",
        })
        data = r.json()
        report("200 status", r.status_code == 200)
        report("has visible_text", "visible_text" in data)
        report("visible_text len>20", len(data.get("visible_text","")) > 20)
        
        # === Talk with empty message (should 422) ===
        sys.stdout.write("=== Empty message (should 422) ===\n")
        r = await c.post(f"{BASE}/api/npc/talk", json={
            "player_id": player_id, "npc_id": npc_id,
            "message": "",
        })
        report("422 for empty", r.status_code == 422)
        
        # === Move to a valid position ===
        sys.stdout.write("=== Move ===\n")
        r = await c.post(f"{BASE}/api/move", json={
            "player_id": player_id, "to_x": 8, "to_y": 12,
        })
        data = r.json()
        report("200 status", r.status_code == 200)
        report("path len>0", len(data.get("path", [])) > 0)
        report("player moved", data["player"]["px"] == 8 and data["player"]["py"] == 12)
        
        # === Agent Mind (after talk) ===
        sys.stdout.write("=== Agent Mind ===\n")
        r = await c.get(f"{BASE}/api/agent/{player_id}/{npc_id}/mind")
        data = r.json()
        report("200 status", r.status_code == 200)
        report("has items", len(data.get("items", [])) > 0)
        report("has plan", bool(data.get("plan_summary")))
        
        # === Saves ===
        sys.stdout.write("=== Saves ===\n")
        r = await c.post(f"{BASE}/api/save", json={"player_id": player_id})
        report("save 200", r.status_code == 200)
        
        r = await c.get(f"{BASE}/api/saves")
        report("list saves 200", r.status_code == 200)
        report("saves non-empty", len(r.json().get("saves", [])) > 0)
        
        # === Load (reload the saved game) ===
        sys.stdout.write("=== Load ===\n")
        r = await c.post(f"{BASE}/api/load", json={
            "player_id": player_id, "display_name": "边界测试者",
            "gender": "女", "permadeath": False,
        })
        report("load 200", r.status_code == 200)
        data = r.json()
        report("loaded player_id", data.get("player_id") == player_id)
        
        # === Talk stream ===
        sys.stdout.write("=== Talk stream ===\n")
        r = await c.post(f"{BASE}/api/npc/talk_stream", json={
            "player_id": player_id, "npc_id": npc_id,
            "message": "讲讲这个地方的传说吧。",
        })
        report("200 status", r.status_code == 200)
        full = ""
        done_data = {}
        async for line in r.aiter_lines():
            if line.startswith("data: "):
                try:
                    d = json.loads(line[6:])
                except:
                    continue
                if d.get("done"):
                    done_data = d
                    break
                if "chunk" in d:
                    full += d["chunk"]
        report("stream has text", len(full) > 20)
        report("done received", bool(done_data))
        if done_data:
            report("done has visible_text", "visible_text" in done_data or "reply" in done_data)
        
        # === Invalid NPC (should 400) ===
        sys.stdout.write("=== Invalid NPC ===\n")
        r = await c.post(f"{BASE}/api/npc/talk", json={
            "player_id": player_id, "npc_id": "nonexistent",
            "message": "hi",
        })
        report("400 for bad npc", r.status_code == 400)
        
        # === Invalid player (should 404) ===
        sys.stdout.write("=== Invalid player ===\n")
        r = await c.get(f"{BASE}/api/state/nonexistent_player")
        report("404 for bad player", r.status_code == 404)
        
        # === Delete save ===
        sys.stdout.write("=== Delete save ===\n")
        r = await c.post(f"{BASE}/api/delete-save", json={"player_id": player_id})
        report("delete 200", r.status_code == 200)
        report("delete ok", r.json().get("ok") is True)
        
        # === Summary ===
        sys.stdout.write(f"\n=== Results: {OK} passed, {FAIL} failed ===\n")
        return FAIL == 0

if __name__ == "__main__":
    success = asyncio.run(test())
    sys.exit(0 if success else 1)