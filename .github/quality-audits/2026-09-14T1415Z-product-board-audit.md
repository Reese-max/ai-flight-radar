# AI Flight Radar — Product Board Incremental Audit

Audit time: 2026-09-14T14:15Z  
Inspected product SHA: c6c6cdd3aff05cb202899311ab2698ce5ae6fb7d  
Previous product-board report: 2026-09-12-2215-product-board-audit.md  
Rules: Issue Quality v2, autodev-ng blob 8167e10798071d2276addaff6b201c6b0e904a2a  
Evidence labels: SOURCE_CONFIRMED / EXECUTED_RECEIPT / STATIC_INFERENCE / UNKNOWN

This is an incremental product-board audit. It does not replace the fixed A01–J05 audit and does not count toward CLEAN. The 50 personas below are synthetic model simulations, not 50 people, market research, incident counts, or prioritization evidence.

## Executive Summary

The product changed materially after the previous board audit. Commits ad95e723 and dad2ef4 added an hourly collector and monthly task seeding. Commit c6c6cdd restored a fail-closed checked-in Wrangler default, but deployment may inject CF_RADAR_COLLECTOR_ENABLED and the same repository variable gates scheduled execution.

The earlier board conclusion was: do not enable scheduled/public collection until Issue #1 has a current, bounded quote-fidelity calibration receipt and a BUILD/NARROW/BLOCK decision. Issue #1 remains open, its comments contain no later calibration evidence, repository search found no committed calibration protocol/report, and the three post-board product SHAs have no associated Actions runs or commit statuses. The commit message for ad95e723 says a provider was validated end-to-end, but a commit message is not a reproducible calibration receipt and does not establish current deployment state.

Disposition: REGRESSION at the release-contract level, with current production exposure UNKNOWN. This maps to existing Issue #1; no duplicate Issue is created. Under Issue Quality v2 the delta is calibrated as VALIDATION_GAP / P2 / NEEDS_REVIEW / auto_implementation=false. It does not assert that any fare is wrong, any user was misled, the schedule actually ran, or that a purchase/cost incident occurred.

Decision remains INVEST / SIMPLIFY: keep the local evidence-first price radar, pause further automation expansion, and require a small machine-checkable calibration decision before a collector can be enabled.

## Inventory and Scope

The owner listing was repaginated in this run: 42 owned repositories, 3 archived, 39 owned and unarchived. Change triage found no product/config change after 2026-09-14T11:15Z; newer commits were audit/radar documentation only. The higher-value unresolved delta was ai-flight-radar product work after its last product-board audit, so this run inspected that repository deeply rather than pretending to re-audit all 39 products.

No portfolio ranking is produced here because a complete same-depth portfolio cycle was not performed.

## Project Discovery

### Product

AI Flight Radar is a Taiwan-origin fare observation and comparison product. It stores price snapshots, compares like-for-like queries, exposes stale/unknown states, and can run as FastAPI/SQLite or a Cloudflare Worker/D1 deployment. Its key value proposition is evidence discipline: it should not label a fare a deal until comparison, freshness, route, passenger, cabin, directness, and source conditions are explicit.

### Users and core task

Primary users are budget-sensitive Taiwan travelers and an operator maintaining bounded fare collection. The core task is: define a flight query, collect current observations, compare them to a defensible history, and decide whether to investigate the fare further. It is not a booking or purchase product.

### Maturity

