"""Deep backend test - talk multiple times, trigger reflection, test memory."""
import asyncio
import httpx
import time
import json

BASE = "http://127.0.0.1:8766"
PLAYER_ID = f"deep_test_{int(time.time())}"


async def main():
    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. Create player
        print("[Setup] Creating player...")
        r = await client.post(f"{BASE}/api/hello", json={
            "player_id": PLAYER_ID,
            "display_name": "深度测试者",
            "gender": "男",
            "permadeath": False,
        })
        assert r.status_code == 200
        data = r.json()
        npcs_here = data.get("npcs_here", [])
        assert npcs_here, "No NPCs at spawn!"
        npc_id = npcs_here[0]["id"]
        npc_name = npcs_here[0]["name"]
        print(f"    Player created, talking to {npc_name} ({npc_id})")

        # 2. Talk multiple times to generate observations & build importance
        print("\n[Test] Talking 8 times to build importance...")
        for i in range(8):
            r = await client.post(f"{BASE}/api/npc/talk", json={
                "player_id": PLAYER_ID,
                "npc_id": npc_id,
                "message": f"第{i+1}次对话：你能告诉我关于这个江湖的秘闻吗？",
            })
            if r.status_code != 200:
                print(f"    Talk {i+1} FAILED: {r.status_code} {r.text[:200]}")
                break
            data = r.json()
            print(f"    Talk {i+1}: {data.get('visible_text', '')[:60]}... (ms={data.get('server_ms', 0)})")
        
        # 3. Check if reflection triggers
        print("\n[Test] Checking reflection trigger...")
        r = await client.get(f"{BASE}/api/agent/{PLAYER_ID}/{npc_id}/mind")
        if r.status_code == 200:
            mind_data = r.json()
            print(f"    importance_since_reflect: {mind_data.get('importance_since_reflect', 0)}")
            print(f"    affect_mood: {mind_data.get('affect_mood', 'N/A')}")
            reflections = [m for m in mind_data.get("items", []) if m.get("kind") == "reflection"]
            print(f"    reflections count: {len(reflections)}")
        
        # 4. Force reflection
        print("\n[Test] Forcing reflection...")
        r = await client.post(f"{BASE}/api/agent/reflect", json={
            "player_id": PLAYER_ID,
            "npc_id": npc_id,
        })
        print(f"    Reflect status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"    Reflections added: {data.get('count', 0)}")
            for m in data.get("added", []):
                print(f"    - {m.get('text', '')[:80]}")
        
        # 5. Test streaming talk
        print("\n[Test] Testing streaming talk...")
        r = await client.post(f"{BASE}/api/npc/talk_stream", json={
            "player_id": PLAYER_ID,
            "npc_id": npc_id,
            "message": "用流式方式回答我的问题",
        }, timeout=60.0)
        print(f"    Stream status: {r.status_code}")
        if r.status_code == 200:
            # Read SSE stream
            async for line in r.aiter_lines():
                if line.startswith("data: "):
                    chunk_data = json.loads(line[6:])
                    if chunk_data.get("done"):
                        print(f"    Stream done: {chunk_data}")
                        break
                    chunk = chunk_data.get("chunk", "")
                    if chunk:
                        print(f"    Chunk: {chunk[:30]}...")
                        break  # Just read first chunk for test
        
        # 6. Test memory retrieval (indirectly via talk)
        print("\n[Test] Testing memory via repeated talk...")
        r = await client.post(f"{BASE}/api/npc/talk", json={
            "player_id": PLAYER_ID,
            "npc_id": npc_id,
            "message": "你还记得我之前问过你什么吗？",
        })
        if r.status_code == 200:
            data = r.json()
            print(f"    Memory test response: {data.get('visible_text', '')[:100]}")
        
        # 7. Check circuit breaker stats
        print("\n[Test] Check if circuit breaker is accessible...")
        # Can't directly access from API, but we can check logs
        
        print("\n=== DEEP TEST COMPLETE ===")


if __name__ == "__main__":
    asyncio.run(main())
