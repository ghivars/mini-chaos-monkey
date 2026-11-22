"""Load generator: kirim request terus-menerus ke gateway dan catat hasilnya."""
import statistics
import threading
import time
import urllib.request


def run_load(url, duration, workers=8):
    results = []  # (ok: bool, latency_ms: float)
    lock = threading.Lock()
    end = time.time() + duration

    def worker():
        while time.time() < end:
            t0 = time.perf_counter()
            try:
                with urllib.request.urlopen(url, timeout=3) as r:
                    ok = r.status == 200
            except Exception:
                ok = False
            ms = (time.perf_counter() - t0) * 1000
            with lock:
                results.append((ok, ms))

    threads = [threading.Thread(target=worker) for _ in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return summarize(results)


def summarize(results):
    total = len(results)
    ok = sum(1 for r in results if r[0])
    lat = sorted(r[1] for r in results) or [0]
    p99 = lat[min(len(lat) - 1, int(len(lat) * 0.99))]
    return {
        "total": total,
        "success": ok,
        "failed": total - ok,
        "success_rate": 100 * ok / total if total else 0,
        "p50_ms": statistics.median(lat),
        "p99_ms": p99,
    }
