"""
Automated Integration Tests for BANT/MEDDIC Enterprise Scoring & Executive PDF Dossier.
"""

import os
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app import app, db
from bant_meddic_scorer import DentalBANTMEDDICScorer
from executive_pdf_reporter import ExecutivePDFReporter
from llm_router import LLMRouter, PROVIDER_GROQ, PROVIDER_OPENROUTER

client = TestClient(app)


def test_dental_bant_meddic_scorer():
    """Verify BANT and MEDDIC qualification logic specialized for dental practices."""
    lead = {
        "id": "test_lead_austin_dental",
        "name": "Austin Premier Smiles",
        "doctor_name": "Sarah Jenkins",
        "city": "Austin",
        "state": "TX",
        "services": ["Invisalign", "Dental Implants", "Emergency Care"],
        "review_count": 84,
        "rating": 4.8,
        "is_dso": 0,
        "gatekeeper_name": "Maria",
        "monthly_leakage": 5200
    }
    audit = {
        "has_online_booking": False,
        "tech_stack": ["Dentrix", "Weave"],
        "negative_review_topics": ["long hold time", "missed call"]
    }

    eval_data = DentalBANTMEDDICScorer.evaluate_lead(lead, audit)

    assert "bant" in eval_data
    assert "meddic" in eval_data
    assert "recommendation" in eval_data

    # BANT Assertions
    bant = eval_data["bant"]
    assert 0 <= bant["total_score"] <= 100
    assert bant["rating"] in ("A_TIER", "B_TIER", "C_TIER")
    assert bant["dimensions"]["budget"]["score"] > 0
    assert bant["dimensions"]["authority"]["score"] > 0
    assert bant["dimensions"]["need"]["score"] > 0
    assert bant["dimensions"]["timeline"]["score"] > 0

    # MEDDIC Assertions
    meddic = eval_data["meddic"]
    assert 0 <= meddic["overall_completeness_pct"] <= 100
    assert meddic["tier"] in ("ENTERPRISE_READY", "QUALIFIED", "NURTURE")
    assert "metrics" in meddic["dimensions"]
    assert "economic_buyer" in meddic["dimensions"]
    assert "champion" in meddic["dimensions"]
    assert meddic["dimensions"]["economic_buyer"]["pct"] == 100  # Dr. Sarah Jenkins is verified


def test_executive_pdf_reporter_generation():
    """Verify vector PDF generation via ReportLab produces valid non-empty PDF document."""
    lead = {
        "id": "test_pdf_lead",
        "name": "Sunset Dental Studio",
        "doctor_name": "Marcus Vance",
        "city": "Dallas",
        "metro": "Dallas-Fort Worth",
        "phone": "+15125550199",
        "website": "https://sunsetdental.example.com",
        "monthly_leakage": 4800,
        "services": ["Cosmetic Dentistry", "Implants"],
        "review_count": 42
    }
    audit = {
        "has_online_booking": False,
        "tech_stack": ["Eaglesoft"],
        "mobile_friendly": True
    }

    pdf_path_str = ExecutivePDFReporter.generate_lead_dossier(
        lead=lead,
        audit=audit,
        output_filename="test_verification_dossier.pdf"
    )

    pdf_path = Path(pdf_path_str)
    assert pdf_path.exists(), f"PDF was not created at {pdf_path}"
    assert pdf_path.stat().st_size > 2000, "PDF file size too small (expected >2KB)"

    # Verify PDF magic header bytes
    with open(pdf_path, "rb") as f:
        header = f.read(5)
        assert header == b"%PDF-", f"Expected %PDF- magic header, got {header}"


def test_llm_router_provider_status_and_freellmapi_expansion():
    """Verify multi-provider status reflects Groq and OpenRouter additions."""
    status = LLMRouter.get_provider_status()
    assert "active_provider" in status
    assert "providers" in status

    providers = status["providers"]
    assert "GEMINI" in providers
    assert "GROQ" in providers
    assert "OPENAI" in providers
    assert "DEEPSEEK" in providers
    assert "OPENROUTER" in providers

    circuit_breakers = status["circuit_breakers"]
    assert "GROQ" in circuit_breakers
    assert "OPENROUTER" in circuit_breakers


def test_api_bant_meddic_and_pdf_endpoints():
    """Verify live FastAPI endpoints for BANT-MEDDIC and PDF dossier streaming."""
    # Ensure at least one lead exists in the database
    all_leads = db.list_all_leads()
    if not all_leads:
        test_lead_id = "test_lead_autogen"
        db.upsert_lead({
            "id": test_lead_id,
            "name": "Lone Star Dental Center",
            "doctor_name": "Amanda Cole",
            "city": "Houston",
            "phone": "+17135550123",
            "stage": "FOUND"
        })
    else:
        test_lead_id = all_leads[0]["id"]

    # 1. Test GET /api/leads/{lead_id}/bant-meddic
    res_bm = client.get(f"/api/leads/{test_lead_id}/bant-meddic")
    assert res_bm.status_code == 200
    bm_json = res_bm.json()
    assert "bant" in bm_json
    assert "meddic" in bm_json
    assert "recommendation" in bm_json

    # 2. Test GET /api/leads/{lead_id}/download-pdf-dossier
    res_pdf = client.get(f"/api/leads/{test_lead_id}/download-pdf-dossier")
    assert res_pdf.status_code == 200
    assert "application/pdf" in res_pdf.headers.get("content-type", "")
    assert len(res_pdf.content) > 2000
    assert res_pdf.content.startswith(b"%PDF-")
