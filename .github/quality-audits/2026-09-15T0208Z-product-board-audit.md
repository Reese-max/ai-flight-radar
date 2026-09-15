# AI Flight Radar — Product Board Audit

Audit time: 2026-09-15T02:08Z  
Issue Quality v2 blob: 8167e10798071d2276addaff6b201c6b0e904a2a  
Default branch: main  
Inspected product SHA: bd983fb1051ac8a6eaf5c9b53e07df2e9f38485e  
Prior product baseline: 2ad341d548653fe0ba56490136c4e96daee1712e  
Evidence mode: repository source, GitHub Issues/branches/Actions logs, and current official public documentation. No browser, purchase, booking, deployment, Cloudflare dashboard, credential mutation, workflow rerun, or destructive failure injection was performed.

> The executive board and 50 personas below are one-model synthetic simulations. They are not independent experts, human research, market share, occurrence rates, or implementation authorization. They are separate from the fixed A01–J05 audit and do not advance its CLEAN streak.

## Executive Summary

AI Flight Radar remains an evidence-oriented Taiwan-origin fare observation product. The current product has a useful separation between observed quotes and final bookable truth, a bounded task collector, D1 receipts, source timestamps, safe defaults, and a now-optional Fli-derived provider.

Three current findings pass Issue Quality v2:

1. Issue #6: the full 48-route matrix cannot meet the six-hour revisit contract with six task claims per hour. This remains SOURCE_CONFIRMED at the inspected SHA.
2. Issue #7: the Cloudflare validation suite still asserts six tasks although plan() now creates 48. Actions run 34884994978 reproduces the exact 48 != 6 failure.
3. Issue #8: the newly landed Fli provider can perform one initial Google call plus three concurrent return-leg calls, and each call can retry three times. The outer six-task/hour budget therefore does not bound actual provider HTTP attempts when Fli is enabled. Safe default remains fast_flights, so this is not claimed as a current production incident.

The Fli phase-1 commit preserves MIT attribution, records upstream commit 121d34fea056dc513258958c4262cb5a4cc033c1, isolates the adapter, retains fast_flights as the default, pins three new runtime dependencies, and adds eight offline adapter tests. The Issue #8 receipt reports two bounded live checks, but this audit did not independently reproduce them and they do not satisfy the full representative calibration or booking-handoff gate.

Decision: INVEST / SIMPLIFY. Keep the product as a truthful, bounded Taiwan-origin fare evidence radar. Repair the validation contract, align route demand with bounded capacity, and complete a small versioned quote/handoff calibration decision before any provider-default switch. Do not build booking, payments, hotel search, multi-tenant travel SaaS, or a general MCP travel platform.

## Discovery

### Product and users

- Product type: local/self-hosted plus Cloudflare fare observation and price-history workbench.
- Primary users: Taiwan-origin budget travelers, careful self-hosters, and operators who want repeatable evidence rather than opaque cheap-flight claims.
- Core job: observe a stable query over time, show source/freshness/history, and tell the user when evidence is insufficient.
- Maturity: advanced prototype / owner-operated service. Real scheduled collection exists, but current-SHA admission and quote-fidelity evidence are incomplete.
- Largest strength: truthful unknown/stale semantics and bounded external effects.
- Largest weakness: the operating contract is split across route count, revisit interval, task budget, provider-internal calls, CI, and runtime receipts.

### Evidence ledger

