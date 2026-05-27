#!/usr/bin/env python3
"""
简单的静态文件服务器，用于提供前端服务
支持通过命令行参数指定端口，默认 8766
"""

from http.server import HTTPServer, SimpleHTTPRequestHandler
import os
import sys

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
    # 支持通过命令行参数指定端口
    port = 8766
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print("⚠️  端口必须是数字，使用默认端口 8766")
            port = 8766
    
    server_address = ("127.0.0.1", port)
    httpd = HTTPServer(server_address, CORSRequestHandler)
    print(f"🏮 活纸江湖 - 前端服务器")
    print(f"📍 服务目录: {static_dir}")
    print(f"🔗 访问地址: http://127.0.0.1:{port}")
    print(f"🚀 按 Ctrl+C 停止服务器\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 服务器已停止")
        sys.exit(0)

if __name__ == "__main__":
    main()
