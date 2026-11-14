"""
Live Prospect Radar Intercept Engine.
Detects in real-time when a doctor or practice manager is actively viewing their confidential
practice teardown portal at `/pitch/{lead_id}`.
Maintains active viewer states and provides instant 1-click speed-to-lead callback triggers
with tailored conversational intercept hooks.
"""

import os
import time
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

import httpx

from database import DatabaseManager
from timeline import OpportunityTimelineManager

logger = logging.getLogger("live_intercept")


class LiveInterceptRadar:
    """Manages real-time visitor tracking and speed-to-lead intercept intelligence."""

    # In-memory registry of active prospect view events: {lead_id: event_data}
    _active_viewers: Dict[str, Dict[str, Any]] = {}
    # Deduplication / cooldown timestamps keyed by "{lead_id}:{event_type}"
    _alert_cooldowns: Dict[str, float] = {}

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

    @classmethod
    async def dispatch_rep_alert(
        cls,
        lead_id: str,
        event_type: str = "PITCH_VIEWED",
        summary_text: Optional[str] = None,
        db: Optional[DatabaseManager] = None,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Dispatches an instant Speed-to-Lead alert to the assigned sales rep via Telnyx SMS
        (REP_ALERT_PHONE) and/or webhook (REP_ALERT_WEBHOOK_URL), with per-lead cooldown
        deduplication so rapid browser refreshes do not spam.
        """
        cooldown_sec = int(os.getenv("REP_ALERT_COOLDOWN_SECONDS", "900"))
        dedupe_key = f"{lead_id}:{event_type}"
        now_ts = time.time()

        if not force:
            last_sent = cls._alert_cooldowns.get(dedupe_key, 0.0)
            if (now_ts - last_sent) < cooldown_sec:
                return {"sent": False, "reason": "COOLDOWN_ACTIVE", "cooldown_seconds": cooldown_sec}

        db = db or DatabaseManager()
        lead = db.get_lead(lead_id) or {}
        clinic_name = lead.get("name") or "Dental Practice"
        phone = lead.get("phone") or "N/A"
        base_url = os.getenv("BASE_APP_URL", "https://dental.34.71.56.145.sslip.io").rstrip("/")
        pitch_url = f"{base_url}/pitch/{lead_id}"

        message = summary_text or (
            f"🔥 SPEED-TO-LEAD: {clinic_name} just opened {pitch_url} — call {phone} now!"
        )

        # Resolve destinations from env or settings
        rep_phone = os.getenv("REP_ALERT_PHONE", "").strip()
        webhook_url = os.getenv("REP_ALERT_WEBHOOK_URL", "").strip()
        try:
            from settings_manager import SettingsManager
            cfg = SettingsManager.get()
            rep_phone = rep_phone or str(cfg.get("rep_alert_phone") or "").strip()
            webhook_url = webhook_url or str(cfg.get("rep_alert_webhook_url") or "").strip()
        except Exception:
            pass

        if not rep_phone and not webhook_url:
            return {"sent": False, "reason": "NO_ALERT_DESTINATION_CONFIGURED"}

        # Reserve cooldown window immediately to suppress concurrent refresh storms
        cls._alert_cooldowns[dedupe_key] = now_ts
        results: Dict[str, Any] = {"sent": False, "channels": {}}

        if rep_phone:
            try:
                from ai_door_opener import AIDoorOpenerEngine
                sms_res = await AIDoorOpenerEngine.dispatch_telnyx_sms(
                    to_phone=rep_phone,
                    text=message,
                    lead_id=lead_id,
                    db=db,
                    bypass_compliance=True,
                    is_internal_alert=True
                )
                results["channels"]["sms"] = sms_res
                if sms_res.get("success"):
                    results["sent"] = True
            except Exception as e:
                logger.warning(f"Speed-to-lead SMS alert failed: {e}")
                results["channels"]["sms"] = {"success": False, "error": str(e)}

        if webhook_url:
            try:
                payload = {
                    "event": event_type,
                    "lead_id": lead_id,
                    "clinic_name": clinic_name,
                    "phone": phone,
                    "pitch_url": pitch_url,
                    "text": message,
                    "timestamp": datetime.now().isoformat()
                }
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.post(webhook_url, json=payload)
                    ok = resp.status_code in (200, 201, 202, 204)
                    results["channels"]["webhook"] = {"success": ok, "status_code": resp.status_code}
                    if ok:
                        results["sent"] = True
            except Exception as e:
                logger.warning(f"Speed-to-lead webhook alert failed: {e}")
                results["channels"]["webhook"] = {"success": False, "error": str(e)}

        if results["sent"]:
            try:
                OpportunityTimelineManager.log_event(
                    db=db,
                    lead_id=lead_id,
                    event_type="REP_ALERT_DISPATCHED",
                    title=f"⚡ Instant Speed-to-Lead Rep Alert Sent ({event_type})",
                    description=message,
                    actor="SYSTEM",
                    metadata=results["channels"]
                )
            except Exception:
                pass

        return results
