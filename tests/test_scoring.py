from datetime import datetime, timedelta
from types import SimpleNamespace
import pytest
from engine.price_history import summarize_history
from engine.deal_scorer import DealScorer

NOW = datetime(2026, 9, 11, 12)


def offer(**changes):
    values = dict(price_twd=5500, is_direct=True, stops=0, primary_airline="長榮航空",
                  origin="TPE", destination="NRT", depart_time_str="10:00", arrival_time_str="14:00")
    values.update(changes)
    return SimpleNamespace(**values)


def reference(days=5, price=8000):
    return summarize_history([(NOW-timedelta(days=i), price) for i in range(1, days+1)], before=NOW)


def test_cold_start_cannot_claim_a_deal_or_discount():
    score, level, reasons, drop = DealScorer.evaluate(offer(), reference(0))
    assert score < 70 and level == "NORMAL" and drop == 0
    assert any("歷史資料不足" in reason for reason in reasons)


def test_real_baseline_is_not_the_same_search_offer_average():
    score, _, _, drop = DealScorer.evaluate(offer(), reference())
    assert drop == 31.2 and score >= 80


def test_airline_name_does_not_prove_checked_baggage():
    fsc = DealScorer.evaluate(offer(), reference())
    lcc = DealScorer.evaluate(offer(primary_airline="廉價航空"), reference())
    assert fsc[0] == lcc[0]
    assert not any("傳統全服務航空含托運" in reason for reason in fsc[2])


def test_unknown_or_invalid_times_do_not_get_bonus():
    known = DealScorer.evaluate(offer(), reference())[0]
    for value in (None, "25:30", "11:99", "broken"):
        assert DealScorer.evaluate(offer(depart_time_str=value), reference())[0] == known - 5


def test_red_eye_arrival_removes_time_bonus():
    assert DealScorer.evaluate(offer(arrival_time_str="23:30"), reference())[0] == 80


def test_short_history_is_not_tagged_as_ninety_day_low():
    assert DealScorer.evaluate(offer(), reference())[1] != "90D_LOW"


def test_full_history_can_support_ninety_day_low():
    assert DealScorer.evaluate(offer(price_twd=8500), reference(90, 12000))[1] == "90D_LOW"


def test_overlapping_windows_do_not_double_count_discount():
    assert DealScorer.evaluate(offer(), reference(5))[0] == DealScorer.evaluate(offer(), reference(90))[0]


def test_invalid_price_is_rejected():
    with pytest.raises(ValueError):
        DealScorer.evaluate(offer(price_twd=0), reference())
