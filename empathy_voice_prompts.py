"""
Empathy Voice Prompt Engine & Conversational Guardrails.
Implements the 12-Second Brevity Rule, Conversational Micro-Affirmations,
and the 3-Step Empathy Bridge (Validate -> Disarm -> Pivot) for human-grade dental outbound sales calls.
"""

import re
from typing import Dict, Any, List, Optional


class EmpathyVoicePromptEngine:
    """Enforces human-grade acoustic, psychological, and conversational empathy for voice sales agents."""

    BREVITY_MAX_WORDS = 18

    # 1. Conversational Micro-Affirmations
    MICRO_AFFIRMATIONS = [
        "Totally get that.",
        "Makes complete sense.",
        "Fair enough.",
        "100%, completely understand.",
        "Right, right.",
        "I hear you."
    ]

    # 2. Empathy Bridge Objections & Rebuttals
    OBJECTION_PLAYBOOKS = {
        "send_email": {
            "keywords": ["send an email", "send email", "email us", "info@", "send me information", "send over some info"],
            "validation": "I can definitely do that!",
            "disarm": "Rather than sending a generic PDF that gets lost in info@,",
            "pivot": "What is the office manager's direct first name so I can address the 45-second analysis specifically to them?"
        },
        "have_front_desk": {
            "keywords": ["already have a receptionist", "front desk handles it", "have staff", "we have someone who answers"],
            "validation": "100%, and your front desk does fantastic work during office hours!",
            "disarm": "The gap is simply between 6 PM and 8 AM and weekends when patients in pain hit voicemail.",
            "pivot": "Right now, those callers hit voicemail and call the next clinic on Google. We simply catch those."
        },
        "have_ehr": {
            "keywords": ["dentrix", "eaglesoft", "open dental", "weave", "nexhealth", "already use"],
            "validation": "Dentrix is great for clinical charting—we don't touch your charting.",
            "disarm": "The challenge is that when a patient in pain searches at 8 PM on a Saturday, charting software can't answer them.",
            "pivot": "We install a WhatsApp concierge that feeds confirmed bookings directly into your existing schedule."
        },
        "doctor_busy": {
            "keywords": ["with a patient", "in surgery", "busy right now", "doesn't take calls", "chair time"],
            "validation": "Totally understand, patient chair time comes first.",
            "disarm": "Not looking to interrupt clinical care at all.",
            "pivot": "Could I shoot a quick 60-second video breakdown of your after-hours setup to your office manager's email?"
        },
        "how_much": {
            "keywords": ["how much", "cost", "pricing", "price", "what are your fees"],
            "validation": "Fair question!",
            "disarm": "It is a flat $1,500 turnkey installation and $399 a month.",
            "pivot": "Capturing just one single weekend dental crown or implant covers the entire year. Would Thursday at 11 AM work to view the live prototype?"
        },
        "not_interested": {
            "keywords": ["not interested", "no thank you", "don't need it", "not looking"],
            "validation": "Totally fair, appreciate your honesty!",
            "disarm": "If you ever notice after-hours inquiries dropping on weekends,",
            "pivot": "Feel free to check out our Dallas clinic case study. Wishing you a great rest of the day!"
        }
    }

    @classmethod
    def build_voice_system_prompt(cls, dossier: Dict[str, Any]) -> str:
        """
        Builds the unified system prompt for real-time speech dialogue.
        Enforces brevity, empathy, consultative posture, and pre-call intelligence.
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
1. Keep EVERY response to 1 to 2 short sentences (10 to 18 words MAXIMUM).
2. NEVER monologue. After making a single point, pass conversational control back with a simple question.
3. Pause naturally. Use conversational warmth and empathy.

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
1. VALIDATE: Warmly agree with their point ('Totally get that', '100% makes sense').
2. DISARM: Remove sales friction ('Not trying to sell anything right now', 'Not interrupting clinical time').
3. PIVOT: Offer low-friction value (a 60-second custom video audit or confirming 7-minute look on Thursday).

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
    def get_empathy_rebuttal(cls, objection_type: str, dossier: Dict[str, Any]) -> str:
        """Returns the pre-computed 3-Step Empathy Bridge rebuttal for a detected objection."""
        pb = cls.OBJECTION_PLAYBOOKS.get(objection_type)
        if not pb:
            return "Totally understand. Could I share a quick two-minute video diagnostic with your office manager?"

        clean_rebuttal = f"{pb['validation']} {pb['disarm']} {pb['pivot']}"
        return clean_rebuttal

    @classmethod
    def enforce_brevity(cls, text: str) -> str:
        """Post-processes and trims any wordy LLM responses to adhere to the 12-second rule."""
        if not text:
            return ""
        # Remove markdown quotes
        clean = text.replace('"', '').replace('\n', ' ').strip()
        words = clean.split()
        if len(words) <= cls.BREVITY_MAX_WORDS:
            return clean

        # If it exceeded word limit, truncate at the first sentence boundary
        sentences = re.split(r'(?<=[.?!])\s+', clean)
        if sentences and len(sentences[0].split()) <= cls.BREVITY_MAX_WORDS:
            return sentences[0].strip()

        # Hard truncate at word limit with clean ending
        trimmed = " ".join(words[:cls.BREVITY_MAX_WORDS])
        if not trimmed.endswith((".", "?", "!")):
            trimmed += "..."
        return trimmed
