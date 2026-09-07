"""
AI Call Roleplay Simulator.
Pre-call sparring partner for solo agency founders:
- Personas:
  1. GATEKEEPER_RECEPTIONIST: Guarded, protective of doctor's schedule ("Dr. Vance doesn't take unsolicited calls. Send an email to info@").
  2. BUSY_DOCTOR: Impatient, skeptical of marketing agencies, values clinical chair time ("I have 60 seconds between procedures. What is this?").
- Evaluates turns across Hook (1-10), Value Proposition (1-10), Control & Closing (1-10).
- Provides instant tactical coaching tips and objection pivots.
"""

import os
import json
import logging
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from config import GOOGLE_API_KEY

logger = logging.getLogger("call_simulator")


class TurnEvaluation(BaseModel):
    hook_score: int = Field(default=7, ge=1, le=10)
    value_score: int = Field(default=7, ge=1, le=10)
    control_score: int = Field(default=7, ge=1, le=10)
    overall_score: int = Field(default=7, ge=1, le=10)
    tactical_feedback: str
    suggested_pivot: str


class SimulatorTurnResponse(BaseModel):
    session_id: str
    persona: str
    speaker_name: str
    prospect_response: str
    status: str  # IN_PROGRESS, MEETING_WON, HANGUP, CALLBACK_AGREED
    evaluation: TurnEvaluation


