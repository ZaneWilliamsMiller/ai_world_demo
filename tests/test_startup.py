#!/usr/bin/env python3
"""测试后端能否正常启动"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

print("测试后端启动...")

try:
    from backend.app import app
    print("✅ FastAPI 应用创建成功!")
    
    from backend.api.routes import router
    print("✅ 主路由加载成功!")
    
    from backend.api.player_routes import router as player_router
    from backend.api.npc_routes import router as npc_router
    from backend.api.save_routes import router as save_router
    print("✅ 所有子路由加载成功!")
    
    # 检查路由数量
    all_routes = []
    for route in app.routes:
        if hasattr(route, 'path'):
            all_routes.append(route.path)
    print(f"✅ 共 {len(all_routes)} 个路由端点")
    
    print("\n🎉 后端启动测试通过!")
    print("\n启动命令:")
    print("  python -m uvicorn backend.app:app --host 127.0.0.1 --port 8765")
    
except Exception as e:
    print(f"❌ 启动失败: {type(e).__name__}")
    print(f"   {str(e)}")
    import traceback
    print(f"\n堆栈:\n{traceback.format_exc()}")
    sys.exit(1)
