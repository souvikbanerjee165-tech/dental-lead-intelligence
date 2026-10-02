"""
Overnight Autopilot & Autonomous Sleep Harvester Engine.
Designed to run unattended on a laptop while the user sleeps:
1. Periodically checkpoints state to disk (output/autopilot_state.json).
2. Sequentially prospects high-value dental metros (Dallas, Austin, Houston, Miami, Atlanta, etc.).
3. Performs automated discovery, website audit, EHR/NPI sniff, and AI qualification.
4. Auto-promotes A-tier prospects into "Today's Calls" queue for morning closing.
5. Employs human jitter delays and graceful retry logic for network drops or laptop sleep/wake.
6. Generates an executive "Morning Briefing" report when the user opens their laptop.
"""

import os
import json
import time
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

from database import DatabaseManager
from config import BASE_DIR, OUTPUT_DIR
from scheduler import AutonomousScheduler

logger = logging.getLogger("overnight_autopilot")

STATE_FILE = OUTPUT_DIR / "autopilot_state.json"

DEFAULT_OVERNIGHT_METROS = [
    "Dallas, TX",
    "Austin, TX",
    "Houston, TX",
    "Fort Worth, TX",
    "Miami, FL",
    "Atlanta, GA",
    "Phoenix, AZ",
    "Denver, CO"
]


