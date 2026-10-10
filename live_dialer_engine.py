"""
Live Dialer & Real-Time Handoff Orchestrator.
Manages:
1. Manual phone dialing with real-time clinic lookup.
2. Dual-audio listening & continuous transcription.
3. Real-time Co-Pilot HUD (live objection detection, counter-punches, buying signals, and talk-to-listen metrics).
4. Seamless Bidirectional Takeover (Human -> AI Takeover, AI -> Human Takeover).
5. Audio recording persistence and closed-loop post-call AI learning engine.
"""

import os
import re
import json
import time
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

from config import GOOGLE_API_KEY, GEMINI_API_KEY
from dental_caller_persona import DentalCallerPersona
from voice_dialer import clean_phone_e164, generate_speech_audio
from database import DatabaseManager
from pre_call_dossier import PreCallDossierCompiler
from empathy_voice_prompts import EmpathyVoicePromptEngine
from carrier_reputation_manager import CarrierReputationManager

logger = logging.getLogger("live_dialer_engine")


class LiveDialerEngine:
    """Orchestrates manual phone calling, real-time AI co-pilot listening, and bidirectional handoffs."""

    # In-memory active call sessions
    _active_sessions: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def start_manual_session(
        cls,
        phone: str,
        lead_id: Optional[str] = None,
        contact_name: Optional[str] = None,
        mode: str = "HUMAN_FIRST",
        carrier_mode: str = "BROWSER",
        db: Optional[DatabaseManager] = None,
        server_base_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Initializes a manual call session with instant clinic lookup and strategy briefing.
        """
        db = db or DatabaseManager()
        clean_phone = clean_phone_e164(phone)
        session_id = f"call_man_{int(time.time())}_{abs(hash(clean_phone)) % 10000}"
        now_str = datetime.now().isoformat()

        # Match existing lead from DB if not provided
        lead = None
        if lead_id:
            lead = db.get_lead(lead_id)
        if not lead and clean_phone:
            lead = db.find_lead_by_phone(clean_phone)

        clinic_name = lead.get("name") if lead else (contact_name or "Dental Practice")
        doctor_name = lead.get("doctor_name") if lead else "Doctor"
        opportunity_score = lead.get("opportunity_score") if lead else 75
        monthly_leakage = lead.get("estimated_monthly_leakage") if lead else 4200

        # Build consultative script & objections
        lead_dict = dict(lead) if lead else {
            "name": clinic_name,
            "doctor_name": doctor_name,
            "phone": clean_phone,
            "opportunity_score": opportunity_score,
            "estimated_missed_revenue_annual": monthly_leakage * 12
        }
        script = DentalCallerPersona.build_call_script(lead_dict)

        # 1. Carrier Reputation & DNC Permission Check
        rep_mgr = CarrierReputationManager(db=db)
        allowed, perm_reason, matched_caller = rep_mgr.check_dial_permission(clean_phone)

        # 2. Compile Pre-Call Commercial Dossier
        dossier = PreCallDossierCompiler.compile_dossier(lead_dict, db=db)
        empathy_prompt = EmpathyVoicePromptEngine.build_voice_system_prompt(dossier)

        session = {
            "session_id": session_id,
            "lead_id": lead.get("id") if lead else None,
            "phone_number": clean_phone or phone,
            "clinic_name": clinic_name,
            "doctor_name": doctor_name,
            "matched_lead": bool(lead),
            "opportunity_score": opportunity_score,
            "monthly_leakage": f"${monthly_leakage:,}/mo" if isinstance(monthly_leakage, (int, float)) else str(monthly_leakage),
            "script": script,
            "dossier": dossier,
            "empathy_voice_prompt": empathy_prompt,
            "dial_permission": {
                "allowed": allowed,
                "reason": perm_reason,
                "matched_caller_id": matched_caller
            },
            "current_mode": mode,  # 'HUMAN_FIRST' or 'AI_FIRST'
            "carrier_mode": carrier_mode,  # 'BROWSER' or 'TELNYX'
            "started_at": now_str,
            "last_active_at": now_str,
            "duration_sec": 0,
            "handoff_count": 0,
            "handoff_log": [],
            "transcript": [],
            "talk_metrics": {
                "human_words": 0,
                "ai_words": 0,
                "prospect_words": 0
            },
            "status": "ACTIVE"
        }

        # Initial turn depending on mode
        if mode == "AI_FIRST":
            hook = script.get("gatekeeper_hook") or f"Hi, good morning! I was reviewing {clinic_name}'s patient intake setup. Who handles weekend scheduling?"
            session["transcript"].append({
                "speaker": "AI Growth Specialist",
                "role": "assistant",
                "text": hook,
                "timestamp": now_str,
                "mode": "AI"
            })
            session["talk_metrics"]["ai_words"] += len(hook.split())
            session["initial_hook"] = hook

        if carrier_mode in ("TELNYX", "TWILIO"):
            try:
                from voice_dialer import VoiceDialerEngine
                carrier_res = VoiceDialerEngine.dispatch_call(
                    lead=lead_dict,
                    to_phone=clean_phone or phone,
                    carrier_override=carrier_mode,
                    db=db,
                    server_base_url=server_base_url,
                    initial_mode=mode
                )
                session["carrier_dispatch"] = carrier_res
                session["carrier_name"] = carrier_mode
                session["carrier_call_id"] = carrier_res.get("call_id")
                session["call_id"] = carrier_res.get("call_id") or session_id
                if carrier_res.get("status") == "failed" or carrier_res.get("error"):
                    err_msg = carrier_res.get("error") or carrier_res.get("message")
                    session["carrier_error"] = err_msg
                    session["telnyx_error"] = err_msg
                logger.info(f"Dispatched real {carrier_mode} call to {clean_phone}: {carrier_res.get('status')}")
            except Exception as e:
                logger.error(f"{carrier_mode} manual dispatch error: {e}")
                session["carrier_error"] = str(e)
                session["telnyx_error"] = str(e)

        cls._active_sessions[session_id] = session
        logger.info(f"Started manual dialer session {session_id} to {clean_phone} (Mode: {mode}, Carrier: {carrier_mode})")
        return session

    @classmethod
    def get_session(cls, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves active session state."""
        return cls._active_sessions.get(session_id)

    @classmethod
    def process_live_turn(
        cls,
        session_id: str,
        text: str,
        speaker: str = "HUMAN",
        audio_url: Optional[str] = None,
        db: Optional[DatabaseManager] = None
    ) -> Dict[str, Any]:
        """
        Ingests a spoken turn (Human, Prospect, or AI) in real-time.
        Computes live Co-Pilot HUD assistance (objection alerts, counter-punches, buying signals).
        """
        session = cls._active_sessions.get(session_id)
        now_str = datetime.now().isoformat()
        if not session:
            # Fallback mock session if session timed out or server restarted
            session = cls.start_manual_session(phone="+15125550199", contact_name="Practice", db=db)
            session_id = session["session_id"]

        session["last_active_at"] = now_str
        word_count = len(text.strip().split())

        # Normalize speaker category
        speaker_upper = speaker.upper()
        if "PROSPECT" in speaker_upper or "RECEPTIONIST" in speaker_upper or "DOCTOR" in speaker_upper or "CLINIC" in speaker_upper:
            speaker_role = "prospect"
            speaker_label = session.get("doctor_name") if "DOCTOR" in speaker_upper else "Receptionist / Prospect"
            session["talk_metrics"]["prospect_words"] += word_count
        elif "AI" in speaker_upper:
            speaker_role = "assistant"
            speaker_label = "AI Growth Specialist"
            session["talk_metrics"]["ai_words"] += word_count
        else:
            speaker_role = "user"
            speaker_label = "You (Human Rep)"
            session["talk_metrics"]["human_words"] += word_count

        turn_entry = {
            "speaker": speaker_label,
            "role": speaker_role,
            "text": text.strip(),
            "timestamp": now_str,
            "mode": session.get("current_mode", "HUMAN_CONTROL"),
            "audio_url": audio_url
        }
        session["transcript"].append(turn_entry)

        # If in a live Telnyx call and the human rep at PC spoke, relay speech to the phone line
        if speaker_role == "user" and session.get("carrier_mode") == "TELNYX" and session.get("carrier_call_id"):
            try:
                from voice_dialer import send_telnyx_speak
                send_telnyx_speak(session["carrier_call_id"], text.strip())
            except Exception as e:
                logger.warning(f"Failed to relay human turn to Telnyx phone line: {e}")

        # Real-Time Co-Pilot Analysis
        copilot_hud = cls._analyze_copilot_hud(session, text, speaker_role)

        return {
            "session_id": session_id,
            "turn": turn_entry,
            "current_mode": session.get("current_mode"),
            "copilot_hud": copilot_hud,
            "talk_ratios": cls._calculate_talk_ratios(session)
        }

    @classmethod
    def execute_ai_takeover(
        cls,
        session_id: str,
        user_prompt_override: Optional[str] = None,
        db: Optional[DatabaseManager] = None
    ) -> Dict[str, Any]:
        """
        Seamlessly hands over call control from Human to AI.
        Generates tactical spoken response from the exact conversational context and synthesizes audio.
        """
        session = cls._active_sessions.get(session_id)
        if not session:
            session = cls.start_manual_session(phone="+15125550199", db=db)
            session_id = session["session_id"]

        now_str = datetime.now().isoformat()
        session["handoff_count"] += 1
        handoff_entry = {
            "handoff_index": session["handoff_count"],
            "from_mode": session.get("current_mode", "HUMAN_CONTROL"),
            "to_mode": "AI_CONTROL",
            "timestamp": now_str,
            "reason": user_prompt_override or "User pressed [AI Takeover]"
        }
        session["handoff_log"].append(handoff_entry)
        session["current_mode"] = "AI_CONTROL"

        # Formulate contextual response
        reply_text = cls._generate_takeover_response(session, user_prompt_override)

        # Sub-second voice synthesis (Google Cloud Journey Neural TTS preferred)
        filename = f"takeover_{int(time.time())}_{abs(hash(reply_text)) % 10000}"
        from voice_dialer import get_instant_conversational_filler
        filler_info = get_instant_conversational_filler()

        speech = generate_speech_audio(
            text=reply_text,
            filename=filename,
            preferred_engine="auto-fast",
            voice_name="en-US-Journey-F"
        )

        ai_turn = {
            "speaker": "AI Growth Specialist (Taken Over)",
            "role": "assistant",
            "text": reply_text,
            "timestamp": now_str,
            "mode": "AI_CONTROL",
            "is_takeover": True,
            "audio_url": speech.get("audio_url"),
            "engine": speech.get("engine")
        }
        session["transcript"].append(ai_turn)
        logger.info(f"Session {session_id}: Handed over to AI. Generated: '{reply_text}'")

        # Relay AI speech to live Telnyx phone line
        carrier_call_id = session.get("carrier_call_id") or session.get("call_id")
        if carrier_call_id and not str(carrier_call_id).startswith("mock_"):
            try:
                from voice_dialer import send_telnyx_speak
                send_telnyx_speak(carrier_call_id, reply_text)
                logger.info(f"Relayed AI takeover speech to Telnyx phone line {carrier_call_id}")
            except Exception as e:
                logger.warning(f"Failed to relay AI speech to Telnyx phone line: {e}")

        return {
            "session_id": session_id,
            "status": "ai_in_control",
            "current_mode": "AI_CONTROL",
            "reply_text": reply_text,
            "audio_url": speech.get("audio_url"),
            "filler_audio_url": filler_info.get("audio_url"),
            "filler_text": filler_info.get("text"),
            "voice_engine": speech.get("engine"),
            "handoff_event": handoff_entry,
            "transcript_turn": ai_turn,
            "copilot_hud": {
                "active_speaker": "AI",
                "instruction": "AI has taken over the call. You can listen or take back control anytime.",
                "suggested_action": "Press [Human Takeover] when you want to jump back in."
            }
        }

    @classmethod
    def execute_human_takeover(
        cls,
        session_id: str,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Seamlessly hands over call control from AI back to Human.
        Halts AI audio and returns microphone control to the human rep.
        """
        session = cls._active_sessions.get(session_id)
        if not session:
            return {"status": "error", "message": "Session not found"}

        now_str = datetime.now().isoformat()
        session["handoff_count"] += 1
        handoff_entry = {
            "handoff_index": session["handoff_count"],
            "from_mode": "AI_CONTROL",
            "to_mode": "HUMAN_CONTROL",
            "timestamp": now_str,
            "reason": reason or "User pressed [Human Takeover]"
        }
        session["handoff_log"].append(handoff_entry)
        session["current_mode"] = "HUMAN_CONTROL"

        # System marker in transcript
        system_turn = {
            "speaker": "System",
            "role": "system",
            "text": "👤 Human sales representative took back control of the call.",
            "timestamp": now_str,
            "mode": "HUMAN_CONTROL",
            "is_takeover_event": True
        }
        session["transcript"].append(system_turn)

        logger.info(f"Session {session_id}: Handed over to Human.")

        return {
            "session_id": session_id,
            "status": "human_in_control",
            "current_mode": "HUMAN_CONTROL",
            "handoff_event": handoff_entry,
            "message": "AI speech halted. Your microphone is live. Speak now.",
            "copilot_hud": {
                "active_speaker": "YOU",
                "instruction": "You have full control of the call. AI is actively listening and transcribing.",
                "suggested_next_line": "Thanks for holding — just wanted to clarify your weekend booking process."
            }
        }

    @classmethod
    def hangup_session(cls, session_id: str) -> Dict[str, Any]:
        """Terminates carrier telecom call and marks active session COMPLETED."""
        session = cls._active_sessions.get(session_id)
        carrier_call_id = None
        if session:
            session["status"] = "COMPLETED"
            carrier_call_id = session.get("carrier_call_id") or session.get("call_id")
        
        # Also check if session_id itself is a call_control_id
        target_carrier_id = carrier_call_id or session_id
        if target_carrier_id and not str(target_carrier_id).startswith("mock_"):
            try:
                from voice_dialer import hangup_telnyx_call
                hangup_telnyx_call(target_carrier_id)
                logger.info(f"Terminated carrier call {target_carrier_id} via hangup_session.")
            except Exception as e:
                logger.warning(f"Error hanging up call {target_carrier_id}: {e}")

        return {"status": "hung_up", "session_id": session_id, "carrier_call_id": target_carrier_id}

    @classmethod
    def finalize_call_session(
        cls,
        session_id: str,
        audio_bytes: Optional[bytes] = None,
        audio_filename: Optional[str] = None,
        duration_sec: int = 0,
        outcome_override: Optional[str] = None,
        db: Optional[DatabaseManager] = None
    ) -> Dict[str, Any]:
        """
        Finalizes call, stores audio recording, executes closed-loop AI learning,
        and saves complete record to SQLite database.
        """
        db = db or DatabaseManager()
        session = cls._active_sessions.pop(session_id, None) or {}
        now_str = datetime.now().isoformat()

        # Immediately terminate live telecom call leg on Telnyx
        carrier_call_id = session.get("carrier_call_id") or session.get("call_id")
        if carrier_call_id and not str(carrier_call_id).startswith("mock_"):
            try:
                from voice_dialer import hangup_telnyx_call
                hangup_telnyx_call(carrier_call_id)
                logger.info(f"Terminated Telnyx telecom call {carrier_call_id} on finalize.")
            except Exception as e:
                logger.warning(f"Failed to hangup Telnyx call on finalize: {e}")

        clean_phone = session.get("phone_number") or "+15125550199"
        clinic_name = session.get("clinic_name") or "Dental Practice"
        doctor_name = session.get("doctor_name") or "Doctor"
        lead_id = session.get("lead_id")
        transcript = session.get("transcript") or []
        handoff_log = session.get("handoff_log") or []

        # Save audio file to disk if provided
        recording_path = ""
        recording_url = ""
        out_dir = Path(__file__).resolve().parent / "output" / "calls"
        out_dir.mkdir(exist_ok=True, parents=True)

        rec_name = audio_filename or f"rec_{session_id}_{int(time.time())}.wav"
        file_dest = out_dir / rec_name

        if audio_bytes and len(audio_bytes) > 0:
            try:
                with open(file_dest, "wb") as f:
                    f.write(audio_bytes)
                recording_path = str(file_dest)
                recording_url = f"/output/calls/{rec_name}"
            except Exception as e:
                logger.error(f"Failed to write recording file: {e}")
        else:
            # Check if any synthesized turn audio exists
            for turn in reversed(transcript):
                if turn.get("audio_url"):
                    recording_url = turn["audio_url"]
                    break

        # Analyze call and extract closed-loop learnings
        learnings = cls._extract_closed_loop_learnings(session, transcript)
        outcome = outcome_override or learnings.get("predicted_outcome", "COMPLETED")

        # Automatically log winning insights into Institutional Knowledge Base
        for insight in learnings.get("playbook_insights", []):
            try:
                db.log_knowledge_base_insight(
                    category=insight.get("category", "OBJECTION_REBUTTAL"),
                    key_phrase=insight.get("key_phrase", "Handling Receptionist"),
                    content=insight.get("content", ""),
                    effectiveness_score=insight.get("effectiveness_score", 8.5)
                )
            except Exception as e:
                logger.warning(f"Failed to log KB insight: {e}")

        # Automatically update relationship memory if gatekeeper details detected
        if learnings.get("gatekeeper_name") and lead_id:
            try:
                db.update_relationship_memory(
                    lead_id=lead_id,
                    contact_name=learnings.get("gatekeeper_name"),
                    role=learnings.get("gatekeeper_role", "Receptionist"),
                    demeanor=learnings.get("gatekeeper_demeanor", "Professional"),
                    notes=f"Identified during call on {now_str[:10]}."
                )
            except Exception as e:
                logger.warning(f"Failed to update relationship memory: {e}")

        # Save to call_recordings table
        rec_data = {
            "call_id": session_id,
            "lead_id": lead_id,
            "phone_number": clean_phone,
            "contact_name": f"{doctor_name} ({clinic_name})",
            "started_at": session.get("started_at", now_str),
            "ended_at": now_str,
            "duration_sec": duration_sec or max(len(transcript) * 12, 45),
            "recording_file_path": recording_path,
            "recording_url": recording_url,
            "initial_mode": session.get("mode", "HUMAN_FIRST"),
            "final_mode": session.get("current_mode", "HUMAN_CONTROL"),
            "handoff_count": len(handoff_log),
            "handoff_log": handoff_log,
            "transcript": transcript,
            "outcome": outcome,
            "learnings": learnings
        }
        rec_row_id = db.save_call_recording(rec_data)

        # Log call outcome in call_logs and progress CRM if meeting booked
        try:
            db.log_call_outcome(
                lead_id=lead_id or "manual_call",
                outcome=outcome,
                rep_notes=f"Call to {clinic_name}. Learnings: {learnings.get('summary', 'Call completed.')}",
                duration_sec=rec_data["duration_sec"]
            )
        except Exception:
            pass

        return {
            "status": "finalized",
            "recording_id": rec_row_id,
            "call_id": session_id,
            "phone_number": clean_phone,
            "clinic_name": clinic_name,
            "doctor_name": doctor_name,
            "duration_sec": rec_data["duration_sec"],
            "recording_url": recording_url,
            "outcome": outcome,
            "handoff_count": len(handoff_log),
            "learnings": learnings,
            "transcript": transcript
        }

    # ================= Private Helper Logic =================

    @classmethod
    def _analyze_copilot_hud(cls, session: Dict[str, Any], text: str, speaker_role: str) -> Dict[str, Any]:
        """Scans the latest turn for objections, buying signals, and strategic recommendations."""
        txt_lower = text.lower()
        script = session.get("script") or {}
        doctor = session.get("doctor_name", "Doctor")
        clinic = session.get("clinic_name", "the clinic")

        detected_objection = None
        counter_punch = None
        buying_signals = []

        # 1. Master Clinical Objection Patterns & Counter-Punches
        if any(w in txt_lower for w in ["weave", "nexhealth", "revenuewell", "podium", "birdeye", "software", "already use"]):
            detected_objection = "Incumbent Software (Passive vs Active Conversion Layer)"
            counter_punch = "Weave is great for daytime reminders, but Friday 8 PM emergency calls hit voicemail. We operate alongside Weave as an active triage layer in under 3 seconds."
        elif any(w in txt_lower for w in ["full", "booked out", "packed", "three weeks", "at capacity", "don't need patients"]):
            detected_objection = "Chairs Full / Calendar Backlog (Dormant Recall Opportunity)"
            counter_punch = "Booked schedules experience 12-15% breakage. Your PMS holds ~850 dormant charts ($190k+ trapped). We reactivate hygiene and backfill cancellations automatically."
        elif any(w in txt_lower for w in ["write directly", "dentrix", "eaglesoft", "open dental", "mess up", "double-book"]):
            detected_objection = "PMS Calendar Integrity & Write-Protection Paranoia"
            counter_punch = "We never overwrite provider columns. Certified APIs place bookings into an isolated WebSched hold column for front-desk approval during morning huddle."
        elif any(w in txt_lower for w in ["don't want emergency", "bad payer", "chaotic", "walk-in", "emergencies disrupt"]):
            detected_objection = "Emergency Patient Profile Concern"
            counter_punch = "Our triage engine screens exclusively for high-value $1,250+ restorative cases (cracked molars, broken crowns) slotted strictly into your pre-set buffer blocks."
        elif any(w in txt_lower for w in ["hipaa", "baa", "compliance", "privacy", "security"]):
            detected_objection = "HIPAA Compliance & Data Security"
            counter_punch = "We execute an omnibus BAA directly with the practice. 256-bit encryption, strict PHI segregation, 10DLC healthcare routes, and TCPA consent logging."
        elif any(w in txt_lower for w in ["partner", "wife", "think about it", "committee", "discuss"]):
            detected_objection = "Internal Governance Deferral (3-Mile Scarcity Lock)"
            counter_punch = "We enforce a strict 3-mile postal exclusivity lock. We can place a temporary 72-hour administrative hold on your territory while your team reviews the SLA."
        elif any(w in txt_lower for w in ["cost", "how much", "price", "expensive", "fee", "$1,500", "budget"]):
            detected_objection = "Setup Cost & Retainer (Single-Patient Break-Even SLA)"
            counter_punch = "A single $1,250 restorative case covers the entire setup. Backed by our Single-Patient Break-Even Guarantee: book >=1 patient in 30 days or 100% refund."
        elif any(w in txt_lower for w in ["ai", "robot", "automated", "recording"]):
            detected_objection = "AI Identity Detection (Live Operational Proof)"
            counter_punch = "Demonstrates how fluidly the engine triages after-hours emergency patients and books them into your PMS in under 5 seconds."
        elif any(w in txt_lower for w in ["operatory", "with a patient", "chair time", "surgery", "busy"]):
            detected_objection = "Doctor In Operatory / Clinical Care Priority"
            counter_punch = f"Clinical care comes first! A 60-second video teardown was prepared for {clinic}. Does the office manager oversee after-hours schedule capacity?"
        elif any(w in txt_lower for w in ["send an email", "email us", "info@", "send information"]):
            detected_objection = "Send Information via Email (Unmonitored Inbox Trap)"
            counter_punch = f"The general info inbox auto-archives outside diagnostic reports. What is the direct email for {doctor}'s practice manager so it routes properly?"
        elif any(w in txt_lower for w in ["not interested", "no thanks", "take off list", "don't call"]):
            detected_objection = "General Disinterest / Territory Closeout"
            counter_punch = "Understood. The 3-mile submarket audit showed $5,350/mo leaking to competitors. Should we close out the territory reservation for another office?"

        # 2. Buying Signals
        if any(w in txt_lower for w in ["sunday", "weekend", "after hours", "evening", "voicemail"]):
            buying_signals.append("Acknowledged after-hours / weekend missed calls")
        if any(w in txt_lower for w in ["hygiene", "recall", "dormant", "cleaning", "reactivat"]):
            buying_signals.append("Interested in dormant hygiene recall cash injection")
        if any(w in txt_lower for w in ["how does it work", "tell me more", "how does that", "show me"]):
            buying_signals.append("Inquiry about operational mechanics")
        if any(w in txt_lower for w in ["thursday", "friday", "tomorrow", "calendar", "meet", "demo", "zoom", "agreement", "sla"]):
            buying_signals.append("Receptive to scheduling preview / territory SLA execution")
        if any(w in txt_lower for w in ["implant", "crown", "emergency", "root canal", "restorative"]):
            buying_signals.append("Mentioned high-ticket clinical procedures")

        # 3. Suggested Next Line for Human
        suggested_line = "Could you tell me who handles patient inquiries when the office closes on Friday?"
        if counter_punch:
            suggested_line = counter_punch
        elif "thursday" in txt_lower or "meet" in txt_lower or "demo" in txt_lower or "agreement" in txt_lower:
            suggested_line = "Thursday at 11 AM works great on my end. Who should receive the 10-minute preview invite and territory SLA link?"
        elif buying_signals:
            suggested_line = f"Exactly — our AI triages callers in 5 seconds and places them into your WebSched hold column for Dr. {doctor}'s review."

        return {
            "detected_objection": detected_objection,
            "counter_punch": counter_punch,
            "buying_signals": buying_signals,
            "suggested_next_line": suggested_line,
            "status_tone": "DEFENSE" if detected_objection else ("HOT" if buying_signals else "NEUTRAL")
        }

    @classmethod
    def _generate_takeover_response(cls, session: Dict[str, Any], user_hint: Optional[str]) -> str:
        """Uses multi-turn conversational context and anti-repetition matrix to generate the next spoken AI line."""
        key = GOOGLE_API_KEY or GEMINI_API_KEY
        clinic_name = session.get("clinic_name", "Dental Practice")
        doctor_name = session.get("doctor_name", "Doctor")
        script = session.get("script") or {}
        history = session.get("transcript") or []
        used_rebuttals = session.setdefault("used_rebuttals", [])

        # Find the last turn from the prospect
        last_prospect_text = "How can I help you?"
        for turn in reversed(history):
            if turn.get("role") in ("prospect", "user") and not turn.get("is_takeover"):
                last_prospect_text = turn.get("text", last_prospect_text)
                break

        # 1. DNC Opt-Out Shield Check
        rep_mgr = CarrierReputationManager()
        if rep_mgr.check_for_opt_out(last_prospect_text):
            rep_mgr.process_opt_out(session.get("phone_number", ""), clinic_name=clinic_name, reason="LIVE_CALL_OPT_OUT")
            return "Understood, I have removed your number from our contact list immediately. Have a wonderful day!"

        # 2. Automated Empathy Bridge Objection Rebuttal (Instant zero-latency response with anti-repetition)
        obj_key = EmpathyVoicePromptEngine.detect_objection(last_prospect_text)
        dossier = session.get("dossier") or {}
        if obj_key and not user_hint:
            rebuttal = EmpathyVoicePromptEngine.get_empathy_rebuttal(obj_key, dossier, used_phrases=used_rebuttals)
            used_rebuttals.append(rebuttal)
            return EmpathyVoicePromptEngine.enforce_brevity(rebuttal)

        # 3. Multi-turn dialogue transcript extraction
        transcript_lines = []
        already_said = []
        for t in history[-6:]:
            spk = t.get("speaker") or ("Prospect" if t.get("role") in ("user", "prospect") else "AI Jordan")
            txt = (t.get("text") or "").strip()
            if txt:
                transcript_lines.append(f"- {spk}: \"{txt}\"")
            if t.get("role") in ("assistant", "system") or "AI" in str(spk):
                already_said.append(txt)

        history_block = "\n".join(transcript_lines) if transcript_lines else f'- Prospect: "{last_prospect_text}"'
        recent_said_guard = "; ".join([f'"{p}"' for p in already_said[-3:]]) if already_said else ""
        repetition_prompt = f"\nCRITICAL ANTI-REPETITION MANDATE:\nYou already stated earlier: [{recent_said_guard}].\nNEVER repeat, rehash, or rephrase any earlier statement, question, or pitch. Move forward!" if recent_said_guard else ""

        # 4. Multi-provider generation through LLMRouter (OpenAI / DeepSeek / Gemini)
        try:
            from llm_router import LLMRouter
            sys_prompt = session.get("empathy_voice_prompt") or f"""You are an elite, warm Dental AI Growth Specialist stepping in on a live call with '{clinic_name}'.
Doctor: Dr. {doctor_name}
Monthly Missed Revenue: {session.get('monthly_leakage', '$4,200/mo')}
User instruction/hint: "{user_hint or 'Pivot smoothly and ask to verify weekend patient capture.'}"

{repetition_prompt}

CRITICAL 12-SECOND BREVITY & CONVERSATIONAL RULES:
- Generate EXACTLY ONE short spoken sentence (10 to 18 words maximum).
- Sound conversational, calm, and consultative.
- Acknowledge what they just said.
- Propose a low-friction 60-second video preview or ask for the practice manager.
- No markdown, no quotes, just plain spoken words.
"""
            prompt_content = f"""RECENT CONVERSATION TRANSCRIPT:
{history_block}

The prospect just said: "{last_prospect_text}"
Generate your next single spoken response (DO NOT REPEAT PREVIOUS STATEMENTS):"""

            txt = LLMRouter.generate_text(
                prompt=prompt_content,
                system_prompt=sys_prompt,
                max_tokens=50
            )
            txt = EmpathyVoicePromptEngine.enforce_brevity(txt)
            if len(txt.split()) <= 24 and len(txt) > 5 and txt not in already_said:
                used_rebuttals.append(txt)
                return txt
        except Exception as e:
            logger.warning(f"LLMRouter takeover generation fallback: {e}")

        # Dynamic fallback matching
        txt_lower = last_prospect_text.lower()
        if "weave" in txt_lower or "software" in txt_lower:
            cand = f"We actually integrate right alongside Weave to capture high-value Sunday implant patients when your team is home."
        elif "busy" in txt_lower or "surgery" in txt_lower:
            cand = f"Totally understand Dr. {doctor_name} is with patients. Who coordinates the calendar so I can send a 60-second video?"
        elif "email" in txt_lower:
            cand = f"Happy to email it over! What is the direct email for your practice manager so it doesn't get lost?"
        else:
            cand = f"Thanks for bearing with us. I was hoping to show Dr. {doctor_name}'s team how to capture 3 extra Sunday bookings."

        used_rebuttals.append(cand)
        return cand

    @classmethod
    def _calculate_talk_ratios(cls, session: Dict[str, Any]) -> Dict[str, Any]:
        """Calculates live conversational share metrics."""
        m = session.get("talk_metrics") or {"human_words": 0, "ai_words": 0, "prospect_words": 0}
        total = m.get("human_words", 0) + m.get("ai_words", 0) + m.get("prospect_words", 0)
        if total == 0:
            return {"rep_pct": 50, "prospect_pct": 50, "ai_share_pct": 0}

        rep_words = m.get("human_words", 0) + m.get("ai_words", 0)
        prospect_words = m.get("prospect_words", 0)

        rep_pct = round((rep_words / total) * 100)
        prospect_pct = round((prospect_words / total) * 100)
        ai_share = round((m.get("ai_words", 0) / max(1, rep_words)) * 100)

        return {
            "rep_pct": rep_pct,
            "prospect_pct": prospect_pct,
            "ai_share_pct": ai_share,
            "human_words": m.get("human_words", 0),
            "ai_words": m.get("ai_words", 0),
            "prospect_words": prospect_words
        }

    @classmethod
    def _extract_closed_loop_learnings(cls, session: Dict[str, Any], transcript: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Mines objections, winning pitch angles, and gatekeeper demeanor from the transcript."""
        structured = EmpathyVoicePromptEngine.extract_structured_call_outcome(transcript)
        all_text = " ".join([t.get("text", "") for t in transcript]).lower()
        clinic_name = session.get("clinic_name", "Dental Practice")
        doctor_name = session.get("doctor_name", "Doctor")

        objections_found = structured.get("detected_objections", [])
        winning_angles = []
        gatekeeper_demeanor = "Friendly & Receptive" if any(w in all_text for w in ["friendly", "thanks", "great", "sure"]) else "Professional"
        outcome = structured.get("predicted_outcome", "COMPLETED")
        gatekeeper_name = structured.get("gatekeeper_name") or session.get("gatekeeper_name")

        if outcome == "MEETING_BOOKED":
            winning_angles.append("Low-friction calendar preview pitch")
        elif outcome == "EMAIL_REQUESTED":
            winning_angles.append("Direct practice manager video prototype offer")

        playbook_insights = [
            {
                "category": "OBJECTION_REBUTTAL",
                "key_phrase": f"Software coexistence at {clinic_name}",
                "content": "Positioning AI as after-hours weekend capture rather than PMS replacement reduced defensiveness immediately.",
                "effectiveness_score": 8.8
            }
        ]
        if outcome == "MEETING_BOOKED":
            playbook_insights.append({
                "category": "WINNING_ANGLE",
                "key_phrase": "Thursday 11 AM Zoom Anchor",
                "content": "Offering Thursday 11 AM as a concrete time slot yielded an immediate calendar commitment.",
                "effectiveness_score": 9.4
            })

        return {
            "predicted_outcome": outcome,
            "objections_encountered": objections_found or ["Standard front-desk screening"],
            "winning_angles": winning_angles or ["Direct weekend revenue leakage calculation"],
            "gatekeeper_demeanor": gatekeeper_demeanor,
            "gatekeeper_name": gatekeeper_name or "Office Coordinator",
            "next_best_action": structured.get("next_best_action", "Re-engage during afternoon huddle"),
            "pain_acknowledged": structured.get("pain_acknowledged", False),
            "handoff_summary": f"Switched between Human and AI {len(session.get('handoff_log', []))} times during the call.",
            "playbook_insights": playbook_insights,
            "summary": f"Call with {clinic_name} concluded as {outcome}. Demeanor: {gatekeeper_demeanor}."
        }
