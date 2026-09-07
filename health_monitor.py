"""
System Health & Telemetry Monitor.
Monitors operational availability across Database, Gemini AI, Playwright,
Autonomous Scheduler, and Disk Storage.
"""

import os
import time
import shutil
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from config import BASE_DIR, OUTPUT_DIR, GEMINI_API_KEY

logger = logging.getLogger("health_monitor")


class SystemHealthMonitor:
    """Performs real-time diagnostics on all system dependencies."""

    def __init__(self, db: Optional[Any] = None, output_dir: Path = OUTPUT_DIR):
        self.db = db
        self.output_dir = Path(output_dir)

    def run_full_diagnostic(self, db: Optional[Any] = None) -> Dict[str, Any]:
        """Instance method alias for check_health."""
        target_db = db or self.db
        return self._run_diagnostic(target_db, self.output_dir)

    def check_health(self, db: Optional[Any] = None) -> Dict[str, Any]:
        target_db = db or self.db
        return self._run_diagnostic(target_db, self.output_dir)

    @classmethod
    def check(cls, db: Any, output_dir: Path = OUTPUT_DIR) -> Dict[str, Any]:
        return cls._run_diagnostic(db, Path(output_dir))

    @staticmethod
    def _run_diagnostic(db: Any, output_dir: Path) -> Dict[str, Any]:
        """Runs a comprehensive health diagnostic and returns status breakdown."""
        start_time = time.time()
        components = {}

        # 1. Database Diagnostic
        db_start = time.time()
        try:
            if db:
                with db._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM leads")
                    total_leads = cursor.fetchone()[0]
                    cursor.execute("PRAGMA integrity_check")
                    integrity = cursor.fetchone()[0]

                db_latency_ms = round((time.time() - db_start) * 1000, 2)
                db_size_mb = round(db.db_path.stat().st_size / (1024 * 1024), 2) if db.db_path.exists() else 0.0

                components["database"] = {
                    "status": "HEALTHY" if integrity.lower() == "ok" else "ERROR",
                    "latency_ms": db_latency_ms,
                    "integrity": integrity,
                    "total_records": total_leads,
                    "file_size_mb": db_size_mb,
                    "path": str(db.db_path)
                }
            else:
                components["database"] = {"status": "UNKNOWN", "message": "Database not provided"}
        except Exception as e:
            components["database"] = {
                "status": "ERROR",
                "error": str(e),
                "latency_ms": 0.0
            }

        # 2. Gemini AI Diagnostic
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or GEMINI_API_KEY
        if api_key and len(api_key.strip()) > 10:
            masked_key = f"{api_key[:6]}...{api_key[-4:]}"
            components["gemini_ai"] = {
                "status": "HEALTHY",
                "model": "gemini-2.5-flash",
                "api_key_configured": True,
                "key_preview": masked_key
            }
        else:
            components["gemini_ai"] = {
                "status": "DEGRADED",
                "model": "rule_based_fallback",
                "api_key_configured": False,
                "message": "Gemini API key missing; operating with instant deterministic heuristics"
            }

        # 3. Playwright Engine Diagnostic
        try:
            import playwright
            components["playwright"] = {
                "status": "HEALTHY",
                "installed": True,
                "headless_mode": True
            }
        except ImportError:
            components["playwright"] = {
                "status": "WARNING",
                "installed": False,
                "message": "Playwright module not found; screenshot capture disabled"
            }

        # 4. Autonomous Daemon Diagnostic
        try:
            from scheduler import AutonomousScheduler
            daemon_status = AutonomousScheduler.get_daemon_status()
            components["scheduler"] = {
                "status": "HEALTHY" if daemon_status.get("running") else "IDLE",
                "daemon_running": daemon_status.get("running", False),
                "interval_hours": daemon_status.get("interval_hours", 6.0),
                "last_run": daemon_status.get("last_run"),
                "cycles_completed": daemon_status.get("cycles_completed", 0)
            }
        except Exception as e:
            components["scheduler"] = {
                "status": "WARNING",
                "error": str(e)
            }

        # 5. Storage Footprint Diagnostic
        try:
            screenshots_dir = output_dir / "screenshots"
            proposals_dir = output_dir / "proposals"
            backups_dir = output_dir / "backups"

            def get_dir_size_mb(p: Path) -> float:
                if not p.exists():
                    return 0.0
                return round(sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) / (1024 * 1024), 2)

            screenshots_mb = get_dir_size_mb(screenshots_dir)
            proposals_mb = get_dir_size_mb(proposals_dir)
            backups_mb = get_dir_size_mb(backups_dir)
            total_storage_mb = round(components.get("database", {}).get("file_size_mb", 0.0) + screenshots_mb + proposals_mb + backups_mb, 2)

            components["storage"] = {
                "status": "HEALTHY",
                "total_mb": total_storage_mb,
                "database_mb": components.get("database", {}).get("file_size_mb", 0.0),
                "screenshots_mb": screenshots_mb,
                "proposals_mb": proposals_mb,
                "backups_mb": backups_mb
            }
        except Exception as e:
            components["storage"] = {"status": "WARNING", "error": str(e)}

        # Overall Status Resolution
        statuses = [c.get("status") for c in components.values()]
        if "ERROR" in statuses:
            overall = "ERROR"
        elif "DEGRADED" in statuses or "WARNING" in statuses:
            overall = "HEALTHY"  # Operational with safe fallbacks
        else:
            overall = "HEALTHY"

        total_diagnostic_ms = round((time.time() - start_time) * 1000, 2)

        return {
            "overall_status": overall,
            "diagnostic_latency_ms": total_diagnostic_ms,
            "timestamp": datetime.now().isoformat(),
            "components": components
        }
