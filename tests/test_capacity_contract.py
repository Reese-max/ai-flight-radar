"""Issue #6 capacity contract: seeded route demand must fit planned capacity.

Documented invariant (docs/CLOUDFLARE.md):
    active_tasks <= revisit_hours * scheduled_runs_per_hour * max_tasks_per_run
    scheduled_runs_per_hour * max_tasks_per_run <= hourly claim budget bound

Every knob is parsed from the real sources — collector.py route sets,
store.mjs/logic.mjs intervals, collector.yml cron + --max-tasks, the
build.mjs UI staleness adaptation — so changing any of them fails loudly
instead of silently re-creating the 48-tasks/6h/6-claims-per-hour deficit.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def _set_members(source, name):
    m = re.search(rf"{name}\s*=\s*\{{([^}}]+)\}}", source)
    assert m, f"{name} set not found"
    return {s.strip().strip("'\"") for s in m.group(1).split(",") if s.strip()}


def _seed_task_count():
    collector = _read("cloudflare/scripts/collector.py")
    tasks_py = _read("cloudflare/scripts/tasks.py")
    assert "for o in sorted(ORIGINS) for d in sorted(DESTINATIONS)" in tasks_py, (
        "tasks.py no longer seeds the full Cartesian product; recount demand"
    )
    return len(_set_members(collector, "ORIGINS")) * len(_set_members(collector, "DESTINATIONS"))


def _ms_expr_hours(token, sources):
    """Resolve an hour-multiple expression like `3600000`, `8*3600000` or a
    named constant defined as one of those."""
    token = token.strip()
    if re.fullmatch(r"[A-Za-z_]\w*", token):
        m = re.search(rf"\b{token}\s*=\s*(?:(\d+)\s*\*\s*)?3600000\b", sources)
        assert m, f"{token} definition not found"
        return int(m.group(1) or 1)
    m = re.fullmatch(r"(?:(\d+)\s*\*\s*)?3600000", token)
    assert m, f"unexpected millisecond expression {token!r}"
    return int(m.group(1) or 1)


def _revisit_and_retry_hours():
    """(ok/empty revisit, error retry) hours from the complete() reschedule."""
    sources = _read("cloudflare/src/store.mjs") + _read("cloudflare/src/logic.mjs")
    m = re.search(
        r"outcome==='error'\s*\?\s*([A-Za-z_]\w*|(?:\d+\s*\*\s*)?3600000)"
        r"\s*:\s*([A-Za-z_]\w*|(?:\d+\s*\*\s*)?3600000)",
        sources,
    )
    assert m, "reschedule expression not found in store.mjs"
    return _ms_expr_hours(m.group(2), sources), _ms_expr_hours(m.group(1), sources)


def _advertised_ttl_hours():
    logic = _read("cloudflare/src/logic.mjs")
    m = re.search(r"\bTTL\s*=\s*(\d+)\s*\*\s*3600000", logic)
    assert m, "TTL freshness window not found in logic.mjs"
    return int(m.group(1))


def _cron_runs_per_hour(text):
    runs = 0
    for cron in re.findall(r"cron:\s*'([^']+)'", text):
        fields = cron.split()
        assert len(fields) == 5 and fields[1:] == ["*"] * 4, (
            f"cron {cron!r} is not an every-hour schedule; recount planned capacity"
        )
        assert re.fullmatch(r"\d{1,2}(,\d{1,2})*", fields[0]), f"cron {cron!r} minute field"
        runs += len(fields[0].split(","))
    return runs


def _scheduled_claims_per_hour():
    """(runs/hour, tasks/run) from the live collector workflow. The dormant
    template's commented schedule must not advertise a different cadence —
    a verbatim copy would silently re-create the demand>capacity deficit."""
    wf = _read(".github/workflows/collector.yml")
    runs = _cron_runs_per_hour(wf)
    assert runs, "collector schedule not found in collector.yml"
    tmpl_runs = _cron_runs_per_hour(_read("cloudflare/templates/cloudflare-collector.yml"))
    assert not tmpl_runs or tmpl_runs == runs, (
        "template collector schedule diverges from the live cadence"
    )
    m = re.search(r"--max-tasks\s+(\d+)", wf)
    assert m, "--max-tasks argument not found in collector.yml"
    return runs, int(m.group(1))


def _cf_stale_threshold_hours():
    """(shared web threshold, adapted cloudflare threshold) in hours."""
    web = _read("web/assets/logic.mjs")
    shared = re.search(r"now - timestamp > (\d+)\*3600000", web)
    assert shared, "shared UI staleness threshold not found"
    build = _read("cloudflare/build.mjs")
    adapted = re.search(
        r"now - timestamp > (\d+)\*3600000'\s*,\s*'now - timestamp > (\d+)\*3600000",
        build,
    )
    assert adapted, "build.mjs does not adapt the staleness threshold for the worker"
    assert int(adapted.group(1)) == int(shared.group(1)), (
        "build.mjs adapts a different source marker than web/assets/logic.mjs carries"
    )
    return int(shared.group(1)), int(adapted.group(2))


def _simulate(tasks, revisit, retry, runs, per_run, hours, error_run=None):
    """Frozen-clock claim simulation over whole hours.

    All seeded tasks start due at hour 0. Each hour, every scheduled run
    claims up to per_run due tasks, oldest next_run first (ORDER BY
    next_run,id). A successful or empty claim re-due's the task at
    now+revisit; a claim answered with outcome 'error' re-due's it at
    now+retry and aborts the rest of that run — matching store.mjs
    next_run semantics and collector.py's stop-on-error batch.
    """
    due = [0] * tasks
    serviced = {i: [] for i in range(tasks)}
    for hour in range(hours):
        for run in range(runs):
            for _ in range(per_run):
                pending = [i for i in range(tasks) if due[i] <= hour]
                if not pending:
                    break
                r = min(pending, key=lambda i: (due[i], i))
                due[r] = hour + retry if error_run == (hour, run) else hour + revisit
                if error_run == (hour, run):
                    break  # the collector stops the batch on an upstream failure
                serviced[r].append(hour)
    return serviced


def test_seeded_demand_fits_scheduled_capacity():
    tasks = _seed_task_count()
    revisit, _ = _revisit_and_retry_hours()
    runs, per_run = _scheduled_claims_per_hour()
    planned = runs * per_run
    demand = tasks / revisit
    assert demand <= planned, (
        f"{tasks} seeded tasks revisited every {revisit}h need "
        f"{demand:.1f} claims/hour but the scheduled collector supplies "
        f"{planned}/hour ({runs} runs x {per_run} tasks)"
    )


def _claim_budget_per_hour():
    """The checked-in hourly claim budget: wrangler var and code fallback
    must carry one consistent value, bounded by the enforced 1-10 range."""
    wrangler = json.loads(_read("cloudflare/wrangler.json"))
    var = int(wrangler["vars"]["MAX_SEARCHES_PER_HOUR"])
    store = _read("cloudflare/src/store.mjs")
    fallback = re.search(r"MAX_SEARCHES_PER_HOUR\|\|'(\d+)'", store)
    bound = re.search(r"integer\(limit,1,(\d+)", store)
    assert fallback and bound, "claim budget fallback/bound not found in store.mjs"
    assert int(fallback.group(1)) == var, (
        "code fallback and checked-in wrangler.json disagree on the claim budget"
    )
    assert var <= int(bound.group(1)), "claim budget exceeds the enforced bound"
    return var


def test_planned_rate_stays_within_bounded_provider_work():
    """The scheduled claim rate must fit inside the checked-in hourly claim
    budget and the collector's own batch cap — provider work stays bounded."""
    runs, per_run = _scheduled_claims_per_hour()
    collector = _read("cloudflare/scripts/collector.py")
    batch_bound = re.search(r"not 1 <= max_tasks <= (\d+)", collector)
    assert batch_bound and per_run <= int(batch_bound.group(1)), (
        "workflow requests more tasks per run than collector.py permits"
    )
    assert runs * per_run <= _claim_budget_per_hour(), (
        "scheduled claims/hour exceed the checked-in hourly claim budget; "
        "a lower budget makes every second scheduled run abort on a 429"
    )


