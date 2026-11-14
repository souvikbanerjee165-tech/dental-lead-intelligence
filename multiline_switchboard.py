"""
4-Channel Multi-Line Concurrency Switchboard & Clinical Triage Engine.
Implements Sections 1, 3, 4, and 5 of Blueprint V1.0.0:
1. 4-Channel Multi-Line Concurrency Switchboard (line-1 to line-4)
2. State Machine: ringing, active_ai, warm_transfer_pending, completed, on_hold
3. Speaker Attribution: customer, ai_agent (Emily AI Receptionist), human_receptionist with ISO timestamps
4. 6-Category Clinical Intent & Urgency Triage Classifier
5. Zero-Repetition Warm Transfer Protocol with Structured Context Briefing Cards
6. Telnyx TeXML Call Control generation (<Say>, <Dial>, <Gather>)
"""

import os
import re
import time
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field

from turn_controller import TurnController

logger = logging.getLogger("multiline_switchboard")

# 6-Category Intent Definitions per Specification
TRIAGE_CATEGORIES = {
    "EMERGENCY_URGENT": {
        "priority": "CRITICAL URGENT",
        "keywords": [
            "severe pain", "throbbing", "swollen jaw", "trauma", "cannot chew",
            "broken tooth", "excruciating", "bleeding heavily", "abscess", "knocked out",
            "emergency", "urgent", "unbearable", "swelling"
        ],
        "action_directive": "Reserve emergency buffer slot; advise cold compress; no aspirin on tissue."
    },
    "NEW_CUSTOMER_INTAKE": {
        "priority": "HIGH PRODUCTION",
        "keywords": [
            "new patient", "just moved", "establish care", "first exam", "first visit",
            "looking for a new dentist", "cleaning and checkup", "switch dentist", "accepting new patients"
        ],
        "action_directive": "Capture insurance ID; book 60-min comprehensive initial onboarding slot."
    },
    "EXISTING_CUSTOMER_RESCHEDULE": {
        "priority": "ROUTINE / MEDIUM",
        "keywords": [
            "reschedule", "work conflict", "push back", "move appointment", "different date",
            "change my time", "cancel and reschedule", "cant make it", "running late"
        ],
        "action_directive": "Offer next open recall slot matching preferences without cancellation fee."
    },
    "BILLING_PAYMENT_INQUIRY": {
        "priority": "MEDIUM",
        "keywords": [
            "copay", "coinsurance", "deductible", "out of pocket", "insurance breakdown",
            "statement", "bill", "claim", "how much will it cost", "carecredit", "financing"
        ],
        "action_directive": "Verify payer eligibility via EDI 271; calculate exact out-of-pocket balance."
    },
    "POST_SERVICE_FOLLOWUP": {
        "priority": "CRITICAL / MEDIUM",
        "keywords": [
            "yesterday", "gauze bleeding", "tooth pulled", "stitches", "post op",
            "extraction pain", "surgery yesterday", "implant sore", "dry socket", "swelling after"
        ],
        "action_directive": "Check post-op protocol. If bleeding persists > 4 hrs, trigger doctor callback."
    },
    "HOURS_LOCATION_INFO": {
        "priority": "ROUTINE",
        "keywords": [
            "hours", "address", "parking directions", "open on weekends", "saturday hours",
            "where are you located", "directions", "suite number", "closing time"
        ],
        "action_directive": "Provide clinic address, operating hours, and link to self-scheduling portal."
    }
}

PATIENT_SPOKEN_REPLIES = {
    "EMERGENCY_URGENT": (
        "I am so sorry you are in discomfort. Let me connect you right away with our emergency coordinator "
        "so we can get you seen as soon as possible."
    ),
    "NEW_CUSTOMER_INTAKE": (
        "We would love to welcome you as a new patient. Let me connect you with our scheduling coordinator "
        "to reserve a convenient onboarding visit for you."
    ),
    "EXISTING_CUSTOMER_RESCHEDULE": (
        "Of course, we can help move your appointment to a time that works better for your schedule. "
        "Would you prefer morning or afternoon availability later this week?"
    ),
    "BILLING_PAYMENT_INQUIRY": (
        "I would be happy to help clarify your dental benefits and estimated out-of-pocket costs. "
        "May I take your insurance provider name so our coordinator can verify coverage?"
    ),
    "POST_SERVICE_FOLLOWUP": (
        "Thank you for calling back after your procedure. Are you experiencing active bleeding or swelling right now "
        "so I can flag our on-call clinical team immediately?"
    ),
    "HOURS_LOCATION_INFO": (
        "Our practice sees patients Monday through Friday with extended urgent coverage, and we can also text you "
        "directions and a direct self-scheduling link."
    ),
}


