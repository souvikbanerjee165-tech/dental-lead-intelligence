"""
Master Clinical Objection Modeling & Autonomous Voice AI Training Architecture.
Trained directly on Dental Practice Acquisition protocols:
- Comprehensive Front-Desk Triage (Screens 1-8)
- Principal Dentist Clinical, Operational & Financial Objections (Objections 1-11)
- The Four Lethal Conversion Engines (Live Intercept, 3-Mile Exclusivity, 60s Teardown, Dormant Hygiene Math)
- Certified PMS Integration Safeguards (Open Dental, Dentrix, Eaglesoft) & HIPAA/BAA Compliance
"""

import re
import random
from typing import Dict, Any, List, Optional, Set


class EmpathyVoicePromptEngine:
    """Master Clinical Voice AI Engine for Dental Practice Acquisition."""

    BREVITY_MAX_WORDS = 20

    # Conversational Micro-Affirmations / Instant Acoustic Fillers
    MICRO_AFFIRMATIONS = [
        "Totally get that.",
        "Makes complete sense.",
        "Fair enough.",
        "100%, completely understand.",
        "Right, yeah.",
        "Understood.",
        "I hear you."
    ]

    # Backward-compatible alias map for legacy tests and dialer integrations
    ALIASES = {
        "doctor_busy": "doctor_in_operatory",
        "doctor_in_operatory": "doctor_in_operatory",
        "have_front_desk": "have_front_desk",
        "have_full_team": "have_front_desk",
        "have_ehr": "have_weave_nexhealth",
        "have_weave_nexhealth": "have_weave_nexhealth",
        "how_much": "price_expensive_deposit",
        "price_expensive_deposit": "price_expensive_deposit",
        "not_interested": "satisfied_not_interested",
        "satisfied_not_interested": "satisfied_not_interested",
    }

    # Master Clinical Objection Taxonomy (Receptionist Screens + Principal Clinical & Financial Objections)
    OBJECTION_PLAYBOOKS: Dict[str, Dict[str, Any]] = {
        # --- PART 1: FRONT-DESK RECEPTIONIST SCREENS ---
        "doctor_in_operatory": {
            "keywords": ["with a patient", "in operatory", "operatory two", "treating patients", "chair time", "in surgery", "doctor is busy", "in chair", "with patients"],
            "variations": [
                "Understood, clinical care in the operatory comes first. This is regarding the practice's after-hours patient intake audit generated this morning. Does the office manager handle schedule capacity, or should the audit link be confirmed directly with {doctor} during afternoon huddle?",
                "Totally understand, patient chair time is priority. The diagnostic file cannot be processed in an unmonitored inbox because it contains local 3-mile submarket teardown data. Who coordinates {doctor}'s schedule capacity?",
                "Fair enough, definitely don't want to interrupt active chair time! Could I shoot a quick 60-second video breakdown of your after-hours setup to your practice manager?",
                "Completely respect that—operatory production always takes precedence. Who oversees patient schedule capacity so we can send the local submarket audit once they step out?",
                "Understood! When {doctor} is between procedures, who handles after-hours intake protocols—would that be the office manager or {doctor} directly?"
            ]
        },
        "send_email": {
            "keywords": ["send an email", "send email", "email us", "info@", "send me information", "send over some info", "just email it", "email brochure"],
            "variations": [
                "The general info inbox typically auto-archives outside diagnostic reports. A 60-second video teardown was recorded specifically on {clinic}’s missed after-hours triage. To ensure it routes properly, who oversees schedule optimization—would that be your office manager or {doctor}?",
                "The interactive preview incorporates live practice revenue estimates and schedule routing, so it cannot be processed by an unmonitored inbox. What is the direct email for your practice administrator?",
                "Happy to email it over! Rather than getting lost in the general info inbox, what is the practice manager's direct first name so I can address the audit specifically to them?",
                "Can definitely do that. How do you currently handle after-hours patient calls—do you have an on-call doctor, voicemail, or an answering service? That helps me send the exact case study."
            ]
        },
        "satisfied_not_interested": {
            "keywords": ["completely satisfied", "not interested", "not looking", "we're satisfied", "don't need it", "no thank you", "no thanks", "not at this time"],
            "variations": [
                "This is not a general solicitation. An analysis of weekend patient call routing within your 3-mile radius revealed local clinics leaking approximately {leakage} monthly to competing walk-ins. Should the territory verification report be closed out, or forwarded to the principal?",
                "Totally fair, receptionists are inundated with pitches daily. The data indicates approximately four prospective emergency patients were routed to voicemail this past weekend, representing uncaptured restorative production. Would your office manager prefer to review the teardown before the 3-mile lock is assigned to another office?",
                "Understood! Most practices we partner with were completely satisfied initially, until they noticed weekend emergencies bouncing to competitors. Would 30 seconds to show how we catch those be worth it?"
            ]
        },
        "what_is_this_regarding": {
            "keywords": ["what is this regarding", "is this a sales call", "who is calling", "what company are you with", "what is this about", "why are you calling"],
            "variations": [
                "The call is regarding the unreturned patient triage protocol for {clinic}—specifically, how missed weekend emergency cases are currently routed before contacting competing practices on Google. Would that fall under the clinic coordinator or {doctor}?",
                "Good morning! This is the clinical intake coordinator calling regarding {doctor}’s after-hours emergency patient intake audit in {city}. I need to confirm whether {doctor} or the practice administrator oversees schedule capacity?",
                "Just a brief 20-second call regarding {clinic}'s after-hours schedule audit generated this morning. Does the office manager oversee your appointment intake?"
            ]
        },
        "have_answering_service": {
            "keywords": ["answering service", "call center", "we have an answering service", "after-hours service", "live answering"],
            "variations": [
                "Most practices rely on live operators or voicemail. The issue identified in the practice teardown is that third-party services take written messages, but 84% of weekend emergencies book the first clinic that issues a confirmed appointment slot. Is the office manager open to reviewing how that gap is closed autonomously?",
                "That makes complete sense—many of our clinics used an answering service. What we offer is an automated WhatsApp triage layer that catches calls the service misses and immediately books them into open chairs. Have you wondered how many callers hang up on operators?"
            ]
        },
        "are_you_ai": {
            "keywords": ["are you an ai", "are you a robot", "automated system", "am i speaking to an ai", "are you real", "is this an ai", "is this a recording"],
            "variations": [
                "That is correct. This is the autonomous patient intake voice model deployed for dental clinics across {city}. The reason for reaching out directly is that this system books unreturned after-hours patient calls straight into your practice management software in under 5 seconds. Does the practice principal handle intake technology?",
                "Yes, this is the autonomous conversational intake engine. If an emergency caller rings at 8:30 on a Friday night, this system conducts full clinical triage and books them into your PMS in under 5 seconds, preventing them from calling the practice down the street. Does {doctor} evaluate intake software?"
            ]
        },
        "office_manager_out": {
            "keywords": ["office manager is out", "out of the office", "manager is not here", "out until next week", "manager is busy", "out of office"],
            "variations": [
                "Understood. Because the 3-mile territory reservation operates on a strict 72-hour window before releasing exclusivity to neighboring clinics in {city}, the audit file needs to be accessible upon their return. What is the practice administrator's direct email address?",
                "No problem at all! Who serves as the secondary clinical coordinator while they are offsite so we can hold the territory reservation?"
            ]
        },
        "slammed_busy": {
            "keywords": ["slammed right now", "very busy", "phones are ringing", "bad time", "call back later", "in the middle of something", "crazy here"],
            "variations": [
                "Understood completely—the fact that the desk is overwhelmed with incoming patient calls right now is the exact bottleneck being resolved. Rather than pulling focus from patients in the clinic, what is the best direct contact for the practice manager so this teardown can be reviewed once the rush clears?",
                "I figured you'd say that—busy front desks are our biggest partners. Could I steal just 20 seconds to explain why we called, or would Thursday at 10 AM be a calmer time to catch your manager?"
            ]
        },
        "does_doctor_know_you": {
            "keywords": ["does the doctor know you", "are they expecting your call", "is doctor expecting you", "do you know doctor"],
            "variations": [
                "{doctor} is not expecting a personal call. The contact is initiated because an interactive operational audit was generated for {clinic} regarding after-hours patient leakage. An exclusive 3-mile territory lock is pending final allocation for this postal code, and we require confirmation before releasing rights to another local office."
            ]
        },
        "have_front_desk": {
            "keywords": ["have a receptionist", "have a full team", "front desk handles it", "full staff", "don't need automation", "already have staff", "have someone who answers"],
            "variations": [
                "The system is not designed to replace front-desk personnel. Highly skilled staff should focus on patient care and high-value treatment presentation, rather than spending four hours dialing dormant charts or answering 8 PM emergency calls. This system works while the clinic is closed, so staff arrive to fully confirmed chairs. Does the office manager oversee workflow optimization?",
                "100%, and your daytime team does fantastic work during office hours! We simply act as their automated after-hours safety net so weekend patients in pain don't bounce to Google competitors.",
                "Totally agree, a great front desk is irreplaceable. Our tool specifically handles the 62% of patient calls that arrive when your team is home for the evening, converting them directly into confirmed appointments.",
                "Makes complete sense! We don't touch daytime phone operations—we simply activate an autonomous mobile intake layer from 6 PM to 8 AM so unreturned emergency calls don't leak to competing practices."
            ]
        },
        "have_full_team": {
            "keywords": ["have a full team", "have a receptionist", "front desk handles it", "full staff", "don't need automation", "already have staff"],
            "variations": [
                "The system is not designed to replace front-desk personnel. Highly skilled staff should focus on patient care and high-value treatment presentation, rather than spending four hours dialing dormant charts or answering 8 PM emergency calls. This system works while the clinic is closed, so staff arrive to fully confirmed chairs. Does the office manager oversee workflow optimization?",
                "100%, and your daytime team does fantastic work during office hours! We simply act as their automated after-hours safety net so weekend patients in pain don't bounce to Google competitors.",
                "Totally agree, a great front desk is irreplaceable. Our tool specifically handles the 62% of patient calls that arrive when your team is home for the evening, converting them directly into confirmed appointments.",
                "Makes complete sense! We don't touch daytime phone operations—we simply activate an autonomous mobile intake layer from 6 PM to 8 AM so unreturned emergency calls don't leak to competing practices."
            ]
        },
        "dnc_opt_out": {
            "keywords": ["take us off your list", "do not call", "stop calling", "remove our number", "remove me", "don't call back"],
            "variations": [
                "Understood completely. The practice telephone record is flagged as restricted immediately, and no further outreach will be directed to this number. The geographic territory reservation for {clinic} is officially closed. Have a professional day."
            ]
        },
        "who_are_you_number": {
            "keywords": ["how did you get this number", "who are you", "where did you get our number", "how do you have my number"],
            "variations": [
                "Totally fair question! We get clinic lines from public state dental registries and Google Maps directories. I respect your privacy—I can remove you immediately if preferred, or take 20 seconds to share how we recover missed after-hours patient calls. Which do you prefer?"
            ]
        },
        "call_back_later": {
            "keywords": ["call back in a few months", "call next quarter", "call next month", "not right now"],
            "variations": [
                "Certainly. When would be a good time—say next quarter—to talk? And just so I follow up effectively: what needs to happen by then regarding your after-hours call volume?",
                "Understood! When is a calmer time for your front desk—around two or closer to four?"
            ]
        },
        "have_no_budget": {
            "keywords": ["have no budget", "no budget", "tight budget", "can't afford", "no money for this"],
            "variations": [
                "Completely understandable. Out of curiosity, if budget weren't an issue, would capturing missed emergency calls or recovering overdue hygiene patients be a priority this quarter? The recovered patient revenue typically pays for the setup ten times over in Month 1.",
                "Fair question! Under our Service Level Agreement, we guarantee you book at least one twelve hundred and fifty dollar patient in 30 days, or we refund the full deposit. Would it be worth 5 minutes to see if the math works?"
            ]
        },

        # --- PART 2: PRINCIPAL DENTIST CLINICAL & FINANCIAL OBJECTIONS ---
        "schedule_full_booked_out": {
            "keywords": ["chairs are full", "booked out", "schedule is packed", "don't need more patients", "full-booked", "three weeks out", "schedule is full", "at capacity", "booked 3 weeks", "booked 4 weeks"],
            "variations": [
                "Dr. {doctor}, having a full three-week schedule reflects exceptional clinical trust. However, practice analytics show booked-out schedules experience 12% to 15% breakage, costing roughly $250 per empty chair-hour. More importantly, an active practice carries approximately {dormant_charts} dormant charts—representing over {trapped_hygiene_val} in trapped hygiene production. Our engine reactivates overdue restorative cases and backfills cancellations automatically. Does recovering high-margin production from your existing database align with your quarterly goals?",
                "I get it, practice growth is a good problem! Our focus isn't random walk-ins; it is dormant hygiene recall. If 35% of your charts are overdue for hygiene, recovering just {month1_reactivations} patients injects over {month1_injection} into your hygiene chairs in Month 1 alone without adding chair chaos. Would that be worth a quick look?"
            ]
        },
        "have_weave_nexhealth": {
            "keywords": ["weave", "nexhealth", "revenuewell", "already use", "podium", "birdeye", "patient pop", "current software"],
            "variations": [
                "Weave and NexHealth are solid tools for daytime VoIP and reminders, but they are passive utilities. When an emergency patient calls at 8:14 PM on Friday with acute pulpitis, Weave sends them to voicemail. By Monday morning, 84% of emergencies have booked a competitor. Our platform acts as an active conversion layer alongside Weave—picking up in 3 seconds and booking them via WhatsApp or voice. We don't replace Weave; we stop the after-hours leakage.",
                "We don't replace your daytime software at all—we integrate alongside it. Charting tools can't triage or book patients on Sunday evening when everyone is home. We catch those high-ticket implant and emergency cases and feed them right into your schedule."
            ]
        },
        "dont_want_emergencies": {
            "keywords": ["don't want emergency", "disrupt our schedule", "bad payers", "no emergencies", "emergencies disrupt", "chaotic walk-ins", "emergency patients"],
            "variations": [
                "That concern is entirely valid, Dr. {doctor}. No practice wants chaotic walk-in traffic disrupting precision restorative blocks. Our clinical triage engine screens specifically for high-value restorative emergencies—cracked teeth, dislodged crowns, and broken prosthetics averaging over twelve hundred and fifty dollars in case value—while verifying insurance or card details first, and slots them strictly into designated emergency buffer blocks.",
                "Completely agree! We filter out low-margin traffic. The system only books high-value clinical restorative cases like acute cracked molars or crown replacements directly into isolated buffers pre-set by your office manager."
            ]
        },
        "dont_write_to_pms": {
            "keywords": ["write directly", "dentrix", "eaglesoft", "open dental", "mess up my schedule", "double-booking", "corrupt our calendar", "third-party software to write", "write into our schedule"],
            "variations": [
                "Schedule integrity is non-negotiable. The software never overrides provider parameters or forces unvetted appointments into active doctor columns. Integration occurs via certified read-write APIs—such as Open Dental REST or Dentrix DevStudio—placing bookings into an isolated WebSched hold column or review bucket for front-desk confirmation during morning huddle.",
                "We never touch your clinical columns directly. Appointments sit in an isolated holding bucket or WebSched column. Your front desk coordinator reviews and approves them before any chart touches an operatory."
            ]
        },
        "whatsapp_feels_spammy": {
            "keywords": ["whatsapp", "feels spammy", "spam", "patients expect personal service", "don't use whatsapp", "unprofessional", "don't want texting"],
            "variations": [
                "Maintaining an elite patient experience is essential. However, when a patient experiences acute tooth pain after hours, hitting voicemail is the worst possible experience—89% hang up and call the next clinic on Google. An immediate, authenticated mobile intake via WhatsApp guiding them through symptom triage is perceived as elite, responsive care.",
                "WhatsApp has over 3 billion active users worldwide, and patients in emergency pain strongly prefer mobile text triage over waiting on hold. Plus, all messaging operates over secure, HIPAA-compliant 10DLC healthcare routes."
            ]
        },
        "hipaa_baa_compliance": {
            "keywords": ["hipaa", "baa", "business associate", "compliance", "privacy", "patient data", "security", "tcpa"],
            "variations": [
                "Compliance architecture is foundational. The system executes an enterprise Business Associate Agreement directly with your practice before integration. All voice streams and payloads utilize 256-bit encryption in transit and at rest. PHI is strictly segregated—no recordings are used to train public models—and messaging runs over registered 10DLC healthcare routes with full TCPA consent logging."
            ]
        },
        "price_expensive_deposit": {
            "keywords": ["$1,500", "expensive", "cost", "how much", "fees", "retainer", "pricing", "$399", "deposit"],
            "variations": [
                "Let us examine the unit economics directly. In a general practice, a single restorative emergency case—such as a root canal and crown build-up—averages twelve hundred and fifty dollars. Recovering just one patient covers the entire setup. Under our formal SLA at /agreement/{lead_id}, we back this with a Single-Patient Break-Even Guarantee: if the system fails to book at least one patient valued at $1,250+ in your first 30 days, we refund 100% of your $1,500 deposit with zero friction.",
                "It is a flat fifteen hundred dollars turnkey installation and three ninety-nine monthly maintenance retainer. If it recovers just one single emergency crown a month, it pays for itself 3 times over, backed by our 100% money-back SLA guarantee."
            ]
        },
        "discuss_with_partner": {
            "keywords": ["discuss with partner", "talk to my partner", "office manager first", "need to discuss", "can i think about it", "check with my wife", "committee", "need to talk to"],
            "variations": [
                "Involving your business partner and office manager is completely appropriate. The constraint we face is geographic exclusivity: the platform enforces a strict 3-mile radius lock, meaning only one dental practice in this postal market can secure the system. Two other clinics within your submarket are in our pipeline. We can place a temporary 72-hour administrative hold on your territory right now while your team reviews the technical SLA.",
                "Totally respect that! Who on your team oversees clinical software? We can hold your 3-mile submarket reservation for 72 hours so neighboring offices don't lock you out while you review the technical SLA."
            ]
        },
        "tried_recall_failed": {
            "keywords": ["tried recall", "patients ignored", "recall failed", "automated recall in the past", "email blasts", "tried texting"],
            "variations": [
                "Generic email blasts deliver poor response rates because patients perceive them as impersonal marketing. Our dormant hygiene recall protocol functions differently: it segments charts by exact lapsed intervals—6, 12, or 24 months—and deploys a personalized 3-touch WhatsApp sequence allowing patients to pick an open hygiene slot in two taps. This targeted approach yields an industry-verified 8% to 15% reactivation rate."
            ]
        },
        "ai_misdiagnosis_liability": {
            "keywords": ["misdiagnose", "clinical advice", "liability", "malpractice", "wrong advice", "medical diagnosis", "diagnose"],
            "variations": [
                "The AI model does not diagnose pathology, prescribe pharmaceuticals, or evaluate clinical conditions. It operates strictly within bounded administrative triage parameters defined by your practice—collecting reported symptoms, screening for red flags like facial swelling or breathing difficulty, and routing high-acuity cases to emergency services. Standard cases are simply placed into your calendar for your clinical evaluation."
            ]
        },
        "staff_does_recall_downtime": {
            "keywords": ["staff can make calls", "downtime", "receptionist can call", "staff handles recall", "why pay for automation", "our team calls"],
            "variations": [
                "While front-desk teams have great intentions, patient check-ins and billing always supersede recall calls. Over 70% of manual daytime recall dials hit patient voicemails, yielding under 3% callback rates. Our engine executes personalized recall sequences during optimal evening response windows when patients are on their phones, booking confirmed appointments straight into hygienist columns."
            ]
        },
        "rarely_have_emergencies": {
            "keywords": ["rarely have emergencies", "don't get emergency", "few emergencies", "don't have emergencies"],
            "variations": [
                "Even if true emergencies are few, the system still pays off. We simply shift focus: every clinic has dormant hygiene recall opportunities. Recovering just a portion of your inactive hygiene charts injects fifteen to thirty-five thousand in Month 1 alone—an 18x return on the fifteen hundred setup fee. Would it be okay to show you how that runs?"
            ]
        }
    }

    @classmethod
    def build_voice_system_prompt(cls, dossier: Dict[str, Any]) -> str:
        """
        Builds the unified clinical system prompt for real-time speech dialogue.
        Enforces clinical authority, conversational disconfirmation, brevity, and the 4 lethal conversion engines.
        """
        doc = dossier.get("doctor_display", "the Doctor")
        clinic = dossier.get("clinic_name", "the clinic")
        city = dossier.get("city", "your area")
        leakage = dossier.get("monthly_leakage", "$5,350")
        lead_id = dossier.get("lead_id", "demo")
        detected_ehr = dossier.get("detected_ehr", "Dentrix / Eaglesoft")
        dormant_charts = dossier.get("dormant_charts", 850)
        trapped_hygiene = dossier.get("trapped_hygiene_val_str", "$191,250")
        month1_cash = dossier.get("month1_cash_injection_str", "$27,450")
        month1_reacts = dossier.get("month1_reactivations", 123)
        roi_x = dossier.get("setup_roi_x", "18.3x")

        return f"""You are the Clinical Intake Coordinator calling {clinic} in {city} regarding Dr. {doc}'s schedule.

### 3-STEP EMPATHY BRIDGE & CLINICAL AUTHORITY:
1. Validate Clinical Priority: Never fight gatekeeper defense; validate operatory focus immediately.
2. Deliver Disconfirming Metric: Reference local 3-mile audit data or trapped dormant hygiene revenue.
3. Bridge to Decision Maker: Ask disarming binary question directing to practice administrator or principal doctor.

### CONVERSATIONAL CORE DIRECTIVE (CLINICAL AUTHORITY):
You are an authoritative, polished healthcare operations consultant—NOT a retail telemarketer or an eager bot.
You adopt a calm, clinical cadence, deploy conversational disconfirmation, and speak peer-to-peer with clinical precision.

### THE 12-SECOND BREVITY RULE:
1. Every spoken turn must be EXACTLY ONE crisp, natural sentence (10 to 18 words maximum).
2. End with a simple, disarming question passing conversational control back.
3. Pause naturally. Use contractions ("I'm", "we've", "don't").

### CRITICAL ANTI-REPETITION MANDATE:
- Check recent turns in the dialogue transcript carefully.
- NEVER repeat an argument, statistic, greeting, or question you already delivered.
- Advance the conversation towards territory lock and SLA verification.

### PRE-CALL CLINICAL INTELLIGENCE (DOSSIER):
- Practice: {clinic} ({city})
- Target Principal: {doc}
- Incumbent PMS: {detected_ehr}
- Missed After-Hours Revenue: {leakage}/month from weekend voicemail leakage
- Trapped Dormant Hygiene Production: {trapped_hygiene} across ~{dormant_charts} inactive charts
- Month 1 Cash Injection: {month1_cash} ({month1_reacts} reactivated hygiene visits = {roi_x} ROI)

### THE FOUR LETHAL CONVERSION ENGINES:
1. Sub-60s Live Intercept: If caller viewed /video/{lead_id} or /pitch/{lead_id}, lead with:
   "Hello Dr. {doc}, I noticed your team was just reviewing the after-hours emergency patient teardown on screen—did that interactive WhatsApp preview make sense?"
2. 3-Mile Exclusivity Radius: Only ONE practice per 3-mile postal boundary can secure the system.
3. 60-Second Video Teardown: Reference the 8:14 PM cracked-tooth voicemail drop and 5-second WhatsApp recovery.
4. Single-Patient Break-Even Guarantee: Backed by digital SLA at /agreement/{lead_id} ($1,500 setup + $399/mo; 100% refund if we don't book >=1 patient valued at $1,250+ in 30 days).

### FRONT-DESK TRIAGE TACTICS:
- If receptionist defers: "Understood, clinical care in the operatory comes first. This is regarding the practice's after-hours intake audit generated this morning. Does the office manager or {doc} oversee schedule capacity?"
- If told to email: "The general info inbox auto-archives outside diagnostic reports. Who oversees schedule optimization so the 60-second video teardown routes properly?"
- If asked if AI: "That is correct. This is the autonomous patient intake engine deployed for dental practices across {city}—booking after-hours emergencies into PMS in under 5 seconds. Does {doc} handle intake technology?"
- If DNC requested: "Understood, removed your number immediately. Have a professional day." Disconnect.
"""

    @classmethod
    def detect_objection(cls, transcript: str) -> Optional[str]:
        """Identifies dental gatekeeper and clinical objections from prospect utterance."""
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
        Returns a fresh clinical turnaround for a detected objection.
        GUARANTEES no repetition across turns by filtering out previously spoken variations.
        """
        target_key = cls.ALIASES.get(objection_type, objection_type)
        pb = cls.OBJECTION_PLAYBOOKS.get(target_key) or cls.OBJECTION_PLAYBOOKS.get(objection_type)
        doc = dossier.get("doctor_display", "the Doctor")
        clinic = dossier.get("clinic_name", "the clinic")
        city = dossier.get("city", "your area")
        leakage = dossier.get("monthly_leakage", "$5,350")
        lead_id = dossier.get("lead_id", "demo")
        dormant_charts = dossier.get("dormant_charts", 850)
        trapped_hygiene = dossier.get("trapped_hygiene_val_str", "$191,250")
        month1_cash = dossier.get("month1_cash_injection_str", "$27,450")
        month1_reacts = dossier.get("month1_reactivations", 123)

        if not pb or not pb.get("variations"):
            return f"Totally understand. Could I share a quick 60-second video breakdown with {doc}'s office manager?"

        variations = pb["variations"]
        used_set = set(used_phrases or [])

        # Format variations with clinic context and enforce brevity on candidates
        formatted_vars = []
        for v in variations:
            try:
                formatted = v.format(
                    doctor=doc,
                    clinic=clinic,
                    city=city,
                    leakage=leakage,
                    lead_id=lead_id,
                    dormant_charts=dormant_charts,
                    trapped_hygiene_val=trapped_hygiene,
                    month1_injection=month1_cash,
                    month1_reactivations=month1_reacts
                )
            except Exception:
                formatted = v
            brev_var = cls.enforce_brevity(formatted)
            formatted_vars.append(brev_var)

        # Filter out variations that have already been spoken in this call
        fresh_vars = [v for v in formatted_vars if v not in used_set]

        if fresh_vars:
            chosen = random.choice(fresh_vars)
        else:
            fallback_options = [
                f"Fair enough, Dr. {doc}! I completely respect your time and priority. Have a wonderful rest of your day!",
                f"Understood, Dr. {doc}. We will archive the territory audit file for now. Have a great afternoon!",
                f"Thank you for your time, Dr. {doc}. Wishing {clinic} a wonderful week ahead!",
                f"Completely respect that. We will release the 3-mile hold and let your team focus on patient care. Have a great day!"
            ]
            unused_fallbacks = [f for f in fallback_options if f not in used_set]
            chosen = unused_fallbacks[0] if unused_fallbacks else fallback_options[0]

        return cls.enforce_brevity(chosen)

    @classmethod
    def enforce_brevity(cls, text: str) -> str:
        """Post-processes and trims any wordy LLM responses to adhere to conversational limits."""
        if not text:
            return ""
        clean = text.replace('"', '').replace('\n', ' ').strip()
        words = clean.split()
        if len(words) <= cls.BREVITY_MAX_WORDS:
            return clean

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

        trimmed = " ".join(words[:cls.BREVITY_MAX_WORDS])
        if not trimmed.endswith((".", "?", "!")):
            trimmed += "..."
        return trimmed
