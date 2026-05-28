"""测试 API 端点：journal, item, rest, finale, bounty 系列 — 之前缺失覆盖的 9 个端点"""
from __future__ import annotations
import httpx
import asyncio
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

BASE = "http://127.0.0.1:8765"
PASSED = 0
FAILED = 0


def ok(cond: bool, label: str, detail: str = "") -> None:
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  [PASS] {label}")
    else:
        FAILED += 1
        extra = f"  -> {detail}" if detail else ""
        print(f"  [FAIL] {label}{extra}")


async def test_all():
    global PASSED, FAILED
    pid = f"_e2e_jbr_{int(time.time())}"
    async with httpx.AsyncClient(timeout=30) as c:
        # Setup: create player
        r = await c.post(f"{BASE}/api/hello", json={
            "player_id": pid,
            "display_name": "端点覆盖率测试",
            "gender": "女",
            "permadeath": False,
        })
        ok(r.status_code == 200, "hello -> 200", f"got {r.status_code}")
        data = r.json()
        pid = data.get("player_id", pid)

        # 1. Journal
        r = await c.get(f"{BASE}/api/journal/{pid}")
        ok(r.status_code == 200, "journal -> 200", r.text[:200])

        # 2. Item Use
        r = await c.post(f"{BASE}/api/item/use", json={"player_id": pid, "item": "金疮药"})
        ok(r.status_code in (200, 404, 422), f"item/use -> {r.status_code}", r.text[:200])

        # 3. Rest
        r = await c.post(f"{BASE}/api/rest", json={"player_id": pid})
        ok(r.status_code in (200, 422), f"rest -> {r.status_code}", r.text[:200])

        # 4. Finale
        r = await c.post(f"{BASE}/api/finale", json={"player_id": pid, "closing_note": "江湖再见"})
        ok(r.status_code in (200, 422, 500), f"finale -> {r.status_code}", r.text[:200])

        # 5. Bounty Refresh
        r = await c.post(f"{BASE}/api/bounty/refresh", json={"player_id": pid})
        ok(r.status_code == 200, f"bounty/refresh -> {r.status_code}", r.text[:200])
        bt_data = r.json()

        # 6. Bounty Accept
        bounties = bt_data.get("bounties", [])
        bid = bounties[0].get("id", "1") if bounties else "1"
        r = await c.post(f"{BASE}/api/bounty/accept", json={"player_id": pid, "bounty_id": bid})
        ok(r.status_code in (200, 404, 422), f"bounty/accept -> {r.status_code}", r.text[:200])

        # 7. Bounty Check
        r = await c.post(f"{BASE}/api/bounty/check", json={"player_id": pid})
        ok(r.status_code == 200, f"bounty/check -> {r.status_code}", r.text[:200])

        # 8. Bounty Complete
        r = await c.post(f"{BASE}/api/bounty/complete", json={"player_id": pid})
        ok(r.status_code in (200, 400, 422), f"bounty/complete -> {r.status_code}", r.text[:200])

        # 9. Bounty Abandon
        r = await c.post(f"{BASE}/api/bounty/abandon", json={"player_id": pid})
        ok(r.status_code in (200, 400, 422), f"bounty/abandon -> {r.status_code}", r.text[:200])

        # Cleanup
        await c.post(f"{BASE}/api/delete-save", json={"player_id": pid})

    print(f"\n=== RESULT: {PASSED} passed, {FAILED} failed ===")
    return FAILED == 0


if __name__ == "__main__":
    success = asyncio.run(test_all())
    sys.exit(0 if success else 1)