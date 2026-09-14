# AI Flight Radar — Fixed A01–J05 50-Persona Audit — Round 2

Audit run: `2026-09-14T23:35:00Z-ai-flight-radar-r2`  
Protocol: `Reese-max/autodev-ng/docs/portfolio-audit/2026-09-06-50-persona-audit.md`  
Protocol blob: `6e3499d6ef5be7e123050e1526946f6a40f99263`  
Issue Quality v2: `Reese-max/autodev-ng/docs/portfolio-audit/2026-09-14-issue-quality-v2.md`  
Quality-v2 blob: `8167e10798071d2276addaff6b201c6b0e904a2a`  
Default branch: `main`  
Inspected product SHA: [`2ad341d548653fe0ba56490136c4e96daee1712e`](https://github.com/Reese-max/ai-flight-radar/commit/2ad341d548653fe0ba56490136c4e96daee1712e)  
Previous fixed-50 report: [Round 1](https://github.com/Reese-max/ai-flight-radar/blob/a886940a30edf3234cbd388d937896029da5524b/.github/quality-audits/2026-09-14T1427Z-50-persona-audit-round-1.md)  
Umbrella: [#5](https://github.com/Reese-max/ai-flight-radar/issues/5)

> All A01–J05 results are synthetic model simulations, not 50 human testers and not 50 independent validations. Persona identities, constraints and original success conditions are inherited unchanged from the governing protocol. `SOURCE_CONFIRMED` is static source evidence; runtime success/failure is claimed only where an actual execution receipt was read.

## Why Round 2 was required

Round 1 inspected product SHA `c6c6cdd3aff05cb202899311ab2698ce5ae6fb7d`. Current `main` is four commits ahead and materially changes the Cloudflare collector/seed operating contract: the collector schedule moved to twice per hour, deployed claim capacity became configurable, and task seeding expanded from six routes to the full 4×12 route matrix. Audit-only files in the same range are not treated as product changes.

No open pull request exists for the repository at this audit point. Existing product Issues #1–#5 and their comments were re-read; active product-board/persona-audit leases on the relevant tracker had been released before this round. Old feature branches exist but are not substituted for default-branch product truth.

## Evidence read

Current README, Cloudflare deployment/check/collector/seed workflows, `cloudflare/scripts/tasks.py`, `collector.py`, `prepare-config.mjs`, D1 store logic, current tests/tree, prior audit, current/open Issues, Issue comments, open PR state, branch state, and Actions runs/jobs were inspected.

### Current execution evidence

1. [Cloudflare Workers checks run 34884994978](https://github.com/Reese-max/ai-flight-radar/actions/runs/34884994978), exact inspected SHA `2ad341d...`, obtained GitHub-hosted runners. `prerequisites` succeeded. The `validate` job actually completed checkout, Node/Python setup, then **failed in `Offline Worker and collector tests`**; build, local migration and workerd smoke were skipped afterward. The connected evidence does not expose the failing assertion/log, so root cause remains `UNKNOWN`. This is a real validation regression receipt, not a zero-step Actions admission failure.
2. [Scheduled collector run 34904595793](https://github.com/Reese-max/ai-flight-radar/actions/runs/34904595793), exact inspected SHA, obtained a GitHub-hosted runner. Checkout, Python setup and provider dependency installation actually succeeded; **`Run a bounded batch` executed and failed**. The failing command output/root cause is not available through the connected evidence path. No inference is made that Issue #6 caused this run failure.
3. Earlier scheduled run [34871848369](https://github.com/Reese-max/ai-flight-radar/actions/runs/34871848369) completed successfully on `a886940a...`, the Round-1 audit-only child of the prior product state. It is historical evidence only; it does not validate current product SHA.
4. Historical Quality/Cloudflare runs on `f2dac801...` remain valid for the exact paths they executed, but they predate the current schedule/capacity/full-matrix changes and are not promoted to current-SHA proof.

No paid provider call, workflow rerun, deployment, purchase, notification, destructive failure injection, secret/settings change, product-code change, merge or repair worker was started by this audit.

## Finding disposition

### NEW P2 — #6 full-matrix demand exceeds the normal collector service rate

Tracker: [#6 — Align 48-route seed coverage with collector capacity](https://github.com/Reese-max/ai-flight-radar/issues/6)

```yaml
issue_quality_version: 2
kind: BUG
severity: P2
evidence: SOURCE_CONFIRMED
triage: NEEDS_REVIEW
auto_implementation: false
confidence: CONFIRMED
runtime_scope: production route ages UNKNOWN
```

Stable fingerprint: `Reese-max/ai-flight-radar + Cloudflare seeded route cadence + 48 active routes rescheduled every 6h + collector can claim at most 6 tasks/hour + advertised 6h rolling coverage is mathematically unsustainable`.

Current source creates the Cartesian product of four origins and twelve destinations = **48 tasks**. Successful/empty tasks are rescheduled for six hours later. Maintaining that contract requires `48 / 6 = 8` successful task claims per hour in steady state. The scheduled collector runs twice per hour and is hard-bounded to three tasks per run, i.e. **6 tasks/hour** planned capacity. Therefore the full configured matrix cannot satisfy a six-hour revisit cadence even under zero provider errors, zero workflow delay and zero contention; average revisit time is at least eight hours. Upstream errors worsen the deficit because a batch stops on error.

The smallest acceptable fix is to align an existing knob—route count, revisit interval, or explicitly authorized bounded service capacity—and add a deterministic capacity invariant/test. This issue deliberately does not require a new scheduler service, database, registry or queue framework.

Actual production route ages remain `UNKNOWN`; this source-level arithmetic defect is not presented as proof that a specific live route is already stale.

Affected fixed personas: C05, D01, D02, D04, H04, H05, I04, J01, J03.

### Existing #1 — collector admission / quote-fidelity gate

[#1](https://github.com/Reese-max/ai-flight-radar/issues/1) remains `VALIDATION_GAP / P2 / REGRESSION_CONTRACT / STILL_REPRODUCIBLE / NEEDS_RUNTIME_VERIFICATION`. Current code can enable scheduled collection through repository/deployment variables without a current versioned BUILD/NARROW calibration decision. The newly observed scheduled-run failure does not identify its own root cause and is not used to invent a new #1 cause.

### Existing #2 — reproducible dependency/build graph

[#2](https://github.com/Reese-max/ai-flight-radar/issues/2) remains P2 and SOURCE_CONFIRMED. Current Cloudflare workflows still use `npm install` and the committed source does not provide the full deterministic Node/Python resolution contract requested by the Issue. A failing current test run is not proof that mutable dependencies caused the failure.

### Current-SHA execution regression — evidence state only

Both current-SHA Cloudflare validation and scheduled collection have real executed failures. This is `CONFIRMED` as execution state, but the connected evidence cannot expose the failing assertion/command output. It is therefore recorded as `NEEDS_EVIDENCE / ROOT_CAUSE_UNKNOWN` rather than promoted into a guessed standalone P0/P1/P2 fingerprint. It blocks CLEAN/runtime claims until explained and re-run successfully or explicitly scoped.

## Fixed 50-persona scenario matrix

Evidence legend: `SRC` = SOURCE_CONFIRMED at inspected SHA; `CI-current` = actual run/job at inspected SHA; `CI-old` = real execution on an older SHA only; `SYN` = synthetic persona reasoning; `NRV` = NEEDS_RUNTIME_VERIFICATION.

| Persona | Goal / precondition / input | Steps / failure trigger | Expected success | Round-2 observation | Evidence | Severity / mapping |
|---|---|---|---|---|---|---|
| A01 | First-time mobile traveler, TPE→FUK | Open UI → filter → detail | Understand observed-vs-bookable state on narrow screen | Responsive source remains; no current-SHA mobile browser receipt | SYN+SRC, NRV | — |
| A02 | Docs-familiar, CLI-new student | README local setup | Fast first success or actionable blocker | Ordered setup remains; dependency reproducibility gap remains | SYN+SRC | P2 #2 |
| A03 | Git/CLI student self-hosting | Clean checkout/install/customize | Reproducible reviewed environment | Build inputs remain mutable | SYN+SRC | P2 #2 |
| A04 | Time-pressured traveler | Pick cheapest result quickly | Avoid false deal confidence | Observed/stale language exists; live quote/handoff fidelity remains uncalibrated | SYN+SRC, NRV | P2 #1 |
| A05 | Visual learner | Explore → compare → detail → watch | Clear state transitions | UI flow remains source-defined; current rendered path not re-executed | SYN+SRC, NRV | — |
| B01 | Non-programmer office user | Use hosted read-only UI | Compare without CLI | Public read-only contract exists; current deployment availability not proven here | SYN+SRC, NRV | — |
| B02 | Junior engineer | Install and diagnose | Deterministic install/errors | Mutable graph remains; current Cloudflare offline suite now actually fails for an unknown assertion | SYN+SRC+CI-current | P2 #2 + NEEDS_EVIDENCE |
| B03 | Designer / reversible actions | Add/pause browser watch | Explicit reversible local state | Browser-local watch contract unchanged; no current browser run | SYN+SRC, NRV | — |
| B04 | Research assistant | Trace quote source/time/history | Auditable observation provenance | Fields exist; provider/handoff truth remains uncalibrated | SYN+SRC, NRV | P2 #1 |
| B05 | Shift worker on phone | Reopen tracked item | Persistent usable short session | Local state contract remains; current mobile execution absent | SYN+SRC, NRV | — |
| C01 | Public-sector reviewer | Explain why a fare was shown | Trace source/age/status | Source fields exist; current external calibration receipt absent | SYN+SRC, NRV | P2 #1 |
| C02 | Low-learning-cost user | Simple shared comparison | Core task without account workflow | Read-only comparison remains suitable; no new blocker found | SYN+SRC | — |
| C03 | Cautious purchaser | Follow source before decision | Clear mismatch boundary | README/UI warn observed/final unknown; booking fidelity not executed | SYN+SRC, NRV | P2 #1 |
| C04 | Interrupted long-flow user | Save watch → close/reopen | Recover without accidental scan | Browser-local persistence source unchanged; restart path current SHA not executed | SYN+SRC, NRV | — |
| C05 | SRE / service owner | Sustain configured radar coverage | Bounded, observable and feasible schedule | 48 tasks × 6h requires 8/h, configured planned rate is 6/h | SYN+SRC | **P2 #6**; #1 also gates live trust |
| D01 | Manager reading status | Inspect abnormal/coverage state | Status reflects real service quality | Typed batch status exists, but nominal 6h matrix target is infeasible at 6/h | SYN+SRC | **P2 #6** |
| D02 | PM / audit operator | Trace task → observation → cadence | Reconstruct progress and coverage | Leases/receipts trace tasks, but configured throughput cannot meet intended full-matrix cadence | SYN+SRC | **P2 #6** |
| D03 | IT admin | Deploy/rollback | Safe deterministic deployment | Safe config boundaries remain; dependency graph still non-deterministic | SYN+SRC | P2 #2 |
| D04 | Cost-sensitive operator | Run scheduled collection under cap | Cap must also support stated coverage | 6/h is bounded but insufficient for 48/6h demand; raising cap requires explicit authorization | SYN+SRC | **P2 #6**; #1 live gate |
| D05 | Compliance reviewer | Inspect credentials/data boundary | No traveler/secret leakage | Dedicated keys/redirect refusal/stripped provider env remain; production secrets not inspected | SYN+SRC, NRV | — |
| E01 | Office desktop user | Browse/filter quotes | No CLI needed | UI contract intact; current public runtime not established | SYN+SRC, NRV | — |
| E02 | Large-text desktop user | 200% zoom/detail | Core content remains usable | No new source blocker; no current 200% execution receipt | SYN, NRV | — |
| E03 | Low digital confidence | Submit invalid filters then recover | Clear non-destructive error | Historical browser fixture exists; current UI not re-executed | SYN+SRC+CI-old, NRV | — |
| E04 | Self-hoster following docs | Deploy from docs | Safe defaults and explicit writes | Collector default is fail-closed, but current validation suite fails before build/workerd smoke | SYN+SRC+CI-current | P2 #2 / NEEDS_EVIDENCE |
| E05 | Long-session reader | Compare many observations | No fake freshness | TTL/history bounds remain; current full-matrix freshness contract now constrained by #6 | SYN+SRC | **P2 #6** where freshness depends on cadence |
| F01 | Senior first-time mobile user | Find one quote | Clear text/buttons | No deterministic source blocker found; current senior/mobile runtime absent | SYN, NRV | — |
| F02 | Low-vision user | Zoom/high contrast | Status not color-only | Text status exists; AT/contrast execution absent | SYN+SRC, NRV | — |
| F03 | Low motor precision | Tap mobile navigation/cards | Core path without precision | Historical narrow layout only; motor usability not executed | SYN+CI-old, NRV | — |
| F04 | Memory-load sensitive user | Pause watch and return | Persistent labeled state | Local watch contract unchanged; resume execution absent | SYN+SRC, NRV | — |
| F05 | Assisted setup user | Helper configures; user browses | Routine use hides admin credentials | Read/admin separation remains; production/browser proof incomplete | SYN+SRC, NRV | — |
| G01 | Keyboard-only user | Filter/detail with keyboard/Escape | Reachable controls/focus recovery | Historical focus fixture exists; current keyboard sweep absent | SYN+SRC+CI-old, NRV | — |
| G02 | Screen-reader user | Navigate search/detail/status | Meaningful labels/structure | No current screen-reader receipt; no new deterministic blocker found | SYN, NRV | — |
| G03 | Color-vision-limited user | Interpret stale/error/deal | Text/icon semantics | Typed text states remain; rendered color-independence unexecuted | SYN+SRC, NRV | — |
| G04 | 200% zoom / narrow window | Explore/compare/detail | No core horizontal overflow | Historical 360/390 smoke exists on old code; current receipt absent | SYN+CI-old, NRV | — |
| G05 | Slow/high-latency user | Refresh across 5xx/timeout | Preserve last data; truthful error | Historical retained-data fixture exists; current external collector run failed but root cause unknown | SYN+SRC+CI-old+CI-current, NRV | P2 #1 / NEEDS_EVIDENCE |
| H01 | Windows developer | Install/run locally | Supported predictable path | PowerShell path documented; deterministic dependency issue remains | SYN+SRC | P2 #2 |
| H02 | macOS developer | Install/run locally | Reproducible environment | Generic venv path remains; mutable graph remains | SYN+SRC | P2 #2 |
| H03 | Linux/CI noninteractive | Run checks from clean checkout | Deterministic unattended checks | Current Cloudflare suite actually executes and fails in offline tests; exact assertion unavailable | SRC+CI-current | P2 #2 / NEEDS_EVIDENCE |
| H04 | Cloudflare self-hoster | Enable bounded scheduled collection | Safe admission and sustainable capacity | Flag can enable collection without #1 decision; 48/6h workload exceeds 6/h planned capacity | SYN+SRC | **P2 #6** + P2 #1 |
| H05 | First-time maintainer | Reproduce/operate documented service | Docs and operating math agree | Seed says 6h rolling cadence while 48-task demand exceeds normal service rate | SYN+SRC | **P2 #6** + P2 #2 |
| I01 | Duplicate/replay actor | Re-submit same result/seed | Idempotent replay / conflict protection | Receipt hash and query-key dedupe remain source-confirmed | SYN+SRC | — |
| I02 | Process interruption | Restart during task | No lost/corrupt work | Lease/receipt recovery model remains; current crash recovery not executed | SYN+SRC, NRV | — |
| I03 | Wrong input/file | Invalid route/date/plan | Fail before external work | Validators/bounds remain; no new blocker found | SYN+SRC | — |
| I04 | Timeout/429/5xx | Upstream/API failure mid-batch | Bounded failure and truthful degraded coverage | Timeouts/no-retry exist; error stops batch, further reducing already-insufficient nominal throughput. Current scheduled batch actually failed but cause unavailable | SYN+SRC+CI-current, NRV | **P2 #6** + P2 #1 |
| I05 | Partial success then retry | One accepted task then later failure | Preserve success; safe later recovery | Receipts/leases remain; current failure-injection detail unavailable | SYN+SRC, NRV | — |
| J01 | Large matrix/history | Sustain all configured routes | Bounded work without silently missing target | 48-route matrix is now larger than 6h/6-per-hour sustainable capacity | SYN+SRC | **P2 #6** |
| J02 | Concurrent operators | Claim same due task | Single owner/bounded concurrency | Conditional leases/budgets remain; current concurrency runtime absent | SYN+SRC, NRV | — |
| J03 | Long-running operation | Run schedule for days | Sustainable resource/cadence envelope | Nominal demand exceeds service rate before provider failures; current scheduled run also actually failed for unknown cause | SYN+SRC+CI-current, NRV | **P2 #6** |
| J04 | Security/privacy-sensitive user | Inspect shortest sensitive path | Least privilege/no credential leak | Dedicated role keys and stripped provider subprocess env remain; no production credential inspection | SYN+SRC, NRV | — |
| J05 | Expert user / automation | Use shortest supported automated path | Automation obeys same safety/capacity contract | Seed/collector path is bounded but mathematically cannot satisfy its full-matrix 6h target at planned 6/h | SYN+SRC | **P2 #6** |

## Ten-dimension coverage summary

1. **First-use/first success:** README/UI onboarding re-read; current external/public success remains runtime-pending.
2. **Core task:** read-only quote exploration remains source-defined; live quote fidelity is still #1.
3. **Error recovery:** validators, receipts, leases and stop-on-error rechecked; exact current test/batch failure causes are unknown.
4. **Data/security:** role-separated keys, redirect refusal and stripped provider env remain; no production-secret claim.
5. **Observability:** typed worker/batch states remain, but #6 shows capacity truth is incomplete if the operator assumes every seeded route will hit six hours.
6. **Accessibility/device:** historical narrow/focus evidence retained only for older SHA; current screen-reader/200%/mobile paths remain NRV.
7. **Performance/cost:** new #6 is the material finding; bounded cost and feasible stated coverage must be consistent.
8. **Maintainability:** #2 remains; current offline suite failure blocks a current green validation receipt.
9. **Failure injection/recovery:** no destructive/provider failure injection was performed; current real scheduled failure is evidence of failure state only, not its root cause.
10. **Trust:** #1 remains the external-source admission/calibration blocker; no booking or purchase claim is made.

## Issue writes / dedupe / regression status

- **Created:** #6 (new independent P2 capacity fingerprint). GitHub returned and was read back as Issue #6.
- **Reused, not duplicated:** #1 and #2.
- **Umbrella:** #5 retained for round summary/state.
- **No new Issue for current Actions failures:** the runs prove execution failure but the connected evidence does not expose a stable root cause; Issue Quality v2 therefore keeps that evidence at `NEEDS_EVIDENCE` instead of inventing a root cause/severity.
- No closed finding was reopened in this round because no previously closed same-fingerprint defect was confirmed to recur.

## HEAD / change check

The inspected product SHA is `2ad341d548653fe0ba56490136c4e96daee1712e`. The Issue write does not modify repository HEAD. This report commit is audit-only and must not be interpreted as a product fix or new runtime validation. If product code/config changes after this report, the affected scenarios must be re-run against that new product SHA.

## CLEAN accounting

Status: **NOT CLEAN — 0/2 qualifying rounds**.

Reasons:
- new P2 #6 is open and resets the qualifying streak;
- existing P2 #1 and #2 remain unresolved/currently applicable;
- current exact-SHA Cloudflare validation and scheduled collector runs include real execution failures whose root causes are not yet established;
- required live provider/booking-fidelity, current mobile/accessibility and other applicable runtime evidence remains incomplete.

Round 2 is a complete 50/50 synthetic re-review of the fixed A01–J05 scenarios for this changed product SHA, but it is **not a qualifying CLEAN round**. No `CLEAN` status can advance from this report.

## Next verification

After a default-branch fix for #6 lands, re-run the same affected scenarios with the same inputs/success conditions and verify adjacent failure/backoff behavior. Do not call the cadence fixed solely from arithmetic/unit tests if the intended claim is that GitHub scheduled operation achieves it; preserve a current/recent actual scheduled execution receipt. Independently resolve or explicitly owner-disposition #1/#2 under their existing acceptance criteria, and obtain the required current runtime evidence before any CLEAN round can begin.