| Evidence | Status | Meaning | Limit |
|---|---|---|---|
| README and Price Intelligence contract | SOURCE_CONFIRMED | Observed quote is not final bookable price | Documentation is not provider fidelity |
| plan() produces ORIGINS × DESTINATIONS | SOURCE_CONFIRMED | 4 × 12 = 48 tasks | Does not show live route age |
| successful/empty task next_run | SOURCE_CONFIRMED | Six-hour revisit intention | Errors and Actions delay increase age |
| collector workflow | SOURCE_CONFIRMED | Two runs/hour, max three tasks/run | Task count is not HTTP request count |
| run 34884994978 | EXECUTED_REPRODUCTION | 108 Node tests passed; Python failed at 48 != 6 | Later build/workerd steps were skipped |
| run 34904595793 | EXECUTED_REPRODUCTION | Three live tasks attempted; two observations and one error | Error cause and quote correctness unknown |
| Fli phase-1 receipt on #8 | SOURCE_REPORTED | Two author-reported bounded live checks | Not independently rerun; no booking comparison |
| current head workflow/status query | CONFIRMED | No commit-bound Actions/status receipt was returned | No claim that tests failed or passed |
| Fli adapter/offline tests | SOURCE_CONFIRMED | Eight fixtures cover mapping and basic failure distinctions | Fixtures do not exercise vendored network/parser path |

### Change since prior board audit

- b8a543d changed collection to twice hourly and allowed a six/hour deployed claim cap.
- 2ad341d expanded seed planning to 48 routes.
- f1613c added fixed A01–J05 Round 2 evidence and Issue #6.
- bd983fb vendored Fli and added the optional FliCustomProvider.
- The default remains fast_flights; no repository source automatically switches production to Fli.
- No product fix for #6 or #7 is present at the inspected SHA.

## Competitive Intelligence

Sources checked 2026-09-15 UTC. Current pages without a published update date are marked current/UNKNOWN update date.

| Product/workflow | Target and value | Core/onboarding | Automation/API/mobile | Reliability and price truth | Open/pricing/distribution | Board classification |
|---|---|---|---|---|---|---|
| Google Flights | Mainstream travelers; broad search and booking handoff | Calendar, price graph, stops/airline/cabin filters | Any-dates tracking; desktop and mobile web | Google says calendar prices are updated about daily and booking completes at airline/OTA | Closed consumer service; free surface | MUST MATCH quote/final-price distinction; DO NOT COPY breadth |
| Skyscanner | Meta-search users comparing many providers | Search then provider handoff | Alerts and app ecosystem | Help says displayed prices estimate taxes/charges; provider price can still change | Closed marketplace/meta-search | MUST MATCH transparent handoff; DO NOT COPY marketplace |
| KAYAK | Search plus trip-management users | Multi-site comparison, saved searches | Price Alerts, Trips, iOS/Android | Prediction/alerts are decision support, not guaranteed fare | Closed commercial service | SHOULD BE BETTER in evidence trace; DO NOT COPY Trips suite |
| Hopper | Mobile-first prediction and booking | App-centered forecast and purchase flow | Push alerts and fintech-style add-ons | Prediction is probabilistic and commercial | Closed mobile commerce | DIFFERENTIATE with transparent evidence; DO NOT COPY checkout/fintech |
| punitarani/fli | Developers and AI clients needing programmatic Google Flights access | pip/CLI/Python/MCP | search_flights, search_dates, filters, HTTP/stdio MCP | Reverse-engineered endpoint; JSON output is documented experimental | MIT open source | Reuse narrowly behind adapter; MUST bound calls and schema |
| Airline/OTA direct | User ready to transact | Final provider page | Varies | Best available source for final availability and rules | Closed transaction channel | MUST MATCH reconfirm/handoff; not a replacement for history |

Official sources:

- Google Flights search: https://support.google.com/travel/answer/2475306
- Google Flights tracking: https://support.google.com/travel/answer/6235879
- Skyscanner prices, page dated 2026-03-26 in current help index: https://help.skyscanner.net/hc/en-gb/categories/200368471-Prices
- KAYAK search and alerts: https://www.kayak.com/c/help/search/
- Hopper predictions: https://help.hopper.com/en_us/about-our-price-predictions-Hy7cLt_Fv
- Fli repository and current README: https://github.com/punitarani/fli

### Capability decisions

MUST MATCH

- Explicit observation time, source, currency, route, dates, stops, and reconfirm-before-booking.
- Clear empty versus provider error versus stale/unknown.
- A sustainable, measurable refresh contract.
- A bounded provider-call budget, not merely a task-claim budget.

SHOULD BE BETTER