- SOURCE_CONFIRMED: the repository contains UI, API, Cloudflare/D1 code, tests, Docker paths, bounded collector code, and scheduled workflow definitions.
- SOURCE_CONFIRMED: only fast-flights 3.1.0 / Google Flights-derived data is implemented as a live provider.
- SOURCE_CONFIRMED: the checked-in Cloudflare config defaults COLLECTOR_ENABLED to false and uses a placeholder D1 ID.
- SOURCE_CONFIRMED: deploy preparation can replace the default with CF_RADAR_COLLECTOR_ENABLED.
- SOURCE_CONFIRMED: collector.yml runs hourly when the repository variable is true; seed.yml can submit six monthly route/date tasks when its variable is true.
- SOURCE_CONFIRMED: the collector is limited to three tasks per run, stops after an upstream error, disables notifications, strips most environment variables, refuses redirects, and uses dedicated collector/admin credentials.
- EXECUTED_RECEIPT: no Actions runs or commit statuses are associated with ad95e723, dad2ef4, or c6c6cdd through the connected GitHub evidence path.
- UNKNOWN: current GitHub variable values, current Worker deployment flag, D1 task inventory, whether an hourly run executed, live quote agreement, and booking-handoff fidelity.

### Maximum weakness

The automation enablement path is controlled by a boolean repository variable, not by a current passing calibration decision. This allows operations to move from UNKNOWN source fidelity to scheduled public-facing observations without satisfying the explicit product gate already tracked in #1.

## Change Delta Since the Previous Board

1. ad95e723 added the hourly collector workflow and temporarily committed a live D1 identifier plus COLLECTOR_ENABLED=true.
2. dad2ef4 added monthly task seeding; generated tasks self-reschedule every six hours until departure.
3. c6c6cdd correctly restored the checked-in safe default and placeholder database ID.
4. c6c6cdd also made deployment inject the same repository-level collector flag, so the gate remains operationally convenient but does not require a calibration receipt.
5. README and deployment guidance still emphasize disabled-by-default collection and prior calibration, while the new workflows can operationalize the collector. Documentation and executable controls are not yet one coherent release contract.

## Competitive Intelligence

Official pages were rechecked on 2026-09-14.

| Product / workflow | Target and value | First success / tracking | Reliability and price truth | Automation / mobile / integration | Business and openness | Board classification |
|---|---|---|---|---|---|---|
| AI Flight Radar | Taiwan-origin evidence-first observers | Self-host/setup; structured query and stored history | Strong typed local logic; one uncalibrated live source | New bounded schedule; responsive web; no booking | Public source without project license; operator-funded | DIFFERENTIATOR if calibration gates automation |
| Google Flights | Broad travelers | Immediate search, filters, price graph, tracked routes/dates | Says prices change and booking price may differ | Email tracking, flexible “Any dates”, web/mobile | Closed, free consumer distribution | MUST MATCH transparency/freshness, not breadth |
| Skyscanner | Comparison shoppers | Search then save/alert | Explicit snapshot/mismatch support | Alerts and broad partner handoff | Closed marketplace/referral model | MUST MATCH mismatch semantics |
| KAYAK | Planning and comparison users | Conventional results plus Ask AI refinement | Forecasts are not guarantees | Alerts, conversational refinement, app/web | Closed travel marketplace | SHOULD BE BETTER through inspectable evidence |
| Hopper | Mobile-first price-timing users | Route watch and prediction | Prediction confidence and limits explained | Notifications and app workflow | Closed app/commerce model | DO NOT COPY purchase/fintech breadth |
| Airline direct sites | Travelers ready to buy | Final inventory and checkout | Closest booking truth, still dynamic | Account/app varies | Closed provider channel | MUST MATCH safe handoff/reconfirmation |
| Spreadsheet/manual checks | Power users and auditors | Slow manual logging | Transparent but error-prone and not scalable | No automation unless scripted | User-owned/open workflow | DIFFERENTIATOR: automate without losing auditability |

Official sources:
- Google Flights tracking: https://support.google.com/travel/answer/6235879
- Google Flights deal caveat: https://support.google.com/travel/answer/16497283
- Google Flights search and price freshness: https://support.google.com/travel/answer/2475306
- Skyscanner price help: https://help.skyscanner.net/hc/en-gb/categories/200368471-Prices
- KAYAK search guidance: https://www.kayak.com/c/help/search/
- Hopper predictions: https://help.hopper.com/en_us/about-our-price-predictions-Hy7cLt_Fv

