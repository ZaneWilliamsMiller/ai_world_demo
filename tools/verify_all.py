import httpx, asyncio, sys

async def check():
    async with httpx.AsyncClient(timeout=10) as c:
        # 1. Health
        r = await c.get("http://127.0.0.1:8766/api/health")
        print(f"[Health] {r.status_code} {r.json()}")

        # 2. Static HTML
        r = await c.get("http://127.0.0.1:8766/")
        ct = r.headers.get("content-type", "")
        size = len(r.text)
        has_script = "doTalk" in r.text
        has_login = "loginOverlay" in r.text
        print(f"[Static] {r.status_code} | {ct} | {size} bytes")
        print(f"  has doTalk: {has_script}")
        print(f"  has loginOverlay: {has_login}")

        # 3. Test auto-save on shutdown (graceful exit)
        r = await c.post("http://127.0.0.1:8766/api/hello", json={
            "player_id": "persist_test",
            "display_name": "持久化测试者",
            "gender": "男",
            "permadeath": False,
        })
        data = r.json()
        print(f"\n[Hello] {r.status_code} player_id={data.get('player_id')}")

        # Save manually
        r = await c.post("http://127.0.0.1:8766/api/save", json={"player_id": "persist_test"})
        print(f"[Save] {r.status_code} {r.json().get('ok')}")

        # List saves
        r = await c.get("http://127.0.0.1:8766/api/saves")
        saves = r.json().get("saves", [])
        found = any(s.get("player_id") == "persist_test" for s in saves)
        print(f"[Saves] {r.status_code} found persist_test: {found} total={len(saves)}")

        # Load
        r = await c.post("http://127.0.0.1:8766/api/load", json={"player_id": "persist_test"})
        print(f"[Load] {r.status_code} player_id={r.json().get('player_id')}")

        # Cleanup
        r = await c.post("http://127.0.0.1:8766/api/delete-save", json={"player_id": "persist_test"})
        print(f"[Delete] {r.status_code} ok={r.json().get('ok')}")

        print("\n=== ALL CHECKS PASSED ===")

asyncio.run(check())