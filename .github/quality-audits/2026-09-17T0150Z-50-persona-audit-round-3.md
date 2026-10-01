# AI Flight Radar — Fixed A01–J05 50-Persona Audit — Round 3

Audit run: `2026-09-17T01:50:00Z-ai-flight-radar-r3`\
Protocol: `Reese-max/autodev-ng/docs/portfolio-audit/2026-09-06-50-persona-audit.md`\
Protocol blob: `6e3499d6ef5be7e123050e1526946f6a40f99263`\
Issue Quality v2: `Reese-max/autodev-ng/docs/portfolio-audit/2026-09-14-issue-quality-v2.md`\
Quality-v2 blob: `8167e10798071d2276addaff6b201c6b0e904a2a`\
Default branch: `main`\
Inspected product SHA: [`6228138337f950cb6399088c4f814f27a518e29e`](https://github.com/Reese-max/ai-flight-radar/commit/6228138337f950cb6399088c4f814f27a518e29e)\
Previous fixed-50 report: [Round 2](https://github.com/Reese-max/ai-flight-radar/blob/f1613c90192ecb2e607e9c4c96160995d8ef66b1/.github/quality-audits/2026-09-14T2340Z-50-persona-audit-round-2.md)\
Umbrella: [#5](https://github.com/Reese-max/ai-flight-radar/issues/5)

> All A01–J05 results are synthetic model simulations, not 50 human testers and not 50 independent validations. Persona identities, constraints and original success conditions are inherited unchanged from the governing protocol. `SOURCE_CONFIRMED` is static source evidence; runtime success/failure is claimed only where an actual execution receipt was read.

## Why Round 3 was required

Round 2 inspected product SHA `2ad341d548653fe0ba56490136c4e96daee1712e`. Current `main` is three commits ahead of the round-2 report commit and materially changes the product surface: `bd983fb` vendored `punitarani/fli` into `third_party/fli/` and added the optional `FliCustomProvider` behind `RADAR_PRIMARY_PROVIDER` (Issue #8 phase 1), and `6228138` repaired the stale six-task seed-plan test so the suite asserts the real 48-route matrix (Issue #7, now closed). Audit-only commits in the same range (`f1613c9` round-2 report, `f17e1ff` product-board audit) are not treated as product changes.

One open pull request exists at audit time: [PR #9 — fix(build): reproducible installs + align seed cadence with collector capacity (#2, #6)](https://github.com/Reese-max/ai-flight-radar/pull/9), head `78c560f4a42179bdfc4f6d10f5aaea8652ac57a6`. It is not merged; the inspected product is unchanged default-branch `main`, and this round audits `main` only. Existing Issues #1–#8 and their comments were re-read; no active audit lease was observed on the tracker.

## Evidence read

Current README, Cloudflare deployment/check/collector/seed workflows, `cloudflare/scripts/tasks.py`, `collector.py`, `search_once.py`, `prepare-config.mjs`, `cloudflare/src/store.mjs`/`logic.mjs`, `build.mjs` label adapter, `providers/selector.py`, `providers/fli_custom/*`, `providers/fast_flights_impl.py`, `providers/rate_limiter.py`, `docs/UPSTREAM_FLI.md`, `third_party/fli/LICENSE.txt`, current tests/tree, prior audit rounds, the 2026-09-15 product-board audit, all open/closed Issues, PR #9 diff and CI, branch state, and Actions runs/jobs **including downloaded step logs** were inspected.

### Current execution evidence

1. [Cloudflare Workers checks run 34920503429](https://github.com/Reese-max/ai-flight-radar/actions/runs/34920503429) on exact inspected SHA `6228138`: **success** — offline Worker/collector tests, `npm install` + build, local D1 migration, and real `workerd` smoke all executed. The Round-2 offline-suite failure is resolved at this SHA (root cause was the #7 stale test).
2. [Quality checks run 34920503499](https://github.com/Reese-max/ai-flight-radar/actions/runs/34920503499) on exact inspected SHA: **success** — pytest, `test_ui_logic.mjs`, `main.py --help`, and `tests/browser_smoke.py` (Playwright Chromium: desktop 1440, mobile 390/360 overflow, dialogs, detail, watchlist, credential masking, retained-data failure states, XSS-in-airline fixture; synthetic API only). This is a current-SHA browser receipt for the covered paths; it does not exercise assistive technology, 200% zoom, or live providers.
3. Scheduled collector on exact inspected SHA — **all 12 recorded runs: 1 success / 11 failures** (schedule `17,47 * * * *` fired at GitHub-delayed times), all failures sharing one confirmed signature. Step logs were retrievable this round; every failed run ends `Run a bounded batch` with `{"attempted":N,"observed":N-1,"errors":1}` → exit code 2:

| Run | UTC | attempted | observed | errors |
|---|---|---:|---:|---:|
| [34935847886](https://github.com/Reese-max/ai-flight-radar/actions/runs/34935847886) | 09-15 06:11 | 1 | 0 | 1 |
| [34965350058](https://github.com/Reese-max/ai-flight-radar/actions/runs/34965350058) | 09-15 11:49 | 1 | 0 | 1 |
| [34998820786](https://github.com/Reese-max/ai-flight-radar/actions/runs/34998820786) | 09-15 17:03 | 1 | 0 | 1 |
| [35018556246](https://github.com/Reese-max/ai-flight-radar/actions/runs/35018556246) | 09-15 20:16 | 1 | 0 | 1 |
| [35033483482](https://github.com/Reese-max/ai-flight-radar/actions/runs/35033483482) | 09-15 22:58 | 1 | 0 | 1 |
| [35044178125](https://github.com/Reese-max/ai-flight-radar/actions/runs/35044178125) | 09-16 01:28 | 3 | 2 | 1 |
| [35065505083](https://github.com/Reese-max/ai-flight-radar/actions/runs/35065505083) | 09-16 06:49 | 3 | 3 | 0 ✅ |
| [35096922119](https://github.com/Reese-max/ai-flight-radar/actions/runs/35096922119) | 09-16 12:38 | 3 | 2 | 1 |
| [35127301203](https://github.com/Reese-max/ai-flight-radar/actions/runs/35127301203) | 09-16 17:18 | 1 | 0 | 1 |
| [35146562920](https://github.com/Reese-max/ai-flight-radar/actions/runs/35146562920) | 09-16 20:27 | 3 | 2 | 1 |
| [35161547074](https://github.com/Reese-max/ai-flight-radar/actions/runs/35161547074) | 09-16 23:16 | 3 | 2 | 1 |
| [35170874929](https://github.com/Reese-max/ai-flight-radar/actions/runs/35170874929) | 09-17 01:31 | 2 | 1 | 1 |

   Aggregate: 23 attempted / 12 observed / 11 errors ≈ **48% per-task error rate**; 11 of 12 runs red. Mechanism `CONFIRMED` from source: each errored task is receipted to D1 as `outcome='error'` and rescheduled +1h (`store.mjs`), the collector stops the batch on the first error (`collector.py` `break`), and `main()` returns 2 whenever `errors > 0`. The per-task error *type* (rate-limit, timeout, parse, or no-valid-offer) is still unexposed — `search_once.py` deliberately sanitizes provider output to `{'outcome':'error'}`. Run env confirms `RADAR_PRIMARY_PROVIDER` unset → production path is `fast_flights`; the new Fli provider is **not** implicated. This is real current-SHA runtime evidence of degraded live source health, attributable to Issue #1's uncalibrated admission — not to #6 (capacity arithmetic) or #8 (dormant provider).
4. Local execution receipt at inspected SHA (this audit, Linux, Python 3.13.5, Node 20.19.2, fresh venv from `requirements-dev.txt`): `pytest` **79/79 pass**; `python -m unittest discover -s cloudflare/tests` **23/23 pass**; `node --test tests/test_ui_logic.mjs` **10/10 pass**; `python cloudflare/scripts/collector.py` dry-run prints `{"mode":"dry-run","network_calls":0}`; `main.py --help` OK; `providers.fli_custom` tests exercise `_load_engine()`, proving the vendored `fli` package imports under the pinned `curl-cffi==0.16.3`/`tenacity==8.5.0`/`babel==2.18.0`. `node --test cloudflare/tests/*.test.mjs`: **34/36 pass**; `local.test.mjs` and `worker.test.mjs` fail to *load* under Node 20 (`ERR_UNKNOWN_BUILTIN_MODULE: node:sqlite`) — an environment limitation only; the workflow pins Node 22 where the same files pass (receipt 1). Not a product defect.
5. [PR #9](https://github.com/Reese-max/ai-flight-radar/pull/9) CI on `78c560f`: Quality checks [35080851069](https://github.com/Reese-max/ai-flight-radar/actions/runs/35080851069) and Cloudflare Workers checks [35080851087](https://github.com/Reese-max/ai-flight-radar/actions/runs/35080851087) both succeeded. It is remediation evidence-in-flight, not a `main` receipt.
6. Historical runs on older SHAs (`f2dac80`, `a886940`, `2ad341d`) remain valid only for what they executed; they are not promoted to current-SHA proof.

No paid provider call, workflow rerun, deployment, purchase, notification, destructive failure injection, secret/settings change, product-code change, merge, or Issue mutation was performed by this audit.

## Finding disposition

### CLOSED this round — #7 stale seed-plan test → VERIFIED_FIXED

[#7](https://github.com/Reese-max/ai-flight-radar/issues/7) is closed. Commit `6228138` replaced the hard-coded six-task assertion with the catalog-derived 48-task contract (48 tasks, deterministic first route, 48 unique route pairs). Cloudflare Workers checks pass on the exact inspected SHA. Disposition: `VERIFIED_FIXED` at `6228138` — the regression scenario now asserts the real matrix instead of pinning a stale number.

### Existing #1 — collector admission / quote-fidelity gate: STILL_REPRODUCIBLE, evidence upgraded

[#1](https://github.com/Reese-max/ai-flight-radar/issues/1) remains `VALIDATION_GAP / RELIABILITY`. Severity is rendered as `P1-gate` this round, matching the Issue's own `[P1]` title (the umbrella tracker's older v2 disposition text listed P2); this is a label alignment, not a new severity claim. Two material changes this round: (a) the scheduled collector is **provably enabled** — run-log `if` evaluation shows `vars.CF_RADAR_COLLECTOR_ENABLED == 'true'` executing real batches against the deployed worker; the issue's older "correctly disabled" premise is stale. (b) Required runtime evidence is now partially present and negative: ≈48% of attempted provider tasks errored across all 12 recorded current-SHA runs. This is exactly the uncalibrated-source risk #1 gates — but the per-task typed cause remains unrecorded by design, and booking-handoff/price-fidelity evidence is still absent. Keep #1 as the tracker; do not invent a new fingerprint for the error rate. No `BUILD/NARROW/BLOCK` calibration decision exists; per #1's own criteria the correct disposition of a ~half-error live source cannot be established without typed receipts.

### Existing #2 — reproducible dependency/build graph: STILL_REPRODUCIBLE at inspected SHA

[#2](https://github.com/Reese-max/ai-flight-radar/issues/2) remains P2 / SOURCE_CONFIRMED. `bd983fb` added three exactly-pinned Fli runtime deps, but the manifest still mixes ranges (`fastapi>=0.115,<1`, etc.) with pins, no `package-lock.json` is committed for `cloudflare/`, and workflows still run `npm install`/`pip install -r requirements.txt`. PR #9 (unmerged) proposes lockfiles, `npm ci`, SHA-pinned actions, and a drift test — remediation pending review, not on `main`.

### Existing #6 — 48-route cadence vs 6 claims/hour: STILL_REPRODUCIBLE at inspected SHA, now with runtime degradation data

[#6](https://github.com/Reese-max/ai-flight-radar/issues/6) remains `BUG / P2 / SOURCE_CONFIRMED`. On `main`: `ROUTES` is still 4×12=48, `store.mjs` still reschedules ok/empty at +6h, the workflow is still 2 runs/h × ≤3 tasks, `MAX_SEARCHES_PER_HOUR` deploy-bound ≤10 with documented 6/h intent — the 8-vs-6 arithmetic is unchanged. New this round: actual run data shows effective coverage is *worse* than the 8h floor, because error tasks re-due at +1h re-consume the same claim budget and ~half of attempts currently error (see evidence 3). PR #9 proposes the 6h→8h revisit plus a deterministic capacity invariant — the issue's "smallest useful fix" path — but it is not merged and must not be credited to `main`. Affected personas: C05, D01, D02, D04, H04, H05, I04, J01, J03, J05 — the same #6-mapped set as Round 2's matrix (Round 2's prose list omitted J05 although its matrix mapped J05 to #6).

### Existing #8 — Fli provider migration: phase 1 PARTIALLY_IMPLEMENTED, one contract gap confirmed

[#8](https://github.com/Reese-max/ai-flight-radar/issues/8) phase 1 landed at `bd983fb` with the required provenance (upstream commit `121d34fe…`, MIT `LICENSE.txt`, `docs/UPSTREAM_FLI.md`), an isolated adapter returning the repo's `StandardFlightOffer`, a safe `fast_flights` default, child-env passthrough of only `RADAR_PRIMARY_PROVIDER`, and 8 offline contract tests (all green locally). Confirmed residual gap already dispositioned by the 2026-09-15 board audit: a round-trip `search()` issues 1 + up to `TOP_N=3` engine calls, each under Fli's own 3-attempt retry, and `rate_limiter.wait()` is invoked once per `search()`, not per internal HTTP attempt — so the outer 6-claims/h task budget does not bound actual provider requests *when fli is selected*. It is opt-in and inactive in production (evidence 3 env), so this is `P2 / SOURCE_CONFIRMED / NEEDS_REVIEW` contract debt under #8's "collector request budget cannot be bypassed by provider internals" acceptance item — not a live incident. Other open #8 acceptance items: `search_dates` bounded flexible-date plan, cabin/adults parameters, fallback wiring (`RADAR_FALLBACK_PROVIDER` is not implemented — selector knows only the primary), and the pre-switch bounded live calibration receipt.

### Existing #3 / #4 — research items unchanged

#3 (licensing research, P3): note the tree now contains vendored MIT-licensed code (`third_party/fli/` + `LICENSE.txt` + provenance doc), which makes the licensing-boundary question more concrete, not resolved. #4 (WatchSpec research): unchanged, not a defect.

### No new independent P0/P1/P2 fingerprint

The high live task-error rate is mechanism-confirmed but type-unknown, and it maps onto #1's existing admission/calibration contract rather than a separate defect. One adjacent *candidate* observation is recorded for owner disposition without an Issue write (this worker is not authorized to create Issues): `search_once.py normalize()` reports `outcome='error'` whenever the provider returned offers but none passed validation — which includes "route/date has only connecting flights under the direct-only contract". If any of the 48 seeded routes lack nonstop service, those tasks would error every run, masquerading as upstream failure, stopping batches early, and re-consuming the +1h retry budget. This is `SOURCE_CONFIRMED` as a code path and *consistent* with the observed signature, but **not** claimed as the proven cause of the live error rate; it is a typed-outcome fidelity question already inside #1's acceptance criteria. If the owner wants it tracked separately, it needs its own Issue.

## Fixed 50-persona scenario matrix

Evidence legend: `SRC` = SOURCE_CONFIRMED at inspected SHA; `CI-current` = actual run/job at inspected SHA; `LOCAL` = this audit's local execution on inspected SHA; `CI-old` = real execution on an older SHA only; `SYN` = synthetic persona reasoning; `NRV` = NEEDS_RUNTIME_VERIFICATION.

| Persona | Goal / precondition / input | Steps / failure trigger | Expected success | Round-3 observation | Evidence | Severity / mapping |
|---|---|---|---|---|---|---|
| A01 | First-time mobile traveler, TPE→FUK | Open UI → filter → detail | Understand observed-vs-bookable state on narrow screen | 390/360 no-overflow + detail path executed on current SHA via CI browser smoke; AT/screen-reader unexecuted | SYN+SRC+CI-current | — |
| A02 | Docs-familiar, CLI-new student | README local setup | Fast first success or actionable blocker | Ordered setup remains; dependency reproducibility gap remains (PR #9 pending) | SYN+SRC | P2 #2 |
| A03 | Git/CLI student self-hosting | Clean checkout/install/customize | Reproducible reviewed environment | Manifest still mixes ranges; no committed locks on main | SYN+SRC | P2 #2 |
| A04 | Time-pressured traveler | Pick cheapest result quickly | Avoid false deal confidence | Observed/stale language exists; live source currently errors ~half of attempts; booking fidelity uncalibrated | SYN+SRC+CI-current | P1-gate #1 |
| A05 | Visual learner | Explore → compare → detail → watch | Clear state transitions | UI flow + dialogs + watchlist executed on current SHA (CI browser smoke) | SYN+SRC+CI-current | — |
| B01 | Non-programmer office user | Use hosted read-only UI | Compare without CLI | Read-only contract exists; public deployment availability not re-verified here | SYN+SRC, NRV | — |
| B02 | Junior engineer | Install and diagnose | Deterministic install/errors | #7 fixed — current-SHA offline suite green; mutable dependency graph remains | SYN+SRC+CI-current+LOCAL | P2 #2 |
| B03 | Designer / reversible actions | Add/pause browser watch | Explicit reversible local state | Browser-local watch contract exercised on current SHA (CI smoke: watchlist checks) | SYN+SRC+CI-current | — |
| B04 | Research assistant | Trace quote source/time/history | Auditable observation provenance | Fields exist; provider/handoff truth uncalibrated; live errors untyped | SYN+SRC+CI-current | P1-gate #1 |
| B05 | Shift worker on phone | Reopen tracked item | Persistent usable short session | Local-state + mobile-width paths exercised on current SHA | SYN+SRC+CI-current | — |
| C01 | Public-sector reviewer | Explain why a fare was shown | Trace source/age/status | Source fields exist; ~48% live error rate lacks typed cause for audit trail | SYN+SRC+CI-current | P1-gate #1 |
| C02 | Low-learning-cost user | Simple shared comparison | Core task without account workflow | Read-only comparison remains suitable; no new blocker found | SYN+SRC | — |
| C03 | Cautious purchaser | Follow source before decision | Clear mismatch boundary | README/UI warn observed/final unknown; booking fidelity not executed | SYN+SRC, NRV | P1-gate #1 |
| C04 | Interrupted long-flow user | Save watch → close/reopen | Recover without accidental scan | Browser-local persistence exercised on current SHA (CI smoke) | SYN+SRC+CI-current | — |
| C05 | SRE / service owner | Sustain configured radar coverage | Bounded, observable, feasible schedule | 48/6h demand vs 6/h capacity persists; live runs additionally lose ~half of attempts to errors; `batch_error` correctly reaches UI label via build adapter | SYN+SRC+CI-current | **P2 #6**; #1 live gate |
| D01 | Manager reading status | Inspect abnormal/coverage state | Status reflects real service quality | `worker.status` batch semantics verified through `build.mjs` label injection (no gap); production status currently dominated by error batches | SYN+SRC+CI-current | **P2 #6** + #1 |
| D02 | PM / audit operator | Trace task → observation → cadence | Reconstruct progress and coverage | Leases/receipts trace tasks; configured throughput cannot meet stated cadence, and measured error rate worsens it | SYN+SRC+CI-current | **P2 #6** + #1 |
| D03 | IT admin | Deploy/rollback | Safe deterministic deployment | Fail-closed wrangler defaults + bounded prepare-config remain; locks absent on main | SYN+SRC | P2 #2 |
| D04 | Cost-sensitive operator | Run scheduled collection under cap | Cap bounds real provider spend | 6/h task cap holds, but dormant Fli path could issue up to ~12 HTTP attempts/task (top_n=3 × 3 retries) if enabled — outer budget doesn't bound requests | SYN+SRC | **P2 #6** + P2 #8 contract gap |
| D05 | Compliance reviewer | Inspect credentials/data boundary | No traveler/secret leakage | Dedicated keys/redirect refusal/stripped provider env remain; vendored MIT code properly attributed; production secrets not inspected | SYN+SRC, NRV | — |
| E01 | Office desktop user | Browse/filter quotes | No CLI needed | Desktop 1440 path executed on current SHA via CI smoke | SYN+SRC+CI-current | — |
| E02 | Large-text desktop user | 200% zoom/detail | Core content remains usable | No new source blocker; 200% zoom still unexecuted | SYN, NRV | — |
| E03 | Low digital confidence | Submit invalid filters then recover | Clear non-destructive error | Failure-state fixture executed on current SHA (CI smoke) | SYN+SRC+CI-current | — |
| E04 | Self-hoster following docs | Deploy from docs | Safe defaults and explicit writes | Collector fail-closed; offline suite now green on current SHA (was red in r2); npm install unpinned remains | SYN+SRC+CI-current+LOCAL | P2 #2 |
| E05 | Long-session reader | Compare many observations | No fake freshness | TTL/history bounds remain; real freshness constrained by #6 and ~48% live error rate | SYN+SRC+CI-current | **P2 #6** + #1 |
| F01 | Senior first-time mobile user | Find one quote | Clear text/buttons | Mobile-width path exercised on current SHA; senior-specific runtime absent | SYN+CI-current, NRV | — |
| F02 | Low-vision user | Zoom/high contrast | Status not color-only | Text status exists; AT/contrast execution absent | SYN+SRC, NRV | — |
| F03 | Low motor precision | Tap mobile navigation/cards | Core path without precision | Narrow layout verified on current SHA; motor-target sizing unmeasured | SYN+CI-current, NRV | — |
| F04 | Memory-load sensitive user | Pause watch and return | Persistent labeled state | Local watch contract unchanged; resume execution covered by CI smoke persistence checks | SYN+SRC+CI-current | — |
| F05 | Assisted setup user | Helper configures; user browses | Routine use hides admin credentials | Read/admin separation remains; production/browser proof incomplete | SYN+SRC, NRV | — |
| G01 | Keyboard-only user | Filter/detail with keyboard/Escape | Reachable controls/focus recovery | Historical focus fixture pattern retained; current keyboard sweep not executed | SYN+SRC+CI-old, NRV | — |
| G02 | Screen-reader user | Navigate search/detail/status | Meaningful labels/structure | No screen-reader receipt at any SHA; no new deterministic blocker found | SYN, NRV | — |
| G03 | Color-vision-limited user | Interpret stale/error/deal | Text/icon semantics | Typed text states remain; rendered color-independence unexecuted | SYN+SRC, NRV | — |
| G04 | 200% zoom / narrow window | Explore/compare/detail | No core horizontal overflow | 360/390 no-overflow assertion ran on current SHA via CI smoke | SYN+CI-current | — |
| G05 | Slow/high-latency user | Refresh across 5xx/timeout | Preserve last data; truthful error | Retained-data fixture green on current SHA; live collector repeatedly errors and stops — truthful but degraded | SYN+SRC+CI-current | P1-gate #1 |
| H01 | Windows developer | Install/run locally | Supported predictable path | PowerShell path documented; deterministic dependency issue remains | SYN+SRC | P2 #2 |
| H02 | macOS developer | Install/run locally | Reproducible environment | Generic venv path remains; mutable graph remains | SYN+SRC | P2 #2 |
| H03 | Linux/CI noninteractive | Run checks from clean checkout | Deterministic unattended checks | Current-SHA Workers checks green; local receipt 79+23+10 green (node:sqlite needs Node≥22 as CI pins) | SRC+CI-current+LOCAL | P2 #2 (locks) |
| H04 | Cloudflare self-hoster | Enable bounded scheduled collection | Safe admission and sustainable capacity | Flag enables collection without #1 decision — now demonstrably live with ~48% task errors; opt-in fli adds unbounded-request caveat | SYN+SRC+CI-current | **P2 #6** + P1-gate #1 + P2 #8 |
| H05 | First-time maintainer | Reproduce/operate documented service | Docs and operating math agree | Cadence math still disagrees (#6); UPSTREAM_FLI.md gives clear vendored-code boundary; new fli deps pinned | SYN+SRC | **P2 #6** + P2 #2 |
| I01 | Duplicate/replay actor | Re-submit same result/seed | Idempotent replay / conflict protection | Receipt hash + query-key dedupe + replayed-accepted path remain source-confirmed | SYN+SRC | — |
| I02 | Process interruption | Restart during task | No lost/corrupt work | Lease/receipt recovery model remains; crash recovery not executed | SYN+SRC, NRV | — |
| I03 | Wrong input/file | Invalid route/date/plan | Fail before external work | Validators/bounds remain; exercised locally via collector dry-run | SYN+SRC+LOCAL | — |
| I04 | Timeout/429/5xx | Upstream/API failure mid-batch | Bounded failure and truthful degraded coverage | Stop-on-error + no-retry verified in source and *observed live*: every failed run ends after its first task error; error tasks re-due +1h erode already-insufficient throughput | SYN+SRC+CI-current | **P2 #6** + #1 |
| I05 | Partial success then retry | One accepted task then later failure | Preserve success; safe later recovery | Receipts/leases remain; 3/2/1 runs show accepted-then-error ordering preserved | SYN+SRC+CI-current | — |
| J01 | Large matrix/history | Sustain all configured routes | Bounded work without silently missing target | 48-route matrix exceeds 6/h sustainable capacity; measured error rate pushes real revisit well past 8h | SYN+SRC+CI-current | **P2 #6** |
| J02 | Concurrent operators | Claim same due task | Single owner/bounded concurrency | Conditional lease update remains; concurrency runtime absent | SYN+SRC, NRV | — |
| J03 | Long-running operation | Run schedule for days | Sustainable resource/cadence envelope | All 12 recorded runs on this SHA: 11 red, 1 green; sustainable envelope not demonstrated live | SYN+SRC+CI-current | **P2 #6** + #1 |
| J04 | Security/privacy-sensitive user | Inspect shortest sensitive path | Least privilege/no credential leak | Dedicated role keys, stripped subprocess env, redirect refusal remain; vendored engine inherits upstream trust surface — pinned deps + verbatim provenance recorded | SYN+SRC, NRV | — |
| J05 | Expert user / automation | Use shortest supported automated path | Automation obeys same safety/capacity contract | `RADAR_PRIMARY_PROVIDER` selector is a clean opt-in, but choosing `fli` bypasses the request-budget intent (expansion+retries); capacity arithmetic unchanged | SYN+SRC | **P2 #6** + P2 #8 |

## Ten-dimension coverage summary

1. **First-use/first success:** README/UI onboarding re-read; current-SHA CI browser smoke now covers desktop/narrow onboarding paths; public hosted availability still NRV.
2. **Core task:** read-only quote exploration is source- and smoke-verified at current SHA; live quote fidelity remains #1, now with measured ~48% live task errors.
3. **Error recovery:** validators, receipts, leases, stop-on-error, replay dedupe rechecked — and this time *observed* failing live in the intended fail-closed shape (red run, error receipt, +1h re-due).
4. **Data/security:** role-separated keys, redirect refusal, stripped provider env, fail-closed wrangler defaults remain; vendored MIT code carries attribution; no production-secret claim.
5. **Observability:** typed batch states verified end-to-end (`store.mjs` → `build.mjs` label injection → UI); live `batch_error` state is truthful; error *type* granularity remains the gap inside #1.
6. **Accessibility/device:** current-SHA receipts now exist for 360/390 overflow, dialogs, failure states; AT/screen-reader/200%/keyboard sweeps remain NRV.
7. **Performance/cost:** #6 capacity deficit persists on main; live evidence shows effective coverage below the 8h floor; dormant Fli path would multiply requests per task if enabled.
8. **Maintainability:** #7 validation defect fixed and green on current SHA; #2 lockfile gap remains pending PR #9; vendored-tree sync process documented.
9. **Failure injection/recovery:** no destructive/provider injection performed; production provides 11 real failure receipts whose per-task cause is unexposed by design.
10. **Trust:** #1 remains the admission/calibration blocker — now strengthened by actual degraded-source evidence; no booking or purchase claim is made.

## Issue writes / dedupe / regression status

- **Created:** none. This worker's authorization covers the report commit + PR only; Issue creation/mutation is outside the granted actions.
- **Reused, not duplicated:** #1 (evidence upgraded), #2, #6 (PR #9 pending), #8 (phase-1 residual gap).
- **Verified fixed:** #7 (closed; green suite on inspected SHA).
- **Candidate for owner disposition:** `normalize()` "offers-but-none-valid → error" outcome conflation — recorded inside #1's typed-outcome scope, not separately filed.
- **Umbrella:** #5 retained for round summary/state.
- No previously closed finding was confirmed to recur; nothing was reopened.

## HEAD / change check

The inspected product SHA is `6228138337f950cb6399088c4f814f27a518e29e`. The Issue write does not modify repository HEAD. This report commit is audit-only and must not be interpreted as a product fix or new runtime validation. If product code/config changes after this report — including merging PR #9 — the affected scenarios must be re-run against that new product SHA.

## CLEAN accounting

Status: **NOT CLEAN — 0/2 qualifying rounds**.

Reasons:
- P2 #6 and P2 #2 remain open and STILL_REPRODUCIBLE at the inspected SHA (remediation PR #9 is open but unmerged);
- #1's admission gate is unmet and now carries negative runtime evidence: ≈48% of attempted provider tasks errored across all 12 recorded current-SHA scheduled runs with untyped causes;
- #8 phase-1 residual contract gap (request budget vs provider-internal attempts) remains SOURCE_CONFIRMED;
- required runtime evidence remains incomplete: typed per-task error causes, booking-handoff fidelity, AT/200%/keyboard paths, and public deployment availability.

Round 3 is a complete 50/50 synthetic re-review of the fixed A01–J05 scenarios for this changed product SHA, but it is **not a qualifying CLEAN round**. The qualifying streak stays 0/2.

## Next verification

1. If PR #9 lands, re-run the capacity-affected personas (C05, D01, D02, D04, H04, H05, I04, J01, J03, J05) against the merge SHA and preserve a fresh scheduled-run receipt before crediting the new cadence.
2. Resolve #1 per its acceptance criteria: a bounded, typed-outcome calibration run — the current ~48% error signature makes this more urgent, and per-task error typing (or the normalize() empty-vs-error candidate above) is the cheapest first cut at cause.
3. Complete #8's remaining gates (request-budget bounding, calibration receipt) before any `RADAR_PRIMARY_PROVIDER` switch; keep the provider dormant until then.
4. Land #2's lock graph (PR #9 covers it) so `npm ci`/locked pip installs become the enforced path.
