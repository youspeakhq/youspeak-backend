"""Minimal HTTP stub for CI: GET /health -> 200 so API can become healthy."""
import http.server
import socketserver

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        code = 200 if self.path.rstrip("/") == "/health" else 404
        self.send_response(code)
        self.end_headers()
    def log_message(self, *args):
        pass

socketserver.TCPServer(("", 8001), Handler).serve_forever()
