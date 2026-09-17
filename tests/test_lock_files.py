"""Reproducible-build contract: committed locks, deterministic installs, pinned Actions.

Every dependency graph used by CI, deployment or Docker must resolve from a
committed artifact (cloudflare/package-lock.json, requirements-lock.txt,
requirements-dev-lock.txt), not from mutable ranges at install time. The
regeneration path is scripts/refresh-locks.sh + docs/DEPENDENCIES.md.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
TEMPLATES = ROOT / "cloudflare" / "templates"
REQ_LINE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s\\]+)", re.M)
SHA_PIN = re.compile(r"uses:\s+([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@([0-9a-f]{40})\s+#\s*(v\d\S*)")


def _norm(name):
    return re.sub(r"[-_.]+", "-", name.lower())


def _manifest_names(path):
    """Direct requirement names from a human-edited manifest, following -r includes."""
    names = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("-r "):
            names |= _manifest_names(ROOT / line.split(None, 1)[1])
            continue
        assert not line.startswith("-"), f"unexpected option in {path.name}: {line}"
        names.add(_norm(re.split(r"[<>=!~;\[ ]", line, maxsplit=1)[0]))
    return names


def _lock_pins(path):
    """name -> version for every pinned entry in a hash-locked requirements file."""
    return {_norm(m.group(1)): m.group(2) for m in REQ_LINE.finditer(path.read_text(encoding="utf-8"))}


def _workflow_texts():
    files = sorted(WORKFLOWS.glob("*.yml"))
    assert files, "no workflow files found"
    return {f.name: f.read_text(encoding="utf-8") for f in files}


def test_node_lock_committed_and_matches_manifest():
    package = json.loads((ROOT / "cloudflare" / "package.json").read_text(encoding="utf-8"))
    lock_path = ROOT / "cloudflare" / "package-lock.json"
    assert lock_path.is_file(), "cloudflare/package-lock.json must be committed"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    assert lock["lockfileVersion"] == 3
    assert lock["packages"][""]["devDependencies"] == package["devDependencies"]
    for name, spec in package["devDependencies"].items():
        entry = lock["packages"][f"node_modules/{name}"]
        assert entry["version"] == spec, f"{name}: lock {entry['version']} != manifest {spec}"
        assert entry["resolved"].startswith("https://")
        assert entry["integrity"].startswith("sha")


def test_python_locks_cover_manifests_with_hashes():
    app_lock = ROOT / "requirements-lock.txt"
    dev_lock = ROOT / "requirements-dev-lock.txt"
    for lock_path, manifest in ((app_lock, "requirements.txt"), (dev_lock, "requirements-dev.txt")):
        assert lock_path.is_file(), f"{lock_path.name} must be committed"
        text = lock_path.read_text(encoding="utf-8")
        pins = _lock_pins(lock_path)
        missing = _manifest_names(ROOT / manifest) - set(pins)
        assert not missing, f"{lock_path.name} does not pin manifest entries: {sorted(missing)}"
        assert len(pins) > len(_manifest_names(ROOT / manifest)), "lock must include transitive deps"
        # Every pinned package must carry a sha256 hash: unhashed pins are mutable installs.
        for line in re.sub(r"\\\n\s+", " ", text).splitlines():
            m = REQ_LINE.match(line)
            if m:
                assert "--hash=sha256:" in line, f"{m.group(1)} pinned without sha256 hash"


def test_dev_lock_includes_browser_test_dependency():
    # The browser smoke test dependency must resolve from the lock, not a CI-side range.
    assert "playwright" in _manifest_names(ROOT / "requirements-dev.txt")
    assert "playwright" in _lock_pins(ROOT / "requirements-dev-lock.txt")


def test_workflows_use_deterministic_installs_only():
    texts = _workflow_texts()
    for name, text in texts.items():
        assert "npm install" not in text, f"{name}: npm install is non-deterministic, use npm ci"
        assert "-r requirements.txt" not in text, f"{name}: install requirements-lock.txt"
        assert "-r requirements-dev.txt" not in text, f"{name}: install requirements-dev-lock.txt"
    for name in ("cloudflare-checks.yml", "cloudflare-deploy.yml"):
        assert "npm ci" in texts[name], f"{name} must install Node deps with npm ci"
    assert "requirements-dev-lock.txt" in texts["ci.yml"]
    assert "requirements-lock.txt" in texts["collector.yml"]
    assert "requirements-lock.txt" in texts["seed.yml"]


def test_ci_gate_regenerates_locks_and_fails_on_drift():
    text = _workflow_texts()["ci.yml"]
    assert "scripts/refresh-locks.sh" in text, "ci.yml must run the documented regeneration"
    assert "git diff --exit-code" in text or "git status --porcelain" in text, \
        "ci.yml must fail when regeneration changes tracked files"


def test_all_workflow_actions_pinned_to_sha_with_version_comment():
    for directory in (WORKFLOWS, TEMPLATES):
        for f in sorted(directory.glob("*.yml")):
            for lineno, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                if "uses:" not in line:
                    continue
                m = SHA_PIN.search(line)
                assert m, f"{f.name}:{lineno} action not pinned to a SHA with a # vX.Y.Z comment"


def test_dockerfile_installs_locked_requirements():
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "requirements-lock.txt" in text
    assert "-r requirements.txt" not in text


def test_refresh_script_and_documentation_exist():
    script = ROOT / "scripts" / "refresh-locks.sh"
    assert script.is_file(), "scripts/refresh-locks.sh must exist"
    text = script.read_text(encoding="utf-8")
    for needle in ("pip compile", "requirements-lock.txt", "requirements-dev-lock.txt",
                   "--generate-hashes", "package-lock-only"):
        assert needle in text, f"refresh-locks.sh missing {needle}"
    docs = (ROOT / "docs" / "DEPENDENCIES.md").read_text(encoding="utf-8")
    for needle in ("refresh-locks.sh", "npm ci", "rollback"):
        assert needle in docs, f"docs/DEPENDENCIES.md missing {needle}"
