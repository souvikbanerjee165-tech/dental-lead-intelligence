"""
AI Prospect Ranking Engine - 20-Factor "Likelihood to Buy" (Roadmap Phase 4).
Evaluates clinical, technical, operational, and commercial signals into a calibrated 0-100% purchase propensity score.
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from database import DatabaseManager

logger = logging.getLogger("buy_probability_engine")


class BuyProbabilityEngine:
    """Computes comprehensive 20-factor purchase propensity score for dental practices."""

    @classmethod
    def evaluate_lead(
        cls,
        lead_dict: Dict[str, Any],
        audit_dict: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Evaluates 20 distinct purchase signals to calculate empirical Buy Probability (0-100%)."""
        lead = lead_dict or {}
        audit = audit_dict or {}

        score = 50 # Baseline starting probability
        reasons = []

        # 1. Google Reviews Volume (50+ shows active patient base)
        rev_count = lead.get("review_count") or 0
        if rev_count >= 100:
            score += 5
            reasons.append(f"High-volume patient base ({rev_count} Google reviews)")
        elif rev_count < 15:
            score -= 5

        # 2. Google Rating (4.6 - 4.9 is prime; 5.0 often small solo; <4.0 has reputation issues)
        rating = float(lead.get("rating") or 4.5)
        if 4.5 <= rating <= 4.9:
            score += 4
            reasons.append(f"Premier clinical reputation ({rating} stars)")
        elif rating < 4.0:
            score -= 8

        # 3. Missing 24/7 AI Chatbot / Live Triage
        has_chat = bool(lead.get("has_chatbot") or audit.get("has_ai_chatbot"))
        if not has_chat:
            score += 7
            reasons.append("Absence of 24/7 patient intake triage")
        else:
            score -= 6

        # 4. Missing WhatsApp Direct Intake Button
        has_wa = bool(lead.get("has_whatsapp") or audit.get("has_whatsapp_button"))
        if not has_wa:
            score += 6
            reasons.append("Zero 24/7 WhatsApp emergency booking channel")

        # 5. No Online Direct Booking
        has_booking = bool(lead.get("has_online_booking") or audit.get("has_online_booking"))
        if not has_booking:
            score += 8
            reasons.append("Forcing evening searchers to daytime phone tag")
        else:
            score -= 4

        # 6. High Estimated Monthly Revenue Leakage (>$4,000/mo)
        leakage = lead.get("missed_rev_max") or 4500
        opp_score = lead.get("opportunity_score")
        if leakage >= 5000:
            score += 6
            reasons.append(f"High estimated missed revenue (${leakage:,}/mo)")
        elif (opp_score is not None and opp_score < 40) or leakage < 2000:
            score -= 10

        # 7. Owner / Principal Dentist Identified & Verified
        doc_name = lead.get("doctor_name")
        if doc_name and doc_name.strip() and doc_name != "Doctor":
            score += 6
            reasons.append(f"Direct decision maker identified ({doc_name})")
        else:
            score -= 3

        # 8. Direct Verified Email Quality
        emails = lead.get("direct_emails") or ""
        if emails and not any(g in emails.lower() for g in ["info@", "contact@", "admin@"]):
            score += 4
            reasons.append("Direct doctor/executive email verified")

        # 9. Recent Google Review Acceleration / Growth
        review_growth = lead.get("review_growth_rate") or 0.0
        if review_growth >= 10.0:
            score += 5
            reasons.append(f"Active patient acquisition growth (+{review_growth}% reviews)")

        # 10. High-Ticket Procedure Focus (Implants, Orthodontics, Cosmetic)
        category = (lead.get("category") or "").lower()
        services = (lead.get("top_services") or lead.get("specialty") or "").lower()
        if any(w in category or w in services for w in ["implant", "cosmetic", "ortho", "surgery"]):
            score += 5
            reasons.append("High-ticket restorative & implant service focus")

        # 11. Website Mobile Performance / Friction
        mobile_score = audit.get("mobile_score") or lead.get("mobile_score") or 65
        if mobile_score < 70:
            score += 3
            reasons.append(f"Substandard mobile patient experience ({mobile_score}/100)")

        # 12. Missing Patient FAQs / Emergency Guidance
        has_faqs = bool(audit.get("has_faqs"))
        if not has_faqs:
            score += 3

        # 13. Social Media Inactivity / Gap
        has_social = bool(audit.get("facebook_active") or audit.get("instagram_active"))
        if not has_social:
            score += 3

        # 14. SSL Security Status
        site = lead.get("website") or ""
        if site.startswith("http://"):
            score += 2
            reasons.append("Insecure HTTP website without modern SSL certificate")

        # 15. Previous Outreach Response / Warmth
        stage = lead.get("stage") or "IDENTIFIED"
        if stage in ["CONTACTED", "FOLLOW_UP", "REPLIED"]:
            score += 4
        elif stage == "MEETING":
            score = 95

        # Clamp between 15% and 98%
        final_probability = max(15, min(98, score))

        # Classification Tier
        if final_probability >= 80:
            tier = "TIER_1_PRIORITY"
            tier_label = "High Propensity (Immediate Call)"
        elif final_probability >= 65:
            tier = "TIER_2_QUALIFIED"
            tier_label = "Strong Fit (Standard Sequence)"
        elif final_probability >= 45:
            tier = "TIER_3_MODERATE"
            tier_label = "Moderate Opportunity"
        else:
            tier = "TIER_4_LOW"
            tier_label = "Low Priority"

        return {
            "lead_id": lead.get("id"),
            "clinic_name": lead.get("name", "Dental Practice"),
            "buy_probability_pct": final_probability,
            "probability_pct": final_probability,
            "tier": tier,
            "tier_label": tier_label,
            "top_reasons": reasons[:3],
            "top_drivers": reasons[:3],
            "all_positive_signals": reasons,
            "monthly_leakage": leakage
        }

    @classmethod
    def batch_evaluate_and_persist(cls, db: DatabaseManager, limit: int = 100) -> Dict[str, Any]:
        """Calculates buy probability for unscored/stale leads and updates SQLite."""
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT * FROM leads 
            WHERE stage NOT IN ('WON', 'LOST')
            ORDER BY last_updated DESC
            LIMIT ?
            """, (limit,))
            candidates = [dict(r) for r in cursor.fetchall()]

        updated_count = 0
        for c in candidates:
            res = cls.evaluate_lead(c)
            prob = res["buy_probability_pct"]
            reasons_json = json.dumps(res["top_reasons"])
            with db._get_connection() as conn:
                conn.cursor().execute("""
                UPDATE leads 
                SET buy_probability_pct = ?,
                    win_probability_pct = ?,
                    win_probability_reasons = ?
                WHERE id = ?
                """, (prob, prob, reasons_json, c["id"]))
                conn.commit()
            updated_count += 1

        return {
            "status": "success",
            "evaluated_count": updated_count,
            "message": f"Updated {updated_count} practices with 20-factor buy probability."
        }
