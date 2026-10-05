"""Exercise the real documented/CI resolver commands using offline local wheels.

Run in the dependency drift job after installing its pinned uv executable.
An older compatible output pin must not influence a fresh cutoff resolution.
"""
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def compile_commands(text):
    pending = ""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("uv pip compile") or pending:
            pending += " " + line.rstrip("\\").strip()
            if not line.endswith("\\"):
                yield shlex.split(pending.strip())
                pending = ""


def make_wheel(directory, version):
    name = "lock_resolution_probe"
    info = f"{name}-{version}.dist-info"
    path = directory / f"{name}-{version}-py3-none-any.whl"
    with zipfile.ZipFile(path, "w") as wheel:
        wheel.writestr(f"{info}/METADATA", f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n")
        wheel.writestr(f"{info}/WHEEL", "Wheel-Version: 1.0\nGenerator: local-fixture\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
        wheel.writestr(f"{info}/RECORD", "")


def main():
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("The dependency resolution smoke requires the CI-pinned uv executable")
    sources = (ROOT / ".github/workflows/dependency-locks.yml", ROOT / "docs/DEPENDENCY_LOCKS.md")
    cutoff = os.environ.get("LOCK_EXCLUDE_NEWER", "2026-10-03T00:00:00Z")
    with tempfile.TemporaryDirectory(prefix="lock-resolution-") as temporary:
        directory = Path(temporary)
        wheels = directory / "wheels"
        wheels.mkdir()
        for version in ("1.0.0", "2.0.0"):
            make_wheel(wheels, version)
        for source in sources:
            commands = list(compile_commands(source.read_text()))
            if len(commands) != 2:
                raise AssertionError(f"{source.name}: expected application and development compile commands")
            for command in commands:
                output = directory / command[command.index("-o") + 1]
                manifest = directory / command[-1]
                output.write_text("lock-resolution-probe==1.0.0\n")
                manifest.write_text("lock-resolution-probe>=1,<3\n")
                command[0] = uv
                command[command.index("-o") + 1] = str(output)
                command[-1] = str(manifest)
                command = [cutoff if argument == "$LOCK_EXCLUDE_NEWER" else argument for argument in command]
                command += ["--offline", "--no-index", "--find-links", str(wheels)]
                subprocess.run(command, check=True, capture_output=True, text=True,
                               env={**os.environ, "UV_CACHE_DIR": str(directory / "cache")})
                resolved = output.read_text()
                pins = dict(re.findall(r"^([a-z0-9-]+)==([^\s\\]+)", resolved, re.MULTILINE))
                if pins.get("lock-resolution-probe") != "2.0.0":
                    raise AssertionError(f"{source.name}: {manifest.name} preserved an older compatible output pin")
                if "--hash=sha256:" not in resolved:
                    raise AssertionError("Resolved lock must retain artifact hashes")
                print(f"PASS {source.name}: {manifest.name} resolves the latest local candidate with hashes")


if __name__ == "__main__":
    main()
