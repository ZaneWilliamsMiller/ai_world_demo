"""Backend API test script for living-paper."""
import asyncio
import httpx
import time
import json

BASE = "http://127.0.0.1:8766"
PLAYER_ID = f"test_player_{int(time.time())}"


async def test_health(client):
    print("[1] Health check...")
    r = await client.get(f"{BASE}/api/health")
    print(f"    Status: {r.status_code}, Body: {r.json()}")
    assert r.status_code == 200
    print("    PASS")


async def test_hello(client):
    print("[2] Hello (create player)...")
    r = await client.post(f"{BASE}/api/hello", json={
        "player_id": PLAYER_ID,
        "display_name": "测试剑客",
        "gender": "男",
        "permadeath": False,
    })
    print(f"    Status: {r.status_code}")
    assert r.status_code == 200, f"Failed: {r.text}"
    data = r.json()
    print(f"    player_id={data.get('player_id')}, map={data['player']['map_id']}")
    print(f"    NPCs here: {[n['name'] for n in data.get('npcs_here', [])]}")
    print("    PASS")
    return data


async def test_state(client):
    print("[3] Get state...")
    r = await client.get(f"{BASE}/api/state/{PLAYER_ID}")
    assert r.status_code == 200, f"Failed: {r.text}"
    data = r.json()
    p = data["player"]
    print(f"    vigor={p['vigor']}, spirit={p['spirit']}, coins={p['coins']}")
    print(f"    world_day={p['world_day']}, shichen={p['world_shichen']}")
    print("    PASS")


async def test_talk(client, npc_id):
    print(f"[4] Talk to NPC {npc_id}...")
    r = await client.post(f"{BASE}/api/npc/talk", json={
        "player_id": PLAYER_ID,
        "npc_id": npc_id,
        "message": "你好，请问这里是什么地方？",
    })
    if r.status_code != 200:
        print(f"    NPC not here (status={r.status_code})")
        return False
    data = r.json()
    print(f"    visible_text: {data.get('visible_text', '')[:100]}...")
    print(f"    server_ms: {data.get('server_ms', 0)}")
    print("    PASS")
    return True


async def test_move(client):
    print("[5] Move...")
    r = await client.post(f"{BASE}/api/move", json={
        "player_id": PLAYER_ID,
        "to_x": 5,
        "to_y": 5,
    })
    assert r.status_code == 200, f"Failed: {r.text}"
    data = r.json()
    p = data["player"]
    print(f"    New pos: ({p['px']}, {p['py']})")
    print(f"    vigor_delta={data.get('delta', {}).get('vigor', 0)}")
    print("    PASS")


async def test_memory_system(client, npc_id):
    print(f"[6] Test memory/reflection for {npc_id}...")
    r = await client.post(f"{BASE}/api/agent/reflect", json={
        "player_id": PLAYER_ID,
        "npc_id": npc_id,
    })
    print(f"    Reflect status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"    Reflections added: {data.get('count', 0)}")
    print("    PASS (non-blocking)")


async def main():
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            await test_health(client)
            data = await test_hello(client)
            
            # Find an NPC at starting location
            npcs_here = data.get("npcs_here", [])
            if npcs_here:
                npc_id = npcs_here[0]["id"]
                print(f"    Will talk to: {npcs_here[0]['name']} ({npc_id})")
                await test_talk(client, npc_id)
                await test_memory_system(client, npc_id)
            else:
                print("    No NPCs at starting location")
            
            await test_state(client)
            await test_move(client)
            
            print("\n=== ALL TESTS PASSED ===")
        except Exception as e:
            print(f"\n!!! TEST FAILED: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
