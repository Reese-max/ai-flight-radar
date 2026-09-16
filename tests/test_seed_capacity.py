"""Issue #6: seeded route demand must not exceed authorized collector capacity.

Invariant (documented in cloudflare/src/store.mjs):
    active_tasks <= revisit_hours * scheduled_runs_per_hour * max_tasks_per_run

The test parses the actual sources — collector.py route sets, collector.yml
cron + --max-tasks, store.mjs revisit constant — so a future change to any
knob fails loudly instead of silently re-creating the 48/6h/6-per-hour deficit.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _set_members(source: str, name: str) -> set[str]:
    m = re.search(rf"{name}\s*=\s*\{{([^}}]+)\}}", source)
    assert m, f"{name} set not found"
    return {s.strip().strip("'\"") for s in m.group(1).split(",") if s.strip()}


def _seed_task_count() -> int:
    collector = (ROOT / "cloudflare/scripts/collector.py").read_text(encoding='utf-8')
    tasks_py = (ROOT / "cloudflare/scripts/tasks.py").read_text(encoding='utf-8')
    origins = _set_members(collector, "ORIGINS")
    destinations = _set_members(collector, "DESTINATIONS")
    assert "for o in sorted(ORIGINS) for d in sorted(DESTINATIONS)" in tasks_py, (
        "tasks.py no longer seeds the full Cartesian product; recount demand"
    )
    return len(origins) * len(destinations)


def _scheduled_claims_per_hour() -> tuple[int, int]:
    wf = (ROOT / ".github/workflows/collector.yml").read_text(encoding='utf-8')
    cron = re.search(r"cron:\s*'([^']+)'", wf)
    assert cron, "collector.yml cron not found"
    runs_per_hour = len(cron.group(1).split(","))
    m = re.search(r"collector\.py --execute --max-tasks (\d+)", wf)
    assert m, "--max-tasks argument not found in collector.yml"
    return runs_per_hour, int(m.group(1))


def _revisit_hours() -> float:
    store = (ROOT / "cloudflare/src/store.mjs").read_text(encoding='utf-8')
    m = re.search(r"REVISIT_OK_MS\s*=\s*(\d+)\s*\*\s*3600000", store)
    assert m, "REVISIT_OK_MS constant not found in store.mjs"
    assert "REVISIT_OK_MS" in store.split("next_run=?")[0] or "REVISIT_OK_MS" in store
    return float(m.group(1))


def test_seeded_demand_fits_scheduled_capacity():
    tasks = _seed_task_count()
    runs_per_hour, max_tasks = _scheduled_claims_per_hour()
    revisit_h = _revisit_hours()
    demand_per_hour = tasks / revisit_h
    capacity_per_hour = runs_per_hour * max_tasks
    assert demand_per_hour <= capacity_per_hour, (
        f"{tasks} tasks / {revisit_h}h revisit needs {demand_per_hour:.1f} "
        f"claims/hour but the scheduled collector supplies only "
        f"{capacity_per_hour}/hour ({runs_per_hour} runs × {max_tasks} tasks)"
    )


def test_collector_batch_cap_matches_workflow():
    """collector.py hard-bounds --max-tasks at 3; workflow must not exceed it."""
    collector = (ROOT / "cloudflare/scripts/collector.py").read_text(encoding='utf-8')
    m = re.search(r"not 1 <= max_tasks <= (\d+)", collector)
    assert m, "collector.py batch cap not found"
    _, workflow_max = _scheduled_claims_per_hour()
    assert workflow_max <= int(m.group(1)), (
        "workflow requests more tasks per run than collector.py permits"
    )


def test_error_revisit_is_shorter_than_ok():
    """Failed tasks retry after 1h — faster than the 8h ok revisit — so
    upstream errors degrade coverage explicitly, not silently."""
    store = (ROOT / "cloudflare/src/store.mjs").read_text(encoding='utf-8')
    assert "clean.outcome==='error'?3600000" in store
