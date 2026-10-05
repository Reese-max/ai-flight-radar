"""Synthetic review-contract checks; no fares, provider calls, or notifications."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

import pytest
from pydantic import ValidationError

from ai.nlp_parser import ParsedSearchIntent
from core.watchspec import ReviewFields, WatchSpec, preview_watch, promote_watch

ROOT = Path(__file__).resolve().parents[1]


def parsed(**changes):
    data = dict(origins=["TPE"], destinations=["NRT", "HND"],
                min_duration=4, max_duration=5, max_budget_twd=12345,
                direct_only=True, start_date="2026-11-01", end_date="2026-11-30",
                summary_text="Synthetic manually reviewed intent")
    return ParsedSearchIntent(**(data | changes))


def review(**changes):
    data = dict(date_mode="flexible", adults=1, cabin="economy", currency="TWD",
                max_stops=0, airlines_include=(), airlines_exclude=(),
                unresolved_terms=(), unsupported_constraints=())
    return ReviewFields(**(data | changes))


def test_hash_is_canonical_and_search_does_not_promote():
    one = preview_watch(parsed(), review(), watch_id="trip")
    two = preview_watch(parsed(destinations=["HND", "NRT"]), review(), watch_id="trip")
    assert one["spec_hash"] == two["spec_hash"]
    assert one["status"] == "REVIEW_REQUIRED"
    assert "promotion_receipt" not in one
    assert one["scheduled_collection"] == "BLOCKED"
    assert one["spec"]["budget_twd"] == 12345
    assert "max_stops=0" in one["summary"]


@pytest.mark.parametrize("field", ["unresolved_terms", "unsupported_constraints"])
def test_any_dates_and_unknown_constraints_do_not_widen_scope(field):
    candidate = preview_watch(parsed(), review(**{field: ("任何日期，不限回程",)}), watch_id="trip")
    assert candidate["status"] == "NEEDS_REVIEW"
    assert candidate["spec"] is None
    with pytest.raises(ValueError):
        promote_watch(candidate, confirmed_hash="", confirmed_fields=[],
                      evaluated_at=datetime.now(timezone.utc))


@pytest.mark.parametrize("changes", [
    {"origins": []}, {"destinations": ["LHR"]}, {"start_date": "2026-11-31"},
    {"end_date": "2028-01-01"}, {"min_duration": 6, "max_duration": 4},
    {"min_duration": 1}, {"max_budget_twd": 0},
])
def test_invalid_or_unbounded_parser_output_fails_closed(changes):
    with pytest.raises((ValueError, ValidationError)):
        preview_watch(parsed(**changes), review(), watch_id="trip")


def test_exact_dates_have_explicit_return_and_duration():
    candidate = preview_watch(parsed(start_date="2026-11-01", end_date="2026-11-04",
                                    min_duration=4, max_duration=4),
                             review(date_mode="exact"), watch_id="trip")
    assert candidate["spec"]["end_date"] == "2026-11-04"
    with pytest.raises(ValidationError):
        preview_watch(parsed(), review(date_mode="exact"), watch_id="trip")


def test_traveler_cabin_stops_and_airline_constraints_are_preserved():
    candidate = preview_watch(parsed(direct_only=False),
                             review(adults=2, cabin="business", max_stops=1,
                                    airlines_include=("CI",), airlines_exclude=("MM",)),
                             watch_id="trip")
    for field, expected in {"adults": 2, "cabin": "business", "max_stops": 1,
                            "airlines_include": ["CI"], "airlines_exclude": ["MM"]}.items():
        assert candidate["spec"][field] == expected
    with pytest.raises(ValidationError):
        preview_watch(parsed(), review(max_stops=1), watch_id="trip")
    with pytest.raises(ValidationError):
        preview_watch(parsed(), review(airlines_include=("CI",), airlines_exclude=("CI",)), watch_id="trip")


def test_review_requires_explicit_fields_and_rejects_extra_code():
    with pytest.raises(ValidationError):
        ReviewFields(date_mode="flexible")
    with pytest.raises(ValidationError):
        ReviewFields(**(review().model_dump() | {"python": "print('hello')"}))


def test_edit_creates_version_without_changing_old_alert_meaning():
    first = preview_watch(parsed(), review(), watch_id="trip")
    old = WatchSpec.model_validate_json(json.dumps(first["spec"]))
    unchanged = preview_watch(parsed(), review(), watch_id="trip", previous=old)
    assert unchanged["spec_hash"] == first["spec_hash"]
    assert unchanged["diff"] == {}
    changed = preview_watch(parsed(max_budget_twd=9999), review(), watch_id="trip", previous=old)
    assert changed["spec"]["version"] == 2
    assert old.version == 1 and old.budget_twd == 12345
    assert changed["diff"]["budget_twd"] == {"before": 12345, "after": 9999}
    with pytest.raises(ValueError):
        preview_watch(parsed(), review(), watch_id="other", previous=old)


def test_hash_bound_confirmation_never_authorizes_runtime():
    candidate = preview_watch(parsed(), review(), watch_id="trip")
    kwargs = dict(confirmed_hash=candidate["spec_hash"],
                  confirmed_fields=list(candidate["spec"]),
                  evaluated_at=datetime(2026, 10, 4, tzinfo=timezone.utc))
    receipt = promote_watch(candidate, **kwargs)
    assert receipt["watch_version"] == 1
    assert receipt["watchspec_hash"] == candidate["spec_hash"]
    assert receipt["source_intent_hash"] == candidate["source_intent_hash"]
    assert receipt["notification_delivery"] == "NOT_ATTEMPTED"
    assert receipt["scheduled_collection"] == "BLOCKED"
    with pytest.raises(ValueError):
        promote_watch(candidate, **(kwargs | {"confirmed_hash": "changed"}))
    with pytest.raises(ValueError):
        promote_watch(candidate, **(kwargs | {"confirmed_fields": ["budget_twd"]}))
    altered = candidate | {"spec": candidate["spec"] | {"budget_twd": 9999}}
    with pytest.raises(ValueError):
        promote_watch(altered, **kwargs)


def test_cli_preview_is_reviewable_escaped_and_runtime_disabled(tmp_path):
    request = {"watch_id": "trip", "parsed": parsed(summary_text="<script>unsafe</script>").model_dump(mode="json"),
               "review": review().model_dump(mode="json")}
    fixture = tmp_path / "intent.json"
    fixture.write_text(json.dumps(request))
    output = tmp_path / "preview"
    result = subprocess.run([sys.executable, str(ROOT / "scripts/watchspec_preview.py"),
                             str(fixture), "--output", str(output)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    data = json.loads((output / "preview.json").read_text())
    html = (output / "preview.html").read_text()
    assert data["status"] == "REVIEW_REQUIRED"
    assert "<script>" not in html
    assert "budget_twd" in html and "diff" in html
    assert "尚未建立伺服器追蹤" in html
    request["parsed"]["unmapped_requirement"] = "exclude an airline"
    fixture.write_text(json.dumps(request))
    rejected = subprocess.run([sys.executable, str(ROOT / "scripts/watchspec_preview.py"),
                               str(fixture), "--output", str(output)], capture_output=True)
    assert rejected.returncode != 0
