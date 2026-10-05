"""Seeded route coverage must fit the bounded collector's service capacity (#6).

Planned demand is `active routes / revisit hours`. Planned service capacity is
`scheduled runs per hour * max tasks per run`, itself capped by the deployed
hourly claim budget. The checked-in configuration has to satisfy

    active routes / revisit hours <= runs per hour * max tasks per run
    active routes / revisit hours <= deployed hourly claim budget

so no route can be systematically starved under normal, zero-error operation.
"""
import json
from pathlib import Path
import re
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'cloudflare' / 'scripts'))

PLAN_KEYS = ('active_routes', 'revisit_hours', 'runs_per_hour', 'max_tasks_per_run', 'claim_budget')


def collector():
    """Import the collector lazily so an absent contract fails as a test, not a collection error."""
    import collector as module
    return module


def plan(**overrides):
    return collector().coverage_plan(**overrides)


def simulate(**overrides):
    checked_in = plan()
    arguments = {key: checked_in[key] for key in PLAN_KEYS}
    arguments.update(overrides)
    return collector().simulate_coverage(**arguments)


def test_seeded_route_matrix_is_the_active_task_count_of_the_contract():
    from tasks import ROUTES
    assert len(ROUTES) == plan()['active_routes'] == 48


def test_checked_in_configuration_is_sustainable():
    checked_in = plan()
    assert checked_in['sustainable'] is True, checked_in
    assert checked_in['demand_per_hour'] <= checked_in['capacity_per_hour']


def test_checked_in_contract_keeps_headroom_over_the_documented_capacity():
    checked_in = plan()
    assert checked_in['active_routes'] == 48
    assert checked_in['revisit_hours'] == 24
    assert checked_in['runs_per_hour'] == 2
    assert checked_in['max_tasks_per_run'] == 3
    assert checked_in['claim_budget'] == 3
    assert checked_in['capacity_per_hour'] == 3.0
    assert checked_in['demand_per_hour'] == 2.0
    assert checked_in['headroom_per_hour'] == 1.0


def test_the_reported_48_routes_at_six_hours_mismatch_is_not_sustainable():
    starved = plan(revisit_hours=6)
    assert starved['demand_per_hour'] == 8.0
    assert starved['capacity_per_hour'] == 3.0
    assert starved['sustainable'] is False


def test_demand_may_not_exceed_the_deployed_claim_budget():
    starved = plan(claim_budget=1)
    assert starved['capacity_per_hour'] == 1.0
    assert starved['sustainable'] is False


def test_every_active_route_is_serviced_within_one_revisit_window():
    summary = simulate()
    assert summary['degraded'] is False
    assert summary['unserved'] == []
    assert summary['routes_delayed'] == []
    assert summary['max_interval_hours'] <= summary['revisit_hours']
    assert summary['target_met'] is True


def test_one_error_batch_is_reported_as_degraded_even_when_headroom_absorbs_it():
    summary = simulate(error_runs=[0])
    assert summary['errors'] == 1
    assert summary['degraded'] is True
    assert summary['target_met'] is False
    assert summary['max_interval_hours'] <= summary['revisit_hours']


def test_the_pre_fix_six_hour_cadence_starves_routes_in_the_same_simulation():
    starved = simulate(revisit_hours=6, windows=4)
    assert starved['routes_delayed']
    assert starved['max_interval_hours'] > 6
    assert starved['target_met'] is False


def test_sustained_upstream_failure_reports_starved_coverage():
    starved = simulate(error_runs=range(0, 100))
    assert starved['served'] == 0
    assert starved['unserved']
    assert starved['degraded'] is True
    assert starved['target_met'] is False


def test_a_cadence_that_is_not_hourly_fails_closed():
    with pytest.raises(collector().SafeFailure):
        collector().cron_runs_per_hour('0 6 * * *')
    with pytest.raises(collector().SafeFailure):
        collector().cron_runs_per_hour('*/7 * * * *')
    assert collector().cron_runs_per_hour('17,47 * * * *') == 2


