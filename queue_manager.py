from typing import List, Dict, Optional, Any, Callable
from datetime import datetime
from database import DatabaseManager
from models import ScoredLead

class QueueManager:
    """Human-in-the-Loop Outreach Review Queue Manager."""

    @classmethod
    def stage_for_review(
        cls,
        scored_lead: ScoredLead,
        pdf_path: Optional[str] = None,
        db: Optional[DatabaseManager] = None
    ) -> str:
        db = db or DatabaseManager()
        lead_id = db._make_lead_id(scored_lead.raw_lead.name, scored_lead.raw_lead.website)

        subject = scored_lead.sequence.day1_email_subject or f"Quick question for {scored_lead.raw_lead.name}"
        body = scored_lead.sequence.day1_email_body or "Hello, following up on your practice digital accessibility."
        final_pdf = pdf_path or scored_lead.pdf_report_path
        tier = scored_lead.deal_priority.tier.value if scored_lead.deal_priority else "TIER 2"

        queue_id = db.enqueue_outreach(
            lead_id=lead_id,
            subject=subject,
            body=body,
            pdf_path=final_pdf,
            opportunity_score=scored_lead.opportunity_score,
            priority_tier=tier
        )
        return queue_id

    @classmethod
    def list_queue(cls, status: Optional[str] = "PENDING_REVIEW", db: Optional[DatabaseManager] = None) -> List[Dict[str, Any]]:
        db = db or DatabaseManager()
        return db.list_outreach_queue(status=status)

    @classmethod
    def approve_item(cls, queue_id: str, review_notes: Optional[str] = None, db: Optional[DatabaseManager] = None) -> bool:
        db = db or DatabaseManager()
        return db.update_queue_status(queue_id=queue_id, status="APPROVED", review_notes=review_notes)

    @classmethod
    def reject_item(cls, queue_id: str, reason: str = "Rejected by sales reviewer", db: Optional[DatabaseManager] = None) -> bool:
        db = db or DatabaseManager()
        return db.update_queue_status(queue_id=queue_id, status="REJECTED", review_notes=reason)

    @classmethod
    def dispatch_approved(
        cls,
        sender_fn: Optional[Callable[[Dict[str, Any]], bool]] = None,
        db: Optional[DatabaseManager] = None
    ) -> List[Dict[str, Any]]:
        db = db or DatabaseManager()
        approved_items = db.list_outreach_queue(status="APPROVED")
        dispatched = []

        for item in approved_items:
            success = True
            if sender_fn:
                try:
                    success = sender_fn(item)
                except Exception:
                    success = False

            if success:
                touch_id = db.record_touch(
                    campaign_id="camp_queue_dispatch",
                    lead_id=item["lead_id"],
                    channel="email",
                    primary_finding_cited=None
                )
                db.update_queue_status(item["id"], status="SENT", review_notes=f"Dispatched via touch {touch_id}")
                db.update_lead_stage(item["lead_id"], new_stage="SENT", notes=f"Approved outreach dispatched ({touch_id})")
                dispatched.append(item)

        return dispatched
