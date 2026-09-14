# AI Flight Radar — Fixed A01–J05 50-Persona Audit — Round 1

Audit run: `2026-09-14T14:25:53Z-ai-flight-radar-r1`  
Protocol: `Reese-max/autodev-ng/docs/portfolio-audit/2026-09-06-50-persona-audit.md`  
Protocol blob: `6e3499d6ef5be7e123050e1526946f6a40f99263`  
Issue Quality v2: `Reese-max/autodev-ng/docs/portfolio-audit/2026-09-14-issue-quality-v2.md`  
Quality-v2 blob: `8167e10798071d2276addaff6b201c6b0e904a2a`  
Default branch: `main`  
Inspected product SHA: [`c6c6cdd3aff05cb202899311ab2698ce5ae6fb7d`](https://github.com/Reese-max/ai-flight-radar/commit/c6c6cdd3aff05cb202899311ab2698ce5ae6fb7d)  
HEAD immediately before this audit write: [`855aed2bdce1ce5976ac25a8d21d720d0628fe41`](https://github.com/Reese-max/ai-flight-radar/commit/855aed2bdce1ce5976ac25a8d21d720d0628fe41), an audit-only child of the inspected product SHA.  
Umbrella: [#5](https://github.com/Reese-max/ai-flight-radar/issues/5)

> All A01–J05 results below are synthetic model simulations, not 50 human testers and not 50 independent validations. `SOURCE_CONFIRMED` means the current inspected source deterministically exposes the stated behavior. Runtime claims are made only where an actual execution receipt was read.

## Scope and evidence boundary

Round 1 read the current README, dependency manifests, Cloudflare deployment/collector/seed workflows, collector/task tooling, D1 store logic, browser smoke source, all repository Issues, full comments on the active reliability tracker, and all PR state. No open or closed PR was returned for this repository. The current product SHA has no workflow run or combined-status receipt returned by the connected GitHub evidence path, so the collector/seed/deploy delta is **not** called runtime-validated.

Historical execution evidence is narrower but real:

- [Quality checks run 34574732514](https://github.com/Reese-max/ai-flight-radar/actions/runs/34574732514) completed successfully on product SHA `f2dac801066edc8b6ed0107bf475cb562bdaceb7`. Its `tests` job actually completed install, `pip check`, compile, pytest, Node UI logic tests, Playwright Chromium install and `tests/browser_smoke.py`; its `container-smoke` job actually completed Docker build and the public-mode startup/auth/non-root smoke.
- [Cloudflare Workers checks run 34574732443](https://github.com/Reese-max/ai-flight-radar/actions/runs/34574732443) completed successfully on the same older SHA. The `validate` job actually completed offline Worker/collector tests, Worker build, local D1 migration, and the real local workerd/D1 smoke; the `prerequisites` job actually completed settings-presence validation without contacting Cloudflare.
- Those receipts predate the hourly collector, monthly task seeding and deployment-flag changes. They support only the paths present at `f2dac801`; they do **not** prove the current collector schedule, seed schedule, Cloudflare deployment flag, external Google Flights source, booking handoff, or current mobile/browser path.

No live provider query, booking, notification, Cloudflare mutation, deployment, destructive failure injection, paid request, product-code change, CI/config change, secret/settings change, merge, or repair worker was started by this audit.

## Existing finding disposition

### #1 — collector admission / quote-fidelity gate

Existing tracker: [#1](https://github.com/Reese-max/ai-flight-radar/issues/1). The latest v2 disposition is preserved rather than duplicated:

```yaml
issue_quality_version: 2
kind: VALIDATION_GAP
severity: P2
evidence: SOURCE_CONFIRMED
triage: NEEDS_REVIEW
auto_implementation: false
status: REGRESSION_CONTRACT / STILL_REPRODUCIBLE / NEEDS_RUNTIME_VERIFICATION
```

At `c6c6cdd3`, the checked-in Worker default is fail-closed, but repository variables can enable the hourly collector and monthly seeding, and deployment preparation can inject the same collector flag. The collector/seed/deploy preflight does not require a current calibration decision artifact. This is the same stable fingerprint already recorded in #1 and the 2026-09-14 product-board regression audit; this round does **not** create a duplicate or claim a new regression version. Current production flag values, schedule execution and quote/booking fidelity remain `UNKNOWN`.

### #2 — mutable build graph

Existing tracker: [#2](https://github.com/Reese-max/ai-flight-radar/issues/2). Status: `STILL_REPRODUCIBLE`, `SOURCE_CONFIRMED`, P2. `cloudflare/package.json` pins Wrangler directly but there is still no committed Node lock in the inspected source; Cloudflare checks run `npm install`. Python application/test manifests retain compatible ranges except `fast-flights==3.1.0`. Historical CI success proves one resolved graph worked on `f2dac801`; it does not make future/current resolution reproducible.

### Non-blocking tracked work

- [#3](https://github.com/Reese-max/ai-flight-radar/issues/3): licensing-boundary research, P3; not a P0/P1/P2 CLEAN blocker.
- [#4](https://github.com/Reese-max/ai-flight-radar/issues/4): WatchSpec competitive opportunity/research; not treated as an established current-product defect.

No additional independent P0/P1/P2 fingerprint passed Issue Quality v2 in this round.

## Fixed 50-persona scenario matrix

Legend: `SRC` = SOURCE_CONFIRMED on inspected SHA; `CI-old` = actual execution on `f2dac801`, useful only where unchanged; `NRV` = NEEDS_RUNTIME_VERIFICATION; `SYN` = synthetic persona reasoning.

| Persona | Goal / precondition / input | Scenario steps | Expected success condition | Observed on inspected product | Evidence | Severity / mapping |
|---|---|---|---|---|---|---|
| A01 | First-time mobile traveler; TPE→FUK | Open UI, filter, inspect a quote | Understand observed-vs-bookable status and finish on narrow screen | Responsive source/tests exist; current-SHA mobile execution absent | SYN+SRC+CI-old, NRV | — |
| A02 | Student unfamiliar with CLI | Follow README local setup then open UI | Short deterministic first success or clear blocker | README gives ordered venv/install/init/status/scan/server path; mutable graph remains | SYN+SRC | P2 #2 |
| A03 | CS student customizes/self-hosts | Clean checkout, install Python/Worker deps | Reproducible reviewed dependency graph | Compatible Python ranges and transient Node lock remain | SRC | P2 #2 |
| A04 | Budget traveler under time pressure | Inspect cheapest result and source age | Avoid false “deal” confidence | UI contract exposes observed/stale semantics; live quote/handoff fidelity uncalibrated | SYN+SRC, NRV | P2 #1 |
| A05 | Visual learner | Navigate explore→detail→compare→watch | Clear state transitions, no hidden live scan | Browser test source exercises those views and confirms search/read paths do not trigger scan | SYN+SRC+CI-old | — |
| B01 | Excel-skilled non-programmer | Use hosted/read-only UI | Complete compare without CLI | Product has public read-only UI contract; deployment availability is not established here | SYN+SRC, NRV | — |
| B02 | Junior engineer | Install and diagnose a clean checkout | Same graph as audited build; actionable errors | Install path is documented but resolution is mutable | SYN+SRC | P2 #2 |
| B03 | Designer wants reversible actions | Add/pause browser-local watch | State is explicit and reversible | Browser smoke source covers local watch save/pause and escaped labels; current-SHA execution absent | SYN+SRC+CI-old, NRV | — |
| B04 | Research assistant | Trace quote origin/time/history | Export/trace evidence enough to audit observation | Quote payload exposes source/time/query dimensions; provider truth and handoff discrepancy remain uncalibrated | SYN+SRC, NRV | P2 #1 |
| B05 | Shift worker on phone | Reopen tracked item in short session | Local state persists and mobile view stays usable | Browser-local scope is explicit; historical browser run passed narrow viewport, current-SHA rerun missing | SYN+SRC+CI-old, NRV | — |
| C01 | Public-sector user | Review a fare and later explain why it was shown | Audit trail distinguishes observation from final fare | Source/time/baseline fields are present; source calibration receipt missing | SYN+SRC, NRV | P2 #1 |
| C02 | Teacher / low learning cost | Use read-only comparison with another person | Core compare understandable without account workflow | Product explicitly is not full multi-tenant SaaS; shared read-only task remains applicable | SYN+SRC | — |
| C03 | High-risk cautious user | Follow source to purchase decision | Strong disclaimer and mismatch boundary | README/UI say observed, baggage/final availability require confirmation; actual handoff fidelity unmeasured | SYN+SRC, NRV | P2 #1 |
| C04 | Long-flow user | Save watch, close/reopen browser, resume | Local state is recoverable without causing server scan | LocalStorage watchlist is supported; current-SHA resume execution not available | SYN+SRC, NRV | — |
| C05 | SRE | Inspect status then enable bounded collector only when safe | Fail-closed admission and observable batch state | D1 exposes not_started/stale/error/ok/empty and bounded claims; calibration decision is not executable admission gate | SYN+SRC | P2 #1 |
| D01 | Manager | Read summary/abnormal state | Quickly distinguish no data, stale, error and success | Worker status model is typed; source correctness still depends on #1 | SYN+SRC | P2 #1 where external truth matters |
| D02 | PM | Trace work from task to observation | Responsibility/progress can be reconstructed | Leases, receipts, last_batch and task outcomes are source-visible; external workflow execution current SHA unknown | SYN+SRC, NRV | — |
| D03 | IT admin | Deploy/rollback from clean commit | Deterministic dependencies and safe configuration | Config defaults fail closed, but dependency graph is not fully committed | SYN+SRC | P2 #2 |
| D04 | Cost-sensitive operator | Run scheduled collection within bounds | Bounded request volume, stop on errors, no silent expansion | Workflow max 3/run; D1 max default 3 claims/hour; subprocess timeout; provider error stops batch | SYN+SRC, NRV for live schedule | P2 #1 only for enablement gate |
| D05 | Compliance reviewer | Inspect data/credential boundaries | No traveler identity/secret leakage and traceable source states | Dedicated keys, redirect refusal, stripped child env, browser key memory-only contract; no production inspection | SYN+SRC+CI-old, NRV | P2 #1 for source evidence |
| E01 | General office user | Browse current quotes and filters | No CLI required for consumer task | Responsive browser surface exists; public deployment/runtime not established | SYN+SRC, NRV | — |
| E02 | Desktop/large-text user | Zoom and inspect detail | Content remains usable at larger scale | Narrow/viewport regression source exists; no explicit current-SHA 200% executed receipt | SYN+SRC, NRV | — |
| E03 | Low digital confidence | Enter bad filter then recover | Inline error, no destructive side effect | Historical browser run actually exercised invalid min/max and Escape/focus restoration; unchanged UI intent, current-SHA rerun missing | SYN+SRC+CI-old | — |
| E04 | Excel-familiar self-hoster | Follow deployment docs | Clear safe defaults and no accidental cloud write | Local defaults disabled; deployment requires explicit config; reproducibility blocker remains | SYN+SRC | P2 #2 |
| E05 | Long-session reader | Compare many observations | Readable state labels and no fake fresh data | TTL/staleness and baseline-confidence semantics are source-defined; fatigue/readability runtime unmeasured | SYN+SRC, NRV | — |
| F01 | Senior first-time user | Find one quote on phone | Clear buttons/text and no hidden purchase implication | UI contract exists but no current-SHA senior/usability execution | SYN+SRC, NRV | — |
| F02 | Low-vision user | Zoom/use high contrast | Status not conveyed only visually | No source-confirmed blocking defect found; actual AT/contrast/200% behavior needs execution | SYN, NRV | — |
| F03 | Low motor precision | Tap mobile navigation/cards | Targets usable without precision | Historical 360/390 browser smoke is layout—not motor usability—evidence | SYN+CI-old, NRV | — |
| F04 | Memory-load sensitive | Pause a watch and return later | Persistent, labeled state | Browser-local watch state is explicit; resume execution current SHA not available | SYN+SRC, NRV | — |
| F05 | Assisted setup then daily use | Helper configures service; user later browses | Routine use does not expose admin key | Read paths are separated; browser API key is kept in memory and can be cleared | SYN+SRC+CI-old | — |
| G01 | Keyboard-only | Open/close filter and navigate detail | Focus returns and controls are reachable | Historical browser run actually exercised Escape and focus restoration; broader keyboard-only sweep current SHA missing | SYN+SRC+CI-old, NRV | — |
| G02 | Screen reader | Navigate search/filter/detail statuses | Labels/structure announced meaningfully | No executed screen-reader receipt was found; no deterministic source blocker established | SYN, NRV | — |
| G03 | Color-vision limitation | Interpret stale/error/deal states | Text/icon semantics, not color-only | Typed textual status exists in source; rendered color-independence needs runtime/accessibility verification | SYN+SRC, NRV | — |
| G04 | 200% zoom / narrow window | Explore→compare→detail at 360/390 | No horizontal overflow/core path usable | Historical browser job actually ran narrow widths and overflow assertions; current product changes are mostly collector/config but no current-SHA UI receipt | SYN+CI-old, NRV | — |
| G05 | Slow/high-latency network | Refresh while API fails | Preserve last data, label update failure, no fake zero result | Historical browser run actually exercised 503 refresh and retained cards; provider/network source path current SHA not executed | SYN+SRC+CI-old, NRV | P2 #1 for external source truth |
| H01 | Windows developer | Install/run local stack | Documented OS path and reproducible deps | PowerShell path documented; mutable graph remains | SYN+SRC | P2 #2 |
| H02 | macOS developer | Install/run local stack | Reproducible environment | Generic venv path documented; mutable graph remains | SYN+SRC | P2 #2 |
| H03 | Linux/CI noninteractive | Run checks from clean checkout | Deterministic noninteractive build/test | Workflows are noninteractive; historical jobs actually ran, but current graph is mutable and current SHA has no run | SRC+CI-old, NRV | P2 #2 |
| H04 | Cloudflare self-hoster | Deploy with collector disabled/enabled deliberately | Safe default plus admission gate before external collection | Checked-in default false; deployment can inject variable without calibration artifact | SYN+SRC | P2 #1 |
| H05 | First-time maintainer | Reproduce current repo from docs/CI | Single source of truth and deterministic graph | Docs are detailed; unresolved dependency reproducibility remains | SYN+SRC | P2 #2 |
| I01 | Duplicate click/replay | Re-submit same collector result/seed task | Idempotent same payload; conflict rejected | Receipt token+hash accepts identical replay and rejects changed payload; task insert dedups query key | SYN+SRC | — |
| I02 | Process/browser interruption | Restart service/browser mid-task | No lost/corrupted task; clear recovery | D1 task lease/receipt model and browser-local watch persistence are source-defined; crash recovery current SHA not executed | SYN+SRC, NRV | — |
| I03 | Wrong input/file | Invalid route/date/task/plan | Fail with explicit error before external work | Task/route/date/plan validators are bounded; implicit task plan cannot execute | SYN+SRC | — |
| I04 | Timeout/429/5xx | Provider/API failure during collection | Bounded timeout, no retry storm, truthful error | API timeout 20s, provider subprocess 90s, HTTP stops without retry; provider error stops batch. Real external behavior remains unknown | SYN+SRC, NRV | P2 #1 for calibration/typed external outcomes |
| I05 | Partial success then retry | One task succeeds then later task errors; rerun | Preserve accepted result; safe replay/retry | Receipts, leases, per-task next_run and stop-on-error are source-defined; executed failure injection current SHA absent | SYN+SRC, NRV | — |
| J01 | Large history | Query many observations / long baseline | Bound memory/query work and signal truncation | API limits 100/page, offset cap, baseline reads 721 and marks truncation non-confident | SYN+SRC | — |
| J02 | Concurrent operators | Claim same due task concurrently | One lease owner, budgets enforce bounds | Conditional task UPDATE plus lease ownership and D1 budgets are source-defined; concurrency runtime not executed current SHA | SYN+SRC, NRV | — |
| J03 | Long-running collector | Hourly schedule over days | Bounded per-run resources and no runaway retry | 10m workflow timeout, max 3 tasks, 90s provider timeout, hourly claim budget; actual scheduled longevity unknown | SYN+SRC, NRV | — |
| J04 | Security/privacy-sensitive | Inspect secrets/source link before using | No credential forwarding/leak; no false source-trust claim | Redirect refused, child env stripped, keys separated; provider fidelity remains uncalibrated | SYN+SRC, NRV | P2 #1 |
| J05 | Expert automation | Shortest path through CLI/CI/deploy | Scriptable, deterministic, safely gated | CLI/workflows are automatable; build graph mutable and collector enablement lacks calibration artifact gate | SYN+SRC | P2 #1/#2 |

## Ten-dimension disposition

1. **First understanding:** README clearly defines observation vs booking, local start, source count and deployment limits. No new P2 found.
2. **Core task:** source/data model supports query→snapshot→compare/detail; external quote and handoff fidelity remain blocked by #1.
3. **Error recovery:** leases, idempotent receipts, validation, stop-on-error and stale/error UI states are source-confirmed; current-SHA failure-injection runtime remains missing.
4. **Data security:** dedicated roles, redirect refusal, stripped search subprocess environment and memory-only browser API key are positive. No new security P0/P1/P2 was established.
5. **Observability:** `last_batch`, heartbeat age, typed worker state and quote timestamps exist; scheduled-run evidence for current collector/seed is missing.
6. **Accessibility/device:** historical Playwright receipt executed 360/390 widths and modal focus behavior on `f2dac801`; screen-reader/200%/current-SHA mobile evidence remains `NEEDS_RUNTIME_VERIFICATION`, not an established product defect.
7. **Performance/cost:** collection is bounded at workflow, server budget and subprocess levels. No paid request was executed. No independent cost bug was established.
8. **Maintainability:** #2 remains the material P2 because dependency resolution is not fully committed/reproducible.
9. **Failure injection:** static paths handle wrong input, duplicates, timeouts and provider errors conservatively; current collector/seed delta has no executed run receipt.
10. **Trust:** #1 remains the key gate: an operator flag can authorize recurring acquisition without a current machine-checkable calibration decision.

## Regression / fixes / Issues

- #1: `REGRESSION_CONTRACT / STILL_REPRODUCIBLE`; already confirmed and tracked before this fixed-persona run. No duplicate and no repeat notification fingerprint is created here.
- #2: `STILL_REPRODUCIBLE`; no relevant default-branch fix landed.
- New actionable P0/P1/P2 Issues: **0**.
- Updated existing actionable Issues in this round: **0**; repeating the already-current product-board evidence would add noise rather than material state.
- Reopened Issues: **0**.
- Umbrella #5 created after duplicate search; it is audit tracking, not an actionable finding.

## Runtime gaps required before CLEAN

`NEEDS_RUNTIME_VERIFICATION` remains for at least:

1. Owner-authorized, rate-bounded quote/source calibration and booking-handoff comparison required by #1, with no purchase and no bypass/evasion behavior.
2. Current/recent product SHA CI execution covering the current collector/seed/deploy delta and the existing unit/browser/workerd/container suites.
3. Actual scheduled/manual collector and seed execution receipt only if those paths are intended to be enabled; absence of a run is not treated as application failure.
4. Current UI narrow/mobile plus applicable keyboard/screen-reader/200%-zoom verification; old Playwright execution is useful evidence but does not establish every current accessibility path.
5. Reproducible clean-checkout dependency graph acceptance for #2.

## Round qualification and CLEAN

- Fixed personas covered: **50/50 A01–J05**.
- This is a complete synthetic scenario matrix for the inspected SHA, but **not a qualifying CLEAN round** because P2 #1 and #2 remain open and required runtime evidence is incomplete.
- Consecutive qualifying CLEAN rounds: **0/2**.
- Repository status: **NOT CLEAN**.
- Audit-only report commits do not count as product fixes and do not themselves invalidate product runtime receipts.

Before any future CLEAN claim, re-read HEAD and distinguish product/config/dependency/runtime changes from audit-only documentation. If #1/#2 fixes reach default branch, re-run the same affected persona scenarios and adjacent paths and classify them as `VERIFIED_FIXED`, `PARTIALLY_FIXED`, `STILL_REPRODUCIBLE`, `REGRESSION`, or `CANNOT_VERIFY/NEEDS_RUNTIME_VERIFICATION` rather than inferring from Issue/PR state alone.
