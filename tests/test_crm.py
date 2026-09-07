import pytest
from database import DatabaseManager
from crm import CRMStage, CRMStageManager
from models import RawLead, ScoredLead, WebsiteAuditResult

def test_crm_stage_validation():
    assert CRMStageManager.validate_stage("found") == CRMStage.FOUND
    assert CRMStageManager.validate_stage("AUDITED") == CRMStage.AUDITED
    assert CRMStageManager.validate_stage("Won") == CRMStage.WON
    with pytest.raises(ValueError):
        CRMStageManager.validate_stage("INVALID_STAGE")

def test_crm_database_lifecycle(tmp_path):
    db_file = tmp_path / "test_crm.db"
    db = DatabaseManager(db_path=db_file)

    raw = RawLead(name="Prestige Dental", website="https://prestigedental.com", phone="512-555-0100")
    scored = ScoredLead(
        raw_lead=raw,
        audit=WebsiteAuditResult(),
        opportunity_score=85,
        estimated_missed_revenue_annual=60000
    )

    lead_id, changes = db.save_scored_lead(scored, [])
    lead = db.get_lead(lead_id)
    assert lead is not None
    assert lead["stage"] == "AUDITED"
    assert lead["opportunity_score"] == 85

    # Move stage
    ok = db.update_lead_stage(lead_id, "EMAIL_PREPARED", "Drafted personalized SDR message")
    assert ok is True
    lead_after = db.get_lead(lead_id)
    assert lead_after["stage"] == "EMAIL_PREPARED"

    # Check stage history
    history = db.get_stage_history(lead_id)
    assert len(history) >= 2
    assert history[0]["to_stage"] == "EMAIL_PREPARED"

    # Add Note
    note_id = db.add_lead_note(lead_id, "Doctor prefers morning meetings", author="Alice SDR")
    assert note_id > 0
    notes = db.get_lead_notes(lead_id)
    assert len(notes) == 1
    assert notes[0]["author"] == "Alice SDR"

    # Pipeline summary
    summary = db.get_crm_pipeline_summary()
    assert "EMAIL_PREPARED" in summary
    assert summary["EMAIL_PREPARED"]["count"] == 1