Competitive gaps:
- MUST MATCH: a current source-health and booking-price discrepancy receipt before scheduled/public promise.
- SHOULD BE BETTER: make every displayed observation traceable to source state, query identity, age, and calibration decision.
- DIFFERENTIATOR: conservative history thresholds and typed UNKNOWN/STALE/PARTIAL outcomes.
- DO NOT COPY: booking, payment, accounts, broad destination content, opaque AI recommendation, or multi-provider expansion before source truth is established.

## Virtual Executive Board

These are multiple lenses from one model, not independent experts.

| Lens | Question / priority | Position |
|---|---|---|
| CEO | If only three things: calibration gate, observable scheduled receipt, then #2 reproducible builds. What not to do? | Do not add booking, more providers, or broader AI planning. |
| CPO | Can a traveler distinguish observation from bookable fare? | Keep source/age/mismatch language visible; collector convenience cannot weaken truth. |
| CTO | What control is smallest? | Require one versioned calibration decision artifact in deploy and collector preflight; no new service. |
| Staff Engineer | Is a boolean flag enough? | No. Reuse the existing #1 decision; fail closed if missing, stale, or BLOCK. |
| UX Lead | What does the user need? | “Observed at”, source health, and “recheck before booking”; no false real-time language. |
| UX Researcher | What remains unknown? | Whether target users understand the current evidence states; runtime/usability study remains pending. |
| Growth | Could limited beta help? | Minority opinion: yes, but only a named bounded research cohort with explicit UNKNOWN state. |
| CFO | Where can cost expand? | Monthly seeds self-reschedule; retain caps, stop rules, and operator-visible request counts. |
| Security/Privacy | Is credential handling bounded? | Dedicated keys, no redirects, stripped environment, and no traveler identity are positive; keep them. |
| QA | What proves release behavior? | An actual scheduled/manual Actions receipt plus replayed typed provider outcomes. |
| SRE | What should page an operator? | Last successful observation, source error class, task backlog, and stale calibration—without claiming availability. |
| Accessibility | What is established? | No new accessibility defect was executed or proven; retain mobile/AT runtime backlog. |
| Support | What ticket will recur? | “Why is this price different now?” needs a traceable observation and handoff explanation. |

Board disagreement: Growth prefers an early narrow beta. QA/SRE/CPO reject enabling recurring public collection on a commit-message claim alone. Resolution: a bounded research run is acceptable only as evidence acquisition; recurring enablement requires the #1 decision artifact and must not imply bookable-price accuracy.

## 50 Synthetic Personas

Baseline B01–B30 preserves the previous regression themes; exploratory E31–E50 rotates operator, edge, and switching cases. “Result” is simulated reasoning, not executed use.

