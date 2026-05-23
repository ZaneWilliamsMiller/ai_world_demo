# 前端布局优化 | 2026-05-23 01:56

## 改动
- `static/index.html`：左侧栏 7 个分组移除 `open` 属性（默认折叠）；右侧栏新增 `sb-right-head` 包裹 + 折叠按钮 + `sb-right-body` 内容容器
- `static/game.css`：新增 `.sb-right-head` / `.sb-toggle` / `.sidebar.right.collapsed` / `.playfield.sb-right-collapsed` 样式，折叠态列宽 3rem，面板内容隐藏，toggle 按钮 180°旋转
- `static/main.js`：新增 `btnToggleRight` click 事件，toggle `collapsed` / `sb-right-collapsed` 类，切换按钮文本 ◀↔▶

## 验证
- `POST /api/hello` 正常返回完整游戏状态
- uvicorn 启动无报错
- push 成功到 `living-paper` 仓库（f81d908）

## 验证地址
http://127.0.0.1:8765 — 先填名号性别，点「踏入江湖」进主界面

## 后续注意事项
- 每次迭代开始前，`Stop-Process -Name python*` 杀旧 uvicorn
- 验证完毕告知用户打开 `http://127.0.0.1:8765`