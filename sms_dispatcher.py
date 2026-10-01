"""
1-Click SMS & WhatsApp Dispatcher Engine with Live Pitch Link Tracking.
Generates personalized SMS/WhatsApp dispatch payloads, provides instant 1-tap OS deep-links (sms: and wa.me),
and tracks real-time prospect link engagement and portal views in the Opportunity Timeline.
"""

import os
import logging
import urllib.parse
from typing import Dict, Any, Optional
from datetime import datetime

from database import DatabaseManager
from timeline import OpportunityTimelineManager

logger = logging.getLogger("sms_dispatcher")


class SMSDispatcherEngine:
    """Manages high-converting SMS and WhatsApp outreach dispatches for dental leads."""

    @classmethod
    def generate_dispatch_payload(
        cls,
        lead_dict: Dict[str, Any],
        base_app_url: str = "http://127.0.0.1:8000"
    ) -> Dict[str, Any]:
        lead_id = lead_dict.get("id") or "preview"
        clinic_name = lead_dict.get("name") or "Your Practice"
        raw_doc = lead_dict.get("doctor_name") or "Doctor"
        clean_doc = raw_doc.replace("Dr.", "").replace("Dr", "").strip()
        doc_display = f"Dr. {clean_doc}" if clean_doc else "the Practice Owner"
        
        raw_phone = lead_dict.get("phone") or ""
        clean_digits = "".join(c for c in raw_phone if c.isdigit())
        e164_phone = f"+1{clean_digits}" if (len(clean_digits) == 10 and not clean_digits.startswith("1")) else f"+{clean_digits}" if clean_digits else ""

        pitch_url = f"{base_app_url}/pitch/{lead_id}"
        demo_url = f"{base_app_url}/demo/{lead_id}"

        # 1-Sentence High-Impact Text Message
        sms_text = (
            f"Hi {doc_display}, test this 10-second WhatsApp patient intake prototype built for {clinic_name}: "
            f"{pitch_url} - Recovers $4,200/mo in weekend toothache emergencies that currently hit your office voicemail."
        )

        encoded_body = urllib.parse.quote(sms_text)
        
        # Native OS SMS deep-link (works on iOS, Android, macOS, and Windows Phone Link)
        native_sms_url = f"sms:{e164_phone}?body={encoded_body}" if e164_phone else f"sms:?body={encoded_body}"
        
        # WhatsApp Web / App deep-link
        whatsapp_url = f"https://wa.me/{clean_digits}?text={encoded_body}" if clean_digits else f"https://wa.me/?text={encoded_body}"

        return {
            "lead_id": lead_id,
            "clinic_name": clinic_name,
            "doctor_name": doc_display,
            "target_phone": e164_phone,
            "pitch_url": pitch_url,
            "demo_url": demo_url,
            "sms_text": sms_text,
            "native_sms_url": native_sms_url,
            "whatsapp_url": whatsapp_url
        }

    @classmethod
    def record_dispatch(
        cls,
        lead_id: str,
        channel: str = "SMS",
        db: Optional[DatabaseManager] = None
    ) -> bool:
        """Logs dispatch to touches table and opportunity timeline."""
        db = db or DatabaseManager()
        now_str = datetime.now().isoformat()
        try:
            db.record_touch(
                campaign_id="CAMPAIGN_PRECISION_DISPATCH",
                lead_id=lead_id,
                channel=channel,
                primary_finding_cited="After-Hours Voicemail Friction Teardown Link"
            )
            OpportunityTimelineManager.log_event(
                db=db,
                lead_id=lead_id,
                event_type="DISPATCH_SENT",
                title=f"Dispatched {channel} Teardown Pitch",
                description=f"Delivered 1-click confidential teardown pitch and interactive simulator to clinic mobile.",
                actor="SALES_REP",
                timestamp=now_str
            )
            return True
        except Exception as e:
            logger.warning(f"Failed to record dispatch event: {e}")
            return False

    @classmethod
    def record_pitch_view(
        cls,
        lead_id: str,
        db: Optional[DatabaseManager] = None
    ) -> Dict[str, Any]:
        """Triggered when doctor or practice manager visits the /pitch/{lead_id} portal."""
        db = db or DatabaseManager()
        now_str = datetime.now().isoformat()
        lead = db.get_lead(lead_id) or {"name": "Practice"}
        clinic_name = lead.get("name") or "Dental Practice"
        doctor_name = lead.get("doctor_name") or "Doctor"

        try:
            # Boost win probability and mark hot activity
            with db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                UPDATE leads
                SET win_probability_pct = MIN(95, COALESCE(win_probability_pct, 75) + 10),
                    last_updated = ?
                WHERE id = ?
                """, (now_str, lead_id))
                conn.commit()

            OpportunityTimelineManager.log_event(
                db=db,
                lead_id=lead_id,
                event_type="PITCH_VIEWED",
                title="🔥 HOT SIGNAL: Pitch Teardown Portal Viewed!",
                description=f"{doctor_name} or practice staff actively opened and reviewed the revenue teardown portal.",
                actor="PROSPECT",
                metadata={"urgency": "HOT_ENGAGED", "clinic": clinic_name},
                timestamp=now_str
            )
            return {"status": "success", "alert": f"Prospect {clinic_name} engaged with pitch page!", "lead_id": lead_id}
        except Exception as e:
            logger.warning(f"Failed to record pitch view: {e}")
            return {"status": "ignored"}
