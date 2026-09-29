import os
import pytest
from pathlib import Path
import sqlite3
import json

from memory_manager import MemoryManager
from ai_qualifier import AIQualifier
from dental_caller_persona import DentalCallerPersona
from database import DatabaseManager

TEST_DB_PATH = Path("test_memory_phase1.db")

@pytest.fixture(autouse=True)
def setup_teardown_db():
    if TEST_DB_PATH.exists():
        try:
            TEST_DB_PATH.unlink()
        except Exception:
            pass
    yield
    if TEST_DB_PATH.exists():
        try:
            TEST_DB_PATH.unlink()
        except Exception:
            pass

def test_memory_manager_initialization_and_seeding():
    """Verify MemoryManager creates the table and seeds baseline battlecard memories."""
    MemoryManager.init_table()
    summary = MemoryManager.get_memory_intelligence_summary()
    
    assert summary["total_interactions_logged"] >= 4
    assert summary["won_deals_count"] >= 3
    assert summary["win_rate_pct"] > 0
    assert summary["total_revenue_won"] > 0
    assert len(summary["top_objection_categories"]) >= 1

def test_memory_manager_record_and_recall():
    """Verify recording custom interaction outcomes and semantic metro recall."""
    MemoryManager.init_table()
    
    mem_id = MemoryManager.record_interaction(
        lead_id="test_lead_miami",
        clinic_name="Miami Ocean Dental",
        doctor_name="Dr. Rodriguez",
        metro="Miami",
        outcome="WON",
        objection_category="AFTER_HOURS_COST",
        objection_quote="We weren't sure if after-hours calls were worth answering.",
        effective_rebuttal="Showed that 3 emergency calls per week equate to $4,500/mo.",
        deal_value=3979.0,
        lessons_learned="Emphasize emergency root canal and extraction margins."
    )
    assert mem_id > 0
    
    lead_dict = {
        "id": "test_lead_miami_2",
        "name": "Biscayne Bay Dental",
        "address": "100 Biscayne Blvd, Miami, FL 33132",
        "doctor_name": "Dr. Smith"
    }
    learnings = MemoryManager.get_learnings_for_lead(lead_dict)
    assert learnings["metro"] == "Miami"
    assert learnings["won_cases_count"] >= 1
    assert "Miami Ocean Dental" in learnings["won_precedents"][0]["clinic_name"]
    assert "[PRECEDENT]" in learnings["memory_summary_prompt"]

def test_calculate_win_probability_five_drivers():
    """Verify the 5-point empirical closing probability engine."""
    # Lead 1: High Fit (Doctor named, high reviews, large leakage, independent owner, no chat)
    lead_high = {
        "name": "Lakeline Family Dental",
        "doctor_name": "Dr. Sarah Miller",
        "review_count": 250,
        "rating": 4.9,
        "missed_rev_max": 6500,
        "technologies": ["WordPress", "Google Analytics"]
    }
    prob_high, reasons_high = AIQualifier.calculate_win_probability(
        lead_dict=lead_high,
        technologies=lead_high["technologies"],
        estimated_monthly_leakage=6500
    )
    assert prob_high >= 85
    assert len(reasons_high) >= 5
    assert any("Doctor identified" in r for r in reasons_high)
    assert any("High revenue leakage" in r for r in reasons_high)
    assert any("Zero 24/7 web chat" in r for r in reasons_high)

    # Lead 2: Corporate DSO Penalty
    lead_dso = {
        "name": "Aspen Dental Corporate Care",
        "doctor_name": None,
        "review_count": 15,
        "rating": 3.8,
        "missed_rev_max": 1500,
        "technologies": ["Podium Webchat", "NexHealth Booking"]
    }
    prob_dso, reasons_dso = AIQualifier.calculate_win_probability(
        lead_dict=lead_dso,
        technologies=lead_dso["technologies"],
        estimated_monthly_leakage=1500
    )
    assert prob_dso <= 50
    assert any("Corporate DSO detected" in r for r in reasons_dso)

def test_dental_caller_persona_memory_flywheel():
    """Verify DentalCallerPersona incorporates institutional memory into scripts and prompts."""
    lead = {
        "name": "South Austin Dental",
        "doctor_name": "Dr. Henderson",
        "address": "South Congress, Austin, TX 78704",
        "rating": 4.9,
        "review_count": 120,
        "missed_rev_max": 5400
    }
    script = DentalCallerPersona.build_call_script(lead)
    assert "institutional_memory" in script
    assert script["institutional_memory"] is not None
    
    prompt = DentalCallerPersona.generate_system_prompt(lead)
    assert "TARGET CLINIC DETAILS:" in prompt
    assert "Austin" in prompt

def test_database_win_probability_persistence():
    """Verify database stores win_probability_pct and reasons in leads table and timeline."""
    db = DatabaseManager(db_path=TEST_DB_PATH)
    lead_id = "test_lead_win_prob_101"
    
    with db._get_connection() as conn:
        conn.execute("""
        INSERT INTO leads (id, name, stage, opportunity_score, buying_probability)
        VALUES (?, 'Lone Star Dental', 'FOUND', 80, 80)
        """, (lead_id,))
        conn.commit()

    success = db.update_lead_qualification(
        lead_id=lead_id,
        buying_probability=85,
        should_call="YES",
        pain_level="CRITICAL",
        practice_type="INDEPENDENT_OWNER",
        decision_accessibility="DIRECT_DOCTOR",
        buying_triggers=["Zero after-hours capture"],
        sales_verdict="Prime target practice",
        win_probability_pct=92,
        win_probability_reasons=["Doctor identified (+15%)", "Leakage > $4k (+15%)"]
    )
    assert success is True
    
    lead_saved = db.get_lead(lead_id)
    assert lead_saved["win_probability_pct"] == 92
    assert isinstance(lead_saved["win_probability_reasons"], list)
    assert len(lead_saved["win_probability_reasons"]) == 2
    assert "Doctor identified (+15%)" in lead_saved["win_probability_reasons"][0]
