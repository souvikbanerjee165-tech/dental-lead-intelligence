"""
Unit and Integration Tests for AI Revenue Operating System (Phase 1 Conversion Trinity):
- Website Change Detection & Trigger Events
- "Why Now?" Urgency Scoring
- AI ROI Unit Economics Calculator
- 1-Click Tailored Proposal Customizer
- 2-Minute Personalized Loom Video Script Generator
"""

import pytest
from fastapi.testclient import TestClient

from app import app
from database import DatabaseManager
from triggers import TriggerEngine, compute_html_hash, compute_tech_hash
from proposals import calculate_practice_roi, generate_tailored_proposal
from loom_script import generate_loom_pitch

client = TestClient(app)


def test_hash_computation_and_change_detection():
    # 1. Test hash determinism
    h1 = compute_html_hash("<html><body><h1>Austin Smiles</h1></body></html>")
    h2 = compute_html_hash("<html> <body>  <h1>Austin Smiles</h1> </body></html>")
    assert h1 == h2
    assert len(h1) == 16

    t1 = compute_tech_hash(["WordPress", "Google Analytics", "NexHealth"])
    t2 = compute_tech_hash(["NexHealth", "wordpress", "google analytics"])
    assert t1 == t2

    # 2. Test change detection delta
    old_lead = {
        "id": "lead_test",
        "html_hash": "old_hash_123",
        "tech_hash": "old_tech_456",
        "review_count": 50,
        "rating": 4.9,
        "doctor_name": None
    }
    new_data = {
        "html_hash": "new_hash_789",
        "tech_hash": "old_tech_456",
        "review_count": 58,
        "rating": 4.6,
        "doctor_name": "Dr. Sarah Vance"
    }

    triggers = TriggerEngine.detect_changes(old_lead, new_data)
    event_types = [t["event_type"] for t in triggers]
    assert "WEBSITE_REDESIGNED" in event_types
    assert "REVIEW_SURGE" in event_types
    assert "RATING_DROP" in event_types
    assert "NEW_DOCTOR_FOUND" in event_types
    assert len(triggers) == 4


def test_urgency_scoring_and_why_now():
    lead = {
        "id": "lead_test_2",
        "name": "Oak Creek Dental",
        "doctor_name": "Dr. Robert Vance",
        "direct_emails": "dr.vance@oakcreek.com",
        "review_count": 85,
        "opportunity_score": 82,
        "missed_rev_max": 5800,
        "missed_rev_min": 2900
    }
    active_triggers = [
        {"severity": "CRITICAL", "title": "Google Rating Slipped", "description": "4.9 -> 4.6"}
    ]

    score = TriggerEngine.calculate_urgency_score(lead, triggers=active_triggers)
    assert 70 <= score <= 100

    reasons = TriggerEngine.generate_why_now_reasons(lead, triggers=active_triggers)
    assert len(reasons) >= 3
    assert any("Dr. Robert Vance" in r for r in reasons)
    assert any("Google Rating Slipped" in r for r in reasons)


def test_roi_calculator_unit_economics():
    lead = {"name": "Metro Family Dental"}
    # 5 recovered patients/mo @ $900/case, $299 fee
    roi = calculate_practice_roi(lead, recovered_patients_per_month=5, avg_case_value=900, monthly_fee=299)
    assert roi["monthly_revenue_recovered"] == 4500
    assert roi["annual_revenue_recovered"] == 54000
    assert roi["annual_cost"] == 3588
    assert roi["net_annual_profit"] == 50412
    assert roi["roi_multiplier"] == 15.1
    assert "15.1x" in roi["headline_roi"]


def test_tailored_proposal_generation():
    lead = {
        "id": "lead_test_proposal",
        "name": "Beacon Dental Care",
        "doctor_name": "Dr. Emily Hayes",
        "phone": "(512) 555-0199",
        "address": "1200 S Congress Ave, Austin, TX",
        "rating": 4.8,
        "review_count": 64,
        "missed_rev_min": 2400,
        "missed_rev_max": 4800
    }
    proposal = generate_tailored_proposal(lead)
    assert proposal["practice_name"] == "Beacon Dental Care"
    assert "Dr. Emily Hayes" in proposal["doctor_name"]
    assert len(proposal["diagnosed_friction"]) >= 2
    assert len(proposal["implementation_roadmap"]) == 3
    assert len(proposal["pricing_options"]) == 2
    assert "30-Day Zero-Risk Guarantee" in proposal["guarantee"]
    assert proposal["roi_breakdown"]["annual_revenue_recovered"] > 0


def test_loom_video_pitch_generator():
    lead = {
        "id": "lead_test_loom",
        "name": "Highland Dental Arts",
        "doctor_name": "Dr. Marcus Cole",
        "address": "Denver, CO",
        "rating": 4.9,
        "review_count": 92,
        "missed_rev_min": 3200,
        "missed_rev_max": 6400,
        "website": "highlanddentalarts.com"
    }
    pitch = generate_loom_pitch(lead)
    assert "Dr. Marcus Cole" in pitch["doctor_greeting"]
    assert len(pitch["scenes"]) == 5
    assert 60 <= pitch["est_duration_sec"] <= 140
    assert "teleprompter_text" in pitch
    assert "Denver, CO" in pitch["scenes"][0]["voiceover"] or "Highland Dental Arts" in pitch["scenes"][0]["voiceover"]


def test_revenue_os_api_endpoints():
    # 1. Fetch top urgent queue
    res_urgent = client.get("/api/queue/top-urgent?limit=5")
    assert res_urgent.status_code == 200
    leads = res_urgent.json()
    assert isinstance(leads, list)
    if leads:
        lead_id = leads[0]["id"]

        # 2. Test ROI endpoint
        res_roi = client.get(f"/api/leads/{lead_id}/roi?patients=6&case_value=1000&fee=399")
        assert res_roi.status_code == 200
        roi_data = res_roi.json()
        assert roi_data["roi"]["monthly_revenue_recovered"] == 6000

        # 3. Test Proposal endpoint
        res_prop = client.get(f"/api/leads/{lead_id}/proposal")
        assert res_prop.status_code == 200
        prop_data = res_prop.json()
        assert "practice_name" in prop_data
        assert "roi_breakdown" in prop_data

        # 4. Test Loom script endpoint
        res_loom = client.get(f"/api/leads/{lead_id}/loom-script")
        assert res_loom.status_code == 200
        loom_data = res_loom.json()
        assert "scenes" in loom_data
        assert len(loom_data["scenes"]) == 5

        # 5. Test Triggers & On-Demand Check
        res_check = client.post(f"/api/leads/{lead_id}/check-changes", json={
            "html_content": "<html><body><h1>Refreshed Site</h1></body></html>",
            "new_reviews": 110,
            "new_rating": 4.7
        })
        assert res_check.status_code == 200
        check_data = res_check.json()
        assert "urgency_score" in check_data
        assert "why_now_reasons" in check_data

        # 6. Test GET triggers
        res_trig = client.get(f"/api/leads/{lead_id}/triggers")
        assert res_trig.status_code == 200
        trig_data = res_trig.json()
        assert "triggers" in trig_data
