import urllib.parse
from typing import Dict, Any, Optional, List

COMPETITOR_ANALYSIS = {
    "tidio": {
        "name": "Tidio",
        "weakness": "Generic browser widget that disconnects when the patient switches tabs or locks their phone.",
        "pitch_angle": "85% of dental searches are on mobile phones. Tidio traps conversations in a browser tab instead of WhatsApp where the patient actually replies.",
        "objection_rebuttal": "Tidio is great for desktop e-commerce, but emergency dental patients on mobile abandon browser chats in seconds. Our WhatsApp AI stays right on their phone so your clinic never loses the lead."
    },
    "podium": {
        "name": "Podium",
        "weakness": "Primarily built for SMS review requests and basic messaging; lacks automated 24/7 clinical emergency triage and direct WhatsApp scheduling.",
        "pitch_angle": "Podium costs hundreds a month for basic texting. Our solution provides 24/7 automated emergency patient intake over WhatsApp with instant qualification.",
        "objection_rebuttal": "Podium is helpful for reviews, but it doesn't automatically triage emergency toothaches at 10 PM and book them into open calendar slots via WhatsApp."
    },
    "weave": {
        "name": "Weave",
        "weakness": "Heavy VoIP phone system; weak after-hours mobile conversational automation.",
        "pitch_angle": "Weave handles your daytime office phones, but does not capture after-hours WhatsApp emergency patients who refuse to leave voicemails.",
        "objection_rebuttal": "Weave is a solid phone system, but today's patients don't leave voicemails after hours—they click the next clinic on Google. We plug into your after-hours gap via WhatsApp."
    },
    "nexhealth": {
        "name": "NexHealth",
        "weakness": "Rigid form-based appointment scheduling without conversational AI triage or WhatsApp persistence.",
        "pitch_angle": "NexHealth uses static multi-step forms. Emergency patients in pain want a 30-second conversational WhatsApp booking, not a 6-page online form.",
        "objection_rebuttal": "NexHealth is great for calendar syncing, but high-friction forms cause 60% drop-off on mobile. Our WhatsApp assistant guides patients through a conversational 3-question booking."
    },
    "intercom": {
        "name": "Intercom",
        "weakness": "Designed for SaaS tech companies, not local dental clinics. Lacks dental emergency workflows.",
        "pitch_angle": "Intercom is designed for software support. We provide dental-specific WhatsApp triage trained on emergency toothaches, cosmetic consults, and insurance questions.",
        "objection_rebuttal": "Intercom is built for tech companies and has high software overhead. Our WhatsApp engine is 100% turnkey for dental patient acquisition."
    }
}

