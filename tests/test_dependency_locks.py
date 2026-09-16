"""Issue #2: build inputs must resolve to a reviewed, committed graph.

Deterministic gate (no network): every manifest dep must appear pinned in the
committed lock artifact; CI must use deterministic install commands; third-party
Actions must be pinned to immutable SHAs. Regenerate locks with:

    npm install --package-lock-only        # in cloudflare/
    uv pip compile requirements.txt -o requirements-lock.txt
    uv pip compile requirements-dev.txt -o requirements-dev-lock.txt
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github/workflows"


def _manifest_names(path: Path) -> set[str]:
    names = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        m = re.match(r"([A-Za-z0-9_.\-]+)", line)
        if m:
            names.add(m.group(1).lower().replace("_", "-"))
    return names


def _lock_pins(path: Path) -> dict[str, str]:
    pins = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^([A-Za-z0-9_.\-]+)==([^\s;\\]+)", line.strip())
        if m:
            pins[m.group(1).lower().replace("_", "-")] = m.group(2)
    return pins


def test_node_lockfile_committed_and_covers_manifest():
    lock = ROOT / "cloudflare/package-lock.json"
    assert lock.exists(), "cloudflare/package-lock.json must be committed"
    data = json.loads(lock.read_text(encoding="utf-8"))
    pkg = json.loads((ROOT / "cloudflare/package.json").read_text(encoding="utf-8"))
    locked = set(data.get("packages", {}).keys())
    for section in ("dependencies", "devDependencies"):
        for name in pkg.get(section, {}):
            assert f"node_modules/{name}" in locked, f"{name} missing from lock"


def test_python_locks_cover_manifests():
    cases = [
        ("requirements.txt", "requirements-lock.txt"),
        ("requirements-dev.txt", "requirements-dev-lock.txt"),
    ]
    for manifest, lock_name in cases:
        lock = ROOT / lock_name
        assert lock.exists(), f"{lock_name} must be committed"
        pins = _lock_pins(lock)
        missing = _manifest_names(ROOT / manifest) - set(pins)
        assert not missing, f"{manifest} deps not pinned in {lock_name}: {missing}"


def test_ci_uses_deterministic_installs():
    for wf in WORKFLOWS.glob("*.yml"):
        text = wf.read_text(encoding="utf-8")
        assert not re.search(r"run:\s*npm install\b", text), (
            f"{wf.name} uses `npm install`; use `npm ci` against the committed lock"
        )
        assert "pip install -r requirements.txt" not in text
        assert "pip install -r requirements-dev.txt" not in text


def test_third_party_actions_pinned_to_sha():
    uses_re = re.compile(r"uses:\s*([^\s#]+)")
    for wf in WORKFLOWS.glob("*.yml"):
        for m in uses_re.finditer(wf.read_text(encoding="utf-8")):
            ref = m.group(1)
            if ref.startswith("./"):
                continue
            version = ref.rsplit("@", 1)[-1]
            assert re.fullmatch(r"[0-9a-f]{40}", version), (
                f"{wf.name}: {ref} is not pinned to an immutable SHA"
            )