| ID | Background / constraint | Goal and expectation | Core journey | Friction | Result | Suggestion / evidence |
|---|---|---|---|---|---|---|
| B01 | 22 student, mobile, limited budget | Find TPE–KIX fare | Search → inspect | Wants bookable truth | Partial | Show observation age and recheck |
| B02 | 31 office worker, desktop | Track NRT weekend | Define → wait | Schedule provenance unclear | Fail | Bind alert to calibrated collector |
| B03 | 45 parent, four travelers | Compare family total | Query party size | Lowest single price can mislead | Partial | Preserve passenger/currency identity |
| B04 | 67 retiree, low digital skill | Know whether to buy | Open detail | Evidence vocabulary is dense | Partial | Plain-language observed/not guaranteed |
| B05 | 28 backpacker, hostel Wi‑Fi | Avoid repeat scans | Reopen stored result | Source health unknown | Partial | Read cache with explicit staleness |
| B06 | 39 direct-flight-only user | Track direct routes | Set direct | Needs no silent widening | Success static | Keep exact query identity |
| B07 | 34 wheelchair traveler | Check practical itinerary | Inspect fare | Accessibility not assessed | Unknown | Runtime keyboard/AT test |
| B08 | 29 traveler with baggage | Compare final cost | Inspect offer | Baggage remains unknown | Fail | Do not infer; link to reconfirm |
| B09 | 52 price-sensitive couple | Spot real drop | Compare history | Insufficient live days | Partial | Keep no-deal until threshold |
| B10 | 26 first-time user | Understand empty state | Search | Empty vs outage unclear live | Fail | Typed provider outcomes |
| B11 | 41 power user | Audit observation | Open details | Wants receipt | Partial | Query/source/calibration IDs |
| B12 | 36 low-vision user | Use filters | Navigate | No executed AT evidence | Unknown | Keep runtime backlog |
| B13 | 24 flexible-date traveler | Find any cheap weekend | Natural language | Parser scope can drift | Partial | Review structured intent |
| B14 | 58 cautious traveler | Avoid stale fare | Open old result | Six-hour boundary helps | Success static | Preserve stale badge |
| B15 | 33 frequent flyer | Exclude airline | Set constraint | Support breadth uncertain | Partial | Type unsupported fields |
| B16 | 47 family planner | Compare multiple dates | Date matrix | Not a time series | Success | Keep distinction explicit |
| B17 | 20 student abroad | Use slow phone | Read current snapshot | Payload/latency unknown | Unknown | Measure, do not assume |
| B18 | 38 security-conscious operator | Protect keys | Run collector | Dedicated key is positive | Partial | Keep no redirect/env strip |
| B19 | 44 SRE | Know schedule worked | Inspect Actions | No runs/statuses for new SHAs | Fail | Require run receipt |
| B20 | 35 QA engineer | Reproduce release | Check workflow | Dependencies still mutable | Fail | Existing #2 |
| B21 | 30 casual traveler | Get alert | Save browser watch | No server notification | Partial | Do not mislabel local watch |
| B22 | 63 rural user, intermittent network | Reopen latest fare | Offline attempt | No PWA promise | Fail expected | Do not build before trust |
| B23 | 27 privacy-sensitive user | Avoid account | Use read-only UI | Local tracking fits | Success | Preserve no-account path |
| B24 | 49 travel agent | Verify handoff | Follow link | Booking comparison unmeasured | Fail | #1 manual handoff strata |
| B25 | 32 operator | Seed routes safely | Review plan → submit | Monthly six-route plan is bounded | Partial | Gate on calibration and budget |
| B26 | 37 cost owner | Bound provider use | Review schedule | Self-rescheduling extends lifetime | Partial | Expose task/request counters |
| B27 | 42 maintainer | Roll back | Rebuild prior graph | Mutable dependencies | Fail | #2 deterministic locks |
| B28 | 18 novice | Trust “deal” label | Open result | Source confidence unknown | Fail | Do not claim deal without receipt |
| B29 | 55 airline-direct loyalist | Confirm final price | Radar → airline | Extra handoff but safer | Success | Keep airline recheck |
| B30 | 40 incident responder | Classify provider error | Examine run | Error is collapsed in client summary | Partial | Preserve typed upstream outcome |
| E31 | 25 Okinawa traveler | Monthly watch | Seed → hourly scans | No current calibration decision | Fail | Block enablement absent PASS |
| E32 | 46 owner | Enable private beta | Set repo flag | Flag alone authorizes too much | Fail | Require explicit research mode/receipt |
| E33 | 31 Windows maintainer | Run subprocess | Execute collector | SYSTEMROOT/site fix is plausible | Unknown | Need actual executed receipt |
| E34 | 28 Linux maintainer | Reproduce collector | Clean env | PYTHONPATH derived at runtime | Unknown | Test clean hosted runner |
| E35 | 50 compliance reviewer | Verify source conduct | Inspect collection | Provider terms/rate evidence absent | Fail | Record authorized environment/limits |
| E36 | 34 traveler using JPY card | Compare TWD display | Search → handoff | Currency agreement unmeasured | Fail | Calibration stratum |
| E37 | 43 two-adult-one-child party | Validate party total | Search → book | Passenger fidelity unmeasured | Fail | Calibration stratum |
| E38 | 23 one-way traveler | Find single leg | Query | Monthly seed is round-trip-only | Partial | Do not broaden; type coverage |
| E39 | 61 traveler with fixed dates | Track exact fare | Alert | Google offers mature tracking | Switch | Product needs trusted evidence niche |
| E40 | 29 “any dates” traveler | Flexible tracking | Natural-language parse | Existing #4 is research only | Switch | Defer until #1 |
| E41 | 37 API consumer | Read source health | Call API | Current deployment unknown | Fail | Expose status without secrets |
| E42 | 45 support agent | Explain mismatch | Inspect receipt | No committed discrepancy sample | Fail | Store minimum comparison evidence |
| E43 | 33 SRE under upstream rate limit | Stop quickly | Scheduled batch | Stop-after-error is positive | Partial | Preserve typed RATE_LIMITED |
| E44 | 26 traveler during schema change | Avoid false quote | Search | Parser drift live unknown | Fail | BLOCK on parse change |
| E45 | 52 operator after restart | Avoid duplicate work | Resume tasks | Lease logic exists | Partial | Runtime restart evidence |
| E46 | 39 accessibility tester | Use mobile screen reader | Navigate results | Not executed | Unknown | Test without inventing defect |
| E47 | 24 developer contributor | Install project | Clean build | No project license/locks | Fail | #2 and #3 |
| E48 | 48 CFO | Review recurring cost | Monthly seed → hourly jobs | Lifetime cost not evidenced | Partial | Bounded plan plus counters |
| E49 | 30 skeptic | Prefer manual airline check | Compare now | Radar adds uncertainty | Switch | Win only through traceability |
| E50 | 36 product owner | Decide launch | Review evidence | Commit message is not gate receipt | Fail | Keep launch blocked pending #1 |

