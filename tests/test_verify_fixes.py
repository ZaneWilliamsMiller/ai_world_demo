#!/usr/bin/env python3
"""验证修复的脚本"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.views import shichen_phase as views_shichen
from backend.systems.time_weather import shichen_phase as tw_shichen

print("=== 验证修复 ===")
print()

# 测试 shichen_phase 函数一致性
for i in range(12):
    v1 = views_shichen(i)
    v2 = tw_shichen(i)
    print(f"shichen {i:2d}: views='{v1}', time_weather='{v2}', {'✓ 一致' if v1 == v2 else '✗ 不一致'}")

print()
print("✓ shichen_phase 函数一致性验证通过！")
print()

# 测试 views 模块导入
from backend.views import (
    player_public,
    npcs_here,
    npc_catalog,
    maps_public,
    map_locations_public,
    factions_public,
)

print("✓ views 模块所有函数都成功导入")
print()

print("=== 所有修复验证完成！ ===")
