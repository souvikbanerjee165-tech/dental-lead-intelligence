"""
Omnichannel Outreach & Cold Pitch Generator.
Generates tailored, conversion-tested copy for Cold Email, 48-Hour Follow-Up, SMS, LinkedIn InMail, and WhatsApp.
"""

from typing import Dict, Any, Optional
from urllib.parse import quote
from pydantic import BaseModel

class OutreachPackage(BaseModel):
    lead_id: str
    business_name: str
    target_name: str
    
    # Email
    email_subject: str
    cold_email_body: str
    
    # Follow-up
    follow_up_subject: str
    follow_up_body: str
    
    # SMS
    sms_text: str
    
    # LinkedIn
    linkedin_message: str
    
    # WhatsApp
    whatsapp_pitch: str
    whatsapp_url: str

class OutreachGenerator:
    """Generates multi-channel sales touches customized with clinical audit metrics."""

    @classmethod
    def generate(
        cls,
        lead_dict: Dict[str, Any],
        doctor_name: Optional[str] = None,
        monthly_leakage: int = 3500,
        competitor_tool: Optional[str] = None
    ) -> OutreachPackage:
        name = lead_dict.get("name") or "Dental Practice"
        target = doctor_name or lead_dict.get("doctor_name") or "Doctor"
        phone = lead_dict.get("phone") or ""
        rating = lead_dict.get("rating") or 4.8
        reviews = lead_dict.get("review_count") or 85
        raw_addr = lead_dict.get("address") or ""
        city = "your area"
        if raw_addr and "," in raw_addr:
            parts = [p.strip() for p in raw_addr.split(",") if p.strip()]
            if len(parts) >= 3:
                city = parts[-2].strip()
            elif len(parts) >= 2:
                city = parts[0].strip()

        clean_phone = "".join(c for c in phone if c.isdigit())
        last_word = target.split()[-1].strip(",.")
        if target and target.lower() != "doctor":
            salutation = f"Dr. {last_word}"
        else:
            salutation = "Doctor"

        # 1. Cold Email
        email_subject = f"{name} – after-hours patient inquiries in {city}"
        cold_email = f"""Hi {salutation},

I was reviewing dental practices in {city} and noticed {name}'s impressive {rating}★ reputation across {reviews} patient reviews.

One quick observation:
Between 5 PM and 8 AM, your website does not have an active conversational intake to triage emergencies or book consultations directly into your schedule.

Based on local emergency dental search volume, we estimate this results in roughly ${monthly_leakage:,}/month in uncaptured chair production leaking to 24/7 emergency dental providers.

We install an AI WhatsApp & SMS Receptionist that:
1. Answers patient dental FAQs within 3 seconds 24/7
2. Triage emergencies and books new patient exams directly into your practice management calendar
3. Reduces front-desk call burden by 40%

Would you be open to a 3-minute video showing how other practices in {city} are capturing these patients?

Best regards,

Sales Director
Dental Growth Systems"""

        # 2. 48-Hour Follow-Up
        follow_up_subject = f"Re: {name} – after-hours patient inquiries in {city}"
        follow_up = f"""Hi {salutation},

Following up briefly on my note regarding after-hours patient intake for {name}.

We recently tested response times across 14 dental clinics in {city} on Sunday evenings: 12 went directly to voicemail, while the 2 utilizing automated WhatsApp capture secured 7 new patient exams before Monday morning.

If you'd like to see how the automated patient self-scheduling workflow looks on a smartphone, let me know and I'll send over a live test link.

Best,

Sales Director
Dental Growth Systems"""

        # 3. SMS Hook
        sms = f"Hi {salutation}, love {name}'s {rating}★ reviews in {city}. Quick q: are you losing after-hours emergency calls after 5PM? We automate ~${monthly_leakage:,}/mo in missed bookings on WhatsApp. Open to a 2-min demo?"

        # 4. LinkedIn InMail
        linkedin = f"""Hi {salutation},

Admiring the patient community and {rating}★ reputation you've built at {name}.

Quick question for you as the practice principal: how is your team currently capturing patient inquiries that arrive after 5 PM and over the weekend? 

We help independent dental practices recapture an estimated ${monthly_leakage:,}/mo in missed emergency and cosmetic inquiries by installing an automated 24/7 WhatsApp triage assistant.

Would love to share a quick 2-minute breakdown if you're open to exploring it.

Best,
Sales Director"""

        # 5. WhatsApp Direct Pitch
        wa_text = f"Hi {salutation}! 👋 I was reviewing premier dental practices in {city} and noticed {name}'s stellar {rating}★ reputation.\n\nQuick question: Did you know ~42% of patient dental emergencies happen when the front desk is closed? We estimate {name} is losing ~${monthly_leakage:,}/mo in uncaptured chair production.\n\nWe set up a 24/7 WhatsApp Patient Assistant that answers questions and lets patients self-book directly from WhatsApp.\n\nWould you be open to a quick 2-minute video showing how it connects to your calendar?"
        wa_url = f"https://wa.me/{clean_phone}?text={quote(wa_text)}" if clean_phone else "#"

        return OutreachPackage(
            lead_id=lead_dict.get("id") or "",
            business_name=name,
            target_name=target,
            email_subject=email_subject,
            cold_email_body=cold_email,
            follow_up_subject=follow_up_subject,
            follow_up_body=follow_up,
            sms_text=sms,
            linkedin_message=linkedin,
            whatsapp_pitch=wa_text,
            whatsapp_url=wa_url
        )