- Explain why a deal signal exists using the users own observation history.
- Expose degraded coverage instead of a generic healthy heartbeat.
- Keep provider changes reversible and compare calibration receipts by version.

DIFFERENTIATOR

- Taiwan-origin route focus with honest evidence thresholds.
- Local/owner-controlled collection and no fabricated demo fares.
- Typed receipts connecting task, source result, history, and alert decision.

DO NOT COPY

- Automatic booking, payments, hotel bundling, travel itinerary SaaS, broad social features.
- Opaque prediction badges without calibration.
- Unbounded flexible-date expansion.
- Fli MCP/CLI breadth inside the internal collector.
- More providers before the existing admission and capacity contracts are stable.

## Virtual Executive Board

This is a single-model multi-perspective exercise.

| Role | Priority | Question / minority view |
|---|---|---|
| CEO | #7 validation receipt, #6 capacity alignment, #1 quote/handoff calibration | Do not make Fli primary or expand travel commerce yet |
| CPO | Preserve fast first success and honest freshness | Minority: reduce the route matrix before raising capacity |
| CTO | One provider interface plus explicit request budget | Vendoring is acceptable only with a small patch surface |
| Staff Engineer | Derive tests from catalogs and budgets | A new scheduler/database is unnecessary |
| UX Lead | Show coverage/degraded status in plain language | Do not add dashboards before the underlying status is true |
| UX Researcher | Validate whether users act on history versus lowest-price snapshots | Synthetic preference cannot rank engineering work |
| Growth | Trust and repeat use depend on reliable alerts | Avoid acquisition work while provider truth is unsettled |
| CFO/Analyst | Measure provider calls per accepted observation | Request amplification can erase the intended cost cap |
| Security/Privacy | Keep child env stripped, no credentials in URLs, no auto-buy | Fli impersonation/retries must not invite bypass behavior |
| QA | Repair stale test; add actual vendored smoke and request-count fixture | Offline duck types alone do not validate the upstream parser |
| SRE | Treat 2/3 observed as degraded, not a successful batch | Six-hour coverage is impossible at current steady-state capacity |
| Accessibility | Preserve text status and schedule keyboard/screen-reader runtime | No accessibility defect is claimed without execution |
| Support | Distinguish no results, source error, stale, and not calibrated | Do not make users debug provider internals |

CEO three choices if resources are limited:

1. Restore a current-head validation baseline by fixing #7 without changing product behavior.
2. Resolve #6 by choosing route count, revisit objective, or explicitly authorized bounded capacity and assert the invariant.
3. Finish #1 with a small, versioned, expiring calibration receipt before any provider-default change.

Do not build: booking/payments, hotels, multi-tenant SaaS, a second scheduling framework, or a broad AI travel agent.

Minority opinion: the product may be more valuable with fewer routes and trustworthy cadence than with full 48-route breadth. Another minority view is to postpone Fli entirely until fast_flights calibration and capacity are complete.

## 50 Synthetic Persona Journeys

Thirty regression baselines and twenty rotating explorations. Evidence codes: SRC source-confirmed; RUN actual GitHub execution; SYN synthetic reasoning; NRV runtime needed. These IDs are not A01–J05.

