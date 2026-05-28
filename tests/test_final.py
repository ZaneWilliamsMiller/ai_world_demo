"""Final comprehensive test after all fixes."""
import httpx, asyncio, os, time, json, sys

BASE = os.environ.get("BACKEND_URL", "http://127.0.0.1:8765")
OK, FAIL = 0, 0

def report(name, cond, detail=""):
    global OK, FAIL
    tag = "[PASS]" if cond else "[FAIL]"
    if cond: OK += 1
    else: FAIL += 1
    sys.stdout.write(f"  {tag} {name} {detail}\n")

async def test():
    pid = f"final_{int(time.time())}"
    async with httpx.AsyncClient(timeout=60.0) as c:
        
        # 1. Hello
        r = await c.post(f"{BASE}/api/hello", json={
            "player_id": pid, "display_name": "终测者",
            "gender": "男", "permadeath": False,
        })
        data = r.json()
        npc0 = data["npcs_here"][0]["id"]
        report("hello 200", r.status_code == 200, f"npc={npc0}")
        
        # 2. Talk 1
        r = await c.post(f"{BASE}/api/npc/talk", json={
            "player_id": pid, "npc_id": npc0,
            "message": "你好，请问这里是什么地方？",
        })
        d = r.json()
        report("talk1 200", r.status_code == 200)
        report("talk1 no fallback", not d.get("llm_fallback", False))
        report("talk1 visible_text len>50", len(d.get("visible_text","")) > 50, f"len={len(d.get('visible_text',''))}")
        report("talk1 reply==visible", d.get("reply") == d.get("visible_text"))
        report("talk1 server_ms>0", d.get("server_ms", 0) > 0, f"ms={d.get('server_ms',0)}")
        
        # 3. Talk 2 (importance buildup)
        r = await c.post(f"{BASE}/api/npc/talk", json={
            "player_id": pid, "npc_id": npc0,
            "message": "我在找一份情报，关于漕帮的。",
        })
        d = r.json()
        report("talk2 200", r.status_code == 200)
        report("talk2 visible_text len>50", len(d.get("visible_text","")) > 50)
        
        # 4. Agent Plan (triggers daily planning for NPC)
        r = await c.post(f"{BASE}/api/agent/plan", json={
            "player_id": pid, "npc_id": npc0,
        })
        report("plan 200", r.status_code == 200, f"status={r.status_code}")
        
        # 5. Agent Mind (now should have plan)
        r = await c.get(f"{BASE}/api/agent/{pid}/{npc0}/mind")
        d = r.json()
        report("mind 200", r.status_code == 200)
        report("mind has items", len(d.get("items", [])) > 0)
        has_plan = bool(d.get("plan_summary") or d.get("plan_by_shichen"))
        report("mind has plan", has_plan, f"plan_summary={d.get('plan_summary','')[:30]}")
        
        # 6. State
        r = await c.get(f"{BASE}/api/state/{pid}")
        d = r.json()
        report("state 200", r.status_code == 200)
        report("state has player", "player" in d)
        report("state vigor in range", 0 <= d.get("player",{}).get("vigor",50) <= 100)
        
        # 7. Move
        r = await c.post(f"{BASE}/api/move", json={
            "player_id": pid, "to_x": 5, "to_y": 8,
        })
        d = r.json()
        report("move 200", r.status_code == 200)
        report("move path len>0", len(d.get("path",[])) > 0)
        
        # 8. Save & Load
        r = await c.post(f"{BASE}/api/save", json={"player_id": pid})
        report("save 200", r.status_code == 200)
        r = await c.get(f"{BASE}/api/saves")
        report("saves 200", r.status_code == 200)
        report("saves lists pid", any(pid in s.get("player_id","") for s in r.json().get("saves",[])))
        
        # 9. Health
        r = await c.get(f"{BASE}/api/health")
        d = r.json()
        report("health 200", r.status_code == 200)
        report("health has model", bool(d.get("model")))
        
        # 10. Delete save (cleanup)
        r = await c.post(f"{BASE}/api/delete-save", json={"player_id": pid})
        report("delete 200", r.status_code == 200)
        
        sys.stdout.write(f"\n=== FINAL: {OK} passed, {FAIL} failed ===\n")
        return FAIL == 0

if __name__ == "__main__":
    ok = asyncio.run(test())
    sys.exit(0 if ok else 1)