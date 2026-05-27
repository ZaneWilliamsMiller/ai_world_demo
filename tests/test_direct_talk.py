"""直接测试NPC对话逻辑，绕过HTTP层"""
import asyncio
import traceback
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_direct():
    print("=" * 60)
    print("直接测试NPC对话内部逻辑")
    print("=" * 60)
    
    try:
        from backend.session.store import room
        from backend.data.npcs_data import NPCS
        from backend.services.talk_service import build_npc_messages, apply_npc_reply, build_graceful_fallback
        from backend.llm_client import chat_completion, parse_npc_reply_json
        
        # 1. 获取或创建玩家
        p = room.get_or_create("direct_test_001", "测试侠客", "男", False)
        print(f"\n✅ 玩家: {p.display_name}")
        print(f"   位置: {p.map_id} ({p.px}, {p.py})")
        
        # 2. 检查NPC
        npc_id = "zhanggui"
        npc = NPCS.get(npc_id)
        if not npc:
            print(f"❌ NPC {npc_id} 不存在")
            return
        print(f"✅ NPC: {npc['name']}")
        
        # 3. 构建消息
        print("\n--- 构建 NPC 消息 ---")
        hist = p.history.setdefault(npc_id, [])
        hist_slice = list(hist[-14:])
        
        try:
            messages = build_npc_messages(p, npc_id, "你好我想住店", hist_slice)
            print(f"✅ 消息构建成功，共 {len(messages)} 条")
            
            # 打印消息概要（避免太长）
            for i, msg in enumerate(messages):
                role = msg.get("role", "?")
                content = str(msg.get("content", ""))[:100]
                print(f"  [{i}] {role}: {content}...")
                
        except Exception as e:
            print(f"❌ build_npc_messages 失败:")
            traceback.print_exc()
            return
        
        # 4. 调用LLM
        print("\n--- 调用 LLM ---")
        try:
            raw = await chat_completion(
                messages,
                temperature=0.85,
                max_tokens=800,
                response_format={"type": "json_object"},
            )
            print(f"✅ LLM 响应成功 ({len(raw)} 字符)")
            print(f"   内容预览: {raw[:200]}...")
            
        except Exception as e:
            print(f"❌ LLM 调用失败: {type(e).__name__}: {e}")
            traceback.print_exc()
            return
        
        # 5. 解析响应
        print("\n--- 解析 LLM 响应 ---")
        try:
            parsed = parse_npc_reply_json(raw)
            print(f"✅ 解析成功")
            print(f"   visible_text: {(parsed.visible_text or '')[:150]}")
            
        except Exception as e:
            print(f"❌ parse_npc_reply_json 失败: {e}")
            traceback.print_exc()
            return
        
        # 6. 应用回复
        print("\n--- 应用 NPC 回复 ---")
        try:
            async with p.lock:
                out, needs_reflect = apply_npc_reply(p, npc_id, "你好我想住店", parsed)
            print(f"✅ apply_npc_reply 成功")
            print(f"   visible_text: {(out.get('visible_text') or '')[:150]}")
            print(f"   needs_reflect: {needs_reflect}")
            
        except Exception as e:
            print(f"❌ apply_npc_reply 失败:")
            traceback.print_exc()
            return
        
        print("\n" + "=" * 60)
        print("✅ 全部流程成功！NPC对话正常工作")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 总体异常: {type(e).__name__}: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_direct())
