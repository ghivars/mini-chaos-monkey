"""Backend service sederhana: satu instance = satu proses di satu port.

GET /health  -> 200 kalau hidup
GET /work    -> 200 + JSON berisi nama instance
"""
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1])
NAME = f"backend-{PORT}"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self._send(200, {"status": "ok", "instance": NAME})
        elif self.path == "/work":
            time.sleep(0.005)  # pura-pura kerja
            self._send(200, {"result": "done", "instance": NAME})
        else:
            self._send(404, {"error": "not found"})

    def _send(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass  # jangan spam terminal


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
