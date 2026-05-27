import asyncio
import json

async def test_npc_talk():
    import httpx
    
    async with httpx.AsyncClient() as client:
        # 1. 先创建玩家
        r = await client.post("http://127.0.0.1:8765/api/hello", json={
            "player_id": "test_user_003",
            "display_name": "测试侠客",
            "gender": "男",
            "permadeath": False
        })
        print("Hello response:", r.status_code)
        data = r.json()
        print("Player created:", data.get("display_name"), "map:", data.get("map_id"))
        
        # 2. 获取状态，看看玩家位置和附近NPC
        r = await client.get(f"http://127.0.0.1:8765/api/state/test_user_003")
        print("\nState response:", r.status_code)
        state = r.json()
        print("Player pos:", state.get("px"), state.get("py"))
        print("Nearby NPCs:", list(state.get("npcs", {}).keys())[:10])
        
        # 3. 测试NPC对话 - 使用正确的 NPC ID
        r = await client.post("http://127.0.0.1:8765/api/npc/talk", json={
            "player_id": "test_user_003",
            "npc_id": "zhanggui",
            "message": "你好我想住店"
        })
        print("\nTalk response status:", r.status_code)
        data = r.json()
        print("visible_text:", data.get("visible_text", "N/A"))
        print("llm_fallback:", data.get("llm_fallback", False))
        
        if data.get("llm_fallback"):
            print("\n⚠️ LLM调用失败！使用了fallback回复")
        else:
            print("\n✅ LLM调用成功！")

asyncio.run(test_npc_talk())
