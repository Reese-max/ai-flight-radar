"""Offline contract tests for FliCustomProvider (Issue #8).

Fixtures are SimpleNamespace stand-ins for Fli ``FlightResult``/``FlightLeg`` —
no vendored import, no network. The provider's ``_fetch`` seam is monkeypatched.
"""
from datetime import datetime, timedelta
from types import SimpleNamespace as NS
import pytest

from providers.fli_custom import FliCustomProvider, FliProviderError
from providers.rate_limiter import rate_limiter


def leg(origin, destination, dep=(10, 0), arr=(14, 0), airline_name="Peach Aviation"):
    airline = NS(name="MM", value=airline_name)
    return NS(airline=airline, flight_number="MM001",
              departure_airport=NS(name=origin), arrival_airport=NS(name=destination),
              departure_datetime=datetime(2027, 1, 1, *dep),
              arrival_datetime=datetime(2027, 1, 1, *arr),
              duration=240, aircraft="A320")


def result(price, stops=0, origin="TPE", destination="NRT"):
    return NS(legs=[leg(origin, destination)], price=price, currency="TWD",
              duration=240, stops=stops, primary_airline=None,
              primary_airline_name="Peach Aviation")


@pytest.fixture(autouse=True)
def _no_rate_sleep(monkeypatch):
    monkeypatch.setattr(rate_limiter, "wait", lambda: None)


def test_round_trip_tuple_maps_to_direct_offer(monkeypatch):
    p = FliCustomProvider()
    dep = (datetime.utcnow().date() + timedelta(days=50)).isoformat()
    ret = (datetime.fromisoformat(dep) + timedelta(days=4)).date().isoformat()
    monkeypatch.setattr(p, "_fetch",
                        lambda f: [(result(None), result(10140, origin="NRT", destination="TPE"))])
    offers = p.search("TPE", "NRT", dep, ret)
    assert len(offers) == 1
    o = offers[0]
    assert o.provider == "fli_custom" and o.price_twd == 10140
    assert o.is_direct and o.stops == 0 and o.trip_type == "round-trip"
    assert o.duration_days == 4 and len(o.legs) == 2
    assert o.legs[0].flight_no == "MM001" and o.legs[0].plane_type == "A320"
    assert o.primary_airline == "Peach Aviation"


def test_one_way_list_maps(monkeypatch):
    p = FliCustomProvider()
    dep = (datetime.utcnow().date() + timedelta(days=50)).isoformat()
    monkeypatch.setattr(p, "_fetch", lambda f: [result(5500)])
    offers = p.search("TPE", "NRT", dep)
    assert offers[0].trip_type == "one-way" and offers[0].is_direct


def test_no_results_is_empty_not_error(monkeypatch):
    p = FliCustomProvider()
    monkeypatch.setattr(p, "_fetch", lambda f: None)
    assert p.search("TPE", "NRT", "2027-01-01", "2027-01-05") == []


def test_upstream_failure_is_error_not_empty(monkeypatch):
    p = FliCustomProvider()
    def boom(_filters):
        raise TimeoutError("simulated upstream timeout")
    monkeypatch.setattr(p, "_fetch", boom)
    with pytest.raises(FliProviderError):
        p.search("TPE", "NRT", "2027-01-01", "2027-01-05")


def test_all_priceless_rows_are_error_not_empty_success(monkeypatch):
    p = FliCustomProvider()
    monkeypatch.setattr(p, "_fetch", lambda f: [result(None), result(None)])
    with pytest.raises(FliProviderError):
        p.search("TPE", "NRT", "2027-01-01", "2027-01-05")


def test_malformed_price_rejected(monkeypatch):
    p = FliCustomProvider()
    monkeypatch.setattr(p, "_fetch", lambda f: [result("NaN"), result(0)])
    with pytest.raises(FliProviderError):
        p.search("TPE", "NRT", "2027-01-01")


