# Upstream: punitarani/fli (vendored engine)

AI Flight Radar vendors the Python search core of [`punitarani/fli`](https://github.com/punitarani/fli)
to serve as the `FliCustomProvider` engine (Issue #8). The tree under
`third_party/fli/fli/` is **verbatim upstream** — no local edits inside it. All
customization lives in `providers/fli_custom/` so upstream diffs and rebases stay
mechanical.

## Provenance

| Field | Value |
|---|---|
| upstream_repository | https://github.com/punitarani/fli |
| upstream_commit | `121d34fea056dc513258958c4262cb5a4cc033c1` |
| upstream_tag | none (commit after v0.10.0 era; see upstream `pyproject.toml` `version = "0.10.0"`) |
| upstream_license | MIT — `third_party/fli/LICENSE.txt` (must be preserved) |
| vendored_at | 2026-09-15 |
| last_upstream_reviewed_at | 2026-09-15 |
| local_patch_series | none — `third_party/fli/fli/` is byte-identical to upstream at `upstream_commit` |
| customization_notes | Adapter only: `providers/fli_custom/` + `providers/selector.py`. Engine timeout bounded via `FLI_TIMEOUT=20`; round-trip expansion bounded via `top_n=3`. |

## Runtime dependencies

The search path needs `pydantic` (already required), plus `curl-cffi`, `tenacity`,
`babel` — pinned in `requirements.txt`. Fli's `cli`/`mcp` extras (typer, fastmcp,
plotext, httpx) are vendored but never imported; their deps are intentionally not
installed.

## Upstream sync process

1. `git clone https://github.com/punitarani/fli` and check out the target commit/tag.
2. `diff -r <upstream>/fli third_party/fli/fli` — review what changed.
3. Replace `third_party/fli/fli/` wholesale; copy upstream `LICENSE.txt` again.
4. Update `upstream_commit` / `last_upstream_reviewed_at` above.
5. Re-run `pytest tests/test_fli_provider.py` plus one bounded live search
   (`RADAR_PRIMARY_PROVIDER=fli`) before flipping the primary provider.

Do not edit files inside `third_party/fli/fli/` — fork-style patches go in
`providers/fli_custom/` or a dedicated patch file documented here.
