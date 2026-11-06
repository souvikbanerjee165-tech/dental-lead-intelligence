import os
import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

from app import app, db
from google_places_client import GooglePlacesClient
from high_intent_pinpointer import HighIntentPinpointer
from territory_checkout import TerritoryCheckoutEngine
from roi_calculator import ROICalculator
from hygiene_recall_calculator import HygieneRecallCalculator
from territory_manager import TerritoryManager

client = TestClient(app)


def test_pricing_unified_1200_setup_497_monthly():
    """Verify $1,200 installation + $497/mo retainer is unified across all sales & ROI engines."""
    assert TerritoryCheckoutEngine.SETUP_FEE_USD == 1200.0
    assert TerritoryCheckoutEngine.MONTHLY_MAINTENANCE_USD == 497.0
    assert HighIntentPinpointer.SETUP_FEE_USD == 1200.0
    assert HighIntentPinpointer.MONTHLY_RETAINER_USD == 497.0

    roi = ROICalculator.calculate(monthly_appointments=180)
    assert roi["inputs"]["setup_fee"] == 1200.0
    assert roi["inputs"]["monthly_software_cost"] == 497.0

    hygiene = HygieneRecallCalculator.calculate_hygiene_leakage({"name": "Test Dental", "review_count": 100})
    assert hygiene["setup_fee_usd"] == 1200.0


def test_us_and_canada_markets_in_territory_catalog():
    """Verify top US and Canadian dental markets are included in TerritoryManager."""
    catalog = TerritoryManager.get_market_catalog()
    cities = {m["city"] for m in catalog}
    assert "Scottsdale" in cities
    assert "Austin" in cities
    assert "Toronto" in cities
    assert "Vancouver" in cities
    assert "Calgary" in cities


def test_zero_waste_corporate_dso_filter_and_hours_parser():
    """Verify Corporate DSOs are caught before LLM spend and opening hours quantify voicemail window."""
    assert GooglePlacesClient.is_corporate_dso("Aspen Dental - Austin") is True
    assert GooglePlacesClient.is_corporate_dso("Heartland Dental Care") is True
    assert GooglePlacesClient.is_corporate_dso("Dentalcorp Toronto") is True
    assert GooglePlacesClient.is_corporate_dso("123Dentist Vancouver") is True
    assert GooglePlacesClient.is_corporate_dso("Barton Springs Family Dentistry", "https://bartonspringsdental.com") is False

    hours_info = GooglePlacesClient.analyze_opening_hours({
        "weekdayDescriptions": [
            "Monday: 8:00 AM – 5:00 PM",
            "Tuesday: 8:00 AM – 5:00 PM",
            "Wednesday: 8:00 AM – 5:00 PM",
            "Thursday: 8:00 AM – 5:00 PM",
            "Friday: Closed",
            "Saturday: Closed",
            "Sunday: Closed"
        ]
    })
    assert hours_info["closed_fridays"] is True
    assert hours_info["closed_weekends"] is True
    assert hours_info["weekly_closed_hours"] >= 120


@pytest.mark.anyio
async def test_google_places_sqlite_cache_prevents_duplicate_api_spend(tmp_path):
    """Verify identical Places queries hit the local SQLite cache on the 2nd call ($0.00 spent)."""
    cache_db = str(tmp_path / "places_cache_test.db")
    p_client = GooglePlacesClient(api_key="AIzaSyRealLookingKeyForTesting123456789", db_path=cache_db)

    mock_http_resp = MagicMock()
    mock_http_resp.status_code = 200
    mock_http_resp.json.return_value = {
        "places": [
            {
                "id": "place_1",
                "displayName": {"text": "Oakville Smile Studio"},
                "formattedAddress": "123 Lakeshore Rd E, Oakville, ON, Canada",
                "nationalPhoneNumber": "(905) 555-0192",
                "rating": 4.8,
                "userRatingCount": 145,
                "websiteUri": "https://oakvillesmilestudio.ca",
                "businessStatus": "OPERATIONAL"
            },
            {
                "id": "place_dso",
                "displayName": {"text": "Aspen Dental"},
                "formattedAddress": "500 Main St, Austin, TX",
                "nationalPhoneNumber": "(512) 555-0000",
                "rating": 3.9,
                "userRatingCount": 400,
                "businessStatus": "OPERATIONAL"
            }
        ]
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_http_resp) as mock_post:
        # 1st call -> hits API, filters out Aspen Dental DSO, caches Oakville Smile Studio
        res1 = await p_client.search_clinics("Dentists in Oakville, ON", limit=10)
        assert len(res1) == 1
        assert res1[0].name == "Oakville Smile Studio"
        assert mock_post.call_count == 1

        # 2nd call -> served 100% from SQLite cache (mock_post NOT called again!)
        res2 = await p_client.search_clinics("Dentists in Oakville, ON", limit=10)
        assert len(res2) == 1
        assert res2[0].name == "Oakville Smile Studio"
        assert mock_post.call_count == 1


def test_high_intent_pinpointer_and_closer_sheet_endpoints():
    """Verify HighIntentPinpointer scores independent dentists high, disqualifies DSOs, and serves full call script."""
    lead_id = "lead_high_intent_prime_001"
    db.save_lead({
        "id": lead_id,
        "name": "Scottsdale Implant & Cosmetic Dentistry",
        "doctor_name": "Dr. Elena Rostova, DDS",
        "phone": "(480) 555-0188",
        "address": "7400 E Camelback Rd, Scottsdale, AZ",
        "website": "https://scottsdaleimplantdentistry.com",
        "rating": 4.9,
        "review_count": 165,
        "opportunity_score": 92
    })

    try:
        # 1. Test /api/leads/{lead_id}/closer-sheet
        resp = client.get(f"/api/leads/{lead_id}/closer-sheet")
        assert resp.status_code == 200
        sheet = resp.json()
        assert sheet["high_intent_score"] >= 85
        assert sheet["intent_grade"] == "A_PLUS_PRIME"
        assert sheet["unit_economics"]["setup_fee_usd"] == 1200
        assert sheet["unit_economics"]["monthly_retainer_usd"] == 497
        assert "Dr. Rostova" in sheet["call_playbook"]["step2_doctor_opener_20s"]
        assert "$1,200" in sheet["call_playbook"]["step3_irresistible_offer_pitch"]
        assert "$497" in sheet["call_playbook"]["step3_irresistible_offer_pitch"]
        assert len(sheet["call_playbook"]["step4_objection_rebuttals"]) == 4

        # 2. Test /api/high-intent/top-targets
        top_resp = client.get("/api/high-intent/top-targets?limit=15")
        assert top_resp.status_code == 200
        top_data = top_resp.json()
        assert top_data["goal_tracker"]["target_clients"] == 10
        assert top_data["goal_tracker"]["target_upfront_cash_usd"] == 12000
        assert top_data["goal_tracker"]["target_mrr_usd"] == 4970
        assert any(t["lead_id"] == lead_id for t in top_data["top_targets"])
    finally:
        with db._get_connection() as conn:
            conn.cursor().execute("DELETE FROM leads WHERE id = ?", (lead_id,))
            conn.commit()
