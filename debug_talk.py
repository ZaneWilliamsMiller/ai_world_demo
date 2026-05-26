import httpx, asyncio, json, time, sys

BASE = "http://127.0.0.1:8766"

async def test():
    player_id = f"debug_{int(time.time())}"
    async with httpx.AsyncClient(timeout=60.0) as cli:
        r = await cli.post(f"{BASE}/api/hello", json={
            "player_id": player_id,
            "display_name": "Debug_Tester",
            "gender": "男",
            "permadeath": False,
        })
        data = r.json()
        npcs_here = data.get("npcs_here", [])
        sys.stdout.write(f"[Hello] NPC: {npcs_here}\n")
        sys.stdout.flush()

        if not npcs_here:
            sys.stdout.write(f"FAILURE: {r.status_code}\n")
            return
        npc_id = npcs_here[0]["id"]

        sys.stdout.write(f"[Talk] Sending to {npc_id}...\n")
        r = await cli.post(f"{BASE}/api/npc/talk", json={
            "player_id": player_id,
            "npc_id": npc_id,
            "message": "你好，请自我介绍。",
        })

        sys.stdout.write(f"[Result] Status: {r.status_code}\n")
        if r.status_code == 200:
            data = r.json()
            for k, v in data.items():
                val = str(v)
                if len(val) > 120:
                    val = val[:120] + "..."
                sys.stdout.write(f"  {k}: {val}\n")
        else:
            sys.stdout.write(f"[Error]: {r.text[:500]}\n")
        sys.stdout.flush()

asyncio.run(test())