"""
Competitor Drift & Continuous Re-Scanning Monitor (Roadmap #4 & #7).
- Automatically re-audits clinic websites to detect CMS changes and technology drift.
- Detects when clinics drop or add competitors (Podium, Birdeye, NexHealth, LocalMed, Weave).
- Logs high-urgency timing alerts to trigger_events and updates lead Urgency & Opportunity scores.
"""

import os
import hashlib
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta

from database import DatabaseManager
from auditor import WebsiteAuditor
from models import RawLead

logger = logging.getLogger("drift_monitor")

COMPETITORS_LIST = {
    "podium": "Podium Webchat",
    "birdeye": "Birdeye Messaging",
    "nexhealth": "NexHealth Booking",
    "localmed": "LocalMed Scheduling",
    "weave": "Weave Communications",
    "swell": "Swell CX",
    "carecru": "CareCru Donna",
    "modento": "Modento Dental",
    "intercom": "Intercom Live Chat",
    "drift": "Drift Chat"
}


class CompetitorDriftMonitor:
    """Monitors competitor changes, widget drift, and re-scans dental practices."""

    @classmethod
    async def rescan_lead(
        cls,
        db: DatabaseManager,
        lead_id: str,
        force: bool = False
    ) -> Dict[str, Any]:
        """Re-audits a single clinic, diffs technology stacks, and emits high-urgency triggers."""
        lead = db.get_lead(lead_id)
        if not lead:
            return {"error": f"Lead {lead_id} not found", "triggers_detected": []}

        website = lead.get("website")
        if not website:
            return {"error": "Lead has no website to audit", "triggers_detected": []}

        clinic_name = lead.get("name", "Dental Clinic")
        now_str = datetime.now().isoformat()

        # 1. Fetch Previous Tech Stack & Hash
        prev_techs = set()
        try:
            stored_techs = db.get_lead_technologies(lead_id) if hasattr(db, "get_lead_technologies") else []
            for t in stored_techs:
                if isinstance(t, dict):
                    prev_techs.add(t.get("name", "").lower())
                elif isinstance(t, str):
                    prev_techs.add(t.lower())
        except Exception:
            pass

        prev_hash = lead.get("html_hash") or lead.get("content_hash") or ""
        prev_leakage = lead.get("missed_rev_max") or 4500

        # 2. Execute New Deep Audit
        auditor = WebsiteAuditor()
        raw_stub = RawLead(
            name=clinic_name,
            website=website,
            phone=lead.get("phone", ""),
            address=lead.get("address", "")
        )

        try:
            scored = await auditor.audit_lead(raw_stub, check_incremental=False, force=True)
        except Exception as e:
            logger.error(f"Audit failed during rescan for {lead_id}: {e}")
            return {"error": str(e), "triggers_detected": []}

        new_techs = set(t.lower() for t in scored.technologies) if hasattr(scored, "technologies") else set()
        new_hash = getattr(scored, "content_hash", "") or ""
        new_leakage = getattr(scored, "estimated_missed_revenue_monthly_max", 4500)

        # 3. Detect Competitor Drift & Trigger Events
        triggers = []

        # Check for dropped competitors
        for comp_key, comp_label in COMPETITORS_LIST.items():
            if any(comp_key in pt for pt in prev_techs) and not any(comp_key in nt for nt in new_techs):
                triggers.append({
                    "event_type": "COMPETITOR_DROPPED",
                    "title": f"Competitor Dropped: {comp_label}",
                    "description": f"{clinic_name} recently removed {comp_label} from their website. Prime window to pitch WhatsApp after-hours automation.",
                    "severity": "HIGH",
                    "old_val": comp_label,
                    "new_val": "REMOVED"
                })

        # Check for newly added competitors
        for comp_key, comp_label in COMPETITORS_LIST.items():
            if any(comp_key in nt for nt in new_techs) and not any(comp_key in pt for pt in prev_techs):
                triggers.append({
                    "event_type": "COMPETITOR_ADDED",
                    "title": f"Competitor Installed: {comp_label}",
                    "description": f"{clinic_name} installed {comp_label}. Focus conversation on higher conversion and zero staff friction.",
                    "severity": "LOW",
                    "old_val": "NONE",
                    "new_val": comp_label
                })

        # Check if 24/7 capture void opened up
        if prev_leakage < 4000 and new_leakage >= 4500:
            triggers.append({
                "event_type": "CAPTURE_GAP_OPENED",
                "title": "Revenue Leakage Escalated",
                "description": f"Monthly revenue leakage increased from ${prev_leakage:,} to ${new_leakage:,} due to missing intake channels.",
                "severity": "CRITICAL",
                "old_val": f"${prev_leakage}/mo",
                "new_val": f"${new_leakage}/mo"
            })

        # Check for significant HTML / CMS redesign
        if prev_hash and new_hash and prev_hash != new_hash:
            triggers.append({
                "event_type": "WEBSITE_REDESIGNED",
                "title": "Website Code Updated",
                "description": f"{clinic_name} refreshed website structure or layout. Owner is actively investing in digital patient acquisition.",
                "severity": "MEDIUM",
                "old_val": prev_hash[:8],
                "new_val": new_hash[:8]
            })

        # Check for Online Booking changes (Phase 2)
        raw_booking = getattr(getattr(scored, "audit", None), "has_online_booking", False)
        new_has_booking = bool(raw_booking) if isinstance(raw_booking, bool) else False
        prev_has_booking = any("booking" in pt or "nexhealth" in pt or "localmed" in pt for pt in prev_techs)
        if not prev_has_booking and new_has_booking:
            triggers.append({
                "event_type": "BOOKING_ADDED",
                "title": "Online Booking Installed",
                "description": f"{clinic_name} installed online scheduling. Adapt pitch to focus on 24/7 WhatsApp emergency triage.",
                "severity": "MEDIUM",
                "old_val": "No Booking",
                "new_val": "Online Booking Active"
            })
        elif prev_has_booking and not new_has_booking:
            triggers.append({
                "event_type": "BOOKING_REMOVED",
                "title": "Online Booking Removed",
                "description": f"{clinic_name} removed online booking! Prime urgency window to pitch automated WhatsApp scheduling.",
                "severity": "CRITICAL",
                "old_val": "Online Booking Active",
                "new_val": "No Booking"
            })

        # Check for Phone Number Changes (Phase 2)
        raw_phone = getattr(getattr(scored, "raw_lead", None), "phone", "")
        new_phone = raw_phone if isinstance(raw_phone, str) else ""
        prev_phone = lead.get("phone") or ""
        if new_phone and prev_phone and new_phone != prev_phone:
            triggers.append({
                "event_type": "PHONE_CHANGED",
                "title": "Clinic Phone Number Updated",
                "description": f"Office phone number changed from {prev_phone} to {new_phone}.",
                "severity": "LOW",
                "old_val": str(prev_phone),
                "new_val": str(new_phone)
            })

        # Check for New Direct Email Discovered (Phase 2)
        new_emails = []
        if hasattr(scored, "audit") and hasattr(scored.audit, "emails"):
            raw_emails = scored.audit.emails
            if isinstance(raw_emails, list):
                new_emails = [e for e in raw_emails if isinstance(e, str)]
        prev_emails_str = lead.get("direct_emails") or ""
        for em in new_emails:
            if em and em.lower() not in prev_emails_str.lower():
                triggers.append({
                    "event_type": "NEW_EMAIL_FOUND",
                    "title": "New Practice Email Discovered",
                    "description": f"Discovered verified practice email: {em}",
                    "severity": "MEDIUM",
                    "old_val": "None",
                    "new_val": str(em)
                })
                break

        # 4. Persist Detected Triggers
        with db._get_connection() as conn:
            cursor = conn.cursor()
            for trig in triggers:
                old_v = str(trig.get("old_val") or "")
                new_v = str(trig.get("new_val") or "")
                cursor.execute("""
                INSERT INTO trigger_events (lead_id, event_type, title, description, severity, detected_at, old_val, new_val)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (lead_id, str(trig["event_type"]), str(trig["title"]), str(trig["description"]), str(trig["severity"]), now_str, old_v, new_v))

                # Log to opportunity timeline
                cursor.execute("""
                INSERT INTO opportunity_timeline (lead_id, timestamp, event_type, title, description, actor)
                VALUES (?, ?, 'DRIFT_DETECTED', ?, ?, 'DRIFT_MONITOR')
                """, (lead_id, now_str, trig["title"], trig["description"]))

            # Recalculate Urgency Score
            new_urgency = 75
            if any(t["severity"] == "CRITICAL" for t in triggers):
                new_urgency = 95
            elif any(t["severity"] == "HIGH" for t in triggers):
                new_urgency = 88
            elif triggers:
                new_urgency = 82

            why_now = [t["title"] for t in triggers]
            cursor.execute("""
            UPDATE leads
            SET urgency_score = ?,
                urgency_driver = ?,
                why_now_reasons = ?,
                last_audit_date = ?,
                html_hash = ?,
                opportunity_score = ?
            WHERE id = ?
            """, (new_urgency, why_now[0] if why_now else "Routine Audit", json.dumps(why_now), now_str, new_hash, scored.opportunity_score, lead_id))
            conn.commit()

        return {
            "status": "success",
            "lead_id": lead_id,
            "clinic_name": clinic_name,
            "triggers_detected": triggers,
            "new_urgency_score": new_urgency,
            "new_opportunity_score": scored.opportunity_score,
            "rescan_timestamp": now_str
        }

    @classmethod
    async def rescan_stale_leads(
        cls,
        db: DatabaseManager,
        days_stale: int = 30,
        limit: int = 5
    ) -> Dict[str, Any]:
        """Discovers and re-scans leads whose last audit exceeds threshold."""
        threshold_date = (datetime.now() - timedelta(days=days_stale)).isoformat()
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT id, name, website, last_audit_date 
            FROM leads 
            WHERE (last_audit_date IS NULL OR last_audit_date <= ?)
              AND stage NOT IN ('WON', 'LOST')
              AND website IS NOT NULL AND website != ''
            LIMIT ?
            """, (threshold_date, limit))
            candidates = [dict(r) for r in cursor.fetchall()]

        results = []
        for c in candidates:
            res = await cls.rescan_lead(db, lead_id=c["id"])
            results.append({
                "lead_id": c["id"],
                "name": c["name"],
                "triggers_count": len(res.get("triggers_detected", []))
            })

        return {
            "stale_candidates_processed": len(candidates),
            "results": results
        }

    @classmethod
    def get_active_triggers(cls, db: DatabaseManager, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieves recent high-value competitor triggers with lead context."""
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT t.*, l.name as clinic_name, l.phone, l.doctor_name, l.win_probability_pct
            FROM trigger_events t
            JOIN leads l ON t.lead_id = l.id
            ORDER BY t.detected_at DESC
            LIMIT ?
            """, (limit,))
            return [dict(r) for r in cursor.fetchall()]

    @classmethod
    def monitor_maps_growth(
        cls,
        db: DatabaseManager,
        lead_id: str,
        current_review_count: int,
        current_rating: float
    ) -> Dict[str, Any]:
        """Tracks monthly Google Maps review count acceleration and updates lead metrics (Phase 3)."""
        return db.update_lead_maps_metrics(lead_id, current_review_count, current_rating)

DriftMonitor = CompetitorDriftMonitor