def test_the_plan_is_derived_from_the_checked_in_configuration_files(tmp_path):
    write_configuration(tmp_path)
    derived = collector().coverage_plan(root=tmp_path)
    assert derived['active_routes'] == 48
    assert derived['revisit_hours'] == 24
    assert derived['runs_per_hour'] == 2
    assert derived['max_tasks_per_run'] == 3
    assert derived['claim_budget'] == 3
    assert derived['sustainable'] is True


def test_a_store_that_stops_using_the_shared_interval_constants_fails_closed(tmp_path):
    write_configuration(tmp_path, store='now+6*3600000\n')
    with pytest.raises(collector().SafeFailure):
        collector().coverage_plan(root=tmp_path)


def test_a_revisit_window_that_is_not_derived_from_the_declared_hours_fails_closed(tmp_path):
    write_configuration(tmp_path, logic='export const REVISIT_HOURS=12,REVISIT_MS=6*3600000;\n'
        'export const ERROR_BACKOFF_MS=HOUR;export const TTL=REVISIT_MS;')
    with pytest.raises(collector().SafeFailure):
        collector().coverage_plan(root=tmp_path)


def test_a_generated_deploy_config_is_the_budget_that_actually_ships(tmp_path):
    write_configuration(tmp_path)
    assert collector().coverage_plan(root=tmp_path)['budget_source'] == 'wrangler.json'
    (tmp_path / 'cloudflare/wrangler.deploy.json').write_text(
        json.dumps({'vars': {'MAX_SEARCHES_PER_HOUR': '1'}}) + '\n', encoding='utf-8')
    deployed = collector().coverage_plan(root=tmp_path)
    assert deployed['budget_source'] == 'wrangler.deploy.json'
    assert deployed['claim_budget'] == 1
    assert deployed['sustainable'] is False


def test_the_local_development_server_uses_the_checked_in_claim_budget():
    budget = re.search(r"MAX_SEARCHES_PER_HOUR:'(\d+)'",
                       (ROOT / 'cloudflare/scripts/local-server.mjs').read_text(encoding='utf-8'))
    assert budget is not None
    assert int(budget.group(1)) == plan()['claim_budget'] == 3


def write_configuration(root, logic='export const REVISIT_HOURS=24,REVISIT_MS=REVISIT_HOURS*HOUR;\n'
        'export const ERROR_BACKOFF_MS=HOUR;export const TTL=REVISIT_MS;\n',
        store='REVISIT_MS,ERROR_BACKOFF_MS\n'):
    (root / 'cloudflare/src').mkdir(parents=True, exist_ok=True)
    (root / '.github/workflows').mkdir(parents=True, exist_ok=True)
    (root / 'cloudflare/src/logic.mjs').write_text(logic, encoding='utf-8')
    (root / 'cloudflare/src/store.mjs').write_text(store, encoding='utf-8')
    (root / 'cloudflare/wrangler.json').write_text(
        json.dumps({'vars': {'MAX_SEARCHES_PER_HOUR': '3'}}) + '\n', encoding='utf-8')
    (root / '.github/workflows/collector.yml').write_text(
        "  schedule:\n    - cron: '17,47 * * * *'\n"
        '        run: python cloudflare/scripts/collector.py --execute --max-tasks 3\n', encoding='utf-8')


def test_replay_enforces_the_hourly_claim_budget_even_when_cron_can_offer_more():
    summary = simulate(revisit_hours=12, claim_budget=3)
    assert summary['claim_budget'] == 3
    assert summary['max_claims_per_hour'] <= 3
    assert summary['routes_delayed']
    assert summary['target_met'] is False


def test_checked_in_replay_never_claims_more_than_the_preserved_three_per_hour():
    summary = simulate()
    assert summary['claim_budget'] == 3
    assert summary['max_claims_per_hour'] <= 3
    assert summary['target_met'] is True