def test_advertised_freshness_matches_revisit():
    """The quote validity window advertised to users is the revisit
    interval — data is not declared fresh longer than it is refetched."""
    revisit, _ = _revisit_and_retry_hours()
    assert _advertised_ttl_hours() == revisit


def test_cf_ui_stale_threshold_matches_revisit():
    revisit, _ = _revisit_and_retry_hours()
    _, adapted = _cf_stale_threshold_hours()
    assert adapted == revisit


def test_error_retry_is_shorter_than_revisit():
    revisit, retry = _revisit_and_retry_hours()
    assert retry < revisit


def test_full_matrix_covered_within_one_revisit_window():
    tasks = _seed_task_count()
    revisit, retry = _revisit_and_retry_hours()
    runs, per_run = _scheduled_claims_per_hour()
    serviced = _simulate(tasks, revisit, retry, runs, per_run, revisit)
    uncovered = [i for i, hits in serviced.items() if not hits]
    assert not uncovered, (
        f"{len(uncovered)} of {tasks} seeded routes cannot be serviced "
        f"within the {revisit}h revisit window at {runs}x{per_run} claims/hour"
    )


def test_error_batch_degrades_coverage_then_recovers():
    """One aborted batch must surface as degraded coverage, not the nominal
    target — and the errored task is retried within the next window rather
    than silently dropped."""
    tasks = _seed_task_count()
    revisit, retry = _revisit_and_retry_hours()
    runs, per_run = _scheduled_claims_per_hour()
    errored = _simulate(tasks, revisit, retry, runs, per_run, revisit, error_run=(0, 1))
    met = all(hits for hits in errored.values())
    assert not met, "an aborted batch must report degraded coverage, not claim the target"
    errored_task = 1 * per_run  # run 1's first claim: run 0 already took tasks 0..per_run-1
    assert errored[errored_task] == [], "the errored task's coverage is what slips"
    recovered = _simulate(tasks, revisit, retry, runs, per_run, revisit * 2, error_run=(0, 1))
    assert all(hits for hits in recovered.values()), "failed tasks must retry and recover"
    assert recovered[errored_task], "the errored task is retried, not silently dropped"
