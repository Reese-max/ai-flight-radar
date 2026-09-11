"""One web process and an optional bounded worker sharing one mounted database.

Railway volumes are mounted at runtime. If Railway starts this entrypoint as
root for volume setup, only the configured data directory is prepared and all
application processes run as the image's unprivileged radar user afterwards.
"""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent


def prepare():
    mode = os.getenv("DEPLOYMENT_MODE", "public").strip().lower()
    if mode not in {"public", "local"}:
        raise RuntimeError("DEPLOYMENT_MODE must be public or local")
    public = mode == "public"
    os.environ["DEPLOYMENT_MODE"] = mode
    if public and len(os.getenv("API_KEY", "").strip()) < 32:
        raise RuntimeError("Public deployment requires an API_KEY of at least 32 characters")
    port = int(os.getenv("PORT", os.getenv("API_PORT", "8787")))
    if not 1 <= port <= 65535:
        raise RuntimeError("PORT must be between 1 and 65535")
    configured = Path(os.getenv("DB_PATH", str(ROOT / "data" / "flights.db")))
    if not configured.is_absolute() or configured.resolve() != configured:
        raise RuntimeError("DB_PATH must be an absolute path without symbolic links")
    mount = os.getenv("RAILWAY_VOLUME_MOUNT_PATH")
    if os.getenv("RAILWAY_ENVIRONMENT_ID") and not mount:
        raise RuntimeError("Attach a persistent Railway volume before starting the service")
    if mount and configured.parent != Path(mount):
        raise RuntimeError("DB_PATH must be directly inside RAILWAY_VOLUME_MOUNT_PATH")
    configured.parent.mkdir(parents=True, exist_ok=True)
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        import pwd
        account = pwd.getpwnam("radar")
        # Never recursively take ownership of a user-specified directory tree.
        targets = [configured.parent, configured,
                   Path(str(configured) + "-wal"), Path(str(configured) + "-shm"),
                   Path(str(configured) + "-journal"), configured.parent / "worker-health.json"]
        for path in targets:
            if path.is_symlink():
                raise RuntimeError("Symbolic links are not allowed for runtime database files")
            if path.exists():
                os.chown(path, account.pw_uid, account.pw_gid)
        os.setgroups([])
        os.setgid(account.pw_gid)
        os.setuid(account.pw_uid)
    if not os.access(configured.parent, os.W_OK):
        raise RuntimeError("Persistent data directory is not writable by the application user")
    os.environ["DB_PATH"] = str(configured)
    return port


def stop_process(process):
    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=5)


def main():
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False)
    port = prepare()
    from config.settings import env_bool
    # Initialize and migrate before accepting any web request or worker scan.
    from core.database import init_db
    init_db()
    children = []
    stopping = False

    def request_stop(signum, frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    try:
        children.append(subprocess.Popen([
            sys.executable, "-m", "uvicorn", "api.site:app", "--host", "0.0.0.0",
            "--port", str(port), "--workers", "1", "--no-access-log",
            "--limit-concurrency", "40", "--timeout-keep-alive", "5",
        ], cwd=ROOT, start_new_session=True))
        if env_bool("AUTOSCAN_ENABLED"):
            children.append(subprocess.Popen([sys.executable, "deploy/worker.py"],
                                             cwd=ROOT, start_new_session=True))
        print("Flight Radar service started; automatic scans are " +
              ("enabled" if len(children) > 1 else "disabled"), flush=True)
        while not stopping:
            if any(child.poll() is not None for child in children):
                raise RuntimeError("A required child process stopped unexpectedly")
            time.sleep(1)
    finally:
        for child in reversed(children):
            stop_process(child)


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    try:
        main()
    except Exception as exc:
        print(f"Startup or supervision failed: {exc}", file=sys.stderr, flush=True)
        sys.exit(1)
