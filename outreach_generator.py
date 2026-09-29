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

    @classmethod
    def generate_step_sequence(
        cls,
        lead_dict: Dict[str, Any],
        touch_number: int = 1
    ) -> Dict[str, Any]:
        """Generates dynamic non-repeating follow-up touches across Email, WhatsApp, and Phone (Phase 12)."""
        name = lead_dict.get("name") or "Dental Practice"
        target = lead_dict.get("doctor_name") or "Doctor"
        last_word = target.split()[-1].strip(",.")
        salutation = f"Dr. {last_word}" if target.lower() != "doctor" else "Doctor"
        raw_addr = lead_dict.get("address") or ""
        city = "your area"
        if raw_addr and "," in raw_addr:
            city = raw_addr.split(",")[-2].strip()
        leakage = lead_dict.get("missed_rev_max") or 4500
        clean_phone = "".join(c for c in (lead_dict.get("phone") or "") if c.isdigit())

        if touch_number == 1:
            # Touch 1 (Day 1): Intake Gap Awareness
            target_tag = f" / {target}" if target and target.lower() != "doctor" else ""
            subject = f"{name}{target_tag} - after-hours patient inquiries in {city}"
            email = f"Hi {salutation},\n\nNoticed {name}'s strong patient reputation in {city}. Between 5 PM and 8 AM, inquiries have no conversational intake to book exams directly into your schedule.\n\nWe estimate ~${leakage:,}/mo in uncaptured chair production is leaking to 24/7 dental clinics. Open to a 3-min video showing how other practices in {city} capture these patients?"
            wa = f"Hi {salutation}! 👋 Quick question for {name}: Did you know ~42% of dental emergencies call when the office is dark? We automate ~${leakage:,}/mo in after-hours bookings on WhatsApp. Open to a 2-min demo?"
            call_hook = f"Hi {salutation}, our practice intake audit for {name} showed you're losing an estimated ${leakage:,}/mo in after-hours emergency patient inquiries. What happens when someone calls at 8 PM on Sunday?"
            delay_days = 0
            angle_name = "Intake Gap & Revenue Leakage"
            stage_label = "Touch 1 (Intake Gap Awareness)"

        elif touch_number == 2:
            # Touch 2 (Day 3): Local Market Social Proof / Peer Comparison
            subject = f"Re: {name} - Sunday Study & weekend patient response in {city}"
            email = f"Hi {salutation},\n\nFollowing up briefly: we recently tested 14 dental clinics in {city} on Sunday evening. 12 went straight to voicemail, while the 2 utilizing automated WhatsApp capture booked 7 new patient exams before Monday morning.\n\nWould you like me to send over the live smartphone self-booking preview link?"
            wa = f"Hi {salutation}, checking in! We tested 14 dental clinics in {city} last Sunday—clinics with automated WhatsApp triage secured 7 new patient exams before 8 AM Monday. Would love to send you a 1-min video test link."
            call_hook = f"Hi {salutation}, following up on the local {city} response study we sent over. Practices deploying automated intake are securing 3-5 extra new patient bookings every weekend. Wanted to see if you reviewed the data?"
            delay_days = 3
            angle_name = "Local Peer Comparison & Sunday Benchmark"
            stage_label = "Touch 2 (Peer Benchmark / Study)"

        elif touch_number == 3:
            # Touch 3 (Day 7): Zero-Disruption PMS Integration
            subject = f"PMS integration question for {name}"
            email = f"Hi {salutation},\n\nOne question practice managers frequently ask us is whether our after-hours assistant interferes with current front desk routines.\n\nThe system integrates directly into your PMS (Dentrix, Open Dental, Eaglesoft, Curve) and only activates after hours when your receptionist is home. Zero workflow change for your daytime staff.\n\nCould I send a quick 90-second integration breakdown for {name}?"
            wa = f"Hi {salutation}! Quick technical note: our 24/7 patient assistant connects natively with your PMS calendar so daytime staff routines don't change at all. Happy to send a 60-second video of how appointments appear on your schedule."
            call_hook = f"Hi {salutation}, calling regarding software integration at {name}. Our system operates completely behind the scenes after hours and drops confirmed bookings right into your calendar. Are you using Open Dental or Dentrix?"
            delay_days = 7
            angle_name = "PMS Integration & Zero Daytime Disruption"
            stage_label = "Touch 3 (PMS Integration / Front Desk)"

        else:
            # Touch 4 (Day 14): 14-Day Risk-Free Pilot / Breakup
            subject = f"14-Day Risk-Free Patient Capture Pilot for {name}"
            email = f"Hi {salutation},\n\nI realize you are focused on clinical chair time and patient care. To make this completely risk-free, we offer a 14-day patient capture pilot: if we don't recover at least 3 confirmed patient appointments for {name} in two weeks, you pay nothing.\n\nIf you'd like to test this before we open the territory exclusivity in {city}, let me know."
            wa = f"Hi {salutation}, last note from me! We offer a 14-day zero-risk patient intake test for {name}—if we don't book at least 3 patient exams in two weeks, it costs $0. Open to trying it before we lock territory exclusivity in {city}?"
            call_hook = f"Hi {salutation}, final follow-up from my end regarding our 14-day patient capture pilot. We guarantee 3 booked patients or zero charge. Is this something you'd like to test this month?"
            delay_days = 14
            angle_name = "14-Day Risk-Free Pilot & Exclusivity"
            stage_label = "Touch 4 (14-Day Risk-Free Pilot)"

        from urllib.parse import quote
        wa_url = f"https://wa.me/{clean_phone}?text={quote(wa)}" if clean_phone else "#"

        return {
            "lead_id": lead_dict.get("id"),
            "touch_number": touch_number,
            "angle_name": angle_name,
            "stage": stage_label,
            "subject": subject,
            "body": email,
            "channels": ["Email", "WhatsApp", "Phone Call"],
            "recommended_delay_days": delay_days,
            "email": {
                "subject": subject,
                "body": email
            },
            "whatsapp": {
                "text": wa,
                "url": wa_url
            },
            "call_script": {
                "opening_hook": call_hook,
                "objective": "Secure 10-minute diagnostic review"
            }
        }
