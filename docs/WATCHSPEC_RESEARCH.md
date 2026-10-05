# Reviewed intent → WatchSpec: offline research (#4)

Decision: **NARROW**. A deterministic, offline review contract is feasible. It does
not establish natural-language mapping accuracy, a durable server watch, live
collection, notification fidelity, or usefulness to travelers.

`ai/nlp_parser.py::ParsedSearchIntent` supplies airport scopes, a bounded date
window, trip-day ranges, budget and directness. It cannot express cabin, traveler
count, stop limit, airline inclusion/exclusion, or arbitrary unsupported terms.
Its defaults (including dates) must be reviewed rather than silently promoted.
The new `ReviewFields` requires those missing decisions explicitly; unresolved
or unsupported constraints produce `NEEDS_REVIEW` with no WatchSpec.

`core/watchspec.py` creates strict, versioned `WatchSpec` candidates. Dates,
scope, currency, custom budgets, cabin, travelers, stops and airline lists enter
the canonical hash. Exact-date return/duration consistency is checked; flexible
windows stay explicit and are never expanded into tasks. No model is called.
Equal normalized specs retain the same version; a material edit produces the
next version and a before/after diff while the old object stays unchanged.

The offline preview shows both the human-readable interpretation and exact JSON
diff. Its status remains `REVIEW_REQUIRED`. Explicit confirmation must supply
the displayed hash and every spec field. The resulting receipt binds the watch
version, parser/compiler versions, source-intent hash and confirmation time.
Its kind is `OFFLINE_WATCH_PROMOTION_RECEIPT`: it grants **no collector authority**.
Scheduled collection is always `BLOCKED`; notification delivery is
`NOT_ATTEMPTED`. No database, task, account, booking or notification API is added.

## Reproduce without a provider

After installing the repository's declared development dependencies:

```bash
python -m pytest tests/test_watchspec.py -q
python scripts/watchspec_preview.py tests/fixtures/watchspec/reviewed-tokyo.json --output /tmp/watchspec-review
```

Open `/tmp/watchspec-review/preview.html`. The fixture is manually reviewed,
synthetic travel intent, not a quoted fare or a measured NLP result. To emit the
offline receipt, add `confirmed_fields` listing every key shown in `spec` to a
copy of the input, then repeat the command with `--confirm-hash` set to the
displayed hash. Missing fields or a changed hash fail closed. Do not publish
personal travel conditions, credentials or runtime artifacts in the repository.

## Evidence and remaining requirements

The 16 deterministic contract tests exercise canonical scope ordering, exact and
flexible dates, custom budget, ambiguity/unsupported rejection, invalid airport
and date windows, stop/airline contradictions, versioned edits, stale-hash
confirmation refusal, required-field confirmation, and escaped HTML output.
These are engineering contract checks; **NLP mapping rate, false mapping rate,
user task time, source fidelity and alert-delivery performance are NOT_RUN**.
Model requests/tokens/cost are 0 for this implementation. Provider and human
time/cost have not been measured.

The existing public UI remains browser-only tracking. This standalone preview
does not complete the in-product one-action flow. No alert is emitted, so
WatchSpec-bound observation/alert receipts remain NOT_RUN. A future integration
must validate all constraints against the selected provider, derive a bounded
evaluation plan, persist immutable versions, bind observation IDs and
source-health state, and distinguish notification attempts from delivery.

Before any scheduled/public provider calls, #1 must admit the exact routes/date
strata through its bounded runtime calibration; request/cost budgets and runtime
authorization must also permit the plan. Merely emitting an offline promotion
receipt does not satisfy those gates. Existing PR #16 supplies reproducible locks
and fixes the SQLModel UTC-naive storage compatibility failure on current
dependencies; those changes are not duplicated here.
