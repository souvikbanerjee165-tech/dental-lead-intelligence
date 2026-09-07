import pytest
from models import RawLead, WebsiteAuditResult, DigitalMaturityScore, TechStackDetail
from prioritizer import DealPrioritizationEngine, DealPriorityTier

def test_tier_1_call_today_assignment():
    """High volume dental practice with large revenue leakage should be ranked Tier 1 (Call Today)."""
    raw_lead = RawLead(
        name="Metropolis Dental Care",
        category="Dentist",
        review_count=150,
        rating=4.9,
        phone="512-555-0199",
        address="Austin, TX",
        website="https://metropolisdental.com"
    )
    audit = WebsiteAuditResult(
        reachable=True,
        has_ai_chatbot=False,
        has_online_booking=False,
        tech_stack=TechStackDetail(
            ad_pixels=["Meta Pixel", "Google Ads"],
            analytics=["Google Analytics 4"]
        )
    )
    maturity = DigitalMaturityScore(
        overall_score=40,
        automation_score=15
    )

    # $6,500/month leakage
    res = DealPrioritizationEngine.evaluate_deal(
        raw_lead=raw_lead,
        audit=audit,
        maturity=maturity,
        estimated_monthly_loss=6500
    )

    assert res.tier == DealPriorityTier.TIER_1_CALL_TODAY
    assert res.priority_score >= 75
    assert res.icp_fit_score >= 80
    assert res.buying_signals_score >= 80  # Has pixels + analytics + high rating
    assert "Top-tier prospect" in res.ranking_rationale

def test_tier_4_skip_assignment():
    """Practice with negligible revenue loss and low ICP fit should be marked Tier 4 (Skip)."""
    raw_lead = RawLead(
        name="Generic Bookstore",
        category="Retail",
        review_count=3,
        rating=3.2,
        website="https://genericbookstore.com"
    )
    audit = WebsiteAuditResult(
        reachable=True,
        has_ai_chatbot=True,
        has_online_booking=True,
        tech_stack=TechStackDetail()
    )
    maturity = DigitalMaturityScore(
        overall_score=85,
        automation_score=85
    )

    res = DealPrioritizationEngine.evaluate_deal(
        raw_lead=raw_lead,
        audit=audit,
        maturity=maturity,
        estimated_monthly_loss=200
    )

    assert res.tier == DealPriorityTier.TIER_4_SKIP
    assert res.priority_score < 40
    assert "Low fit" in res.ranking_rationale