| ID | Background / constraint | Goal and journey | Friction / result | Severity / suggestion / evidence |
|---|---|---|---|---|
| B01 | First-time mobile traveler | TPE to FUK, compare then open detail | Can understand observed price, but current mobile runtime absent | NRV; keep source/time near price; SYN+SRC |
| B02 | Budget traveler | Track one route for a month | Six-hour promise may not hold across 48 routes | P2 #6; align cadence; SRC |
| B03 | Time-pressured buyer | Pick cheapest direct flight | Final bookable price remains unverified | P2 #1; reconfirm gate; SRC+NRV |
| B04 | Low digital confidence | Use public read-only view | No account flow is a benefit | Pass source-level; preserve simplicity; SYN |
| B05 | New self-hoster | Install and run locally | Dependency graph is not fully locked | P2 #2; reproducible lock; SRC |
| B06 | Cloud operator | Deploy with safe defaults | Fli stays off by default | Pass boundary; retain fail-closed selection; SRC |
| B07 | SRE | Check six-hour coverage | Demand is 8 tasks/hour, plan is 6 | P2 #6; deterministic capacity invariant; SRC |
| B08 | Cost owner | Bound Google work | One Fli task may create up to four calls before retries | P2 #8; count actual calls; SRC |
| B09 | Security reviewer | Inspect child process credentials | Child env strips application/GitHub secrets | Pass source-level; runtime NRV; SRC |
| B10 | Privacy reviewer | Avoid traveler-profile persistence | Current task schema is route/date focused | Pass scoped path; production data NRV; SRC |
| B11 | Returning mobile user | Reopen saved watch | Browser-local persistence avoids account complexity | Pass source-level; browser NRV; SYN+SRC |
| B12 | Keyboard-only user | Filter and open detail | No current-head keyboard receipt | NRV; run existing smoke on current head; SYN |
| B13 | Screen-reader user | Hear price freshness and errors | Text semantics exist but AT not executed | NRV; retain typed status; SYN+SRC |
| B14 | Low-vision user | Zoom to 200 percent | Responsive intent documented, current rendering unknown | NRV; browser check; SYN |
| B15 | Limited motor precision | Tap mobile controls | No measured target-size evidence | NRV; do not claim defect; SYN |
| B16 | Slow network user | Load cached quotes | Read path can work without live search | Likely success; test throttled browser later; SYN+SRC |
| B17 | Intermittent network | Resume after failed provider call | Error reschedules; exact user recovery unclear | P2 #1/#6 context; expose degraded state; SRC |
| B18 | No-result route user | Search route with no offers | Empty is distinct from error in adapters | Pass fixture-level; live NRV; SRC |
| B19 | Rate-limited source | Scheduled batch hits upstream limit | Batch stops after error | Expected safety; status/root cause still coarse; SRC+RUN |
| B20 | Stale-price user | Returns after six hours | Stale filtering exists, cadence capacity does not | P2 #6; show coverage truth; SRC |
| B21 | Multi-airport traveler | Compare TPE/TSA | Catalog supports both but no combined itinerary | Within scope; do not expand silently; SRC |
| B22 | Family traveler | Wants multiple passengers | Current collector fixes adults=1 | Clear non-goal now; do not misrepresent; SRC |
| B23 | Direct-only traveler | Exclude connections | Both provider and normalize path enforce direct | Pass fixture-level; live NRV; SRC |
| B24 | One-way traveler | Wants one-way watch | Cloudflare task contract is round-trip | Not current core defect; document scope; SRC |
| B25 | Currency-sensitive user | Needs TWD | Settings and storage require TWD | Pass source-level; handoff currency NRV; SRC |
| B26 | Flexible-date traveler | Find cheapest four-day window | Current radar lacks bounded flexible-date path | Opportunity only; defer until core gates; SYN |
| B27 | Booking handoff user | Confirm exact itinerary | Generic Google source URL is not verified booking option | P2 #1; calibration/handoff; SRC+NRV |
| B28 | Price-history analyst | Compare like-for-like queries | Query identity and history thresholds exist | Strength; current live sample size unknown; SRC |
| B29 | Support agent | Explain one failed run | Summary shows one error but not typed cause | P2 #1 context; retain sanitized typed category; RUN |
| B30 | Maintainer | Change route catalog | Stale hard-coded six-task test breaks CI | P2 #7; derive invariant from catalog; RUN |
| X01 | RMQ-origin traveler | Expect fair refresh | Full matrix includes RMQ but capacity cannot meet target | P2 #6; choose truthful objective; SRC |
| X02 | KHH-origin traveler | Monitor KHH to Japan | Same capacity deficit | P2 #6; no special new issue; SRC |
| X03 | TSA-origin traveler | Compare city airport | Same capacity deficit | P2 #6; merge root cause; SRC |
| X04 | Rare route user | Track lower-volume destination | Queue order may delay cold routes | P2 #6; verify max age at runtime; SRC+NRV |
| X05 | Holiday traveler | Observe high-demand dates | Provider results may change quickly | P2 #1; no accuracy claim; SYN |
| X06 | Last-minute traveler | Needs actionable current fare | Six-hour TTL may be too weak for purchase | Not established; reconfirm at provider; SYN |
| X07 | Route catalog editor | Adds a destination | Fixed-number tests will recur | P2 #7; Cartesian invariant; SRC |
| X08 | Upstream schema-drift case | Fli returns malformed rows | Adapter rejects all-invalid results as error | Pass fixture-level; actual parser drift NRV; SRC |
| X09 | Partial malformed response | Some rows valid, some invalid | Valid rows survive; partial-loss visibility limited | P3 research backlog; do not open without impact; SRC |
| X10 | Scheduled operator | Reviews 2/3 observed run | Cannot know whether error was rate, parse, or route | P2 #1 context; typed receipt experiment; RUN |
| X11 | Monthly seeding operator | Seeds 48 tasks in two calls | Seed budget delay is explicit | Likely pass; deployment execution NRV; SRC |
| X12 | Capacity planner | Simulates a six-hour window | At least eight hours average at six/hour | P2 #6; arithmetic reproduction; SRC |
| X13 | Mobile large-text user | Uses status during commute | No current-head visual receipt | NRV; no fabricated accessibility issue; SYN |
| X14 | Reduced-motion user | Navigates price list | No motion-specific evidence | Deferred evidence backlog; SYN |
| X15 | zh-TW locale user | Wants local language/currency | Fli adapter passes zh-TW/TW/TWD | Author-reported live only; NRV; SRC |
| X16 | Airline-filter power user | Wants include/exclude airline | Fli supports it but radar contract does not | DO NOT COPY now; opportunity not defect; SRC |
| X17 | Baggage-sensitive buyer | Needs total trip cost | Product correctly marks baggage unverified | P2 #1/roadmap; no fake completion; SRC |
| X18 | Sixty-day explorer | Wants flexible date search | Fli search_dates is not integrated | Deferred until bounded experiment; SYN |
| X19 | Provider evaluator | Compare fast_flights with Fli | Only two author-reported Fli routes exist | NEEDS_EVIDENCE; paired bounded calibration; SRC_REPORTED |
| X20 | License maintainer | Update vendored Fli | Provenance and MIT copy exist | Pass source-level; verify byte identity in CI later; SRC |

