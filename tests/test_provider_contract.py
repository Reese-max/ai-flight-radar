"""Exercise the installed v3 API, but replace its network fetch with fixtures."""
from datetime import datetime, timedelta
from types import SimpleNamespace as NS
import pytest


def segment(origin, destination):
    return NS(from_airport=NS(code=origin), to_airport=NS(code=destination),
              departure=NS(time=(10, 0)), arrival=NS(time=(14, 0)), duration=180, plane_type="Test")


def test_round_trip_two_direct_legs_are_not_one_transfer(monkeypatch):
    import fast_flights
    from providers.fast_flights_impl import FastFlightsProvider, rate_limiter
    monkeypatch.setattr(rate_limiter, "wait", lambda: None)
    observed_queries = []
    def fetch(query):
        observed_queries.append(query)
        return [NS(price=5500, airlines=["Test"], flights=[segment("TPE", "NRT"), segment("NRT", "TPE")])]
    monkeypatch.setattr(fast_flights, "get_flights", fetch)
    dep = datetime.utcnow().date()+timedelta(days=50)
    result = FastFlightsProvider().search("TPE", "NRT", dep.isoformat(), (dep+timedelta(days=4)).isoformat())
    assert result[0].is_direct and result[0].stops == 0
    assert observed_queries[0].currency == "TWD"
    assert observed_queries[0].get_trip_type() == "round-trip"


def test_upstream_errors_are_not_reported_as_empty_success(monkeypatch):
    import fast_flights
    from providers.fast_flights_impl import FastFlightsProvider, ProviderError, rate_limiter
    monkeypatch.setattr(rate_limiter, "wait", lambda: None)
    def fail(query):
        raise RuntimeError("Simulated HTTP failure")
    monkeypatch.setattr(fast_flights, "get_flights", fail)
    with pytest.raises(ProviderError):
        FastFlightsProvider().search("TPE", "NRT", "2027-01-01", "2027-01-05")


def test_malformed_price_does_not_enter_history(monkeypatch):
    import fast_flights
    from providers.fast_flights_impl import FastFlightsProvider, ProviderError, rate_limiter
    monkeypatch.setattr(rate_limiter, "wait", lambda: None)
    monkeypatch.setattr(fast_flights, "get_flights", lambda query: [NS(price="NaN")])
    with pytest.raises(ProviderError):
        FastFlightsProvider().search("TPE", "NRT", "2027-01-01", "2027-01-05")
