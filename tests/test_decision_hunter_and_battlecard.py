import pytest
from fastapi.testclient import TestClient
from bs4 import BeautifulSoup
from app import app, db
from decision_hunter import DecisionMakerHunter
from battlecard import SalesBattlecardGenerator
from models import RawLead, WebsiteAuditResult, ScoredLead

client = TestClient(app)

SAMPLE_HOMEPAGE_HTML = """
<!DOCTYPE html>
<html>
<head><title>Apex Dental Studio - Austin</title></head>
<body>
  <h1>Welcome to Apex Dental Studio</h1>
  <h2>Meet Dr. Marcus Vance, DDS</h2>
  <p>Dr. Vance has been serving Austin families for over 15 years with premier cosmetic and restorative dentistry.</p>
  <div>
    <h3>Clinical Staff</h3>
    <p>Elena Rostova, DMD - Associate Dentist</p>
    <p>Sarah Jenkins - Practice Manager</p>
  </div>
  <footer>
    <a href="mailto:contact@apexdentalstudio.com">Email Us</a>
    <a href="/our-team">Our Team</a>
  </footer>
</body>
</html>
"""

def test_decision_maker_hunter_extraction():
    soup = BeautifulSoup(SAMPLE_HOMEPAGE_HTML, "html.parser")
    res = DecisionMakerHunter.extract_from_html(SAMPLE_HOMEPAGE_HTML, soup)

    # Verify primary doctor detected
    assert res["primary_doctor"] is not None
    assert "Marcus Vance" in res["primary_doctor"]

    # Verify office manager detected
    assert res["practice_manager"] is not None
    assert "Sarah Jenkins" in res["practice_manager"]

    # Verify email extraction
    assert "contact@apexdentalstudio.com" in res["emails"]

    # Verify subpage link scoring and filtering
    subpages = DecisionMakerHunter.find_team_subpages(soup, "https://apexdentalstudio.com")
    assert any("our-team" in u for u in subpages)

def test_decision_maker_discard_false_positives():
    html = """
    <h1>About Us</h1>
    <h2>Dental Care That Matters</h2>
    <p>Meet our Emergency Dental team. Contact Us today.</p>
    """
    res = DecisionMakerHunter.extract_from_html(html)
    assert res["primary_doctor"] is None
    assert res["practice_manager"] is None

def test_sales_battlecard_generator_no_chatbot():
    lead_dict = {
        "id": "lead_test_001",
        "name": "Oak Creek Family Dental",
        "doctor_name": "Dr. Alan Grant, DDS",
        "decision_maker_role": "Practice Owner",
        "phone": "512-555-1234",
        "website": "https://oakcreekdental.com",
        "rating": 4.9,
        "review_count": 210,
        "opportunity_score": 85,
        "missed_rev_min": 4000,
        "missed_rev_max": 7500,
        "address": "123 Oak St, Austin, TX"
    }

    card = SalesBattlecardGenerator.generate_battlecard(lead_dict)

    assert card["doctor_name"] == "Dr. Alan Grant, DDS"
    assert "Dr. Alan Grant" in card["cold_call_doctor_script"]
    assert "Austin" in card["cold_call_doctor_script"]
    assert card["competitor_detected"] == "None"
    assert len(card["objection_matrix"]) == 3
    assert "wa.me/15125551234" in card["whatsapp_direct_url"]

def test_sales_battlecard_generator_competitor_tidio():
    lead_dict = {
        "id": "lead_test_002",
        "name": "Smiles of Dallas",
        "doctor_name": "Dr. Rachel Green",
        "decision_maker_role": "Clinical Director",
        "phone": "214-555-9876",
        "website": "https://smilesofdallas.com",
        "rating": 4.8,
        "review_count": 140,
        "detected_chatbot_name": "Tidio Live Chat",
        "address": "456 Main St, Dallas, TX"
    }

    card = SalesBattlecardGenerator.generate_battlecard(lead_dict)

    assert card["competitor_detected"] == "Tidio"
    assert "Tidio" in card["cold_call_doctor_script"]
    assert "Tidio" in card["tech_status"]
    # Verify competitor rebuttal is specifically about browser tabs vs. WhatsApp
    rebuttal_texts = [o["rebuttal"] for o in card["objection_matrix"]]
    assert any("Tidio" in r for r in rebuttal_texts)

def test_database_doctor_persistence():
    raw = RawLead(
        name="Lakeside Dental Arts",
        website="https://lakesidedentalarts.com",
        phone="512-555-7777",
        address="789 Lake Blvd, Austin, TX"
    )
    audit = WebsiteAuditResult(
        doctor_name="Dr. Gregory House, DMD",
        decision_maker_role="Founder & Chief Dentist",
        emails=["drhouse@lakesidedental.com"]
    )
    scored = ScoredLead(
        raw_lead=raw,
        audit=audit,
        opportunity_score=80,
        doctor_name="Dr. Gregory House, DMD",
        decision_maker_role="Founder & Chief Dentist"
    )

    lead_id, _ = db.save_scored_lead(scored, [])

    saved = db.get_lead(lead_id)
    assert saved is not None
    assert saved["doctor_name"] == "Dr. Gregory House, DMD"
    assert saved["decision_maker_role"] == "Founder & Chief Dentist"
    assert "drhouse@lakesidedental.com" in (saved["direct_emails"] or "")

def test_api_battlecard_endpoint():
    # Fetch existing lead or test lead
    leads = db.list_all_leads()
    if not leads:
        test_database_doctor_persistence()
        leads = db.list_all_leads()

    target_id = leads[0]["id"]
    res = client.get(f"/api/leads/{target_id}/battlecard")
    assert res.status_code == 200
    data = res.json()
    assert "doctor_name" in data
    assert "cold_call_doctor_script" in data
    assert "objection_matrix" in data
    assert "whatsapp_direct_url" in data

def test_api_briefing_today():
    res = client.get("/api/briefing/today")
    assert res.status_code == 200
    data = res.json()
    assert "total_targets_ready" in data
    assert "combined_monthly_missed_revenue" in data
    assert "total_annual_arr_opportunity" in data
    assert "targets" in data
    assert isinstance(data["targets"], list)
