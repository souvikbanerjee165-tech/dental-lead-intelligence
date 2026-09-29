"""
Tests for Phases 7, 9, 10:
- Phase 7: Relationship Memory (Staff & Gatekeeper Dossier, Demeanor, Software Mentioned)
- Phase 9: Pre-Call Research (Warm Conversation Starters, Review Compliments, Doctor-Direct Pitch)
- Phase 10: Institutional Knowledge Base (Self-Learning Repository of Proven Rebuttals & Winning Touch Angles)
"""

import pytest
from database import DatabaseManager
from pre_call_researcher import PreCallResearcher

@pytest.fixture
def clean_db(tmp_path):
    db_file = tmp_path / "test_rel_research.db"
    db = DatabaseManager(db_path=str(db_file))
    with db._get_connection() as conn:
        conn.execute("DELETE FROM leads;")
        conn.execute("DELETE FROM relationship_memory;")
        conn.execute("DELETE FROM knowledge_base;")
        conn.commit()
    yield db

def test_phase7_relationship_memory_storage(clean_db):
    """Verifies that front desk & gatekeeper intelligence is permanently stored and retrievable."""
    lead_id = "test-lead-gk-01"
    clean_db.save_lead({
        "id": lead_id,
        "name": "Arboretum Dental Care",
        "doctor_name": "Dr. Emily Taylor"
    })

    mem_id = clean_db.record_relationship_memory(
        lead_id=lead_id,
        contact_name="Sarah",
        role="Office Manager",
        demeanor="Friendly but busy",
        notes="Best to call on Tuesday mornings between 9:30 AM and 11 AM before doctor sees implant patients.",
        best_time_to_call="Tuesday 10:00 AM",
        software_mentioned="Dentrix G7"
    )
    assert mem_id is not None

    records = clean_db.get_relationship_memory(lead_id)
    assert len(records) == 1
    rec = records[0]
    assert rec["contact_name"] == "Sarah"
    assert rec["role"] == "Office Manager"
    assert rec["software_mentioned"] == "Dentrix G7"

    # Verify lead table columns were also synchronized
    lead = clean_db.get_lead(lead_id)
    assert lead["receptionist_name"] == "Sarah"
    assert "Tuesday 10:00 AM" in lead["best_call_time"]

def test_phase9_pre_call_researcher(clean_db):
    """Verifies generation of warm conversation openers and doctor-direct hooks."""
    lead_id = "test-lead-research-01"
    clean_db.save_lead({
        "id": lead_id,
        "name": "Capital City Cosmetic Dentistry",
        "doctor_name": "Dr. Marcus Vance",
        "address": "701 Brazos St, Austin, TX",
        "rating": 4.9,
        "review_count": 280,
        "opportunity_score": 84,
        "missed_rev_max": 6200
    })

    # Add gatekeeper memory
    clean_db.record_relationship_memory(
        lead_id=lead_id,
        contact_name="Jessica",
        role="Lead Receptionist",
        demeanor="Guarded",
        notes="Requests written info"
    )

    research = PreCallResearcher.research_lead(clean_db, lead_id)
    assert research is not None
    assert "Dr. Marcus Vance" in research["doctor_direct_opener"]
    assert "280" in research["review_compliment"]
    assert research["gatekeeper_briefing"]["receptionist_name"] == "Jessica"
    assert len(research["recommended_warm_starters"]) >= 3

def test_phase10_institutional_knowledge_base(clean_db):
    """Verifies logging and querying of institutional knowledge base entries."""
    ins_id = clean_db.log_knowledge_base_insight(
        category="OBJECTION_REBUTTAL",
        key_phrase="already have a receptionist",
        content="Who answers high-ticket implant and emergency questions at 8:30 PM on Sunday when the office is dark?",
        effectiveness_score=9.4
    )
    assert ins_id is not None

    # Query all insights
    insights = clean_db.get_knowledge_base_insights()
    assert len(insights) >= 1
    found = [i for i in insights if i["key_phrase"] == "already have a receptionist"]
    assert len(found) == 1
    assert found[0]["effectiveness_score"] == 9.4