def test_nonstop_constraint_drops_connecting_rows(monkeypatch):
    p = FliCustomProvider()
    monkeypatch.setattr(p, "_fetch",
                        lambda f: [result(4000, stops=1), result(8000)])
    offers = p.search("TPE", "NRT", "2027-01-01", max_stops=0)
    assert len(offers) == 1 and offers[0].price_twd == 8000


def test_unknown_fields_stay_unknown(monkeypatch):
    p = FliCustomProvider()
    bare = NS(legs=[NS(airline=None, flight_number=None,
                       departure_airport=NS(name="TPE"), arrival_airport=NS(name="NRT"),
                       departure_datetime=None, arrival_datetime=None,
                       duration=240, aircraft=None)],
              price=5500, duration=240, stops=0,
              primary_airline=None, primary_airline_name=None)
    monkeypatch.setattr(p, "_fetch", lambda f: [bare])
    offer = p.search("TPE", "NRT", "2027-01-01")[0]
    assert offer.legs[0].flight_no is None and offer.legs[0].plane_type == ""
    assert offer.primary_airline == "未知航空"


# --- Issue #8 phase 2: cabin / passenger / airline / multi-airport contract ---


def test_cabin_and_adults_reach_the_engine_filters(monkeypatch):
    p = FliCustomProvider()
    seen = []
    monkeypatch.setattr(p, "_fetch", lambda f: seen.append(f) or [result(5500)])
    dep = (datetime.utcnow().date() + timedelta(days=50)).isoformat()
    p.search("TPE", "NRT", dep, cabin="BUSINESS", adults=2)
    filters = seen[0]
    assert filters.seat_type.name == "BUSINESS"
    assert filters.passenger_info.adults == 2


def test_unknown_cabin_is_rejected_before_any_request(monkeypatch):
    p = FliCustomProvider()
    monkeypatch.setattr(p, "_fetch", lambda f: (_ for _ in ()).throw(AssertionError("must not fetch")))
    with pytest.raises(FliProviderError):
        p.search("TPE", "NRT", "2027-01-01", cabin="DELUXE")
    with pytest.raises(FliProviderError):
        p.search("TPE", "NRT", "2027-01-01", adults=0)
    with pytest.raises(FliProviderError):
        p.search("TPE", "NRT", "2027-01-01", adults=10)


def test_airline_include_filter_maps_iata_codes(monkeypatch):
    p = FliCustomProvider()
    seen = []
    monkeypatch.setattr(p, "_fetch", lambda f: seen.append(f) or [result(5500)])
    dep = (datetime.utcnow().date() + timedelta(days=50)).isoformat()
    p.search("TPE", "NRT", dep, airlines=["MM", "BR"])
    airlines = seen[0].airlines
    assert sorted(a.name for a in airlines) == ["BR", "MM"]
    with pytest.raises(FliProviderError):
        p.search("TPE", "NRT", dep, airlines=["XX"])


def test_multi_airport_search_is_a_single_bounded_request(monkeypatch):
    p = FliCustomProvider()
    seen = []
    monkeypatch.setattr(p, "_fetch", lambda f: seen.append(f) or [result(5500)])
    dep = (datetime.utcnow().date() + timedelta(days=50)).isoformat()
    offers = p.search("TPE", "NRT", dep,
                      origins=["TPE", "TSA"], destinations=["NRT", "HND"])
    assert len(seen) == 1  # one upstream call — never a per-pair explosion
    segment = seen[0].flight_segments[0]
    assert len(segment.departure_airport) == 2 and len(segment.arrival_airport) == 2
    assert offers[0].origin == "TPE+TSA" and offers[0].destination == "NRT+HND"