## Competitor Switching Test

Pure synthetic scenario choice, not market share or survey evidence:

| Choice | Synthetic share |
|---|---:|
| Google Flights | 30% |
| AI Flight Radar | 28% |
| Skyscanner | 18% |
| KAYAK | 12% |
| Hopper | 6% |
| Fli / manual scripts | 6% |

Why users choose this product: owner control, Taiwan-origin focus, source/freshness/history, and honest unknown states.  
Why users switch away: Google/Skyscanner/KAYAK have broader inventory, flexible-date UX, alerts, mobile polish, and direct provider handoff.  
This simulated share is not used for severity or ROI.

## Red Team

1. Existing functionality already solves part of the problem: safe default fast_flights means Fli amplification is not currently active unless explicitly selected.
2. Smaller alternative to #6: reduce route breadth or lengthen cadence; a new scheduler is unnecessary.
3. Smaller alternative to #7: replace the fixed six with a catalog-derived invariant; do not change production behavior.
4. Alternative root cause for live one-error run is unknown. It may be provider response, route availability, or transient upstream behavior; do not attribute it to #6 or Fli.
5. The Fli live receipt is author-reported and covers two routes, not the representative Taiwan matrix or booking handoff.
6. Fli and fast_flights both depend on Google Flights-derived behavior; adding Fli is not automatically an independent source.
7. Vendoring hundreds of upstream files adds maintenance and security review surface. The moat is not owning a fork; it is truthful normalized evidence.
8. Flexible-date breadth can multiply requests. A bounded date plan must precede the feature.
9. Competitive parity with Google Flights is not plausible or desirable for this repository scale.
10. Synthetic persona preference is circular if used to justify roadmap priority; it is used only to enumerate scenarios.
11. A green offline fixture suite would not validate real Google schema, locale, currency, booking handoff, or Cloudflare scheduling.
12. Raising MAX_SEARCHES_PER_HOUR without explicit cost/traffic authorization would hide #6 by weakening a safety boundary.

