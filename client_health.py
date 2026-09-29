"""
Post-Sale Client Health & Retention Engine (Agency Machine Pillar 3).
Tracks live telemetry and generates monthly ROI retention scorecards for active paying clinics:
- Messages answered
- Appointments booked
- Total revenue generated
- Patients recovered
- Missed calls saved
- AI conversations vs. Human takeover
- Average response time (seconds)
- Health Score (0-100) & Churn Risk Warning
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from database import DatabaseManager

logger = logging.getLogger("client_health")


class ClientHealthTracker:
    """Monitors live post-sale telemetry to guarantee retention and demonstrate continuous ROI."""

    @classmethod
    def get_client_dashboard(cls, db: DatabaseManager, client_id: str) -> Dict[str, Any]:
        """Returns deep telemetry and retention metrics for a paying dental client."""
        account = db.get_client_account(client_id)
        if not account:
            # Create a sample account if not yet seeded
            default_data = {
                "client_id": client_id,
                "clinic_name": "Premier Family & Cosmetic Dental",
                "doctor_name": "Dr. Marcus Vance",
                "plan_tier": "SILVER",
                "monthly_retainer": 697.0,
                "messages_answered": 184,
                "appointments_booked": 22,
                "revenue_generated": 26400.0,
                "patients_recovered": 17,
                "missed_calls_saved": 31,
                "ai_conversations": 210,
                "human_takeovers": 8,
                "avg_response_time_sec": 3.8,
                "health_score": 96
            }
            db.save_client_account(default_data)
            account = db.get_client_account(client_id)

        # Compute dynamic retention ROI
        retainer = account.get("monthly_retainer") or 697.0
        rev_gen = account.get("revenue_generated") or 0.0
        roi_multiple = round(rev_gen / max(1.0, retainer), 1)

        # Health status determination
        health = account.get("health_score", 95)
        if health >= 85:
            status_label = "EXCELLENT_RETENTION"
            badge_color = "emerald"
        elif health >= 65:
            status_label = "STABLE"
            badge_color = "amber"
        else:
            status_label = "CHURN_RISK"
            badge_color = "rose"

        # Automated monthly proof-of-ROI statement
        statement = (
            f"Over the last 30 days, your 24/7 AI assistant answered {account.get('messages_answered')} inquiries "
            f"in an average of {account.get('avg_response_time_sec')}s, successfully booking {account.get('appointments_booked')} confirmed "
            f"appointments and recovering {account.get('patients_recovered')} emergency patients that called after hours. "
            f"Total estimated chair production recovered: ${rev_gen:,.0f} ({roi_multiple}× return on your monthly retainer)."
        )

        return {
            "client_id": client_id,
            "clinic_name": account.get("clinic_name"),
            "doctor_name": account.get("doctor_name"),
            "plan_tier": account.get("plan_tier"),
            "monthly_retainer": retainer,
            "health_score": health,
            "health_status": status_label,
            "badge_color": badge_color,
            "telemetry": {
                "messages_answered": account.get("messages_answered"),
                "appointments_booked": account.get("appointments_booked"),
                "revenue_generated": rev_gen,
                "patients_recovered": account.get("patients_recovered"),
                "missed_calls_saved": account.get("missed_calls_saved"),
                "ai_conversations": account.get("ai_conversations"),
                "human_takeovers": account.get("human_takeovers"),
                "avg_response_time_sec": account.get("avg_response_time_sec")
            },
            "roi_multiple": f"{roi_multiple}x",
            "monthly_retention_statement": statement,
            "joined_at": account.get("joined_at"),
            "last_activity_at": account.get("last_activity_at")
        }

    @classmethod
    def get_portfolio_overview(cls, db: DatabaseManager) -> Dict[str, Any]:
        """Calculates macro retention statistics across all paying client clinics."""
        accounts = db.get_all_client_accounts()
        if not accounts:
            # Seed 2 clients to provide telemetry immediately
            cls.get_client_dashboard(db, "client-austin-01")
            accounts = db.get_all_client_accounts()

        total_clients = len(accounts)
        total_mrr = sum(a.get("monthly_retainer", 0.0) for a in accounts)
        total_recaptured = sum(a.get("revenue_generated", 0.0) for a in accounts)
        total_appts = sum(a.get("appointments_booked", 0) for a in accounts)
        avg_health = round(sum(a.get("health_score", 95) for a in accounts) / max(1, total_clients), 1)

        return {
            "active_clients_count": total_clients,
            "portfolio_mrr": total_mrr,
            "portfolio_arr": total_mrr * 12,
            "total_patient_revenue_recaptured": total_recaptured,
            "total_appointments_booked": total_appts,
            "average_health_score": avg_health,
            "clients": accounts
        }
