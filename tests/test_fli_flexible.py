"""Issue #8 phase 2: filter mapping, bounded flexible dates, route cap, fallback."""
from datetime import datetime, timedelta
from types import SimpleNamespace as NS
import pytest

from providers.fli_custom import FliCustomProvider, FliProviderError
from providers.rate_limiter import rate_limiter


@pytest.fixture(autouse=True)
def _no_rate_sleep(monkeypatch):
    monkeypatch.setattr(rate_limiter, "wait", lambda: None)


@pytest.fixture(autouse=True)
def _offline_vendored_models(monkeypatch):
    """Load real Fli models while keeping HTTP client imports out of unit tests."""
    from providers.fli_custom import dates, provider

    provider._ensure_fli_path()
    from fli.models import (Airport, DateSearchFilters, FlightSearchFilters,
                            FlightSegment, MaxStops, PassengerInfo, SeatType,
                            TripType)

    monkeypatch.setattr(provider, "_load_engine", lambda: (
        Airport, FlightSearchFilters, FlightSegment, MaxStops, PassengerInfo,
        SeatType, TripType, object,
    ))
    monkeypatch.setattr(dates, "_load_dates_engine", lambda: (
        Airport, DateSearchFilters, FlightSegment, MaxStops, PassengerInfo,
        SeatType, TripType, object,
    ))


def _dep(days=50):
    return (datetime.utcnow().date() + timedelta(days=days)).isoformat()


def test_cabin_and_adults_mapped_into_filters(monkeypatch):
    p = FliCustomProvider()
    seen = {}
    def fake_fetch(f):
        seen["f"] = f
        return []
    monkeypatch.setattr(p, "_fetch", fake_fetch)
    p.search("TPE", "NRT", _dep(), cabin="BUSINESS", adults=2)
    f = seen["f"]
    assert f.seat_type.name == "BUSINESS"
    assert f.passenger_info.adults == 2


def test_airlines_mapped_into_filters(monkeypatch):
    p = FliCustomProvider()
    seen = {}
    def fake_fetch(f):
        seen["f"] = f
        return []
    monkeypatch.setattr(p, "_fetch", fake_fetch)
    p.search("TPE", "NRT", _dep(), airlines=["MM", "BR"])
    assert [a.name for a in seen["f"].airlines] == ["MM", "BR"]


def test_unknown_cabin_rejected_before_fetch(monkeypatch):
    p = FliCustomProvider()
    called = []
    monkeypatch.setattr(p, "_fetch", lambda f: called.append(f) or [])
    with pytest.raises(FliProviderError):
        p.search("TPE", "NRT", _dep(), cabin="YACHT")
    assert not called


def test_unknown_airline_rejected_before_fetch(monkeypatch):
    p = FliCustomProvider()
    called = []
    monkeypatch.setattr(p, "_fetch", lambda f: called.append(f) or [])
    with pytest.raises(FliProviderError):
        p.search("TPE", "NRT", _dep(), airlines=["XX99"])
    assert not called


def test_zero_adults_rejected(monkeypatch):
    p = FliCustomProvider()
    with pytest.raises(FliProviderError):
        p.search("TPE", "NRT", _dep(), adults=0)


def test_flexible_dates_normalizes_and_sorts(monkeypatch):
    from providers.fli_custom import dates
    rows = [NS(date=(datetime(2027, 2, 10), datetime(2027, 2, 14)), price=8200.0, currency="TWD"),
            NS(date=(datetime(2027, 2, 3), datetime(2027, 2, 7)), price=6100.0, currency="TWD")]
    monkeypatch.setattr(dates, "_fetch_dates", lambda f: rows)
    out = dates.search_flexible_dates("TPE", "KIX", "2027-02-01", "2027-03-01", trip_duration_days=4)
    assert [r.price_twd for r in out] == [6100, 8200]
    assert out[0].origin == "TPE" and out[0].destination == "KIX"
    assert out[0].depart_date == "2027-02-03" and out[0].return_date == "2027-02-07"


def test_flexible_dates_rejects_rows_outside_range_or_duration(monkeypatch):
    from providers.fli_custom import dates
    rows = [
        NS(date=(datetime(2027, 1, 31), datetime(2027, 2, 4)), price=5000),
        NS(date=(datetime(2027, 2, 3), datetime(2027, 2, 9)), price=6000),
    ]
    monkeypatch.setattr(dates, "_fetch_dates", lambda f: rows)
    with pytest.raises(FliProviderError, match="none validated"):
        dates.search_flexible_dates(
            "TPE", "KIX", "2027-02-01", "2027-02-20", trip_duration_days=4)


