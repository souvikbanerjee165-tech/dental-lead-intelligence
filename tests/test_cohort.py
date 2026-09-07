import pytest
from models import RawLead, WebsiteAuditResult, ScoredLead, TechStackDetail
from cohort import MarketCohortAnalyzer, CohortBenchmark

def test_market_cohort_analyzer():
    lead1 = ScoredLead(
        raw_lead=RawLead(name="Cedar Park Smiles", review_count=100, rating=4.8),
        audit=WebsiteAuditResult(
            reachable=True,
            has_online_booking=True,
            detected_booking_tool="NexHealth",
            has_ai_chatbot=True,
            detected_chatbot_name="Drift",
            tech_stack=TechStackDetail(ad_pixels=["Meta Pixel"], crm_and_marketing=["HubSpot"])
        )
    )
    lead2 = ScoredLead(
        raw_lead=RawLead(name="Brushy Creek Dental", review_count=50, rating=4.6),
        audit=WebsiteAuditResult(
            reachable=True,
            has_online_booking=True,
            detected_booking_tool="NexHealth",
            has_ai_chatbot=False,
            tech_stack=TechStackDetail()
        )
    )
    lead3 = ScoredLead(
        raw_lead=RawLead(name="Old Town Dental", review_count=30, rating=4.4),
        audit=WebsiteAuditResult(
            reachable=True,
            has_online_booking=False,
            has_ai_chatbot=False,
            tech_stack=TechStackDetail()
        )
    )

    cohort = MarketCohortAnalyzer.analyze_cohort([lead1, lead2, lead3], geo_query="Round Rock, TX")

    assert cohort.total_competitors == 3
    # 2 out of 3 have booking -> 66.7%
    assert round(cohort.booking_adoption_pct) == 67
    # 1 out of 3 has chat -> 33.3%
    assert round(cohort.chat_adoption_pct) == 33
    assert "NexHealth" in cohort.popular_booking_tools
    assert "Drift" in cohort.popular_chatbots

    hooks = MarketCohortAnalyzer.generate_competitive_hook(lead3, cohort)
    assert "booking_peer_comparison" in hooks
    assert "66%" in hooks["booking_peer_comparison"] or "67%" in hooks["booking_peer_comparison"]
    assert "Old Town Dental" in hooks["booking_peer_comparison"]
