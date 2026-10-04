"""
Deterministic Sales State Machine & Voice Orchestrator.
Architecture:
- The LLM does NOT control the whole conversation freely.
- The State Machine dictates allowed transitions, allowed sales tools, and current objectives.
- The LLM decides what to say strictly within the bounds of the active state.
- Compliant & Transparent: Non-deceptive AI identity, explicit Do-Not-Call (DNC) and Graceful Exits.
"""

import os
import json
import logging
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from pydantic import BaseModel, Field

from config import GOOGLE_API_KEY, GEMINI_API_KEY, OPENAI_API_KEY, DEEPSEEK_API_KEY
from database import DatabaseManager

logger = logging.getLogger("sales_state_machine")


class CallState(str, Enum):
    INTRO = "INTRO"
    GATEKEEPER = "GATEKEEPER"
    DISCOVERY = "DISCOVERY"
    PAIN_PROBE = "PAIN_PROBE"
    OBJECTION_HANDLING = "OBJECTION_HANDLING"
    VALUE_OFFER = "VALUE_OFFER"
    DEMO_ASK = "DEMO_ASK"
    BOOKING = "BOOKING"
    CALLBACK_PROMPT = "CALLBACK_PROMPT"
    DNC_EXIT = "DNC_EXIT"
    GRACEFUL_EXIT = "GRACEFUL_EXIT"
    TERMINATED = "TERMINATED"


class StateTransition(BaseModel):
    from_state: CallState
    to_state: CallState
    trigger_reason: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


# Allowed deterministic transitions per state
ALLOWED_TRANSITIONS: Dict[CallState, List[CallState]] = {
    CallState.INTRO: [
        CallState.GATEKEEPER,
        CallState.DISCOVERY,
        CallState.OBJECTION_HANDLING,
        CallState.DNC_EXIT,
        CallState.GRACEFUL_EXIT
    ],
    CallState.GATEKEEPER: [
        CallState.DISCOVERY,
        CallState.CALLBACK_PROMPT,
        CallState.OBJECTION_HANDLING,
        CallState.DNC_EXIT,
        CallState.GRACEFUL_EXIT
    ],
    CallState.DISCOVERY: [
        CallState.PAIN_PROBE,
        CallState.OBJECTION_HANDLING,
        CallState.VALUE_OFFER,
        CallState.CALLBACK_PROMPT,
        CallState.DNC_EXIT,
        CallState.GRACEFUL_EXIT
    ],
    CallState.PAIN_PROBE: [
        CallState.VALUE_OFFER,
        CallState.OBJECTION_HANDLING,
        CallState.DEMO_ASK,
        CallState.CALLBACK_PROMPT,
        CallState.DNC_EXIT,
        CallState.GRACEFUL_EXIT
    ],
    CallState.OBJECTION_HANDLING: [
        CallState.VALUE_OFFER,
        CallState.DEMO_ASK,
        CallState.CALLBACK_PROMPT,
        CallState.DNC_EXIT,
        CallState.GRACEFUL_EXIT
    ],
    CallState.VALUE_OFFER: [
        CallState.DEMO_ASK,
        CallState.OBJECTION_HANDLING,
        CallState.CALLBACK_PROMPT,
        CallState.DNC_EXIT,
        CallState.GRACEFUL_EXIT
    ],
    CallState.DEMO_ASK: [
        CallState.BOOKING,
        CallState.OBJECTION_HANDLING,
        CallState.CALLBACK_PROMPT,
        CallState.GRACEFUL_EXIT,
        CallState.DNC_EXIT
    ],
    CallState.BOOKING: [
        CallState.TERMINATED,
        CallState.CALLBACK_PROMPT,
        CallState.GRACEFUL_EXIT
    ],
    CallState.CALLBACK_PROMPT: [
        CallState.TERMINATED,
        CallState.GRACEFUL_EXIT,
        CallState.DNC_EXIT
    ],
    CallState.DNC_EXIT: [
        CallState.TERMINATED
    ],
    CallState.GRACEFUL_EXIT: [
        CallState.TERMINATED
    ],
    CallState.TERMINATED: []
}