class SalesBattlecardGenerator:
    """Generates an actionable, pre-call sales briefing and objection matrix for any dental lead."""

    @classmethod
    def generate_battlecard(cls, lead: Dict[str, Any]) -> Dict[str, Any]:
        """Compile a comprehensive sales battlecard from lead attributes."""
        lead_id = lead.get("id", "")
        name = lead.get("name", "Dental Practice")
        doctor_name = lead.get("doctor_name") or "Doctor"
        role = lead.get("decision_maker_role") or "Practice Owner"
        phone = lead.get("phone", "")
        website = lead.get("website", "")
        rating = lead.get("rating", 0.0)
        reviews = lead.get("review_count", 0)
        opp_score = lead.get("opportunity_score", 70)
        
        # Financial metrics
        rev_min = lead.get("missed_rev_min") or lead.get("estimated_missed_revenue_monthly_min") or 3500
        rev_max = lead.get("missed_rev_max") or lead.get("estimated_missed_revenue_monthly_max") or 6800
        annual_rev = (rev_min + rev_max) // 2 * 12

        # Extract address / city
        address = lead.get("address", "")
        city = "your area"
        if address:
            parts = [p.strip() for p in address.split(",") if p.strip()]
            if len(parts) >= 2:
                city = parts[-2]

        # Tech stack competitor inspection
        detected_chatbot = (lead.get("detected_chatbot_name") or "").lower()
        detected_booking = lead.get("detected_booking_tool") or ""
        
        # Check competitor profile
        competitor_profile = None
        for key, comp in COMPETITOR_ANALYSIS.items():
            if key in detected_chatbot:
                competitor_profile = comp
                break

        # Vulnerability summary
        if competitor_profile:
            tech_status = f"Using {competitor_profile['name']} (Browser-only widget)"
            tech_weakness = competitor_profile["weakness"]
            comp_name = competitor_profile["name"]
        elif detected_chatbot:
            tech_status = f"Using {detected_chatbot.title()} widget"
            tech_weakness = "Generic web chat widget lacking automated 24/7 WhatsApp emergency triage."
            comp_name = detected_chatbot.title()
        else:
            tech_status = "No Active Chatbot / No AI Receptionist"
            tech_weakness = "Zero after-hours digital patient intake. Visitors between 6 PM and 8 AM have no way to book emergency appointments."
            comp_name = "None"

        # Booking tool status
        if detected_booking:
            booking_status = f"Online booking active ({detected_booking})"
        else:
            booking_status = "No direct online booking (Telephone-only friction)"

        # 15-Second Cold Call Opening Script for Doctor
        greeting_doc = doctor_name if doctor_name != "Doctor" else f"Dr. at {name}"
        if comp_name != "None":
            doc_hook = (
                f"“Hi {greeting_doc}, my name is [Your Name]. I was reviewing {name}’s digital setup in {city}—"
                f"you have a great clinical reputation with {reviews} reviews, but I noticed your website is using {comp_name}. "
                f"Most emergency patients searching on their phones bounce because browser chats don't connect to WhatsApp. "
                f"We help clinics capture an estimated ${rev_min:,.0f}–${rev_max:,.0f}/mo in after-hours patient bookings without adding staff. "
                f"Do you have 2 minutes to hear how we plug that leak?”"
            )
        else:
            doc_hook = (
                f"“Hi {greeting_doc}, my name is [Your Name]. I was looking at {name}’s patient intake in {city}—"
                f"you have an impressive {rating}★ rating, but patients searching after 5 PM have no way to book an emergency slot or reach you on WhatsApp. "
                f"In {city}, practices with your search volume typically leak ${rev_min:,.0f}–${rev_max:,.0f} every month in uncaptured after-hours inquiries. "
                f"We set up a 24/7 automated WhatsApp receptionist that books patients directly into your calendar. "
                f"Would you be open to a 2-minute overview?”"
            )

        # Gatekeeper / Office Manager Script
        gatekeeper_hook = (
            f"“Hi, I was hoping to speak with whoever handles patient intake and front-desk operations at {name}. "
            f"I put together an audit showing how many prospective emergency patients visiting {website or name} after 5 PM "
            f"are bouncing because there’s no instant WhatsApp booking. Is {doctor_name} or the office manager available for 60 seconds?”"
        )

        # Objection Handling Matrix
        if competitor_profile:
            obj_chat_rebuttal = competitor_profile["objection_rebuttal"]
        else:
            obj_chat_rebuttal = (
                "“Contact forms have an average 14-hour response delay. An emergency toothache or cosmetic inquiry won't wait—"
                "they click the next dental clinic on Google Maps. Our WhatsApp AI answers in 15 seconds and books the appointment while you're asleep.”"
            )

        objections = [
            {
                "objection": "“We already have a front desk / receptionist answering our phones.”",
                "rebuttal": "“Your front desk does an amazing job during normal hours, but what happens when a patient cracks a crown at 9:00 PM on a Tuesday? Over 42% of high-value dental searches occur outside office hours. We give your staff qualified appointments on their calendar every morning without paying overtime.”"
            },
            {
                "objection": f"“We already have a website chat tool / form ({comp_name}).”" if comp_name != "None" else "“We already have a website contact form.”",
                "rebuttal": obj_chat_rebuttal
            },
            {
                "objection": "“We're too busy right now / not looking for more patients.”",
                "rebuttal": "“That’s exactly why high-volume clinics use us—not just for more volume, but to free up your front desk staff from answering the same 20 repetitive questions about insurance and pricing all day so they can focus on delivering care to patients in the chair.”"
            }
        ]

        # 1-Click WhatsApp Pitch Message
        wa_text = (
            f"Hi {greeting_doc}! 👋 I noticed {name} has a great {rating}★ rating ({reviews} reviews) in {city}. "
            f"Quick question: how do you currently capture patients who need emergency appointments after 5 PM? "
            f"We built an automated 24/7 WhatsApp AI receptionist that recovers an estimated ${rev_min:,.0f}–${rev_max:,.0f}/mo "
            f"in after-hours inquiries without requiring front-desk staff. Would you like a 60-second video demo of how it works for dental practices?"
        )
        clean_phone = "".join(c for c in phone if c.isdigit())
        if len(clean_phone) == 10:
            clean_phone = f"1{clean_phone}"
        wa_url = f"https://wa.me/{clean_phone}?text={urllib.parse.quote(wa_text)}" if clean_phone else f"https://wa.me/?text={urllib.parse.quote(wa_text)}"

        return {
            "lead_id": lead_id,
            "business_name": name,
            "doctor_name": doctor_name,
            "decision_maker_role": role,
            "phone": phone,
            "website": website,
            "rating": rating,
            "reviews": reviews,
            "opportunity_score": opp_score,
            "estimated_monthly_leakage": f"${rev_min:,.0f} – ${rev_max:,.0f}/mo",
            "estimated_annual_leakage": f"${annual_rev:,.0f}/yr",
            "tech_status": tech_status,
            "tech_weakness": tech_weakness,
            "competitor_detected": comp_name,
            "booking_status": booking_status,
            "cold_call_doctor_script": doc_hook,
            "gatekeeper_script": gatekeeper_hook,
            "objection_matrix": objections,
            "whatsapp_pitch_message": wa_text,
            "whatsapp_direct_url": wa_url
        }
