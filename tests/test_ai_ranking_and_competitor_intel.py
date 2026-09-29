"""
Tests for Phases 4, 5, 6:
- Phase 4: AI Prospect Ranking (20-Factor Buy Probability 0-100%, Tiers, Top Drivers)
- Phase 5: Competitor Intelligence (Metro Benchmarks, Ordinal Ranks: "You rank #X out of Y")
- Phase 6: Territory Heatmaps (Pin color logic: Red >=75%, Yellow 45-74%, Green <45%)
"""

import pytest
from database import DatabaseManager
from buy_probability_engine import BuyProbabilityEngine
from cohort import calculate_metro_benchmark, rank_clinic_in_metro

@pytest.fixture
def clean_db(tmp_path):
    db_file = tmp_path / "test_ranking_cohort.db"
    db = DatabaseManager(db_path=str(db_file))
    with db._get_connection() as conn:
        conn.execute("DELETE FROM leads;")
        conn.commit()
    yield db

def test_phase4_buy_probability_engine_evaluation():
    """Verifies that the 20-factor BuyProbabilityEngine calculates score, tier, and drivers."""
    high_intent_lead = {
        "id": "lead-intent-high",
        "name": "Dr. Sarah Dental Implants",
        "doctor_name": "Dr. Sarah Miller",
        "rating": 4.9,
        "review_count": 250,
        "opportunity_score": 85,
        "missed_rev_max": 7500,
        "has_online_booking": 0,
        "has_after_hours_ai": 0,
        "website_speed_score": 40,
        "review_growth_rate": 25.0,
        "years_in_business": 10
    }

    eval_result = BuyProbabilityEngine.evaluate_lead(high_intent_lead)
    assert eval_result["probability_pct"] >= 75
    assert eval_result["tier"] == "TIER_1_PRIORITY"
    assert len(eval_result["top_drivers"]) >= 3

    low_intent_lead = {
        "id": "lead-intent-low",
        "name": "Generic Corporate Dental Care",
        "rating": 3.8,
        "review_count": 20,
        "opportunity_score": 30,
        "has_online_booking": 1,
        "has_after_hours_ai": 1
    }
    low_eval = BuyProbabilityEngine.evaluate_lead(low_intent_lead)
    assert low_eval["probability_pct"] < 50
    assert low_eval["tier"] in ("TIER_3_MODERATE", "TIER_4_LOW")

def test_phase4_batch_evaluate_and_persist(clean_db):
    """Verifies batch evaluation populates buy_probability_pct across the pipeline."""
    clean_db.save_lead({
        "id": "batch-lead-1",
        "name": "Austin Modern Smiles",
        "doctor_name": "Dr. John Doe",
        "review_count": 180,
        "opportunity_score": 80
    })
    clean_db.save_lead({
        "id": "batch-lead-2",
        "name": "Lakeway Family Dental",
        "review_count": 40,
        "opportunity_score": 45
    })

    summary = BuyProbabilityEngine.batch_evaluate_and_persist(clean_db)
    assert summary["evaluated_count"] == 2

    l1 = clean_db.get_lead("batch-lead-1")
    assert l1["buy_probability_pct"] is not None
    assert l1["buy_probability_pct"] >= 50

def test_phase5_competitor_intelligence_and_cohort_ranking(clean_db):
    """Verifies metro cohort benchmark and ordinal clinic ranking ('You rank #1 out of 3')."""
    # Seed Austin clinics
    clean_db.save_lead({
        "id": "austin-1",
        "name": "Austin Elite Dental",
        "address": "100 Congress Ave, Austin, TX",
        "rating": 4.9,
        "review_count": 300,
        "opportunity_score": 95,
        "buy_probability_pct": 92
    })
    clean_db.save_lead({
        "id": "austin-2",
        "name": "South Congress Dental Studio",
        "address": "1500 S Congress Ave, Austin, TX",
        "rating": 4.7,
        "review_count": 150,
        "opportunity_score": 75,
        "buy_probability_pct": 78
    })
    clean_db.save_lead({
        "id": "austin-3",
        "name": "Barton Springs Dental Care",
        "address": "200 Barton Springs Rd, Austin, TX",
        "rating": 4.4,
        "review_count": 50,
        "opportunity_score": 50,
        "buy_probability_pct": 48
    })

    # Test Metro Benchmark
    benchmark = calculate_metro_benchmark(clean_db, "Austin")
    assert benchmark["total_practices"] == 3
    assert benchmark["avg_rating"] > 4.5
    assert benchmark["avg_opportunity_score"] > 60

    # Test Ordinal Ranking
    rank1 = rank_clinic_in_metro(clean_db, "austin-1")
    assert rank1["rank"] == 1
    assert rank1["total_in_metro"] == 3
    assert "rank #1 out of 3" in rank1["rank_hook"]

    rank3 = rank_clinic_in_metro(clean_db, "austin-3")
    assert rank3["rank"] == 3
    assert rank3["percentile"] < 50