## Findings and Issue Mapping

| Finding | Quality v2 | Fingerprint | Tracking action |
|---|---|---|---|
| 48 tasks cannot meet six-hour revisit at six claims/hour | BUG / P2 / SOURCE_CONFIRMED / NEEDS_REVIEW / auto=false | ai-flight-radar + seed/cadence + 48 tasks + 6h + 6 claims/hour + unavoidable deficit | Existing #6; no duplicate/update because its body already contains this exact evidence |
| Cloudflare test still expects six tasks | VALIDATION_GAP / P2 / EXECUTED_REPRODUCTION / READY_FOR_IMPLEMENTATION subject to owner authorization / auto=false | ai-flight-radar + Cloudflare plan test + 48-task product contract + hard-coded six + current CI failure | Existing #7; exact run and minimal repair already recorded |
| Fli internal expansion/retries escape outer task budget | BUG / P2 / SOURCE_CONFIRMED / NEEDS_REVIEW / auto=false | ai-flight-radar + RADAR_PRIMARY_PROVIDER=fli + round-trip search + top_n=3 expansion + three retries/call + task budget does not bound HTTP attempts | Existing #8 acceptance already requires no bypass; SKIPPED_LOCKED/concurrent because issue-loop-bot just landed bd983fb and posted its receipt |

Issue URLs:

- #6 https://github.com/Reese-max/ai-flight-radar/issues/6
- #7 https://github.com/Reese-max/ai-flight-radar/issues/7
- #8 https://github.com/Reese-max/ai-flight-radar/issues/8
- #1 https://github.com/Reese-max/ai-flight-radar/issues/1
- #2 https://github.com/Reese-max/ai-flight-radar/issues/2

No new Issue was created by this product-board run. This is complete mapping, not a candidate-only escape: all three passed findings already have open tracking objects. #8 was not mutated because a fresh external implementation handler had just written the product commit and receipt, so ownership was treated as active even without a formal marker.

## Priority and Roadmap

NOW

1. #7: restore a trustworthy current-head validation receipt using catalog-derived tests.
2. #6: choose a sustainable route/cadence/capacity contract without silently raising cost limits.
3. #1/#8: require a versioned calibration decision and bound actual provider HTTP attempts before enabling Fli.

NEXT

- #2: complete deterministic dependency resolution and supply-chain review, including vendored Fli.
- Add a small test that counts Fli HTTP attempts under success and retry scenarios.
- Report max route age/degraded coverage from real task state if #6 chooses to retain the full matrix.

LATER

- A paired, bounded fast_flights versus Fli calibration across representative Taiwan routes.
- Bounded flexible-date research only after call-budget and calibration gates pass.
- Booking-handoff evidence for selected itineraries, without booking automation.

DON'T

- Automatic purchase/payment/rebooking.
- Hotels, itinerary planning, social/community, native app, multi-tenant SaaS.
- A second scheduler, general provider registry platform, or MCP-first internal architecture.
- More Google-derived providers presented as independent source diversity.
- Raising traffic/cost limits merely to make the route matrix fit.

Order: SIMPLIFY → FIX → VERIFY → only then ADD.

## Regression Review

- #1 quote-fidelity/collector admission: STILL_REPRODUCIBLE / PARTIAL_RUNTIME_EVIDENCE. Live collection reached two observations, but quote correctness, booking handoff, representative strata, and expiring decision receipt are incomplete.
- #2 reproducible build: STILL_REPRODUCIBLE. Three new Fli dependencies are pinned, but the whole Python/Node graph is not yet represented by reviewed locks/hashes.
- #6 route capacity: STILL_REPRODUCIBLE at bd983fb.
- #7 stale test: STILL_REPRODUCIBLE at bd983fb; run 34884994978 is exact executed evidence.
- #8 phase 1: PARTIALLY_IMPLEMENTED / NEEDS_RUNTIME_VERIFICATION. Safe selection and provenance exist; actual-call budgeting, broader calibration, current-head CI, search_dates, and booking evidence remain incomplete.
- VERIFIED_FIXED: none.