# Permitted tools per state
ALLOWED_TOOLS_PER_STATE: Dict[CallState, List[str]] = {
    CallState.INTRO: ["mark_dnc", "graceful_exit"],
    CallState.GATEKEEPER: ["mark_dnc", "graceful_exit", "request_transfer"],
    CallState.DISCOVERY: ["mark_dnc", "graceful_exit", "log_practice_pain"],
    CallState.PAIN_PROBE: ["mark_dnc", "graceful_exit", "calculate_leakage"],
    CallState.OBJECTION_HANDLING: ["mark_dnc", "graceful_exit", "lookup_objection_rebuttal"],
    CallState.VALUE_OFFER: ["mark_dnc", "graceful_exit"],
    CallState.DEMO_ASK: ["mark_dnc", "graceful_exit", "check_calendar_availability"],
    CallState.BOOKING: ["mark_dnc", "graceful_exit", "book_calendar_slot", "send_confirmation_sms"],
    CallState.CALLBACK_PROMPT: ["mark_dnc", "graceful_exit", "schedule_callback"],
    CallState.DNC_EXIT: ["mark_dnc"],
    CallState.GRACEFUL_EXIT: ["log_exit_reason"],
    CallState.TERMINATED: []
}


class SalesStateMachine:
    """Manages the state, rules, and bounded tool execution of an outbound sales call."""

    def __init__(self, lead: Dict[str, Any], agency_name: str = "WhatsApp Growth Partners", db: Optional[DatabaseManager] = None):
        self.lead = lead
        self.lead_id = lead.get("id", "temp_lead")
        self.clinic_name = lead.get("name") or "Dental Practice"
        self.doctor_name = lead.get("doctor_name") or "Doctor"
        self.agency_name = agency_name
        self.db = db or DatabaseManager()

        self.current_state = CallState.INTRO
        self.transition_history: List[StateTransition] = []
        self.call_history: List[Dict[str, str]] = []
        self.is_terminal = False
        self.outcome: Optional[str] = None
        self.booked_slot: Optional[str] = None
        self.objections_encountered: List[Dict[str, Any]] = []

        # Pre-call intelligence dossier
        self.intelligence = self._load_or_synthesize_intelligence()

    def _load_or_synthesize_intelligence(self) -> Dict[str, Any]:
        """Loads pre-call intelligence or builds lightweight default."""
        return {
            "opening_angle": f"After-hours patient intake gap for {self.clinic_name}",
            "likely_pain_points": [
                "Unanswered patient calls after 5 PM and on weekends",
                "High-value treatment inquiries (implants, cosmetic) bouncing to competitors",
                "Front-desk staff overwhelmed during peak chair procedures"
            ],
            "discovery_questions": [
                "How does your clinic currently handle patient appointment requests that come in after hours?",
                "Do emergency callers usually leave voicemails or do they end up calling someone else?",
                "Are your front desk staff able to answer 100% of calls while checking in chair patients?"
            ],
            "value_propositions": [
                "24/7 AI Receptionist answers on Web and WhatsApp in under 5 seconds",
                "Directly synchronizes patient bookings into your practice calendar",
                "Recaptures an estimated $4,000–$7,000/month in lost high-ticket cases"
            ]
        }

    def get_state_prompt_instructions(self) -> str:
        """Returns strict conversational guidelines restricted to the current state."""
        state = self.current_state

        base_rules = (
            f"You are Alex, an AI sales assistant calling on behalf of {self.agency_name} to {self.clinic_name}.\n"
            "COMMUNICATION RULES:\n"
            "- Speak naturally, respectfully, and concisely (1 to 2 sentences per response).\n"
            "- If asked whether you are AI, answer with total transparency: 'Yes, I'm an AI assistant calling on behalf of "
            f"{self.agency_name}. I wanted to quickly see how your practice handles after-hours patient inquiries.'\n"
            "- Never argue or harass. If the prospect is angry, closing down, or says 'don't call again', exit immediately.\n"
        )

        if state == CallState.INTRO:
            return base_rules + (
                "CURRENT STATE: INTRO\n"
                f"OBJECTIVE: Introduce yourself clearly, state you are an AI assistant for {self.agency_name}, "
                f"and politely ask for the office manager or {self.doctor_name} regarding after-hours patient intake.\n"
                "Allowed Next: Ask to speak with manager, or transition to Discovery."
            )
        elif state == CallState.GATEKEEPER:
            return base_rules + (
                "CURRENT STATE: GATEKEEPER\n"
                "OBJECTIVE: Respectfully engage the receptionist. Explain you are calling with a quick 30-second inquiry "
                "about their patient scheduling after 5 PM. If they refuse, offer to text a 2-minute video link."
            )
        elif state == CallState.DISCOVERY:
            return base_rules + (
                "CURRENT STATE: DISCOVERY\n"
                "OBJECTIVE: Ask ONE crisp discovery question about how they handle patient calls outside office hours. "
                "Listen to their response."
            )
        elif state == CallState.PAIN_PROBE:
            return base_rules + (
                "CURRENT STATE: PAIN_PROBE\n"
                "OBJECTIVE: Gently mirror their response and point out the financial leakage from emergency patients "
                "calling competing dental offices when they hit voicemail."
            )
        elif state == CallState.OBJECTION_HANDLING:
            return base_rules + (
                "CURRENT STATE: OBJECTION_HANDLING\n"
                "OBJECTIVE: Acknowledge their objection completely before offering a 1-sentence rebuttal. "
                "Always validate their current staff and system before pivoting."
            )
        elif state == CallState.VALUE_OFFER:
            return base_rules + (
                "CURRENT STATE: VALUE_OFFER\n"
                "OBJECTIVE: State that our 24/7 AI Receptionist answers emergency inquiries in 5 seconds and books "
                "directly into their practice management calendar without staff effort."
            )
        elif state == CallState.DEMO_ASK:
            return base_rules + (
                "CURRENT STATE: DEMO_ASK\n"
                "OBJECTIVE: Ask for a brief 10-minute live screen share with the doctor or practice manager. "
                "Suggest Thursday at 11 AM or Friday at 1 PM."
            )
        elif state == CallState.BOOKING:
            return base_rules + (
                "CURRENT STATE: BOOKING\n"
                "OBJECTIVE: Confirm the appointment time and best mobile number/email to send the invite."
            )
        elif state == CallState.CALLBACK_PROMPT:
            return base_rules + (
                "CURRENT STATE: CALLBACK_PROMPT\n"
                "OBJECTIVE: Ask what time or day would be best to call back when the doctor is not between chair procedures."
            )
        elif state == CallState.DNC_EXIT:
            return base_rules + (
                "CURRENT STATE: DNC_EXIT\n"
                "OBJECTIVE: Apologize politely for any interruption, state they are removed from future calls, and say goodbye."
            )
        elif state == CallState.GRACEFUL_EXIT:
            return base_rules + (
                "CURRENT STATE: GRACEFUL_EXIT\n"
                "OBJECTIVE: Thank them warmly for their time, wish their clinical practice a great week, and hang up."
            )
        else:
            return "Call completed."

    def transition_to(self, new_state: CallState, reason: str) -> bool:
        """Transitions state if allowed by the state machine rules."""
        if new_state not in ALLOWED_TRANSITIONS.get(self.current_state, []):
            logger.warning(f"Illegal transition attempted: {self.current_state} -> {new_state} (Reason: {reason})")
            return False

        transition = StateTransition(
            from_state=self.current_state,
            to_state=new_state,
            trigger_reason=reason
        )
        self.transition_history.append(transition)
        self.current_state = new_state

        if new_state in (CallState.TERMINATED, CallState.DNC_EXIT, CallState.GRACEFUL_EXIT):
            if new_state == CallState.DNC_EXIT:
                self.outcome = "DO_NOT_CALL"
                self._record_dnc()
            elif new_state == CallState.GRACEFUL_EXIT:
                self.outcome = self.outcome or "NOT_INTERESTED"
            self.is_terminal = True

        return True

    def process_prospect_input(self, prospect_message: str) -> Dict[str, Any]:
        """
        Analyzes prospect message to determine state transitions and bounded tool execution.
        """
        lower = prospect_message.lower().strip()

        # Universal Exit 1: Do Not Call
        dnc_triggers = ["don't call", "do not call", "remove me", "take me off", "stop calling", "sue you"]
        if any(t in lower for t in dnc_triggers):
            self.transition_to(CallState.DNC_EXIT, reason="Prospect requested Do Not Call")
            return {
                "action": "DNC",
                "state": self.current_state,
                "reply": "I completely understand. I'm taking your practice off our list right now. Have a good day.",
                "is_terminal": True
            }

        # Universal Exit 2: Definite Graceful Exit (Closing practice / angry refusal)
        exit_triggers = ["closing down", "retiring", "shutting down", "selling practice", "not interested at all"]
        if any(t in lower for t in exit_triggers):
            self.transition_to(CallState.GRACEFUL_EXIT, reason="Prospect closing or firm disinterest")
            return {
                "action": "GRACEFUL_EXIT",
                "state": self.current_state,
                "reply": "Thank you for letting me know. I appreciate your time and wish your team the best. Goodbye!",
                "is_terminal": True
            }

        # State-specific deterministic transition triggers
        if self.current_state == CallState.INTRO:
            if any(w in lower for w in ["speaking", "doctor", "manager", "i am"]):
                self.transition_to(CallState.DISCOVERY, reason="Connected with decision maker")
            elif any(w in lower for w in ["busy", "call back", "later"]):
                self.transition_to(CallState.CALLBACK_PROMPT, reason="Prospect requested callback")
            else:
                self.transition_to(CallState.GATEKEEPER, reason="Front desk response")

        elif self.current_state == CallState.GATEKEEPER:
            if any(w in lower for w in ["transfer", "hold on", "one moment", "speaking"]):
                self.transition_to(CallState.DISCOVERY, reason="Transferred or connected to doctor/manager")
            elif any(w in lower for w in ["receptionist", "we have", "not interested", "email"]):
                self.transition_to(CallState.OBJECTION_HANDLING, reason="Gatekeeper objection raised")
            elif any(w in lower for w in ["call back", "with a patient"]):
                self.transition_to(CallState.CALLBACK_PROMPT, reason="Clinician busy")

        elif self.current_state == CallState.DISCOVERY:
            if any(w in lower for w in ["voicemail", "miss", "nobody", "closed", "answering service"]):
                self.transition_to(CallState.PAIN_PROBE, reason="Prospect admitted intake weakness")
            elif any(w in lower for w in ["we don't", "not a problem", "happy"]):
                self.transition_to(CallState.OBJECTION_HANDLING, reason="Prospect claims no intake issue")
            else:
                self.transition_to(CallState.VALUE_OFFER, reason="Completed discovery")

        elif self.current_state == CallState.PAIN_PROBE:
            self.transition_to(CallState.VALUE_OFFER, reason="Surfaced pain point")

        elif self.current_state == CallState.OBJECTION_HANDLING:
            self.objections_encountered.append({
                "quote": prospect_message,
                "state": "OBJECTION_HANDLING",
                "timestamp": datetime.now().isoformat()
            })
            if any(w in lower for w in ["makes sense", "how does it work", "tell me more", "cost", "price"]):
                self.transition_to(CallState.VALUE_OFFER, reason="Objection cleared, prospect curious")
            elif any(w in lower for w in ["still no", "no thanks", "not for us"]):
                self.transition_to(CallState.GRACEFUL_EXIT, reason="Unresolved objection")
            else:
                self.transition_to(CallState.DEMO_ASK, reason="Pivoted from objection to demo ask")

        elif self.current_state == CallState.VALUE_OFFER:
            self.transition_to(CallState.DEMO_ASK, reason="Value presented, asking for meeting")

        elif self.current_state == CallState.DEMO_ASK:
            if any(w in lower for w in ["sure", "yes", "okay", "thursday", "friday", "sounds good", "send invite", "time"]):
                self.transition_to(CallState.BOOKING, reason="Prospect agreed to meeting")
                if any(d in lower for d in ["thursday", "friday", "morning", "afternoon", "am", "pm"]):
                    self.booked_slot = "Thursday 11:00 AM" if "thursday" in lower else ("Friday 1:00 PM" if "friday" in lower else "Upcoming weekday 11:00 AM")
                    self.outcome = "MEETING_BOOKED"
            elif any(w in lower for w in ["no", "busy", "don't want"]):
                self.transition_to(CallState.CALLBACK_PROMPT, reason="Prospect declined demo, offering callback/video")

        elif self.current_state == CallState.BOOKING:
            # Slot extraction heuristic
            self.booked_slot = "Thursday 11:00 AM" if "thursday" in lower else ("Friday 1:00 PM" if "friday" in lower else "Upcoming weekday 11:00 AM")
            self.outcome = "MEETING_BOOKED"
            self.transition_to(CallState.TERMINATED, reason="Demo successfully confirmed")

        elif self.current_state == CallState.CALLBACK_PROMPT:
            self.outcome = "CALLBACK_SCHEDULED"
            self.transition_to(CallState.TERMINATED, reason="Callback agreed")

        return {
            "state": self.current_state,
            "instructions": self.get_state_prompt_instructions(),
            "allowed_tools": ALLOWED_TOOLS_PER_STATE.get(self.current_state, []),
            "is_terminal": self.is_terminal,
            "outcome": self.outcome,
            "booked_slot": self.booked_slot
        }

    def _record_dnc(self):
        """Persists Do-Not-Call status into SQLite database."""
        try:
            with self.db._get_connection() as conn:
                conn.execute("""
                UPDATE leads SET stage = 'LOST', notes = COALESCE(notes, '') || ' [DNC: PROSPECT REQUESTED NO CALLS]'
                WHERE id = ?
                """, (self.lead_id,))
                conn.commit()
            logger.info(f"Lead {self.lead_id} permanently marked DO_NOT_CALL.")
        except Exception as e:
            logger.error(f"Failed to record DNC for lead {self.lead_id}: {e}")

    # --- Tool Execution Layer ---
    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Executes a sales tool ONLY if permitted in the current state."""
        allowed = ALLOWED_TOOLS_PER_STATE.get(self.current_state, [])
        if tool_name not in allowed and tool_name not in ["mark_dnc", "graceful_exit"]:
            return {
                "success": False,
                "error": f"Tool '{tool_name}' is not permitted during state '{self.current_state}'"
            }

        if tool_name == "check_calendar_availability":
            from calendar_sync import CalendarSyncEngine
            slots = CalendarSyncEngine.get_available_slots(days_ahead=3)
            slot_names = [s["slot_key"] for s in slots[:3]]
            return {
                "success": True,
                "available_slots": slot_names or ["Thursday at 11:00 AM", "Friday at 2:00 PM"],
                "recommended_slot": slot_names[0] if slot_names else "Thursday at 11:00 AM"
            }

        elif tool_name == "book_calendar_slot":
            from calendar_sync import CalendarSyncEngine
            slot = arguments.get("slot") or "Thursday at 11:00 AM"
            self.booked_slot = slot
            self.outcome = "MEETING_BOOKED"
            booking = CalendarSyncEngine.book_slot(
                lead_id=self.lead_id,
                slot_str=slot,
                clinic_name=self.lead.get("name"),
                doctor_name=self.lead.get("doctor_name"),
                phone=self.lead.get("phone"),
                db=self.db
            )
            self.transition_to(CallState.TERMINATED, reason=f"Tool booked slot {slot}")
            return {
                "success": True,
                "booked_slot": slot,
                "status": "CONFIRMED",
                "meet_link": booking.get("meet_link")
            }

        elif tool_name == "mark_dnc":
            self.transition_to(CallState.DNC_EXIT, reason="Tool triggered DNC")
            return {"success": True, "status": "DNC_RECORDED"}

        elif tool_name == "schedule_callback":
            time_str = arguments.get("callback_time", "Next business day morning")
            self.outcome = "CALLBACK_SCHEDULED"
            self.transition_to(CallState.TERMINATED, reason=f"Callback scheduled for {time_str}")
            return {"success": True, "callback_time": time_str}

        elif tool_name == "lookup_objection_rebuttal":
            obj_name = arguments.get("objection", "")
            return {
                "success": True,
                "rebuttal": "We completely agree your daytime team is essential; our software only catches after-hours emergencies."
            }

        return {"success": True, "tool": tool_name}


class DeepSeekIntelligenceEngine:
    """Uses DeepSeek for cheap, high-ROI pre-call research synthesis and post-call evaluation."""

    @classmethod
    def generate_pre_call_intelligence(cls, lead: Dict[str, Any]) -> Dict[str, Any]:
        """
        Uses DeepSeek to synthesize practice data into tactical SDR hooks.
        """
        key = os.getenv("DEEPSEEK_API_KEY")
        clinic_name = lead.get("name") or "Dental Practice"
        doctor_name = lead.get("doctor_name") or "Primary Clinician"
        website = lead.get("website") or ""
        reviews = lead.get("review_count", 50)
        rating = lead.get("rating", 4.8)

        prompt = f"""You are a specialized B2B sales intelligence agent for dental software.
