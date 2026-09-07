"""
Data Quality & Completeness Scoring Engine.
Evaluates the commercial richness of every prospect record to prioritize enrichment
and prevent dialing un-researched dental practices.
"""

from typing import Dict, Any, List, Tuple


class DataQualityEngine:
    """Computes a 0 - 100% data completeness rating for dental leads."""

    @classmethod
    def evaluate(cls, lead: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluates lead completeness across 7 commercial criteria:
        - Doctor Name (25 pts)
        - Active Phone (20 pts)
        - Direct Email (15 pts)
        - Valid Website (15 pts)
        - Coordinates Lat/Lng (10 pts)
        - Review Count >= 10 (10 pts)
        - Rating >= 4.0 (5 pts)
        """
        score = 0
        missing = []
        checks = {}

        # 1. Doctor / Owner Identified (25 pts)
        doc = lead.get("doctor_name")
        if doc and len(doc.strip()) > 3:
            score += 25
            checks["doctor_identified"] = True
        else:
            missing.append("Doctor / Practice Principal")
            checks["doctor_identified"] = False

        # 2. Phone Number (20 pts)
        phone = lead.get("phone")
        if phone and any(c.isdigit() for c in str(phone)):
            score += 20
            checks["phone_present"] = True
        else:
            missing.append("Practice Phone Number")
            checks["phone_present"] = False

        # 3. Direct Email (15 pts)
        email = lead.get("direct_emails") or lead.get("email")
        if email and "@" in str(email):
            score += 15
            checks["email_present"] = True
        else:
            missing.append("Direct Practice Email")
            checks["email_present"] = False

        # 4. Valid Website (15 pts)
        website = lead.get("website")
        if website and ("." in str(website) and len(str(website)) > 5):
            score += 15
            checks["website_present"] = True
        else:
            missing.append("Verified Website")
            checks["website_present"] = False

        # 5. Geocoding Lat/Lng Coordinates (10 pts)
        lat = lead.get("latitude")
        lng = lead.get("longitude")
        if lat and lng and (float(lat) != 0.0 or float(lng) != 0.0):
            score += 10
            checks["coordinates_present"] = True
        else:
            checks["coordinates_present"] = False

        # 6. Review Count Depth (10 pts)
        reviews = int(lead.get("review_count") or lead.get("reviews_count") or 0)
        if reviews >= 10:
            score += 10
            checks["review_volume"] = True
        else:
            missing.append("Patient Review Volume (<10)")
            checks["review_volume"] = False

        # 7. Rating (5 pts)
        rating = float(lead.get("rating") or 0.0)
        if rating >= 4.0:
            score += 5
            checks["rating_reputation"] = True
        else:
            checks["rating_reputation"] = False

        score = min(100, max(0, score))

        if score >= 85:
            tier = "EXCELLENT"
            color = "text-emerald-400 border-emerald-500/30 bg-emerald-500/10"
        elif score >= 60:
            tier = "GOOD"
            color = "text-blue-400 border-blue-500/30 bg-blue-500/10"
        elif score >= 40:
            tier = "FAIR"
            color = "text-amber-400 border-amber-500/30 bg-amber-500/10"
        else:
            tier = "NEEDS_ENRICHMENT"
            color = "text-rose-400 border-rose-500/30 bg-rose-500/10"

        return {
            "data_quality_score": score,
            "quality_tier": tier,
            "badge_color": color,
            "missing_fields": missing,
            "checks": checks
        }


def calculate_data_completeness(lead: Dict[str, Any]) -> Tuple[int, str, List[str]]:
    """Helper function returning (score, tier, missing_fields)."""
    res = DataQualityEngine.evaluate(lead)
    return res["data_quality_score"], res["quality_tier"], res["missing_fields"]
