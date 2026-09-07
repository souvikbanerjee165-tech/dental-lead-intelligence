import pytest
from database import DatabaseManager
from queue_manager import QueueManager
from models import RawLead, ScoredLead, WebsiteAuditResult, MultichannelSequence

def test_queue_staging_and_lifecycle(tmp_path):
    db_file = tmp_path / "test_queue.db"
    db = DatabaseManager(db_path=db_file)

    raw = RawLead(name="Lone Star Ortho", website="https://lonestarortho.com", phone="512-555-0808")
    scored = ScoredLead(
        raw_lead=raw,
        audit=WebsiteAuditResult(),
        opportunity_score=88,
        sequence=MultichannelSequence(
            day1_email_subject="Lone Star Ortho - After hours intake",
            day1_email_body="Hi Dr. Smith, noticed you have no online booking."
        )
    )

    db.save_scored_lead(scored, [])

    # Stage for review
    qid = QueueManager.stage_for_review(scored, pdf_path="output/reports/report.pdf", db=db)
    assert qid.startswith("q_")

    # List queue
    items = QueueManager.list_queue(status="PENDING_REVIEW", db=db)
    assert len(items) == 1
    assert items[0]["lead_name"] == "Lone Star Ortho"
    assert items[0]["subject"] == "Lone Star Ortho - After hours intake"

    # Approve
    approved = QueueManager.approve_item(qid, review_notes="Looks great, verified doctor name", db=db)
    assert approved is True

    # Check approved list
    app_items = QueueManager.list_queue(status="APPROVED", db=db)
    assert len(app_items) == 1

    # Dispatch approved
    dispatched = QueueManager.dispatch_approved(db=db)
    assert len(dispatched) == 1

    # Check lead stage moved to SENT
    lead_id = db._make_lead_id(raw.name, raw.website)
    lead = db.get_lead(lead_id)
    assert lead["stage"] == "SENT"

    # Queue status updated to SENT
    sent_items = QueueManager.list_queue(status="SENT", db=db)
    assert len(sent_items) == 1
