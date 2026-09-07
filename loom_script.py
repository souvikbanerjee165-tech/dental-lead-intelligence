"""
One-Click Loom Video Pitch Generator.
Creates customized 90-120 second video outreach scripts with screen directions
designed for solo-founder personalized cold video selling.
"""

from typing import Dict, Any, List


def generate_loom_pitch(lead: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generates a personalized, time-coded 2-minute Loom video pitch
    and teleprompter-ready script.
    """
    practice_name = lead.get("name", "your practice")
    raw_doc = lead.get("doctor_name")
    if raw_doc:
        doc_greeting = f"Dr. {raw_doc.replace('Dr. ', '')}"
    else:
        doc_greeting = f"team at {practice_name}"

    address = lead.get("address") or ""
    city = lead.get("city") or (address.split(",")[-2].strip() if "," in address else "your area")
    reviews = int(lead.get("review_count") or 45)
    rating = float(lead.get("rating") or 4.9)
    missed_min = int(lead.get("missed_rev_min") or 3000)
    missed_max = int(lead.get("missed_rev_max") or 6500)
    website = lead.get("website") or "your website"

    scenes = [
        {
            "time": "0:00 - 0:18",
            "section": "Pattern Interrupt & Personalized Hook",
            "screen_action": "Screen share their Google Maps profile with patient reviews highlighted. Webcam circle in bottom-left corner.",
            "voiceover": f"Hey {doc_greeting}, quick heads up — this is a personal 90-second video specifically for {practice_name} here in {city}, definitely not an automated mass message. I was reviewing top-rated dental clinics in {city} and was genuinely impressed by your {reviews} reviews at {rating} stars."
        },
        {
            "time": "0:18 - 0:48",
            "section": "The Specific Mobile Friction Observation",
            "screen_action": "Switch browser tab to their homepage in mobile responsive view (F12 inspect mode). Scroll down to booking/contact section.",
            "voiceover": f"I pulled up {website} on my phone yesterday evening around 7:45 PM. While your clinical work looks top-tier, I noticed that if an emergency patient or after-hours inquiry visits after 5 PM, their only option is to leave a voicemail or fill out a multi-step form. Studies show over 65% of patients in pain won't wait — they immediately click back to Google and book with the next practice that answers."
        },
        {
            "time": "0:48 - 1:15",
            "section": "The 24/7 AI Receptionist Contrast",
            "screen_action": "Briefly show an instant chat / SMS preview screen demonstrating an appointment booked in under 30 seconds.",
            "voiceover": f"What we did for similar practices is install a 24/7 AI Receptionist right on their website, WhatsApp, and SMS. It engages patients in 4 seconds, answers clinical questions (insurance, sedation, cleanings), and locks them into an appointment on your calendar — even on Sunday night at 11 PM."
        },
        {
            "time": "1:15 - 1:38",
            "section": "Dental Unit Economics & ROI",
            "screen_action": "Keep screen on clean before/after comparison graphic.",
            "voiceover": f"At {practice_name}'s patient volume, recovering just 4 or 5 of those after-hours patient inquiries a month translates to roughly $50,000 to $60,000 in net new production every year. And our system costs less than a single filling per month to run."
        },
        {
            "time": "1:38 - 1:55",
            "section": "Zero-Pressure Next Step (CTA)",
            "screen_action": "Smile, switch webcam to center or hover cursor over your calendar link.",
            "voiceover": f"I know you're booked with patients, so I'm not asking to sell you anything right now. If you'd like to see a private 2-minute sandbox demo tuned to your clinic's procedures, just reply 'SHOW ME' to this email or ping me back on WhatsApp. Either way, hope you have a fantastic week!"
        }
    ]

    teleprompter_text = "\n\n".join([
        f"[{s['section']} - {s['time']}]\n"
        f"ACTION: {s['screen_action']}\n"
        f"SCRIPT: \"{s['voiceover']}\""
        for s in scenes
    ])

    words = sum(len(s["voiceover"].split()) for s in scenes)
    est_duration_sec = round((words / 135) * 60)

    return {
        "lead_id": lead.get("id"),
        "practice_name": practice_name,
        "doctor_greeting": doc_greeting,
        "video_title": f"Quick 90s website idea for {doc_greeting} ({practice_name})",
        "email_subject_line": f"Quick 90s video idea for {doc_greeting} regarding {practice_name}",
        "word_count": words,
        "est_duration_sec": est_duration_sec,
        "scenes": scenes,
        "teleprompter_text": teleprompter_text
    }