def test_multi_airport_side_is_hard_capped(monkeypatch):
    p = FliCustomProvider()
    monkeypatch.setattr(p, "_fetch", lambda f: (_ for _ in ()).throw(AssertionError("must not fetch")))
    with pytest.raises(FliProviderError):
        p.search("TPE", "NRT", "2027-01-01",
                 origins=["TPE", "TSA", "KHH", "RMQ"])
    with pytest.raises(FliProviderError):
        p.search("TPE", "NRT", "2027-01-01", origins=["TPE", "TPE"])
    with pytest.raises(FliProviderError):
        p.search("TPE", "NRT", "2027-01-01", origins=["TPE"], destinations=["TPE"])


def test_non_twd_currency_row_is_rejected_not_relabelled(monkeypatch):
    p = FliCustomProvider()
    priced_usd = result(300)
    priced_usd.currency = "USD"
    monkeypatch.setattr(p, "_fetch", lambda f: [priced_usd])
    with pytest.raises(FliProviderError):
        p.search("TPE", "NRT", "2027-01-01")


def test_booking_token_maps_to_booking_ref(monkeypatch):
    p = FliCustomProvider()
    row = result(5500)
    row.booking_token = "tok-abc"
    monkeypatch.setattr(p, "_fetch", lambda f: [row])
    offer = p.search("TPE", "NRT", "2027-01-01")[0]
    assert offer.booking_ref == "tok-abc"


def test_upstream_change_rows_are_error_not_empty_success(monkeypatch):
    """A wholesale response-shape change must not masquerade as zero fares."""
    p = FliCustomProvider()
    monkeypatch.setattr(p, "_fetch", lambda f: [object(), object()])
    with pytest.raises(FliProviderError):
        p.search("TPE", "NRT", "2027-01-01")


# --- Issue #8 phase 2: bounded flexible-date capability ---


def date_price(dep, ret=None, price=5500.0, currency="TWD"):
    return NS(date=(datetime.fromisoformat(dep),) if ret is None
              else (datetime.fromisoformat(dep), datetime.fromisoformat(ret)),
              price=price, currency=currency)


def test_search_dates_round_trip_normalizes_and_sorts(monkeypatch):
    from providers.fli_custom import models
    p = FliCustomProvider()
    dep = (datetime.utcnow().date() + timedelta(days=45)).isoformat()
    end = (datetime.fromisoformat(dep) + timedelta(days=30)).date().isoformat()
    ret_a = (datetime.fromisoformat(dep) + timedelta(days=4)).date().isoformat()
    ret_b = (datetime.fromisoformat(dep) + timedelta(days=5)).date().isoformat()
    calls = []
    def fake(filters):
        calls.append(filters)
        if filters.duration == 4:
            return [date_price(dep, ret_a, price=8200.0),
                    date_price(dep, ret_a, price=6400.0)]
        return [date_price(dep, ret_b, price=7100.0)]
    monkeypatch.setattr(p, "_fetch_dates", fake)
    offers = p.search_dates("TPE", "KIX", dep, end, trip_durations=[4, 5])
    assert len(calls) == 2  # one bounded calendar query per allowed duration
    assert all(isinstance(o, models.FlexibleDateOffer) for o in offers)
    assert [o.price_twd for o in offers] == [6400, 7100, 8200]
    assert offers[0].trip_type == "round-trip" and offers[0].duration_days == 4
    assert offers[0].provider == "fli_custom" and offers[0].origin == "TPE"


def test_search_dates_one_way_single_query(monkeypatch):
    p = FliCustomProvider()
    dep = (datetime.utcnow().date() + timedelta(days=45)).isoformat()
    end = (datetime.fromisoformat(dep) + timedelta(days=14)).date().isoformat()
    calls = []
    monkeypatch.setattr(p, "_fetch_dates",
                        lambda f: calls.append(f) or [date_price(dep, price=4300.0)])
    offers = p.search_dates("TPE", "NRT", dep, end)
    assert len(calls) == 1 and calls[0].duration is None
    assert offers[0].trip_type == "one-way" and offers[0].return_date is None


