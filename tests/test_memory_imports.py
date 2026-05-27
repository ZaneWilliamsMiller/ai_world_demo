#!/usr/bin/env python3
"""测试 memory 模块的所有导入和引用是否正常"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

print("=== 测试 memory 模块导入 ===")

# 测试 1: 从 backend 导入 memory
print("\n1. 测试从 backend 导入 memory:")
try:
    from backend import memory as mem
    print("   ✓ 成功")
except Exception as e:
    print(f"   ✗ 失败: {e}")
    sys.exit(1)

# 测试 2: 验证基本数据结构
print("\n2. 测试基本数据结构:")
try:
    memory_obj = mem.Memory(
        id="test123",
        kind="observation",
        text="测试记忆",
        importance=5.0,
        created_day=1,
        created_shichen="辰时",
        created_at=0.0,
        last_accessed=0.0,
    )
    print(f"   ✓ Memory 类正常")
    
    agent_mind = mem.AgentMind()
    print(f"   ✓ AgentMind 类正常")
except Exception as e:
    print(f"   ✗ 失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 测试 3: 验证所有公共 API
print("\n3. 测试所有公共 API:")
api_list = [
    ("make_memory", mem.make_memory),
    ("estimate_importance_heuristic", mem.estimate_importance_heuristic),
    ("text_relevance", mem.text_relevance),
    ("retrieve", mem.retrieve),
    ("build_retrieval_query", mem.build_retrieval_query),
    ("condense_old_observations", mem.condense_old_observations),
    ("format_memories_for_prompt", mem.format_memories_for_prompt),
    ("format_plan_for_prompt", mem.format_plan_for_prompt),
    ("format_mood_for_prompt", mem.format_mood_for_prompt),
    ("format_plan_for_reflection", mem.format_plan_for_reflection),
    ("format_mood_for_reflection", mem.format_mood_for_reflection),
    ("affective_memory_importance", mem.affective_memory_importance),
]

all_good = True
for name, func in api_list:
    try:
        if func is not None:
            print(f"   ✓ {name} 正常")
        else:
            print(f"   ✗ {name} 为 None")
            all_good = False
    except Exception as e:
        print(f"   ✗ {name} 失败: {e}")
        all_good = False

# 测试 4: 验证 agent_brain 中的引用
print("\n4. 测试 agent_brain 模块:")
try:
    from backend import agent_brain
    print("   ✓ agent_brain 模块导入成功")
    
    # 测试 agent_brain 中的函数是否可用
    test_funcs = [
        "reflect",
        "cross_reflect", 
        "plan_day",
        "import_seeds",
        "record_observation"
    ]
    
    for func_name in test_funcs:
        if hasattr(agent_brain, func_name):
            print(f"   ✓ {func_name} 存在")
        else:
            print(f"   ✗ {func_name} 不存在")
            all_good = False
            
except Exception as e:
    print(f"   ✗ 失败: {e}")
    import traceback
    traceback.print_exc()
    all_good = False

# 测试 5: 测试实际创建记忆
print("\n5. 测试创建记忆:")
try:
    new_memory = mem.make_memory(
        kind="observation",
        text="这是一条测试记忆",
        importance=7.5,
        world_day=1,
        world_shichen="辰时"
    )
    print(f"   ✓ 成功创建记忆: {new_memory.text[:30]}...")
except Exception as e:
    print(f"   ✗ 失败: {e}")
    import traceback
    traceback.print_exc()
    all_good = False

print("\n" + "="*40)
if all_good:
    print("✓ 所有 memory 相关引用测试通过!")
    sys.exit(0)
else:
    print("✗ 存在问题")
    sys.exit(1)
