"""
Automated 5-Touch Omnichannel Sales Cadence Engine.
Orchestrates multi-channel prospecting sequences across Phone, WhatsApp/SMS, and Email
to ensure every dental prospect is systematically nurtured until demo booked or disqualified.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger("sales_cadence")

CADENCE_STEPS = [
    {
        "step": 1,
        "day_offset": 0,
        "channel": "PHONE",
        "title": "Touch 1: Outbound Call & Gatekeeper Triage",
        "objective": "Identify office manager, pitch after-hours patient leakage, and request cell for prototype link.",
        "action_type": "LIVE_CALL",
        "badge_color": "rose"
    },
    {
        "step": 2,
        "day_offset": 0,
        "channel": "WHATSAPP_SMS",
        "title": "Touch 2: Instant WhatsApp Prototype Link",
        "objective": "Deliver 10-second interactive clinic-branded WhatsApp demo link directly to practice mobile.",
        "action_type": "SEND_SMS_WHATSAPP",
        "badge_color": "emerald"
    },
    {
        "step": 3,
        "day_offset": 2,
        "channel": "EMAIL",
        "title": "Touch 3: Empirical Mystery Shopper Audit",
        "objective": "Email customized audit breakdown showing exact revenue loss and voicemail bounce proof.",
        "action_type": "SEND_EMAIL",
        "badge_color": "cyan"
    },
    {
        "step": 4,
        "day_offset": 4,
        "channel": "PHONE",
        "title": "Touch 4: Re-engagement Call / Thursday Anchor",
        "objective": "Follow up with practice manager on audit findings and lock in Thursday 11 AM Zoom preview.",
        "action_type": "LIVE_CALL",
        "badge_color": "purple"
    },
    {
        "step": 5,
        "day_offset": 6,
        "channel": "PROPOSAL",
        "title": "Touch 5: 1-Click Interactive Proposal & ROI Guarantee",
        "objective": "Send $1,500 setup + $399/mo client proposal highlighting 1-patient break-even guarantee.",
        "action_type": "SEND_PROPOSAL",
        "badge_color": "amber"
    }
]


class SalesCadenceEngine:
    """Manages multi-touch sales sequences and cadence progression for dental leads."""

    @classmethod
    def get_lead_cadence(cls, lead_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Calculates current cadence status, history, and next recommended action."""
        current_step = lead_dict.get("cadence_step") or 1
        current_step = max(1, min(current_step, 5))
        
        step_meta = next((s for s in CADENCE_STEPS if s["step"] == current_step), CADENCE_STEPS[0])
        started_at = lead_dict.get("cadence_started_at") or datetime.now().isoformat()

        # Dynamic copy generation tailored for this step
        doc = lead_dict.get("doctor_name") or "Doctor"
        clinic = lead_dict.get("name") or "Dental Practice"
        phone = lead_dict.get("phone") or ""

        cadence_timeline = []
        for s in CADENCE_STEPS:
            is_completed = s["step"] < current_step
            is_active = s["step"] == current_step
            is_pending = s["step"] > current_step

            cadence_timeline.append({
                **s,
                "status": "COMPLETED" if is_completed else ("ACTIVE" if is_active else "PENDING"),
                "is_current": is_active
            })

        return {
            "lead_id": lead_dict.get("id"),
            "clinic_name": clinic,
            "current_step": current_step,
            "total_steps": 5,
            "current_channel": step_meta["channel"],
            "current_title": step_meta["title"],
            "current_objective": step_meta["objective"],
            "action_type": step_meta["action_type"],
            "cadence_timeline": cadence_timeline,
            "next_action_due": (datetime.now() + timedelta(days=step_meta["day_offset"])).strftime("%b %d, %Y")
        }

    @classmethod
    def advance_cadence(cls, current_step: int, outcome: str) -> Dict[str, Any]:
        """Computes next step based on touch outcome."""
        outcome_upper = outcome.upper()
        if outcome_upper in ("MEETING_BOOKED", "CLOSED_WON"):
            return {"next_step": 5, "status": "CONVERTED", "action": "MEETING_CONFIRMED"}
        elif outcome_upper in ("DO_NOT_CALL", "NOT_INTERESTED_FINAL"):
            return {"next_step": current_step, "status": "DISQUALIFIED", "action": "STOPPED"}
        
        # Standard step advancement
        next_s = min(5, current_step + 1)
        return {
            "next_step": next_s,
            "status": "IN_PROGRESS",
            "action": f"ADVANCED_TO_STEP_{next_s}"
        }
