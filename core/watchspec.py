"""Offline reviewed-intent contract. Nothing here creates tasks or sends alerts.

The existing parser cannot express every travel constraint. Require the review
to state them explicitly; an unknown constraint blocks promotion rather than
silently widening the search.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai.nlp_parser import ParsedSearchIntent
from config.routes import JAPAN_AIRPORTS, TAIWAN_AIRPORTS

PARSER_VERSION = "NLPIntentParser/rule-based-v1"
COMPILER_VERSION = "watchspec-research-v1"


def canonical_hash(value: dict) -> str:
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


class ReviewFields(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    date_mode: Literal["exact", "flexible"]
    # Explicit even for a one-adult/economy search; parser defaults are not review.
    adults: int = Field(ge=1, le=9)
    cabin: Literal["economy", "premium_economy", "business", "first"]
    currency: Literal["TWD"]
    max_stops: int | None = Field(ge=0, le=3)
    airlines_include: tuple[str, ...]
    airlines_exclude: tuple[str, ...]
    unresolved_terms: tuple[str, ...]
    unsupported_constraints: tuple[str, ...]


class WatchSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: Literal[1] = 1
    watch_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    version: int = Field(ge=1)
    origins: tuple[str, ...]
    destinations: tuple[str, ...]
    date_mode: Literal["exact", "flexible"]
    start_date: str
    end_date: str
    # Parser/UI durations count both departure and return calendar dates.
    min_trip_days: int = Field(ge=2, le=31)
    max_trip_days: int = Field(ge=2, le=31)
    budget_twd: int | None = Field(ge=1, le=1_000_000)
    currency: Literal["TWD"]
    adults: int = Field(ge=1, le=9)
    cabin: Literal["economy", "premium_economy", "business", "first"]
    direct_only: bool
    max_stops: int | None = Field(ge=0, le=3)
    airlines_include: tuple[str, ...]
    airlines_exclude: tuple[str, ...]

    @model_validator(mode="after")
    def coherent(self):
        for values, allowed in ((self.origins, TAIWAN_AIRPORTS),
                                (self.destinations, JAPAN_AIRPORTS)):
            if not values or any(value not in allowed for value in values):
                raise ValueError("unsupported or empty airport scope")
            if tuple(sorted(set(values))) != values:
                raise ValueError("airport scopes must be unique and canonical")
        start, end = date.fromisoformat(self.start_date), date.fromisoformat(self.end_date)
        if start.isoformat() != self.start_date or end.isoformat() != self.end_date:
            raise ValueError("dates must use YYYY-MM-DD")
        if end < start or (end - start).days > 366:
            raise ValueError("invalid or unbounded date window")
        if self.min_trip_days > self.max_trip_days:
            raise ValueError("invalid trip duration range")
        if self.date_mode == "exact":
            if (end - start).days + 1 != self.min_trip_days or self.min_trip_days != self.max_trip_days:
                raise ValueError("exact departure/return dates must match trip duration")
        if self.direct_only and self.max_stops != 0:
            raise ValueError("direct flights require max_stops=0")
        if not self.direct_only and self.max_stops == 0:
            raise ValueError("non-direct scope contradicts max_stops=0")
        for values in (self.airlines_include, self.airlines_exclude):
            if tuple(sorted(set(values))) != values or any(not value.strip() for value in values):
                raise ValueError("airline scopes must be unique nonempty names")
        if set(self.airlines_include) & set(self.airlines_exclude):
            raise ValueError("airline is both included and excluded")
        return self

    def content(self) -> dict:
        return self.model_dump(mode="json")

    @property
    def spec_hash(self) -> str:
        return canonical_hash(self.content())


def preview_watch(parsed: ParsedSearchIntent, review: ReviewFields, *,
                  watch_id: str, previous: WatchSpec | None = None) -> dict:
    """Produce a reviewable candidate, with no scheduler/database side effects."""
    if review.unresolved_terms or review.unsupported_constraints:
        return {"status": "NEEDS_REVIEW", "spec": None, "spec_hash": None,
                "unresolved_terms": list(review.unresolved_terms),
                "unsupported_constraints": list(review.unsupported_constraints),
                "scheduled_collection": "BLOCKED"}
    if previous and previous.watch_id != watch_id:
        raise ValueError("previous WatchSpec belongs to a different watch")
    spec = WatchSpec(
        watch_id=watch_id, version=previous.version + 1 if previous else 1,
        origins=tuple(sorted(set(parsed.origins))),
        destinations=tuple(sorted(set(parsed.destinations))),
        date_mode=review.date_mode, start_date=parsed.start_date, end_date=parsed.end_date,
        min_trip_days=parsed.min_duration, max_trip_days=parsed.max_duration,
        budget_twd=parsed.max_budget_twd, currency=review.currency, adults=review.adults,
        cabin=review.cabin, direct_only=parsed.direct_only, max_stops=review.max_stops,
        airlines_include=tuple(sorted(set(review.airlines_include))),
        airlines_exclude=tuple(sorted(set(review.airlines_exclude))),
    )
    old = previous.content() if previous else {}
    fields = spec.content()
    material_fields = set(fields) - {"version", "schema_version"}
    if previous and all(old[key] == fields[key] for key in material_fields):
        spec = previous
        fields = spec.content()
    diff = {key: {"before": old.get(key), "after": value}
            for key, value in fields.items() if old.get(key) != value}
    source_intent_hash = canonical_hash({"parsed": parsed.model_dump(mode="json"),
                                         "review": review.model_dump(mode="json")})
    return {
        "status": "REVIEW_REQUIRED", "spec": fields, "spec_hash": spec.spec_hash,
        "source_intent_hash": source_intent_hash, "diff": diff,
        "parser_version": PARSER_VERSION, "compiler_version": COMPILER_VERSION,
        "summary": (f"{','.join(spec.origins)} → {','.join(spec.destinations)}; "
                    f"{spec.start_date}–{spec.end_date} ({spec.date_mode}); "
                    f"{spec.min_trip_days}–{spec.max_trip_days} calendar days; "
                    f"{spec.adults} adult(s), {spec.cabin}; "
                    f"budget {spec.budget_twd if spec.budget_twd else 'unlimited'} TWD; "
                    f"direct={spec.direct_only}, max_stops={spec.max_stops}; "
                    f"include={list(spec.airlines_include)}, exclude={list(spec.airlines_exclude)}"),
        "scheduled_collection": "BLOCKED",
    }


def promote_watch(preview: dict, *, confirmed_hash: str, confirmed_fields: list[str],
                  evaluated_at: datetime) -> dict:
    """Emit only an offline promotion receipt; never grant collector authority."""
    if preview.get("status") != "REVIEW_REQUIRED" or not preview.get("spec"):
        raise ValueError("unresolved or unsupported intent cannot be promoted")
    spec = WatchSpec.model_validate_json(json.dumps(preview["spec"]))
    if confirmed_hash != spec.spec_hash or preview.get("spec_hash") != spec.spec_hash:
        raise ValueError("reviewed WatchSpec changed; review again")
    if set(confirmed_fields) != set(spec.content()) or len(confirmed_fields) != len(set(confirmed_fields)):
        raise ValueError("every WatchSpec field requires explicit confirmation")
    if evaluated_at.tzinfo is None:
        raise ValueError("confirmation timestamp must include timezone")
    return {"schema_version": 1, "kind": "OFFLINE_WATCH_PROMOTION_RECEIPT",
            "watch_id": spec.watch_id, "watch_version": spec.version,
            "source_intent_hash": preview["source_intent_hash"],
            "watchspec_hash": spec.spec_hash, "parser_version": PARSER_VERSION,
            "compiler_version": COMPILER_VERSION,
            "confirmed_fields": sorted(confirmed_fields),
            "confirmed_at": evaluated_at.astimezone(timezone.utc).isoformat(),
            "scheduled_collection": "BLOCKED", "notification_delivery": "NOT_ATTEMPTED"}
