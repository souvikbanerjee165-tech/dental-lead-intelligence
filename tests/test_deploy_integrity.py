"""
End-to-End Deployment Integrity & Zero-Crash Health Verification Test.
Validates all core subsystems before deploying to Google Cloud.
"""

import pytest
import asyncio
from database import DatabaseManager
from pre_call_dossier import PreCallDossierCompiler
from empathy_voice_prompts import EmpathyVoicePromptEngine
from carrier_reputation_manager import CarrierReputationManager
from http_scraper_shield import HttpScraperShield
from missed_revenue_diagnostic import MissedRevenueDiagnosticEngine
from google_places_client import GooglePlacesClient


def test_database_and_dnc_schema():
    db = DatabaseManager()
    assert db is not None

    test_phone = "+19995550199"
    # Ensure add to DNC works
    success = db.add_to_dnc(test_phone, clinic_name="Test DNC Clinic", reason="TEST_REASON")
    assert success is True
    assert db.is_dnc_phone(test_phone) is True

    # Record carrier call log
    call_id = db.record_carrier_call(
        caller_phone="+12145550100",
        destination_phone=test_phone,
        lead_id="test_lead_id",
        area_code="214",
        status="COMPLETED",
        duration_sec=45
    )
    assert call_id > 0
    assert db.get_hourly_call_count("+12145550100") >= 1


def test_pre_call_dossier_compiler():
    db = DatabaseManager()
    lead = {
        "id": "lead_deploy_test",
        "name": "Dallas Cosmetic Smiles",
        "doctor_name": "Dr. Sarah Jenkins, DDS",
        "rating": 4.9,
        "review_count": 88,
        "phone": "+1 (214) 555-0144",
        "address": "Dallas, TX",
        "website": "https://dallascosmeticsmiles.com"
    }
    dossier = PreCallDossierCompiler.compile_dossier(lead, db=db)
    assert dossier["clinic_name"] == "Dallas Cosmetic Smiles"
    assert dossier["doctor_display"] == "Dr. Sarah Jenkins"
    assert "monthly_leakage" in dossier
    assert len(dossier["intake_friction_points"]) > 0

    briefing = PreCallDossierCompiler.format_llm_prompt_briefing(dossier)
    assert "LIVE PRE-CALL CLINIC INTELLIGENCE" in briefing


def test_empathy_voice_prompts():
    dossier = {
        "clinic_name": "Austin Premier Smiles",
        "doctor_display": "Dr. Vance",
        "city": "Austin",
        "monthly_leakage": "$14,000",
        "detected_ehr": "Dentrix"
    }
    prompt = EmpathyVoicePromptEngine.build_voice_system_prompt(dossier)
    assert "THE 12-SECOND BREVITY RULE" in prompt
    assert "3-STEP EMPATHY BRIDGE" in prompt

    # Test objection detection
    detected = EmpathyVoicePromptEngine.detect_objection("We already have a receptionist who answers the phone")
    assert detected == "have_front_desk"

    rebuttal = EmpathyVoicePromptEngine.get_empathy_rebuttal("have_front_desk", dossier)
    assert len(rebuttal.split()) > 5

    # Test brevity enforcement
    wordy_text = "This is a very long response that goes on and on without stopping because the model wanted to talk too much and explain everything in great detail instead of pausing."
    brev = EmpathyVoicePromptEngine.enforce_brevity(wordy_text)
    assert len(brev.split()) <= 20


def test_carrier_reputation_manager():
    db = DatabaseManager()
    mgr = CarrierReputationManager(db=db)
    assert mgr.extract_area_code("+12145550123") == "214"
    assert mgr.extract_area_code("5125550123") == "512"

    # DNC opt out check
    opt_out_detected = mgr.check_for_opt_out("Please stop calling this number, take me off your list")
    assert opt_out_detected is True

    # Process opt out
    res = mgr.process_opt_out("+12145559988", clinic_name="Test Exit", reason="UNIT_TEST")
    assert res["success"] is True
    assert "removed your number" in res["polite_exit_statement"]


def test_missed_revenue_diagnostic_engine():
    db = DatabaseManager()
    lead = {
        "id": "diag_test_id",
        "name": "Atlanta Dental Studio",
        "doctor_name": "Dr. Davis",
        "rating": 4.7,
        "review_count": 92,
        "phone": "+1 (404) 555-0188",
        "address": "Atlanta, GA"
    }
    data = MissedRevenueDiagnosticEngine.generate_diagnostic_data(lead, db=db)
    assert data["monthly_leakage_dollars"] > 0
    assert len(data["findings"]) > 0

    links = MissedRevenueDiagnosticEngine.generate_outreach_links(lead)
    assert "wa.me" in links["whatsapp_url"]
    assert "mail.google.com" in links["gmail_url"]
    assert "/diagnostic/diag_test_id" in links["diagnostic_url"]

    html = MissedRevenueDiagnosticEngine.render_diagnostic_html(lead)
    assert "<!DOCTYPE html>" in html
    assert "Atlanta Dental Studio" in html


def test_google_places_client_interface():
    client = GooglePlacesClient()
    # Should cleanly initialize without errors
    assert hasattr(client, "search_clinics")
    assert hasattr(client, "is_configured")
