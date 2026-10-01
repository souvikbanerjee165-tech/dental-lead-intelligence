"""
EHR & Patient Portal Tech-Stack Sniffer.
Detects dental practice management systems (Dentrix, Eaglesoft, Open Dental, Curve)
and front-office engagement platforms (Weave, NexHealth, Modento, Podium, Birdeye)
from practice website HTML, portal endpoints, and embedded script tags.
"""

import re
import logging
from typing import Dict, Any, List, Optional
import urllib.parse

logger = logging.getLogger("ehr_sniffer")

# Fingerprinting signatures for dental EHR / PMS and patient communication systems
TECH_SIGNATURES = {
    "dentrix": {
        "name": "Dentrix (Henry Schein)",
        "category": "EHR_PMS",
        "patterns": [
            r"dentrixascend\.com",
            r"dentrix\.com",
            r"patientconnections\.com",
            r"quickbill\.com",
            r"ehs-dentrix",
            r"dexis"
        ],
        "battlecard_key": "dentrix",
        "pitch_angle": "Integrates directly alongside Dentrix to capture after-hours missed calls that Dentrix voicemail drops."
    },
    "eaglesoft": {
        "name": "Eaglesoft (Patterson Dental)",
        "category": "EHR_PMS",
        "patterns": [
            r"patientviewer\.com",
            r"eaglesoft",
            r"pattersondental\.com",
            r"patterson-portal",
            r"fuse-eaglesoft"
        ],
        "battlecard_key": "dentrix",
        "pitch_angle": "Plugs into Eaglesoft patient booking, automatically recovering weekend emergencies into open chair slots."
    },
    "opendental": {
        "name": "Open Dental",
        "category": "EHR_PMS",
        "patterns": [
            r"opendentalcloud\.com",
            r"opendental\.com",
            r"open-dental",
            r"web-sched",
            r"odmobile"
        ],
        "battlecard_key": "opendental",
        "pitch_angle": "Connects natively with Open Dental so WhatsApp-scheduled patients flow directly into the appointment book."
    },
    "curvedental": {
        "name": "Curve Dental",
        "category": "EHR_PMS",
        "patterns": [
            r"curvedental\.com",
            r"curve-hero",
            r"curvedms\.com"
        ],
        "battlecard_key": "curvedental",
        "pitch_angle": "Complements Curve Dental cloud PMS with 24/7 autonomous mobile patient acquisition on WhatsApp."
    },
    "nexhealth": {
        "name": "NexHealth",
        "category": "PATIENT_ENGAGEMENT",
        "patterns": [
            r"nexhealth\.com",
            r"nexhealth-widget",
            r"assets\.nexhealth"
        ],
        "battlecard_key": "nexhealth",
        "pitch_angle": "Replaces clunky multi-step web forms with high-converting 30-second conversational WhatsApp intake."
    },
    "weave": {
        "name": "Weave",
        "category": "COMMUNICATIONS",
        "patterns": [
            r"getweave\.com",
            r"weave-widget",
            r"weave-phone"
        ],
        "battlecard_key": "weave",
        "pitch_angle": "Works outside office hours when Weave desk phones roll to voicemail, catching emergency toothaches."
    },
    "modento": {
        "name": "Modento / Dental Intelligence",
        "category": "PATIENT_ENGAGEMENT",
        "patterns": [
            r"modento\.io",
            r"dentalintel\.com",
            r"modento-form"
        ],
        "battlecard_key": "nexhealth",
        "pitch_angle": "Adds automated after-hours WhatsApp patient capture on top of daytime Modento forms."
    },
    "podium": {
        "name": "Podium",
        "category": "COMMUNICATIONS",
        "patterns": [
            r"podium\.com",
            r"connect\.podium\.com"
        ],
        "battlecard_key": "podium",
        "pitch_angle": "Upgrades basic SMS review texting into 24/7 intelligent clinical triage and instant booking."
    },
    "birdeye": {
        "name": "Birdeye",
        "category": "REVIEWS_CHAT",
        "patterns": [
            r"birdeye\.com",
            r"birdeye-chat"
        ],
        "battlecard_key": "birdeye",
        "pitch_angle": "Replaces generic browser webchat widgets that drop when patients lock their phone with persistent WhatsApp."
    }
}


class EHRSniffer:
    """Detects dental PMS and engagement platforms from website HTML, portal links, and scripts."""

    @classmethod
    def sniff_html(cls, html_content: str, website_url: str = "") -> Dict[str, Any]:
        """
        Analyzes HTML content and URL patterns to identify practice technology stack.
        """
        if not html_content:
            return {
                "detected_pms": None,
                "detected_tools": [],
                "primary_software": "Legacy On-Premise",
                "battlecard_recommendation": "dentrix",
                "confidence_score": 0.4,
                "summary": "No cloud patient portal detected. Practice likely uses legacy on-premise Dentrix or Eaglesoft."
            }

        html_lower = html_content.lower()
        found_tools = []
        primary_pms = None

        for key, tech in TECH_SIGNATURES.items():
            matched = False
            for pat in tech["patterns"]:
                if re.search(pat, html_lower):
                    matched = True
                    break

            if matched:
                found_tools.append({
                    "key": key,
                    "name": tech["name"],
                    "category": tech["category"],
                    "battlecard_key": tech["battlecard_key"],
                    "pitch_angle": tech["pitch_angle"]
                })
                if tech["category"] == "EHR_PMS" and not primary_pms:
                    primary_pms = tech

        # Determine primary battlecard target
        if primary_pms:
            primary_name = primary_pms["name"]
            battlecard_target = primary_pms["battlecard_key"]
            confidence = 0.95
            summary = f"Detected {primary_name} integration. Use the {primary_pms['battlecard_key'].upper()} coexistence pitch."
        elif found_tools:
            primary_name = found_tools[0]["name"]
            battlecard_target = found_tools[0]["battlecard_key"]
            confidence = 0.85
            summary = f"Detected {primary_name}. Pitch how WhatsApp captures calls where this tool falls short."
        else:
            primary_name = "Dentrix / Eaglesoft (Standard US Setup)"
            battlecard_target = "dentrix"
            confidence = 0.50
            summary = "No third-party patient portal detected. Standard Dentrix/Eaglesoft on-premise coexistence pitch applies."

        return {
            "detected_pms": primary_pms["name"] if primary_pms else None,
            "detected_tools": [t["name"] for t in found_tools],
            "primary_software": primary_name,
            "battlecard_recommendation": battlecard_target,
            "confidence_score": confidence,
            "summary": summary,
            "details": found_tools
        }
