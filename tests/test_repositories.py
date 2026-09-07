import pytest
import tempfile
from pathlib import Path
from models import RawLead
from evidence import Finding, DOMEvidence
from insights import BusinessInsight
from repositories import (
    SQLiteLeadRepository, SQLiteFindingRepository,
    SQLiteInsightRepository, SQLiteAuditRepository
)

@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_storage.db"
    return db_file

def test_sqlite_lead_repository(temp_db):
    repo = SQLiteLeadRepository(db_path=temp_db)
    
    # Initialize table
    with repo._get_conn() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT,
            rating REAL,
            review_count INTEGER,
            phone TEXT,
            address TEXT,
            website TEXT,
            maps_url TEXT,
            first_seen TEXT,
            last_updated TEXT
        );
        """)

    raw_lead = RawLead(
        name="Oak Ridge Dental",
        category="Dentist",
        rating=4.8,
        review_count=75,
        phone="512-555-0144",
        website="https://oakridgedental.com"
    )

    lead_id = repo.save_lead(raw_lead, "lead_oakridge")
    assert lead_id == "lead_oakridge"

    fetched = repo.get_lead("lead_oakridge")
    assert fetched is not None
    assert fetched["name"] == "Oak Ridge Dental"
    assert fetched["rating"] == 4.8

def test_sqlite_finding_and_insight_repository(temp_db):
    f_repo = SQLiteFindingRepository(db_path=temp_db)
    i_repo = SQLiteInsightRepository(db_path=temp_db)

    # Initialize findings table
    with f_repo._get_conn() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS findings (
            id TEXT PRIMARY KEY,
            audit_id TEXT NOT NULL,
            lead_id TEXT NOT NULL,
            category TEXT,
            title TEXT,
            description TEXT,
            confidence REAL,
            severity TEXT,
            recommendation TEXT,
            projected_roi REAL,
            evidence_json TEXT
        );
        """)

    finding = Finding(
        id="FIND-TEST",
        category="Testing",
        title="Test Finding",
        description="Verification finding",
        evidence=[DOMEvidence(element_snippet="<test>", confidence=0.95)],
        confidence=0.95,
        severity="medium",
        recommendation="Test recommendation",
        projected_monthly_roi=100.0
    )

    f_repo.save_findings(audit_id="aud_123", lead_id="lead_123", findings=[finding])
    findings = f_repo.get_findings("aud_123")
    assert len(findings) == 1
    assert findings[0]["title"] == "Test Finding"

    insight = BusinessInsight(
        id="INS_TEST",
        insight_type="operational",
        title="Test Executive Insight",
        executive_summary="Summary",
        impact_analysis="High impact",
        projected_annual_loss=12000.0,
        strategic_recommendation="Deploy solution"
    )

    i_repo.save_insights(audit_id="aud_123", lead_id="lead_123", insights=[insight])
    insights = i_repo.get_insights("aud_123")
    assert len(insights) == 1
    assert insights[0]["title"] == "Test Executive Insight"
    assert insights[0]["projected_annual_loss"] == 12000.0
