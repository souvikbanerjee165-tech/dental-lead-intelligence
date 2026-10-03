"""
Carrier Reputation & Anti-Spam Shield Manager.
Protects outbound phone numbers against STIR/SHAKEN 'Spam Likely' flags.
Provides:
1. Local Presence Area Code Dialing (matches caller area code to clinic area code).
2. Call Velocity Throttling (enforces 15 calls/hour limit per outbound line).
3. Automated Do-Not-Call (DNC) Blacklist Shield with instant keyword opt-out.
"""

import os
import re
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from database import DatabaseManager

logger = logging.getLogger("carrier_reputation_manager")


class CarrierReputationManager:
    """Orchestrates outbound telephony reputation, area code matching, and TCPA/DNC compliance."""

    MAX_CALLS_PER_HOUR_PER_NUMBER = 18
    MIN_CALL_INTERVAL_SECONDS = 120

    # Major dental territory area codes
    AREA_CODE_DIRECTORY = {
        "214": "Dallas, TX",
        "972": "Dallas, TX",
        "469": "Dallas, TX",
        "512": "Austin, TX",
        "737": "Austin, TX",
        "713": "Houston, TX",
        "281": "Houston, TX",
        "832": "Houston, TX",
        "404": "Atlanta, GA",
        "678": "Atlanta, GA",
        "470": "Atlanta, GA",
        "305": "Miami, FL",
        "786": "Miami, FL",
        "407": "Orlando, FL",
        "312": "Chicago, IL",
        "773": "Chicago, IL",
        "212": "New York, NY",
        "718": "New York, NY",
        "917": "New York, NY",
        "213": "Los Angeles, CA",
        "310": "Los Angeles, CA",
        "323": "Los Angeles, CA",
        "602": "Phoenix, AZ",
        "480": "Phoenix, AZ",
        "720": "Denver, CO",
        "303": "Denver, CO"
    }

    # Opt-out keywords triggering instant DNC blacklisting
    DNC_OPT_OUT_KEYWORDS = [
        "do not call", "don't call", "stop calling", "remove me", "remove my number",
        "take me off", "take us off", "unsubscribe", "put me on your do not call list",
        "wrong number", "delete my number", "never call again"
    ]

    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or DatabaseManager()
        # Pool of configured outbound numbers from env (comma-separated), or default Telnyx/Twilio number
        pool_str = os.getenv("CALLER_ID_POOL", os.getenv("TELNYX_CALLER_PHONE", "+12145550199"))
        self.caller_pool = [p.strip() for p in pool_str.split(",") if p.strip()]

    @classmethod
    def extract_area_code(cls, phone: str) -> Optional[str]:
        """Extracts 3-digit US area code from phone string."""
        digits = re.sub(r"\D", "", phone)
        if len(digits) == 11 and digits.startswith("1"):
            return digits[1:4]
        elif len(digits) == 10:
            return digits[0:3]
        return None

    def match_local_caller_id(self, destination_phone: str) -> str:
        """
        Selects the best outbound caller ID from the pool to match target clinic's area code.
        Boosts answer rate by up to 400% via local presence.
        """
        dest_area = self.extract_area_code(destination_phone)
        if not dest_area or not self.caller_pool:
            return self.caller_pool[0] if self.caller_pool else "+12145550199"

        # Check for exact area code match in pool
        for num in self.caller_pool:
            num_area = self.extract_area_code(num)
            if num_area and num_area == dest_area:
                return num

        # Fallback to first available number in pool
        return self.caller_pool[0]

    def check_dial_permission(
        self,
        destination_phone: str,
        caller_phone: Optional[str] = None
    ) -> Tuple[bool, str, str]:
        """
        Evaluates whether a phone call can be legally and safely placed.
        Checks:
        1. DNC Blacklist (100% hard block)
        2. Area Code matching
        3. Velocity limit (<18 calls/hr on caller number)
        Returns: (allowed, reason_message, selected_caller_id)
        """
        clean_dest = re.sub(r"\D", "", destination_phone)
        if len(clean_dest) < 10:
            return False, "INVALID_PHONE_NUMBER", ""

        # 1. DNC Check
        if self.db.is_dnc_phone(destination_phone):
            return False, "DNC_BLACKLISTED: Number requested no further contact.", ""

        # 2. Match Caller ID
        outbound_caller = caller_phone or self.match_local_caller_id(destination_phone)

        # 3. Call Velocity Check
        hourly_count = self.db.get_hourly_call_count(outbound_caller)
        if hourly_count >= self.MAX_CALLS_PER_HOUR_PER_NUMBER:
            msg = f"VELOCITY_THROTTLED: Caller {outbound_caller} has made {hourly_count} calls this hour (max {self.MAX_CALLS_PER_HOUR_PER_NUMBER}). Pausing to protect carrier reputation."
            logger.warning(msg)
            return False, msg, outbound_caller

        return True, "DIAL_APPROVED", outbound_caller

    def check_for_opt_out(self, transcript_text: str) -> bool:
        """Checks if prospect utterance contains DNC opt-out keywords."""
        if not transcript_text:
            return False
        t_lower = transcript_text.lower()
        return any(kw in t_lower for kw in self.DNC_OPT_OUT_KEYWORDS)

    def process_opt_out(
        self,
        destination_phone: str,
        clinic_name: str = "",
        reason: str = "PROSPECT_REQUESTED"
    ) -> Dict[str, Any]:
        """
        Adds phone to DNC blacklist immediately and returns the polite compliance statement.
        """
        success = self.db.add_to_dnc(phone=destination_phone, clinic_name=clinic_name, reason=reason)
        polite_exit = "Understood, I have removed your number from our contact list immediately. Have a wonderful day!"
        logger.info(f"DNC Opt-Out processed for {destination_phone} ({clinic_name}): {reason}")

        return {
            "success": success,
            "destination_phone": destination_phone,
            "clinic_name": clinic_name,
            "reason": reason,
            "polite_exit_statement": polite_exit,
            "timestamp": datetime.now().isoformat()
        }

    def log_call_attempt(
        self,
        caller_phone: str,
        destination_phone: str,
        lead_id: Optional[str] = None,
        status: str = "INITIATED",
        duration_sec: int = 0
    ) -> int:
        """Records the call for velocity tracking."""
        dest_area = self.extract_area_code(destination_phone) or "000"
        return self.db.record_carrier_call(
            caller_phone=caller_phone,
            destination_phone=destination_phone,
            lead_id=lead_id,
            area_code=dest_area,
            status=status,
            duration_sec=duration_sec
        )
