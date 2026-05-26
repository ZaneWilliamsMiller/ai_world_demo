#!/usr/bin/env bash
# Living Paper 启动脚本
# 用法: ./start.sh [backend|web|godot|test|all]

set -e

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="C:/Users/AAWZV/.workbuddy/binaries/python/envs/living-paper/Scripts/python.exe"
PORT=8765

case "${1:-all}" in
  backend)
    echo "[启动] 后端服务 (port=$PORT)..."
    cd "$REPO_DIR"
    $PYTHON -m uvicorn backend.app:app --host 127.0.0.1 --port $PORT
    ;;

  web)
    echo "[启动] Web 前端 (独立模式)..."
    cd "$REPO_DIR/web-standalone"
    # 使用 Python 简易服务器
    $PYTHON -m http.server 8080
    ;;

  test)
    echo "[运行] 自动化测试..."
    cd "$REPO_DIR"
    $PYTHON tools/auto_test.py
    ;;

  all)
    echo "[启动] 完整环境..."
    echo "  后端: http://127.0.0.1:$PORT"
    echo "  Web:  http://127.0.0.1:8080"
    echo ""
    cd "$REPO_DIR"
    $PYTHON -m uvicorn backend.app:app --host 127.0.0.1 --port $PORT &
    BACKEND_PID=$!
    sleep 3
    echo "[后端已启动] PID=$BACKEND_PID"
    echo "按 Ctrl+C 停止所有服务..."
    wait $BACKEND_PID
    ;;

  *)
    echo "用法: $0 [backend|web|test|all]"
    echo ""
    echo "  backend  - 启动后端 API 服务器"
    echo "  web      - 启动独立 Web 前端"
    echo "  test     - 运行自动化测试"
    echo "  all      - 启动所有服务"
    exit 1
    ;;
esac
