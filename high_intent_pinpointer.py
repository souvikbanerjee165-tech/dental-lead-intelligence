"""
High-Intent Dentist Pinpointer & Ready-to-Close Sales Command Engine.
Specifically engineered for selling the 24/7 AI Front Desk (Missed-Call Revenue Recovery Agent)
to US & Canadian independent dental practices at $1,200 installation + $497/month.
"""

import re
import json
import urllib.parse
from datetime import datetime
from typing import Dict, Any, List, Optional

from database import DatabaseManager
from google_places_client import GooglePlacesClient


class HighIntentPinpointer:
    """
    Identifies highest-intent independent dental practices and compiles the complete
    1-Screen 'Call & Close' dossier ($1,200 setup + $497/mo offer).
    """

    SETUP_FEE_USD = 1200.0
    MONTHLY_RETAINER_USD = 497.0
    DEFAULT_PATIENT_VALUE_USD = 1200.0

    @classmethod
    def score_and_compile(
        cls,
        lead_dict: Dict[str, Any],
        db: Optional[DatabaseManager] = None,
        base_app_url: str = "http://127.0.0.1:8000"
    ) -> Dict[str, Any]:
        """
        Evaluates 7 empirical missed-call vulnerability signals and generates
        the complete word-for-word closing playbook for a dental practice.
        """
        lead = lead_dict or {}
        lead_id = lead.get("id") or "preview"
        clinic_name = lead.get("name") or "Dental Practice"
        raw_phone = lead.get("phone") or ""
        website = lead.get("website") or ""
        address = lead.get("address") or "Austin, TX"
        rating = float(lead.get("rating") or 4.6)
        reviews = int(lead.get("review_count") or 55)
        raw_doc = lead.get("doctor_name") or ""
        detected_ehr = lead.get("detected_ehr") or "Dentrix / Open Dental"
        npi_number = lead.get("npi_number") or ""

        # Parse city & state/province (US & Canada)
        city = "your area"
        region = ""
        if address and "," in address:
            parts = [p.strip() for p in address.split(",") if p.strip()]
            if len(parts) >= 2:
                city = parts[-2]
                region_tokens = parts[-1].split()
                if region_tokens:
                    region = region_tokens[0].upper()

        is_canada = any(
            prov in f" {region} " or prov in address.upper()
            for prov in (" ON ", " BC ", " AB ", " QC ", " MB ", " SK ", " NS ", "CANADA", "ONTARIO", "TORONTO", "VANCOUVER", "CALGARY")
        )
        currency_label = "USD" if not is_canada else "USD (North America Standard)"

        # Clean Doctor Name
        has_verified_doctor = False
        doc_last_name = ""
        doc_display = "Doctor"
        if raw_doc and raw_doc.strip().lower() not in ("", "doctor", "not identified", "unknown", "none", "practice principal"):
            has_verified_doctor = True
            clean_doc = re.sub(r"^(Dr\.?|Doctor)\s*", "", raw_doc, flags=re.IGNORECASE).strip()
            clean_doc_no_cred = re.sub(r",?\s*\b(DDS|DMD|BDS|MS|PC|FAGD|MAGD)\b.*", "", clean_doc, flags=re.IGNORECASE).strip()
            tokens = clean_doc_no_cred.split()
            doc_last_name = tokens[-1] if tokens else clean_doc_no_cred
            doc_display = f"Dr. {clean_doc_no_cred}"
        else:
            doc_display = f"the Owner Dentist at {clinic_name}"
            doc_last_name = "Doctor"

        # Check Corporate DSO status
        is_dso = bool(lead.get("is_dso")) or GooglePlacesClient.is_corporate_dso(clinic_name, website)

        # Tech & Intake Signals
        has_chatbot = bool(lead.get("has_ai_chatbot") or lead.get("has_chatbot"))
        has_booking = bool(lead.get("has_online_booking"))
        has_whatsapp = bool(lead.get("has_whatsapp"))
        closed_hours_wk = int(lead.get("weekly_closed_hours") or 130)

        # High-ticket procedure detection
        cat_and_notes = f"{lead.get('category') or ''} {lead.get('notes') or ''} {clinic_name}".lower()
        is_high_ticket = any(
            kw in cat_and_notes
            for kw in ("implant", "cosmetic", "ortho", "invisalign", "surgery", "emergency", "sedation", "prostho", "smile", "studio")
        )
        avg_case_val = 1650.0 if is_high_ticket else cls.DEFAULT_PATIENT_VALUE_USD

        # -------------------------------------------------------------------------
        # 7-Factor High-Intent Scoring Model (0 - 100) for AI Front Desk
        # -------------------------------------------------------------------------
        intent_score = 35
        why_buys: List[str] = []
        vulnerability_breakdown: List[Dict[str, Any]] = []

        # Factor 1: Sweet-Spot Inbound Call Volume (Google Reviews 35 - 400)
        if 40 <= reviews <= 450:
            intent_score += 20
            why_buys.append(
                f"Active inbound call volume ({reviews} Google reviews at {rating}★) overwhelms a 1-2 person front desk during peak clinic hours."
            )
            vulnerability_breakdown.append({"signal": "High Call Volume vs. Front-Desk Capacity", "points": "+20", "status": "CRITICAL_FIT"})
        elif reviews > 450:
            intent_score += 12
            why_buys.append(f"High-traffic practice ({reviews} reviews) leaking overflow daytime & evening calls.")
            vulnerability_breakdown.append({"signal": "High Inbound Patient Traffic", "points": "+12", "status": "STRONG_FIT"})
        elif 15 <= reviews < 40:
            intent_score += 10
            vulnerability_breakdown.append({"signal": "Growing Practice Call Volume", "points": "+10", "status": "MODERATE_FIT"})
        else:
            intent_score -= 15
            vulnerability_breakdown.append({"signal": "Low Review Volume (<15 reviews)", "points": "-15", "status": "LOW_FIT"})

        # Factor 2: Zero 24/7 AI Front Desk / Instant Missed-Call Textback
        if not has_chatbot and not has_whatsapp:
            intent_score += 20
            why_buys.append(
                "Zero 24/7 AI Front Desk or instant missed-call textback—100% of unanswered calls roll to voicemail where 67% of patients hang up."
            )
            vulnerability_breakdown.append({"signal": "No 24/7 AI Receptionist or Missed-Call Recovery", "points": "+20", "status": "CRITICAL_FIT"})
        elif not has_whatsapp:
            intent_score += 10
            vulnerability_breakdown.append({"signal": "Browser Widget Only (No Instant SMS/WhatsApp Recovery)", "points": "+10", "status": "STRONG_FIT"})

        # Factor 3: After-Hours & Weekend Voicemail Window
        unattended_pct = round((closed_hours_wk / 168.0) * 100)
        intent_score += 12
        why_buys.append(
            f"Phones are unattended ~{closed_hours_wk} hrs/week ({unattended_pct}% of the week—evenings, Fridays & weekends) when emergency toothaches strike."
        )
        vulnerability_breakdown.append({"signal": f"{closed_hours_wk} Hrs/Week Unattended Voicemail Window", "points": "+12", "status": "CRITICAL_FIT"})

        # Factor 4: Single Decision-Maker / Independent Owner Accessibility
        if is_dso:
            intent_score = min(25, intent_score - 50)
            why_buys = ["Corporate DSO chain—software decisions locked at national HQ. Skip calling."]
            vulnerability_breakdown.append({"signal": "Corporate DSO Chain Detected", "points": "-50", "status": "DISQUALIFIED"})
        elif has_verified_doctor:
            intent_score += 14
            why_buys.insert(
                0,
                f"Verified independent owner-dentist ({doc_display}{' • NPI #' + str(npi_number) if npi_number else ''}) with direct authority to approve $1,200 + $497/mo."
            )
            vulnerability_breakdown.append({"signal": f"Direct Owner Identified ({doc_display})", "points": "+14", "status": "CRITICAL_FIT"})
        else:
            intent_score += 5

        # Factor 5: High-Ticket Procedure Economics
        if is_high_ticket:
            intent_score += 9
            why_buys.append(
                f"High-ticket clinical mix (${avg_case_val:,.0f}+ avg case)—recovering just 1 missed patient pays for the entire $1,200 setup on Day 1."
            )
            vulnerability_breakdown.append({"signal": "High-Ticket Restorative/Implant Mix", "points": "+9", "status": "STRONG_FIT"})

        # Factor 6: Telephone-Only Scheduling Friction
        if not has_booking:
            intent_score += 7
            vulnerability_breakdown.append({"signal": "No Direct Online Self-Scheduling", "points": "+7", "status": "STRONG_FIT"})

        # Factor 7: Direct Valid Phone Number
        if raw_phone and len(re.sub(r"\D", "", raw_phone)) >= 10:
            intent_score += 5
        else:
            intent_score -= 30

        intent_score = max(10, min(99, intent_score))

        if is_dso or intent_score < 50:
            intent_grade = "C_SKIP"
            intent_badge = "🛑 SKIP (LOW FIT / DSO)"
        elif intent_score >= 85:
            intent_grade = "A_PLUS_PRIME"
            intent_badge = f"🔥 {intent_score}% PRIME BUYER — CALL NOW"
        elif intent_score >= 72:
            intent_grade = "A_HIGH_INTENT"
            intent_badge = f"✅ {intent_score}% HIGH-INTENT DENTIST"
        else:
            intent_grade = "B_WARM"
            intent_badge = f"⚡ {intent_score}% QUALIFIED PROSPECT"

        # -------------------------------------------------------------------------
        # Exact Missed-Call Unit Economics ($1,200 Setup + $497/Mo)
        # -------------------------------------------------------------------------
        est_missed_calls_mo = max(8, min(38, int(round(reviews * 0.14)) if reviews >= 30 else 10))
        est_recaptured_patients_mo = max(3, int(round(est_missed_calls_mo * 0.35)))
        monthly_leaked_usd = int(est_missed_calls_mo * avg_case_val)
        annual_leaked_usd = monthly_leaked_usd * 12
        monthly_recovered_usd = int(est_recaptured_patients_mo * avg_case_val)
        annual_recovered_usd = monthly_recovered_usd * 12
        year1_investment_usd = int(cls.SETUP_FEE_USD + (cls.MONTHLY_RETAINER_USD * 12))  # $1,200 + $5,964 = $7,164
        year1_roi_multiple = round(annual_recovered_usd / max(1.0, year1_investment_usd), 1)

        # -------------------------------------------------------------------------
        # Ready-to-Close Call Script & Objection Playbook
        # -------------------------------------------------------------------------
        doc_salutation = f"Dr. {doc_last_name}" if has_verified_doctor else "Doctor"
        pitch_url = f"{base_app_url.rstrip('/')}/pitch/{lead_id}"

        gatekeeper_bypass = (
            f"“Hi there! Quick question for you—I just ran an after-hours missed-call audit for {clinic_name} "
            f"showing what happens when patients call after 5 PM or while you're busy checking in patients at the front desk. "
            f"I prepared a 1-page revenue recovery report for {doc_salutation}. Is {doc_salutation} free for 60 seconds between patients, "
            f"or are you the Office Manager who oversees the phone system?”"
        )

        doctor_opener_20s = (
            f"“{doc_salutation}, I'll be super brief—you've built an amazing {rating}★ reputation with {reviews} reviews here in {city}, "
            f"which drives strong new-patient call volume. But when we audited {clinic_name}, we found that callers after 5 PM, on weekends, "
            f"or during peak morning check-in roll to voicemail. American Dental Association data shows 67% of patients in pain hang up on voicemail "
            f"and immediately call the next dentist on Google. We deploy a 24/7 AI Front Desk that catches 100% of your missed calls within 3 seconds, "
            f"answers patient questions, verifies insurance, and books them straight onto your schedule.”"
        )

        irresistible_offer_pitch = (
            f"“Based on your review volume in {city}, missing just {est_missed_calls_mo} calls a month is costing roughly ${monthly_leaked_usd:,}/month "
            f"in uncaptured production. Our turnkey installation is a one-time $1,200 setup and $497/month to run—which is 1/8th the cost of a human receptionist "
            f"and works 24/7/365. Even better: we back it with a Single-Patient 30-Day Refund Guarantee and 3-Mile Territory Exclusivity. "
            f"If it doesn't recover at least ONE new patient worth $1,200+ in your first 30 days, we refund your $1,200 setup in full.”"
        )

        objection_rebuttals = [
            {
                "objection": "“My front desk girls already answer all our calls.”",
                "rebuttal": (
                    f"“Your daytime team is fantastic, {doc_salutation}—we never replace them! The problem isn't when they're free; "
                    f"it's the 130 hours a week your clinic is closed in the evenings and weekends, plus the 10 minutes they're busy checking out a patient "
                    f"or verifying insurance when Line 2 rings. We only catch the overflow and after-hours calls that would have gone to voicemail.”"
                )
            },
            {
                "objection": "“We have voicemail / an answering service.”",
                "rebuttal": (
                    "“When a patient cracks a molar at 7:30 PM or is shopping for implants on Sunday, they don't leave voicemails—and human answering services "
                    "only take a name and number without booking the chair. Our AI Front Desk texts and talks to them in 3 seconds, qualifies their dental need, "
                    "and locks the appointment before they can call a competitor down the street.”"
                )
            },
            {
                "objection": "“We already use Weave / NexHealth / Podium.”",
                "rebuttal": (
                    f"“Those are great daytime tools, {doc_salutation}, and we coexist right alongside {detected_ehr} and your current phones! "
                    "The difference is static web forms and generic missed-call texts still require a human to text back. Our AI Front Desk actually conducts "
                    "the full 2-way clinical triage at 10 PM on Sunday and hands your front desk a confirmed patient on Monday morning.”"
                )
            },
            {
                "objection": "“$1,200 setup and $497/mo is another expense / send me an email.”",
                "rebuttal": (
                    f"“I totally respect that—and I can text your custom {clinic_name} audit link to your mobile right now while we're on the line. "
                    "Remember, 1 single crown, root canal, or emergency patient is worth $1,200+. Capturing just ONE caller who would have hung up on voicemail "
                    "pays for the entire $1,200 installation, and 1 patient every 2 months covers the $497/mo retainer. What's the best mobile number to text your live demo link?”"
                )
            },
            {
                "objection": "“I need to talk to my partner / office manager first.”",
                "rebuttal": (
                    f"“Completely understand, {doc_salutation}—practice decisions like this should involve your key team members! "
                    f"We prepared a 1-page executive teardown and interactive prototype specifically for practice partners and office managers. "
                    f"What's your office manager's name and mobile number? I'll text it over so both of you can review the missed-call leakage together, "
                    f"and we can do a quick 10-minute walkthrough this Thursday.”"
                )
            }
        ]

        closing_ask = (
            f"“{doc_salutation}, I have your custom {clinic_name} AI Front Desk prototype ready on my screen right now. "
            f"Can I text you the 30-second live test link so you can see how it responds to a missed call on your own phone, "
            f"or do you have 10 minutes this Thursday at 12:30 PM to lock your 3-mile territory in {city}?”"
        )

        live_sms_text = (
            f"Hi {doc_salutation}, here is the confidential Missed-Call Revenue Recovery audit & live AI Front Desk simulator "
            f"we prepared for {clinic_name} (${monthly_leaked_usd:,}/mo estimated after-hours leakage): {pitch_url}"
        )

        digits = re.sub(r"\D", "", raw_phone)
        if len(digits) == 10:
            digits = "1" + digits
        wa_url = f"https://wa.me/{digits}?text={urllib.parse.quote(live_sms_text)}" if digits else ""

        return {
            "lead_id": lead_id,
            "clinic_name": clinic_name,
            "doctor_display": doc_display,
            "doctor_salutation": doc_salutation,
            "has_verified_doctor": has_verified_doctor,
            "phone": raw_phone,
            "website": website,
            "city": city,
            "region": region,
            "is_canada": is_canada,
            "currency_label": currency_label,
            "rating": rating,
            "review_count": reviews,
            "detected_ehr": detected_ehr,
            "npi_number": npi_number,
            "is_dso": is_dso,
            "high_intent_score": intent_score,
            "intent_grade": intent_grade,
            "intent_badge": intent_badge,
            "why_this_dentist_buys": why_buys[:4],
            "vulnerability_breakdown": vulnerability_breakdown,
            "unit_economics": {
                "setup_fee_usd": int(cls.SETUP_FEE_USD),
                "monthly_retainer_usd": int(cls.MONTHLY_RETAINER_USD),
                "avg_case_value_usd": int(avg_case_val),
                "estimated_missed_calls_monthly": est_missed_calls_mo,
                "estimated_recaptured_patients_monthly": est_recaptured_patients_mo,
                "monthly_leaked_revenue_usd": monthly_leaked_usd,
                "annual_leaked_revenue_usd": annual_leaked_usd,
                "monthly_recovered_revenue_usd": monthly_recovered_usd,
                "annual_recovered_revenue_usd": annual_recovered_usd,
                "year1_total_investment_usd": year1_investment_usd,
                "year1_roi_multiple": f"{year1_roi_multiple}x",
                "break_even_summary": (
                    f"1 recovered patient (${int(avg_case_val):,}) pays off the entire $1,200 setup fee immediately. "
                    f"Recovering {est_recaptured_patients_mo} patients/mo generates +${monthly_recovered_usd:,}/mo against a $497/mo retainer ({year1_roi_multiple}x annual ROI)."
                )
            },
            "call_playbook": {
                "step1_gatekeeper_bypass": gatekeeper_bypass,
                "step2_doctor_opener_20s": doctor_opener_20s,
                "step3_irresistible_offer_pitch": irresistible_offer_pitch,
                "step4_objection_rebuttals": objection_rebuttals,
                "step5_closing_ask": closing_ask,
                "live_call_sms_text": live_sms_text,
                "whatsapp_one_click_url": wa_url,
                "pitch_portal_url": pitch_url
            },
            "generated_at": datetime.now().isoformat()
        }
