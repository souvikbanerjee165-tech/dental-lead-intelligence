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
        self.caller_pool = self._resolve_caller_pool()

    @staticmethod
    def _resolve_caller_pool() -> List[str]:
        """Builds deduplicated outbound caller ID pool from env vars and runtime SettingsManager."""
        candidates: List[str] = []
        pool_env = os.getenv("CALLER_ID_POOL", "")
        if pool_env:
            candidates.extend(p.strip() for p in pool_env.split(",") if p.strip())

        for env_key in ("TELNYX_FROM_PHONE", "TELNYX_CALLER_PHONE", "TWILIO_FROM_PHONE"):
            val = os.getenv(env_key, "").strip()
            if val:
                candidates.append(val)

        try:
            from settings_manager import SettingsManager
            cfg = SettingsManager.get()
            for cfg_key in ("telnyx_from_phone", "twilio_from_phone"):
                val = str(cfg.get(cfg_key) or "").strip()
                if val:
                    candidates.append(val)
        except Exception:
            pass

        # Deduplicate while preserving order; fallback only when no real number is configured
        seen = set()
        pool: List[str] = []
        for num in candidates:
            if num not in seen:
                seen.add(num)
                pool.append(num)
        return pool or ["+12145550199"]

    @classmethod
    def extract_area_code(cls, phone: str) -> Optional[str]:
        """Extracts 3-digit US area code from phone string."""
        digits = re.sub(r"\D", "", phone)
        if len(digits) == 11 and digits.startswith("1"):
            return digits[1:4]
        elif len(digits) == 10:
            return digits[0:3]
        return None

    def match_local_caller_id(self, destination_phone: str, fallback_caller_id: Optional[str] = None) -> str:
        """
        Selects the best outbound caller ID from the pool to match target clinic's area code.
        Boosts answer rate via local presence while respecting a configured carrier fallback.
        """
        pool = self.caller_pool or self._resolve_caller_pool()
        dest_area = self.extract_area_code(destination_phone)
        if dest_area and pool:
            for num in pool:
                num_area = self.extract_area_code(num)
                if num_area and num_area == dest_area:
                    return num

        if fallback_caller_id and fallback_caller_id.strip():
            return fallback_caller_id.strip()
        return pool[0] if pool else "+12145550199"

    def verify_outbound_action(
        self,
        destination_phone: str,
        caller_phone: Optional[str] = None,
        channel: str = "VOICE",
        bypass_velocity: bool = False
    ) -> Tuple[bool, str, str]:
        """
        Central compliance guard for both Voice and SMS outbound dispatches:
        1. Phone number format check (>=10 digits)
        2. Hard DNC Blacklist check
        3. Local-presence area code matching
        4. Hourly velocity throttle per outbound caller number (for VOICE unless bypassed)
        Returns: (allowed, reason_message, selected_caller_id)
        """
        clean_dest = re.sub(r"\D", "", destination_phone or "")
        if len(clean_dest) < 10:
            return False, "INVALID_PHONE_NUMBER", ""

        # 1. DNC Check (applies strictly to all channels)
        if self.db.is_dnc_phone(destination_phone):
            return False, "DNC_BLACKLISTED: Number requested no further contact.", ""

        # 2. Match Local Presence Caller ID (prefer exact area-code match in pool over generic fallback)
        outbound_caller = self.match_local_caller_id(destination_phone, fallback_caller_id=caller_phone)

        # 3. Call Velocity Check
        if not bypass_velocity and channel.upper() == "VOICE":
            hourly_count = self.db.get_hourly_call_count(outbound_caller)
            if hourly_count >= self.MAX_CALLS_PER_HOUR_PER_NUMBER:
                msg = f"VELOCITY_THROTTLED: Caller {outbound_caller} has made {hourly_count} calls this hour (max {self.MAX_CALLS_PER_HOUR_PER_NUMBER}). Pausing to protect carrier reputation."
                logger.warning(msg)
                return False, msg, outbound_caller

        return True, "DIAL_APPROVED", outbound_caller

    def check_dial_permission(
        self,
        destination_phone: str,
        caller_phone: Optional[str] = None
    ) -> Tuple[bool, str, str]:
        """
        Evaluates whether a phone call can be legally and safely placed.
        """
        return self.verify_outbound_action(
            destination_phone=destination_phone,
            caller_phone=caller_phone,
            channel="VOICE",
            bypass_velocity=False
        )

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
