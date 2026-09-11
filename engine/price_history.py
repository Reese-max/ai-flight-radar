"""Pure, offline-testable statistics for *one identical search query*.

Each input is already the lowest returned price in one search. A daily median
then gives each observation day one vote, regardless of polling frequency.
These are observed quotes, not guaranteed bookable fares or market history.
"""
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
from math import isfinite
from statistics import fmean, median
from typing import Iterable


def utc_naive(value: datetime) -> datetime:
    """The existing database stores UTC without a timezone offset."""
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def query_key(origin: str, destination: str, depart_date: str, return_date: str,
              *, source: str = "google_flights", currency: str = "TWD",
              direct_only: bool = True, adults: int = 1,
              cabin: str = "economy") -> str:
    departure, arrival = date.fromisoformat(depart_date), date.fromisoformat(return_date)
    if arrival <= departure:
        raise ValueError("Return date must be after departure date")
    origin, destination = origin.upper(), destination.upper()
    if any(len(code) != 3 or not code.isascii() or not code.isalpha()
           for code in (origin, destination)) or origin == destination:
        raise ValueError("Two distinct three-letter airport codes are required")
    if adults < 1:
        raise ValueError("At least one adult is required")
    payload = dict(origin=origin, destination=destination,
                   departure=departure.isoformat(), return_date=arrival.isoformat(),
                   source=source, currency=currency.upper(), direct_only=direct_only,
                   adults=adults, cabin=cabin, fare_policy="unverified-baggage-v1")
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def summarize_history(observations: Iterable[tuple[datetime, int]], *,
                      before: datetime, minimum_days: int = 5) -> dict:
    """Exclude the current/future batch and avoid high-frequency sampling bias.

    A '30-day' window means observations collected WITHIN that window, not a
    promise of 30 days' coverage. The returned counts/span make that explicit.
    """
    if minimum_days < 2:
        raise ValueError("minimum_days must be at least two")
    before = utc_naive(before)
    valid = []
    for timestamp, price in observations:
        timestamp = utc_naive(timestamp)
        if (isinstance(price, bool) or not isinstance(price, (int, float))
                or not isfinite(price) or price <= 0 or timestamp >= before):
            continue
        valid.append((timestamp, float(price)))

    result = {
        "sample_count": len(valid), "min_historical": None,
        "max_historical": None, "is_cold_start": True,
        "sufficient_history": False, "has_90d_coverage": False,
        "baseline_type": "same_query_daily_median_mean",
        "observed_days": 0, "coverage_days": 0,
    }
    for days in (7, 30, 90):
        window = [(at, price) for at, price in valid
                  if at >= before - timedelta(days=days)]
        daily = defaultdict(list)
        for at, price in window:
            daily[at.date()].append(price)
        daily_prices = [median(prices) for prices in daily.values()]
        result[f"avg_{days}d"] = round(fmean(daily_prices), 2) if daily_prices else None
        result[f"observed_days_{days}d"] = len(daily)
        result[f"min_{days}d"] = min((p for _, p in window), default=None)
        result[f"coverage_{days}d_days"] = (
            (max(daily) - min(daily)).days + 1 if daily else 0
        )
    if valid:
        result["min_historical"] = min(p for _, p in valid)
        result["max_historical"] = max(p for _, p in valid)
    result["observed_days"] = result["observed_days_30d"]
    result["coverage_days"] = result["coverage_30d_days"]
    result["sufficient_history"] = result["observed_days_30d"] >= minimum_days
    result["is_cold_start"] = not result["sufficient_history"]
    result["has_90d_coverage"] = (
        result["observed_days_90d"] >= 60 and result["coverage_90d_days"] >= 90
    )
    return result
