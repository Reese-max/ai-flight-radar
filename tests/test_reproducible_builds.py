"""Reproducible dependency graphs: committed locks, deterministic installs.

Issue #2: a clean checkout plus a deterministic install must reproduce the
reviewed Node and Python dependency graphs, and CI must fail on graph drift.
These tests assert the committed resolution artifacts, the deterministic
install paths, the SHA-pinned third-party Actions, and the drift gate.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS_DIR = ROOT / ".github" / "workflows"
CLOUDFLARE_DIR = ROOT / "cloudflare"
APP_MANIFEST = ROOT / "requirements.txt"
DEV_MANIFEST = ROOT / "requirements-dev.txt"
APP_LOCK = ROOT / "requirements.lock"
DEV_LOCK = ROOT / "requirements-dev.lock"
NODE_LOCK = CLOUDFLARE_DIR / "package-lock.json"
LOCK_DOC = ROOT / "docs" / "DEPENDENCY_LOCKS.md"
DRIFT_WORKFLOW = WORKFLOWS_DIR / "dependency-locks.yml"

_PINNED_USES = re.compile(r"^[^#\s]+?@[0-9a-f]{40}(?:\s*#\s*\S+)?\s*$")
_MUTABLE_NPM_INSTALL = re.compile(r"(?<![\w-])npm\s+install(?![\w-])")


def _normalize(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def manifest_requirement_names(manifest_text):
    """Direct package names from a human-edited manifest (skips includes/comments)."""
    names = []
    for raw in manifest_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        match = re.match(r"^([A-Za-z0-9_.\-]+)(\[[^\]]*\])?\s*(.*?)\s*$", line)
        if match:
            names.append(_normalize(match.group(1)))
    return names


def lock_pins(lock_text):
    """Exact ``name -> version`` pins from a ``pip freeze``-style lock."""
    pins = {}
    for raw in lock_text.splitlines():
        line = raw.strip().rstrip("\\").strip()
        match = re.match(r"^([A-Za-z0-9_.\-]+)==([^\s;\\]+)", line)
        if match:
            pins[_normalize(match.group(1))] = match.group(2)
    return pins


def manifest_covered_by_lock(manifest_text, lock_text):
    """True when every manifest requirement has an exact pin in the lock.

    Returns ``(covered, missing)`` so the CI drift gate and this suite can
    report which dependency changed without its lock being regenerated.
    """
    pins = lock_pins(lock_text)
    missing = [n for n in manifest_requirement_names(manifest_text) if n not in pins]
    return (not missing, missing)


def workflow_uses_entries(workflow_text):
    entries = []
    for raw in workflow_text.splitlines():
        stripped = raw.strip()
        if stripped.startswith("uses:"):
            entries.append(stripped[len("uses:"):].strip())
    return entries


def test_node_lock_committed_and_consistent():
    assert NODE_LOCK.is_file(), "cloudflare/package-lock.json must be committed"
    package = json.loads((CLOUDFLARE_DIR / "package.json").read_text())
    lock = json.loads(NODE_LOCK.read_text())
    assert lock.get("name") == package["name"]
    assert lock.get("lockfileVersion") in (2, 3)
    packages = lock.get("packages", {})
    assert packages, "lock must record the resolved package tree"
    root_entry = packages.get("", {})
    locked_wrangler = (root_entry.get("devDependencies") or {}).get("wrangler")
    assert locked_wrangler == package["devDependencies"]["wrangler"]
    assert any(
        info.get("resolved") and info.get("integrity")
        for path, info in packages.items() if path
    ), "locked entries must carry resolved URLs and integrity hashes"


def test_no_mutable_npm_install_in_workflows():
    offenders = []
    for workflow in sorted(WORKFLOWS_DIR.glob("*.yml")):
        for lineno, raw in enumerate(workflow.read_text().splitlines(), 1):
            # `--package-lock-only` regenerates the committed lock without
            # installing anything; only real installs must go through `npm ci`.
            if "--package-lock-only" in raw:
                continue
            if _MUTABLE_NPM_INSTALL.search(raw):
                offenders.append(f"{workflow.name}:{lineno}:{raw.strip()}")
    assert not offenders, f"mutable installs must use `npm ci`: {offenders}"
    for name in ("cloudflare-checks.yml", "cloudflare-deploy.yml"):
        text = (WORKFLOWS_DIR / name).read_text()
        assert "npm ci" in text, f"{name} must install the committed lock with `npm ci`"


def test_python_locks_cover_manifests_with_hashes():
    for manifest_path, lock_path in ((APP_MANIFEST, APP_LOCK), (DEV_MANIFEST, DEV_LOCK)):
        assert lock_path.is_file(), f"{lock_path.name} must be committed"
        lock_text = lock_path.read_text()
        assert "--hash=sha256:" in lock_text, f"{lock_path.name} must carry hashes"
        covered, missing = manifest_covered_by_lock(
            manifest_path.read_text(), lock_text
        )
        assert covered, f"{lock_path.name} missing pins for manifest change: {missing}"


def test_third_party_actions_pinned_to_shas():
    offenders = []
    unpinned = []
    for workflow in sorted(WORKFLOWS_DIR.glob("*.yml")):
        for entry in workflow_uses_entries(workflow.read_text()):
            if entry.startswith("./") or entry.startswith("docker://"):
                continue
            if "@" not in entry:
                offenders.append(f"{workflow.name}:{entry}")
                continue
            if not _PINNED_USES.match(entry):
                unpinned.append(f"{workflow.name}:{entry}")
    assert not offenders, f"actions without pins: {offenders}"
    assert not unpinned, f"actions not pinned to immutable SHAs: {unpinned}"


def test_clean_checkout_drift_gate_exists():
    assert DRIFT_WORKFLOW.is_file(), "dependency drift gate workflow must exist"
    text = DRIFT_WORKFLOW.read_text()
    for token in (
        "npm ci",
        "requirements.lock",
        "requirements-dev.lock",
        "package-lock.json",
        "git diff --exit-code",
    ):
        assert token in text, f"drift gate must cover {token}"


def test_lock_workflow_documented_with_update_and_rollback():
    assert LOCK_DOC.is_file(), "lock workflow doc must exist"
    text = LOCK_DOC.read_text()
    for token in (
        "uv pip compile",
        "--generate-hashes",
        "--exclude-newer",
        "npm ci",
        "requirements.lock",
        "package-lock.json",
    ):
        assert token in text, f"lock doc must describe {token}"
    assert "ollback" in text, "lock doc must give rollback instructions"


def test_manifest_drift_detected_without_lock_regeneration():
    manifest = "fastapi>=0.115,<1\npytest>=8,<10\n"
    lock = (
        "fastapi==0.139.2 \\\n"
        "    --hash=sha256:aaa\n"
        "pytest==8.3.4 \\\n"
        "    --hash=sha256:bbb\n"
    )
    covered, _ = manifest_covered_by_lock(manifest, lock)
    assert covered
    drifted = manifest + "django>=5,<6\n"
    covered, missing = manifest_covered_by_lock(drifted, lock)
    assert not covered, "manifest changed without lock regen must fail the gate"
    assert missing == ["django"]
