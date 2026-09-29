"""
Automated Follow-Up Reminder & Snooze Engine (Agency Machine Pillar 3).
Automatically schedules and manages multi-touch follow-ups based on call outcomes:
- "No Answer" -> Automatically triggers 2-day reminder
- "Requested Written Info" -> Triggers 24-hour follow-up touch
- "Spoke to Gatekeeper" -> Schedules morning callback with receptionist name
"""

import time
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from database import DatabaseManager

logger = logging.getLogger("reminder_manager")


class ReminderManager:
    """Manages automated follow-up scheduling, snooze intervals, and completion tracking."""

    @classmethod
    def auto_schedule_from_call_outcome(
        cls,
        db: DatabaseManager,
        lead_id: str,
        outcome: str,
        notes: str = ""
    ) -> Optional[int]:
        """
        Automatically schedules a follow-up reminder rule based on call outcome.
        """
        lead = db.get_lead(lead_id)
        if not lead:
            return None

        clinic_name = lead.get("name", "Dental Practice")
        now = datetime.now()
        outcome_upper = outcome.upper()

        if "NO_ANSWER" in outcome_upper or "VOICEMAIL" in outcome_upper:
            # Rule: Follow up after 2 days
            due = (now + timedelta(days=2)).strftime("%Y-%m-%d 09:30:00")
            reason = "NO_ANSWER_2_DAYS"
            rem_notes = f"Auto-reminder: Second touch attempt. {notes}".strip()
        elif "INFO_REQUESTED" in outcome_upper or "SEND_INFO" in outcome_upper or "EMAIL" in outcome_upper:
            # Rule: Follow up in 24 hours
            due = (now + timedelta(days=1)).strftime("%Y-%m-%d 10:00:00")
            reason = "INFO_REQUESTED_24H"
            rem_notes = f"Auto-reminder: Follow up on sent proposal / WhatsApp demo video. {notes}".strip()
        elif "GATEKEEPER" in outcome_upper or "RECEPTIONIST" in outcome_upper:
            # Rule: Callback during prime doctor consultation time
            best_time = lead.get("best_call_time") or "Morning"
            due = (now + timedelta(days=1)).strftime("%Y-%m-%d 08:30:00")
            reason = "GATEKEEPER_CALLBACK"
            rem_notes = f"Auto-reminder: Ask for Dr. {lead.get('doctor_name') or 'Doctor'} during {best_time}. {notes}".strip()
        elif "DEMO_SCHEDULED" in outcome_upper or "MEETING" in outcome_upper:
            # Rule: Meeting prep 2 hours before
            due = (now + timedelta(days=1)).strftime("%Y-%m-%d 09:00:00")
            reason = "MEETING_CONFIRMATION"
            rem_notes = f"Prep: Diagnostic review scheduled with {clinic_name}. {notes}".strip()
        else:
            # Default 3-day follow-up
            due = (now + timedelta(days=3)).strftime("%Y-%m-%d 10:00:00")
            reason = "GENERAL_FOLLOW_UP"
            rem_notes = notes or "General follow-up checkpoint"

        reminder_id = db.create_followup_reminder(
            lead_id=lead_id,
            clinic_name=clinic_name,
            due_date=due,
            trigger_reason=reason,
            notes=rem_notes
        )

        # Log to timeline
        with db._get_connection() as conn:
            conn.execute("""
            INSERT INTO opportunity_timeline (lead_id, timestamp, event_type, title, description, actor)
            VALUES (?, ?, 'REMINDER_SCHEDULED', ?, ?, 'REMINDER_ENGINE');
            """, (lead_id, now.isoformat(), f"Follow-up Scheduled ({reason})", f"Due on {due}: {rem_notes}"))
            conn.commit()

        logger.info(f"Scheduled follow-up reminder #{reminder_id} for {clinic_name} due {due}")
        return reminder_id

    @classmethod
    def get_due_reminders(cls, db: DatabaseManager, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves list of active pending reminders with overdue status."""
        reminders = db.get_due_reminders(limit=limit)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for r in reminders:
            r["is_overdue"] = r.get("due_date", "") < now_str
            r["display_label"] = f"[{r.get('trigger_reason')}] {r.get('clinic_name')} (Due: {r.get('due_date')})"

        return reminders

    @classmethod
    def complete_reminder(cls, db: DatabaseManager, reminder_id: int) -> bool:
        """Marks a reminder as completed and logs completion."""
        return db.complete_reminder(reminder_id)

    @classmethod
    def snooze_reminder(cls, db: DatabaseManager, reminder_id: int, days: int = 2) -> bool:
        """Snoozes a reminder by specified days."""
        new_due = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d 09:30:00")
        return db.snooze_reminder(reminder_id, new_due)