def test_search_dates_plan_is_bounded(monkeypatch):
    p = FliCustomProvider()
    dep = (datetime.utcnow().date() + timedelta(days=45)).isoformat()
    far = (datetime.fromisoformat(dep) + timedelta(days=90)).date().isoformat()
    near = (datetime.fromisoformat(dep) + timedelta(days=30)).date().isoformat()
    monkeypatch.setattr(p, "_fetch_dates", lambda f: (_ for _ in ()).throw(AssertionError("must not fetch")))
    with pytest.raises(FliProviderError):  # span beyond one upstream chunk
        p.search_dates("TPE", "KIX", dep, far)
    with pytest.raises(FliProviderError):  # durations x chunks exceed query budget
        p.search_dates("TPE", "KIX", dep, near, trip_durations=[3, 4, 5, 6, 7])
    with pytest.raises(FliProviderError):  # garbage duration is never a plan
        p.search_dates("TPE", "KIX", dep, near, trip_durations=[4, 40])
    plan = p.flexible_plan("TPE", "KIX", dep, near, trip_durations=[4, 5, 6])
    assert len(plan) == 3 and {q.duration_days for q in plan} == {4, 5, 6}
    assert all(q.trip_type == "round-trip" for q in plan)


def test_search_dates_never_exceeds_result_budget(monkeypatch):
    p = FliCustomProvider()
    dep = (datetime.utcnow().date() + timedelta(days=45)).isoformat()
    end = (datetime.fromisoformat(dep) + timedelta(days=30)).date().isoformat()
    rows = [date_price(dep, price=1000.0 + i) for i in range(30)]
    monkeypatch.setattr(p, "_fetch_dates", lambda f: rows)
    offers = p.search_dates("TPE", "NRT", dep, end, max_results=10)
    assert len(offers) == 10
    assert [o.price_twd for o in offers] == sorted(o.price_twd for o in offers)


def test_search_dates_empty_and_failure_semantics(monkeypatch):
    p = FliCustomProvider()
    dep = (datetime.utcnow().date() + timedelta(days=45)).isoformat()
    end = (datetime.fromisoformat(dep) + timedelta(days=30)).date().isoformat()
    monkeypatch.setattr(p, "_fetch_dates", lambda f: None)
    assert p.search_dates("TPE", "NRT", dep, end) == []
    def boom(_filters):
        raise TimeoutError("simulated upstream timeout")
    monkeypatch.setattr(p, "_fetch_dates", boom)
    with pytest.raises(FliProviderError):
        p.search_dates("TPE", "NRT", dep, end)


def test_search_dates_drops_out_of_plan_rows(monkeypatch):
    """Dates outside the window, wrong durations, bad prices/currency are dropped;
    a wholly malformed batch is an error, never a clean sweep."""
    p = FliCustomProvider()
    dep = (datetime.utcnow().date() + timedelta(days=45)).isoformat()
    end = (datetime.fromisoformat(dep) + timedelta(days=30)).date().isoformat()
    good_ret = (datetime.fromisoformat(dep) + timedelta(days=4)).date().isoformat()
    wrong_ret = (datetime.fromisoformat(dep) + timedelta(days=9)).date().isoformat()
    outside = (datetime.fromisoformat(end) + timedelta(days=1)).isoformat()
    rows = [date_price(dep, good_ret, price=6400.0),                    # keep
            date_price(dep, wrong_ret, price=3000.0),                   # wrong duration
            date_price(outside, None, price=2000.0),                    # depart out of window
            date_price(dep, good_ret, price=0.0),                       # bad price
            date_price(dep, good_ret, price=5000.0, currency="USD")]    # wrong currency
    monkeypatch.setattr(p, "_fetch_dates", lambda f: rows)
    offers = p.search_dates("TPE", "KIX", dep, end, trip_durations=[4])
    assert len(offers) == 1 and offers[0].price_twd == 6400
    monkeypatch.setattr(p, "_fetch_dates", lambda f: [object(), "junk"])
    with pytest.raises(FliProviderError):
        p.search_dates("TPE", "KIX", dep, end, trip_durations=[4])