def get_current_iso_time() -> str:
    """Returns exact ISO-8601 UTC timestamp."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class TranscriptTurn(BaseModel):
    speaker: str = "customer"  # customer, ai_agent, human_receptionist
    text: str
    timestampIso: str = Field(default_factory=get_current_iso_time)
    audioUrl: Optional[str] = None


class ContextBriefingCard(BaseModel):
    callerSummary: str
    identifiedNeed: str
    suggestedResolution: str
    transferredTo: str
    timestampIso: str = Field(default_factory=get_current_iso_time)


class ChannelState(BaseModel):
    id: str  # line-1, line-2, line-3, line-4
    status: str = "completed"  # ringing, active_ai, warm_transfer_pending, completed, on_hold
    caller_phone: str = ""
    caller_name: str = ""
    member_id: Optional[str] = None
    started_at_ms: Optional[int] = None
    duration_seconds: int = 0
    triage_category: Optional[str] = None
    triage_priority: Optional[str] = None
    action_directive: Optional[str] = None
    context_briefing_card: Optional[Dict[str, Any]] = None
    transcript: List[Dict[str, Any]] = Field(default_factory=list)
    call_control_id: Optional[str] = None
    target_operator: str = "Front Desk Coordinator (Sarah)"
    operator_phone: str = os.getenv("FRONT_DESK_TRANSFER_PHONE", "+15559876543")


class MultiLineSwitchboard:
    """
    4-Channel Concurrency Switchboard maintaining isolated timers, VAD state,
    and reactive transitions for 4 parallel caller lines without memory bleed.
    """

    def __init__(self):
        self.channels: Dict[str, ChannelState] = {
            f"line-{i}": ChannelState(id=f"line-{i}") for i in range(1, 5)
        }
        self.turn_controllers: Dict[str, TurnController] = {
            f"line-{i}": TurnController() for i in range(1, 5)
        }
        self._call_id_to_line: Dict[str, str] = {}

    # -------------------------------------------------------------
    # Line & Concurrency Management
    # -------------------------------------------------------------
    def get_all_lines(self) -> List[Dict[str, Any]]:
        """Returns snapshot of all 4 concurrent channels with active call timers."""
        now_ms = int(time.time() * 1000)
        result = []
        for line_id, channel in self.channels.items():
            ch_dict = channel.dict()
            if channel.status in ("ringing", "active_ai", "warm_transfer_pending", "on_hold") and channel.started_at_ms:
                ch_dict["duration_seconds"] = max(0, int((now_ms - channel.started_at_ms) / 1000))
            result.append(ch_dict)
        return result

    def get_line(self, line_id: str) -> Optional[Dict[str, Any]]:
        """Returns details of a specific line."""
        channel = self.channels.get(line_id)
        if not channel:
            return None
        ch_dict = channel.dict()
        if channel.status in ("ringing", "active_ai", "warm_transfer_pending", "on_hold") and channel.started_at_ms:
            now_ms = int(time.time() * 1000)
            ch_dict["duration_seconds"] = max(0, int((now_ms - channel.started_at_ms) / 1000))
        return ch_dict

    def find_available_line(self) -> Optional[str]:
        """Finds the first idle/completed channel line (line-1 to line-4)."""
        for line_id, channel in self.channels.items():
            if channel.status == "completed":
                return line_id
        return None

    # -------------------------------------------------------------
    # 6-Category Intent & Urgency Triage Classifier
    # -------------------------------------------------------------
    @classmethod
    def classify_call_intent(cls, text: str) -> Dict[str, Any]:
        """
        Classifies incoming conversational speech into one of 6 clinical categories:
        1. EMERGENCY_URGENT (CRITICAL URGENT)
        2. NEW_CUSTOMER_INTAKE (HIGH PRODUCTION)
        3. EXISTING_CUSTOMER_RESCHEDULE (ROUTINE / MEDIUM)
        4. BILLING_PAYMENT_INQUIRY (MEDIUM)
        5. POST_SERVICE_FOLLOWUP (CRITICAL / MEDIUM)
        6. HOURS_LOCATION_INFO (ROUTINE)
        """
        clean_text = text.lower().strip()
        best_match = "HOURS_LOCATION_INFO"
        highest_score = 0
        matched_symptoms = []

        for category, meta in TRIAGE_CATEGORIES.items():
            score = 0
            hits = []
            for kw in meta["keywords"]:
                if kw in clean_text:
                    score += 2 if len(kw.split()) > 1 else 1
                    hits.append(kw)
            if score > highest_score:
                highest_score = score
                best_match = category
                matched_symptoms = hits

        meta = TRIAGE_CATEGORIES[best_match]
        return {
            "intent_category": best_match,
            "category": best_match,  # Alias
            "priority": meta["priority"],
            "priority_level": meta["priority"],  # Alias
            "detected_symptoms": matched_symptoms or ["general inquiry"],
            "automated_action_directive": meta["action_directive"],
            "action_directive": meta["action_directive"]  # Alias
        }

    @classmethod
    def get_patient_spoken_reply(cls, triage_or_category: Any) -> str:
        """Maps a triage result dict or category key into natural, empathetic patient speech."""
        cat = (
            triage_or_category.get("intent_category") or triage_or_category.get("category")
            if isinstance(triage_or_category, dict)
            else str(triage_or_category or "HOURS_LOCATION_INFO")
        )
        return PATIENT_SPOKEN_REPLIES.get(cat, PATIENT_SPOKEN_REPLIES["HOURS_LOCATION_INFO"])

    def get_line_for_call(self, call_control_id: Optional[str]) -> Optional[str]:
        """Looks up which switchboard line tracks a live Telnyx call_control_id / CallSid."""
        if not call_control_id:
            return None
        mapped = self._call_id_to_line.get(call_control_id)
        if mapped and mapped in self.channels and self.channels[mapped].status != "completed":
            return mapped
        for lid, ch in self.channels.items():
            if ch.call_control_id == call_control_id and ch.status != "completed":
                self._call_id_to_line[call_control_id] = lid
                return lid
        return None

    def register_or_get_pstn_line(
        self,
        call_id: str,
        caller_phone: str = "Unknown Caller",
        caller_name: str = "Inbound Caller",
        initial_speech: str = ""
    ) -> Dict[str, Any]:
        """Assigns an inbound PSTN/TeXML call to a switchboard channel (or returns existing active line)."""
        existing = self.get_line_for_call(call_id)
        if existing:
            channel = self.channels[existing]
            if caller_phone and caller_phone != "Unknown Caller":
                channel.caller_phone = caller_phone
            if caller_name and caller_name != "Inbound Caller":
                channel.caller_name = caller_name
            return {"success": True, "line_id": existing, "channel": channel.dict(), "is_new": False}

        line_id = self.find_available_line()
        if not line_id:
            # Recycle oldest completed line or report capacity
            return {"success": False, "error": "SWITCHBOARD_AT_CAPACITY", "line_id": None}

        now_ms = int(time.time() * 1000)
        triage = self.classify_call_intent(initial_speech or "hours")
        ch = self.channels[line_id]
        ch.status = "active_ai"
        ch.caller_name = caller_name or "Inbound Caller"
        ch.caller_phone = caller_phone or "Unknown Caller"
        ch.member_id = None
        ch.started_at_ms = now_ms
        ch.duration_seconds = 0
        ch.triage_category = triage["intent_category"] if initial_speech else None
        ch.triage_priority = triage["priority"] if initial_speech else None
        ch.action_directive = triage["automated_action_directive"] if initial_speech else None
        ch.context_briefing_card = None
        ch.call_control_id = call_id
        ch.transcript = [
            {
                "speaker": "ai_agent",
                "text": "Thank you for calling Apex Dental Studio. This is Emily, your AI patient coordinator. How can I help you today?",
                "timestampIso": get_current_iso_time()
            }
        ]
        self.turn_controllers[line_id].reset()
        self._call_id_to_line[call_id] = line_id

        if initial_speech:
            self.process_line_turn(line_id, "customer", initial_speech)

        return {"success": True, "line_id": line_id, "channel": ch.dict(), "is_new": True}

    # -------------------------------------------------------------
    # Inbound Call Lifecycle (Simulated & Carrier PSTN)
    # -------------------------------------------------------------
    def simulate_inbound_call(
        self,
        caller_name: str = "Amanda Cole",
        caller_phone: str = "+1 555-332-9011",
        initial_message: str = "Hi, I have severe throbbing pain in my lower left molar and I cannot chew.",
        line_override: Optional[str] = None,
        member_id: Optional[str] = "MET-987654321"
    ) -> Dict[str, Any]:
        """
        Seeds an inbound phone call into one of the 4 switchboard channels:
        Transitions: ringing -> active_ai (AI Receptionist Emily answers immediately).
        """
        line_id = line_override or self.find_available_line()
        if not line_id or line_id not in self.channels:
            # If all 4 lines busy, return capacity limit notice
            return {
                "success": False,
                "error": "SWITCHBOARD_AT_CAPACITY",
                "message": "All 4 telephony channels currently engaged."
            }

        now_ms = int(time.time() * 1000)
        triage = self.classify_call_intent(initial_message)

        channel = self.channels[line_id]
        channel.status = "active_ai"
        channel.caller_name = caller_name
        channel.caller_phone = caller_phone
        channel.member_id = member_id
        channel.started_at_ms = now_ms
        channel.duration_seconds = 0
        channel.triage_category = triage["intent_category"]
        channel.triage_priority = triage["priority"]
        channel.action_directive = triage["automated_action_directive"]
        channel.context_briefing_card = None
        channel.call_control_id = f"call_{line_id}_{int(time.time())}"

        # Initialize Transcript with turn attribution
        emily_greeting = f"Thank you for calling Apex Dental Studio, this is Emily. How can I help you today?"
        channel.transcript = [
            {
                "speaker": "ai_agent",
                "text": emily_greeting,
                "timestampIso": get_current_iso_time()
            },
            {
                "speaker": "customer",
                "text": initial_message,
                "timestampIso": get_current_iso_time()
            }
        ]

        # Reset turn controller for this line
        tc = self.turn_controllers[line_id]
        tc.reset()

        logger.info(f"Switchboard [{line_id}]: Inbound call connected for {caller_name} ({caller_phone}). Triage: {triage['intent_category']}")
        return {
            "success": True,
            "line_id": line_id,
            "channel": channel.dict(),
            "triage": triage
        }

    # -------------------------------------------------------------
    # Conversational Turns & Vocal Barge-In
    # -------------------------------------------------------------
    def process_line_turn(
        self,
        line_id: str,
        speaker: str,
        text: str,
        audio_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Appends an attributed turn to the active line transcript with ISO timestamp."""
        channel = self.channels.get(line_id)
        if not channel:
            return {"success": False, "error": "Invalid line_id"}

        turn = {
            "speaker": speaker,  # customer, ai_agent, human_receptionist
            "text": text,
            "timestampIso": get_current_iso_time(),
            "audioUrl": audio_url
        }
        channel.transcript.append(turn)

        # Re-evaluate triage dynamically if customer mentions new clinical details
        if speaker == "customer":
            updated_triage = self.classify_call_intent(text)
            if updated_triage["priority"] in ("CRITICAL URGENT", "HIGH PRODUCTION"):
                channel.triage_category = updated_triage["intent_category"]
                channel.triage_priority = updated_triage["priority"]
                channel.action_directive = updated_triage["automated_action_directive"]

        return {"success": True, "turn": turn, "channel": channel.dict()}

    def process_vad_frame(
        self,
        line_id: str,
        raw_volume: float,
        now_ms: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Feeds an incoming audio frame into the channel's TurnController.
        Returns whether Vocal Barge-In is triggered (<200ms latency cutoff).
        """
        tc = self.turn_controllers.get(line_id)
        if not tc:
            return {"error": "Invalid line_id"}

        result = tc.process_audio_frame(raw_volume, now_ms=now_ms)
        return {"line_id": line_id, "vad": result}

    # -------------------------------------------------------------
    # Zero-Repetition Warm Transfer Protocol
    # -------------------------------------------------------------
    def initiate_warm_transfer(
        self,
        line_id: str,
        transferred_to: Optional[str] = None,
        operator_phone: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes Section 5 Zero-Repetition Warm Transfer:
        1. Formulates the structured Context Briefing Card whispered to operator.
        2. Transitions line status: active_ai -> warm_transfer_pending.
        3. Generates Telnyx TeXML call control (<Say> + <Dial>).
        """
        channel = self.channels.get(line_id)
        if not channel or channel.status == "completed":
            return {"success": False, "error": "Channel not active"}

        target_op = transferred_to or channel.target_operator
        op_phone = operator_phone or channel.operator_phone

        # Synthesize Zero-Repetition Briefing Schema
        customer_turns = [t["text"] for t in channel.transcript if t["speaker"] == "customer"]
        latest_need = customer_turns[-1] if customer_turns else "Seeking appointment or dental assistance."

        caller_summary = f"{channel.caller_name or 'Caller'} ({channel.caller_phone or 'Unknown Phone'}"
        if channel.member_id:
            caller_summary += f", Member ID {channel.member_id}"
        caller_summary += ")"

        # Generate intelligent suggestion resolution based on triage category
        cat = channel.triage_category or "HOURS_LOCATION_INFO"
        if cat == "EMERGENCY_URGENT":
            suggestion = "Patient in acute pain. Offer emergency buffer slot today at 2:00 PM; advise cold compress."
        elif cat == "NEW_CUSTOMER_INTAKE":
            suggestion = "New patient establishing care. Book 60-min initial comprehensive exam & take insurance ID."
        elif cat == "BILLING_PAYMENT_INQUIRY":
            suggestion = "MetLife covers 50% after $50 deductible. True estimated copay is $650."
        elif cat == "POST_SERVICE_FOLLOWUP":
            suggestion = "Patient reporting post-op discomfort. Verify gauze pressure protocol; triage for doctor callback if needed."
        elif cat == "EXISTING_CUSTOMER_RESCHEDULE":
            suggestion = "Reschedule requested. Next available recall hygiene slot is Thursday at 11:00 AM."
        else:
            suggestion = "Provide practice office hours (M-F 8AM-5PM, Sat 9AM-2PM) and direct booking link."

        briefing_card = {
            "callerSummary": caller_summary,
            "identifiedNeed": latest_need,
            "suggestedResolution": suggestion,
            "transferredTo": target_op,
            "timestampIso": get_current_iso_time()
        }

        channel.status = "warm_transfer_pending"
        channel.context_briefing_card = briefing_card
        channel.target_operator = target_op
        channel.operator_phone = op_phone

        # Generate Official TeXML Call Control Response
        texml_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Polly.Joanna-Neural" language="en-US">
    Connecting you directly to our front desk coordinator right now. Please hold.
  </Say>
  <Dial timeout="25">{op_phone}</Dial>
</Response>"""

        logger.info(f"Switchboard [{line_id}]: Warm Transfer Initiated to {target_op} ({op_phone})")
        return {
            "success": True,
            "line_id": line_id,
            "status": "warm_transfer_pending",
            "context_briefing_card": briefing_card,
            "texml_xml": texml_xml
        }

    # -------------------------------------------------------------
    # Call Completion & Archive
    # -------------------------------------------------------------
    def complete_call(self, line_id: str, reason: str = "Normal clearing") -> Dict[str, Any]:
        """Completes and archives the call, returning line to idle state."""
        channel = self.channels.get(line_id)
        if not channel:
            return {"success": False, "error": "Invalid line_id"}

        now_ms = int(time.time() * 1000)
        if channel.started_at_ms:
            channel.duration_seconds = max(0, int((now_ms - channel.started_at_ms) / 1000))

        channel.status = "completed"
        # Reset turn controller
        self.turn_controllers[line_id].reset()

        logger.info(f"Switchboard [{line_id}]: Call completed ({reason}). Duration: {channel.duration_seconds}s")
        return {
            "success": True,
            "line_id": line_id,
            "status": "completed",
            "duration_seconds": channel.duration_seconds,
            "channel": channel.dict()
        }

    def set_line_hold(self, line_id: str, on_hold: bool = True) -> Dict[str, Any]:
        """Toggles on_hold status for audio channel muting during staff lookup."""
        channel = self.channels.get(line_id)
        if not channel:
            return {"success": False, "error": "Invalid line_id"}

        channel.status = "on_hold" if on_hold else "active_ai"
        return {"success": True, "line_id": line_id, "status": channel.status}


# Singleton Switchboard Engine Instance
switchboard_engine = MultiLineSwitchboard()

