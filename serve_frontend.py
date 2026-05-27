#!/usr/bin/env python3
"""
简单的静态文件服务器，用于在 8766 端口提供前端服务
"""

from http.server import HTTPServer, SimpleHTTPRequestHandler
import os
import sys

PORT = 8766

# 切换到 static 目录
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.chdir(static_dir)

class CORSRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

def main():
    server_address = ("127.0.0.1", PORT)
    httpd = HTTPServer(server_address, CORSRequestHandler)
    print(f"🏮 活纸江湖 - 前端服务器")
    print(f"📍 服务目录: {static_dir}")
    print(f"🔗 访问地址: http://127.0.0.1:{PORT}")
    print(f"🚀 按 Ctrl+C 停止服务器\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 服务器已停止")
        sys.exit(0)

if __name__ == "__main__":
    main()
