"""
Autonomous AI Voice Door-Opener & 30-Second SDR Engine.
Engineered specifically for US & Canadian dental practices:
1. 30-second high-status conversational door-opener (Door-Opener, NOT Closer).
2. Gatekeeper bypass focused on after-hours voicemail leakage.
3. 1-click Telnyx SMS dispatch of personalized teardown link (/pitch/{lead_id}).
4. Immediate handoff to Hand-Raiser Radar for human close ($1,200 earned setup + $497/mo).
"""

import os
import re
import json
import logging
from typing import Dict, Any, Optional
import httpx

from dotenv import load_dotenv
from database import DatabaseManager
from timeline import OpportunityTimelineManager

load_dotenv()
logger = logging.getLogger("ai_door_opener")


class AIDoorOpenerEngine:
    """Manages autonomous AI outbound SDR calls and instantaneous SMS teardown drops."""

    TELNYX_API_URL = "https://api.telnyx.com/v2/messages"

    @classmethod
    def get_telnyx_config(cls) -> Dict[str, str]:
        return {
            "api_key": os.getenv("TELNYX_API_KEY", "").strip(),
            "from_phone": os.getenv("TELNYX_FROM_PHONE", "+13343780005").strip(),
            "connection_id": os.getenv("TELNYX_CONNECTION_ID", "").strip()
        }

    @classmethod
    def generate_sdr_campaign_assets(
        cls,
        lead_dict: Dict[str, Any],
        base_app_url: str = os.getenv("BASE_APP_URL", "https://dental.34.71.56.145.sslip.io")
    ) -> Dict[str, Any]:
        """
        Builds the 30-second conversational opening, gatekeeper rebuttal, and SMS payload.
        """
        lead_id = lead_dict.get("id") or "preview"
        clinic_name = lead_dict.get("name") or "Dental Practice"
        raw_doc = lead_dict.get("doctor_name") or "Doctor"
        clean_doc = raw_doc.replace("Dr.", "").replace("Dr", "").strip()
        doc_display = f"Dr. {clean_doc}" if clean_doc else "the Practice Owner"
        
        raw_phone = lead_dict.get("phone") or ""
        digits = re.sub(r"\D", "", raw_phone)
        e164_phone = f"+1{digits}" if (len(digits) == 10 and not digits.startswith("1")) else f"+{digits}" if digits else ""

        address = lead_dict.get("address") or "Austin, TX"
        city = address.split(",")[-2].strip() if ("," in address and len(address.split(",")) >= 2) else "your city"

        rev_min = lead_dict.get("missed_rev_min") or 3500
        rev_max = lead_dict.get("missed_rev_max") or 9600
        monthly_leaked = int((rev_min + rev_max) / 2) if (rev_min and rev_max) else 9600

        pitch_url = f"{base_app_url}/pitch/{lead_id}"

        # 1. The 30-Second Conversational Script (High-status, not salesy)
        door_opener_script = (
            f"Hi, this is Alex with the dental patient routing team. "
            f"I was reviewing {clinic_name}'s after-hours line in {city}, and noticed emergency weekend calls are hitting standard voicemail. "
            f"We built a 30-second interactive test prototype showing how neighboring clinics capture those toothache cases automatically. "
            f"What is the best mobile number to text {doc_display}'s confidential preview link to?"
        )

        # 2. Gatekeeper Rebuttal ("What is this regarding?")
        gatekeeper_rebuttal = (
            f"We audit after-hours revenue loss for local independent dental practices. "
            f"Our models show {clinic_name} leaks an estimated ${monthly_leaked:,} a month to neighboring emergency clinics because weekend callers hang up on voicemail. "
            f"I just want to text {doc_display} the 30-second audit link so they have it on their phone."
        )

        # 3. High-Converting SMS Payload
        sms_text = (
            f"Hi {doc_display}, here is the confidential after-hours patient intake audit & 10s interactive prototype "
            f"we prepared for {clinic_name} (${monthly_leaked:,}/mo estimated leakage): {pitch_url}"
        )

        return {
            "lead_id": lead_id,
            "clinic_name": clinic_name,
            "doctor_display": doc_display,
            "target_phone": e164_phone,
            "city": city,
            "monthly_leaked_usd": monthly_leaked,
            "door_opener_script": door_opener_script,
            "gatekeeper_rebuttal": gatekeeper_rebuttal,
            "pitch_url": pitch_url,
            "sms_text": sms_text
        }

    @classmethod
    async def dispatch_telnyx_sms(
        cls,
        to_phone: str,
        text: str,
        lead_id: Optional[str] = None,
        db: Optional[DatabaseManager] = None
    ) -> Dict[str, Any]:
        """
        Sends an official SMS through Telnyx REST API.
        """
        cfg = cls.get_telnyx_config()
        api_key = cfg["api_key"]
        from_phone = cfg["from_phone"]

        if not api_key:
            return {"success": False, "error": "TELNYX_API_KEY is not configured."}

        # Normalize to E.164
        digits = re.sub(r"\D", "", to_phone)
        if len(digits) == 10:
            digits = "1" + digits
        formatted_to = f"+{digits}"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "from": from_phone,
            "to": formatted_to,
            "text": text
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(cls.TELNYX_API_URL, headers=headers, json=payload)
                if resp.status_code in (200, 201, 202):
                    data = resp.json().get("data", {})
                    msg_id = data.get("id")

                    # Log to database timeline
                    if lead_id:
                        db = db or DatabaseManager()
                        OpportunityTimelineManager.log_event(
                            db=db,
                            lead_id=lead_id,
                            event_type="SMS_DISPATCHED",
                            title="Telnyx SMS Teardown Dispatched",
                            description=f"Sent confidential teardown link to {formatted_to} via Telnyx (Msg ID: {msg_id})",
                            actor="AI_SDR"
                        )
                        # Mark contact status as CONTACTED
                        try:
                            with db._get_connection() as conn:
                                conn.execute("UPDATE leads SET contact_status = 'CONTACTED', last_updated = CURRENT_TIMESTAMP WHERE id = ?", (lead_id,))
                                conn.commit()
                        except Exception:
                            pass

                    return {
                        "success": True,
                        "message_id": msg_id,
                        "to": formatted_to,
                        "from": from_phone,
                        "status": "DELIVERED"
                    }
                else:
                    return {
                        "success": False,
                        "status_code": resp.status_code,
                        "error": resp.text
                    }
        except Exception as e:
            logger.error(f"Telnyx SMS dispatch error: {e}")
            return {"success": False, "error": str(e)}

    @classmethod
    def launch_telnyx_door_opener_call(
        cls,
        lead_dict: Dict[str, Any],
        to_phone: Optional[str] = None,
        base_app_url: str = os.getenv("BASE_APP_URL", "https://dental.34.71.56.145.sslip.io"),
        db: Optional[DatabaseManager] = None
    ) -> Dict[str, Any]:
        """
        Dispatches an autonomous AI outbound SDR call using Telnyx and the 30-second door-opener script.
        """
        from voice_dialer import VoiceDialerEngine
        assets = cls.generate_sdr_campaign_assets(lead_dict, base_app_url=base_app_url)
        lead_id = lead_dict.get("id")
        target_phone = to_phone or assets.get("target_phone")
        
        result = VoiceDialerEngine.dispatch_call(
            lead=lead_dict,
            to_phone=target_phone,
            carrier_override="TELNYX",
            db=db,
            server_base_url=base_app_url,
            initial_mode="AI_FIRST"
        )
        
        if lead_id and db:
            try:
                OpportunityTimelineManager.log_event(
                    db=db,
                    lead_id=lead_id,
                    event_type="AI_CALL_DISPATCHED",
                    title="AI SDR Door-Opener Call Launched",
                    description=f"Outbound AI SDR call initiated to {target_phone} via Telnyx. Opener: '{assets['door_opener_script'][:80]}...'",
                    actor="AI_SDR"
                )
            except Exception as e:
                logger.warning(f"Failed to log call to timeline: {e}")

            try:
                with db._get_connection() as conn:
                    conn.execute("UPDATE leads SET contact_status = 'CALLED', last_updated = CURRENT_TIMESTAMP WHERE id = ?", (lead_id,))
                    conn.commit()
            except Exception:
                pass
                
        return {
            "status": "success" if result.get("status") in ("dispatched", "simulated", "success") else "error",
            "lead_id": lead_id,
            "target_phone": target_phone,
            "call_result": result,
            "assets": assets
        }
