import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from database import DatabaseManager
from sales_coach import SalesCoach, SalesOS
from fastapi.testclient import TestClient
from app import app

TEST_COACH_DB = Path("test_coach_os.db")

@pytest.fixture(autouse=True)
def setup_teardown_db():
    test_db = DatabaseManager(db_path=TEST_COACH_DB)
    with test_db._get_connection() as conn:
        conn.execute("DELETE FROM leads;")
        conn.execute("DELETE FROM call_logs;")
        conn.execute("DELETE FROM sales_memory;")
        conn.commit()
    yield
    try:
        if TEST_COACH_DB.exists():
            TEST_COACH_DB.unlink()
    except Exception:
        pass

def test_sales_coach_talk_to_listen_ratio():
    """Verify talk-to-listen percentage calculations and diagnostics."""
    # 1. Rep dominant transcript (>60% rep)
    rep_heavy = """
    Rep: Hello, this is Alex from Dental Growth Engine. I wanted to reach out regarding your clinic patient flow. We provide an advanced 24/7 automated answering service that directly integrates into your scheduling software to ensure no after-hours leads are ever dropped or missed.
    Prospect: Okay.
    Rep: We have helped over two hundred dental clinics throughout Texas recover an extra fifteen to thirty thousand dollars in high-ticket implants and cosmetic dental procedures every single month.
    Prospect: Thanks.
    """
    analysis_poor = SalesCoach.analyze_call(rep_heavy)
    assert analysis_poor["talk_to_listen"]["grade"] == "POOR"
    assert analysis_poor["talk_to_listen"]["rep_percent"] > 60

    # 2. Optimal listening transcript (<48% rep)
    prospect_heavy = """
    Rep: Hi, quick question regarding your patient intake—who handles inquiries when the office is dark?
    Prospect: Well, normally our receptionist Sarah handles everything between eight and five, but once we lock up at five, everything goes to voicemail. On Monday mornings we usually have six or seven voicemails, and by the time Sarah calls them back, half of them have already scheduled with the dental clinic down the street. It has been a huge frustration for Dr. Miller.
    Rep: That makes total sense.
    """
    analysis_optimal = SalesCoach.analyze_call(prospect_heavy)
    assert analysis_optimal["talk_to_listen"]["grade"] == "OPTIMAL"
    assert analysis_optimal["talk_to_listen"]["rep_percent"] < 48

def test_sales_coach_buying_signals_and_objections():
    """Verify buying signal detection, objection classification, and tactical counter-punch."""
    transcript = """
    Rep: Hi Dr. Miller, we ran a digital intake audit on your Austin office.
    Prospect: We already have a receptionist who handles all our scheduling. But how much does your service cost, and does it integrate with Open Dental?
    Rep: Our system integrates natively with Open Dental and covers after-hours when Sarah is home.
    """
    analysis = SalesCoach.analyze_call(transcript, lead_dict={"id": "lead_test_01", "name": "Miller Dental", "address": "Austin, TX"})
    
    signals = [s["type"] for s in analysis["buying_signals"]]
    assert "PRICING_INQUIRY" in signals
    assert "TECH_INTEGRATION" in signals
    
    objections = [o["category"] for o in analysis["objections_detected"]]
    assert "RECEPTIONIST_COVERAGE" in objections
    
    assert analysis["objection_handling"]["score"] >= 6
    assert "Sunday" in analysis["objection_handling"]["recommended_rebuttal"] or "receptionist" in analysis["objection_handling"]["recommended_rebuttal"].lower()
    assert analysis["overall_score"] > 0

def test_sales_os_daily_metrics():
    """Verify SalesOS KPI calculations (targets count, MRR potential, calls pacing)."""
    test_db = DatabaseManager(db_path=TEST_COACH_DB)
    
    # Seed leads
    with test_db._get_connection() as conn:
        conn.execute("""
        INSERT INTO leads (id, name, stage, win_probability_pct, missed_rev_max, category)
        VALUES 
        ('lead_1', 'Austin Smile Design', 'IDENTIFIED', 85, 6000, 'Cosmetic Dentistry'),
        ('lead_2', 'Hill Country Dental', 'CONTACTED', 78, 5000, 'General Dentistry'),
        ('lead_3', 'Low Fit Clinic', 'IDENTIFIED', 40, 3000, 'General Dentistry'),
        ('lead_4', 'Won Clinic', 'WON', 90, 8000, 'Implants');
        """)
        
        # Seed a call log today
        now_ts = "2026-09-09 10:00:00"
        conn.execute("""
        INSERT INTO call_logs (lead_id, timestamp, outcome, rep_notes, call_duration_sec)
        VALUES ('lead_2', ?, 'COMPLETED', 'Discussed after-hours gaps', 120);
        """, (now_ts,))
        conn.commit()

    metrics = SalesOS.get_daily_sales_metrics(test_db)
    
    assert metrics["total_leads_tracked"] == 4
    # lead_1 and lead_2 qualify (win_prob >= 75 and not in WON/LOST)
    assert metrics["today_targets_count"] >= 2
    assert metrics["pipeline_mrr_potential"] > 0
    assert metrics["calls_daily_target"] == 15
    assert "pacing_status" in metrics
    assert len(metrics["top_niches"]) > 0

def test_sales_coach_and_os_api_endpoints():
    """Verify FastAPI routes /api/sales-os/metrics and /api/coach/analyze."""
    client = TestClient(app)

    # 1. GET /api/sales-os/metrics
    res_os = client.get("/api/sales-os/metrics")
    assert res_os.status_code == 200
    os_data = res_os.json()
    assert "pipeline_mrr_potential" in os_data
    assert "calls_daily_target" in os_data
    assert "daily_action_briefing" in os_data

    # 2. POST /api/coach/analyze
    sample_transcript = "Rep: Hi, this is Sarah. Prospect: How much does this cost?"
    res_coach = client.post("/api/coach/analyze", json={
        "transcript": sample_transcript,
        "lead_id": None,
        "duration_sec": 45
    })
    assert res_coach.status_code == 200
    coach_data = res_coach.json()
    assert "talk_to_listen" in coach_data
    assert "overall_score" in coach_data
    assert "coaching_summary" in coach_data
