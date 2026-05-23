# Task Artifact: 存档系统改造 2026-05-23 16:45

## 需求来源
用户反馈：存档管理需要优化
1. 新建角色体力异常（"直接没体力了"）
2. 多角色共用同一存档，无法独立
3. 非真实江湖模式：重伤后应自动返回最近补给点
4. 真实江湖模式：死亡后直接损坏/删除该角色存档

## 改动概要

### 新增文件
| 文件 | 说明 |
|------|------|
| `backend/systems/save_system.py` | JSON 文件存档核心（序列化/反序列化/列表/删除/复活） |
| 新增 `saves/` 目录 | 每个角色一个 JSON 文件 |

### 修改文件
| 文件 | 改动 |
|------|------|
| `backend/session/store.py` | `get_or_create` 优先从存档加载；体力/心气保底值保护 |
| `backend/api/routes.py` | 新增 /api/save, /api/saves, /api/load, /api/delete-save；移动后自动存档；死亡时真实江湖删档/非真实江湖复活 |

## 核心逻辑

### 存档文件格式
- 路径：`saves/<player_id>.json`
- 覆盖所有 PlayerState 字段（lock 除外）
- `minds` (AgentMind) → dict → JSON；反序列化时重建
- `npc_positions` tuple → list → JSON；反序列化时还原 tuple

### 死亡处理（移动时）
```
if 真实江湖 + 死亡:
    save_game(p)      # 先存档（记录死亡时刻状态）
    delete_save(p)     # 删除存档，角色不可再玩

if 非真实江湖 + 体力归零:
    respawn_at_supply_point(p)  # 移到最近补给点，恢复50%体力
```

### 补给点优先级
1. 当前地图最近的 {T:客栈, Y:驿站, I:黑店, M:市集, B:兵站}
2. 均无 → county 客栈 (4,2)

### 新建角色体力保底
- `store.py`：存档加载时 vigor≤0 → 重置为 80
- 防止老存档/损坏存档导致开局无体力

## API 端点
- `GET /api/saves` — 列出所有存档角色
- `POST /api/save` — 手动保存（player_id）
- `POST /api/load` — 加载已有角色（覆盖内存）
- `POST /api/delete-save` — 删除存档（手动弃档）
- `/api/move` — 移动后自动存档；返回 `respawn_msg` 字段（若发生复活）

## 修复的 Bug
- 新角色 vigor=0 → 强制保底 80（`load_game` 反序列化时）
- 旧存档缺字段 → `defaults` 字典兜底

## 测试
- 28 个测试全部通过（端点×20 + 寻路×8）
- 手动验证：round-trip 保存/加载、体力0坏档修复、补给点复活