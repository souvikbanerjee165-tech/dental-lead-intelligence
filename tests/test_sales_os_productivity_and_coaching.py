"""
Tests for Phases 8, 11, 12, 13, 14:
- Phase 8: Automatic Morning Plan ("Today's Mission" Sequential Queue & 1-Click Actions)
- Phase 11: AI Sales Coach & Simulator (Sparring Mode with Confidence, Pacing, Objection, Closing)
- Phase 12: Follow-Up Automation (4-Stage Non-Repeating Sequences: Intake Gap, Benchmark, PMS, 14-Day Pilot)
- Phase 13: Predictive Revenue Forecaster (Empirical Conversion Forecaster: 35%, 18%, 28%, $499 MRR, ARR)
- Phase 14: Personal Productivity Dashboard (Founder Telemetry: Calls, WhatsApps, Best City, Best Niche)
"""

import pytest
from database import DatabaseManager
from sales_coach import SalesOS
from outreach_generator import OutreachGenerator
from simulator import AICallSimulator, TurnEvaluation

@pytest.fixture
def clean_db(tmp_path):
    db_file = tmp_path / "test_sales_os.db"
    db = DatabaseManager(db_path=str(db_file))
    with db._get_connection() as conn:
        conn.execute("DELETE FROM leads;")
        conn.execute("DELETE FROM opportunity_timeline;")
        conn.commit()
    yield db

def test_phase8_todays_mission_queue(clean_db):
    """Verifies that Today's Mission orders targets by buy probability and delivers 1-click execution actions."""
    clean_db.save_lead({
        "id": "target-1",
        "name": "Target Clinic One",
        "doctor_name": "Dr. First",
        "phone": "+15125550001",
        "opportunity_score": 95,
        "buy_probability_pct": 92
    })
    clean_db.save_lead({
        "id": "target-2",
        "name": "Target Clinic Two",
        "doctor_name": "Dr. Second",
        "phone": "+15125550002",
        "opportunity_score": 75,
        "buy_probability_pct": 78
    })

    # Offset 0 -> Should be Target Clinic One
    mission1 = SalesOS.get_todays_mission(clean_db, offset=0)
    assert mission1["mission_active"] is True
    assert mission1["total_queue"] == 2
    assert mission1["current_index"] == 1
    assert mission1["target"]["clinic_name"] == "Target Clinic One"
    assert mission1["target"]["quick_actions"]["call_now_url"] is not None
    assert "https://wa.me/" in mission1["target"]["quick_actions"]["whatsapp_url"]

    # Advance offset 1 -> Should be Target Clinic Two
    mission2 = SalesOS.get_todays_mission(clean_db, offset=1)
    assert mission2["target"]["clinic_name"] == "Target Clinic Two"

    # Advance offset 2 -> Mission Complete
    mission3 = SalesOS.get_todays_mission(clean_db, offset=2)
    assert mission3["mission_active"] is False

def test_phase11_simulator_sparring_scorecard():
    """Verifies that practice sparring evaluates Confidence, Pacing, Objection Handling, and Closing."""
    sim = AICallSimulator()
    # Test deterministic fallback evaluation
    eval_res = sim._fallback_evaluate(
        user_pitch="Hi Dr. Miller, we capture missed weekend dental implants. Open to a 60-second video demo tomorrow at 10 AM?",
        persona_key="BUSY_DOCTOR"
    )
    assert isinstance(eval_res, TurnEvaluation)
    assert eval_res.confidence_score is not None
    assert eval_res.pacing_score is not None
    assert eval_res.objection_score is not None
    assert eval_res.closing_score is not None
    assert 1 <= eval_res.confidence_score <= 10
    assert 1 <= eval_res.pacing_score <= 10
    assert 1 <= eval_res.objection_score <= 10
    assert 1 <= eval_res.closing_score <= 10

def test_phase12_follow_up_automation_sequences():
    """Verifies that OutreachGenerator generates non-repeating copy for Touches 1, 2, 3, and 4."""
    lead = {
        "id": "seq-lead-01",
        "name": "Mueller Dental Center",
        "doctor_name": "Dr. Rachel Green",
        "missed_rev_max": 5400,
        "review_count": 210,
        "address": "Mueller, Austin, TX"
    }

    t1 = OutreachGenerator.generate_step_sequence(lead, touch_number=1)
    assert "Touch 1" in t1["stage"] and "Gap" in t1["stage"]
    assert "Dr. Rachel Green" in t1["subject"]
    assert "WhatsApp" in t1["channels"]

    t2 = OutreachGenerator.generate_step_sequence(lead, touch_number=2)
    assert t2["stage"] == "Touch 2 (Peer Benchmark / Study)"
    assert "Sunday Study" in t2["subject"]
    assert t2["body"] != t1["body"]

    t3 = OutreachGenerator.generate_step_sequence(lead, touch_number=3)
    assert t3["stage"] == "Touch 3 (PMS Integration / Front Desk)"
    assert "PMS" in t3["subject"] or "Dentrix" in t3["body"]

    t4 = OutreachGenerator.generate_step_sequence(lead, touch_number=4)
    assert t4["stage"] == "Touch 4 (14-Day Risk-Free Pilot)"
    assert "14-Day" in t4["subject"] or "pilot" in t4["body"].lower()

def test_phase13_predictive_revenue_forecaster(clean_db):
    """Verifies empirical revenue calculations for planned calls and pipeline."""
    forecast = SalesOS.get_revenue_forecast(clean_db, calls_planned=10)
    # 10 calls * 35% connects = 3.5 connects
    assert forecast["expected_connects"] == 3.5
    # 3.5 connects * 18% meetings = 0.63 meetings
    assert forecast["expected_meetings"] > 0.5
    # Closes * $499 MRR
    assert forecast["expected_mrr"] > 0
    assert forecast["expected_arr"] == round(forecast["expected_mrr"] * 12.0, 2)
    assert len(forecast["scenarios"]) == 4

def test_phase14_personal_productivity_telemetry(clean_db):
    """Verifies logging and retrieval of founder productivity KPIs."""
    # Log some calls and activities
    clean_db.record_call_log(lead_id="test-lead-1", outcome="INTERESTED", rep_notes="Great conversation", duration_sec=180)
    SalesOS.log_productivity_activity(clean_db, activity_type="WHATSAPP_SENT", count=3)

    telemetry = SalesOS.get_productivity_telemetry(clean_db)
    assert telemetry["calls_made_today"] >= 1
    assert telemetry["daily_call_target"] == 15
    assert telemetry["target_progress_pct"] > 0
    assert telemetry["total_activities_today"] >= 1
