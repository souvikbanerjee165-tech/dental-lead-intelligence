"""
BANT + MEDDIC Enterprise Lead Qualification Engine.
Adapted from ai-sales-team-claude (MIT License) with domain specialization for dental practices.

Provides structured, explainable enterprise qualification:
1. BANT Score (0-100):
   - Budget (0-25): Estimated revenue, operatory count, premium services (implants, aligners), tech spend.
   - Authority (0-25): Doctor/Owner verified, Practice Manager identified, ownership model.
   - Need (0-25): Missed call reviews, after-hours booking absence, unfilled chair friction.
   - Timeline (0-25): Urgency ranking, hiring signals, seasonal implant surges.
2. MEDDIC Completeness (0-100%):
   - Metrics: Quantified financial leakage ($EV).
   - Economic Buyer: Verified owner dentist.
   - Decision Criteria: EHR / PMS compatibility (Dentrix, Eaglesoft, Weave).
   - Decision Process: Private practice vs DSO governance.
   - Identify Pain: Documented intake bottlenecks.
   - Champion: Office manager or front desk coordinator.
"""

from typing import Dict, Any, List, Optional
import math


class DentalBANTMEDDICScorer:
    """Computes standardized BANT and MEDDIC scores for dental practice prospects."""

    @classmethod
    def score_budget(cls, lead: Dict[str, Any], audit: Dict[str, Any]) -> Dict[str, Any]:
        """Score Budget capability (0-25)."""
        score = 0
        factors = []

        # 1. Tech spend indicators
        tech_stack = audit.get("tech_stack", []) or audit.get("detected_tech", []) or []
        tech_count = len(tech_stack)
        if tech_count >= 4:
            score += 8
            factors.append(f"High tech stack investment ({tech_count} tools detected)")
        elif tech_count >= 2:
            score += 5
            factors.append(f"Moderate software investment ({tech_count} tools detected)")
        elif tech_count >= 1:
            score += 3
            factors.append("Baseline dental software detected")

        # 2. Premium high-ticket services (Implants, Veneers, Sleep Apnea, Invisalign)
        services = lead.get("services", []) or []
        if isinstance(services, str):
            services = [s.strip() for s in services.split(",")]
        
        name_lower = (lead.get("name") or "").lower()
        services_text = " ".join([str(s).lower() for s in services]) + " " + name_lower
        
        high_ticket_matches = 0
        for high_kw in ["implant", "cosmetic", "aligner", "invisalign", "veneer", "sedation", "surgery", "oral"]:
            if high_kw in services_text:
                high_ticket_matches += 1

        if high_ticket_matches >= 3:
            score += 10
            factors.append(f"High-ticket service portfolio ({high_ticket_matches} premium clinical lines)")
        elif high_ticket_matches >= 1:
            score += 6
            factors.append(f"Premium procedures offered ({high_ticket_matches} procedure types)")
        else:
            score += 3
            factors.append("General dentistry practice")

        # 3. Practice Scale & Operatory Estimates
        doctors = lead.get("doctors", []) or []
        doc_count = len(doctors) if isinstance(doctors, list) else 1
        if doc_count >= 3:
            score += 7
            factors.append(f"Multi-provider clinical group ({doc_count}+ doctors)")
        elif doc_count >= 2:
            score += 5
            factors.append(f"Dual-doctor practice ({doc_count} dentists)")
        else:
            score += 4
            factors.append("Solo practitioner owner")

        final_score = min(score, 25)
        return {
            "score": final_score,
            "max": 25,
            "rating": "HIGH" if final_score >= 18 else ("MEDIUM" if final_score >= 12 else "LOW"),
            "factors": factors
        }

    @classmethod
    def score_authority(cls, lead: Dict[str, Any]) -> Dict[str, Any]:
        """Score Authority & Decision-Maker access (0-25)."""
        score = 0
        factors = []

        doc_name = (lead.get("doctor_name") or "").strip()
        is_generic_doctor = doc_name.lower() in ("doctor", "owner", "owner dentist", "practice owner", "")
        
        # 1. Verified Doctor / DDS
        if doc_name and not is_generic_doctor:
            score += 12
            factors.append(f"Verified Owner Dentist identified: {doc_name}")
        elif lead.get("decision_maker_identified"):
            score += 8
            factors.append("Clinical decision maker recognized")
        else:
            score += 4
            factors.append("Unverified practitioner name")

        # 2. Practice Manager / Gatekeeper
        pm_name = (lead.get("gatekeeper_name") or lead.get("office_manager") or "").strip()
        if pm_name:
            score += 8
            factors.append(f"Office Manager mapped: {pm_name}")
        else:
            score += 4
            factors.append("Front desk team unmapped")

        # 3. Ownership Agility (Private Owner = Instant authority vs Multi-clinic DSO)
        is_dso = bool(lead.get("is_dso") or lead.get("dso_affiliated"))
        if not is_dso and doc_name and not is_generic_doctor:
            score += 5
            factors.append("Autonomous private practice owner (Single-call closing authority)")
        else:
            score += 2
            factors.append("Consensus or group decision structure")

        final_score = min(score, 25)
        return {
            "score": final_score,
            "max": 25,
            "rating": "HIGH" if final_score >= 18 else ("MEDIUM" if final_score >= 12 else "LOW"),
            "factors": factors
        }

    @classmethod
    def score_need(cls, lead: Dict[str, Any], audit: Dict[str, Any]) -> Dict[str, Any]:
        """Score Operational & Revenue Pain/Need (0-25)."""
        score = 0
        factors = []

        # 1. Missed Patient Reviews & Friction
        rev_count = int(lead.get("review_count") or 0)
        rating = float(lead.get("rating") or 4.5)
        
        # High volume but moderate rating indicates operational strain
        if rev_count >= 100 and rating < 4.6:
            score += 9
            factors.append(f"Review velocity strain: {rev_count} reviews at {rating}★ indicates phone triage bottlenecks")
        elif rev_count >= 40:
            score += 6
            factors.append(f"Solid patient volume ({rev_count} reviews)")
        else:
            score += 4
            factors.append(f"Emerging local presence ({rev_count} reviews)")

        # 2. Absence of Online Booking / After-Hours Capture
        has_booking = bool(audit.get("has_online_booking") or audit.get("has_booking"))
        has_ai = bool(audit.get("has_ai_chatbot") or audit.get("has_chatbot"))
        
        if not has_booking and not has_ai:
            score += 9
            factors.append("Severe after-hours leakage: Zero online scheduling & zero AI chatbot on website")
        elif not has_booking:
            score += 6
            factors.append("Missed weekend capture: Phone-only intake with no instant booking engine")
        else:
            score += 3
            factors.append("Partial digital booking presence installed")

        # 3. Quantified Trapped Leakage
        leakage = float(lead.get("monthly_leakage") or lead.get("missed_rev_max") or 4200)
        if leakage >= 5000:
            score += 7
            factors.append(f"High monthly chair leakage: ${leakage:,.0f}/mo trapped")
        elif leakage >= 3000:
            score += 5
            factors.append(f"Material revenue loss: ${leakage:,.0f}/mo trapped")
        else:
            score += 3
            factors.append(f"Baseline revenue leakage: ${leakage:,.0f}/mo")

        final_score = min(score, 25)
        return {
            "score": final_score,
            "max": 25,
            "rating": "HIGH" if final_score >= 18 else ("MEDIUM" if final_score >= 12 else "LOW"),
            "factors": factors
        }

    @classmethod
    def score_timeline(cls, lead: Dict[str, Any], audit: Dict[str, Any]) -> Dict[str, Any]:
        """Score Timing & Urgency (0-25)."""
        score = 0
        factors = []

        # 1. Urgency Rating from Scanner / Diagnostics
        urgency = int(lead.get("urgency_score") or lead.get("opportunity_score") or 70)
        if urgency >= 85:
            score += 10
            factors.append(f"Immediate 'Why Now' trigger score ({urgency}/100)")
        elif urgency >= 65:
            score += 7
            factors.append(f"Elevated conversion window ({urgency}/100)")
        else:
            score += 4
            factors.append("Standard sales cadence pacing")

        # 2. Broken Tech / Website Vulnerabilities
        ssl = bool(audit.get("has_ssl", True))
        mobile = bool(audit.get("is_mobile_friendly", True))
        load_time = float(audit.get("load_time_sec") or 1.5)

        if not ssl or not mobile or load_time > 3.0:
            score += 9
            factors.append("Urgent technical defect: Insecure SSL, non-mobile layout, or sluggish load")
        else:
            score += 4
            factors.append("Modern site infrastructure verified")

        # 3. Active Hiring or Market Signals
        if lead.get("market_shift_signal") or lead.get("hiring_receptionist"):
            score += 6
            factors.append("Active receptionist vacancy / recent market competitor shift")
        else:
            score += 3
            factors.append("Stable front desk headcount")

        final_score = min(score, 25)
        return {
            "score": final_score,
            "max": 25,
            "rating": "HIGH" if final_score >= 18 else ("MEDIUM" if final_score >= 12 else "LOW"),
            "factors": factors
        }

    @classmethod
    def assess_meddic(cls, lead: Dict[str, Any], audit: Dict[str, Any], bant_scores: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assess MEDDIC Completeness (0-100%):
        M = Metrics (Quantified Revenue Loss)
        E = Economic Buyer (Doctor/Owner Verified)
        D = Decision Criteria (Software & Workflow Requirements)
        D = Decision Process (Buying Governance)
        I = Identify Pain (Operational Friction)
        C = Champion (Practice Coordinator Identified)
        """
        doc_name = (lead.get("doctor_name") or "").strip()
        is_generic = doc_name.lower() in ("doctor", "owner", "owner dentist", "practice owner", "")
        tech_stack = audit.get("tech_stack", []) or []
        leakage = float(lead.get("monthly_leakage") or lead.get("missed_rev_max") or 4200)

        # 1. Metrics (M)
        metrics_complete = leakage > 0
        metrics_pct = 100 if metrics_complete else 30
        metrics_note = f"Quantified ${leakage:,.0f}/mo in lost weekend & emergency patient bookings"

        # 2. Economic Buyer (E)
        econ_buyer_complete = bool(doc_name and not is_generic)
        econ_buyer_pct = 100 if econ_buyer_complete else 40
        econ_buyer_note = f"Dr. {doc_name}" if econ_buyer_complete else "Owner dentist name unverified"

        # 3. Decision Criteria (D)
        criteria_complete = len(tech_stack) > 0 or not audit.get("has_online_booking")
        criteria_pct = 90 if criteria_complete else 50
        criteria_note = f"Integrates with {', '.join(tech_stack[:2]) or 'standard dental PMS'}"

        # 4. Decision Process (D)
        is_dso = bool(lead.get("is_dso"))
        process_pct = 95 if not is_dso else 60
        process_note = "Private practice owner: 1-step direct decision" if not is_dso else "DSO: 2-step clinical committee"

        # 5. Identify Pain (I)
        pain_complete = not audit.get("has_online_booking") or lead.get("review_count", 0) > 30
        pain_pct = 100 if pain_complete else 50
        pain_note = "Uncaptured after-hours emergency calls & weekend implant booking loss"

        # 6. Champion (C)
        champion_name = lead.get("gatekeeper_name") or lead.get("office_manager")
        champion_pct = 100 if champion_name else 45
        champion_note = f"Office Manager {champion_name}" if champion_name else "Front desk coordinator to be engaged"

        dimensions = {
            "metrics": {"pct": metrics_pct, "label": "Metrics", "detail": metrics_note},
            "economic_buyer": {"pct": econ_buyer_pct, "label": "Economic Buyer", "detail": econ_buyer_note},
            "decision_criteria": {"pct": criteria_pct, "label": "Decision Criteria", "detail": criteria_note},
            "decision_process": {"pct": process_pct, "label": "Decision Process", "detail": process_note},
            "identify_pain": {"pct": pain_pct, "label": "Identify Pain", "detail": pain_note},
            "champion": {"pct": champion_pct, "label": "Champion", "detail": champion_note}
        }

        overall_pct = round(sum(d["pct"] for d in dimensions.values()) / len(dimensions))
        tier = "ENTERPRISE_READY" if overall_pct >= 85 else ("QUALIFIED" if overall_pct >= 65 else "NURTURE")

        return {
            "overall_completeness_pct": overall_pct,
            "tier": tier,
            "dimensions": dimensions
        }

    @classmethod
    def evaluate_lead(cls, lead: Dict[str, Any], audit: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Performs full BANT + MEDDIC evaluation on a prospect."""
        audit_data = audit or lead.get("audit_data") or {}
        if not isinstance(audit_data, dict):
            audit_data = {}

        budget = cls.score_budget(lead, audit_data)
        authority = cls.score_authority(lead)
        need = cls.score_need(lead, audit_data)
        timeline = cls.score_timeline(lead, audit_data)

        total_bant = budget["score"] + authority["score"] + need["score"] + timeline["score"]
        bant_rating = "A_TIER" if total_bant >= 80 else ("B_TIER" if total_bant >= 60 else "C_TIER")

        bant_scores = {
            "total_score": total_bant,
            "max": 100,
            "rating": bant_rating,
            "dimensions": {
                "budget": budget,
                "authority": authority,
                "need": need,
                "timeline": timeline
            }
        }

        meddic = cls.assess_meddic(lead, audit_data, bant_scores)

        # Prescriptive Recommendation
        if total_bant >= 80 and meddic["overall_completeness_pct"] >= 75:
            recommendation = "IMMEDIATE_CALL: Perfect profile. Owner dentist identified, high trapped leakage, and 1-step buying authority."
        elif total_bant >= 65:
            recommendation = "DISCOVERY_CALL: High pain verified. Conduct consultative SPIN call to lock in demo with Doctor."
        else:
            recommendation = "NURTURE: Deliver value-first WhatsApp video teardown before placing direct outbound call."

        return {
            "lead_id": lead.get("id"),
            "clinic_name": lead.get("name"),
            "doctor_name": lead.get("doctor_name"),
            "bant": bant_scores,
            "meddic": meddic,
            "recommendation": recommendation
        }
