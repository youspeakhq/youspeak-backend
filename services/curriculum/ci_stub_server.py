"""Minimal HTTP stub for CI: GET /health -> 200 so API can become healthy; other methods -> 404."""
import http.server
import socketserver


def _send(self, code: int):
    self.send_response(code)
    self.end_headers()


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        code = 200 if self.path.rstrip("/") == "/health" else 404
        _send(self, code)

    def do_POST(self):
        _send(self, 404)

    def do_PATCH(self):
        _send(self, 404)

    def do_DELETE(self):
        _send(self, 404)

    def log_message(self, *args):
        pass

socketserver.TCPServer(("", 8001), Handler).serve_forever()
