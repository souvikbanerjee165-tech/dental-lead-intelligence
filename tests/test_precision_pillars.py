"""
Unit and Integration Tests for the 5 Precision & Usefulness Pillars:
1. Empirical Mystery Shopper Verification & Friction Audit Engine
2. Dental EHR / PMS Tech-Stack Sniffer & US NPI Registry Enrichment
3. Dynamic 1-Click Interactive WhatsApp Demo Engine & Mobile Simulator
4. Automated 5-Touch Omnichannel Sales Cadence Engine
5. Real-Time Institutional Objection Intelligence & Conversion Flywheel
"""

import pytest
from fastapi.testclient import TestClient

from app import app
from database import DatabaseManager
from ehr_sniffer import EHRSniffer
from npi_registry import NPIRegistryEnricher
from whatsapp_demo_engine import WhatsAppDemoEngine
from mystery_shopper import MysteryShopperAuditor
from sales_cadence import SalesCadenceEngine
from objection_analytics import ObjectionAnalyticsEngine


@pytest.fixture
def test_client():
    return TestClient(app)


@pytest.fixture
def db():
    return DatabaseManager()


# -------------------------------------------------------------
# 1. EHR / PMS Tech-Stack Sniffer Unit Tests
# -------------------------------------------------------------

def test_ehr_sniffer_detects_dentrix():
    sample_html = """
    <html>
      <head><title>Oak Hill Dental</title></head>
      <body>
        <a href="https://dentrixascend.com/portal/oakhill">Patient Portal</a>
        <script src="https://assets.nexhealth.com/widget.js"></script>
      </body>
    </html>
    """
    result = EHRSniffer.sniff_html(sample_html, website_url="https://oakhilldental.com")
    assert result["detected_pms"] == "Dentrix (Henry Schein)"
    assert "NexHealth" in result["detected_tools"]
    assert result["battlecard_recommendation"] == "dentrix"
    assert result["confidence_score"] >= 0.90


def test_ehr_sniffer_detects_eaglesoft_and_weave():
    sample_html = """
    <html>
      <body>
        <div class="patientviewer-portal">Access Eaglesoft Portal</div>
        <script src="https://getweave.com/widget.js"></script>
      </body>
    </html>
    """
    result = EHRSniffer.sniff_html(sample_html)
    assert result["detected_pms"] == "Eaglesoft (Patterson Dental)"
    assert "Weave" in result["detected_tools"]


def test_ehr_sniffer_fallback_on_premise():
    empty_html = "<html><body>Simple static text without portals</body></html>"
    result = EHRSniffer.sniff_html(empty_html)
    assert result["detected_pms"] is None
    assert result["battlecard_recommendation"] == "dentrix"
    assert "Standard Dentrix/Eaglesoft" in result["summary"]


# -------------------------------------------------------------
# 2. US CMS NPI Registry Unit Tests
# -------------------------------------------------------------

def test_npi_registry_enricher_structure():
    # Test query format construction and failure resilience
    res = NPIRegistryEnricher.lookup_provider(
        first_name="Sarah",
        last_name="Jenkins",
        city="Austin",
        state="TX"
    )
    # The call should never raise an unhandled exception
    assert isinstance(res, dict)
    assert "found" in res
    assert "summary" in res


# -------------------------------------------------------------
# 3. Dynamic WhatsApp Demo Engine Unit Tests
# -------------------------------------------------------------

def test_whatsapp_demo_assets_generation():
    lead_data = {
        "id": "lead_austin_smile",
        "name": "Austin Smile Center",
        "doctor_name": "Dr. Marcus Vance",
        "address": "1200 S Congress Ave, Austin, TX 78704",
        "phone": "+1 (512) 555-0144",
        "high_value_services": ["Dental Implants", "Emergency Care"]
    }

    assets = WhatsAppDemoEngine.generate_demo_assets(lead_data, base_app_url="http://127.0.0.1:8000")
    assert assets["lead_id"] == "lead_austin_smile"
    assert assets["clinic_name"] == "Austin Smile Center"
    assert "Dr. Marcus Vance" in assets["doctor_name"]
    assert "https://wa.me/" in assets["whatsapp_link"]
    assert "https://api.qrserver.com/v1/create-qr-code/" in assets["qr_code_url"]
    assert "http://127.0.0.1:8000/demo/lead_austin_smile" == assets["web_simulation_url"]
    assert "Austin Smile Center" in assets["starter_message"]
    assert "Austin Smile Center" in assets["sms_pitch"]


def test_whatsapp_demo_html_rendering():
    lead_data = {
        "id": "lead_test_demo",
        "name": "Hill Country Dental",
        "doctor_name": "Dr. Emily Stone",
        "address": "Sunset Valley, TX"
    }

    html = WhatsAppDemoEngine.render_demo_page_html(lead_data)
    assert "<!DOCTYPE html>" in html
    assert "Hill Country Dental" in html
    assert "Dr. Emily Stone" in html
    assert "Emergency Toothache" in html
    assert "24/7 AI Patient Assistant" in html


# -------------------------------------------------------------
# 4. Empirical Mystery Shopper Verification Audit Unit Tests
# -------------------------------------------------------------

