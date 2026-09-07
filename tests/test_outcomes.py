import pytest
from database import DatabaseManager
from outcomes import OutcomeAttributionEngine, FindingPerformanceMetric

FINDING_ID = "FIND-BOOKING-ABSENCE"

def test_outcome_metric_properties():
    metric = FindingPerformanceMetric(
        finding_id=FINDING_ID,
        finding_name="Absence of Online Booking Widget",
        touches_sent=100,
        replies_count=25,
        meetings_booked=10,
        deals_won=4,
        total_revenue=18000.0,
        mrr_generated=2600.0
    )
    assert metric.reply_rate_pct == 25.0
    assert metric.meeting_rate_pct == 10.0
    assert metric.win_rate_pct == 40.0
    assert metric.avg_deal_size == 4500.0

def test_outcome_attribution_engine_computation(tmp_path):
    db_file = tmp_path / "test_outcomes.db"
    db = DatabaseManager(db_path=db_file)

    metrics = OutcomeAttributionEngine.compute_performance(db=db)

    assert FINDING_ID in metrics
    booking_m = metrics[FINDING_ID]
    assert booking_m.touches_sent == 450
    assert booking_m.deals_won == 48
    assert booking_m.win_rate_pct > 30.0

    mult = OutcomeAttributionEngine.get_finding_win_multiplier(FINDING_ID, db=db)
    assert mult >= 1.25

    unknown_mult = OutcomeAttributionEngine.get_finding_win_multiplier("NON-EXISTENT", db=db)
    assert unknown_mult == 1.0
