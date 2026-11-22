"""Gateway / load balancer di depan beberapa backend.

Dua mode:
  naive      -> round-robin buta, tanpa retry. Kalau backend mati, request gagal.
  resilient  -> health check berkala + retry ke instance lain + timeout pendek.

python gateway.py <port> <mode> <backend_port1,backend_port2,...>
"""
import itertools
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1])
MODE = sys.argv[2]
BACKENDS = [int(p) for p in sys.argv[3].split(",")]

TIMEOUT = 0.5
MAX_ATTEMPTS = 3
HEALTH_INTERVAL = 0.5

healthy = set(BACKENDS)
lock = threading.Lock()
rr = itertools.cycle(BACKENDS)


def call(port, path):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=TIMEOUT) as r:
        return r.status, r.read()


def health_loop():
    while True:
        for p in BACKENDS:
            try:
                ok = call(p, "/health")[0] == 200
            except Exception:
                ok = False
            with lock:
                (healthy.add if ok else healthy.discard)(p)
        time.sleep(HEALTH_INTERVAL)


def pick():
    """Ambil instance berikutnya; mode resilient melewati yang tidak sehat."""
    for _ in range(len(BACKENDS)):
        p = next(rr)
        if MODE == "naive":
            return p
        with lock:
            if p in healthy:
                return p
    return next(rr)  # semua dianggap mati: tetap coba satu


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        attempts = 1 if MODE == "naive" else MAX_ATTEMPTS
        tried = []
        for _ in range(attempts):
            port = pick()
            tried.append(port)
            try:
                status, body = call(port, self.path)
                return self._send(status, body)
            except Exception:
                with lock:
                    healthy.discard(port)  # tandai mati segera, jangan tunggu health check
        self._send(502, json.dumps({"error": "all attempts failed", "tried": tried}).encode())

    def _send(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    if MODE == "resilient":
        threading.Thread(target=health_loop, daemon=True).start()
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
