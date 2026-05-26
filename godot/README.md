# 活纸 · 江湖行纪 — Godot 桌面版

AI 驱动的江湖文字冒险游戏客户端，使用 Godot 4.3 引擎构建。

**后端 API**: 复用 `living-paper` 的 FastAPI 后端（端口 8766）。

## 项目结构

```
living-paper-godot/
├── project.godot          # Godot 项目配置
├── scenes/
│   └── game.tscn          # 主场景（全单场景架构）
├── scripts/
│   ├── main_game.gd       # 主场景脚本 — 构建全部 UI
│   ├── api_client.gd      # HTTP 客户端（Autoload）
│   ├── game_manager.gd    # 游戏状态管理器（Autoload）
│   ├── map_view.gd        # ASCII 地图 → 色块瓦片渲染
│   ├── dialogue_system.gd # NPC 对话 UI
│   └── hud.gd             # 玩家状态面板
└── assets/fonts/          # （字体可选）
```

## Autoload 单例

| 名称 | 文件 | 功能 |
|------|------|------|
| `ApiClient` | `scripts/api_client.gd` | HTTP 请求封装 |
| `GameManager` | `scripts/game_manager.gd` | 游戏状态 + 信号发射 |

## 运行

```bash
# 1. 启动后端
cd ../living-paper
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8766

# 2. 打开 Godot 编辑器，导入本项目
#    → 导入 → 选择 project.godot → 导入并编辑 → F6 运行

# 3. 或者命令行运行
godot --path . --editor  # 编辑器
godot --path .           # 直接运行游戏
```

## 功能特性

- **地图渲染**：ASCII 网格 → ColorRect 色块瓦片（14px 网格）
  - 🟫 墙 · ⬜ 地面 · 🟦 水道 · 🟩 林地 · 🟨 客栈 · 🟪 城关
- **点击移动**：左键点击地图格 → 寻路移动
- **流式对话**：输入文字 → SSE 流式 NPC 回复（打字机效果）
- **状态面板**：体力条、心气条、制钱、物品、好感度
- **存档管理**：💾 一键存档 / 📂 载入旧档
- **地图切换**：走到界门格自动切换场景
- **暗黑主题**：江湖夜行风配色

## 配置

后端 URL 默认 `http://127.0.0.1:8766`。

修改方式：
1. 在 Godot 编辑器中打开 `ApiClient` → 修改 `base_url`
2. 同样修改 `GameManager` 的 `backend_url`

## 依赖

- Godot 4.3+
- Python 后端 (`living-paper/`) 需运行在 `127.0.0.1:8766`
