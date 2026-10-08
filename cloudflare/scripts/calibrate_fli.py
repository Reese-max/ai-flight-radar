"""Bounded live calibration for the Fli-derived provider (Issue #8 gate).

Runs a small, fixed set of representative searches and records typed
outcomes as JSON. Never prints upstream bodies, tokens, or secrets.
Usage:
    python cloudflare/scripts/calibrate_fli.py --out docs/calibration/2026-10-03.json
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

CASES = [
    {"origin": "TPE", "destination": "NRT", "return": True, "note": "round-trip direct"},
    {"origin": "TPE", "destination": "KIX", "return": False, "note": "one-way direct"},
    {"origin": "KHH", "destination": "FUK", "return": True, "note": "round-trip south"},
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    from providers.fli_custom import FliCustomProvider, FliProviderError
    provider = FliCustomProvider()
    depart = (datetime.now(timezone.utc).date() + timedelta(days=60)).isoformat()
    back = (datetime.now(timezone.utc).date() + timedelta(days=64)).isoformat()

    receipt = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": "fli_custom",
        "upstream": "punitarani/fli@121d34fea056dc513258958c4262cb5a4cc033c1",
        "cases": [],
    }
    for case in CASES:
        row = {**case}
        try:
            offers = provider.search(
                case["origin"], case["destination"], depart,
                back if case["return"] else None, max_stops=0)
            row["outcome"] = "success" if offers else "no_results"
            row["offer_count"] = len(offers)
            if offers:
                best = min(offers, key=lambda o: o.price_twd)
                row["lowest_price_twd"] = best.price_twd
                row["primary_airline"] = best.primary_airline
                row["currency"] = "TWD"
        except FliProviderError as exc:
            row["outcome"] = "error"
            row["error_type"] = type(exc).__name__
        except Exception:
            row["outcome"] = "error"
            row["error_type"] = "unexpected"
        receipt["cases"].append(row)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(receipt, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
