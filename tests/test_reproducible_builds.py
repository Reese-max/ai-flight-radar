"""Reproducible-build guarantees (issue #2).

Clean checkout + deterministic install must reproduce the reviewed Node and
Python dependency graphs: committed resolution artifacts, hash-locked Python
installs, `npm ci` in admission/deploy workflows, immutable action pins, and a
CI gate that fails when regenerating a lock changes tracked files.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
CF = ROOT / "cloudflare"


def _workflow_texts():
    texts = {p.name: p.read_text(encoding="utf-8") for p in sorted(WORKFLOWS.glob("*.yml"))}
    for p in sorted((CF / "templates").glob("*.yml")):
        texts[f"cloudflare/templates/{p.name}"] = p.read_text(encoding="utf-8")
    return texts


def _requirement_names(path):
    names = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        names.add(re.match(r"[A-Za-z0-9._-]+", line).group(0).lower())
    return names


def _lock_blocks(path):
    """Return one block per `name==version` line with its continuation lines."""
    blocks, current = [], None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if re.match(r"^[A-Za-z0-9._-]+==", line):
            current = [line]
            blocks.append(current)
        elif current is not None and line and not line.startswith("#"):
            current.append(line)
    return blocks


def _pinned_names(path):
    pins = {}
    for block in _lock_blocks(path):
        m = re.match(r"^([A-Za-z0-9._-]+)==([^\s\\;]+)", block[0])
        pins[m.group(1).lower()] = m.group(2)
    return pins


def test_node_lockfile_is_committed_and_consistent():
    pkg = json.loads((CF / "package.json").read_text(encoding="utf-8"))
    lock_path = CF / "package-lock.json"
    assert lock_path.is_file(), "cloudflare/package-lock.json must be committed"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    assert lock.get("lockfileVersion") == 3
    root = lock["packages"][""]
    for section in ("dependencies", "devDependencies"):
        assert root.get(section, {}) == pkg.get(section, {})
    wrangler = lock["packages"]["node_modules/wrangler"]
    assert wrangler["version"] == pkg["devDependencies"]["wrangler"]
    for path, entry in lock["packages"].items():
        if not path:
            continue
        assert entry.get("resolved"), f"{path} missing resolved URL"
        assert entry.get("integrity"), f"{path} missing integrity hash"


def test_python_locks_cover_manifests_with_hashes():
    app_lock = ROOT / "requirements.lock"
    dev_lock = ROOT / "requirements-dev.lock"
    assert app_lock.is_file(), "requirements.lock (compiled app graph) must be committed"
    assert dev_lock.is_file(), "requirements-dev.lock (compiled test graph) must be committed"
    app_pins = _pinned_names(app_lock)
    dev_pins = _pinned_names(dev_lock)
    app_names = _requirement_names(ROOT / "requirements.txt")
    dev_names = _requirement_names(ROOT / "requirements-dev.txt")
    assert app_names <= set(app_pins), f"missing from requirements.lock: {app_names - set(app_pins)}"
    assert dev_names <= set(dev_pins), f"missing from requirements-dev.lock: {dev_names - set(dev_pins)}"
    assert set(app_pins) <= set(dev_pins)
    for lock in (app_lock, dev_lock):
        for block in _lock_blocks(lock):
            assert re.match(r"^[A-Za-z0-9._-]+==[^\s\\;]+", block[0]), block[0]
            assert any("--hash=sha256:" in line for line in block[1:]), f"{block[0]} lacks sha256 hashes"


def test_no_mutable_install_commands_in_workflows():
    for name, text in _workflow_texts().items():
        for m in re.finditer(r"\bnpm\s+install\b([^\n]*)", text):
            args = m.group(1).strip()
            assert args == "--package-lock-only", f"{name}: mutable 'npm install{ ' ' + args if args else ''}'"
        for m in re.finditer(r"\bpip\s+install\b([^\n|]+)", text):
            args = m.group(1).strip()
            if "-r" in args.split():
                assert "--require-hashes" in args, f"{name}: pip -r install must verify hashes"
                assert re.search(r"requirements(?:-dev)?\.lock\b", args), f"{name}: pip -r must install a lock file"
                assert not re.search(r"requirements(?:-dev)?\.txt\b", args), f"{name}: installs the range manifest, not the lock"
            else:
                pkgs = [a for a in args.split() if not a.startswith("-")]
                assert pkgs and all("==" in a for a in pkgs), f"{name}: unpinned 'pip install {args}'"


def test_cloudflare_workflows_install_with_npm_ci():
    texts = _workflow_texts()
    for wf in ("cloudflare-checks.yml", "cloudflare-deploy.yml"):
        assert re.search(r"\bnpm\s+ci\b", texts[wf]), f"{wf} must install with npm ci"


def test_third_party_actions_pinned_to_commit_sha():
    uses_re = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)(?:\s+#\s*(.+?))?\s*$")
    sha_re = re.compile(r"^[A-Za-z0-9_-]+/[A-Za-z0-9._-]+@[0-9a-f]{40}$")
    found = 0
    for name, text in _workflow_texts().items():
        for lineno, line in enumerate(text.splitlines(), 1):
            m = uses_re.match(line)
            if not m or m.group(1).startswith("./"):
                continue
            found += 1
            assert sha_re.match(m.group(1)), f"{name}:{lineno} action not pinned to a 40-char commit SHA: {m.group(1)}"
            assert m.group(2) and re.search(r"v\d+\.\d+", m.group(2)), f"{name}:{lineno} missing readable version comment"
    assert found >= 4


def test_ci_gate_fails_on_lock_drift():
    ci = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
    assert "dependency-locks:" in ci
    assert "npm ci" in ci
    assert "--require-hashes" in ci
    assert "uv pip compile" in ci
    assert re.search(r"npm@[\d.]+\s+install --package-lock-only", ci)
    assert "git diff --exit-code" in ci


def test_dockerfile_installs_from_committed_lock():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "requirements.lock" in dockerfile
    assert "--require-hashes" in dockerfile
    assert re.search(r"^FROM\s+\S+@sha256:[0-9a-f]{64}", dockerfile, re.M), "base image must be digest-pinned"


def test_dependabot_files_reviewable_update_prs():
    cfg = ROOT / ".github" / "dependabot.yml"
    assert cfg.is_file(), "dependabot.yml must file reviewable dependency-update PRs"
    text = cfg.read_text(encoding="utf-8")
    assert re.search(r'package-ecosystem:\s*"?npm', text)
    assert re.search(r'package-ecosystem:\s*"?(uv|pip)"', text)
    assert re.search(r'package-ecosystem:\s*"?github-actions', text)


def test_docs_describe_update_and_rollback():
    doc = ROOT / "docs" / "DEPENDENCIES.md"
    assert doc.is_file(), "docs/DEPENDENCIES.md must document the lock workflow"
    text = doc.read_text(encoding="utf-8")
    assert "requirements.lock" in text
    assert "package-lock.json" in text
    assert "uv pip compile" in text
    assert re.search(r"revert|rollback|roll back|還原|回退", text, re.IGNORECASE)
