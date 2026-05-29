"""诊断NPC对话fallback问题的完整脚本"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


async def diagnose():
    import httpx

    timeout = httpx.Timeout(connect=30.0, read=300.0, write=30.0, pool=30.0)
    base = os.environ.get("BACKEND_URL", "http://127.0.0.1:8765")

    async with httpx.AsyncClient(timeout=timeout) as client:
        print("=" * 60)
        print("第1步：检查后端是否运行")
        print("=" * 60)
        try:
            r = await client.get(f"{base}/docs", follow_redirects=True)
            print(f"✅ 后端状态: {r.status_code}")
        except Exception as e:
            print(f"❌ 后端未运行或无法连接: {e}")
            return

        print("\n" + "=" * 60)
        print("第2步：创建/获取玩家")
        print("=" * 60)
        r = await client.post(f"{base}/api/hello", json={
            "player_id": "diag_user_001",
            "display_name": "诊断侠客",
            "gender": "男",
            "permadeath": False
        })
        print(f"Hello API: {r.status_code}")
        data = r.json()
        player = data.get("player", {})
        print(f"  玩家: {player.get('display_name')}")
        print(f"  位置: map={player.get('map_id')}, ({player.get('px')}, {player.get('py')})")
        print(f"  附近NPC: {data.get('npcs_here', [])[:5]}")

        print("\n" + "=" * 60)
        print("第3步：直接测试LLM API调用（简单消息）")
        print("=" * 60)
        try:
            from backend.config import settings
            print(f"  LLM URL: {settings.llm_base_url}")
            print(f"  LLM Model: {settings.llm_model}")

            API_KEY = os.environ.get("LLM_API_KEY", "")
            if not API_KEY:
                print("  ⚠️ 未设置环境变量 LLM_API_KEY，跳过直连测试")
            else:
                t0 = time.time()
                r = await client.post(
                    f"{settings.llm_base_url.rstrip('/')}/chat/completions",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {API_KEY}",
                    },
                    json={
                        "model": settings.llm_model,
                        "messages": [{"role": "user", "content": "说一个字：好"}],
                        "temperature": 0.7,
                        "max_tokens": 10,
                    }
                )
                elapsed = time.time() - t0
                print(f"  响应状态: {r.status_code}")
                print(f"  耗时: {elapsed:.2f}秒")

                if r.status_code == 200:
                    data = r.json()
                    content = data["choices"][0]["message"]["content"]
                    print(f"  ✅ LLM响应: {content[:100]}")
                else:
                    print(f"  ❌ LLM错误: {r.text[:300]}")
        except Exception as e:
            print(f"  ❌ LLM调用异常: {type(e).__name__}: {e}")

        print("\n" + "=" * 60)
        print("第4步：直接测试LLM API调用（JSON格式）")
        print("=" * 60)
        try:
            API_KEY = os.environ.get("LLM_API_KEY", "")
            if not API_KEY:
                print("  ⚠️ 未设置环境变量 LLM_API_KEY，跳过JSON格式测试")
            else:
                t0 = time.time()
                r = await client.post(
                    f"{settings.llm_base_url.rstrip('/')}/chat/completions",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {API_KEY}",
                    },
                    json={
                        "model": settings.llm_model,
                        "messages": [
                            {"role": "system", "content": "你是一个客栈掌柜。回复必须是JSON格式。"},
                            {"role": "user", "content": "我想住店"}
                        ],
                        "temperature": 0.85,
                        "max_tokens": 200,
                        "response_format": {"type": "json_object"},
                    }
                )
                elapsed = time.time() - t0
                print(f"  响应状态: {r.status_code}")
                print(f"  耗时: {elapsed:.2f}秒")

                if r.status_code == 200:
                    data = r.json()
                    content = data["choices"][0]["message"]["content"]
                    print(f"  ✅ LLM JSON响应:\n{content[:300]}")

                    try:
                        parsed = json.loads(content)
                        print(f"  ✅ JSON解析成功: keys={list(parsed.keys())[:5]}")
                    except Exception as e:
                        print(f"  ❌ JSON解析失败: {e}")
                else:
                    print(f"  ❌ LLM错误: {r.text[:300]}")
        except Exception as e:
            print(f"  ❌ LLM调用异常: {type(e).__name__}: {e}")

        print("\n" + "=" * 60)
        print("第5步：通过后端API测试NPC对话（非流式）")
        print("=" * 60)
        try:
            t0 = time.time()
            r = await client.post(f"{base}/api/npc/talk", json={
                "player_id": "diag_user_001",
                "npc_id": "zhanggui",
                "message": "你好我想住店"
            })
            elapsed = time.time() - t0
            print(f"  Talk API: {r.status_code}")
            print(f"  耗时: {elapsed:.2f}秒")

            if r.status_code == 200:
                data = r.json()
                print(f"  visible_text: {(data.get('visible_text') or 'N/A')[:150]}")
                print(f"  llm_fallback: {data.get('llm_fallback', False)}")

                if data.get("llm_fallback"):
                    print("\n  ⚠️ 使用了fallback回复！说明LLM调用失败")
                else:
                    print("\n  ✅ LLM调用成功！")
            elif r.status_code == 400:
                print(f"  ❌ 请求错误: {r.text[:200]}")
            else:
                print(f"  ❌ 错误: {r.text[:200]}")
        except Exception as e:
            print(f"  ❌ Talk API异常: {type(e).__name__}: {e}")

        print("\n" + "=" * 60)
        print("第6步：查看后端日志中的错误信息")
        print("=" * 60)
        print("  请检查后端终端输出中是否有以下关键字：")
        print("  - 'LLM fallback' 或 'graceful fallback'")
        print("  - 'LLM API Error'")
        print("  - 'LLM Request Timeout'")
        print("  - 'circuit breaker'")
        print("  - 'Failed to parse NPC reply'")

        print("\n" + "=" * 60)
        print("诊断完成！")
        print("=" * 60)

if __name__ == "__main__":
    asyncio.run(diagnose())
