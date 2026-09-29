import os
import pytest
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

from database import DatabaseManager
from drift_monitor import CompetitorDriftMonitor
from models import ScoredLead, DigitalMaturityScore
from fastapi.testclient import TestClient
from app import app

TEST_DRIFT_DB = Path("test_drift_monitor.db")

@pytest.fixture(autouse=True)
def setup_teardown_drift_db():
    test_db = DatabaseManager(db_path=TEST_DRIFT_DB)
    with test_db._get_connection() as conn:
        conn.execute("DELETE FROM leads;")
        conn.execute("DELETE FROM audits;")
        conn.execute("DELETE FROM technologies;")
        conn.execute("DELETE FROM trigger_events;")
        conn.execute("DELETE FROM opportunity_timeline;")
        conn.commit()
    yield
    try:
        if TEST_DRIFT_DB.exists():
            TEST_DRIFT_DB.unlink()
    except Exception:
        pass

def test_drift_competitor_dropped_detection():
    """Verify CompetitorDriftMonitor detects when a clinic removes a competitor."""
    test_db = DatabaseManager(db_path=TEST_DRIFT_DB)
    
    # 1. Insert lead and initial technology (Podium)
    lead_id = "lead_drift_podium"
    with test_db._get_connection() as conn:
        conn.execute("""
        INSERT INTO leads (id, name, website, phone, address, stage, missed_rev_max, html_hash)
        VALUES (?, 'Smile Austin', 'https://smileaustin.com', '5125550100', 'Austin, TX', 'IDENTIFIED', 4500, 'old_hash_123')
        """, (lead_id,))
        conn.execute("""
        INSERT INTO audits (id, lead_id, timestamp, maturity_score, opportunity_score)
        VALUES ('audit_prev_01', ?, '2026-08-01 10:00:00', 50, 75)
        """, (lead_id,))
        conn.execute("""
        INSERT INTO technologies (audit_id, lead_id, name, category, confidence)
        VALUES ('audit_prev_01', ?, 'podium', 'Live Chat', 0.95)
        """, (lead_id,))
        conn.commit()

    # 2. Mock audit to return NO podium (dropped)
    mock_scored = MagicMock()
    mock_scored.technologies = ["Google Analytics", "WordPress"]
    mock_scored.content_hash = "new_hash_456"
    mock_scored.opportunity_score = 88.0
    mock_scored.estimated_missed_revenue_monthly_max = 5200

    with patch("drift_monitor.WebsiteAuditor.audit_lead", new_callable=AsyncMock) as mock_audit:
        mock_audit.return_value = mock_scored

        res = asyncio.run(CompetitorDriftMonitor.rescan_lead(test_db, lead_id=lead_id))
        assert res["status"] == "success"
        triggers = res["triggers_detected"]
        assert len(triggers) >= 1
        dropped = [t for t in triggers if t["event_type"] == "COMPETITOR_DROPPED"]
        assert len(dropped) == 1
        assert "Podium" in dropped[0]["title"]
        assert res["new_urgency_score"] >= 88

    # 3. Verify triggers persisted in database
    triggers_db = CompetitorDriftMonitor.get_active_triggers(test_db)
    assert len(triggers_db) >= 1
    assert triggers_db[0]["lead_id"] == lead_id

def test_drift_competitor_added_detection():
    """Verify CompetitorDriftMonitor detects when a clinic adopts a competitor widget."""
    test_db = DatabaseManager(db_path=TEST_DRIFT_DB)
    
    lead_id = "lead_drift_nexhealth"
    with test_db._get_connection() as conn:
        conn.execute("""
        INSERT INTO leads (id, name, website, phone, stage, missed_rev_max)
        VALUES (?, 'Hill Country Dental', 'https://hillcountrydentist.com', '5125550200', 'IDENTIFIED', 4500)
        """, (lead_id,))
        conn.commit()

    mock_scored = MagicMock()
    mock_scored.technologies = ["nexhealth", "WordPress"]
    mock_scored.content_hash = "hash_nex_123"
    mock_scored.opportunity_score = 80.0
    mock_scored.estimated_missed_revenue_monthly_max = 4500

    with patch("drift_monitor.WebsiteAuditor.audit_lead", new_callable=AsyncMock) as mock_audit:
        mock_audit.return_value = mock_scored

        res = asyncio.run(CompetitorDriftMonitor.rescan_lead(test_db, lead_id=lead_id))
        assert res["status"] == "success"
        added = [t for t in res["triggers_detected"] if t["event_type"] == "COMPETITOR_ADDED"]
        assert len(added) == 1
        assert "NexHealth" in added[0]["title"]

def test_drift_monitor_api_endpoints():
    """Verify FastAPI routes /api/monitor/triggers and /api/monitor/rescan."""
    client = TestClient(app)

    # 1. GET /api/monitor/triggers
    res_trig = client.get("/api/monitor/triggers")
    assert res_trig.status_code == 200
    trig_data = res_trig.json()
    assert "triggers" in trig_data
    assert "count" in trig_data

    # 2. POST /api/monitor/rescan for stale leads
    with patch("drift_monitor.CompetitorDriftMonitor.rescan_stale_leads", new_callable=AsyncMock) as mock_stale:
        mock_stale.return_value = {"stale_candidates_processed": 0, "results": []}
        res_rescan = client.post("/api/monitor/rescan", json={"limit": 5})
        assert res_rescan.status_code == 200
        assert "stale_candidates_processed" in res_rescan.json()