def test_search_dates_nonnumeric_price_is_dropped_not_raised(monkeypatch):
    """``Decimal("abc")`` raises InvalidOperation, not ValueError — a malformed
    price must degrade to a dropped row, never escape the per-row guard."""
    p = FliCustomProvider()
    dep = (datetime.utcnow().date() + timedelta(days=45)).isoformat()
    end = (datetime.fromisoformat(dep) + timedelta(days=30)).date().isoformat()
    rows = [date_price(dep, price="abc"), date_price(dep, price=4300.0)]
    monkeypatch.setattr(p, "_fetch_dates", lambda f: rows)
    offers = p.search_dates("TPE", "NRT", dep, end)
    assert len(offers) == 1 and offers[0].price_twd == 4300


def test_search_dates_rejects_mixed_type_durations(monkeypatch):
    p = FliCustomProvider()
    dep = (datetime.utcnow().date() + timedelta(days=45)).isoformat()
    end = (datetime.fromisoformat(dep) + timedelta(days=30)).date().isoformat()
    monkeypatch.setattr(p, "_fetch_dates", lambda f: (_ for _ in ()).throw(AssertionError("must not fetch")))
    with pytest.raises(FliProviderError):
        p.search_dates("TPE", "KIX", dep, end, trip_durations=[4, "x"])
    with pytest.raises(FliProviderError):
        p.search_dates("TPE", "KIX", dep, end, trip_durations=[])


def test_empty_airline_list_is_rejected(monkeypatch):
    """An explicit empty include list must not silently widen to any airline."""
    p = FliCustomProvider()
    monkeypatch.setattr(p, "_fetch", lambda f: (_ for _ in ()).throw(AssertionError("must not fetch")))
    with pytest.raises(FliProviderError):
        p.search("TPE", "NRT", "2027-01-01", airlines=[])


def test_inbound_non_twd_currency_rejects_the_tuple(monkeypatch):
    """Round-trip: a foreign currency on the priced inbound leg invalidates
    the whole offer — never a mislabelled TWD price."""
    p = FliCustomProvider()
    dep = (datetime.utcnow().date() + timedelta(days=50)).isoformat()
    ret = (datetime.fromisoformat(dep) + timedelta(days=4)).date().isoformat()
    inbound = result(10140, origin="NRT", destination="TPE")
    inbound.currency = "JPY"
    monkeypatch.setattr(p, "_fetch", lambda f: [(result(None), inbound)])
    with pytest.raises(FliProviderError):
        p.search("TPE", "NRT", dep, ret)


# --- Issue #8 phase 2: provider selection + calibration command ---


def test_fallback_provider_is_configurable_and_safe(monkeypatch):
    from providers import selector
    monkeypatch.delenv("RADAR_FALLBACK_PROVIDER", raising=False)
    assert type(selector.get_fallback_provider()).__name__ == "FastFlightsProvider"
    monkeypatch.setenv("RADAR_FALLBACK_PROVIDER", "fli")
    assert type(selector.get_fallback_provider()).__name__ == "FliCustomProvider"
    monkeypatch.setenv("RADAR_FALLBACK_PROVIDER", "bogus")
    with pytest.raises(ValueError):
        selector.get_fallback_provider()


def test_calibration_dry_run_makes_no_network_calls():
    import importlib.util
    from pathlib import Path
    script = Path(__file__).resolve().parents[1] / "cloudflare" / "scripts" / "calibrate_fli.py"
    spec = importlib.util.spec_from_file_location("calibrate_fli", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    plan = mod.build_plan()
    assert plan["mode"] == "dry-run" and plan["network_calls"] == 0
    assert 1 <= len(plan["cases"]) <= 12
    assert all(c["origin"] in {"TPE", "TSA", "KHH", "RMQ"} for c in plan["cases"])
    assert {c["kind"] for c in plan["cases"]} == {"search", "dates"}
    assert any(c.get("expect") == "empty-allowed" for c in plan["cases"])
