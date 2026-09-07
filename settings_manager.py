"""
Runtime Agency Settings & Configuration Manager.
Allows dynamic adjustment of scraping targets, thresholds, unit economics,
and rate limits directly from the dashboard without modifying source code,
with strict boundary validation preventing corrupted operational state.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from config import OUTPUT_DIR

logger = logging.getLogger("settings_manager")

DEFAULT_SETTINGS_FILE = OUTPUT_DIR / "settings.json"

DEFAULT_SETTINGS = {
    "target_cities": [
        "Austin, TX",
        "Dallas, TX",
        "Houston, TX",
        "San Antonio, TX",
        "Fort Worth, TX",
        "Denver, CO",
        "Phoenix, AZ",
        "Atlanta, GA",
        "Charlotte, NC",
        "Tampa, FL"
    ],
    "min_reviews_threshold": 15,
    "min_buying_probability": 65,
    "default_case_value": 900,
    "default_monthly_retainer": 299,
    "daemon_interval_hours": 6.0,
    "daemon_limit_per_city": 8,
    "rate_limit_min_delay_sec": 2.0,
    "rate_limit_max_delay_sec": 4.5,
    "auto_backup_enabled": True,
    "agency_name": "Apex Practice Growth Partners",
    "require_auth_pin": False,
    "auth_pin": ""
}


class SettingsManager:
    """Provides read/write persistence for runtime operational configurations."""

    def __init__(self, settings_file: Path = DEFAULT_SETTINGS_FILE):
        self.settings_file = Path(settings_file)

    def get_settings(self) -> Dict[str, Any]:
        return self._get_settings_impl(self.settings_file)

    def update_settings(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        return self._update_settings_impl(self.settings_file, updates)

    @classmethod
    def get(cls, settings_file: Path = DEFAULT_SETTINGS_FILE) -> Dict[str, Any]:
        return cls._get_settings_impl(Path(settings_file))

    @classmethod
    def update(cls, updates: Dict[str, Any], settings_file: Path = DEFAULT_SETTINGS_FILE) -> Dict[str, Any]:
        return cls._update_settings_impl(Path(settings_file), updates)

    @staticmethod
    def validate_updates(current: Dict[str, Any], updates: Dict[str, Any]) -> None:
        """Enforces commercial boundaries on configuration updates."""
        if "min_buying_probability" in updates:
            try:
                val = int(updates["min_buying_probability"])
            except (ValueError, TypeError):
                raise ValueError("Buying probability must be a valid integer")
            if not (0 <= val <= 100):
                raise ValueError(f"Buying probability must be between 0% and 100%, got {val}%")

        if "min_reviews_threshold" in updates:
            try:
                val = int(updates["min_reviews_threshold"])
            except (ValueError, TypeError):
                raise ValueError("Reviews threshold must be an integer")
            if not (0 <= val <= 10000):
                raise ValueError(f"Minimum reviews threshold must be between 0 and 10,000, got {val}")

        if "default_case_value" in updates:
            try:
                val = int(updates["default_case_value"])
            except (ValueError, TypeError):
                raise ValueError("Case value must be an integer")
            if not (50 <= val <= 50000):
                raise ValueError(f"Average case value must be between $50 and $50,000, got ${val}")

        if "default_monthly_retainer" in updates:
            try:
                val = int(updates["default_monthly_retainer"])
            except (ValueError, TypeError):
                raise ValueError("Monthly retainer must be an integer")
            if not (10 <= val <= 20000):
                raise ValueError(f"Monthly retainer must be between $10 and $20,000, got ${val}")

        if "daemon_interval_hours" in updates:
            try:
                val = float(updates["daemon_interval_hours"])
            except (ValueError, TypeError):
                raise ValueError("Daemon interval must be a number")
            if not (0.1 <= val <= 168.0):
                raise ValueError(f"Daemon interval must be between 0.1 and 168.0 hours, got {val}h")

        if "daemon_limit_per_city" in updates:
            try:
                val = int(updates["daemon_limit_per_city"])
            except (ValueError, TypeError):
                raise ValueError("Daemon limit must be an integer")
            if not (1 <= val <= 500):
                raise ValueError(f"Daemon limit per city must be between 1 and 500, got {val}")

        if "rate_limit_min_delay_sec" in updates or "rate_limit_max_delay_sec" in updates:
            min_d = float(updates.get("rate_limit_min_delay_sec", current.get("rate_limit_min_delay_sec", 2.0)))
            max_d = float(updates.get("rate_limit_max_delay_sec", current.get("rate_limit_max_delay_sec", 4.5)))
            if not (0.1 <= min_d <= 60.0 and 0.1 <= max_d <= 60.0):
                raise ValueError(f"Rate limit delays must be between 0.1s and 60.0s")
            if min_d > max_d:
                raise ValueError(f"Minimum delay ({min_d}s) cannot exceed maximum delay ({max_d}s)")

        if "target_cities" in updates:
            cities = updates["target_cities"]
            if not isinstance(cities, list) or len(cities) == 0:
                raise ValueError("Target territories list cannot be empty")
            if len(cities) > 50:
                raise ValueError("Target territories list cannot exceed 50 entries")

    @staticmethod
    def _get_settings_impl(settings_file: Path) -> Dict[str, Any]:
        """Loads persistent runtime settings with safe fallback defaults."""
        if settings_file.exists():
            try:
                with open(settings_file, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    merged = dict(DEFAULT_SETTINGS)
                    merged.update(saved)
                    return merged
            except Exception as e:
                logger.warning(f"Failed to read settings: {e}")
        return dict(DEFAULT_SETTINGS)

    @staticmethod
    def _update_settings_impl(settings_file: Path, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Validates and persists updated agency configurations."""
        current = SettingsManager._get_settings_impl(settings_file)
        
        # Enforce validation bounds
        SettingsManager.validate_updates(current, updates)

        for k, v in updates.items():
            if k in DEFAULT_SETTINGS:
                # Type sanitization
                if isinstance(DEFAULT_SETTINGS[k], int):
                    current[k] = int(v)
                elif isinstance(DEFAULT_SETTINGS[k], float):
                    current[k] = float(v)
                elif isinstance(DEFAULT_SETTINGS[k], bool):
                    current[k] = bool(v)
                elif isinstance(DEFAULT_SETTINGS[k], list) and isinstance(v, list):
                    current[k] = [str(item).strip() for item in v if str(item).strip()]
                else:
                    current[k] = str(v).strip()

        try:
            settings_file.parent.mkdir(parents=True, exist_ok=True)
            with open(settings_file, "w", encoding="utf-8") as f:
                json.dump(current, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to write settings: {e}")

        return current
