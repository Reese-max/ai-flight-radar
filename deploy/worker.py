"""Bounded cloud scans with a real heartbeat and graceful subprocess shutdown."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from config.settings import settings


def bounded_int(name, default, lower, upper):
    value = int(os.getenv(name, str(default)))
    if not lower <= value <= upper:
        raise ValueError(f"{name} must be between {lower} and {upper}")
    return value


def main():
    interval = bounded_int("SCAN_INTERVAL_SECONDS", 300, 60, 86400)
    count = bounded_int("SCAN_BATCH_SIZE", 3, 1, 10)
    timeout = bounded_int("SCAN_TIMEOUT_SECONDS", 180, 30, 600)
    path = Path(settings.DB_PATH).parent / "worker-health.json"
    stopping = False
    child = None

    def request_stop(signum, frame):
        nonlocal stopping
        stopping = True

    def heartbeat(status):
        temporary = path.with_suffix(f".{os.getpid()}.tmp")
        temporary.write_text(json.dumps({"status": status,
            "heartbeat_at": datetime.now(timezone.utc).isoformat()}), encoding="utf-8")
        temporary.replace(path)

    def kill_child():
        if child is not None and child.poll() is None:
            # Scan runs in this worker's process group. The supervisor can kill
            # the entire group, including a stuck network request, on shutdown.
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    try:
        while not stopping:
            heartbeat("scanning")
            child = subprocess.Popen([sys.executable, "main.py", "scan", "--count", str(count)], cwd=ROOT)
            started = time.monotonic()
            next_beat = started + 15
            timed_out = False
            while child.poll() is None and not stopping:
                now = time.monotonic()
                if now - started > timeout:
                    timed_out = True
                    kill_child()
                    break
                if now >= next_beat:
                    heartbeat("scanning")
                    next_beat = now + 15
                time.sleep(1)
            kill_child()
            if stopping:
                break
            # A zero exit status is NOT a claim that a quote was found. The UI
            # separately displays the actual latest successful database snapshot.
            state = "error" if timed_out or child.returncode else "idle"
            wait_until = time.monotonic() + interval
            while not stopping and time.monotonic() < wait_until:
                heartbeat(state)
                for _ in range(15):
                    if stopping or time.monotonic() >= wait_until:
                        break
                    time.sleep(1)
    finally:
        kill_child()
        heartbeat("stopped")


if __name__ == "__main__":
    main()