Persona synthesis groups one root cause: recurring collection can be authorized without a current calibration decision. Accessibility, performance, real price mismatch, and actual schedule execution remain UNKNOWN and are not converted into findings.

## Competitor Switching Test

Synthetic choices: AI Flight Radar 14/50 (28%), Google Flights 15/50 (30%), Skyscanner 9/50 (18%), KAYAK 6/50 (12%), Hopper 3/50 (6%), airline/manual workflow 3/50 (6%).

Reasons to choose this product: local/self-hosted control, Taiwan route focus, explicit history thresholds, and inspectable evidence. Reasons to switch: mature inventory, alerts, mobile polish, and greater confidence that the displayed search can be completed at booking. These are simulated scenario choices, not market share, survey responses, demand, revenue, or severity evidence.

## Red Team

1. Existing controls may be sufficient: both scheduled jobs require repository variables, the collector requires a dedicated key, and checked-in config is now fail-closed. Counterpoint: those are enablement controls, not evidence that source fidelity passed #1.
2. The commit message says end-to-end provider validation occurred. Counterpoint: it lacks protocol, denominators, discrepancy observations, retention rules, and BUILD/NARROW/BLOCK outcome. Treat as an operational claim, not reproducible proof.
3. No workflow runs on the new SHAs could be a connector/indexing limitation. Therefore this report records “no receipt returned,” not “Actions never ran” or a guessed billing/YAML cause.
4. A machine-readable gate could be over-engineering. Minimum alternative: one small versioned JSON/Markdown decision file and a preflight check, not a registry, database, or service.
5. The product may be only an owner-operated experiment. That lowers distribution risk but not cost/source-truth risk. A private research mode can remain available with explicit status.
6. The scheduled collector may never have been enabled because the variable could be false. Current production exposure therefore remains UNKNOWN; the regression is the missing calibration-dependent admission control.
7. Adding another provider would not validate the first provider and would increase terms, parsing, and cost surfaces. Reject.
8. Turning on alerts would amplify uncertain observations. Keep notifications off until source truth and delivery receipts are proven.

