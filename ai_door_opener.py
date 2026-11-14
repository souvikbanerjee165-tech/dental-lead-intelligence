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

        # 4. 15-Second High-Status Voicemail Sting (Drop & SMS)
        voicemail_sting = (
            f"Hi {doc_display}, this is Alex with patient routing. "
            f"I noticed weekend emergency patient calls for {clinic_name} are hitting voicemail. "
            f"I'm texting a 30-second audit link to this office line right now so you can review the after-hours leakage. "
            f"Have a great day."
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
            "sms_text": sms_text,
            "voicemail_sting": voicemail_sting
        }

    @classmethod
    async def dispatch_telnyx_sms(
        cls,
        to_phone: str,
        text: str,
        lead_id: Optional[str] = None,
        db: Optional[DatabaseManager] = None,
        bypass_compliance: bool = False,
        is_internal_alert: bool = False
    ) -> Dict[str, Any]:
        """
        Sends an official SMS through Telnyx REST API, enforcing DNC compliance and
        area-code matching via CarrierReputationManager for prospect outreach.
        """
        cfg = cls.get_telnyx_config()
        api_key = cfg["api_key"]
        from_phone = cfg["from_phone"]

        if not api_key:
            return {"success": False, "error": "TELNYX_API_KEY is not configured."}

        # Normalize to E.164
        digits = re.sub(r"\D", "", to_phone or "")
        if len(digits) == 10:
            digits = "1" + digits
        formatted_to = f"+{digits}" if digits else ""

        if not bypass_compliance:
            from carrier_reputation_manager import CarrierReputationManager
            rep_mgr = CarrierReputationManager(db=db)
            allowed, reason, matched_caller = rep_mgr.verify_outbound_action(
                destination_phone=formatted_to,
                caller_phone=from_phone,
                channel="SMS",
                bypass_velocity=True
            )
            if not allowed:
                logger.warning(f"Telnyx SMS blocked by CarrierReputationManager for {formatted_to}: {reason}")
                return {
                    "success": False,
                    "blocked": True,
                    "error": reason,
                    "reason": reason,
                    "to": formatted_to
                }
            if matched_caller and matched_caller != "+12145550199":
                from_phone = matched_caller

        if not from_phone:
            return {"success": False, "error": "TELNYX_FROM_PHONE is not configured."}

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

                    # Log to database timeline (skip prospect status mutation for internal rep alerts)
                    if lead_id and not is_internal_alert:
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

        if result.get("status") == "blocked" or result.get("blocked"):
            return {
                "status": "blocked",
                "blocked": True,
                "error": result.get("reason") or result.get("error"),
                "lead_id": lead_id,
                "target_phone": target_phone,
                "call_result": result,
                "assets": assets
            }
        
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
            "status": "success" if result.get("status") in ("dispatched", "simulated", "success", "initiated") else "error",
            "lead_id": lead_id,
            "target_phone": target_phone,
            "call_result": result,
            "assets": assets
        }

    @classmethod
    async def handle_answering_machine_detected(
        cls,
        call_control_id: str,
        client_state: Dict[str, Any],
        base_app_url: str = os.getenv("BASE_APP_URL", "https://dental.34.71.56.145.sslip.io"),
        db: Optional[DatabaseManager] = None
    ) -> Dict[str, Any]:
        """
        Executes immediate Voicemail Drop + SMS Teardown protocol when Telnyx AMD detects machine/beep:
        1. Speaks the 15-second Voicemail Sting.
        2. Immediately texts the teardown link to the practice phone.
        3. Marks session as VOICEMAIL_DROP for rapid hangup after speech to save carrier minutes.
        4. Logs to timeline & database.
        """
        from voice_dialer import VoiceDialerEngine
        from live_dialer_engine import LiveDialerEngine

        lead_id = client_state.get("lead_id")
        target_phone = client_state.get("phone") or ""
        assets = cls.generate_sdr_campaign_assets(client_state, base_app_url=base_app_url)
        voicemail_text = assets["voicemail_sting"]
        sms_text = assets["sms_text"]

        logger.info(f"AMD Machine Detected for call {call_control_id}. Dropping Voicemail Sting: '{voicemail_text[:60]}...'")

        # 1. Speak Voicemail Sting
        VoiceDialerEngine.send_telnyx_speak(call_control_id, voicemail_text)

        # 2. Dispatch SMS Teardown link to practice phone
        sms_result = {}
        if target_phone:
            sms_result = await cls.dispatch_telnyx_sms(
                to_phone=target_phone,
                text=sms_text,
                lead_id=lead_id,
                db=db
            )

        # Mark active session as VOICEMAIL_DROP
        for s in list(LiveDialerEngine._active_sessions.values()):
            if s.get("carrier_call_id") == call_control_id or s.get("call_id") == call_control_id:
                s["status"] = "VOICEMAIL_DROP"
                s["current_mode"] = "VOICEMAIL_DROP"
                break

        # 3. Log event to OpportunityTimelineManager & DB
        if lead_id:
            db = db or DatabaseManager()
            try:
                OpportunityTimelineManager.log_event(
                    db=db,
                    lead_id=lead_id,
                    event_type="VOICEMAIL_STING_DROPPED",
                    title="Voicemail Sting & Teardown SMS Dropped",
                    description=f"AMD detected answering machine on {target_phone}. Spoke 15s voicemail sting and dispatched SMS audit link.",
                    actor="AI_SDR"
                )
            except Exception as e:
                logger.warning(f"Failed to log voicemail drop timeline: {e}")

            try:
                with db._get_connection() as conn:
                    conn.execute("UPDATE leads SET contact_status = 'VOICEMAIL_DROPPED', last_updated = CURRENT_TIMESTAMP WHERE id = ?", (lead_id,))
                    conn.commit()
            except Exception:
                pass

        return {
            "status": "voicemail_dropped",
            "call_control_id": call_control_id,
            "lead_id": lead_id,
            "sms_result": sms_result
        }

    @classmethod
    async def handle_human_answered(
        cls,
        call_control_id: str,
        client_state: Dict[str, Any],
        base_app_url: str = os.getenv("BASE_APP_URL", "https://dental.34.71.56.145.sslip.io"),
        db: Optional[DatabaseManager] = None
    ) -> Dict[str, Any]:
        """
        Executes live conversational door-opener when Telnyx AMD detects a live human:
        1. Speaks the 30-second door-opener hook immediately to eliminate dead air.
        2. Starts Telnyx live speech transcription.
        3. Logs to timeline & DB.
        """
        from voice_dialer import VoiceDialerEngine
        from live_dialer_engine import LiveDialerEngine

        lead_id = client_state.get("lead_id")
        target_phone = client_state.get("phone") or ""
        assets = cls.generate_sdr_campaign_assets(client_state, base_app_url=base_app_url)
        hook_text = assets["door_opener_script"]

        logger.info(f"AMD Human Answered for call {call_control_id}. Speaking live door opener: '{hook_text[:60]}...'")

        # 1. Start live transcription
        VoiceDialerEngine.start_telnyx_transcription(call_control_id)

        # 2. Speak live door-opener hook
        VoiceDialerEngine.send_telnyx_speak(call_control_id, hook_text)

        # Mark active session as CONNECTED
        for s in list(LiveDialerEngine._active_sessions.values()):
            if s.get("carrier_call_id") == call_control_id or s.get("call_id") == call_control_id:
                s["status"] = "CONNECTED"
                s["answered_hook_spoken"] = True
                break

        if lead_id:
            db = db or DatabaseManager()
            try:
                OpportunityTimelineManager.log_event(
                    db=db,
                    lead_id=lead_id,
                    event_type="HUMAN_ANSWERED_DOOR_OPENER",
                    title="Live Human Answered AI Door-Opener",
                    description=f"Human answered at {target_phone}. Spoke 30s conversational intake opener.",
                    actor="AI_SDR"
                )
            except Exception as e:
                logger.warning(f"Failed to log human answer timeline: {e}")

        return {
            "status": "human_connected",
            "call_control_id": call_control_id,
            "lead_id": lead_id
        }
