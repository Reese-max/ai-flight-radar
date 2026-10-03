"""Issue #8 phase 2: filter mapping, bounded flexible dates, route cap, fallback."""
from datetime import datetime, timedelta
from types import SimpleNamespace as NS
import pytest

from providers.fli_custom import FliCustomProvider, FliProviderError
from providers.rate_limiter import rate_limiter


@pytest.fixture(autouse=True)
def _no_rate_sleep(monkeypatch):
    monkeypatch.setattr(rate_limiter, "wait", lambda: None)


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
