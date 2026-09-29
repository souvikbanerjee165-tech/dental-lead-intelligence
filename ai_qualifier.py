"""
AI Sales Qualification Agent (B2B SaaS Sales Director Engine).
Evaluates whether a practice is genuinely worth 30 minutes of a solo founder's time,
calculates rigorous Buying Probability %, determines practice structure, and extracts core buying catalysts.
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field

logger = logging.getLogger("ai_qualifier")

class AIQualificationResult(BaseModel):
    lead_id: str
    business_name: str
    would_spend_30min_calling: str = "YES"  # "YES" or "NO"
    buying_probability_pct: int = 85        # 0 to 100
    win_probability_pct: int = 85           # 0 to 100 (Closing Probability)
    win_probability_reasons: List[str] = Field(default_factory=list)
    pain_level: str = "HIGH"               # "CRITICAL", "HIGH", "MODERATE", "LOW"
    decision_accessibility: str = "DIRECT_DOCTOR"  # "DIRECT_DOCTOR", "OFFICE_MANAGER", "GATEKEEPER_WALL"
    practice_type: str = "INDEPENDENT_OWNER"        # "INDEPENDENT_OWNER", "MULTI_LOCATION", "CORPORATE_DSO"
    buying_triggers: List[str] = Field(default_factory=list)
    sales_manager_verdict: str = ""
    is_a_tier: bool = True

class AIQualifier:
    """Simulates a seasoned VP of Sales qualifying dental practice prospects."""

    @classmethod
    def qualify_lead(
        cls,
        lead_dict: Dict[str, Any],
        doctor_name: Optional[str] = None,
        technologies: Optional[List[str]] = None,
        opportunity_score: int = 75,
        estimated_monthly_leakage: int = 3500
    ) -> AIQualificationResult:
        """
        Qualify lead using Gemini 2.5 Flash, falling back to expert deterministic heuristics.
        """
        name = lead_dict.get("name") or "Dental Clinic"
        rating = float(lead_dict.get("rating") or 4.5)
        reviews = int(lead_dict.get("review_count") or 50)
        phone = lead_dict.get("phone") or ""
        website = lead_dict.get("website") or ""
        lead_id = lead_dict.get("id") or "lead_unknown"
        doc = doctor_name or lead_dict.get("doctor_name")
        tech_list = technologies or lead_dict.get("technologies") or []

        # Attempt Gemini 2.5 Flash qualification
        gemini_result = cls._try_gemini_qualification(
            lead_id=lead_id,
            name=name,
            rating=rating,
            reviews=reviews,
            phone=phone,
            website=website,
            doctor_name=doc,
            technologies=tech_list,
            opportunity_score=opportunity_score,
            estimated_monthly_leakage=estimated_monthly_leakage
        )

        res = gemini_result or cls._deterministic_qualification(
            lead_id=lead_id,
            name=name,
            rating=rating,
            reviews=reviews,
            phone=phone,
            website=website,
            doctor_name=doc,
            technologies=tech_list,
            opportunity_score=opportunity_score,
            estimated_monthly_leakage=estimated_monthly_leakage
        )

        # Calculate Win Probability & Drivers via institutional memory flywheel
        try:
            from memory_manager import MemoryManager
            memory_learnings = MemoryManager.get_learnings_for_lead(lead_dict)
        except Exception:
            memory_learnings = None

        win_prob, win_reasons = cls.calculate_win_probability(
            lead_dict=lead_dict,
            technologies=tech_list,
            memory_learnings=memory_learnings,
            estimated_monthly_leakage=estimated_monthly_leakage
        )

        res.win_probability_pct = win_prob
        res.win_probability_reasons = win_reasons
        return res

    @classmethod
    def _try_gemini_qualification(
        cls,
        lead_id: str,
        name: str,
        rating: float,
        reviews: int,
        phone: str,
        website: str,
        doctor_name: Optional[str],
        technologies: List[str],
        opportunity_score: int,
        estimated_monthly_leakage: int
    ) -> Optional[AIQualificationResult]:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return None

        try:
            from google import genai
            client = genai.Client(api_key=api_key)

            prompt = f"""
You are an elite B2B SaaS Sales Director selling a 24/7 AI WhatsApp Receptionist & Automated Patient Booking System ($497/mo retainer) to dental clinics.
Your solo founder has limited time and can only call top-tier, high-probability prospects.

Analyze this dental clinic:
- Practice Name: {name}
- Doctor/Owner: {doctor_name or "Not explicitly identified"}
- Google Rating: {rating} stars ({reviews} reviews)
- Website: {website or "None"}
- Phone: {phone}
- Detected Technologies: {', '.join(technologies) if technologies else "No modern chat or booking widgets detected"}
- Technical Opportunity Score: {opportunity_score}/100
- Estimated Monthly Revenue Leakage: ${estimated_monthly_leakage}/month

