# Fast Flights source calibration protocol

Protocol version: 1.0  
Target: the public Cloudflare collector using fast_flights 3.1.0 and Google Flights-derived results.

## Authorization and limits

This is a pre-registered protocol, not permission to run it. An owner must first confirm provider terms and authorization, approve the query budget, and name the isolated research account and operator. Until then, the committed admission receipt is BLOCK.

The planned maximum is 48 searches: exactly one attempt for each of the 16 routes already configured in cloudflare/src/catalog.mjs in each of three date windows (30, 90, and 180 Taipei calendar days ahead). Record each flight's `depart_date`; the evaluator derives its window from `queried_at` in Asia/Taipei and rejects a repeated window, a different window, or more than 48 attempts. Each route uses the collector's supported profile only: one adult, economy, round trip, direct flights. The existing service default is at most three claims per hour; never exceed the configured hard cap of ten claims per hour. There are no automatic retries. Stop immediately after any rate limit, upstream schema change, parse failure, unsafe or unresolved handoff, or owner stop request. A NO_RESULTS result consumes one attempt and is never recorded as a successful quote.

The product cannot currently express one-way trips, multiple passengers, other cabins, or connecting flights through the Cloudflare collector. Those profiles are out of scope and must be marked BLOCKED without querying. Baggage and final fees remain unknown and must not be inferred from an economy/direct result.

The 48-attempt ceiling gives three independent date-window observations per configured route. A route can be admitted only with at least three successful, parse-complete observations and three manual handoff comparisons. If some routes pass, produce NARROW with only those routes. BUILD requires all 16 configured routes to pass. If no route passes, or authorization/terms/budget is absent, the decision is BLOCK.

## Recorded evidence and thresholds

Record one normalized JSON object per attempt using the schema accepted by cloudflare/src/calibration.mjs. Allowed outcomes are SUCCESS, NO_RESULTS, RATE_LIMITED, UPSTREAM_CHANGED, PARSE_FAILED, and BLOCKED. A successful observation includes quote age, source currency and supported profile fields, safe-link resolution status, and (when manually checked) displayed and handoff prices. The application timestamp is not evidence of the source quote's age. The aggregate receipt records sample counts beside rates and percentiles: attempted/successful/parsed, date-window coverage, quote-age sample count, each consistency match count, safe-link count, and handoff-comparison count. BUILD/NARROW receipts also carry explicit owner, terms, and budget approval flags; all three must be true and the blocker list empty.

Each admitted route must meet all of these predeclared thresholds:

- At least 3 attempts and 3 successful observations; search success rate at least 90%.
- Parse completeness at least 98%.
- 95th-percentile source quote age no more than 6 hours.
- 100% agreement for currency, passenger count, cabin, and directness.
- 100% safe handoff-link resolution and at least 3 manual booking-handoff comparisons.
- 95th-percentile absolute displayed-to-handoff price difference no more than 5%.

Any RATE_LIMITED, UPSTREAM_CHANGED, PARSE_FAILED, BLOCKED, unsafe link, or operator stop blocks the whole run. An unresolved link cannot count as a safe comparison. Do not click through, store, or replay a purchase action.

## Privacy and retention

Do not retain raw provider responses, HTML, query URLs, booking URLs, cookies, credentials, traveler identity, or payment data. Keep only the normalized outcome and aggregate metrics needed for the decision. Use synthetic identifiers; discard per-attempt normalized records after the owner has reviewed the aggregate receipt, and retain the aggregate receipt for at most 30 days before re-evaluation. No real user notifications or purchases are part of this protocol. No CAPTCHA bypass, proxy evasion, or credential scraping is allowed.

The committed cloudflare/calibration/admission.json contains only the current decision. An owner-reviewed receipt must be generated from normalized observations and committed before BUILD or NARROW can admit collection. Receipts expire after 14 days. The runtime rechecks the decision and, for NARROW, filters claims to the exact allowed route list.

## Source-health states exposed by the API and UI

- available: a current receipt admits the route and the latest batch has successful observations, no errors, and is less than 3 hours old.
- partial: the latest batch is less than 3 hours old and has both successful observations and errors.
- stale: the latest batch is over 3 hours old or has an invalid future timestamp. Its prices must be rechecked at the source.
- unavailable: no successful observation exists, the latest batch is empty or failed, or calibration is blocked, invalid, or expired. This is not the same as NO_RESULTS.

The API reports a state and a bounded reason code. The UI uses plain-language labels and continues to identify stored fares as observations rather than guaranteed booking prices.
