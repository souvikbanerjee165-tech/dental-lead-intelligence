"""
Website Change Detection & Trigger Event Engine.
Tracks changes in dental practice websites (HTML, screenshots, tech stack, reviews)
and calculates dynamic Urgency Scores (Why Now?) to prioritize outreach timing.
"""

import hashlib
import json
import logging
import re
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple

logger = logging.getLogger("trigger_engine")


def compute_html_hash(html_content: str) -> str:
    """Calculates SHA256 hash of normalized HTML content."""
    if not html_content:
        return ""
    # Strip tag spacing and whitespace to ignore superficial formatting
    normalized = re.sub(r">\s+<", "><", html_content.strip())
    normalized = re.sub(r"\s+", " ", normalized)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def compute_tech_hash(tech_names: List[str]) -> str:
    """Calculates SHA256 hash of sorted technology names."""
    if not tech_names:
        return ""
    normalized = ",".join(sorted(set(t.strip().lower() for t in tech_names if t)))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


class TriggerEngine:
    """Detects website and business changes, generates 'Why Now?' signals, and computes Urgency Scores."""

    TRIGGER_TYPES = {
        "WEBSITE_REDESIGNED": {"title": "Website Redesigned", "severity": "HIGH", "icon": "🎨"},
        "TECH_STACK_ALTERED": {"title": "Tech Stack Changed", "severity": "MEDIUM", "icon": "⚙️"},
        "NEW_BOOKING_TOOL": {"title": "New Booking System Added", "severity": "MEDIUM", "icon": "📅"},
        "LOST_CHAT_TOOL": {"title": "Live Chat Removed", "severity": "HIGH", "icon": "⚠️"},
        "RATING_DROP": {"title": "Google Rating Dropped", "severity": "CRITICAL", "icon": "📉"},
        "REVIEW_SURGE": {"title": "Recent Review Velocity Surge", "severity": "HIGH", "icon": "🚀"},
        "NEW_DOCTOR_FOUND": {"title": "New Doctor Identified", "severity": "HIGH", "icon": "👨‍⚕️"},
        "HIRING_SIGNALS": {"title": "Receptionist Hiring Detected", "severity": "CRITICAL", "icon": "💼"},
        "AFTER_HOURS_LEAKAGE": {"title": "High After-Hours Traffic Leakage", "severity": "HIGH", "icon": "🌙"},
    }

    @classmethod
    def detect_changes(
        cls,
        old_lead: Dict[str, Any],
        new_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Compares an existing lead record against fresh audit data.
        Returns a list of detected Trigger Events.
        """
        detected_triggers = []
        now_iso = datetime.now().isoformat()

        # 1. Check HTML Content Hash Change (Website Redesign)
        old_hash = old_lead.get("html_hash") or old_lead.get("content_hash")
        new_hash = new_data.get("html_hash") or new_data.get("content_hash")
        if old_hash and new_hash and old_hash != new_hash:
            detected_triggers.append({
                "event_type": "WEBSITE_REDESIGNED",
                "title": "Practice Website Redesigned",
                "description": "HTML structure changed significantly. Practice is actively investing in digital presence.",
                "severity": "HIGH",
                "detected_at": now_iso,
                "old_val": old_hash,
                "new_val": new_hash
            })

        # 2. Check Tech Stack Hash Change
        old_tech = old_lead.get("tech_hash")
        new_tech = new_data.get("tech_hash")
        if old_tech and new_tech and old_tech != new_tech:
            detected_triggers.append({
                "event_type": "TECH_STACK_ALTERED",
                "title": "Practice Technology Stack Updated",
                "description": "Detected software changes on website. Verify if AI tools or booking widgets were modified.",
                "severity": "MEDIUM",
                "detected_at": now_iso,
                "old_val": old_tech,
                "new_val": new_tech
            })

        # 3. Check Google Reviews Surge
        old_reviews = int(old_lead.get("review_count") or 0)
        new_reviews = int(new_data.get("review_count") or old_reviews)
        if new_reviews > old_reviews + 3:
            diff = new_reviews - old_reviews
            detected_triggers.append({
                "event_type": "REVIEW_SURGE",
                "title": f"Recent Review Velocity (+{diff} New Reviews)",
                "description": f"Patient volume is accelerating with {diff} new reviews. High front-desk call load.",
                "severity": "HIGH",
                "detected_at": now_iso,
                "old_val": str(old_reviews),
                "new_val": str(new_reviews)
            })

        # 4. Check Google Rating Drop
        old_rating = float(old_lead.get("rating") or 0.0)
        new_rating = float(new_data.get("rating") or old_rating)
        if old_rating > 0 and new_rating > 0 and (old_rating - new_rating >= 0.2):
            detected_triggers.append({
                "event_type": "RATING_DROP",
                "title": f"Google Rating Slipped ({old_rating} → {new_rating})",
                "description": "Rating drop signals patient dissatisfaction or missed front-desk communication. Receptive to solutions.",
                "severity": "CRITICAL",
                "detected_at": now_iso,
                "old_val": str(old_rating),
                "new_val": str(new_rating)
            })

        # 5. Check Doctor Newly Discovered
        old_doc = old_lead.get("doctor_name")
        new_doc = new_data.get("doctor_name")
        if not old_doc and new_doc:
            detected_triggers.append({
                "event_type": "NEW_DOCTOR_FOUND",
                "title": f"Practice Principal Identified: {new_doc}",
                "description": f"Successfully mapped practice owner/lead clinician. Enables direct peer-to-peer outreach.",
                "severity": "HIGH",
                "detected_at": now_iso,
                "old_val": None,
                "new_val": new_doc
            })

        return detected_triggers

    @classmethod
    def calculate_urgency_score(
        cls,
        lead: Dict[str, Any],
        triggers: Optional[List[Dict[str, Any]]] = None
    ) -> int:
        """
        Calculates Urgency Score (0 - 100) representing 'Why Contact Today'.
        Synthesizes:
        - Front-desk friction & missed revenue (25%)
        - Decision-maker accessibility (20%)
        - Trigger events & timing signals (25%)
        - Google review velocity & active patient base (15%)
        - Tech stack readiness & lack of AI booking (15%)
        """
        score = 40  # Baseline

        # 1. Missed Revenue / After-Hours Bleed (up to 20 pts)
        missed_max = int(lead.get("missed_rev_max") or 0)
        if missed_max >= 6000:
            score += 20
        elif missed_max >= 3000:
            score += 15
        elif missed_max >= 1500:
            score += 10

        # 2. Decision Maker Identified (up to 15 pts)
        if lead.get("doctor_name"):
            score += 10
            if lead.get("direct_emails"):
                score += 5

        # 3. Patient Volume / Review Count (up to 10 pts)
        reviews = int(lead.get("review_count") or 0)
        if reviews >= 100:
            score += 10
        elif reviews >= 40:
            score += 7
        elif reviews >= 10:
            score += 4

        # 4. Opportunity Score Alignment (up to 10 pts)
        opp_score = int(lead.get("opportunity_score") or 0)
        if opp_score >= 80:
            score += 10
        elif opp_score >= 65:
            score += 6

        # 5. Trigger Events Bonus (up to 20 pts)
        active_triggers = triggers or []
        for t in active_triggers:
            sev = t.get("severity", "MEDIUM")
            if sev == "CRITICAL":
                score += 12
            elif sev == "HIGH":
                score += 8
            else:
                score += 4

        return min(100, max(20, score))

    @classmethod
    def generate_why_now_reasons(
        cls,
        lead: Dict[str, Any],
        triggers: Optional[List[Dict[str, Any]]] = None
    ) -> List[str]:
        """
        Generates 3 to 4 concise, high-impact 'Why Now?' timing triggers
        for the sales rep before dialing.
        """
        reasons = []
        name = lead.get("name", "Practice")
        doc = lead.get("doctor_name")
        reviews = int(lead.get("review_count") or 0)
        rating = float(lead.get("rating") or 4.8)
        missed_min = int(lead.get("missed_rev_min") or 2500)
        missed_max = int(lead.get("missed_rev_max") or 5500)

        # Trigger 1: Active Signals / Changes
        active_triggers = triggers or []
        if active_triggers:
            top_trigger = active_triggers[0]
            reasons.append(f"🔥 {top_trigger.get('title')}: {top_trigger.get('description', '')}")

        # Trigger 2: Decision Maker Direct Line
        if doc:
            reasons.append(f"👨‍⚕️ Direct Access: Lead clinician {doc} is identified; bypasses front-desk gatekeeper on morning calls.")
        else:
            reasons.append(f"📞 Timing: Active business line ({lead.get('phone', 'Listed')}) during high-intent morning scheduling window.")

        # Trigger 3: Commercial Leakage
        if missed_max > 0:
            reasons.append(f"💸 Bleeding Patients: Estimated ${missed_min:,} - ${missed_max:,}/mo escaping due to uncaptured after-hours patient inquiries.")
        else:
            reasons.append("🌙 After-Hours Gap: No automated 24/7 instant chat or SMS booking fallback on website.")

        # Trigger 4: Review Volume vs Response Friction
        if reviews >= 50:
            reasons.append(f"📈 High Inbound Flow: {reviews} Google reviews ({rating}★) indicate busy chairs; front desk likely drops 15-25% of inbound calls.")
        else:
            reasons.append("⚡ Competitive Vulnerability: Nearby area dental clinics actively marketing online booking; easy conversion pitch.")

        return reasons[:4]
