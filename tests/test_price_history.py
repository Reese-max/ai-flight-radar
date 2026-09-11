from datetime import datetime, timedelta, timezone
import pytest
from engine.price_history import query_key, summarize_history

NOW = datetime(2026, 9, 11, 12)


def test_no_fabricated_cold_start_benchmark():
    ref = summarize_history([], before=NOW)
    assert ref["avg_30d"] is None
    assert ref["is_cold_start"] and not ref["sufficient_history"]


def test_current_and_future_batches_are_excluded():
    rows = [(NOW - timedelta(days=1), 8000), (NOW, 1000), (NOW + timedelta(seconds=1), 1)]
    assert summarize_history(rows, before=NOW)["avg_30d"] == 8000


def test_poll_frequency_does_not_inflate_baseline():
    rows = [(NOW - timedelta(days=1), 5000)] * 100
    rows += [(NOW - timedelta(days=2), 10000)]
    assert summarize_history(rows, before=NOW)["avg_30d"] == 7500


def test_three_rows_are_not_ninety_days_of_history():
    ref = summarize_history([(NOW - timedelta(hours=i), 8000) for i in range(1, 4)], before=NOW)
    assert ref["is_cold_start"]
    assert not ref["has_90d_coverage"]


def test_five_distinct_days_enable_a_limited_reference():
    ref = summarize_history([(NOW - timedelta(days=i), 8000) for i in range(1, 6)], before=NOW)
    assert ref["sufficient_history"]
    assert ref["observed_days"] == 5
    assert not ref["has_90d_coverage"]


def test_ninety_day_claim_requires_long_observed_coverage():
    rows = [(NOW - timedelta(days=i), 8000) for i in range(1, 91)]
    assert summarize_history(rows, before=NOW)["has_90d_coverage"]


def test_sparse_long_history_is_not_adequate_coverage():
    rows = [(NOW-timedelta(days=i), 8000) for i in [1, 30, 60, 90]]
    assert not summarize_history(rows, before=NOW)["has_90d_coverage"]


@pytest.mark.parametrize("price", [0, -1, float("nan"), float("inf"), True, "8000"])
def test_invalid_prices_are_ignored(price):
    assert summarize_history([(NOW-timedelta(days=1), price)], before=NOW)["sample_count"] == 0


def test_timezone_aware_input_matches_existing_utc_storage():
    at = (NOW-timedelta(days=1)).replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=8)))
    assert summarize_history([(at, 8000)], before=NOW)["avg_30d"] == 8000


def test_windows_exclude_old_observations_but_keep_observed_minimum():
    ref = summarize_history([(NOW-timedelta(days=40), 5000)], before=NOW)
    assert ref["avg_30d"] is None and ref["avg_90d"] == 5000
    assert ref["min_historical"] == 5000


def test_query_keys_isolate_dates_source_currency_and_passengers():
    args = ("TPE", "NRT", "2026-11-01", "2026-11-05")
    original = query_key(*args)
    assert original == query_key("tpe", "nrt", args[2], args[3])
    assert original != query_key(*args, currency="USD")
    assert original != query_key(*args, source="another_provider")
    assert original != query_key(*args, direct_only=False)
    assert original != query_key(*args, adults=2)
    assert original != query_key(*args, cabin="business")
    assert original != query_key("TPE", "NRT", "2026-11-02", "2026-11-06")


@pytest.mark.parametrize("departure,return_date", [("bad", "2026-11-05"), ("2026-11-05", "2026-11-01")])
def test_invalid_dates_are_rejected(departure, return_date):
    with pytest.raises(ValueError):
        query_key("TPE", "NRT", departure, return_date)
