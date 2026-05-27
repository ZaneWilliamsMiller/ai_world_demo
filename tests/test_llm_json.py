import asyncio
from backend.llm_client import chat_completion

async def test():
    messages = [
        {"role": "system", "content": "你是一个客栈掌柜。回复必须使用JSON格式：{\"visible_text\": \"你的回复\"}"},
        {"role": "user", "content": "你好我想住店"}
    ]
    try:
        r = await chat_completion(
            messages,
            temperature=0.85,
            max_tokens=200,
            response_format={"type": "json_object"},
        )
        print("SUCCESS! Raw response:")
        print(repr(r[:500]))
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")

asyncio.run(test())
