"""
Live Prospect Radar Intercept Engine.
Detects in real-time when a doctor or practice manager is actively viewing their confidential
practice teardown portal at `/pitch/{lead_id}`.
Maintains active viewer states and provides instant 1-click speed-to-lead callback triggers
with tailored conversational intercept hooks.
"""

import time
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from database import DatabaseManager
from timeline import OpportunityTimelineManager

logger = logging.getLogger("live_intercept")


class LiveInterceptRadar:
    """Manages real-time visitor tracking and speed-to-lead intercept intelligence."""

    # In-memory registry of active prospect view events: {lead_id: event_data}
    _active_viewers: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def record_view(
        cls,
        lead_id: str,
        client_ip: Optional[str] = "127.0.0.1",
        user_agent: Optional[str] = None,
        db: Optional[DatabaseManager] = None
    ) -> Dict[str, Any]:
        """
        Records a live portal view event, updates the lead's database metrics,
        and registers the lead in the active radar intercept pool.
        """
        db = db or DatabaseManager()
        now_ts = time.time()
        now_str = datetime.now().isoformat()

        lead = db.get_lead(lead_id) or {}
        clinic_name = lead.get("name") or "Dental Practice"
        raw_doc = lead.get("doctor_name") or "Doctor"
        clean_doc = raw_doc.replace("Dr.", "").replace("Dr", "").strip()
        doc_display = f"Dr. {clean_doc}" if clean_doc else "Practice Owner"
        phone = lead.get("phone") or ""
        city = lead.get("address") or "Austin, TX"
        if "," in city:
            parts = city.split(",")
            if len(parts) >= 2:
                city = parts[-2].strip()

        # Update database lead record
        try:
            with db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                UPDATE leads
                SET win_probability_pct = MIN(98, COALESCE(win_probability_pct, 75) + 12),
                    pitch_view_count = COALESCE(pitch_view_count, 0) + 1,
                    last_pitch_viewed_at = ?,
                    last_updated = ?
                WHERE id = ?;
                """, (now_str, now_str, lead_id))
                conn.commit()
        except Exception as e:
            logger.warning(f"Failed to update lead pitch view metrics in DB: {e}")

        # High-impact speed-to-lead conversational phone hook
        intercept_hook = (
            f"Hey {doc_display}! This is Sarah with the Dental Growth concierge team. "
            f"I noticed your team was just reviewing the after-hours emergency patient teardown for {clinic_name}—"
            f"did that interactive WhatsApp scheduling preview make sense?"
        )

        viewer_record = {
            "lead_id": lead_id,
            "id": lead_id,
            "clinic_name": clinic_name,
            "name": clinic_name,
            "doctor_name": doc_display,
            "phone": phone,
            "city": city,
            "client_ip": client_ip,
            "user_agent": user_agent[:60] if user_agent else "Mobile Browser",
            "first_seen_ts": cls._active_viewers.get(lead_id, {}).get("first_seen_ts", now_ts),
            "last_seen_ts": now_ts,
            "last_seen_iso": now_str,
            "view_count": cls._active_viewers.get(lead_id, {}).get("view_count", 0) + 1,
            "speed_to_lead_hook": intercept_hook,
            "recommended_hook": intercept_hook,
            "conversational_hook": intercept_hook,
            "is_hot": True
        }

        cls._active_viewers[lead_id] = viewer_record

        # Log timeline event
        try:
            OpportunityTimelineManager.log_event(
                db=db,
                lead_id=lead_id,
                event_type="PITCH_VIEWED",
                title="🚨 LIVE RADAR: Prospect Viewing Teardown Portal Right Now!",
                description=f"{doc_display} or office manager actively opened their confidential pitch teardown portal from {viewer_record['user_agent']}.",
                actor="PROSPECT",
                metadata={"hot_intercept": True, "ip": client_ip, "hook": intercept_hook},
                timestamp=now_str
            )
        except Exception as e:
            logger.warning(f"Failed to log live radar timeline event: {e}")

        return viewer_record

    @classmethod
    def get_active_viewers(
        cls,
        max_age_seconds: int = 1800,
        ttl_seconds: Optional[int] = None,
        db: Optional[DatabaseManager] = None
    ) -> List[Dict[str, Any]]:
        """
        Returns list of prospects who have opened their pitch portal within max_age_seconds,
        sorted by most recent view activity.
        """
        if ttl_seconds is not None:
            max_age_seconds = ttl_seconds
        now_ts = time.time()
        active = []

        for lead_id, data in list(cls._active_viewers.items()):
            sec_ago = int(now_ts - data["last_seen_ts"])
            if sec_ago <= max_age_seconds:
                item = dict(data)
                item["seconds_ago"] = sec_ago
                item["is_live_now"] = sec_ago < 90  # Live within 90 seconds
                active.append(item)
            else:
                # Expire stale sessions
                cls._active_viewers.pop(lead_id, None)

        active.sort(key=lambda x: x["last_seen_ts"], reverse=True)
        return active

    @classmethod
    def clear_active_viewer(cls, lead_id: str) -> None:
        """Removes a lead from active radar once intercept call is placed."""
        cls._active_viewers.pop(lead_id, None)

    @classmethod
    def dismiss_viewer(cls, lead_id: str) -> bool:
        """Alias to dismiss/clear active viewer from radar."""
        if lead_id in cls._active_viewers:
            cls._active_viewers.pop(lead_id, None)
            return True
        return False
