"""详细诊断NPC对话500错误"""
import asyncio
import json
import traceback

async def diagnose_500():
    import httpx
    
    timeout = httpx.Timeout(connect=30.0, read=300.0, write=30.0, pool=30.0)
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        print("测试NPC对话，捕获详细错误...")
        
        try:
            r = await client.post("http://127.0.0.1:8765/api/npc/talk", json={
                "player_id": "diag_user_001",
                "npc_id": "zhanggui",
                "message": "你好"
            })
            print(f"\n状态码: {r.status_code}")
            print(f"响应头: {dict(r.headers)}")
            print(f"响应体:\n{r.text}")
            
        except Exception as e:
            print(f"\n请求异常:")
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(diagnose_500())
