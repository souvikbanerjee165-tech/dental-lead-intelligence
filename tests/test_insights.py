import pytest
from evidence import Finding
from insights import InsightEngine, BusinessInsight

def test_manual_intake_bottleneck_insight():
    """Missing both online booking and AI chat should synthesize operational bottleneck insight."""
    findings = [
        Finding(
            id="FIND-CHAT-ABSENCE",
            category="Automation & AI Intake",
            title="Absence of 24/7 AI Chatbot",
            description="No chat detected",
            confidence=0.96,
            severity="critical",
            projected_monthly_roi=2000.0
        ),
        Finding(
            id="FIND-BOOKING-ABSENCE",
            category="Patient Experience",
            title="Absence of Online Booking",
            description="No self-scheduling detected",
            confidence=0.95,
            severity="critical",
            projected_monthly_roi=2500.0
        )
    ]

    insights = InsightEngine.synthesize_insights(findings=findings, review_count=30, rating=4.5, has_pixels=False)
    insight_ids = [i.id for i in insights]

    assert "INSIGHT-MANUAL-INTAKE-BOTTLENECK" in insight_ids
    bottleneck = next(i for i in insights if i.id == "INSIGHT-MANUAL-INTAKE-BOTTLENECK")
    assert bottleneck.urgency == "immediate"
    assert bottleneck.projected_annual_loss == (2000.0 + 2500.0) * 12
    assert "24/7 AI Receptionist" in bottleneck.strategic_recommendation

def test_blind_ad_spend_insight():
    """Ad pixels active while lacking CRM and chat should trigger paid acquisition leakage insight."""
    findings = [
        Finding(
            id="FIND-CRM-ABSENCE",
            category="Automation & AI Intake",
            title="Missing CRM Pipeline",
            description="No automated lead follow-up",
            confidence=0.95,
            severity="high",
            projected_monthly_roi=1500.0
        )
    ]

    insights = InsightEngine.synthesize_insights(findings=findings, review_count=40, rating=4.6, has_pixels=True)
    insight_ids = [i.id for i in insights]

    assert "INSIGHT-BLIND-AD-SPEND" in insight_ids
    blind_ad = next(i for i in insights if i.id == "INSIGHT-BLIND-AD-SPEND")
    assert blind_ad.insight_type == "marketing_leakage"
    assert blind_ad.urgency == "immediate"

def test_reputation_asymmetry_insight():
    """High review volume (100+) and stellar rating (4.7+) with intake gaps triggers reputation asymmetry."""
    findings = [
        Finding(
            id="FIND-BOOKING-ABSENCE",
            category="Patient Experience",
            title="Absence of Online Booking",
            description="No self-scheduling",
            confidence=0.95,
            severity="critical",
            projected_monthly_roi=3000.0
        )
    ]

    insights = InsightEngine.synthesize_insights(findings=findings, review_count=180, rating=4.9, has_pixels=False)
    insight_ids = [i.id for i in insights]

    assert "INSIGHT-REPUTATION-ASYMMETRY" in insight_ids
    asymmetry = next(i for i in insights if i.id == "INSIGHT-REPUTATION-ASYMMETRY")
    assert "Premier Clinical Reputation" in asymmetry.title
    assert asymmetry.urgency == "near_term"

def test_optimized_foundation_fallback():
    """Fully equipped practice triggers optimized foundation insight."""
    findings = [
        Finding(
            id="FIND-CHAT-ACTIVE",
            category="Automation & AI Intake",
            title="Active Chatbot Widget",
            description="Live chat active",
            confidence=0.98,
            severity="optimal",
            projected_monthly_roi=0.0
        )
    ]

    insights = InsightEngine.synthesize_insights(findings=findings, review_count=30, rating=4.5, has_pixels=False)
    assert len(insights) >= 1
    assert insights[0].id == "INSIGHT-OPTIMIZED-FOUNDATION"
