"""Offline contract tests for FliCustomProvider (Issue #8).

Fixtures are SimpleNamespace stand-ins for Fli ``FlightResult``/``FlightLeg`` —
no vendored import, no network. The provider's ``_fetch`` seam is monkeypatched.
"""
from datetime import datetime, timedelta
import json
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


@pytest.fixture(autouse=True)
def _offline_vendored_models(monkeypatch):
    """Use real Fli filter models without importing its HTTP client."""
    from providers.fli_custom import provider

    provider._ensure_fli_path()
    from fli.models import (Airport, FlightSearchFilters, FlightSegment,
                            MaxStops, PassengerInfo, SeatType, TripType)

    monkeypatch.setattr(provider, "_load_engine", lambda: (
        Airport, FlightSearchFilters, FlightSegment, MaxStops, PassengerInfo,
        SeatType, TripType, object,
    ))


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


@pytest.mark.parametrize('code', ['7C', ' 5j ', '9C'])
def test_digit_leading_iata_airline_codes_use_real_vendored_enum(monkeypatch, code):
    from fli.models import Airline
    p = FliCustomProvider()
    seen = []
    monkeypatch.setattr(p, '_fetch', lambda filters: seen.append(filters.airlines) or [])
    assert p.search('TPE', 'NRT', '2027-01-01', airlines=[code]) == []
    assert seen == [[Airline['_' + code.strip().upper()]]]


@pytest.mark.parametrize('code', ['ZZZZ', ''])
def test_unknown_airline_still_fails_before_upstream_request(monkeypatch, code):
    p = FliCustomProvider()
    monkeypatch.setattr(p, '_fetch', lambda _filters: pytest.fail('invalid code reached upstream'))
    with pytest.raises(FliProviderError):
        p.search('TPE', 'NRT', '2027-01-01', airlines=[code])


def _real_flight_engine_with_mock_transport(monkeypatch, body):
    from providers.fli_custom import provider
    from fli.models import (Airport, FlightSearchFilters, FlightSegment,
                            MaxStops, PassengerInfo, SeatType, TripType)
    from fli.search.flights import SearchFlights

    monkeypatch.setattr(provider, "_load_engine", lambda: (
        Airport, FlightSearchFilters, FlightSegment, MaxStops, PassengerInfo,
        SeatType, TripType, SearchFlights,
    ))
    calls = []
    def post(**kwargs):
        calls.append(kwargs)
        return NS(text=body, raise_for_status=lambda: None)
    monkeypatch.setattr("fli.search.flights.get_client", lambda: NS(post=post))
    return calls


@pytest.mark.parametrize("body", [
    "<html>blocked</html>",
    json.dumps([["changed", None, "[]"]]),
    json.dumps([["wrb.fr", None, "not JSON"]]),
    json.dumps([["wrb.fr", None, "null"]]),
    json.dumps([["wrb.fr", None, json.dumps({"new_schema": True})]]),
    json.dumps([["wrb.fr", None, json.dumps([None, None, {}, {}])]]),
    json.dumps([["wrb.fr", None, json.dumps([None, None, None, None])]]),
    json.dumps([["wrb.fr", None, json.dumps([None, None, [{}], None])]]),
    json.dumps([["wrb.fr", None, json.dumps([None, None, [""], None])]]),
    json.dumps([["wrb.fr", None, json.dumps([None, None, 7, [[]]])]]),
])
def test_actual_flight_wire_failures_are_typed_for_provider_fallback(monkeypatch, body):
    from providers.fli_custom.errors import FliSearchError

    calls = _real_flight_engine_with_mock_transport(monkeypatch, body)
    with pytest.raises(FliSearchError):
        FliCustomProvider().search("TPE", "NRT", "2027-01-01")
    assert len(calls) == 1


@pytest.mark.parametrize("return_date", [None, "2027-01-05"])
@pytest.mark.parametrize("buckets", [[[[]], [[]]], [[[]], None], [None, [[]]]])
def test_actual_flight_empty_frame_remains_successful_no_results(monkeypatch, return_date, buckets):
    frame = json.dumps([["wrb.fr", None, json.dumps([None, None, *buckets])]])
    calls = _real_flight_engine_with_mock_transport(monkeypatch, frame)
    assert FliCustomProvider().search("TPE", "NRT", "2027-01-01", return_date) == []
    assert len(calls) == 1
