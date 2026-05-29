import json
import os

import httpx


def main():
    base = os.environ.get("BACKEND_URL", "http://127.0.0.1:8765")

    body = {
        "player_id": "test123",
        "display_name": "测试侠客",
        "gender": "男",
        "permadeath": False,
    }
    r = httpx.post(f"{base}/api/hello", json=body, timeout=10)
    print("=== /api/hello ===")
    data = r.json()
    print("maps keys:", list(data.get("maps", {}).keys()))
    p = data.get("player", {})
    print(f"player map_id={p.get('map_id')}, px={p.get('px')}, py={p.get('py')}")
    print(f"ambush_markers count={len(data.get('ambush_markers', []))}")
    print(f"maps.world name={data['maps'].get('world', {}).get('name', 'N/A')}")

    move_body = {
        "player_id": data["player_id"],
        "to_x": p.get("px", 0) + 1,
        "to_y": p.get("py", 0),
    }
    r2 = httpx.post(f"{base}/api/move", json=move_body, timeout=30)
    print("\n=== /api/move ===")
    data2 = r2.json()
    print("injuries:", data2.get("injuries", []))
    print("player:", json.dumps(data2.get("player", {}), ensure_ascii=False))
    print("forced_encounter:", data2.get("forced_encounter"))


if __name__ == "__main__":
    main()