## Finding F1

Metadata:

- issue_quality_version: 2
- kind: VALIDATION_GAP
- severity: P2
- decision_priority: HIGH
- evidence: SOURCE_CONFIRMED; runtime state UNKNOWN
- triage: NEEDS_REVIEW
- auto_implementation: false
- regression: REGRESSION_CONTRACT / NEEDS_RUNTIME_VERIFICATION

Fingerprint: Reese-max/ai-flight-radar + scheduled Cloudflare collector enablement + repository flag true or deploy flag injection + recurring live observations can run without a current #1 calibration decision + boolean enablement is not coupled to calibration receipt.

Affected users: travelers relying on observed fares and the operator funding/maintaining collection.

Problem: post-board commits created recurring collection and seeding, but executable enablement checks only boolean variables and credentials. No committed current calibration decision is required.

Impact: the core evidence-first promise can be weakened by operational enablement. This does not prove a wrong fare or incident; it proves the release path cannot distinguish “authorized research run” from “calibrated recurring product.”

Existing workaround: keep both enable variables false and run only an explicitly authorized bounded research sample.

Minimum change: reuse #1. Add one small calibration decision artifact with expiry/source/version and BUILD/NARROW/BLOCK. Collector, deploy preparation, and seeding fail closed unless the current decision permits their exact mode. Avoid a new service/state machine.

Acceptance focus:
1. Default and absent decision remain disabled.
2. BLOCK, expired, source/version mismatch, or missing decision prevents deploy-time enablement and scheduled/seeding execution.
3. BUILD/NARROW includes explicit allowed routes, dates, rate/request budget, and expiry.
4. One actual workflow receipt shows the preflight steps and chosen decision without exposing secrets.
5. README/deployment text matches the executable contract.

Regression scenario: attempt to set CF_RADAR_COLLECTOR_ENABLED=true on a commit with no current passing calibration receipt. Expected: preflight fails before live provider work. Then use a synthetic passing receipt in a no-network fixture; expected: contract validation passes but no live request occurs. A real bounded calibration remains separately owner-authorized.

## Issue Mapping and Coordination

- UPDATED EXISTING ISSUE: #1, because the new source/config delta matches its existing fingerprint and changes its status materially.
- No new Issue: same root cause; creating a “collector gate” duplicate would split the calibration contract.
- #2 dependency locking remains STILL REPRODUCIBLE but has no new evidence requiring a comment.
- #3 licensing remains open research; no owner/legal decision appeared.
- #4 WatchSpec research is downstream of #1 and should remain deferred.

Before writing, all #1 comments were read; no unexpired competing lock was found. Open PR search returned none. Branches were main plus three older feature/fix branches; no github-1 or other active #1 implementation branch was present. autodev-ng search returned no matching active owner-status/heartbeat/GOAL. This audit acquired and re-read its own product-board lock before writing.

## Roadmap

NOW:
- Keep scheduled collector and seeding disabled unless #1 has a current permitted calibration decision.
- Preserve one actual workflow/preflight receipt and current source-health outcome.
- Continue #2 reproducible dependency work.

NEXT:
- Run the bounded #1 calibration with explicit authorization, request budget, typed outcomes, and booking-handoff comparison.
- Align README/deployment/operator status with actual Cloudflare modes.
- Only after #1 yields BUILD/NARROW, evaluate the smallest #4 WatchSpec experiment.

LATER:
- Second independent licensed provider, richer baggage/final-price semantics, or multi-user service—only with evidence and rights/cost boundaries.

DON'T:
- Automatic booking/payment, CAPTCHA/proxy evasion, unlimited recurring collection, invented historical fares, broad AI travel planner, native app, social feed, or multi-provider expansion now.

## Regression and Runtime Pending

