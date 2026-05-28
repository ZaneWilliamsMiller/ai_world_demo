"""API 冒烟验证 — 测试健康检查、存档/读档、删除"""
import httpx, asyncio, sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

BASE = "http://127.0.0.1:8765"

async def check():
    async with httpx.AsyncClient(timeout=10) as c:
        # 1. Health
        r = await c.get(f"{BASE}/api/health")
        print(f"[Health] {r.status_code} {r.json()}")

        # 2. Hello
        r = await c.post(f"{BASE}/api/hello", json={
            "player_id": "persist_test",
            "display_name": "持久化测试者",
            "gender": "男",
            "permadeath": False,
        })
        data = r.json()
        print(f"\n[Hello] {r.status_code} player_id={data.get('player_id')}")

        # 3. Save
        r = await c.post(f"{BASE}/api/save", json={"player_id": "persist_test"})
        print(f"[Save] {r.status_code} {r.json().get('ok')}")

        # 4. List saves
        r = await c.get(f"{BASE}/api/saves")
        saves = r.json().get("saves", [])
        found = any(s.get("player_id") == "persist_test" for s in saves)
        print(f"[Saves] {r.status_code} found persist_test: {found} total={len(saves)}")

        # 5. Load
        r = await c.post(f"{BASE}/api/load", json={"player_id": "persist_test"})
        print(f"[Load] {r.status_code} player_id={r.json().get('player_id')}")

        # 6. Cleanup
        r = await c.post(f"{BASE}/api/delete-save", json={"player_id": "persist_test"})
        print(f"[Delete] {r.status_code} ok={r.json().get('ok')}")

        print("\n=== ALL CHECKS PASSED ===")

asyncio.run(check())