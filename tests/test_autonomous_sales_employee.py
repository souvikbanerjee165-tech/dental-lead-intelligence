import pytest
from fastapi.testclient import TestClient
from app import app, db
from territory_manager import TerritoryManager, TOP_US_DENTAL_MARKETS
from ai_qualifier import AIQualifier, AIQualificationResult
from outreach_generator import OutreachGenerator, OutreachPackage

client = TestClient(app)

def test_territory_manager_catalog_and_selection():
    # Verify curated catalog contains top markets
    catalog = TerritoryManager.get_market_catalog()
    assert len(catalog) >= 25
    cities = [m["city"] for m in catalog]
    assert "Scottsdale" in cities
    assert "Plano" in cities
    assert "Austin" in cities

    # Initialize territories in database
    TerritoryManager.initialize_territories(db)
    all_t = db.get_all_territories()
    assert len(all_t) >= len(catalog)

    # Verify next target selection returns high affluence pending territory
    next_t = TerritoryManager.get_next_target_territory(db)
    assert next_t is not None
    assert "city" in next_t
    assert "affluence_tier" in next_t

def test_ai_qualifier_deterministic_heuristics():
    lead_dict = {
        "id": "lead_test_qualifier",
        "name": "Oakmont Family Dental",
        "rating": 4.9,
        "review_count": 310,
        "phone": "5125551234",
        "website": "https://oakmontdental.com"
    }

    result = AIQualifier._deterministic_qualification(
        lead_id=lead_dict["id"],
        name=lead_dict["name"],
        rating=lead_dict["rating"],
        reviews=lead_dict["review_count"],
        phone=lead_dict["phone"],
        website=lead_dict["website"],
        doctor_name="Dr. Robert Oakmont",
        technologies=["WordPress", "Google Analytics"],
        opportunity_score=85,
        estimated_monthly_leakage=4500
    )

    assert isinstance(result, AIQualificationResult)
    assert result.would_spend_30min_calling == "YES"
    assert result.buying_probability_pct >= 75
    assert result.pain_level in ("CRITICAL", "HIGH")
    assert result.decision_accessibility == "DIRECT_DOCTOR"
    assert result.practice_type == "INDEPENDENT_OWNER"
    assert len(result.buying_triggers) >= 1
    assert "Robert Oakmont" in result.buying_triggers[0] or "after-hours" in result.buying_triggers[0]

def test_outreach_generator_multichannel_copy():
    lead_dict = {
        "id": "lead_test_outreach",
        "name": "Boca Premier Dentistry",
        "phone": "+1 561 555 9988",
        "rating": 4.8,
        "review_count": 140,
        "address": "1200 Glades Rd, Boca Raton, FL 33431"
    }

    outreach = OutreachGenerator.generate(
        lead_dict=lead_dict,
        doctor_name="Dr. Amanda Cross",
        monthly_leakage=5200
    )

    assert isinstance(outreach, OutreachPackage)
    assert "Dr. Cross" in outreach.cold_email_body
    assert "$5,200/month" in outreach.cold_email_body
    assert "Boca Raton" in outreach.email_subject
    assert "Dr. Cross" in outreach.follow_up_body
    assert len(outreach.sms_text) > 20
    assert "WhatsApp" in outreach.whatsapp_pitch
    assert "15615559988" in outreach.whatsapp_url

def test_call_outcome_logging_and_crm_progression():
    # Insert or get a test lead
    lead_id = "lead_test_call_flow"
    with db._get_connection() as conn:
        conn.execute("""
        INSERT OR REPLACE INTO leads (id, name, rating, review_count, phone, stage, opportunity_score, buying_probability, should_call)
        VALUES (?, 'Lone Star Pediatric Dental', 4.9, 210, '5125550011', 'FOUND', 88, 92, 'YES')
        """, (lead_id,))
        conn.commit()

    # 1. Log call outcome as INTERESTED
    res = client.post(f"/api/leads/{lead_id}/call-outcome", json={
        "outcome": "INTERESTED",
        "notes": "Spoke with Dr. Star; agreed to 15-min calendar walkthrough on Thursday",
        "duration_sec": 185
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["recorded_outcome"] == "INTERESTED"
    assert data["new_crm_stage"] == "MEETING"

    # Verify stage transition recorded in database
    lead = db.get_lead(lead_id)
    assert lead["stage"] == "MEETING"

def test_todays_calls_api():
    res = client.get("/api/queue/todays-calls?min_probability=50")
    assert res.status_code == 200
    leads = res.json()
    assert isinstance(leads, list)
    if len(leads) > 0:
        first = leads[0]
        assert "buying_probability" in first
        assert "missed_rev_range" in first

def test_territories_api():
    res = client.get("/api/territories")
    assert res.status_code == 200
    data = res.json()
    assert "total_territories" in data
    assert data["total_territories"] >= 25
    assert "next_target" in data
    assert "territories" in data

def test_learning_insights_api():
    res = client.get("/api/learning/insights")
    assert res.status_code == 200
    data = res.json()
    assert "total_calls" in data
    assert "interest_rate_pct" in data
    assert "win_rate_pct" in data
    assert "insights" in data
    assert len(data["insights"]) >= 1

def test_outreach_api():
    lead_id = "lead_test_call_flow"
    res = client.get(f"/api/leads/{lead_id}/outreach")
    assert res.status_code == 200
    data = res.json()
    assert "cold_email_body" in data
    assert "sms_text" in data
    assert "whatsapp_url" in data
