"""
Empathy Voice Prompt Engine & Conversational Guardrails.
Implements the 12-Second Brevity Rule, Conversational Micro-Affirmations,
Dynamic Objection Variation Matrix (Anti-Repetition), and the 3-Step Empathy Bridge
(Validate -> Disarm -> Pivot) for human-grade dental outbound sales calls.
"""

import re
import random
from typing import Dict, Any, List, Optional, Set


class EmpathyVoicePromptEngine:
    """Enforces human-grade acoustic, psychological, and conversational empathy for voice sales agents."""

    BREVITY_MAX_WORDS = 20

    # 1. Conversational Micro-Affirmations / Instant Fillers
    MICRO_AFFIRMATIONS = [
        "Totally get that.",
        "Makes complete sense.",
        "Fair enough.",
        "100%, completely understand.",
        "Right, yeah.",
        "Understood.",
        "I hear you."
    ]

    # 2. Dynamic Objection Playbooks with Multiple Natural Variations (Anti-Repetition Matrix)
    OBJECTION_PLAYBOOKS: Dict[str, Dict[str, Any]] = {
        "send_email": {
            "keywords": ["send an email", "send email", "email us", "info@", "send me information", "send over some info", "email it"],
            "variations": [
                "Happy to email it over! What is the office manager's direct first name so it doesn't get buried in the info inbox?",
                "Can definitely do that. Who coordinates {doctor}'s schedule so I can address the 60-second video directly to them?",
                "Sure thing! Rather than spamming your general inbox, who handles practice growth so I can send the quick audit?",
                "Will do! What's the best direct email for your practice manager so they can review the weekend intake breakdown?",
                "Absolutely. Would you like me to send that to your attention, or directly to your office manager?"
            ]
        },
        "have_front_desk": {
            "keywords": ["already have a receptionist", "front desk handles it", "have staff", "we have someone who answers", "our staff handles"],
            "variations": [
                "100%, and your front desk does fantastic work during office hours! We only catch high-value Sunday implant inquiries when your team is home.",
                "Totally agree, your team handles daytime calls. The gap is simply weekend emergencies hitting voicemail and calling competitors.",
                "Makes complete sense. We don't touch daytime calls; we just prevent after-hours callers from bouncing to another practice.",
                "Of course! This is strictly for the fifteen to twenty inquiries that come in between Friday evening and Monday morning.",
                "Fair enough! Your receptionist is irreplaceable. We simply act as their safety net when the office is closed."
            ]
        },
        "have_ehr": {
            "keywords": ["dentrix", "eaglesoft", "open dental", "weave", "nexhealth", "already use", "our system", "software"],
            "variations": [
                "Dentrix is great for clinical charting! We actually integrate alongside it to capture weekend patients after hours.",
                "Weave is fantastic during office hours. Our system simply catches high-ticket Sunday implant patients when your team is home.",
                "We don't replace your system at all—we feed confirmed appointments right into your existing schedule.",
                "Totally get that! We work directly with your existing software so your staff doesn't have to learn a new tool.",
                "Understood. Most practices we partner with use that exact setup—we just plug the 6 PM to 8 AM gap."
            ]
        },
        "doctor_busy": {
            "keywords": ["with a patient", "in surgery", "busy right now", "doesn't take calls", "chair time", "in with a patient", "treating patients"],
            "variations": [
                "Totally understand, {doctor} is focused on patients. Who coordinates the doctor's calendar so I can send a 60-second video?",
                "Completely get that, patient care comes first! Could I shoot a quick 60-second video breakdown to your office manager?",
                "No problem at all, didn't mean to interrupt chair time. When does the office manager usually review practice tools?",
                "Fair enough! If I send over a quick one-page diagnostic of your after-hours setup, who is the best person to take a look?",
                "Understood. What is the best time tomorrow to catch the practice manager for just two minutes?"
            ]
        },
        "how_much": {
            "keywords": ["how much", "cost", "pricing", "price", "what are your fees", "expensive"],
            "variations": [
                "It is a flat fifteen hundred dollars turnkey installation and three ninety-nine a month—capturing just one weekend implant covers the entire year.",
                "Just three ninety-nine a month with zero per-lead fees. If it captures even one emergency crown, it pays for itself three times over.",
                "Under four hundred dollars a month. Would Thursday at eleven work to take a quick five-minute look at how it runs live?",
                "It's three ninety-nine monthly, and most clinics see an extra four to six thousand in recovered appointments within thirty days."
            ]
        },
        "not_interested": {
            "keywords": ["not interested", "no thank you", "don't need it", "not looking", "no thanks", "not at this time"],
            "variations": [
                "Totally fair, appreciate your honesty! If capturing Sunday implant inquiries ever becomes a priority, we're here. Have a great day!",
                "Appreciate your straightforwardness! I will let you get back to your patients. Have a wonderful rest of the week.",
                "No worries at all! If you ever want to see how local clinics capture after-hours emergencies, our door is open. Take care!",
                "Fair enough! Thanks for taking the time to let me know, and have a fantastic week ahead."
            ]
        },
        "who_is_this": {
            "keywords": ["who is this", "who are you", "what company", "what is this regarding", "why are you calling", "who is calling"],
            "variations": [
                "Hi, this is Jordan calling regarding {doctor}'s after-hours patient intake in {city}. Do you oversee the scheduling calendar?",
                "Hey there, Jordan with Dental Intake Partners. Noticed your Google profile in {city} has no after-hours booking on weekends.",
                "Hi, Jordan calling! Just a quick 20-second call regarding weekend patient inquiries for {clinic}."
            ]
        },
        "call_back_later": {
            "keywords": ["call back later", "call tomorrow", "bad time", "call back", "try later"],
            "variations": [
                "Happy to call back! Would tomorrow morning or Thursday afternoon be better for the practice manager?",
                "Understood! When is a calmer time for your front desk—around two or closer to four?",
                "Totally respect that. What day this week is generally lightest so I don't interrupt your desk?"
            ]
        }
    }

    @classmethod
    def build_voice_system_prompt(cls, dossier: Dict[str, Any]) -> str:
        """
        Builds the unified system prompt for real-time speech dialogue.
        Enforces brevity, empathy, anti-repetition, consultative posture, and pre-call intelligence.
        """
        doc = dossier.get("doctor_display", "the Doctor")
        clinic = dossier.get("clinic_name", "the clinic")
        city = dossier.get("city", "your area")
        leakage = dossier.get("monthly_leakage", "$5,200")
        detected_ehr = dossier.get("detected_ehr", "standard office software")

        return f"""You are Jordan, Practice Growth Director at Dental Intake Partners calling {clinic} in {city}.

### CONVERSATIONAL CORE DIRECTIVE:
You are a calm, polished, consultative peer—NOT a fast-talking telemarketer or an eager robotic bot.
You speak like a respected healthcare consultant having an unhurried, respectful conversation with a colleague.

### THE 12-SECOND BREVITY RULE (NON-NEGOTIABLE):
1. Keep EVERY response to 1 short, natural sentence (10 to 18 words MAXIMUM).
2. NEVER monologue. After making a single point, pass conversational control back with a simple question.
3. Pause naturally. Use conversational warmth, empathy, and contractions ("I'm", "we've", "don't").

### CRITICAL ANTI-REPETITION MANDATE:
- Check previous turns in the conversation transcript carefully.
- NEVER repeat a greeting, pitch, statistic, or question you already asked earlier in the call.
- Always validate their specific statement, disarm any friction, and advance to the next natural step.

### PRE-CALL INTELLIGENCE (DOSSIER):
- Clinic: {clinic} ({city})
- Target Principal: {doc}
- Existing System: {detected_ehr}
- Quantified Opportunity: Est. {leakage}/month in missed weekend/after-hours new patient inquiries
- Gatekeeper Objective: Do not pitch the receptionist. Ask for the office manager with polite disarming permission.

### DISARMING OPENERS:
- If receptionist answers: "Hi, know you're likely juggling patients at the desk so I'll be 20 seconds. Quick question regarding {doc}'s after-hours schedule..."
- If office manager answers: "Hi, I was reviewing {clinic}'s Google profile in {city}. Noticed your patient intake drops after 6 PM on mobile. Is that something you oversee?"
- If Doctor answers: "Hi {doc}, know you're likely between chair appointments so I'll be brief. Noticed your site in {city} is leaking about {leakage} in after-hours patient bookings..."

### 3-STEP EMPATHY BRIDGE (FOR ANY OBJECTION):
1. VALIDATE: Warmly agree with their point ('Totally get that', 'Makes complete sense').
2. DISARM: Remove sales friction ('Not trying to sell anything right now', 'Not interrupting clinical time').
3. PIVOT: Offer low-friction value (a 60-second custom video audit or confirming Thursday at 11 AM).

### DNC / OPT-OUT RULE:
If prospect asks to stop or remove number, say:
"Understood, removed your number right now. Have a wonderful day!" and immediately disconnect.
"""

    @classmethod
    def detect_objection(cls, transcript: str) -> Optional[str]:
        """Identifies common dental gatekeeper objections from prospect utterance."""
        t_lower = transcript.lower()
        for key, pb in cls.OBJECTION_PLAYBOOKS.items():
            if any(kw in t_lower for kw in pb["keywords"]):
                return key
        return None

    @classmethod
    def get_empathy_rebuttal(
        cls,
        objection_type: str,
        dossier: Dict[str, Any],
        used_phrases: Optional[List[str]] = None
    ) -> str:
        """
        Returns a fresh 3-Step Empathy Bridge rebuttal for a detected objection.
        GUARANTEES no repetition across turns by filtering out previously spoken variations.
        """
        pb = cls.OBJECTION_PLAYBOOKS.get(objection_type)
        doc = dossier.get("doctor_display", "the Doctor")
        clinic = dossier.get("clinic_name", "the clinic")
        city = dossier.get("city", "your area")

        if not pb or not pb.get("variations"):
            return f"Totally understand. Could I share a quick 60-second video with {doc}'s office manager?"

        variations = pb["variations"]
        used_set = set(used_phrases or [])

        # Format variations with clinic context
        formatted_vars = []
        for v in variations:
            formatted = v.format(doctor=doc, clinic=clinic, city=city)
            formatted_vars.append(formatted)

        # Filter out variations that have already been spoken in this call
        fresh_vars = [v for v in formatted_vars if v not in used_set]

        if fresh_vars:
            chosen = random.choice(fresh_vars)
        else:
            # If all variations exhausted, select a gentle escalation / disarm
            chosen = f"Fair enough! I completely respect your time. Have a wonderful rest of your day!"

        return cls.enforce_brevity(chosen)

    @classmethod
    def enforce_brevity(cls, text: str) -> str:
        """Post-processes and trims any wordy LLM responses to adhere to conversational limits."""
        if not text:
            return ""
        # Remove markdown quotes and clean spacing
        clean = text.replace('"', '').replace('\n', ' ').strip()
        words = clean.split()
        if len(words) <= cls.BREVITY_MAX_WORDS:
            return clean

        # If it exceeded word limit, truncate at the first or second sentence boundary
        sentences = re.split(r'(?<=[.?!])\s+', clean)
        accum = []
        accum_words = 0
        for s in sentences:
            s_len = len(s.split())
            if accum_words + s_len <= cls.BREVITY_MAX_WORDS:
                accum.append(s)
                accum_words += s_len
            else:
                break

        if accum:
            return " ".join(accum).strip()

        # Hard truncate at word limit with clean ending
        trimmed = " ".join(words[:cls.BREVITY_MAX_WORDS])
        if not trimmed.endswith((".", "?", "!")):
            trimmed += "..."
        return trimmed
