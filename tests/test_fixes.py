import httpx, asyncio, time, json, sys

BASE = "http://127.0.0.1:8766"

async def test():
    player_id = f"fix_test_{int(time.time())}"
    async with httpx.AsyncClient(timeout=60.0) as c:
        # Hello
        r = await c.post(f"{BASE}/api/hello", json={
            "player_id": player_id,
            "display_name": "修复验证者",
            "gender": "男",
            "permadeath": False,
        })
        assert r.status_code == 200
        npc_id = r.json()["npcs_here"][0]["id"]
        
        # Talk
        r = await c.post(f"{BASE}/api/npc/talk", json={
            "player_id": player_id,
            "npc_id": npc_id,
            "message": "你好，自我介绍一下吧。",
        })
        assert r.status_code == 200
        data = r.json()
        
        # Check keys
        has_visible = "visible_text" in data
        has_reply = "reply" in data
        vis_len = len(data.get("visible_text", ""))
        rep_len = len(data.get("reply", ""))
        llm_fallback = data.get("llm_fallback", False)
        
        sys.stdout.write(f"visible_text in response: {has_visible}\n")
        sys.stdout.write(f"reply in response: {has_reply}\n")
        sys.stdout.write(f"visible_text length: {vis_len}\n")
        sys.stdout.write(f"reply length: {rep_len}\n")
        sys.stdout.write(f"llm_fallback: {llm_fallback}\n")
        sys.stdout.write(f"server_ms: {data.get('server_ms', 'N/A')}\n")
        
        assert has_visible, "FAIL: visible_text not in response!"
        assert vis_len > 10, f"FAIL: visible_text too short ({vis_len})"
        assert not llm_fallback, f"FAIL: llm_fallback activated!"
        sys.stdout.write("\n=== ALL FIX VERIFICATIONS PASSED ===\n")

if __name__ == "__main__":
    asyncio.run(test())