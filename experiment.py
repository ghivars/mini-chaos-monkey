"""Jalankan eksperimen chaos: bandingkan gateway naive vs resilient
saat backend dibunuh secara acak.

python experiment.py [--duration 15] [--seed 42]
"""
import argparse
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from chaos_monkey import ChaosMonkey, Fleet
from loadtest import run_load

HERE = Path(__file__).parent
BACKEND_PORTS = [8101, 8102, 8103]
GATEWAY_PORT = 8100


def wait_up(port, path="/health", timeout=5):
    end = time.time() + timeout
    while time.time() < end:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=0.5)
            return
        except Exception:
            time.sleep(0.1)
    raise RuntimeError(f"port {port} tidak hidup")


def trial(mode, duration, seed, chaos=True):
    fleet = Fleet(BACKEND_PORTS)
    for p in BACKEND_PORTS:
        wait_up(p)
    gw = subprocess.Popen([sys.executable, str(HERE / "gateway.py"), str(GATEWAY_PORT), mode,
                           ",".join(map(str, BACKEND_PORTS))])
    monkey = None
    try:
        wait_up(GATEWAY_PORT, "/work")
        if chaos:
            monkey = ChaosMonkey(fleet, seed=seed)
            monkey.start()
        stats = run_load(f"http://127.0.0.1:{GATEWAY_PORT}/work", duration)
        stats["kills"] = monkey.kills if monkey else 0
        return stats
    finally:
        if monkey:
            monkey.stop()
        gw.kill()
        gw.wait()
        fleet.stop_all()
        time.sleep(0.5)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=float, default=15)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()

    runs = [("baseline (tanpa chaos)", "naive", False),
            ("naive + chaos", "naive", True),
            ("resilient + chaos", "resilient", True)]
    rows = []
    for label, mode, chaos in runs:
        print(f"\n== {label} ==")
        s = trial(mode, a.duration, a.seed, chaos)
        rows.append((label, s))

    print("\n| Skenario | Request | Gagal | Sukses | p50 (ms) | p99 (ms) | Kill |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for label, s in rows:
        print(f"| {label} | {s['total']} | {s['failed']} | {s['success_rate']:.2f}% "
              f"| {s['p50_ms']:.1f} | {s['p99_ms']:.1f} | {s['kills']} |")


if __name__ == "__main__":
    main()