Runtime pending:

- Current-head Quality and Cloudflare checks.
- Current-head scheduled collector receipt and per-provider typed errors.
- Actual route max-age distribution under the chosen #6 contract.
- Representative paired provider calibration with SHA, commands, dates, result schema, and booking handoff.
- Mobile/keyboard/screen-reader checks on current head.
- Verification that vendored source stays identical to recorded upstream and that transitive dependencies are reviewable.

## Decision Memo

What this product should become: a small, trustworthy Taiwan-origin fare evidence radar that explains what was observed, when, under which query, how it changed, and when the user must reconfirm.

Who it should serve: careful travelers and self-hosters who value repeatable evidence and bounded automation more than marketplace breadth.

Why users choose it: transparent history, local control, truthful unknown/stale states, and no fabricated fare data.

Why users choose competitors: broader inventory, mature flexible-date UX, polished mobile alerts, richer filters, and direct booking-provider handoff.

Biggest competitive gaps: live quote/handoff calibration, sustainable coverage, actual provider-call budgeting, and current-head execution receipts.

Potential moat: trustworthy query identity plus source/freshness/history/decision traceability for Taiwan-origin routes. The vendored provider is infrastructure, not the moat.

Top priorities: #7 validation, #6 capacity, #1/#8 admission and call budget.

What not to build: travel commerce, hotel/itinerary suite, multi-tenant SaaS, broad AI agent, native app, or another scheduling framework.

Features worth removing/simplifying: if the 48-route matrix cannot fit the owner-approved budget, reduce routes or relax cadence rather than hiding the deficit.

Biggest risks: reverse-engineered upstream drift, request amplification, false price confidence, mutable dependencies, and equating successful collection with bookable truth.

Next experiments:

1. Deterministic capacity simulation for one full revisit window.
2. Count actual Fli HTTP attempts under success, timeout, and retry.
3. Small paired provider calibration with explicit BUILD / NARROW / BLOCK decision and expiry.

Recommendation: INVEST / SIMPLIFY.

## Run Accounting

- Inventory: 42 Reese-max repositories; 39 unarchived; 3 archived.
- Deep product scope this round: ai-flight-radar at bd983fb; avatar-vfo fair-rotation check found only audit changes plus active PRs and was not rewritten.
- Total Findings: 3.
- New Issues Created by this run: 0.
- Updated Existing Issues: 0.
- Reopened Issues: 0.
- Research Issues: 0 new.
- Duplicate Avoided: 3, mapped to #6, #7, #8.
- Rejected/Deferred: 12 Red-Team directions, including automatic booking, hotels, SaaS, native app, additional provider breadth, unbounded flexible dates, broad MCP, second scheduler, synthetic-priority claims, blind cap increases, unsupported live-error attribution, and accessibility claims without runtime.
- Scope Narrowed: 1, #8 from broad provider/MCP expansion to safe optional adapter plus bounded validation gates.
- Severity Calibration: #7 treated as P2 VALIDATION_GAP rather than a proven P1 production failure; #8 as P2 opt-in contract defect rather than a production incident.
- Issue Write Blocked: 0.
- Report Write Blocked: 0 at preparation time.
- SKIPPED_LOCKED / concurrent: #8 issue mutation; fresh issue-loop-bot commit and receipt indicated active ownership.
- Verified Fixed: 0.
- Distribution: P0 0 / P1 0 / P2 3 / P3 0 / NOT_ESTABLISHED opportunities deferred.
- Highest Priority: #7 for trustworthy admission, then #6 for product operating truth; #1/#8 before provider enablement.
- Finding Mapping: 3/3 PASS.
- Portfolio CLEAN: not claimed. The fixed A01–J05 protocol remains NOT CLEAN and separate from this board simulation.