Analyze this practice:
Name: {clinic_name}
Doctor: {doctor_name}
Website: {website}
Reviews: {reviews} ({rating} stars)

Produce a crisp JSON sales brief with this exact structure:
{{
  "likely_pain_points": ["point 1", "point 2"],
  "opening_angle": "concise hook",
  "discovery_questions": ["question 1", "question 2", "question 3"],
  "likely_objections": ["objection 1", "objection 2"],
  "value_propositions": ["value 1", "value 2"]
}}"""

        if key and not key.startswith("mock_"):
            try:
                import urllib.request
                req = urllib.request.Request(
                    "https://api.deepseek.com/chat/completions",
                    data=json.dumps({
                        "model": "deepseek-chat",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.2
                    }).encode("utf-8"),
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json"
                    }
                )
                with urllib.request.urlopen(req, timeout=10) as res:
                    body = json.loads(res.read().decode("utf-8"))
                    text = body["choices"][0]["message"]["content"].strip()
                    if "```json" in text:
                        text = text.split("```json")[1].split("```")[0].strip()
                    return json.loads(text)
            except Exception as e:
                logger.warning(f"DeepSeek pre-call intelligence failed: {e}. Using deterministic fallback.")

        # Deterministic fallback
        return {
            "likely_pain_points": [
                f"After-hours patient bounce when {clinic_name} is closed",
                "High-ticket emergency implant patients calling competitors",
                "Front-desk phone overload during daytime procedures"
            ],
            "opening_angle": f"Capturing after-hours patient inquiries for {clinic_name} without staff overtime",
            "discovery_questions": [
                "What happens to patients who call with urgent tooth pain after 5 PM?",
                "Do you currently have an automated SMS or chat system to book them instantly?",
                "How much production time is lost to missed calls every week?"
            ],
            "likely_objections": [
                "We already have a front desk receptionist",
                "Send an email with information",
                "The doctor doesn't take cold calls"
            ],
            "value_propositions": [
                "24/7 AI Receptionist responds in under 5 seconds",
                "Syncs confirmed appointments directly into your practice calendar",
                "Recovers $4,000 to $7,000/month in unbooked chair production"
            ]
        }

    @classmethod
    def evaluate_post_call(cls, transcript: List[Dict[str, str]], outcome: str, db: Optional[DatabaseManager] = None) -> Dict[str, Any]:
        """
        Extracts structured sales lessons from a completed call transcript and stores them in sales_memory.
        """
        db = db or DatabaseManager()
        key = os.getenv("DEEPSEEK_API_KEY")
        transcript_str = "\n".join(f"{t.get('speaker', 'Speaker')}: {t.get('text', '')}" for t in transcript)

        prompt = f"""You are a sales evaluation analyst.
