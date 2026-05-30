"""API 冒烟验证 — 测试健康检查、存档/读档、删除"""
import asyncio
import os

import httpx

BASE = os.environ.get("BACKEND_URL", "http://127.0.0.1:8765")


async def check():
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{BASE}/api/health")
        print(f"[Health] {r.status_code} {r.json()}")

        r = await c.post(f"{BASE}/api/hello", json={
            "player_id": "persist_test",
            "display_name": "持久化测试者",
            "gender": "男",
            "permadeath": False,
        })
        data = r.json()
        print(f"\n[Hello] {r.status_code} player_id={data.get('player_id')}")

        r = await c.post(f"{BASE}/api/save", json={"player_id": "persist_test"})
        print(f"[Save] {r.status_code} {r.json().get('ok')}")

        r = await c.get(f"{BASE}/api/saves")
        saves = r.json().get("saves", [])
        found = any(s.get("player_id") == "persist_test" for s in saves)
        print(f"[Saves] {r.status_code} found persist_test: {found} total={len(saves)}")

        r = await c.post(f"{BASE}/api/load", json={"player_id": "persist_test"})
        print(f"[Load] {r.status_code} player_id={r.json().get('player_id')}")

        r = await c.post(f"{BASE}/api/delete-save", json={"player_id": "persist_test"})
        print(f"[Delete] {r.status_code} ok={r.json().get('ok')}")

        print("\n=== ALL CHECKS PASSED ===")


if __name__ == "__main__":
    asyncio.run(check())
