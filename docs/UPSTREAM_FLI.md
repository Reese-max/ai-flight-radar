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
5. Re-run `pytest tests/test_fli_provider.py tests/test_fli_flexible.py` plus one bounded
   live search (`RADAR_PRIMARY_PROVIDER=fli`) before flipping the primary provider.

## Phase 2 additions (locally authored)

- `providers/fli_custom/provider.py`: `search(...)` now maps `cabin`
  (`ECONOMY|PREMIUM_ECONOMY|BUSINESS|FIRST`), `adults`, and IATA `airlines`
  into the vendored filter object; invalid values fail before any upstream call.
  A local response wrapper refuses HTML or absent/invalid `wrb.fr` payloads
  before the vendored search can return an ambiguous `None`. A supported empty
  shopping frame remains `NO_RESULTS`; refused frames are typed failures that
  may use the configured fallback. The existing client keeps its request budget.
- `providers/fli_custom/dates.py`: bounded flexible-date search over
  `SearchDates`. The query range has a hard 61-day ceiling, one round-trip
  duration is limited to 1–30 days, and callers cannot raise the 50-result
  ceiling. Returned dates, duration, and TWD currency are validated before a
  result is exposed. Typed upstream failures remain distinct from an empty
  successful search.
  Before the vendored calendar parser runs, the local adapter checks the
  `wrb.fr` payload and terminal row array. HTML, missing/invalid wire frames,
  unsupported terminal shapes, and malformed row structures are typed failures,
  while a supported empty row array remains `NO_RESULTS`. The wrapper adds no
  requests or retries and does not edit the upstream baseline. Offline transport
  fixtures exercise the actual vendored parser; they are not live calibration.
- `providers/fli_custom/plan.py`: `bound_route_matrix` enforces a hard 8-pair
  ceiling before building the Cartesian product.
- `providers/selector.py`: `search_with_provider_chain()` uses the configured
  `RADAR_PRIMARY_PROVIDER` and optional `RADAR_FALLBACK_PROVIDER`. It tries
  fallback only after a typed engine/upstream failure; validation and
  configuration errors propagate without retrying another provider, and a
  successful empty result stops the chain. The collector passes only these
  allowlisted, non-secret settings to its isolated search subprocess. The production default remains
  `fast_flights` until runtime calibration passes.
- `cloudflare/scripts/calibrate_fli.py`: bounded live calibration command;
  receipts land in `docs/calibration/` (e.g. `2026-10-03.json`).

## Calibration status: partial, not an acceptance pass

The existing `docs/calibration/2026-10-03.json` records three successful
observations: TPE–NRT round-trip, TPE–KIX one-way, and KHH–FUK round-trip. It is
useful preliminary evidence only. It has no TSA or RMQ origin, Okinawa or
Sapporo destination, repeated-date sample, or no-results case. The receipt also
does not record the requested/returned travel dates, parsed directness/stops,
or booking handoff evidence needed to validate those acceptance dimensions.
No additional live provider requests were made for this change. The issue's
representative-route, multiple-date, no-result, and response-correctness
calibration gates remain open, so this receipt does not authorize a production
provider switch.

Do not edit files inside `third_party/fli/fli/` — fork-style patches go in
`providers/fli_custom/` or a dedicated patch file documented here.
