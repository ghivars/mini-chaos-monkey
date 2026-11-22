"""Mini Chaos Monkey: secara acak membunuh satu backend, lalu (opsional) supervisor
menghidupkannya lagi setelah beberapa detik, seperti auto-restart di Kubernetes.
"""
import random
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).parent


class Fleet:
    """Mengelola proses-proses backend."""

    def __init__(self, ports):
        self.procs = {p: self._start(p) for p in ports}
        self.lock = threading.Lock()

    def _start(self, port):
        return subprocess.Popen([sys.executable, str(HERE / "backend.py"), str(port)])

    def alive(self):
        with self.lock:
            return [p for p, pr in self.procs.items() if pr.poll() is None]

    def kill(self, port):
        with self.lock:
            self.procs[port].kill()
            self.procs[port].wait()

    def restart(self, port):
        with self.lock:
            if self.procs[port].poll() is not None:
                self.procs[port] = self._start(port)

    def stop_all(self):
        with self.lock:
            for pr in self.procs.values():
                pr.kill()


class ChaosMonkey(threading.Thread):
    def __init__(self, fleet, interval=(1.0, 2.0), restart_after=1.5, seed=None, log=print):
        super().__init__(daemon=True)
        self.fleet, self.interval, self.restart_after = fleet, interval, restart_after
        self.rng = random.Random(seed)
        self.log = log
        self.kills = 0
        self._stop = threading.Event()

    def run(self):
        while not self._stop.wait(self.rng.uniform(*self.interval)):
            alive = self.fleet.alive()
            if len(alive) <= 1:
                continue  # sisakan minimal satu, kita mau uji ketahanan, bukan kiamat
            victim = self.rng.choice(alive)
            self.fleet.kill(victim)
            self.kills += 1
            self.log(f"  [monkey] membunuh backend-{victim}")
            if self.restart_after is not None:
                threading.Timer(self.restart_after, self._revive, args=(victim,)).start()

    def _revive(self, port):
        if not self._stop.is_set():
            self.fleet.restart(port)
            self.log(f"  [supervisor] menghidupkan lagi backend-{port}")

    def stop(self):
        self._stop.set()