Answer these questions:
1. Would you personally spend 30 minutes calling this dentist? ("YES" or "NO")
2. What is the Buying Probability % (0 to 100)?
3. What is the Pain Level? ("CRITICAL", "HIGH", "MODERATE", "LOW")
4. What is the Decision Accessibility? ("DIRECT_DOCTOR", "OFFICE_MANAGER", "GATEKEEPER_WALL")
5. What is the Practice Structure? ("INDEPENDENT_OWNER", "MULTI_LOCATION", "CORPORATE_DSO")
6. List 3 specific buying triggers / psychological pain points.
7. Provide a concise 2-sentence sales manager verdict.

Respond ONLY with valid JSON matching this schema:
{{
  "would_spend_30min_calling": "YES" or "NO",
  "buying_probability_pct": 88,
  "pain_level": "HIGH",
  "decision_accessibility": "DIRECT_DOCTOR",
  "practice_type": "INDEPENDENT_OWNER",
  "buying_triggers": [
    "Trigger 1",
    "Trigger 2",
    "Trigger 3"
  ],
  "sales_manager_verdict": "Verdict text."
}}
"""
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
            )

            raw_text = response.text.strip()
            # Clean markdown codeblocks
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]

            data = json.loads(raw_text.strip())
            prob = int(data.get("buying_probability_pct", 75))

            return AIQualificationResult(
                lead_id=lead_id,
                business_name=name,
                would_spend_30min_calling=data.get("would_spend_30min_calling", "YES" if prob >= 75 else "NO"),
                buying_probability_pct=prob,
                pain_level=data.get("pain_level", "HIGH"),
                decision_accessibility=data.get("decision_accessibility", "DIRECT_DOCTOR" if doctor_name else "OFFICE_MANAGER"),
                practice_type=data.get("practice_type", "INDEPENDENT_OWNER"),
                buying_triggers=data.get("buying_triggers", []),
                sales_manager_verdict=data.get("sales_manager_verdict", f"High fit prospect with ~${estimated_monthly_leakage}/mo missed revenue."),
                is_a_tier=prob >= 80
            )
        except Exception as e:
            logger.warning(f"Gemini qualification fallback engaged: {e}")
            return None

    @classmethod
    def _deterministic_qualification(
        cls,
        lead_id: str,
        name: str,
        rating: float,
        reviews: int,
        phone: str,
        website: str,
        doctor_name: Optional[str],
        technologies: List[str],
        opportunity_score: int,
        estimated_monthly_leakage: int
    ) -> AIQualificationResult:
        """High-precision heuristic qualification engine."""
        base_prob = 50

        # Doctor identified (+20%)
        if doctor_name:
            base_prob += 20
            accessibility = "DIRECT_DOCTOR"
        else:
            base_prob += 5
            accessibility = "OFFICE_MANAGER"

        # High reviews = established patient flow losing after-hours leads (+15%)
        if reviews >= 200:
            base_prob += 15
        elif reviews >= 50:
            base_prob += 10

        # No chat or booking tools detected (+15%)
        has_chat = any("chat" in t.lower() or "tidio" in t.lower() or "podium" in t.lower() for t in technologies)
        has_booking = any("booking" in t.lower() or "nexhealth" in t.lower() for t in technologies)

        if not has_chat and not has_booking:
            base_prob += 15
            pain = "CRITICAL" if reviews > 100 else "HIGH"
        elif not has_chat:
            base_prob += 10
            pain = "HIGH"
        else:
            pain = "MODERATE"

        # Penalize if no phone
        if not phone:
            base_prob -= 30

        # Clamp 10 - 96
        buying_prob = max(10, min(96, base_prob))
        should_call = "YES" if buying_prob >= 75 and phone else "NO"

        # Practice type detection
        name_lower = name.lower()
        if any(w in name_lower for w in ["heartland", "aspen", "pacific dental", "smile brands", "dso"]):
            practice_type = "CORPORATE_DSO"
            buying_prob = min(buying_prob, 40)
            should_call = "NO"
            accessibility = "GATEKEEPER_WALL"
        elif any(w in name_lower for w in ["associates", "group", "partners", "care center"]):
            practice_type = "MULTI_LOCATION"
        else:
            practice_type = "INDEPENDENT_OWNER"

        triggers = []
        if doctor_name:
            triggers.append(f"Direct access to practice owner {doctor_name} bypasses front-desk gatekeeper")
        if not has_chat:
            triggers.append("Zero after-hours capture: patients inquiring after 5 PM call nearby competitors")
        if reviews >= 100:
            triggers.append(f"Strong clinical reputation ({rating}★ across {reviews} reviews) leaking high-ticket cosmetic/implant inquiries")
        if not triggers:
            triggers.append("Sub-optimal mobile booking flow causing friction for emergency patients")

        verdict = f"{'Prime target: ' if should_call == 'YES' else 'Lower priority: '}Owner-operated practice with ${estimated_monthly_leakage}/mo estimated leakage and {reviews} verified patient reviews."

        return AIQualificationResult(
            lead_id=lead_id,
            business_name=name,
            would_spend_30min_calling=should_call,
            buying_probability_pct=buying_prob,
            pain_level=pain,
            decision_accessibility=accessibility,
            practice_type=practice_type,
            buying_triggers=triggers[:3],
            sales_manager_verdict=verdict,
            is_a_tier=buying_prob >= 80
        )

    @classmethod
    def calculate_win_probability(
        cls,
        lead_dict: Dict[str, Any],
        technologies: Optional[List[str]] = None,
        memory_learnings: Optional[Dict[str, Any]] = None,
        estimated_monthly_leakage: int = 3500
    ) -> Tuple[int, List[str]]:
        """
        Calculates multi-factor empirical Closing Probability (0-100%) and returns
        reasons based on 5 verified drivers:
        1. Doctor identified (+15%) -> Direct owner reach
        2. High reviews / reputation (+15%) -> Established patient flow to protect
        3. Significant monthly revenue leakage (+$4k/mo) (+15%) -> Urgent economic pain
        4. Lack of modern after-hours booking/chat (+10%) -> Immediate fixable gap
        5. Independent Practice vs DSO (+10% for independent, -25% for corporate DSO)
        Bonus: Memory flywheel precedent (+5% if market precedent exists)
        """
        reasons = []
        prob = 40  # baseline anchor

        # 1. Doctor / Owner Identification
        doc = lead_dict.get("doctor_name")
        if doc:
            prob += 15
            reasons.append(f"Doctor identified ({doc}): Direct access eliminates gatekeeper friction (+15%)")
        else:
            reasons.append("No doctor named: Outreach begins with front-desk office manager (+0%)")

        # 2. Review volume & reputation
        reviews = int(lead_dict.get("review_count") or 0)
        rating = float(lead_dict.get("rating") or 0.0)
        if reviews >= 100:
            prob += 15
            reasons.append(f"Strong patient demand ({reviews} reviews, {rating}★): High inquiry volume losing after-hours leads (+15%)")
        elif reviews >= 30:
            prob += 8
            reasons.append(f"Established local practice ({reviews} reviews): Steady baseline flow (+8%)")
        else:
            reasons.append(f"Low review count ({reviews} reviews): Emerging or quiet clinic (+0%)")

        # 3. Monthly Revenue Leakage
        leakage = int(estimated_monthly_leakage or lead_dict.get("missed_rev_max") or 0)
        if leakage >= 4000:
            prob += 15
            reasons.append(f"High revenue leakage (${leakage:,}/mo): Clear, urgent financial ROI justification (+15%)")
        elif leakage >= 2000:
            prob += 10
            reasons.append(f"Moderate revenue leakage (${leakage:,}/mo): Measurable upside (+10%)")
        else:
            reasons.append("Low estimated revenue leakage: Lower perceived financial urgency (+0%)")

        # 4. Lack of after-hours capture
        tech_list = technologies or lead_dict.get("technologies") or []
        has_chat = any("chat" in t.lower() or "tidio" in t.lower() or "podium" in t.lower() or "livechat" in t.lower() for t in tech_list)
        has_booking = any("booking" in t.lower() or "nexhealth" in t.lower() or "localmed" in t.lower() or "schedul" in t.lower() for t in tech_list)
        if not has_chat and not has_booking:
            prob += 10
            reasons.append("Zero 24/7 web chat or self-scheduling detected: Urgent capture void (+10%)")
        elif not has_chat:
            prob += 5
            reasons.append("No live/AI chat: Evening patient inquiries go unanswered (+5%)")
        else:
            reasons.append("Already utilizing chat or widget tools: Lower capture deficiency (+0%)")

        # 5. Practice Structure (Corporate DSO vs Independent Owner)
        name_lower = (lead_dict.get("name") or "").lower()
        if any(w in name_lower for w in ["heartland", "aspen", "pacific dental", "smile brands", "dso"]):
            prob -= 25
            reasons.append("Corporate DSO detected: Long enterprise procurement cycle and committee signoff (-25%)")
        elif any(w in name_lower for w in ["associates", "group", "partners", "care center"]):
            prob += 5
            reasons.append("Multi-doctor partnership: Multiple stakeholders (+5%)")
        else:
            prob += 10
            reasons.append("Independent owner-operated: Agile single-decision-maker structure (+10%)")

        # Flywheel Bonus: Memory Precedent
        if memory_learnings and memory_learnings.get("won_cases_count", 0) > 0:
            prob += 5
            metro = memory_learnings.get("metro") or "market"
            reasons.append(f"Historical win precedent: System successfully closed similar clinic in {metro} (+5%)")

        final_prob = max(15, min(98, prob))
        return final_prob, reasons