def test_mystery_shopper_voicemail_friction_proof():
    lead_data = {
        "id": "lead_downtown_dental",
        "name": "Downtown Dental Care",
        "phone": "(512) 555-9012",
        "doctor_name": "Dr. Robert Chen"
    }

    proof = MysteryShopperAuditor.generate_audit_proof(
        lead_dict=lead_data,
        ring_count=5,
        reached_voicemail=True
    )
    assert proof["status"] == "CONFIRMED_PHONE_FRICTION"
    assert proof["ring_count"] == 5
    assert proof["reached_voicemail"] is True
    assert proof["leakage_risk"] == "HIGH"
    assert "Dr. Robert Chen" in proof["sales_pitch_quote"]
    assert "voicemail" in proof["evidence_summary"]


def test_mystery_shopper_resolved_intake_proof():
    lead_data = {
        "id": "lead_247_dental",
        "name": "24/7 Dental Express",
        "phone": "(512) 555-2424"
    }

    proof = MysteryShopperAuditor.generate_audit_proof(
        lead_dict=lead_data,
        ring_count=2,
        reached_voicemail=False
    )
    assert proof["status"] == "RESOLVED_INTAKE"
    assert proof["leakage_risk"] == "LOW"


# -------------------------------------------------------------
# 5. Automated 5-Touch Cadence Engine Unit Tests
# -------------------------------------------------------------

def test_sales_cadence_engine_lifecycle():
    lead_data = {
        "id": "lead_cadence_test",
        "name": "Lone Star Dental",
        "cadence_step": 1
    }

    cadence = SalesCadenceEngine.get_lead_cadence(lead_data)
    assert cadence["current_step"] == 1
    assert cadence["total_steps"] == 5
    assert cadence["current_channel"] == "PHONE"
    assert len(cadence["cadence_timeline"]) == 5

    # Step progression
    step2 = SalesCadenceEngine.advance_cadence(1, "COMPLETED")
    assert step2["next_step"] == 2
    assert step2["status"] == "IN_PROGRESS"

    # Conversion shortcut
    converted = SalesCadenceEngine.advance_cadence(2, "MEETING_BOOKED")
    assert converted["next_step"] == 5
    assert converted["status"] == "CONVERTED"


# -------------------------------------------------------------
# 6. Objection Analytics Engine Unit Tests
# -------------------------------------------------------------

def test_objection_analytics_report(db):
    report = ObjectionAnalyticsEngine.get_objection_report(db)
    assert report["total_calls_analyzed"] >= 100
    assert "objections_breakdown" in report
    assert len(report["objections_breakdown"]) >= 4
    
    categories = [o["category"] for o in report["objections_breakdown"]]
    assert any("Dentrix" in c for c in categories)
    assert any("Pricing" in c for c in categories)

    for item in report["objections_breakdown"]:
        assert item["frequency_pct"] > 0
        assert item["win_rate_pct"] > 0
        assert len(item["recommended_rebuttal"]) > 10


# -------------------------------------------------------------
# 7. FastAPI Precision Pillar Endpoints Integration Tests
# -------------------------------------------------------------

def test_api_whatsapp_demo_page(test_client):
    res = test_client.get("/demo/preview")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "WhatsApp" in res.text


def test_api_whatsapp_demo_assets(test_client):
    res = test_client.get("/api/leads/preview/whatsapp-demo")
    assert res.status_code == 200
    data = res.json()
    assert "whatsapp_link" in data
    assert "qr_code_url" in data
    assert "sms_pitch" in data


def test_api_objection_analytics(test_client):
    res = test_client.get("/api/analytics/objections")
    assert res.status_code == 200
    data = res.json()
    assert "top_objection" in data
    assert "objections_breakdown" in data
    assert "tactical_insights" in data


def test_api_lead_precision_lifecycle(test_client, db):
    # Insert test lead into persistent sqlite
    lead_id = "lead_test_precision_suite"
    db.save_lead({
        "id": lead_id,
        "name": "Precision Test Dental",
        "doctor_name": "Dr. Alan Grant",
        "address": "100 Test St, Dallas, TX 75201",
        "phone": "+1 (214) 555-0199",
        "website": "precisiontestdental.com"
    })

    # 1. Sniff Tech and NPI
    sniff_res = test_client.post(f"/api/leads/{lead_id}/sniff-tech")
    assert sniff_res.status_code == 200
    sniff_data = sniff_res.json()
    assert "detected_ehr" in sniff_data
    assert "ehr_sniffer" in sniff_data
    assert "npi_registry" in sniff_data

    # 2. Mystery Shopper Audit
    audit_res = test_client.get(f"/api/leads/{lead_id}/mystery-audit")
    assert audit_res.status_code == 200
    audit_data = audit_res.json()
    assert audit_data["status"] == "CONFIRMED_PHONE_FRICTION"
    assert "Dr. Alan Grant" in audit_data["sales_pitch_quote"]

    # 3. Omnichannel Cadence Status
    cadence_res = test_client.get(f"/api/leads/{lead_id}/cadence")
    assert cadence_res.status_code == 200
    cad_data = cadence_res.json()
    assert cad_data["current_step"] == 1

    # 4. Advance Cadence Step
    adv_res = test_client.post(f"/api/leads/{lead_id}/cadence/advance", json={"outcome": "COMPLETED"})
    assert adv_res.status_code == 200
    adv_data = adv_res.json()
    assert adv_data["current_step"] == 2
