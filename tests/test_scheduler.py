import pytest
from database import DatabaseManager
from scheduler import AutonomousScheduler
from models import RawLead, WebsiteAuditResult, ScoredLead, MultichannelSequence

@pytest.mark.anyio
async def test_scheduler_morning_cycle(tmp_path, monkeypatch):
    db_file = tmp_path / "test_scheduler.db"
    db = DatabaseManager(db_path=db_file)

    # Mock lead finder
    async def mock_search(self, query, limit):
        city = query.split(" in ")[-1]
        return [
            RawLead(name=f"Clinic A in {city}", website=f"https://clinica-{city.lower().replace(' ', '')}.com", review_count=50, rating=4.8),
            RawLead(name=f"Clinic B in {city}", website=f"https://clinicb-{city.lower().replace(' ', '')}.com", review_count=90, rating=4.9)
        ]

    # Mock auditor
    async def mock_audit(self, raw_lead, check_incremental=True, force=False):
        return ScoredLead(
            raw_lead=raw_lead,
            audit=WebsiteAuditResult(),
            opportunity_score=80,
            estimated_missed_revenue_annual=50000,
            sequence=MultichannelSequence(
                day1_email_subject=f"Inquiry for {raw_lead.name}",
                day1_email_body="Hello"
            ),
            content_hash="hash_abc"
        )

    from lead_finder import GoogleMapsLeadFinder
    from auditor import WebsiteAuditor

    monkeypatch.setattr(GoogleMapsLeadFinder, "search", mock_search)
    monkeypatch.setattr(WebsiteAuditor, "audit_lead", mock_audit)

    summary = await AutonomousScheduler.run_morning_cycle(
        cities=["Austin, TX", "Dallas, TX"],
        limit_per_city=2,
        db=db
    )

    assert summary["total_discovered"] == 4
    assert summary["new_audited"] == 4
    assert summary["queued_for_review"] == 4
    assert len(summary["city_breakdown"]) == 2
