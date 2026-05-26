# 活纸 · 江湖行纪 — Godot 桌面版

AI 驱动的江湖文字冒险游戏客户端，使用 Godot 4.3 引擎构建。

**后端 API**: 复用 `living-paper` 的 FastAPI 后端（端口 8766）。

## 项目结构

```
godot/
├── project.godot          # Godot 项目配置
├── scenes/
│   └── game.tscn          # 主场景（全单场景架构）
├── scripts/
│   ├── main_game.gd       # 主场景脚本（18.6KB）— 程序化构建全部 UI
│   │                      #   · 登录界面（新建/载入/性别/永久死亡）
│   │                      #   · 地图渲染（ColorRect 14px 色块网格）
│   │                      #   · 对话系统（RichTextLabel BBcode + LineEdit 输入）
│   │                      #   · HUD 面板（体力/心气/制钱/时辰/天气/位置/行囊/好感）
│   ├── api_client.gd      # HTTP 客户端（Autoload 单例）
│   └── game_manager.gd    # 游戏状态管理器（Autoload 单例）
└── .godot/                # Godot 编辑器缓存（自动生成，不入库）
```

## Autoload 单例

| 名称 | 文件 | 功能 |
|------|------|------|
| `ApiClient` | `scripts/api_client.gd` | HTTP 请求封装（GET/POST + SSE 流式） |
| `GameManager` | `scripts/game_manager.gd` | 游戏状态 + 信号发射 + 全 API 封装 |

## 运行

```bash
# 1. 启动后端（在仓库根目录）
cd ..
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8766

# 2. 打开 Godot 编辑器，导入本项目
#    → 导入 → 选择 godot/project.godot → 导入并编辑 → F6 运行

# 3. 或者命令行运行
godot --path godot --editor  # 编辑器
godot --path godot           # 直接运行游戏
```

## 功能特性

- **地图渲染**：ASCII 网格 → ColorRect 色块瓦片（14px 网格）
  - 🟫 墙  · ⬜ 地面  · 🟦 水道  · 🟩 林地  · 🟨 客栈  · 🟪 城关
- **点击移动**：左键点击地图格 → 寻路移动
- **流式对话**：输入文字 → SSE 流式 NPC 回复（打字机效果）
- **状态面板**：体力条、心气条、制钱、物品、好感度
- **存档管理**：💾 一键存档 / 📂 载入旧档
- **暗黑主题**：江湖夜行风配色

## 配置

后端 URL 默认 `http://127.0.0.1:8766`。

修改方式：
1. 在 Godot 编辑器中打开 `ApiClient` → 修改 `base_url`
2. 同样修改 `GameManager` 的 `backend_url`

## 依赖

- Godot 4.3+
- Python 后端 (`living-paper/backend/`) 需运行在 `127.0.0.1:8766`