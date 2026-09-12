# Product Board Audit — AI Flight Radar

Audit date: 2026-09-12 (Asia/Taipei)

> Evidence policy: CONFIRMED means directly supported by repository code, GitHub metadata, or a named CI result. LIKELY means a bounded static inference. UNKNOWN means runtime, human, legal, or market validation is still required. Every persona and preference result below is synthetic simulation, not human research, market share, or a claim about production behavior.

## Executive Summary

AI Flight Radar is an early but unusually honest Taiwan-origin fare-observation workstation. Its defensible direction is not “more AI”; it is evidence-preserving fare monitoring: exact-query history, freshness, typed unknowns, bounded collection, and clear separation between an observed price and a purchasable final price.

The default branch has two passing receipts on commit f2dac801: [Quality checks](https://github.com/Reese-max/ai-flight-radar/actions/runs/34574732514) and [Cloudflare Workers checks](https://github.com/Reese-max/ai-flight-radar/actions/runs/34574732443). They cover unit/API/UI/browser-simulation/Docker and actual local workerd/D1 behavior. They intentionally do not contact the fare source, send real notifications, buy tickets, or prove production deployment.

Three distinct findings passed the Quality Gate. All three were written to GitHub Issues: [#1](https://github.com/Reese-max/ai-flight-radar/issues/1) live-source calibration, [#2](https://github.com/Reese-max/ai-flight-radar/issues/2) reproducible dependency graphs, and [#3](https://github.com/Reese-max/ai-flight-radar/issues/3) project/data licensing boundaries. Decision: **INVEST / SIMPLIFY**, but keep public scheduled collection gated until #1 yields BUILD or NARROW.

## Project Discovery

| Dimension | Assessment | Evidence status |
|---|---|---|
| Product type | Local-first fare observation, comparison, watchlist, and notification workstation with Python/FastAPI/SQLite plus a Cloudflare Worker/D1 port | CONFIRMED |
| Maturity | Early operational prototype with strong static/offline gates; not a proven public service | CONFIRMED |
| Target users | Taiwan-origin budget/flexible travelers and a technically capable self-hosting operator | LIKELY from copy/workflows |
| Core task | Observe route/date-specific fares, compare against same-query history, expose freshness/evidence, and notify only after a real delivery succeeds | CONFIRMED |
| Primary value | More trustworthy “is this cheap?” reasoning than an unqualified lowest-price scrape | CONFIRMED design; market value LIKELY |
| Largest weakness | One upstream wrapper and zero committed live-calibration receipt leave source health and booking fidelity UNKNOWN | CONFIRMED gap |
| Distribution state | Docker and guarded Cloudflare deployment paths exist; collector defaults off and no public runtime was verified in this audit | CONFIRMED / UNKNOWN runtime |

### Discovery evidence read

- README, requirements.txt, requirements-dev.txt, pyproject.toml, cloudflare/package.json, environment/deployment docs, price methodology, roadmap, provider/engine/store/worker/UI code, tests, workflow definitions, repository tree, recent commits, all Issues, all PRs, branches, and Actions runs.
- Recent product changes: price-integrity hardening (a5295fc0), responsive Figma UI (0798ce99), and guarded Workers/D1 port (f2dac801).
- Open and closed Issues before this audit: 0. Open PRs: 0. Existing quality-audit reports: 0.
- Historical feature/fix branches are not ahead of main. No github-* Issue branch exists.
- autodev-ng has tracked scan/sync/run/status and owner-* implementations, but host dataDir/status.json, heartbeats, GOALs, and leases are not in GitHub; live worker state is UNKNOWN.

### Evidence boundaries

- **CONFIRMED code/CI:** exact-query price keys; daily-weighted historical comparison; five-prior-day evidence gate; 90-day coverage gate; stale/unknown UI states; safe booking-link allowlist; bounded worker subprocess; fail-closed public writes; passing local workerd/D1 smoke.
- **LIKELY static inference:** users will value a transparent source-health receipt; one source increases fragility; unclear rights slow external adoption.
- **UNKNOWN / runtime:** current Google Flights-derived response success, provider throttling, schema drift, final booking price, mobile/assistive-tech usability, notification delivery, Cloudflare production state, real latency/load, and legal permissions.

## Competitive Intelligence

Public product information was checked on 2026-09-12. Pricing and feature surfaces can change.

| Product / alternative | Target user & value | Core / killer / onboarding / UX | Automation & AI | Integrations, API, mobile | Performance & reliability | Security/privacy, pricing, source/community/docs/distribution | Common strength / weakness |
|---|---|---|---|---|---|---|---|
| AI Flight Radar | Taiwan-origin self-hoster wanting inspectable evidence | Exact-query history, typed unknowns, browser-local watchlist; technical setup | Rule parsing and scheduled bounded scans; no LLM claim | FastAPI/CLI/Docker/Worker; responsive web; no public API promise | Strong offline gates; one uncalibrated live source | Local-first/private; free code visible but unlicensed; small community/docs strong; self-host distribution | Trust-oriented model / live source and onboarding unproven |
| [Google Flights](https://support.google.com/travel/answer/2475306?co=GENIE.Platform%3DDesktop&hl=en) | Mainstream travelers comparing broad inventory | Calendar, price graph, filters, 300+ airline/OTA partners, booking redirect | Price tracking, change alerts, forecasts; AI Flight Deals beta | Web/mobile web; Google account surfaces; no general public product API | Broad distribution; explicit freshness/availability limits | Closed/free consumer service; mature help/distribution | Coverage and UX / opaque upstream logic and not self-hosted |
| [Skyscanner](https://help.skyscanner.net/hc/en-gb/categories/200368471-Prices) | Price-sensitive global travelers | Route/date search, flexible month/everywhere, price alerts, provider redirect | Regular alert checking; limited filter carry-over | Web/apps; account required for alerts | Explicit indicative/snapshot and booking-time mismatch semantics | Closed/free metasearch; global docs/distribution | Breadth and mismatch honesty / alert price not guaranteed |
| [KAYAK](https://www.kayak.com/c/help/search/) | Leisure/business travelers needing comparison and trips | Flexible dates, Explore, filters, Trips, flight tracker | Price Forecast with confidence/insufficient-data state; Ask AI | Web/apps, alerts, trip organization | Broad multi-site comparison; forecasts are non-guaranteed | Closed/freemium ecosystem; mature support/distribution | Rich decision surface / complexity and account ecosystem |
| [Hopper](https://help.hopper.com/en_us/about-our-price-predictions-Hy7cLt_Fv) | Mobile-first travelers deciding buy vs wait | Watch a trip, notification-led flow, in-app booking ecosystem | Historical/real-time price prediction and buy/wait guidance | Native mobile, push notifications | Large claimed observation volume; model performance not independently verified here | Closed commercial app; account/payment relationship | Low-friction timing advice / less inspectable and higher platform coupling |
| Airline-direct/manual check | Traveler prioritizing final terms | Airline search and final checkout terms | Little cross-airline automation | Web/apps, carrier-specific | Closest to final inventory but poor comparison breadth | Direct commercial relationship; fragmented docs | Final-price authority / high manual effort |

### Capability classifications

- **MUST MATCH:** freshness/source status; typed empty/error/partial states; booking-time reconfirmation; directness/passenger/currency/baggage truth; safe handoff links; reliable alert delivery.
- **SHOULD BE BETTER:** auditability of the historical baseline; local-first privacy; exact-query comparisons; explain why evidence is insufficient; cheap self-host operation.
- **DIFFERENTIATOR:** provider-independent EvidenceReceipt joining source health, normalized query, observation time, comparison cohort, score explanation, and handoff verification.
- **DO NOT COPY:** booking/payment, credit products, generic travel planning, massive account systems, opaque “AI found a deal” claims, or breadth before source fidelity.

## Virtual Executive Board

| Role | Question | Opportunity | Priority |
|---|---|---|---|
| CEO | Can a user trust the next action more than a cheaper-looking competitor result? | Own inspectable Taiwan-origin fare evidence | Gate public collection, then lock reproducibility and rights |
| CPO | Which promise is the product: lowest price, timely signal, or evidence? | Make evidence and uncertainty the promise | One Preview → Observe → Reconfirm journey |
| CTO | Can the same source/build contract be reproduced after upstream change? | Typed provider outcomes and canonical locks | #1 and #2 |
| Staff/Principal Engineer | Where can partial data masquerade as success? | Single EvidenceReceipt across provider/store/API/UI | Contract tests and fail-closed admission |
| UX Lead | Can a traveler distinguish stale, unavailable, and unknown from “no cheap flights”? | Evidence-forward cards without jargon | State copy and booking reconfirmation |
| UX Researcher | Which uncertainty blocks booking versus merely annoys? | Test source/freshness comprehension | Runtime moderated research after calibration |
| Growth Lead | What shareable hook avoids becoming another metasearch site? | Taiwan-origin watchlists with trustworthy explanations | Validate repeat watch behavior, not traffic vanity |
| CFO/Business Analyst | What is the cost per useful verified observation? | Budgeted collection with quality denominator | Unit-cost and success-rate telemetry |
| Security/Privacy Lead | Does public collection expand secret/data exposure? | Local-first storage and role-separated keys | Provider terms, key isolation, dependency locks |
| QA Lead | Can failures be replayed deterministically? | Typed fixtures for no-results/rate-limit/schema drift | #1 replay suite and #2 clean installs |
| SRE Lead | What wakes an operator before users see stale truth? | Source-health SLO and last-success visibility | Do not enable schedule without observable gate |
| Accessibility Specialist | Does evidence remain understandable without color/pointer? | Native semantics for status and filters | Keyboard/screen-reader runtime matrix; no untested defect claim |
| Customer Support Lead | Can support explain a mismatch without raw logs? | Shareable redacted observation receipt | Stable receipt ID and handoff context |

### Cross-review and minority opinions

- CEO answer if resources permit only three things: (1) complete #1 and keep collection gated by the result, (2) complete #2 so incidents are reproducible, (3) settle #3 so distribution intent is explicit. Do not build booking/payment, multi-user SaaS, or another AI planner.
- Growth minority: launch an early public beta to learn faster. SRE/Security/Support objection: without calibrated source semantics, learning is confounded by upstream failure. Resolution: private, bounded research is allowed; public reliability claims are not.
- Product minority: add a second provider immediately. Engineering objection: two uncalibrated wrappers double ambiguity. Resolution: define the provider-independent receipt with the current source, then add an actually independent provider.
- Legal minority: leave the repository unlicensed until the business model is clear. Resolution: that is an acceptable outcome only if documented as an intentional rights boundary via #3.

## 50 Synthetic Personas

These are synthetic simulations. B01–B30 are regression-baseline personas (60%); R31–R50 rotate edge/exploration scenarios (40%). No browser, device, purchase, provider, or human test is claimed.

| ID | Background | Goal | Expectation | Task | Journey | Friction | Outcome | Comment | Severity | Suggestion |
|---|---|---|---|---|---|---|---|---|---|---|
| B01 | 19, student, Android/4G, first trip | Taipei→Osaka under NT$8k | Fresh comparable price | Search fixed dates | Enter route → inspect cards → open source | Cannot see live-calibration receipt | Partial | Unknown is honest, but I still verify elsewhere | P1 | #1 source-health badge and handoff check |
| B02 | 27, first-time traveler, iPhone/Wi-Fi | Choose a weekend flight | Simple cheapest trustworthy option | Compare ±3 days | Search → date grid → quote detail | Flexible grid narrower than incumbents | Success | Exact-date evidence is understandable | P2 | Improve only after fidelity gate |
| B03 | 38, family planner, laptop | Price four travelers with bags | Group total and baggage truth | Round-trip family search | Set passengers → filter → handoff | Baggage/final total remain unknown | Partial | Do not imply base fare is family total | P1 | #1 compare passenger/currency/baggage semantics |
| B04 | 24, backpacker, power user | Find lowest flexible Japan trip | Broad destination/date discovery | Explore cheaply | Try multiple tasks → rank | Collection budget and one source limit breadth | Partial | Trust beats fake breadth | P2 | Keep bounded scans; no invented prices |
| B05 | 34, shift worker, Android/5G | Watch rare days off | Persistent alert without babysitting | Save route and wait | Save watch → close tab | Watchlist is browser-local, no server schedule | Failure | The product copy states the boundary | P2 | Later: notification outbox after #1 |
| B06 | 68, retired, low digital skill, tablet | Know whether to buy now | One plain-language answer | Read top card | Open site → read status | Technical evidence terms may overwhelm | Partial | I need a short reason and a details link | P2 | Plain-language status; runtime usability test |
| B07 | 31, blind, screen reader/keyboard | Compare quotes independently | Semantic controls/status | Filter and open details | Tab → select filters → quote → link | Assistive-tech behavior not runtime-tested | Unknown | Static code is insufficient evidence | P2 | Keyboard/screen-reader matrix before claim |
| B08 | 55, low vision, Windows/high zoom | Read price and freshness | No clipped state at 200% | Zoom and inspect | Load → zoom → filter | Responsive code exists; reflow unknown | Unknown | Do not call it accessible yet | P2 | Runtime reflow/contrast check |
| B09 | 42, motor disability, keyboard only | Operate all actions | No pointer dependency | Search/filter/watch | Keyboard journey | Browser simulation is not device verification | Unknown | Need visible focus and native controls | P2 | Runtime keyboard acceptance |
| B10 | 29, Deaf traveler, mobile | Understand alerts visually | No sound-only cue | Save/receive alert | Configure channel → wait | Real notification not tested | Unknown | Text channels fit; delivery is unknown | P2 | Outbox/delivery receipt later |
| B11 | 46, rural user, spotty 3G | Load last observed fare | Stale data labeled, light payload | Open on weak network | Load → cached/latest card | Production latency/offline behavior unknown | Partial | A dated snapshot is still useful | P2 | Expose last success and payload budget |
| B12 | 33, Taiwan expatriate, desktop | Compare TPE and regional airports | Airport identity preserved | Search multiple origins | Create tasks → compare | Airport ambiguity handling not runtime-validated | Partial | Exact query key is promising | P2 | Airport identity contract tests |
| B13 | 41, independent travel adviser, expert | Explain fare evidence to client | Shareable audit context | Inspect details | Search → evidence → handoff | No portable redacted receipt | Partial | Screenshots lose provenance | P2 | Later EvidenceReceipt export |
| B14 | 36, data analyst, desktop | Audit 30/90-day claim | Denominators and cohort visible | Inspect history | Open quote → methodology | Five-day/coverage logic exists | Success | Daily weighting avoids scan-frequency bias | P3 | Keep exact denominators visible |
| B15 | 39, DevOps operator, Linux | Deploy reproducibly | Same dependency graph | Fresh clone and build | Install Python/Node → CI | No committed Node/Python resolution locks | Failure | Today’s green is not future reproducibility | P2 | #2 deterministic locks |
| B16 | 32, security reviewer, desktop | Assess public collector risk | Least privilege and immutable deps | Review workflows | Keys → auth → installs | Dependencies/actions not fully immutable | Partial | Write paths fail closed, supply chain does not | P2 | #2 including action SHAs |
| B17 | 28, self-hoster, Mac | Run privately | Clear rights and one-command setup | Fork and deploy | Read README → license → setup | No project license | Failure | Public visibility is not permission | P3 | #3 rights decision |
| B18 | 45, privacy-sensitive traveler, Firefox | Avoid account/profile | Local-first watchlist | Search and save | Use without login | Good local boundary; source request privacy unknown | Partial | Better than account-first alternatives | P2 | #1 retention/redaction protocol |
| B19 | 30, direct-flight-only traveler, Android | Avoid connections | Constraint remains true at handoff | Filter direct | Search → direct filter → provider | Handoff consistency uncalibrated | Partial | Directness must be checked, not inferred | P1 | #1 field-consistency metric |
| B20 | 37, parent, iPad | Know baggage-inclusive cost | Unknown shown as unknown | Inspect fare detail | Search → baggage row → link | Cannot compare total without verified baggage | Partial | Honesty prevents false confidence | P1 | #1 plus later fare-basis provider |
| B21 | 26, round-trip planner, laptop | Compare complete itinerary | Both legs traceable | Enter outbound/return | Search → inspect route | Current model may summarize offers | Partial | Need segment identity before broad launch | P2 | Later roadmap; do not fake completeness |
| B22 | 23, one-way traveler, Android | Find cheapest single leg | Correct one-way semantics | One-way search | Create task → quote | Runtime provider behavior unknown | Unknown | Tests cannot prove live source semantics | P1 | #1 include one-way stratum |
| B23 | 35, flexible remote worker, desktop | Move trip by days | Fast date comparison | Compare dates | Create multiple tasks → grid | More manual than Google/KAYAK | Partial | Useful only if evidence is better | P2 | Post-#1 batch/date UX research |
| B24 | 44, fixed wedding traveler, mobile | Track exact itinerary | No irrelevant flexible result | Exact dates + alert | Save → revisit | No verified scheduled delivery | Failure | Browser save alone is insufficient | P2 | Later outbox after source gate |
| B25 | 50, group organizer, laptop | Price four adults | All-passenger total consistent | Set travelers | Search → quote → booking | Group inventory can reprice | Unknown | Snapshot must not masquerade as checkout total | P1 | #1 passenger and handoff discrepancy |
| B26 | 31, late-booking traveler, 5G | Act within hours | Freshness obvious | Search today | Load → inspect observed_at → click | Six-hour TTL may be too broad for volatile fares | Partial | TTL is explicit but needs calibration | P1 | #1 measure discrepancy versus age |
| B27 | 40, long-horizon planner, desktop | Watch 9 months ahead | No false no-results | Create future task | Scan → no result state | Airlines may not publish yet | Partial | Typed no-results is essential | P1 | #1 strata and typed outcomes |
| B28 | 22, hard budget cap, low-income, Android | Stay below NT$10k | Budget compared to real total | Set budget | Search → sort → link | Base/final price gap may break cap | Partial | Budget breach is high-impact | P1 | #1 discrepancy threshold |
| B29 | 48, alert-driven user, iPhone | Wait for meaningful drop | No noisy notifications | Watch route | Observe history → alert | Independent channel retry incomplete | Partial | Existing roadmap owns outbox root cause | P2 | Do not duplicate; sequence after #1 |
| B30 | 43, admin/operator, Linux | Run bounded scans safely | Budget, lease, status | Trigger three tasks | Auth → scan → status | Live provider health absent | Partial | Process safety is stronger than source safety | P1 | #1 operational gate |
| R31 | 29, iOS Safari, mobile data | Use public Worker UI | Same truth on mobile | Filter/date/share | Open → filter → details | No real Safari run | Unknown | Responsive code is not device proof | P2 | Device matrix after deployment |
| R32 | 25, Android WebView, constrained device | Open shared result | Graceful supported path | Load embedded browser | Link → page → source | Runtime support unknown | Unknown | Do not infer from Chromium simulation | P2 | WebView acceptance or explicit support |
| R33 | 52, Firefox ESR, desktop | Use without Chromium | Stable controls | Full journey | Search → filter → source | Only browser simulation evidence reviewed | Unknown | Standards-based code looks likely | P3 | Cross-browser runtime smoke |
| R34 | 60, JavaScript restricted, enterprise laptop | Read evidence | Fallback or clear unsupported state | Open site | Load static response | No no-JS contract assessed | Unknown | Not enough evidence for a defect | P3 | Research support boundary, not feature creep |
| R35 | 21, high-latency hostel Wi-Fi | Avoid repeated scans | Read stored result | Open → retry | Weak link → quote | Production retry/cache behavior unknown | Partial | Read-only snapshot is valuable | P2 | Measure payload/latency later |
| R36 | 34, offline traveler, PWA expectation | Use cached watchlist | Offline support | Disconnect and open | Save → offline | No PWA promise | Failure | Do not copy native/offline breadth | P3 | DON'T build PWA before core trust |
| R37 | 47, multi-currency shopper | Compare TWD/JPY | No hidden conversion | Inspect currency | Search → quote | Exact currency key exists; conversion UX limited | Success | No fake conversion is safer | P3 | Keep currency explicit |
| R38 | 39, midnight/timezone edge, Taiwan | Correct dates | No off-by-one journey | Create around midnight | Date input → API → store | Static code suggests care; runtime unknown | Unknown | Travel dates are high-risk edges | P2 | Timezone contract/replay after #1 |
| R39 | 33, airport-code novice | Search Tokyo city | Clear airport scope | Type city intent | Natural language → confirm | Rule parser scope limited | Partial | Confirmation is better than silent guess | P2 | Existing NLP roadmap; no duplicate Issue |
| R40 | 27, malformed-date edge | Recover safely | Validation error, no task | Submit invalid range | Input → API | Tests cover errors; live UI wording unknown | Success | Fail closed is correct | P3 | Maintain regression |
| R41 | 36, source returns empty | Know no inventory vs outage | Typed state | Run authorized query | Provider → empty | Current live distinction unmeasured | Failure | Empty cannot mean success | P1 | #1 typed calibration outcome |
| R42 | 38, source rate-limited | Avoid false no-deal | Typed rate limit and retry | Run bounded batch | Provider → limit | Code retries; live behavior unknown | Partial | Budgeting is good, evidence missing | P1 | #1 rate-limit stratum |
| R43 | 35, schema-drift operator | Detect upstream change | Parse failure and alarm | Replay changed payload | Provider → normalize | Fixtures cannot predict next upstream change | Partial | Need last-success/source-health receipt | P1 | #1 drift fixture and gate |
| R44 | 30, handoff mismatch traveler | Pay displayed price | Explain mismatch | Click source | Card → provider page | No measured discrepancy distribution | Failure | This is the core trust break | P1 | #1 booking-handoff comparison |
| R45 | 41, stale-quote edge | Avoid expired deal | Visible age and exclusion | Open 7-hour quote | Store → API → UI | Six-hour expiry exists; real adequacy unknown | Partial | Good invariant, uncalibrated threshold | P1 | #1 price-age analysis |
| R46 | 32, baggage-unknown edge | Avoid surprise fee | Unknown never scored as included | Inspect score | Quote → breakdown | Unknown handling is explicit | Success | Do not infer from airline brand | P2 | Maintain regression; later provider data |
| R47 | 28, self-transfer-sensitive | Avoid risky itinerary | Segments/transfer explicit | Inspect route | Quote → handoff | Full segment identity is later roadmap | Partial | Do not launch broad promise first | P2 | Later complete itinerary contract |
| R48 | 35, adult + child traveler | Correct passenger pricing | Passenger type fidelity | Create family query | Passengers → source | Current passenger model/live fidelity unknown | Unknown | Adult-only assumptions are unsafe | P1 | #1 include supported passenger boundary |
| R49 | 26, Windows contributor | Reproduce CI locally | Deterministic setup | Clone → install → tests | Mutable Python/Node graph | Failure | Setup may drift after audit date | P2 | #2 locks and documented regeneration |
| R50 | 49, institutional procurement/legal | Approve internal deployment | License/data/terms matrix | Review repository | README → license → provider terms | No project-level rights decision | Failure | Cannot approve a fork on implication | P3 | #3 owner/legal memo |

### Persona coverage summary

- Age 19–68; students, families, shift workers, retirees, developers, operators, security/legal reviewers, analysts, advisers, and accessibility users.
- Devices: Android, iPhone/iPad, Windows, macOS, Linux, tablets, WebView, Firefox ESR; conditions include 3G/4G/5G, high latency, offline expectations, restricted JavaScript, screen reader, zoom, and keyboard-only use.
- Primary root-cause clusters: source/handoff trust (#1), reproducible operations (#2), permitted use/distribution (#3). Accessibility/performance observations remain runtime research, not asserted defects.

## Competitor Switching Test

Scenario: each synthetic persona chooses one tool for the next flight-monitoring journey given current documented capabilities and evidence. This is simulated preference share, not market share or a survey.

| Choice | Personas | Share | Main reason |
|---|---:|---:|---|
| AI Flight Radar | 14 | 28% | Local-first privacy, exact-query evidence, honest unknown states |
| Google Flights | 13 | 26% | Breadth, calendar/graph UX, tracking, direct mainstream onboarding |
| Skyscanner | 10 | 20% | Flexible discovery, alerts, broad provider comparison, mismatch documentation |
| KAYAK | 7 | 14% | Filters, flexible dates, forecast confidence, trip ecosystem |
| Hopper | 4 | 8% | Mobile notification-led buy/wait journey |
| Airline direct/manual | 2 | 4% | Closest view of final inventory and terms |

Switching interpretation: AI Flight Radar wins technically capable/private users, but 36/50 choose an alternative when breadth, mobile onboarding, alert delivery, or final-price confidence dominates. The actionable answer is source-health evidence and a narrow moat, not copying every incumbent feature.

## Red Team

1. Persona bias: the sample may overrepresent technical self-hosters, which inflates the product’s 28%. Countermeasure: treat share only as a prioritization simulation; recruit real novice/mobile travelers later.
2. Competitor selection: Google Flights is also the apparent upstream source, so it is both dependency and alternative. This tension strengthens, rather than resolves, the need for provider-independent receipts.
3. Confirmation bias: strong repository honesty could cause the board to overrate actual accuracy. The audit explicitly keeps live accuracy UNKNOWN.
4. Overengineering: do not build a universal provenance platform. #1 should start with the smallest typed observation receipt that makes a go/no-go decision.
5. Feature bloat: a second provider, native app, accounts, AI planner, and booking are deferred.
6. Copying competitors: price forecasts and expansive flexible-date maps are not requirements until enough independent historical evidence exists.
7. Growth pressure: traffic is not a useful metric if source success and handoff fidelity are unknown.
8. Simplify/delete first: keep the public collector disabled; retire any copy that implies live, realtime, AI prediction, or baggage-inclusive final price without evidence.
9. License caveat: an automated audit must not choose a legal license; #3 preserves the owner/human decision.
10. Security caveat: no source terms violation, CAPTCHA bypass, proxy evasion, or secret retrieval is justified by “research.”

## Findings and Quality Gate

| Finding | Type | Priority | Impact | Strategic value | Gap | Risk reduction | Confidence | Effort | Gate | Tracking |
|---|---|---:|---|---|---|---|---|---|---|---|
| Live source/booking fidelity is uncalibrated before public collection | RESEARCH_REQUIRED, RELIABILITY | P1 | High | High | MUST MATCH | High | High gap / unknown runtime result | M | PASS | [#1](https://github.com/Reese-max/ai-flight-radar/issues/1) NEW RESEARCH |
| Node/Python/Actions dependency graph is not reproducible from source | SECURITY, RELIABILITY, TECH_DEBT | P2 | Medium | Medium | MUST MATCH | High | High | M | PASS | [#2](https://github.com/Reese-max/ai-flight-radar/issues/2) NEW |
| Code/docs/generated-data rights boundary is intentionally unresolved | RESEARCH_REQUIRED, DOCUMENTATION | P3 | Medium for adopters | Medium | Distribution | Medium | High gap / legal choice unknown | S–M | PASS | [#3](https://github.com/Reese-max/ai-flight-radar/issues/3) NEW RESEARCH |

Quality Gate checks: each finding has direct evidence, a distinct stable fingerprint, actionability, impact, explicit acceptance criteria, regression scenario, confidence boundary, and full search across open/closed Issues, roadmap, audits, PRs, and branches. No prior Issue or closed regression existed.

### Duplicate avoided / root grouping

- Source outage, empty results, rate limits, schema drift, quote age, passenger/directness/currency mismatch, and booking-page price mismatch share the acquisition-calibration root and map to #1.
- Missing Node lock, Python hashes, mutable install command, and moving Action tags share the reproducible-build root and map to #2.
- Contributor hesitation, self-host permission, design-asset reuse, generated-data reuse, and contribution ownership share the rights-boundary root and map to #3.
- NLP scope, notification channel outbox, lease renewal, second provider, full round-trip/baggage, E2E/Docker, and multi-user work remain named roadmap items; no duplicate Issues were created without new independent evidence.

### Rejected findings

1. “Google Flights is currently down” — rejected: no live query was run.
2. “Current quotes are wrong” — rejected: no live quote/handoff comparison exists.
3. Immediate P0 incident — rejected: collector is disabled and no deployed-user harm is confirmed.
4. Add multiple providers now — rejected: uncalibrated breadth doubles ambiguity; roadmap owns sequencing.
5. Auto-booking/payment — rejected: safety, liability, and scope expansion; explicitly outside roadmap.
6. Multi-user SaaS/accounts — rejected: privacy/operations expansion before core fidelity.
7. Native app/PWA — rejected: no demand evidence; incumbents already dominate breadth.
8. General AI trip planner or opaque deal forecast — rejected: insufficient proprietary evidence and confirmation risk.
9. CAPTCHA/proxy evasion or aggressive scraping — rejected: terms/security risk.
10. Generate synthetic historical fares to improve scoring — rejected: destroys evidence integrity.
11. Separate Issues for stale, empty, parse, and mismatch symptoms — rejected as duplicate root; mapped to #1.
12. Separate Node, Python, and Actions lock Issues — rejected as duplicate mutable-build root; mapped to #2.
13. Separate license Issues for code, docs, assets, and generated data — rejected as one owner decision; mapped to #3.
14. Accessibility or performance defect claims — rejected: no device/assistive-tech/load runtime evidence.

## NOW / NEXT / LATER / DON'T

| Horizon | Work | Rationale |
|---|---|---|
| NOW | #1 bounded live calibration; keep schedule/public collector off unless BUILD/NARROW | Core trust gate |
| NOW | #2 committed dependency resolution and deterministic CI | Reproducible incidents and supply chain |
| NOW | #3 owner rights decision | Clarify whether external reuse/contribution is intended |
| NEXT | Provider-independent EvidenceReceipt, source-health UI, independent notification outbox | Convert findings into a narrow moat |
| NEXT | Runtime keyboard/screen-reader/mobile matrix and measured payload/latency | Close UNKNOWN UX/accessibility/performance states |
| LATER | Actually independent second provider; complete segment/fare/baggage/total-price model | Broaden only after one source is measurable |
| LATER | Multi-user service only with identity, isolation, privacy, recovery, and audit | High operational cost |
| DON'T | Booking/payment, credit products, fake history, generic AI planner, social marketplace, native rewrite, source-control bypass | Scope, trust, safety, and maintenance harm |

## Difference From Previous Round

This is the first product-board audit stored in this repository. There is no prior audit baseline and no historical audit Issue to regression-test. Compared with the product’s own roadmap, this run converts three evidence-backed roadmap/contract gaps into actual GitHub tracking objects. It does not claim the recently merged price-integrity or Cloudflare work is a verified fix for a prior Issue.

## Regression

| Object | Status | Evidence |
|---|---|---|
| Prior audit Issues | CANNOT VERIFY / none existed | Repository had zero Issues before this run |
| Price-integrity commit a5295fc0 | CODE/CI PRESENT, not VERIFIED FIXED | Passing later CI, but no prior acceptance object or live fare validation |
| Cloudflare port f2dac801 | LOCAL CI VERIFIED, production UNKNOWN | workerd/D1 smoke passes; public collector disabled; deployment not verified |
| New #1–#3 | OPEN / NOT FIXED | Created in this run; acceptance criteria not yet executed |

Verified Fixed count: **0**.

## Runtime Pending

- Authorized bounded provider queries, typed source outcomes, final booking-handoff comparison, price-age/discrepancy relationship, and rate-limit/schema-drift behavior.
- Real notification delivery and independent channel retry.
- Public Cloudflare/D1 state, HTTPS, secret roles, migration/rollback, latency/load/cost, and source schedule.
- Safari, Android WebView, Firefox ESR, keyboard, screen reader, 200% zoom/reflow, weak network, and timezone/date edges.
- Human owner/legal review of code/assets/data/provider terms.

## Decision Memo

- **What this product should become:** a narrow, trustworthy Taiwan-origin fare evidence radar that tells users what was observed, how comparable it is, how fresh it is, and what must be reconfirmed.
- **Who it should serve:** price-sensitive/flexible travelers who value evidence and privacy, plus a small self-hosting operator; not every global traveler.
- **Why users would choose it:** local-first control, exact-query historical reasoning, transparent unknowns, and inspectable scoring.
- **Why users choose competitors:** broader supply, smoother onboarding, flexible-date discovery, mature mobile alerts, accounts/trips, and higher perceived booking confidence.
- **Biggest competitive gaps:** calibrated source health, final-price/handoff evidence, alert delivery, inventory breadth, and mainstream onboarding.
- **Potential moat:** an EvidenceReceipt connecting query identity, provider outcome, raw/normalized fields, observation age, comparison cohort, score explanation, and booking reconfirmation.
- **Top strategic/engineering/UX priorities:** #1 source calibration, #2 reproducible graph, #3 explicit distribution rights; then source-health UI and notification receipts.
- **What NOT to build:** booking/payment, generic AI planner, social/community marketplace, broad SaaS accounts, or native apps.
- **Features worth removing:** none proven harmful in current code; keep collection disabled and remove/avoid any copy that implies live, realtime, final-total, or predictive capability without a receipt.
- **Biggest risks:** upstream fragility/terms, silent schema/price drift, mutable builds, unclear rights, operator overclaim, and insufficient mobile/accessibility evidence.
- **Next experiments:** pre-registered #1 calibration; comprehension test for observed/stale/unavailable/handoff states; cost per useful verified observation; repeat watch behavior after calibrated alerts.
- **Portfolio decision:** **INVEST / SIMPLIFY**. Invest in trust infrastructure and a narrow Taiwan-origin wedge; simplify by refusing breadth until evidence is measurable.

## Portfolio CEO Review

This run deeply re-audited only AI Flight Radar. The ranking below carries forward the latest available portfolio baseline and must not be read as a fresh runtime revalidation of every repository.

| Rank | Repository | Portfolio decision / role | Shared opportunity |
|---:|---|---|---|
| 1 | academic-mcp | INVEST: private evidence-first academic gateway | Shared provider health, auth, evidence receipts |
| 2 | autodev-ng | INVEST/SIMPLIFY: governed issue-to-change execution | Shared lock/goal/verification receipts |
| 3 | police-exam-archive | INVEST: authoritative exam data/product core | Shared exam data layer and accessible practice components |
| 4 | ai-flight-radar | INVEST/SIMPLIFY: trusted fare observation | Shared provider health, scheduler, auth, CI admission |
| 5 | 92-duty-scheduler | INVEST: local rule-aware operations | Shared auth, backup/recovery, export validation |
| 6 | prompt-autoresearch | INVEST/SIMPLIFY: evidence-gated prompt optimization | Shared evaluation and typed inconclusive results |
| 7 | soundbox-offline | INVEST/SIMPLIFY: local-first media appliance | Shared backup/restore and offline design system |
| 8 | cyber-prep-coach | INVEST with SME gate | Shared exam UX/data layer, provenance |
| 9 | minideck | INVEST/SIMPLIFY: explicit publish lifecycle | Shared publish/auth/storage components |
| 10 | voice-actress | REPOSITION/SIMPLIFY: Taiwan legal essay practice | Merge naming/UX/data concepts with exam portfolio |
| 11 | exam-archive | SIMPLIFY/MAINTAIN | Candidate shared practice renderer/data contracts |
| 12 | police-exam-practice | MAINTAIN as compatibility layer | Merge product functionality into police-exam-archive |

Portfolio consolidation: build reusable evidence/source-health receipts for academic-mcp, ai-flight-radar, prompt-autoresearch, and intelligence dashboards; a common dependency/admission gate; a small auth/key-role module for Cloudflare/FastAPI products; one accessible exam renderer/data identity layer; and one publish lifecycle contract. Do not merge domains into one app or create a universal “platform” before three consumers share the exact contract.

## Mandatory Verification

- **Total Findings:** 3
- **New Issues Created:** 3
  - Reese-max/ai-flight-radar [#1](https://github.com/Reese-max/ai-flight-radar/issues/1) — [Research][P1][RELIABILITY] Calibrate live quote fidelity before enabling the public collector
  - Reese-max/ai-flight-radar [#2](https://github.com/Reese-max/ai-flight-radar/issues/2) — [P2][SECURITY][RELIABILITY] Make Python and Cloudflare builds reproducible with committed locks
  - Reese-max/ai-flight-radar [#3](https://github.com/Reese-max/ai-flight-radar/issues/3) — [Research][P3][DOCUMENTATION] Decide code, generated-data, and deployment licensing boundaries
- **Updated Existing Issues:** 0
- **Reopened Issues:** 0
- **Research Issues:** 2 (#1, #3)
- **Duplicate Avoided:** 15 persona/symptom manifestations consolidated into three root Issues; 7 roadmap-only candidates were not duplicated without new independent evidence.
- **Issue Write Blocked:** 0
- **SKIPPED_LOCKED:** 0. Issues #1–#3 had no competing unexpired marker; product-board locks were written and read back. Open PRs and github-* branches were 0 immediately before report write.
- **Rejected Findings:** 14, listed above with explicit reasons.
- **Verified Fixed:** 0
- **Priority distribution:** P0 0 / P1 1 / P2 1 / P3 1 / STRATEGIC 0
- **Highest Priority:** #1
- **Finding mapping:** 3/3 PASS — every Quality-Gate finding maps to NEW or NEW RESEARCH.
- **Safety:** no merge, deployment, source modification, secret/settings change, booking, real notification, or live fare query.

## Sources checked 2026-09-12

- Google Flights search/booking/freshness: https://support.google.com/travel/answer/2475306?co=GENIE.Platform%3DDesktop&hl=en
- Google Flights price tracking: https://support.google.com/travel/answer/6235879?co=GENIE.Platform%3DDesktop&hl=en
- Skyscanner prices and alerts: https://help.skyscanner.net/hc/en-gb/categories/200368471-Prices
- KAYAK search, flexible dates, forecast, alerts: https://www.kayak.com/c/help/search/
- Hopper prediction model: https://help.hopper.com/en_us/about-our-price-predictions-Hy7cLt_Fv
- npm ci: https://docs.npmjs.com/cli/v11/commands/npm-ci/
- GitHub dependency graph: https://docs.github.com/en/code-security/supply-chain-security/understanding-your-software-supply-chain/about-the-dependency-graph
- GitHub repository licensing: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository