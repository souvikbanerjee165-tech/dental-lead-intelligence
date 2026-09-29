"""
Clinic Web Researcher & Gemini Proposal Drafting Engine.
Crawls clinic websites, extracts clinical team, procedures, and intake friction,
and uses Google Gemini to draft deeply personalized, research-backed growth proposals.
"""

import os
import re
import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from config import USER_AGENT, OUTPUT_DIR, GEMINI_API_KEY
from decision_hunter import DecisionMakerHunter
from database import DatabaseManager
from models import RawLead, ScoredLead, WebsiteAuditResult, TechStackDetail, DigitalMaturityScore

logger = logging.getLogger("clinic_researcher")

# Dental specialty keywords
PROCEDURE_KEYWORDS = [
    "dental implants", "all-on-4", "all on 4", "single implant", "multiple implants",
    "emergency dentistry", "emergency dentist", "root canal", "crowns", "bridges",
    "invisalign", "clear aligners", "teeth whitening", "veneers", "smile makeover",
    "dentures", "full mouth reconstruction", "pediatric dentistry", "sedation dentistry",
    "periodontics", "oral surgery", "tooth extraction", "sinus lift", "cosmetic dentistry"
]

BOOKING_WIDGET_SIGNATURES = [
    "nexhealth", "localmed", "zocdoc", "calendly", "acuityscheduling",
    "solutionreach", "weave", "practice-minder", "simplifeye", "modento"
]

CHAT_WIDGET_SIGNATURES = [
    "podium", "weave", "drift", "crisp", "livechat", "tawk.to", "intercom",
    "zendesk", "whatsapp", "tidio", "birdeye", "swell", "chatra"
]

class ClinicResearchProfile(BaseModel):
    name: str
    website: str
    phone: str = ""
    address: str = ""
    city_state: str = ""
    doctors: List[str] = Field(default_factory=list)
    primary_doctor: str = "Practice Principal"
    services_found: List[str] = Field(default_factory=list)
    has_online_booking: bool = False
    detected_booking_tool: Optional[str] = None
    has_ai_chat: bool = False
    detected_chat_tool: Optional[str] = None
    has_ssl: bool = True
    is_mobile_responsive: bool = True
    page_load_seconds: float = 1.0
    digital_maturity_score: int = 45
    estimated_monthly_leakage: int = 4500
    subpages_crawled: List[str] = Field(default_factory=list)
    raw_snippets: List[str] = Field(default_factory=list)