def test_flexible_dates_preserves_unknown_currency():
    from providers.fli_custom import dates
    row = NS(date=(datetime(2027, 2, 3), datetime(2027, 2, 7)), price=6100)
    result = dates._normalize_row(
        row, "TPE", "KIX", datetime(2027, 2, 1).date(),
        datetime(2027, 2, 20).date(), 4)
    assert result.currency is None


def test_flexible_dates_empty_is_empty_not_error(monkeypatch):
    from providers.fli_custom import dates
    monkeypatch.setattr(dates, "_fetch_dates", lambda f: None)
    assert dates.search_flexible_dates("TPE", "KIX", "2027-02-01", "2027-02-20", trip_duration_days=4) == []


def test_flexible_dates_upstream_failure_is_error(monkeypatch):
    from providers.fli_custom import dates
    def boom(_f):
        raise TimeoutError("simulated")
    monkeypatch.setattr(dates, "_fetch_dates", boom)
    with pytest.raises(FliProviderError):
        dates.search_flexible_dates("TPE", "KIX", "2027-02-01", "2027-02-20", trip_duration_days=4)


def test_flexible_dates_rejects_span_over_budget():
    from providers.fli_custom import dates
    with pytest.raises(FliProviderError):
        dates.search_flexible_dates("TPE", "KIX", "2027-02-01", "2027-06-30", trip_duration_days=4)


@pytest.mark.parametrize("kwargs", [
    {"max_span_days": 62},
    {"max_results": 51},
    {"max_span_days": 0},
    {"max_results": True},
    {"trip_duration_days": 31},
    {"max_stops": 3},
])
def test_flexible_search_rejects_overrides_and_filters_before_engine(monkeypatch, kwargs):
    from providers.fli_custom import dates
    monkeypatch.setattr(dates, "_load_dates_engine",
                        lambda: pytest.fail("invalid request reached the Fli engine"))
    args = {"trip_duration_days": 4}
    args.update(kwargs)
    with pytest.raises(FliProviderError):
        dates.search_flexible_dates("TPE", "KIX", "2027-02-01", "2027-02-20", **args)


def test_flexible_date_search_maps_supported_airline_filter(monkeypatch):
    from providers.fli_custom import dates
    seen = {}
    def fake_fetch(filters):
        seen["filters"] = filters
        return []
    monkeypatch.setattr(dates, "_fetch_dates", fake_fetch)
    dates.search_flexible_dates("TPE", "KIX", "2027-02-01", "2027-02-20",
                                trip_duration_days=4, airlines=["MM", "BR"])
    assert [airline.name for airline in seen["filters"].airlines] == ["MM", "BR"]


def test_flexible_dates_rejects_bad_duration():
    from providers.fli_custom import dates
    with pytest.raises(FliProviderError):
        dates.search_flexible_dates("TPE", "KIX", "2027-02-01", "2027-02-20", trip_duration_days=0)


def test_route_matrix_is_bounded():
    from providers.fli_custom.plan import bound_route_matrix
    with pytest.raises(ValueError):
        bound_route_matrix(["TPE", "TSA", "KHH"], ["NRT", "KIX", "FUK"])
    pairs = bound_route_matrix(["TPE", "TSA"], ["NRT", "KIX"], max_routes=8)
    assert pairs == [("TPE", "NRT"), ("TPE", "KIX"), ("TSA", "NRT"), ("TSA", "KIX")]


def test_route_matrix_rejects_worst_case_before_product_expansion(monkeypatch):
    from providers.fli_custom import plan

    class SizedWithoutIteration:
        def __len__(self):
            return 1000

        def __iter__(self):
            raise AssertionError("oversized route inputs must not be expanded")

    monkeypatch.setattr(plan, "product",
                        lambda *_args: pytest.fail("product must not be called before cap check"))
    with pytest.raises(ValueError, match="budget"):
        plan.bound_route_matrix(SizedWithoutIteration(), SizedWithoutIteration())
    with pytest.raises(ValueError, match="max_routes"):
        plan.bound_route_matrix(["TPE"], ["NRT"], max_routes=plan.MAX_ROUTES + 1)


def test_provider_chain_defaults_safe(monkeypatch):
    monkeypatch.delenv("RADAR_PRIMARY_PROVIDER", raising=False)
    monkeypatch.delenv("RADAR_FALLBACK_PROVIDER", raising=False)
    from providers.selector import get_provider_chain
    chain = get_provider_chain()
    assert [type(p).__name__ for p in chain] == ["FastFlightsProvider"]


