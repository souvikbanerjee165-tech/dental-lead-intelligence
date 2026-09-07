import pytest
from pathlib import Path
from models import RawLead, ScoredLead, Finding, WebsiteAuditResult
from proposals import ProposalGenerator

def test_proposal_generation(tmp_path):
    raw_lead = RawLead(
        name="Austin Family Dental",
        website="https://austinfamilydental.com",
        phone="(512) 555-0199",
        rating=4.8,
        review_count=120
    )
    finding = Finding(
        id="FIND-BOOKING-ABSENCE",
        category="conversion",
        title="Missing Online Booking",
        description="No online scheduling widget or booking link detected on clinic website",
        confidence=0.95
    )
    scored = ScoredLead(
        raw_lead=raw_lead,
        audit=WebsiteAuditResult(),
        opportunity_score=85,
        estimated_missed_revenue_monthly_min=4000,
        estimated_missed_revenue_monthly_max=8000,
        estimated_missed_revenue_annual=72000,
        findings=[finding]
    )

    proposal_path = ProposalGenerator.generate_proposal(
        scored_lead=scored,
        agency_name="Premier Medical Growth Partners"
    )

    assert proposal_path.exists()
    assert proposal_path.suffix == ".html"

    content = proposal_path.read_text(encoding="utf-8")
    assert "Austin Family Dental" in content
    assert "Premier Medical Growth Partners" in content
    assert "24/7 AI Patient Intake" in content
    assert "Frictionless Self-Scheduling" in content
    assert "Practice Growth Engine" in content
    assert "$1,500" in content
    assert "$2,500" in content
    assert "$4,500" in content