class AICallSimulator:
    """Simulates real-world cold call sparring against dental office personas."""

    PERSONA_PROFILES = {
        "GATEKEEPER_RECEPTIONIST": {
            "title": "Front Desk Receptionist / Office Manager",
            "temperament": "Protective, busy answering phones, reflex objection is 'send an email' or 'we're not interested'.",
            "goal": "Filter out cold calls without letting unsolicited pitches reach the doctor.",
            "test_questions": [
                "Is Dr. [NAME] expecting your call?",
                "We already have a web person who handles everything.",
                "Can you just send an email with your pricing to info@[DOMAIN]?"
            ]
        },
        "BUSY_DOCTOR": {
            "title": "Owner / Principal Dentist",
            "temperament": "Clinical, impatient, high skepticism toward digital marketing agencies, values production time.",
            "goal": "Get back to patients unless you immediately prove you can fix real revenue leakage without wasting chair time.",
            "test_questions": [
                "Look, I've got a patient in chair 2 right now. Give me the 15-second version.",
                "I get five calls a day from people selling SEO or AI. What makes you different?",
                "How much does it cost and how much of my time will it take?"
            ]
        }
    }

    @classmethod
    def start_session(
        cls,
        lead_dict: Dict[str, Any],
        persona: str = "GATEKEEPER_RECEPTIONIST"
    ) -> Dict[str, Any]:
        """Initializes a roleplay call session with an opening greeting from the prospect."""
        lead_name = lead_dict.get("name") or "Dental Clinic"
        doc_name = lead_dict.get("doctor_name")
        persona_key = persona if persona in cls.PERSONA_PROFILES else "GATEKEEPER_RECEPTIONIST"

        if persona_key == "BUSY_DOCTOR":
            doc_display = f"Dr. {doc_name}" if doc_name else "Dr. Miller"
            greeting = f"Hello, this is {doc_display}. Make it quick please, I'm between root canals."
            speaker_name = doc_display
        else:
            receptionist_names = ["Sarah", "Jessica", "Ashley", "Emily", "Maria"]
            # Pick deterministically from lead name
            idx = sum(ord(c) for c in lead_name) % len(receptionist_names)
            speaker_name = f"{receptionist_names[idx]} (Front Desk)"
            greeting = f"Thank you for calling {lead_name}, this is {receptionist_names[idx]}. How can I direct your call?"

        session_id = f"sim_{lead_dict.get('id', 'temp')}_{abs(hash(greeting)) % 100000}"

        return {
            "session_id": session_id,
            "persona": persona_key,
            "speaker_name": speaker_name,
            "initial_message": greeting,
            "lead_name": lead_name,
            "doctor_name": doc_name,
            "status": "IN_PROGRESS",
            "history": [
                {"role": "assistant", "content": greeting, "speaker": speaker_name}
            ]
        }

    @classmethod
    def simulate_turn(
        cls,
        lead_dict: Dict[str, Any],
        persona: str,
        conversation_history: List[Dict[str, str]],
        user_pitch: str,
        api_key: Optional[str] = None
    ) -> SimulatorTurnResponse:
        """
        Executes one turn of sparring:
        Sends conversation history + user pitch to Gemini 2.5 Flash, which plays the prospect
        and evaluates the rep's tactical performance.
        """
        persona_key = persona if persona in cls.PERSONA_PROFILES else "GATEKEEPER_RECEPTIONIST"
        profile = cls.PERSONA_PROFILES[persona_key]
        lead_name = lead_dict.get("name") or "Dental Clinic"
        doc_name = lead_dict.get("doctor_name") or "the doctor"
        annual_gap = lead_dict.get("annual_gap") or 42000
        monthly_gap = int(annual_gap / 12)
        technologies = lead_dict.get("technologies") or []
        tech_str = ", ".join(technologies) if technologies else "No online chat or 24/7 booking"

        key = api_key or GOOGLE_API_KEY or os.getenv("GEMINI_API_KEY")

        if key and not key.startswith("mock_"):
            try:
                from google import genai
                client = genai.Client(api_key=key)

                history_text = ""
                for turn in conversation_history:
                    role_label = "Prospect" if turn.get("role") == "assistant" else "Sales Rep"
                    history_text += f"{role_label}: {turn.get('content')}\n"

                prompt = f"""
You are an expert sales trainer and a realistic roleplay partner.
You are roleplaying as a dental practice {profile['title']} for '{lead_name}'.
Doctor name: {doc_name}.
Current practice tech: {tech_str}.
Estimated missed revenue: ${monthly_gap}/month due to uncaptured after-hours patient calls.

PERSONA ATTRIBUTES:
- Role: {persona_key}
- Profile: {profile['temperament']}
- Objective: {profile['goal']}

CONVERSATION SO FAR:
{history_text}
Sales Rep: "{user_pitch}"

TASK:
1. Stay in character as {profile['title']} and provide the next realistic verbal response.
   - If the rep's pitch was generic, push back with a common objection (e.g. "We already have a receptionist", "Doctor is busy", "Send an email").
   - If the rep addressed a real problem (e.g., missed evening calls, lost new patient implants) and asked a low-friction question, soften up or agree to a quick 10-minute Zoom with Dr. {doc_name}.
   - If the rep was aggressive, spammy, or pushy, hang up or firmly decline.
2. Determine the conversation status: "IN_PROGRESS", "MEETING_WON", "HANGUP", or "CALLBACK_AGREED".
3. Evaluate the Sales Rep's pitch across 3 dimensions (1-10 scale):
   - Hook: Did they grab attention in 7 seconds without sounding like a sleazy telemarketer?
   - Value: Did they connect to practice revenue or patient capture?
   - Control: Did they maintain conversational control and close with a sharp binary question?
4. Provide 1 actionable tactical coaching tip for improvement.
5. Provide 1 suggested objection pivot sentence they could have used instead.

Respond strictly in valid JSON matching this schema:
{{
  "speaker_name": "{profile['title']}",
  "prospect_response": "The in-character verbal response.",
  "status": "IN_PROGRESS",
  "hook_score": 8,
  "value_score": 7,
  "control_score": 8,
  "overall_score": 8,
  "tactical_feedback": "One clear sentence of tactical advice.",
  "suggested_pivot": "The exact wording to pivot."
}}
"""
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt,
                )

                txt = response.text.strip()
                if "```json" in txt:
                    txt = txt.split("```json")[1].split("```")[0].strip()
                elif "```" in txt:
                    txt = txt.split("```")[1].split("```")[0].strip()

                data = json.loads(txt)
                return SimulatorTurnResponse(
                    session_id=f"sim_{lead_dict.get('id', 'temp')}",
                    persona=persona_key,
                    speaker_name=data.get("speaker_name", profile["title"]),
                    prospect_response=data.get("prospect_response", "We're not interested, thank you."),
                    status=data.get("status", "IN_PROGRESS"),
                    evaluation=TurnEvaluation(
                        hook_score=int(data.get("hook_score", 7)),
                        value_score=int(data.get("value_score", 7)),
                        control_score=int(data.get("control_score", 7)),
                        overall_score=int(data.get("overall_score", 7)),
                        tactical_feedback=data.get("tactical_feedback", "State the specific financial gap earlier in the pitch."),
                        suggested_pivot=data.get("suggested_pivot", f"Dr. {doc_name}, most clinics lose 3-5 weekend implant inquiries because nobody answers at 8 PM. Does your front desk capture those today?")
                    )
                )
            except Exception as e:
                logger.warning(f"Gemini call simulator failed, falling back to deterministic model: {e}")

        # Deterministic Sparring Engine (High Quality Fallback)
        return cls._deterministic_turn(lead_dict, persona_key, user_pitch)

    @classmethod
    def _deterministic_turn(
        cls,
        lead_dict: Dict[str, Any],
        persona: str,
        pitch: str
    ) -> SimulatorTurnResponse:
        """Rule-based simulation for testing and offline execution."""
        pitch_lower = pitch.lower()
        lead_name = lead_dict.get("name") or "the clinic"
        doc_name = lead_dict.get("doctor_name") or "the doctor"

        # Check key tactical sales patterns
        mentioned_doctor = bool(doc_name and doc_name.lower() in pitch_lower) or "dr." in pitch_lower or "doctor" in pitch_lower
        mentioned_problem = any(w in pitch_lower for w in ["missed", "after-hours", "booking", "patient", "receptionist", "call", "inquiries", "revenue"])
        asked_close = any(w in pitch_lower for w in ["thursday", "tuesday", "morning", "afternoon", "10 minutes", "open to", "fair to say", "?"])
        is_sleazy = any(w in pitch_lower for w in ["guarantee", "leads", "grow your business", "number one on google", "seo"])

        hook_score = 8 if mentioned_doctor else 5
        value_score = 9 if mentioned_problem else 5
        control_score = 8 if asked_close else 5

        if is_sleazy:
            hook_score = max(2, hook_score - 4)
            value_score = max(2, value_score - 3)
            control_score = max(2, control_score - 3)

        overall_score = round((hook_score + value_score + control_score) / 3)

        if persona == "BUSY_DOCTOR":
            speaker = f"Dr. {doc_name}" if doc_name else "Dr. Miller"
            if overall_score >= 8:
                response_text = f"Alright, you actually did your homework on {lead_name}. I'm with a patient right now, but have your calendar invite sent to my front desk for Thursday at 12:15 PM."
                status = "MEETING_WON"
                feedback = "Excellent! You named the specific clinic pain immediately and respected the doctor's clinical time."
                pivot = "Lock down the email address immediately and send the calendar invite before hanging up."
            elif overall_score >= 5:
                response_text = "Look, we get three marketing companies pitching us every week. What specifically did you find broken on our site?"
                status = "IN_PROGRESS"
                feedback = "You piqued interest, but you need to state the specific missed revenue leak from their after-hours gap."
                pivot = f"Dr. {doc_name}, your site has no 24/7 booking. When an emergency patient visits at 9 PM, they bounce to your competitor down the road."
            else:
                response_text = "I don't have time for this marketing pitch. Take me off your list."
                status = "HANGUP"
                feedback = "Sounded too much like a generic agency pitch. Never pitch 'AI' or 'leads'—pitch uncaptured patient revenue."
                pivot = f"Dr. {doc_name}, quick question: when someone calls at 7:30 PM with a cracked crown, who books them right now?"
        else:
            speaker = "Front Desk (Sarah)"
            if overall_score >= 8:
                response_text = f"Honestly, our front desk has been slammed and we do miss evening inquiries. Let me see if Dr. {doc_name} has 10 minutes open on Thursday lunch."
                status = "MEETING_WON"
                feedback = "Phenomenal gatekeeper navigation! You validated her workload instead of treating her as an obstacle."
                pivot = "Confirm the best phone number and secure the direct calendar slot."
            elif overall_score >= 5:
                response_text = f"Dr. {doc_name} is in treatment right now. If you want to email information to frontdesk@{lead_name.lower().replace(' ', '')}.com, we'll review it."
                status = "IN_PROGRESS"
                feedback = "Standard defensive gatekeeper reflex. Acknowledge the email address, but bridge back to a concrete problem."
                pivot = "I can definitely send an email, but Sarah, if I do, what should I put in the subject line so you know it's about the missed weekend calls?"
            else:
                response_text = "We are completely happy with our current setup and don't accept cold calls. Have a good day."
                status = "HANGUP"
                feedback = "Triggered immediate defensive gatekeeper filter. Never ask 'how are you doing today'—it screams telemarketer."
                pivot = f"Hi Sarah, could you help me for a moment? I had a quick question regarding Dr. {doc_name}'s after-hours patient intake."

        return SimulatorTurnResponse(
            session_id=f"sim_{lead_dict.get('id', 'temp')}",
            persona=persona,
            speaker_name=speaker,
            prospect_response=response_text,
            status=status,
            evaluation=TurnEvaluation(
                hook_score=hook_score,
                value_score=value_score,
                control_score=control_score,
                overall_score=overall_score,
                tactical_feedback=feedback,
                suggested_pivot=pivot
            )
        )