- #1: REGRESSION_CONTRACT / STILL REPRODUCIBLE. The prior “collector correctly disabled pending calibration” assumption no longer holds as a complete release control. Current deployment and actual quote accuracy remain CANNOT_VERIFY.
- #2: STILL REPRODUCIBLE from source; no VERIFIED_FIXED claim.
- #3: CANNOT_VERIFY owner/legal decision.
- #4: DEFERRED downstream research; no implementation claim.
- Verified Fixed: 0.

Runtime pending:
- current GitHub repository variables and Worker deployment flag;
- actual collector/seed workflow execution;
- D1 task inventory and request counts;
- live source outcome taxonomy;
- booking link resolution and displayed-to-handoff price discrepancy;
- restart/lease behavior;
- mobile, keyboard, screen-reader, and low-bandwidth journeys.

## Decision Memo

What this product should become: a small, Taiwan-focused, evidence-first fare observation radar whose automation is subordinate to source truth.

Who it should serve: self-hosting operators and budget-conscious travelers willing to trade marketplace breadth for transparent query identity, history, freshness, and source status.

Why users choose it: local control, conservative “deal” logic, explicit UNKNOWN/stale behavior, and reproducible observation history.

Why users choose competitors: mature inventory, account-backed tracking, mobile polish, broader integrations, and clearer path from search to booking.

Biggest gap: a current, reproducible live source/booking-fidelity decision that is enforced by deployment and scheduling.

Potential moat: not “AI flight search,” but auditable claims—every observation and alert can explain what was queried, when, through which source state, against what history, and under which calibration.

Top three priorities: #1 calibration/admission; observable scheduled receipt; #2 reproducible builds.

What not to build: booking/payment, broad travel planning, accounts/social, native app, or additional providers before source trust.

Features worth removing/simplifying: no product feature must be removed now. Simplify the three collector flags/paths into one calibration-dependent enablement contract.

Biggest risks: source change, price mismatch, recurring request cost, misleading freshness, dependency drift, and licensing ambiguity.

Next experiment: an owner-approved, rate-bounded #1 sample with predeclared strata and a BUILD/NARROW/BLOCK output. Do not treat routine hourly collection as the experiment.

Recommendation: INVEST / SIMPLIFY. The collector implementation is useful, but its activation must follow evidence rather than substitute for it.

## Mandatory Accounting

- Total Findings: 1
- New Issues Created: 0
- Updated Existing Issues: 1 — Reese-max/ai-flight-radar #1
- Reopened Issues: 0
- Research Issues: 0 new; #1 remains the bounded research/validation tracker
- Duplicate Avoided: 9 persona/operational symptoms merged into #1
- Rejected/Deferred Findings: 12
  - wrong-fare incident claim: no executed mismatch evidence;
  - public collector definitely active: repository variable/deployment state unavailable;
  - Actions/YAML/billing cause: no job/log evidence;
  - production outage: not observed;
  - cost overrun: no request/cost receipt;
  - source terms breach: no legal/runtime evidence;
  - add second provider: does not resolve current source truth;
  - auto booking/payment: outside scope and high risk;
  - broad AI travel agent: feature bloat;
  - native/PWA rebuild: no validated need;
  - accessibility defect claim: no executed AT test;
  - performance defect claim: no executed latency/load test.
- Scope Narrowed: 1 — reuse #1 and a small decision artifact; no new framework/service/database
- Severity Calibration: 1 — delta tracked as VALIDATION_GAP/P2, not P0/P1 incident
- Issue Write Blocked: 0
- Report Write Blocked: 0
- SKIPPED_LOCKED: 0
- Verified Fixed: 0
- Distribution: P0 0 / P1 0 / P2 1 / P3 0 / NOT_ESTABLISHED 0
- Highest Priority: #1
- Finding Mapping: 1/1 PASS
- Portfolio CLEAN: not assessed; this incremental board cannot declare CLEAN.

No product source, CI/config, secrets, permissions, settings, branches, PRs, deployments, paid requests, provider writes, or implementation agents were changed or started by this audit.
