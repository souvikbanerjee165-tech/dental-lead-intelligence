"""
Tests for Pillar 2: Google Review Analyzer, 12+ Software Detector & AI Objection Predictor.
Verifies:
1. Google review complaint mining & classification (phones unanswered, long waits, booking friction, after-hours emergencies).
2. Detection of 12+ software platforms and AI objection prediction with turnkey counter-punches.
3. Deep clinical AI service research.
"""

import pytest
from database import DatabaseManager
from review_analyzer import ReviewAnalyzer
from battlecard import SalesBattlecardGenerator
from pre_call_researcher import PreCallResearcher


@pytest.fixture
def clean_db(tmp_path):
    db_file = tmp_path / "test_pillar2.db"
    return DatabaseManager(db_path=str(db_file))


def test_google_review_complaint_miner():
    """Verifies that patient review texts are correctly categorized into clinical operational pain points."""
    reviews = [
        "Dr. Marcus is great, but nobody answers the phone and calls go straight to voicemail.",
        "Played phone tag for three days just to get an appointment confirmed. Very frustrating.",
        "Waiting room delay was over 45 minutes because the front desk receptionist was overwhelmed with phone calls.",
        "I had a severe toothache on Saturday night and their office was closed with no emergency number. Had to go elsewhere.",
        "I tried to book an appointment on their website form, but nobody ever followed up."
    ]

    result = ReviewAnalyzer.mine_complaints(reviews, clinic_name="Westlake Dental")
    assert result["total_reviews_analyzed"] == 5
    assert result["friction_categories_detected"] >= 3

    categories = [c["category"] for c in result["ranked_complaints"]]
    assert "PHONE_UNANSWERED" in categories
    assert "WAIT_TIME_EXCESSIVE" in categories
    assert "AFTER_HOURS_NEGLECT" in categories
    assert "BOOKING_FRICTION" in categories

    top = result["top_complaint"]
    assert top is not None
    assert "pitch_hook" in top
    assert "solution_bridge" in top
    assert len(result["executive_bridge"]) > 20


def test_ai_objection_predictor_with_competitor_detection():
    """Verifies that AI Objection Predictor accurately anticipates competitor defenses (Weave, NexHealth, etc.)."""
    # Case 1: Clinic using Weave
    weave_lead = {
        "id": "lead-weave-01",
        "name": "Oak Hill Family Dental",
        "detected_chatbot_name": None,
        "detected_booking_tool": "Weave Scheduling",
        "doctor_name": "Dr. Thomas Vance",
        "receptionist_name": "Sarah"
    }
    pred_weave = SalesBattlecardGenerator.predict_objection(weave_lead)
    assert "Weave" in pred_weave["predicted_objection"]
    assert pred_weave["confidence_pct"] >= 90
    assert "WhatsApp" in pred_weave["suggested_answer"]
    assert "Sunday" in pred_weave["pivot_question"]

    # Case 2: Clinic using NexHealth
    nex_lead = {
        "id": "lead-nex-02",
        "name": "Downtown Cosmetic Dental",
        "detected_chatbot_name": "NexHealth Widget",
        "detected_booking_tool": None
    }
    pred_nex = SalesBattlecardGenerator.predict_objection(nex_lead)
    assert "NexHealth" in pred_nex["predicted_objection"]
    assert "60% drop-off" in pred_nex["suggested_answer"] or "conversational" in pred_nex["suggested_answer"].lower()

    # Case 3: Front Desk receptionist objection
    front_desk_lead = {
        "id": "lead-fd-03",
        "name": "Barton Springs Dental",
        "detected_chatbot_name": None,
        "detected_booking_tool": None,
        "receptionist_name": "Jessica"
    }
    pred_fd = SalesBattlecardGenerator.predict_objection(front_desk_lead)
    assert "Jessica" in pred_fd["predicted_objection"] or "front desk" in pred_fd["predicted_objection"].lower()
    assert "5:30 PM" in pred_fd["pivot_question"] or "after hours" in pred_fd["suggested_answer"].lower()


def test_deep_clinical_ai_research_agent(clean_db):
    """Verifies that pre-call research synthesizes high-ticket implants, cosmetic, aligner, and financing intelligence."""
    lead_id = "test-clinical-01"
    clean_db.save_lead({
        "id": lead_id,
        "name": "Capitol Surgical & Cosmetic Center",
        "doctor_name": "Dr. Robert Sterling",
        "category": "Oral Surgery & Cosmetic Dentistry",
        "rating": 4.9,
        "review_count": 210,
        "missed_rev_max": 8500
    })

    research = PreCallResearcher.research_lead(clean_db, lead_id)
    assert "clinical_services" in research
    services = research["clinical_services"]
    assert "implants" in services
    assert services["implants"]["detected"] is True
    assert "cosmetics" in services
    assert "financing_and_insurance" in services

    # Verify conversation openers include implants and financing
    starters = [s["script"] for s in research["conversation_starters"]]
    assert any("implant" in s.lower() for s in starters)
    assert any("financing" in s.lower() or "carecredit" in s.lower() for s in starters)