class ClinicResearcher:
    """Automated Clinic Intelligence Gathering & Gemini Proposal Architect."""

    @classmethod
    async def research_website(cls, url: str, practice_name_hint: Optional[str] = None) -> ClinicResearchProfile:
        """
        Crawls the clinic website (homepage + team/about/services) and extracts structured intelligence.
        """
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url

        has_ssl = url.startswith("https://")
        
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        profile = ClinicResearchProfile(
            name=practice_name_hint or "Dental Practice",
            website=url,
            has_ssl=has_ssl
        )

        t0 = time.time()
        home_html = ""
        team_html = ""
        crawled_urls = [url]

        async with httpx.AsyncClient(headers=headers, timeout=12.0, follow_redirects=True, verify=False) as client:
            # 1. Fetch Homepage
            try:
                r_home = await client.get(url)
                profile.page_load_seconds = round(time.time() - t0, 2)
                if r_home.status_code < 400:
                    home_html = r_home.text
            except Exception as e:
                logger.warning(f"Failed to fetch homepage {url}: {e}")

            if not home_html:
                # If homepage fails, return minimum baseline
                profile.digital_maturity_score = 30
                return profile

            soup_home = BeautifulSoup(home_html, "html.parser")

            # Extract Title / Name if not provided or generic
            if not practice_name_hint or practice_name_hint.lower() in ("dental practice", "premier dental clinic", "clinic"):
                title_tag = soup_home.find("title")
                if title_tag and title_tag.string:
                    clean_title = title_tag.string.split("|")[0].split("-")[0].strip()
                    if clean_title and len(clean_title) > 3:
                        profile.name = clean_title

            # Extract Phone: prioritize tel: links
            tel_links = [a["href"].replace("tel:", "").strip() for a in soup_home.find_all("a", href=True) if a["href"].startswith("tel:")]
            if tel_links:
                profile.phone = tel_links[0]
            else:
                phone_matches = re.findall(r'\(?\b\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b', home_html)
                valid_phones = [p for p in phone_matches if not p.startswith("000") and not p.startswith("555-01") and ("-" in p or "(" in p)]
                if valid_phones:
                    profile.phone = valid_phones[0]

            # Extract Address / City / State
            address_block = soup_home.find(lambda tag: tag.name in ['p', 'div', 'span', 'address', 'footer'] and re.search(r'\b[A-Z]{2}\s+\d{5}\b', tag.get_text()))
            if address_block:
                profile.address = " ".join(address_block.get_text(strip=True).split())
                city_match = re.search(r'([A-Z][a-zA-Z\s]+),\s*([A-Z]{2})\b', profile.address)
                if city_match:
                    profile.city_state = f"{city_match.group(1).strip()}, {city_match.group(2)}"

            # Detect Internal Team / About Subpages
            candidate_team_links = []
            for a in soup_home.find_all("a", href=True):
                href = a["href"]
                full_sub = urljoin(url, href)
                # Keep only internal links
                if urlparse(full_sub).netloc == urlparse(url).netloc:
                    link_text = a.get_text(strip=True).lower()
                    url_lower = full_sub.lower()
                    if any(k in url_lower or k in link_text for k in ['meet-the-team', 'our-team', 'meet-the-doctor', 'about-us', 'our-practice', 'dentist', 'doctors']):
                        candidate_team_links.append(full_sub)

            # 2. Fetch Team Page if found
            if candidate_team_links:
                team_url = candidate_team_links[0]
                try:
                    r_team = await client.get(team_url)
                    if r_team.status_code < 400:
                        team_html = r_team.text
                        crawled_urls.append(team_url)
                except Exception as e:
                    logger.warning(f"Failed to fetch team page {team_url}: {e}")

        combined_html = home_html + " " + team_html
        combined_text = " ".join(BeautifulSoup(combined_html, "html.parser").stripped_strings)
        combined_text_lower = combined_text.lower()

        # Extract City/State fallback if not found
        if not profile.city_state:
            city_state_matches = re.findall(r'\b([A-Z][a-zA-Z\s]{2,20}),\s*([A-Z]{2})\b', combined_text)
            valid_cities = [f"{c[0].strip()}, {c[1]}" for c in city_state_matches if c[0].strip().lower() not in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "read more")]
            if valid_cities:
                profile.city_state = valid_cities[0]

        # 3. Extract Doctors
        doctors_found = []
        extracted_decision = DecisionMakerHunter.extract_from_html(combined_html)
        if extracted_decision.get("doctors"):
            doctors_found.extend(extracted_decision["doctors"])

        doc_patterns = [
            r'Dr\.\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})',
            r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2}),?\s+(?:DDS|DMD|BDS)\b'
        ]
        for pat in doc_patterns:
            for m in re.finditer(pat, combined_text):
                d_name = m.group(1).strip()
                if DecisionMakerHunter.is_valid_person_name(d_name):
                    doctors_found.append(f"Dr. {d_name}")

        # Clean doctor names from title suffixes
        title_suffixes = {"General", "President", "Ceo", "Dds", "Dmd", "Bds", "Fagd", "Dentist", "And", "Implant", "Associate", "Staff"}
        cleaned_doctors = []
        for d in doctors_found:
            parts = d.split()
            kept = []
            for p in parts:
                if p.capitalize() in title_suffixes and len(kept) >= 3:
                    break
                kept.append(p)
            clean_d = " ".join(kept)
            if len(clean_d.split()) >= 2 and clean_d not in cleaned_doctors:
                cleaned_doctors.append(clean_d)

        profile.doctors = cleaned_doctors[:3]
        if profile.doctors:
            profile.primary_doctor = profile.doctors[0]

        # 4. Extract Services & Procedures
        found_services = []
        for kw in PROCEDURE_KEYWORDS:
            if kw in combined_text_lower:
                found_services.append(kw.title())
        profile.services_found = list(dict.fromkeys(found_services))[:8]

        # 5. Intake & Tech Audit
        for tool in BOOKING_WIDGET_SIGNATURES:
            if tool in combined_html.lower():
                profile.has_online_booking = True
                profile.detected_booking_tool = tool.capitalize()
                break

        # Check for interactive AI / live chat widget (filter out simple social share links)
        for chat in CHAT_WIDGET_SIGNATURES:
            if chat == "whatsapp":
                if re.search(r'wa\.me/\d+|whatsapp-widget|joinchat|whatsapp-chat|id=["\']whatsapp-widget', combined_html, re.I):
                    profile.has_ai_chat = True
                    profile.detected_chat_tool = "WhatsApp Chat"
                    break
            else:
                if f"/{chat}" in combined_html.lower() or f"{chat}.com" in combined_html.lower() or f"{chat}-widget" in combined_html.lower():
                    profile.has_ai_chat = True
                    profile.detected_chat_tool = chat.capitalize()
                    break

        viewport = soup_home.find("meta", attrs={"name": "viewport"})
        profile.is_mobile_responsive = bool(viewport)

        # 6. Calculate Empirical Digital Maturity Score
        score = 20
        if profile.has_ssl:
            score += 10
        if profile.is_mobile_responsive:
            score += 15
        if profile.page_load_seconds < 2.5:
            score += 10
        if profile.has_online_booking:
            score += 20
        if profile.has_ai_chat:
            score += 25
        # Deduct if high ticket services exist but online booking/chat missing
        has_high_ticket = any(s.lower() in ("dental implants", "all-on-4", "emergency dentistry") for s in profile.services_found)
        if has_high_ticket and not profile.has_online_booking and not profile.has_ai_chat:
            score = max(25, min(score, 48))  # Solid diagnosis of intake bottleneck

        profile.digital_maturity_score = score

        # 7. Estimate Revenue Leakage based on high-ticket service mix
        if any(s.lower() in ("all-on-4", "all on 4") for s in profile.services_found):
            profile.estimated_monthly_leakage = 7800
        elif any(s.lower() in ("dental implants", "emergency dentistry") for s in profile.services_found):
            profile.estimated_monthly_leakage = 5400
        else:
            profile.estimated_monthly_leakage = 3800

        profile.subpages_crawled = crawled_urls
        # Store representative snippets
        profile.raw_snippets = [combined_text[:1200]]

        return profile

    @classmethod
    async def draft_with_gemini(cls, profile: ClinicResearchProfile) -> Dict[str, Any]:
        """
        Uses Google Gemini to synthesize research findings into a customized proposal draft.
        Gracefully falls back to heuristic generation if the API is offline or unavailable.
        """
        api_key = os.getenv("GEMINI_API_KEY") or GEMINI_API_KEY
        if api_key:
            try:
                from google import genai
                client = genai.Client(api_key=api_key)

                services_str = ", ".join(profile.services_found) if profile.services_found else "General, Restorative & Emergency Dentistry"
                doctors_str = ", ".join(profile.doctors) if profile.doctors else profile.primary_doctor
                location_str = profile.city_state or profile.address or "California"

                prompt = f"""
You are an elite B2B Healthcare Practice Growth Consultant & Dental Practice Architect.
You are preparing a bespoke Client Growth & Patient Recapture Proposal for a dental practice.

CRITICAL INSTRUCTION:
Do NOT use generic placeholder text. Thoroughly analyze the empirical clinic research below and customize every single section, package title, deliverable, and financial calculation to this specific practice and its doctors.

CLINIC RESEARCH DOSSIER:
- Practice Name: {profile.name}
- Identified Doctors: {doctors_str}
- Lead Doctor / CEO: {profile.primary_doctor}
- Practice Location: {location_str}
- Phone Number: {profile.phone or "(Local Phone)"}
- High-Value Services Offered: {services_str}
- Online Booking Status: {"Present (" + str(profile.detected_booking_tool) + ")" if profile.has_online_booking else "MISSING (No direct 24/7 online scheduling tool detected)"}
- Live Chat / AI Receptionist: {"Present (" + str(profile.detected_chat_tool) + ")" if profile.has_ai_chat else "MISSING (No 24/7 AI chat or WhatsApp receptionist detected)"}
- Digital Maturity Score: {profile.digital_maturity_score}/100
- Estimated Monthly Revenue Leakage: ${profile.estimated_monthly_leakage:,}/mo

Generate a structured JSON proposal matching this exact JSON schema:
{{
  "practice_headline": "Compelling 1-sentence headline referencing practice name, location, and high-ticket specialties",
  "executive_diagnostic": "2-3 sentences addressing the lead doctor by name, identifying their high-value clinical services (e.g. implants, emergency), and pointing out how their current front-desk intake leaks revenue after hours.",
  "diagnosed_friction_points": [
    {{
      "title": "Title of specific intake friction",
      "evidence": "Evidence observed from their site (e.g., after-hours emergency calls going to voicemail, lack of instant mobile chat)",
      "financial_impact": "Financial loss estimate (e.g., losing 2-3 implant or emergency cases per month = $X,000 leakage)",
      "solution": "How our 24/7 WhatsApp & AI receptionist solves this immediately"
    }},
    {{
      "title": "Second specific friction point",
      "evidence": "Concrete evidence",
      "financial_impact": "Financial loss estimate",
      "solution": "Specific solution"
    }},
    {{
      "title": "Third specific friction point",
      "evidence": "Concrete evidence",
      "financial_impact": "Financial loss estimate",
      "solution": "Specific solution"
    }}
  ],
  "custom_packages": [
    {{
      "tier": 1,
      "name": "Package Name (tailored to practice)",
      "tagline": "Punchy benefit-driven tagline",
      "setup_fee": 1500,
      "monthly_retainer": 397,
      "deliverables": [
        "Deliverable 1 mentioning clinic procedures",
        "Deliverable 2 mentioning instant notification to team",
        "Deliverable 3",
        "Deliverable 4"
      ],
      "projected_annual_recapture": {int(profile.estimated_monthly_leakage * 12 * 0.45)}
    }},
    {{
      "tier": 2,
      "name": "Package Name (Featured - Most Popular)",
      "tagline": "Punchy benefit-driven tagline",
      "setup_fee": 2500,
      "monthly_retainer": 697,
      "deliverables": [
        "Everything in Tier 1",
        "Direct 2-way patient conversational booking over WhatsApp & Web",
        "Deliverable mentioning their high-ticket services",
        "Automated appointment recall & reschedule sequences",
        "Deliverable 5"
      ],
      "projected_annual_recapture": {int(profile.estimated_monthly_leakage * 12 * 0.75)}
    }},
    {{
      "tier": 3,
      "name": "Package Name (Elite Growth Engine)",
      "tagline": "Punchy benefit-driven tagline",
      "setup_fee": 4500,
      "monthly_retainer": 997,
      "deliverables": [
        "Everything in Tier 1 & Tier 2",
        "Automated 5-Star Google Review Booster after treatment completion",
        "High-Ticket Treatment Lead Accelerator (Implants & Cosmetic)",
        "Deliverable 4",
        "Deliverable 5"
      ],
      "projected_annual_recapture": {int(profile.estimated_monthly_leakage * 12 * 1.15)}
    }}
  ],
  "roi_rationale": "Clear 2-sentence payback explanation demonstrating that recovering just ONE single high-ticket patient (e.g. dental implant or root canal) completely pays for the entire year of service.",
  "implementation_roadmap": [
    {{"phase": "Phase 1: Setup & Practice Onboarding", "days": "Days 1–3", "description": "Seamless zero-downtime setup mapping practice hours and services."}},
    {{"phase": "Phase 2: Private Sandbox Review", "days": "Days 4–7", "description": "Doctor and staff test the conversational AI in a private sandbox."}},
    {{"phase": "Phase 3: Live Patient Recapture", "days": "Day 8 Onward", "description": "System goes live capturing after-hours inquiries directly into your practice schedule."}}
  ]
}}
Respond ONLY with valid, unescaped JSON. No markdown backticks.
"""
                for model_choice in ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash']:
                    try:
                        response = client.models.generate_content(
                            model=model_choice,
                            contents=prompt
                        )
                        raw_text = response.text.strip()
                        if raw_text.startswith("```json"):
                            raw_text = raw_text[7:]
                        if raw_text.startswith("```"):
                            raw_text = raw_text[3:]
                        if raw_text.endswith("```"):
                            raw_text = raw_text[:-3]

                        data = json.loads(raw_text.strip())
                        logger.info(f"Successfully drafted proposal with {model_choice} for {profile.name}")
                        return data
                    except Exception as model_err:
                        logger.warning(f"Model {model_choice} drafting failed: {model_err}")
                        continue
            except Exception as e:
                logger.error(f"Gemini client initialization failed: {e}")

        # Fallback to intelligent deterministic drafting incorporating real research
        return cls._fallback_heuristic_draft(profile)

    @classmethod
    def _fallback_heuristic_draft(cls, profile: ClinicResearchProfile) -> Dict[str, Any]:
        """High-quality heuristic draft using extracted real practice details."""
        doc = profile.primary_doctor
        services = profile.services_found or ["Implants", "Emergency Dentistry", "Restorative Care"]
        service_sample = ", ".join(services[:3])
        location = profile.city_state or "your local area"
        annual_loss = profile.estimated_monthly_leakage * 12

        return {
            "practice_headline": f"Patient Intake & Revenue Recapture Architecture for {profile.name} ({location})",
            "executive_diagnostic": f"Prepared for {doc} and the clinical team at {profile.name}. While your practice offers premier clinical treatments in {service_sample}, our technical audit identified that after-hours and weekend patient inquiries currently face front-desk phone friction, leading high-intent patients to seek immediate care with competing local practices.",
            "diagnosed_friction_points": [
                {
                    "title": "Uncaptured After-Hours & Emergency Inquiries",
                    "evidence": f"Prospective patients visiting {profile.website} after 5 PM or on weekends encounter static contact details with no 24/7 instant booking or chat.",
                    "financial_impact": f"Estimated leakage of ${profile.estimated_monthly_leakage:,}/mo in unbooked chair production.",
                    "solution": "24/7 Conversational AI Receptionist responds instantly in under 5 seconds to triage emergencies and capture appointments."
                },
                {
                    "title": "High-Value Treatment Conversion Gap",
                    "evidence": f"Patients researching high-ticket procedures such as {service_sample} must call during business hours rather than self-qualifying.",
                    "financial_impact": "Loss of 1-2 comprehensive treatment cases per month ($3,000 - $6,000+).",
                    "solution": "Automated WhatsApp & Web treatment guidance chatbot that qualifies patient intent and reserves consultation slots."
                },
                {
                    "title": "Front-Desk Phone Latency During Peak Clinic Hours",
                    "evidence": f"When reception is checking in patients or processing claims, incoming callers on {profile.phone or 'office phone'} risk rolling to voicemail.",
                    "financial_impact": "Over 65% of patients who reach voicemail hang up and immediately dial a competing dental office.",
                    "solution": "Instant Missed-Call Auto-Textback on SMS & WhatsApp with 1-click self-scheduling link."
                }
            ],
            "custom_packages": [
                {
                    "tier": 1,
                    "name": "24/7 AI Patient Intake & Triage",
                    "tagline": f"Never miss an after-hours patient inquiry for {profile.name}",
                    "setup_fee": 1500,
                    "monthly_retainer": 397,
                    "deliverables": [
                        f"Custom 24/7 AI Receptionist calibrated for {profile.name}'s procedures",
                        "Instant SMS & Email dispatch to office coordinator for high-priority cases",
                        "Emergency dental inquiry qualification & after-hours triage",
                        "Google Business Profile & Website 1-click WhatsApp sync"
                    ],
                    "projected_annual_recapture": int(annual_loss * 0.45)
                },
                {
                    "tier": 2,
                    "name": "Frictionless Self-Scheduling & Intake",
                    "tagline": "Complete 24/7 direct appointment booking synchronized with your calendar",
                    "setup_fee": 2500,
                    "monthly_retainer": 697,
                    "deliverables": [
                        "Everything in Tier 1 (24/7 AI Receptionist)",
                        f"High-intent patient qualification for {service_sample}",
                        "Direct calendar booking integration (Dentrix, Eaglesoft, OpenDental, Curve)",
                        "Automated appointment confirmation & zero-show reduction sequences",
                        "Dedicated conversion analytics & monthly ROI report"
                    ],
                    "projected_annual_recapture": int(annual_loss * 0.75)
                },
                {
                    "tier": 3,
                    "name": "Full Practice Revenue Growth Engine",
                    "tagline": "End-to-end patient acquisition, high-ticket treatment recapture & reputation defense",
                    "setup_fee": 4500,
                    "monthly_retainer": 997,
                    "deliverables": [
                        "Everything in Tier 1 & Tier 2 (Intake + Direct Booking)",
                        "Automated 5-Star Google Review booster following completed procedures",
                        "Dormant patient recall campaigns via 98% open-rate WhatsApp/SMS broadcasts",
                        "Instant Missed-Call Text-Back automation on primary clinic line",
                        "Quarterly local competitor benchmark audits and executive ROI review"
                    ],
                    "projected_annual_recapture": int(annual_loss * 1.15)
                }
            ],
            "roi_rationale": f"Because {profile.name} performs high-value procedures like {service_sample}, recapturing just ONE single procedure every 2-3 months covers the entire annual investment, delivering an estimated 7x–10x net ROI.",
            "implementation_roadmap": [
                {"phase": "Phase 1: Setup & Practice Onboarding", "days": "Days 1–3", "description": f"Zero staff disruption. We map your practice hours, fees, and {service_sample} guidelines."},
                {"phase": "Phase 2: Private Sandbox Review", "days": "Days 4–7", "description": f"{doc} and practice staff test-drive the AI receptionist in a private test environment."},
                {"phase": "Phase 3: Live Patient Recapture", "days": "Day 8 Onward", "description": "System goes live capturing after-hours and weekend inquiries directly into your schedule."}
            ]
        }

    @classmethod
    async def research_and_generate(
        cls,
        name: str,
        url: str,
        lead_id: Optional[str] = None,
        db: Optional[DatabaseManager] = None
    ) -> Dict[str, Any]:
        """
        Executes full pipeline: Research -> Gemini Drafting -> Proposal Generation -> SQLite Persistence.
        """
        db = db or DatabaseManager()

        # 1. Research Website
        logger.info(f"Starting deep website research for: {name} ({url})")
        profile = await cls.research_website(url=url, practice_name_hint=name)

        # 2. Draft Proposal with Gemini
        logger.info(f"Drafting bespoke proposal with Gemini for: {profile.name}")
        draft = await cls.draft_with_gemini(profile)

        # 3. Create/Update ScoredLead in DB
        lead_id = lead_id or db._make_lead_id(profile.name, profile.website)
        raw_lead = RawLead(
            id=lead_id,
            name=profile.name,
            website=profile.website,
            phone=profile.phone or "N/A",
            address=profile.address or profile.city_state or "California"
        )
        
        audit_res = WebsiteAuditResult(
            reachable=True,
            has_ssl=profile.has_ssl,
            has_ai_chatbot=profile.has_ai_chat,
            detected_chatbot_name=profile.detected_chat_tool,
            has_online_booking=profile.has_online_booking,
            detected_booking_tool=profile.detected_booking_tool,
            is_mobile_responsive=profile.is_mobile_responsive,
            load_time_seconds=profile.page_load_seconds
        )

        maturity = DigitalMaturityScore(
            overall_score=profile.digital_maturity_score,
            website_quality=min(90, profile.digital_maturity_score + 15),
            patient_experience=profile.digital_maturity_score,
            automation_score=75 if profile.has_ai_chat else 30,
            conversion_score=70 if profile.has_online_booking else 35
        )

        scored_lead = ScoredLead(
            raw_lead=raw_lead,
            audit=audit_res,
            maturity=maturity,
            opportunity_score=100 - profile.digital_maturity_score,
            estimated_missed_revenue_monthly_max=profile.estimated_monthly_leakage,
            estimated_missed_revenue_annual=profile.estimated_monthly_leakage * 12
        )

        # Update database with rich doctor & research data
        try:
            scored_lead.doctor_name = profile.primary_doctor
            db.save_scored_lead(scored_lead, [])
            with db._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    UPDATE leads 
                    SET doctor_name = COALESCE(?, doctor_name),
                        decision_maker_role = COALESCE(?, decision_maker_role),
                        staff_roster = COALESCE(?, staff_roster)
                    WHERE id = ?
                """, (profile.primary_doctor, "President / Practice Principal", json.dumps({"doctors": profile.doctors, "services": profile.services_found}), lead_id))
                conn.commit()
        except Exception as e:
            logger.warning(f"Could not persist researched lead to DB: {e}")

        # 4. Generate Proposal File
        from proposals import ProposalGenerator
        proposal_file = ProposalGenerator.generate_proposal(
            scored_lead=scored_lead,
            agency_name="WhatsApp Growth Partners for Dentists",
            research_dossier=profile,
            gemini_draft=draft
        )

        packages = draft.get("custom_packages", [])
        tier1_setup = 1500
        tier2_setup = 2500
        if packages and len(packages) > 0 and isinstance(packages[0], dict) and "price" in packages[0]:
            try:
                tier1_setup = int(packages[0]["price"].replace("$", "").replace(",", "").split()[0])
            except Exception:
                pass

        return {
            "status": "success",
            "lead_id": lead_id,
            "practice_name": profile.name,
            "doctor_name": profile.primary_doctor,
            "doctors": profile.doctors,
            "services": profile.services_found,
            "digital_maturity_score": profile.digital_maturity_score,
            "monthly_leakage": profile.estimated_monthly_leakage,
            "proposal_path": str(proposal_file),
            "proposal_url": f"/output/proposals/{proposal_file.name}",
            "tier1_setup": tier1_setup,
            "tier2_setup": tier2_setup,
            "headline": draft.get("practice_headline"),
            "executive_diagnostic": draft.get("executive_diagnostic"),
            "diagnosed_friction": draft.get("diagnosed_friction_points", []),
            "packages": packages,
            "roi_rationale": draft.get("roi_rationale")
        }
