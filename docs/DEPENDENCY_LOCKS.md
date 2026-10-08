# Dependency locks and reproducible builds

One canonical dependency graph per runtime is committed to this repository.
A clean checkout plus a deterministic install reproduces the exact graph that
was reviewed — no silent resolution drift between audit time and deploy time.

## Artifacts

| Artifact | Generated from | Installs with |
|---|---|---|
| `cloudflare/package-lock.json` | `cloudflare/package.json` | `npm ci` (in `cloudflare/`) |
| `requirements.lock` | `requirements.txt` (application deps) | `pip install --require-hashes -r requirements.lock` |
| `requirements-dev.lock` | `requirements-dev.txt` (application + test deps) | `pip install --require-hashes -r requirements-dev.lock` |

`requirements.txt` / `requirements-dev.txt` stay human-edited with
compatible ranges. The `.lock` files are the reviewed resolution: every
package pinned with `==` plus `sha256` hashes for supply-chain review.
`npm install` is never used in CI or deploy paths; only `npm ci`, which
errors when `package.json` disagrees with the committed lock.

## Regenerating the locks

Prerequisites: Node 22+, `uv 0.12.21`, Python 3.12 target (matches CI and
the Docker image).

```bash
# Node (from the repository root)
npm --prefix cloudflare install --package-lock-only --ignore-scripts --no-audit --no-fund

# Python (from the repository root; keep the cutoff date in sync with
# .github/workflows/dependency-locks.yml)
uv pip compile --python-version 3.12 --generate-hashes --upgrade \
  --exclude-newer 2026-10-03T00:00:00Z \
  -o requirements.lock requirements.txt
uv pip compile --python-version 3.12 --generate-hashes --upgrade \
  --exclude-newer 2026-10-03T00:00:00Z \
  -o requirements-dev.lock requirements-dev.txt
```

`--exclude-newer` freezes the resolver's view of the package indexes.
`--upgrade` ignores compatible pins in an existing output file, so advancing
the cutoff actually resolves the newer eligible versions. With the cutoff
unchanged, regeneration reproduces the reviewed resolution.
After regenerating, `git diff --exit-code` must be clean unless the change
is the intended update under review.

## Verifying locally

```bash
# Node
npm ci --prefix cloudflare

# Python (clean environment)
python -m venv /tmp/lockcheck
/tmp/lockcheck/bin/pip install --require-hashes -r requirements.lock
/tmp/lockcheck/bin/pip install --require-hashes -r requirements-dev.lock

# Fast manifest/lock consistency check (also enforced by tests)
python -m pytest tests/test_reproducible_builds.py -q
```

## CI enforcement

- `Quality checks` installs from `requirements-dev.lock` with
  `--require-hashes` (Playwright included; only browser binaries are
  fetched separately via `playwright install`).
- `Cloudflare Workers checks` and `Deploy Cloudflare Workers` install with
  `npm ci`.
- The collector and seed workflows install from `requirements.lock` with
  `--require-hashes`; the Docker image builds from `requirements.lock`.
- The `Dependency locks drift gate` workflow installs from all three
  artifacts, runs an offline local-wheel check proving old output pins do not
  influence resolution, regenerates them with the documented commands, and fails when
  `git diff --exit-code` reports any change. Changing a manifest without
  regenerating its lock fails this gate; regenerating through the documented
  commands returns it to green.

## Update procedure (reviewable dependency PRs)

1. Edit the human-edited manifest (`requirements.txt`,
   `requirements-dev.txt`, or `cloudflare/package.json`) — never hand-edit
   a lock.
2. To take fresh versions, advance the `--exclude-newer` cutoff to the
   current UTC time in both this document and
   `.github/workflows/dependency-locks.yml`, then regenerate with the
   commands above (use `npm update <pkg>` + regen for targeted Node bumps).
3. Open a PR whose description names the dependency-graph change:
   added/removed packages and notable version moves from the lock diff.
4. The drift gate, the offline test suite, and the Cloudflare checks must
   all pass on the PR.

## Rollback

Dependency changes are ordinary commits, so rollback is a revert:

```bash
# Find the lock commit (locks always change in their own reviewable diff)
git log --oneline -- requirements.lock requirements-dev.lock cloudflare/package-lock.json
git revert <lock-commit-sha>
```

Then reinstall from the restored locks (`npm ci`,
`pip install --require-hashes -r ...`) and redeploy. Because installs read
only the committed artifacts, the reverted tree resolves the exact graph
that was live before the update — no archaeology required.

## Third-party Actions pinning

Every third-party step in `.github/workflows/*.yml` is pinned to an
immutable commit SHA with the reviewed tag kept as a trailing comment, e.g.
`actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803 # v6`.
To update an Action: resolve the new tag to its commit SHA
(`gh api repos/<owner>/<repo>/git/ref/tags/<tag>`), replace the SHA, keep
the `# <tag>` comment, and note the change in the PR. The offline suite
(`tests/test_reproducible_builds.py`) fails on any unpinned or floating
`uses:` reference.
