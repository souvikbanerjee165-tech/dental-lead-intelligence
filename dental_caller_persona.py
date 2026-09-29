"""
Dental Caller Persona & Dynamic Script Generator.
Generates research-backed conversational scripts, objection battlecards, and system prompts
for autonomous outbound AI voice calls to dental clinics.
"""

from typing import Dict, Any, List, Optional
import json


class DentalCallerPersona:
    """Generates hyper-personalized cold outreach phone scripts and live objection playbooks."""

    @classmethod
    def build_call_script(cls, lead: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generates structured conversational assets tailored to the specific dental clinic.
        """
        clinic_name = lead.get("name") or "the dental practice"
        doctor_name = lead.get("doctor_name")
        if not doctor_name or doctor_name.lower() in ("not identified", "unknown", "primary dentist"):
            doc_salutation = "the practice owner"
            doc_display = "Doctor"
        else:
            clean_doc = doctor_name.replace("Dr.", "").replace("Dr", "").strip()
            doc_salutation = f"Dr. {clean_doc}"
            doc_display = f"Dr. {clean_doc}"

        phone = lead.get("phone") or "their office line"
        raw_addr = lead.get("address") or ""
        city = raw_addr.split(",")[-2].strip() if ("," in raw_addr and len(raw_addr.split(",")) >= 2) else "your area"
        rating = lead.get("rating", 4.8)
        reviews = lead.get("review_count", 65)

        # Revenue leakage calculations
        rev_min = lead.get("missed_rev_min") or lead.get("audit_missed_rev_min") or 3500
        rev_max = lead.get("missed_rev_max") or lead.get("audit_missed_rev_max") or 6800
        monthly_leakage = f"${rev_max:,.0f}" if rev_max else "$5,200"

        # Specialties / High value procedures
        services = lead.get("high_value_services") or lead.get("specialties") or []
        if isinstance(services, str):
            try:
                services = json.loads(services)
            except Exception:
                services = [s.strip() for s in services.split(",") if s.strip()]
        if not services:
            services = ["Dental Implants", "Emergency Care", "Cosmetic Dentistry"]

        top_services_str = " and ".join(services[:2]) if len(services) >= 2 else services[0]

        # 1. Gatekeeper / Receptionist Hook
        gatekeeper_hook = (
            f"Hi, good morning! I'm calling for {doc_salutation}'s office manager. "
            f"I was reviewing {clinic_name}'s patient intake setup for {top_services_str}. "
            f"Could you tell me who handles patient scheduling after 5 PM when the office is closed?"
        )

        # 2. Doctor Direct Hook (15-second elevator pitch)
        doctor_hook = (
            f"Hi {doc_display}, I know you're likely between chair appointments so I'll be brief. "
            f"We noticed {clinic_name}'s stellar {rating}★ reputation in {city}, but right now "
            f"prospective emergency and {services[0]} patients have no way to book online after hours. "
            f"Our models show that's leaking about {monthly_leakage} a month to neighboring practices. "
            f"We install a 24/7 AI receptionist that captures those calls directly into your calendar."
        )

        # 3. Dynamic Objection Battlecard
        objections = [
            {
                "objection": "We already have a front desk receptionist.",
                "rebuttal": (
                    f"Completely agree, your receptionist is invaluable during office hours! "
                    f"The challenge is that ~42% of urgent dental searches happen after 6 PM and on weekends when the front desk is closed. "
                    f"Right now those patients hit voicemail and immediately call the next dentist on Google. We catch those callers in seconds."
                )
            },
            {
                "objection": "The doctor is with a patient / Doesn't take unsolicited calls.",
                "rebuttal": (
                    f"Totally understand, patient chair time comes first. "
                    f"Could I send a quick 2-minute video prototype showing how the after-hours calendar syncs with your system "
                    f"to {doc_salutation}'s direct email or mobile?"
                )
            },
            {
                "objection": "Send an email to info@ / we'll pass it along.",
                "rebuttal": (
                    f"I can certainly do that! What is the office manager's direct first name so I can address the custom {city} analysis "
                    f"specifically to them rather than letting it get lost in the general inbox?"
                )
            },
            {
                "objection": "We already use Dentrix / Weave.",
                "rebuttal": (
                    f"Dentrix is great for clinical charting and billing—we don't touch your charting. "
                    f"The problem is that when a patient in pain calls at 7 PM or over the weekend, Dentrix can't answer them or recover the call. "
                    f"Our WhatsApp engine instantly engages them in under 5 seconds, collects their details, and feeds confirmed appointments right to your team."
                )
            },
            {
                "objection": "How much does it cost?",
                "rebuttal": (
                    f"It's a flat $1,500 turnkey installation and $399 a month for ongoing maintenance and support. "
                    f"Recovering just one single emergency crown or filling each month covers the entire maintenance fee multiple times over. "
                    f"Would you be open to a 10-minute preview on Thursday?"
                )
            }
        ]

        # 4. Closing / Next Steps
        closing_pitches = {
            "calendar_demo": f"Would Thursday at 11 AM or Friday at 1 PM work better for a 10-minute screen share with {doc_salutation}?",
            "sms_video_prototype": f"I can text a 2-minute Loom walkthrough showing your practice's exact prototype right to your cell. Is this number best?"
        }

        # 5. Institutional Memory Flywheel Integration
        try:
            from memory_manager import MemoryManager
            learnings = MemoryManager.get_learnings_for_lead(lead)
        except Exception:
            learnings = None

        if learnings and learnings.get("top_market_objections"):
            for mo in learnings["top_market_objections"][:2]:
                cat = mo.get("objection_category")
                rebuttal = mo.get("effective_rebuttal") or mo.get("lessons_learned")
                if cat and rebuttal and not any(cat.lower() in o["objection"].lower() for o in objections):
                    objections.append({
                        "objection": f"{cat} (Market Learned Pattern)",
                        "rebuttal": rebuttal
                    })

        return {
            "clinic_name": clinic_name,
            "doctor_salutation": doc_salutation,
            "doctor_name": doctor_name,
            "city": city,
            "monthly_leakage": monthly_leakage,
            "top_services": services,
            "gatekeeper_hook": gatekeeper_hook,
            "doctor_hook": doctor_hook,
            "objections": objections,
            "closing_pitches": closing_pitches,
            "institutional_memory": learnings
        }

    @classmethod
    def generate_system_prompt(cls, lead: Dict[str, Any], caller_name: str = "Alex") -> str:
        """
        Creates the real-time LLM system prompt for the voice agent to maintain
        a conversational, consultative, non-pushy demeanor during outbound calling.
        """
        script = cls.build_call_script(lead)
        objection_text = "\n".join(
            f"- Objection: \"{o['objection']}\"\n  Response: \"{o['rebuttal']}\""
            for o in script["objections"]
        )

        memory_prompt_segment = ""
        learnings = script.get("institutional_memory")
        if learnings and learnings.get("memory_summary_prompt"):
            memory_prompt_segment = f"""
INSTITUTIONAL SALES MEMORY & MARKET LEARNINGS:
- {learnings['memory_summary_prompt']}
- Tactic: Use past wins as subtle social proof without violating patient privacy.
"""

        return f"""You are {caller_name}, a polite, professional, and knowledgeable dental growth specialist calling on behalf of Dental Intelligence Automation.

TARGET CLINIC DETAILS:
- Practice Name: {script['clinic_name']}
- Doctor / Owner: {script['doctor_salutation']}
- Market: {script['city']}
- High Value Services: {', '.join(script['top_services'])}
- Estimated Monthly After-Hours Leakage: {script['monthly_leakage']}
{memory_prompt_segment}
YOUR CORE OBJECTIVE:
Your goal is NOT to sell on this call. Your only goal is to secure a 10-minute demo on Zoom with the doctor/office manager OR get permission to send a 2-minute SMS video prototype to their cell phone.

CONVERSATIONAL RULES (CRITICAL):
1. Keep your responses short and punchy: Speak in 1 to 2 sentences MAXIMUM per turn. Real phone calls are fast dialogues, not speeches.
2. Tone: Warm, respectful, consultative, unhurried, natural. Never sound like an aggressive pushy telemarketer.
3. Natural conversation fillers: Occasionally use natural acknowledgment phrases ("Got it", "Fair enough", "Totally understand", "Makes complete sense").
4. If the person answering is the Receptionist:
   - Use the Gatekeeper Hook: "{script['gatekeeper_hook']}"
   - Respect their time, ask if the doctor or office manager is available, or offer to send a 2-minute video.
5. If the person answering is the Doctor:
   - Use the Doctor Hook: "{script['doctor_hook']}"
   - Address their chair time and focus on the missed weekend/evening revenue.
6. When handling objections:
{objection_text}
7. Closing question:
   - "{script['closing_pitches']['calendar_demo']}"

CALL CONTROL INSTRUCTIONS:
- If they agree to a meeting or video, immediately ask: "Great, what's the best cell number or email to confirm that?"
- Once confirmed, thank them warmly and wrap up the call politely.
"""
