"""Quick endpoint test for cron iteration."""
import sys, io, json, urllib.request, urllib.error
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

BASE = "http://127.0.0.1:8766"

def post(path, data):
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(f"{BASE}{path}", body, {"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:500]
        return {"error": e.code, "body": body}

# --- /api/health ---
print("=== /api/health ===")
with urllib.request.urlopen(f"{BASE}/api/health") as resp:
    h = json.loads(resp.read())
print(f"  status={h['status']} model={h['model']} world={h['world']}")

# --- /api/hello ---
print("\n=== /api/hello ===")
r = post("/api/hello", {"player_id": "test_qclaw_iter", "gender": "男"})
print(f"  player_id={r.get('player_id')}  display_name={r.get('display_name')}  world={r.get('world_name')}")
npcs = r.get("npcs_here", [])
print(f"  npcs_here={npcs}")
maps = r.get("maps", {})
for mk, mv in maps.items():
    print(f"  map: {mk}={mv['name']} ({mv['rows']}x{mv.get('cols','?')})")

# --- /api/npc/talk (test if npcs available) ---
if npcs:
    npc_id = npcs[0]["id"]
    print(f"\n=== /api/npc/talk (npc={npc_id}) ===")
    r2 = post("/api/npc/talk", {
        "player_id": "test_qclaw_iter",
        "npc_id": npc_id,
        "message": "您好，初到贵地，敢问此地近日可有什么新鲜事？"
    })
    if "error" in r2:
        print(f"  ERROR {r2['error']}: {r2.get('body','')[:200]}")
    else:
        print(f"  reply={r2.get('reply','')[:200]}")
        print(f"  server_ms={r2.get('server_ms')}")
        print(f"  flags={r2.get('flags')}")
else:
    print("\n=== NO NPCS AVAILABLE ===")
    print("  Trying to talk to 'wang' anyway...")
    r2 = post("/api/npc/talk", {
        "player_id": "test_qclaw_iter",
        "npc_id": "wang",
        "message": "您好，初到贵地，敢问此地近日可有什么新鲜事？"
    })
    print(f"  result={json.dumps({k: str(v)[:200] for k,v in r2.items()}, ensure_ascii=False)}")

print("\n=== DONE ===")