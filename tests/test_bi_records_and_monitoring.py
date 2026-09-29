"""
Tests for Phases 1, 2, 3:
- Phase 1: Permanent BI Records (Never Forget Anything, Dossier, Score Increase, Bot Dropped)
- Phase 2: Website Drift Monitoring (Booking Added/Removed, Phone Changed, New Email, Redesigned)
- Phase 3: Google Maps Monitoring (Review Growth Delta, Rating Velocity)
"""

import os
import json
import pytest
from database import DatabaseManager
from drift_monitor import DriftMonitor

@pytest.fixture
def clean_db(tmp_path):
    db_file = tmp_path / "test_bi_monitoring.db"
    db = DatabaseManager(db_path=str(db_file))
    with db._get_connection() as conn:
        conn.execute("DELETE FROM leads;")
        conn.execute("DELETE FROM changes;")
        conn.execute("DELETE FROM opportunity_timeline;")
        conn.commit()
    yield db

def test_phase1_permanent_bi_record_and_dossier(clean_db):
    """Verifies that full lead dossier preserves all audits, timeline events, and changes."""
    lead_id = "test-lead-bi-01"
    clean_db.save_lead({
        "id": lead_id,
        "name": "Austin Smile Design",
        "url": "https://austinsmiledesign.com",
        "doctor_name": "Dr. Sarah Miller",
        "phone": "+15125551234",
        "opportunity_score": 88,
        "stage": "FOUND",
        "buy_probability_pct": 85
    })

    # Log audit
    clean_db.save_audit({
        "id": "audit-01",
        "lead_id": lead_id,
        "timestamp": "2026-09-08T10:00:00",
        "maturity_score": 45,
        "opportunity_score": 88,
        "missed_rev_min": 3500,
        "missed_rev_max": 6500,
        "annual_gap": 60000
    })

    # Log change
    with clean_db._get_connection() as conn:
        conn.execute("""
        INSERT INTO changes (lead_id, change_type, summary, previous_val, new_val, detected_at)
        VALUES (?, 'SCORE_INCREASED', 'Opportunity score increased from 70 to 88', '70', '88', '2026-09-08T12:00:00')
        """, (lead_id,))
        conn.commit()

    # Query full dossier
    dossier = clean_db.get_full_lead_dossier(lead_id)
    assert dossier is not None
    assert dossier["lead"]["name"] == "Austin Smile Design"
    assert len(dossier["audits"]) == 1
    assert len(dossier["changes"]) == 1
    assert dossier["changes"][0]["change_type"] == "SCORE_INCREASED"

    # Query score increased
    increased = clean_db.get_leads_with_score_increase()
    assert len(increased) == 1
    assert increased[0]["id"] == lead_id

def test_phase1_chatbot_removed_query(clean_db):
    """Verifies retrieval of leads where a chatbot or widget was dropped."""
    lead_id = "test-lead-bot-dropped"
    clean_db.save_lead({
        "id": lead_id,
        "name": "Westlake Dental Studio",
        "url": "https://westlakedental.com",
        "opportunity_score": 92
    })

    with clean_db._get_connection() as conn:
        conn.execute("""
        INSERT INTO changes (lead_id, change_type, summary, previous_val, new_val, detected_at)
        VALUES (?, 'CHATBOT_REMOVED', 'Chatbot widget dropped: previous Intercom removed', 'Intercom', 'None', '2026-09-08T12:00:00')
        """, (lead_id,))
        conn.commit()

    dropped = clean_db.get_leads_with_chatbot_removed()
    assert len(dropped) == 1
    assert dropped[0]["id"] == lead_id
    assert "CHATBOT_REMOVED" in dropped[0]["change_type"]

def test_phase3_maps_growth_monitoring(clean_db):
    """Verifies that review growth velocity and score increases are accurately calculated."""
    lead_id = "test-lead-maps-01"
    clean_db.save_lead({
        "id": lead_id,
        "name": "Downtown Orthodontics",
        "url": "https://downtownortho.com",
        "rating": 4.6,
        "review_count": 100,
        "opportunity_score": 60
    })

    # First audit: set baseline
    res1 = DriftMonitor.monitor_maps_growth(clean_db, lead_id, current_review_count=100, current_rating=4.6)
    assert res1["growth_rate"] == 0
    assert res1["delta_reviews"] == 0

    # Second audit: clinic grew by 46 reviews (+46% growth velocity!)
    res2 = DriftMonitor.monitor_maps_growth(clean_db, lead_id, current_review_count=146, current_rating=4.7)
    assert res2["delta_reviews"] == 46
    assert res2["growth_rate"] == 46.0
    assert res2["rating_velocity"] == 0.1

    # Opportunity score should have bumped due to rapid review surge
    lead = clean_db.get_lead(lead_id)
    assert lead["review_count"] == 146
    assert lead["previous_review_count"] == 100
    assert lead["opportunity_score"] > 60
