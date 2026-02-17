#!/usr/bin/env python3
"""
Simple reverse proxy to make localhost:8000 and localhost:8001 accessible via network IP
Runs on all interfaces (0.0.0.0) and forwards to localhost
"""
import http.server
import socketserver
import urllib.request
import urllib.error
import sys

class ProxyHandler(http.server.SimpleHTTPRequestHandler):
    target_host = "127.0.0.1"
    target_port = None
    
    def do_GET(self):
        self.proxy_request()
    
    def do_POST(self):
        self.proxy_request()
    
    def do_PUT(self):
        self.proxy_request()
    
    def do_DELETE(self):
        self.proxy_request()
    
    def do_HEAD(self):
        self.proxy_request()
    
    def do_OPTIONS(self):
        self.proxy_request()
    
    def proxy_request(self):
        url = f"http://{self.target_host}:{self.target_port}{self.path}"
        if self.query_string:
            url += f"?{self.query_string}"
        
        try:
            req = urllib.request.Request(
                url,
                data=self.rfile.read(int(self.headers.get('content-length', 0))) if self.command != 'GET' else None,
                headers={k: v for k, v in self.headers.items() if k.lower() not in ['host', 'connection']}
            )
            req.get_method = lambda: self.command
            
            with urllib.request.urlopen(req) as response:
                self.send_response(response.status)
                for header, value in response.headers.items():
                    self.send_header(header, value)
                self.end_headers()
                self.wfile.write(response.read())
        except Exception as e:
            self.send_response(502)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(f'{{"error": "Gateway Error", "details": "{str(e)}"}}'.encode())


class DjangoProxyHandler(ProxyHandler):
    target_port = 8000


class FastAPIProxyHandler(ProxyHandler):
    target_port = 8001


if __name__ == '__main__':
    print("Starting reverse proxies...")
    print("Django API: http://0.0.0.0:9000 -> http://localhost:8000")
    print("FastAPI: http://0.0.0.0:9001 -> http://localhost:8001")
    print("\nAccess from network:")
    print("Django: http://10.10.13.27:9000/api/auth/register/")
    print("FastAPI: http://10.10.13.27:9001/api/chat/send/")
    
    django_server = socketserver.TCPServer(("0.0.0.0", 9000), DjangoProxyHandler)
    fastapi_server = socketserver.TCPServer(("0.0.0.0", 9001), FastAPIProxyHandler)
    
    print("\nServers running (Press Ctrl+C to stop)...")
    
    try:
        django_server.handle_request()
        fastapi_server.handle_request()
    except KeyboardInterrupt:
        print("\nShutting down...")
        django_server.server_close()
        fastapi_server.server_close()
