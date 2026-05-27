#!/usr/bin/env python3
"""全面的后端健康检查"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

print("="*60)
print("后端健康检查".center(60))
print("="*60)

all_good = True
total_tests = 0
passed_tests = 0

def test_section(name):
    print(f"\n{'='*60}")
    print(f"{name}".center(60))
    print(f"{'='*60}")

def check(name, test_func, critical=False):
    global total_tests, passed_tests, all_good
    total_tests += 1
    print(f"\n  ▶️  {name}...", end=" ")
    try:
        result = test_func()
        if result:
            print("✅ 通过")
            passed_tests += 1
        else:
            print("❌ 失败")
            if critical:
                all_good = False
    except Exception as e:
        print(f"❌ 异常: {type(e).__name__}")
        print(f"     {str(e)[:100]}")
        import traceback
        print(f"     堆栈: {traceback.format_exc()[:200]}")
        if critical:
            all_good = False

# 测试 1: 基础模块导入
test_section("1. 基础模块导入")

check("config 模块", lambda: __import__("backend.config"), critical=True)
check("app 模块", lambda: __import__("backend.app"), critical=True)
check("models.player", lambda: __import__("backend.models.player"), critical=True)
check("models.npc", lambda: __import__("backend.models.npc"), critical=True)
check("models.llm_schema", lambda: __import__("backend.models.llm_schema"), critical=True)

# 测试 2: 系统模块
test_section("2. 系统模块")

check("systems.core", lambda: __import__("backend.systems.core"), critical=True)
check("systems.time_weather", lambda: __import__("backend.systems.time_weather"), critical=True)
check("systems.pathfinding", lambda: __import__("backend.systems.pathfinding"), critical=True)
check("systems.perception", lambda: __import__("backend.systems.perception"), critical=True)
check("systems.trap", lambda: __import__("backend.systems.trap"), critical=True)
check("systems.npc_state", lambda: __import__("backend.systems.npc_state"), critical=True)
check("systems.economy", lambda: __import__("backend.systems.economy"), critical=True)
check("systems.reputation", lambda: __import__("backend.systems.reputation"), critical=True)
check("systems.encounter", lambda: __import__("backend.systems.encounter"), critical=True)
check("systems.bounty_board", lambda: __import__("backend.systems.bounty_board"), critical=True)
check("systems.save_system", lambda: __import__("backend.systems.save_system"), critical=True)

# 测试 3: 数据模块
test_section("3. 数据模块")

check("data.npcs_data", lambda: __import__("backend.data.npcs_data"), critical=True)
check("data.maps_data", lambda: __import__("backend.data.maps_data"), critical=True)
check("data.factions", lambda: __import__("backend.data.factions"), critical=True)
check("data.prompts", lambda: __import__("backend.data.prompts"), critical=True)
check("data.atmosphere", lambda: __import__("backend.data.atmosphere"), critical=True)
check("data.relationships", lambda: __import__("backend.data.relationships"), critical=True)

# 测试 4: 服务模块
test_section("4. 服务模块")

check("services.talk_service", lambda: __import__("backend.services.talk_service"), critical=True)
check("services.agent_service", lambda: __import__("backend.services.agent_service"), critical=True)

# 测试 5: API 路由
test_section("5. API 路由")

check("api.routes", lambda: __import__("backend.api.routes"), critical=True)
check("api.player_routes", lambda: __import__("backend.api.player_routes"), critical=True)
check("api.npc_routes", lambda: __import__("backend.api.npc_routes"), critical=True)
check("api.save_routes", lambda: __import__("backend.api.save_routes"), critical=True)

# 测试 6: 工具模块
test_section("6. 工具模块")

check("llm_client", lambda: __import__("backend.llm_client"), critical=True)
check("game_state", lambda: __import__("backend.game_state"), critical=True)
check("views", lambda: __import__("backend.views"), critical=True)
check("agent_brain", lambda: __import__("backend.agent_brain"), critical=True)
check("memory_index", lambda: __import__("backend.memory_index"), critical=True)
check("circuit_breaker", lambda: __import__("backend.circuit_breaker"), critical=True)
check("llm_cache", lambda: __import__("backend.llm_cache"), critical=True)
check("session.store", lambda: __import__("backend.session.store"), critical=True)

# 测试 7: 具体功能
test_section("7. 具体功能检查")

def check_config():
    from backend.config import settings
    assert settings.llm_base_url is not None
    assert settings.llm_api_key is not None
    assert settings.llm_model is not None
    return True

check("配置加载", check_config, critical=True)

def check_views():
    from backend.views import (
        player_public, npcs_here, npc_catalog,
        maps_public, map_locations_public, factions_public
    )
    assert callable(player_public)
    assert callable(npcs_here)
    assert callable(npc_catalog)
    return True

check("视图函数", check_views, critical=True)

def check_time_weather():
    from backend.systems.time_weather import (
        shichen_name, shichen_phase, is_night, advance_clock
    )
    assert shichen_phase(0) == "深夜"
    assert shichen_phase(4) == "上午"
    return True

check("时间天气系统", check_time_weather, critical=True)

def check_memory_api():
    from backend import memory as mem
    assert hasattr(mem, "Memory")
    assert hasattr(mem, "AgentMind")
    assert hasattr(mem, "make_memory")
    assert hasattr(mem, "retrieve")
    return True

check("Memory API", check_memory_api, critical=True)

# 测试 8: API 应用初始化
test_section("8. 应用初始化")

def check_app():
    from backend.app import app
    assert app is not None
    return True

check("FastAPI 应用", check_app, critical=True)

def check_routes():
    from backend.api.routes import router
    from backend.api.player_routes import router as player_router
    from backend.api.npc_routes import router as npc_router
    from backend.api.save_routes import router as save_router
    assert router is not None
    assert player_router is not None
    assert npc_router is not None
    assert save_router is not None
    return True

check("路由初始化", check_routes, critical=True)

# 总结
print("\n" + "="*60)
print("健康检查总结".center(60))
print(f"{'='*60}")
print(f"\n总测试: {total_tests}")
print(f"通过: {passed_tests}")
print(f"失败: {total_tests - passed_tests}")
print(f"\n{'✅ 后端健康!' if all_good else '❌ 发现问题!'}")

if all_good:
    print("\n所有关键模块正常，后端可以启动!")
    sys.exit(0)
else:
    print("\n请检查以上失败的测试!")
    sys.exit(1)