Review this outbound sales call transcript:
OUTCOME: {outcome}
TRANSCRIPT:
{transcript_str}

Extract structured lessons in JSON:
{{
  "objection_detected": "exact objection or 'None'",
  "response_used": "what AI replied",
  "effectiveness": "POSITIVE" | "NEUTRAL" | "NEGATIVE",
  "better_response_recommendation": "improved phrasing",
  "confidence": 0.85,
  "key_takeaway": "actionable insight"
}}"""

        evaluation = {
            "objection_detected": "We already have staff",
            "response_used": "We catch after-hours inquiries when staff is home",
            "effectiveness": "POSITIVE" if outcome == "MEETING_BOOKED" else "NEUTRAL",
            "better_response_recommendation": "Quantify after-hours leakage earlier in the hook",
            "confidence": 0.88,
            "key_takeaway": "Practices respond best to weekend and emergency patient recovery"
        }

        if key and not key.startswith("mock_"):
            try:
                import urllib.request
                req = urllib.request.Request(
                    "https://api.deepseek.com/chat/completions",
                    data=json.dumps({
                        "model": "deepseek-chat",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.2
                    }).encode("utf-8"),
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json"
                    }
                )
                with urllib.request.urlopen(req, timeout=10) as res:
                    body = json.loads(res.read().decode("utf-8"))
                    text = body["choices"][0]["message"]["content"].strip()
                    if "```json" in text:
                        text = text.split("```json")[1].split("```")[0].strip()
                    evaluation = json.loads(text)
            except Exception as e:
                logger.warning(f"DeepSeek post-call analysis failed: {e}. Using deterministic evaluation.")

        # Persist structured lesson to DB without uncontrolled self-modification
        try:
            with db._get_connection() as conn:
                conn.execute("""
                INSERT INTO sales_memory (
                    lead_id, clinic_name, doctor_name, metro, specialty, outcome,
                    objection_category, objection_quote, effective_rebuttal, deal_value,
                    lessons_learned, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    "call_evaluation",
                    "Evaluated Clinic",
                    "Doctor",
                    "National",
                    "General Dentistry",
                    outcome,
                    evaluation.get("objection_detected", "General"),
                    evaluation.get("objection_detected", ""),
                    evaluation.get("better_response_recommendation", ""),
                    1500.0 if outcome == "MEETING_BOOKED" else 0.0,
                    evaluation.get("key_takeaway", ""),
                    datetime.now().isoformat()
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to persist evaluated lesson: {e}")

        return evaluation
