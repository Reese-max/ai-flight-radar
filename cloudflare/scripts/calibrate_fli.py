"""Bounded live calibration of the Fli-derived provider (Issue #8 production gate).

Default mode is a dry-run that prints the plan and makes zero network calls.
``--execute`` requires ``RADAR_CALIBRATION_ENABLED=true`` and runs at most
``--max-cases`` cases sequentially — one shopping request per one-way
``search`` case (a round-trip case adds up to ``top_n=3`` bounded expansion
requests), and one calendar request per allowed duration per ``dates`` case.
Typed outcomes (ok / empty / invalid / error + class) are written to a JSON
receipt under ``docs/calibration/`` so the primary-provider decision has real
evidence. No retries beyond the engine's own bounded policy, no secrets are
read, and raw upstream payloads or tokens are never recorded.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import json
import os
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

MAX_CASES = 12
RECEIPT_DIR = ROOT / "docs" / "calibration"


class SafeFailure(RuntimeError):
    """A deliberately sanitized message suitable for CI logs."""


def _iso(d: date) -> str:
    return d.isoformat()


def build_cases(today: date | None = None) -> list[dict]:
    """The fixed calibration matrix — Taiwan origins x Japan destinations,
    one-way and round-trip, direct-only, plus a flexible-date pair and a
    route where empty results are a legitimate outcome."""
    dep = (today or date.today()) + timedelta(days=45)
    end30 = dep + timedelta(days=30)
    end14 = dep + timedelta(days=14)
    ret4 = dep + timedelta(days=4)
    return [
        {"id": "tpe-nrt-roundtrip-direct", "kind": "search",
         "origin": "TPE", "destination": "NRT",
         "depart_date": _iso(dep), "return_date": _iso(ret4), "max_stops": 0},
        {"id": "tsa-hnd-roundtrip-direct", "kind": "search",
         "origin": "TSA", "destination": "HND",
         "depart_date": _iso(dep), "return_date": _iso(ret4), "max_stops": 0},
        {"id": "khh-nrt-oneway-direct", "kind": "search",
         "origin": "KHH", "destination": "NRT",
         "depart_date": _iso(dep), "return_date": None, "max_stops": 0},
        {"id": "rmq-cts-roundtrip-direct", "kind": "search",
         "origin": "RMQ", "destination": "CTS",
         "depart_date": _iso(dep), "return_date": _iso(ret4), "max_stops": 0,
         "expect": "empty-allowed"},
        {"id": "tpe-oka-roundtrip-direct", "kind": "search",
         "origin": "TPE", "destination": "OKA",
         "depart_date": _iso(dep), "return_date": _iso(ret4), "max_stops": 0},
        {"id": "tpe-kix-dates-4to6d", "kind": "dates",
         "origin": "TPE", "destination": "KIX",
         "from_date": _iso(dep), "to_date": _iso(end30),
         "trip_durations": [4, 5, 6], "max_stops": 0},
        {"id": "tpe-nrt-dates-oneway", "kind": "dates",
         "origin": "TPE", "destination": "NRT",
         "from_date": _iso(dep), "to_date": _iso(end14),
         "trip_durations": None, "max_stops": 0},
    ]


ROUND_TRIP_EXPANSION_MAX = 3  # mirrors providers.fli_custom.provider.TOP_N


def build_plan(today: date | None = None, max_cases: int = MAX_CASES) -> dict:
    """The dry-run plan; ``max_upstream_requests`` is the worst case, counting
    the bounded round-trip expansion calls underneath each search."""
    cases = build_cases(today)[:max_cases]
    worst = 0
    for c in cases:
        if c["kind"] == "dates":
            worst += len(c.get("trip_durations") or [None])
        else:
            worst += 1 + (ROUND_TRIP_EXPANSION_MAX if c.get("return_date") else 0)
    return {"mode": "dry-run", "network_calls": 0,
            "budget": {"max_cases": len(cases), "max_upstream_requests": worst},
            "cases": cases}


def _error_class(exc: Exception) -> str:
    """Classify the failure; walk the cause chain because providers sanitize
    the original exception type into a FliProviderError wrapper."""
    seen = 0
    current = exc
    while current is not None and seen < 6:
        name = type(current).__name__.lower()
        if "timeout" in name:
            return "timeout"
        if "http" in name or "status" in name:
            return "http"
        if "parse" in name or "decode" in name:
            return "upstream_changed"
        current = current.__cause__ or current.__context__
        seen += 1
    return "provider" if "provider" in type(exc).__name__.lower() else "error"


def _check_search(offers: list, case: dict) -> dict:
    checks = {"route_match": True, "dates_match": True, "positive_price": True,
              "direct_only": True, "currency_ok": True}
    for o in offers:
        if o.origin != case["origin"] or o.destination != case["destination"]:
            checks["route_match"] = False
        if o.depart_date != case["depart_date"] or o.return_date != case["return_date"]:
            checks["dates_match"] = False
        if type(o.price_twd) is not int or o.price_twd <= 0:
            checks["positive_price"] = False
        if case.get("max_stops") == 0 and not (o.is_direct and o.stops == 0):
            checks["direct_only"] = False
        if o.currency not in (None, "TWD"):
            checks["currency_ok"] = False
    return checks


def _check_dates(offers: list, case: dict) -> dict:
    checks = {"route_match": True, "window_match": True, "positive_price": True,
              "duration_allowed": True, "return_matches_duration": True,
              "currency_ok": True}
    allowed = set(case.get("trip_durations") or [])
    for o in offers:
        if o.origin != case["origin"] or o.destination != case["destination"]:
            checks["route_match"] = False
        if not (case["from_date"] <= o.depart_date <= case["to_date"]):
            checks["window_match"] = False
        if type(o.price_twd) is not int or o.price_twd <= 0:
            checks["positive_price"] = False
        if case.get("trip_durations"):
            if o.duration_days not in allowed:
                checks["duration_allowed"] = False
            expected_ret = (date.fromisoformat(o.depart_date)
                            + timedelta(days=o.duration_days or 0)).isoformat()
            if o.return_date != expected_ret:
                checks["return_matches_duration"] = False
        elif o.return_date is not None or o.duration_days is not None:
            checks["return_matches_duration"] = False
        if o.currency not in (None, "TWD"):
            checks["currency_ok"] = False
    return checks


def run_case(provider, case: dict) -> dict:
    """Execute one case; never let an exception escape untyped."""
    try:
        if case["kind"] == "search":
            offers = provider.search(case["origin"], case["destination"],
                                     case["depart_date"], case["return_date"],
                                     max_stops=case.get("max_stops", 0))
            checks = _check_search(offers, case)
        else:
            offers = provider.search_dates(
                case["origin"], case["destination"],
                case["from_date"], case["to_date"],
                trip_durations=case.get("trip_durations"),
                max_stops=case.get("max_stops", 0))
            checks = _check_dates(offers, case)
    except Exception as exc:  # noqa: BLE001 — typed outcome, never a crash
        return {"id": case["id"], "kind": case["kind"],
                "outcome": "error", "error_class": _error_class(exc)}
    if not offers:
        return {"id": case["id"], "kind": case["kind"], "outcome": "empty",
                "expect": case.get("expect")}
    detail = {"observations": len(offers),
              "lowest_price_twd": min(o.price_twd for o in offers),
              "airlines": sorted({o.primary_airline for o in offers
                                  if getattr(o, "primary_airline", None)})[:5]
              if case["kind"] == "search" else [],
              "checks": checks}
    return {"id": case["id"], "kind": case["kind"],
            "outcome": "ok" if all(checks.values()) else "invalid",
            "expect": case.get("expect"), **detail}


def execute(max_cases: int, out_path: Path | None) -> dict:
    os.environ.setdefault("FLI_TIMEOUT", "20")
    os.environ["RADAR_PRIMARY_PROVIDER"] = "fli"
    from providers.selector import get_provider
    provider = get_provider("fli")
    cases = build_cases()[:max_cases]
    results = [run_case(provider, case) for case in cases]
    summary = {"attempted": len(results),
               "ok": sum(1 for r in results if r["outcome"] == "ok"),
               "empty": sum(1 for r in results if r["outcome"] == "empty"),
               "invalid": sum(1 for r in results if r["outcome"] == "invalid"),
               "error": sum(1 for r in results if r["outcome"] == "error")}
    verdict_pass = (summary["invalid"] == 0 and summary["error"] == 0
                    and summary["ok"] >= 1)
    unexpected_empty = [r["id"] for r in results
                        if r["outcome"] == "empty" and r.get("expect") != "empty-allowed"]
    try:
        receipt_path = str(out_path.relative_to(ROOT)) if out_path else None
    except ValueError:
        receipt_path = str(out_path)
    return {
        "tool": "calibrate_fli", "schema_version": 1,
        "ran_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "engine": "fli_custom", "python": platform.python_version(),
        "budget": {"max_cases": len(cases)},
        "cases": results, "summary": summary,
        "verdict": {
            "criteria_passed": verdict_pass,
            "unexpected_empty": unexpected_empty,
            "production_switch": "eligible-for-review" if verdict_pass else "blocked",
            "note": ("Receipt only — RADAR_PRIMARY_PROVIDER stays 'fast_flights' "
                     "until a human flips it after reviewing this evidence.")},
        "receipt_path": receipt_path,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--max-cases", type=int, default=MAX_CASES)
    parser.add_argument("--out", type=str, default=None,
                        help="receipt path (default: docs/calibration/fli-calibration-<ts>.json)")
    args = parser.parse_args(argv)
    if not 1 <= args.max_cases <= MAX_CASES:
        raise SafeFailure(f"--max-cases must be within 1..{MAX_CASES}")
    if not args.execute:
        print(json.dumps(build_plan(max_cases=args.max_cases), ensure_ascii=False, indent=2))
        return 0
    if os.getenv("RADAR_CALIBRATION_ENABLED") != "true":
        raise SafeFailure("RADAR_CALIBRATION_ENABLED must explicitly be true")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = Path(args.out) if args.out else RECEIPT_DIR / f"fli-calibration-{stamp}.json"
    receipt = execute(args.max_cases, out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(json.dumps({"receipt": str(out_path), "summary": receipt["summary"],
                      "verdict": receipt["verdict"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SafeFailure as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
