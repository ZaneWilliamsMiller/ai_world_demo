"""Debug: trace exactly why first LLM call fails."""
import httpx, asyncio, json, sys

BASE = "http://127.0.0.1:8766"

async def test():
    async with httpx.AsyncClient(timeout=60.0) as c:
        # Hello first
        r = await c.post(f"{BASE}/api/hello", json={
            "player_id": "debug_llm", "display_name": "调试者",
            "gender": "男", "permadeath": False,
        })
        assert r.status_code == 200, f"Hello failed: {r.text}"
        npc_id = r.json()["npcs_here"][0]["id"]
        sys.stdout.write(f"NPC: {npc_id}\n")
        
        # DIRECT LLM call — bypass living-paper
        sys.stdout.write("=== Direct LLM call ===\n")
        try:
            async with httpx.AsyncClient(timeout=30.0) as dc:
                r = await dc.post(
                    "https://llmapi.paratera.com/v1/chat/completions",
                    headers={
                        "Authorization": "Bearer sk-o5exptybwJAro8OfIqqmjQ",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "DeepSeek-V4-Pro",
                        "messages": [
                            {"role": "system", "content": "你是一个简洁的助手。"},
                            {"role": "user", "content": "用一句话介绍自己。"},
                        ],
                        "temperature": 0.85,
                        "max_tokens": 200,
                        "response_format": {"type": "json_object"},
                    },
                )
            sys.stdout.write(f"Direct LLM: {r.status_code}\n")
            body = r.json()
            content = body["choices"][0]["message"]["content"][:150]
            sys.stdout.write(f"Content: {content}\n")
        except Exception as e:
            sys.stdout.write(f"Direct LLM FAILED: {type(e).__name__}: {e}\n")
        
        # Now try via living-paper
        sys.stdout.write("\n=== Via living-paper talk ===\n")
        r = await c.post(f"{BASE}/api/npc/talk", json={
            "player_id": "debug_llm", "npc_id": npc_id,
            "message": "你好，自我介绍一下。",
        })
        data = r.json()
        sys.stdout.write(f"Status: {r.status_code}\n")
        sys.stdout.write(f"llm_fallback: {data.get('llm_fallback')}\n")
        sys.stdout.write(f"visible_text: {(data.get('visible_text',''))[:100]}\n")
        sys.stdout.write(f"reply: {(data.get('reply',''))[:100]}\n")

if __name__ == "__main__":
    asyncio.run(test())