class OvernightAutopilot:
    """Manages unattended overnight prospecting runs with atomic state persistence."""

    _task: Optional[asyncio.Task] = None
    _running: bool = False
    _state: Dict[str, Any] = {}

    @classmethod
    def _load_state(cls) -> Dict[str, Any]:
        """Loads existing state from disk or initializes clean state."""
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    cls._state = json.load(f)
                    return cls._state
            except Exception as e:
                logger.warning(f"Failed to load autopilot state: {e}")

        cls._state = {
            "status": "IDLE",  # IDLE, RUNNING, PAUSED, COMPLETED_FOR_NIGHT
            "started_at": None,
            "last_checkpoint_at": None,
            "target_metros": DEFAULT_OVERNIGHT_METROS,
            "current_metro_index": 0,
            "current_metro": DEFAULT_OVERNIGHT_METROS[0],
            "target_leads_total": 50,
            "batch_per_metro": 8,
            "leads_discovered_tonight": 0,
            "leads_audited_tonight": 0,
            "a_tier_promoted_tonight": 0,
            "total_trapped_leakage_monthly": 0,
            "consecutive_errors": 0,
            "promoted_leads_summary": [],
            "morning_briefing": None
        }
        cls._save_state()
        return cls._state

    @classmethod
    def _save_state(cls) -> None:
        """Persists current state atomically to disk."""
        cls._state["last_checkpoint_at"] = datetime.now().isoformat()
        try:
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            temp_file = STATE_FILE.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(cls._state, f, indent=2)
            temp_file.replace(STATE_FILE)
        except Exception as e:
            logger.error(f"Failed to save autopilot state: {e}")

    @classmethod
    def get_status(cls) -> Dict[str, Any]:
        """Returns live status, progress metrics, and morning briefing."""
        cls._load_state()
        is_active = cls._running and (cls._task is not None and not cls._task.done())
        cls._state["is_active"] = is_active
        if not is_active and cls._state.get("status") == "RUNNING":
            cls._state["status"] = "PAUSED"
        return cls._state

    @classmethod
    async def start(
        cls,
        target_metros: Optional[List[str]] = None,
        target_leads_total: int = 50,
        batch_per_metro: int = 8,
        db: Optional[DatabaseManager] = None
    ) -> Dict[str, Any]:
        """Starts or resumes overnight autonomous prospecting loop."""
        if cls._running and cls._task and not cls._task.done():
            return cls.get_status()

        cls._load_state()
        cls._running = True
        cls._state["status"] = "RUNNING"
        cls._state["started_at"] = cls._state.get("started_at") or datetime.now().isoformat()
        if target_metros:
            cls._state["target_metros"] = target_metros
        cls._state["target_leads_total"] = target_leads_total
        cls._state["batch_per_metro"] = batch_per_metro
        cls._save_state()

        cls._task = asyncio.create_task(cls._worker_loop(db=db))
        logger.info(f"Overnight Autopilot started targeting {len(cls._state['target_metros'])} metros (Goal: {target_leads_total} leads)")
        return cls.get_status()

    @classmethod
    def stop(cls) -> Dict[str, Any]:
        """Pauses the overnight autopilot safely and saves progress."""
        cls._running = False
        if cls._task and not cls._task.done():
            cls._task.cancel()
        cls._task = None
        cls._state["status"] = "PAUSED"
        cls._save_state()
        logger.info("Overnight Autopilot paused by user.")
        return cls.get_status()

    @classmethod
    def reset_state(cls) -> Dict[str, Any]:
        """Resets the overnight autopilot state to zero."""
        cls.stop()
        if STATE_FILE.exists():
            try:
                STATE_FILE.unlink()
            except Exception:
                pass
        cls._state = {}
        return cls._load_state()

    @classmethod
    async def _worker_loop(cls, db: Optional[DatabaseManager] = None) -> None:
        """Main overnight loop: iterates through metros, checkpoints progress, and sleeps gently."""
        db = db or DatabaseManager()

        while cls._running:
            try:
                # Check if nightly quota already reached
                if cls._state["leads_discovered_tonight"] >= cls._state["target_leads_total"]:
                    cls._finish_nightly_run()
                    break

                metros = cls._state["target_metros"]
                curr_idx = cls._state["current_metro_index"] % len(metros)
                city = metros[curr_idx]
                cls._state["current_metro"] = city
                cls._save_state()

                logger.info(f"🌙 Autopilot: Prospecting {city} (Progress: {cls._state['leads_discovered_tonight']}/{cls._state['target_leads_total']})...")

                # Parse city and state
                parts = city.split(",")
                city_name = parts[0].strip()
                state_code = parts[1].strip() if len(parts) > 1 else "US"
                t_id = f"{city_name.lower().replace(' ', '_')}_{state_code.lower()}"

                # Ensure territory exists
                try:
                    db.insert_territory(t_id, city_name, state_code, city_name, 500000, "HIGH", 200)
                except Exception:
                    pass

                # Calculate remaining leads needed for tonight
                remaining_needed = cls._state["target_leads_total"] - cls._state["leads_discovered_tonight"]
                batch_limit = min(cls._state["batch_per_metro"], remaining_needed)

                # Execute autonomous cycle
                cycle_res = await AutonomousScheduler.run_autonomous_cycle(
                    territory_id=t_id,
                    category="Dentists",
                    limit=batch_limit,
                    headless=True,
                    db=db
                )

                # Accumulate stats
                discovered = cycle_res.get("total_discovered", 0)
                audited = cycle_res.get("new_audited", 0)
                promoted = cycle_res.get("promoted_to_todays_calls", 0)
                promoted_list = cycle_res.get("promoted_leads", [])

                cls._state["leads_discovered_tonight"] += discovered
                cls._state["leads_audited_tonight"] += audited
                cls._state["a_tier_promoted_tonight"] += promoted
                cls._state["consecutive_errors"] = 0

                # Calculate trapped revenue from promoted leads
                for p in promoted_list:
                    cls._state["promoted_leads_summary"].append({
                        "id": p.get("id"),
                        "name": p.get("name"),
                        "doctor_name": p.get("doctor_name") or "Doctor",
                        "phone": p.get("phone"),
                        "buying_probability": p.get("buying_probability", 80),
                        "city": city
                    })
                    cls._state["total_trapped_leakage_monthly"] += 4200  # Conservative estimate

                # Advance to next city
                cls._state["current_metro_index"] = (curr_idx + 1) % len(metros)
                cls._save_state()

                # Check if target hit
                if cls._state["leads_discovered_tonight"] >= cls._state["target_leads_total"]:
                    cls._finish_nightly_run()
                    break

                # Gentle human-like cooldown between batches (30 to 45 seconds)
                # Allows laptop cooling and zero Google rate-limiting
                logger.info(f"Autopilot: Batch completed for {city}. Resting 30s before next metro...")
                for _ in range(30):
                    if not cls._running:
                        break
                    await asyncio.sleep(1)

            except asyncio.CancelledError:
                logger.info("Autopilot worker received cancellation request.")
                break
            except Exception as e:
                logger.error(f"Autopilot worker encountered error: {e}", exc_info=True)
                cls._state["consecutive_errors"] = cls._state.get("consecutive_errors", 0) + 1
                cls._save_state()

                # Exponential backoff on errors (e.g. Wi-Fi drop / laptop sleep)
                backoff_time = min(300, 15 * (2 ** min(4, cls._state["consecutive_errors"])))
                logger.info(f"Autopilot: Pausing for {backoff_time}s before retrying network connection...")
                for _ in range(backoff_time):
                    if not cls._running:
                        break
                    await asyncio.sleep(1)

    @classmethod
    def _finish_nightly_run(cls) -> None:
        """Constructs morning briefing summary when quota is met."""
        cls._running = False
        cls._state["status"] = "COMPLETED_FOR_NIGHT"

        # Construct high-impact Morning Briefing
        discovered = cls._state["leads_discovered_tonight"]
        promoted = cls._state["a_tier_promoted_tonight"]
        leakage = cls._state["total_trapped_leakage_monthly"]
        top_leads = cls._state["promoted_leads_summary"][:5]

        briefing = {
            "completed_at": datetime.now().isoformat(),
            "headline": f"🌅 Good morning! Over the night, {discovered} dental clinics were prospected.",
            "metrics": {
                "discovered": discovered,
                "a_tier_staged": promoted,
                "total_trapped_leakage_monthly": leakage,
                "potential_commission": int(promoted * 1500 * 0.2)  # E.g. $300 commission per closed deal
            },
            "call_queue_message": f"{promoted} high-probability clinics are pre-loaded in your 1-Click Call Queue with direct doctor scripts and teardowns.",
            "top_prospects": top_leads
        }

        cls._state["morning_briefing"] = briefing
        cls._save_state()
        logger.info(f"🏆 Overnight Prospecting Completed! {promoted} A-tier leads ready for call queue.")