def test_provider_chain_includes_explicit_fallback(monkeypatch):
    monkeypatch.setenv("RADAR_PRIMARY_PROVIDER", "fli")
    monkeypatch.setenv("RADAR_FALLBACK_PROVIDER", "fast_flights")
    from providers.selector import get_provider_chain
    chain = get_provider_chain()
    assert [type(p).__name__ for p in chain] == ["FliCustomProvider", "FastFlightsProvider"]


def test_fallback_only_setting_keeps_safe_primary_first(monkeypatch):
    monkeypatch.delenv("RADAR_PRIMARY_PROVIDER", raising=False)
    monkeypatch.setenv("RADAR_FALLBACK_PROVIDER", "fli")
    from providers.selector import get_provider_chain
    assert [type(p).__name__ for p in get_provider_chain()] == [
        "FastFlightsProvider", "FliCustomProvider"]


def test_provider_search_uses_fallback_after_typed_failure(monkeypatch):
    from providers import selector
    from providers.fli_custom.errors import FliSearchError

    calls = []

    class Primary:
        name = "fli_custom"

        def search(self, *_args, **_kwargs):
            calls.append(self.name)
            raise FliSearchError("simulated upstream timeout")

    class Fallback:
        name = "fast_flights"

        def search(self, *_args, **_kwargs):
            calls.append(self.name)
            return ["fallback offer"]

    monkeypatch.setattr(selector, "get_provider_chain", lambda: [Primary(), Fallback()])
    assert selector.search_with_provider_chain("TPE", "NRT", _dep()) == ["fallback offer"]
    assert calls == ["fli_custom", "fast_flights"]


def test_successful_no_results_does_not_trigger_fallback(monkeypatch):
    from providers import selector

    calls = []

    class Provider:
        def __init__(self, name, result):
            self.name, self.result = name, result

        def search(self, *_args, **_kwargs):
            calls.append(self.name)
            return self.result

    monkeypatch.setattr(selector, "get_provider_chain", lambda: [
        Provider("fli_custom", []), Provider("fast_flights", ["unexpected"])
    ])
    assert selector.search_with_provider_chain("TPE", "NRT", _dep()) == []
    assert calls == ["fli_custom"]


def test_all_provider_failures_remain_typed_and_observable(monkeypatch):
    from providers import selector
    from providers.fast_flights_impl import ProviderError
    from providers.fli_custom.errors import FliSearchError

    class Failing:
        def __init__(self, name, error):
            self.name, self.error = name, error

        def search(self, *_args, **_kwargs):
            raise self.error

    failures = [
        ("fli_custom", FliSearchError("timeout")),
        ("fast_flights", ProviderError("upstream unavailable")),
    ]
    monkeypatch.setattr(selector, "get_provider_chain", lambda: [
        Failing(name, error) for name, error in failures
    ])
    with pytest.raises(selector.ProviderChainError) as caught:
        selector.search_with_provider_chain("TPE", "NRT", _dep())
    assert [(name, type(error)) for name, error in caught.value.failures] == [
        ("fli_custom", FliSearchError), ("fast_flights", ProviderError)
    ]


def test_adapter_validation_error_does_not_trigger_fallback(monkeypatch):
    from providers import selector

    calls = []

    class InvalidRequest:
        name = "fli_custom"

        def search(self, *_args, **_kwargs):
            calls.append(self.name)
            raise FliProviderError("invalid cabin")

    class Fallback:
        name = "fast_flights"

        def search(self, *_args, **_kwargs):
            calls.append(self.name)
            return ["fallback offer"]

    monkeypatch.setattr(selector, "get_provider_chain", lambda: [InvalidRequest(), Fallback()])
    with pytest.raises(FliProviderError, match="invalid cabin"):
        selector.search_with_provider_chain("TPE", "NRT", _dep())
    assert calls == ["fli_custom"]


def test_missing_fast_flights_engine_is_a_typed_search_failure(monkeypatch):
    import builtins
    from providers.fast_flights_impl import FastFlightsProvider, ProviderError

    real_import = builtins.__import__

    def missing_fast_flights(name, *args, **kwargs):
        if name == "fast_flights":
            raise ModuleNotFoundError("test-only missing provider engine")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing_fast_flights)
    with pytest.raises(ProviderError, match="engine unavailable"):
        FastFlightsProvider().search("TPE", "NRT", _dep())


def test_missing_fli_date_engine_is_a_typed_search_failure(monkeypatch):
    from providers.fli_custom import dates
    from providers.fli_custom.errors import FliSearchError

    def unavailable():
        raise ModuleNotFoundError("test-only missing engine")

    monkeypatch.setattr(dates, "_load_dates_engine", unavailable)
    with pytest.raises(FliSearchError, match="engine unavailable"):
        dates.search_flexible_dates(
            "TPE", "KIX", "2027-02-01", "2027-02-20", trip_duration_days=4)
