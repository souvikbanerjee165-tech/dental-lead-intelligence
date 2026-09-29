"""
AI Sales Memory & Objection Learning Engine.
Maintains persistent institutional sales memory across all dental interactions:
- Logs won deals, lost reasons, objections raised, and winning rebuttals.
- Semantically queries historical memory to brief the AI caller and sales rep before every turn.
- Feeds closing probability calculations with empirical conversion patterns.
"""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from config import BASE_DIR

logger = logging.getLogger("memory_manager")

if hasattr(Path, "resolve"):
    DB_PATH = BASE_DIR / "storage.db"
else:
    DB_PATH = Path("storage.db")


class MemoryManager:
    """Manages longitudinal sales memory, objection ledgers, and tactical recommendations."""

    @staticmethod
    def _get_connection() -> sqlite3.Connection:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    @classmethod
    def init_table(cls):
        """Initializes the sales_memory table and performance indexes."""
        with cls._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS sales_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id TEXT NOT NULL,
                clinic_name TEXT NOT NULL,
                doctor_name TEXT,
                metro TEXT,
                specialty TEXT,
                outcome TEXT NOT NULL,
                objection_category TEXT,
                objection_quote TEXT,
                effective_rebuttal TEXT,
                deal_value REAL DEFAULT 0.0,
                lessons_learned TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (lead_id) REFERENCES leads (id)
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_memory_lead ON sales_memory(lead_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_memory_metro ON sales_memory(metro);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_memory_objection ON sales_memory(objection_category);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_memory_outcome ON sales_memory(outcome);")
            conn.commit()

        # Seed initial high-value dental objection memory if empty
        cls._seed_initial_memory_if_needed()

    @classmethod
    def _seed_initial_memory_if_needed(cls):
        """Pre-populates baseline battlecard memories so the AI learns immediately."""
        with cls._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM sales_memory")
            count = cursor.fetchone()["count"]
            if count > 0:
                return

            seed_entries = [
                (
                    "seed_austin_1",
                    "Austin Family Dentistry",
                    "Dr. Hernandez",
                    "Austin",
                    "Dental Implants",
                    "WON",
                    "ALREADY_HAS_STAFF",
                    "We already have two full-time receptionists at the front desk.",
                    "Highlighted that 42% of urgent implant callers search after 6 PM when front desk is home. Missed callers don't leave voicemails, they call the next clinic.",
                    499.0,
                    "Emphasize after-hours rescue rather than replacing daytime staff. Doctors love protecting their staff from overtime.",
                    datetime.now().isoformat()
                ),
                (
                    "seed_dallas_1",
                    "Plano Premier Smiles",
                    "Dr. Miller",
                    "Dallas",
                    "Emergency Care",
                    "WON",
                    "PRICE",
                    "We are watching overhead and not adding software subscriptions right now.",
                    "Anchored cost against a single root canal or crown ($1,100). One saved emergency patient every 3 months produces a 3.5x net profit over the annual fee.",
                    399.0,
                    "Always anchor fee ($350-499) against their average case value ($900-1400). It makes the software feel free.",
                    datetime.now().isoformat()
                ),
                (
                    "seed_scottsdale_1",
                    "Scottsdale Aesthetic Dental",
                    "Dr. Vance",
                    "Phoenix",
                    "Cosmetic Dentistry",
                    "WON",
                    "INFO_EMAIL",
                    "Just email info@ and someone might look at it next week.",
                    "Offered to send a personalized 2-minute Loom prototype specifically analyzing their Google Maps competitor traffic to the office manager's direct first name.",
                    499.0,
                    "Ask for the office manager's first name to bypass the black-hole info@ general inbox.",
                    datetime.now().isoformat()
                ),
                (
                    "seed_houston_1",
                    "Memorial Dental Studio",
                    "Dr. Chen",
                    "Houston",
                    "General Dentistry",
                    "LOST",
                    "SKEPTICAL_AI",
                    "Our patients are older and prefer talking to human beings, not robots.",
                    "Explained it sounds 100% human with local Texas accent, but pushed too hard before validating their concern.",
                    0.0,
                    "Validate patient demographics first. Offer a live 30-second test call to their own mobile phone so they hear how natural the voice sounds.",
                    datetime.now().isoformat()
                )
            ]

            cursor.executemany("""
            INSERT INTO sales_memory (
                lead_id, clinic_name, doctor_name, metro, specialty, outcome,
                objection_category, objection_quote, effective_rebuttal, deal_value,
                lessons_learned, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, seed_entries)
            conn.commit()
            logger.info("Initialized sales memory ledger with baseline conversion memory.")

    @classmethod
    def record_interaction(
        cls,
        lead_id: str,
        outcome: str,
        objection_category: Optional[str] = None,
        objection_quote: Optional[str] = None,
        effective_rebuttal: Optional[str] = None,
        deal_value: float = 0.0,
        lessons_learned: Optional[str] = None,
        clinic_name: Optional[str] = None,
        doctor_name: Optional[str] = None,
        metro: Optional[str] = None,
        specialty: Optional[str] = None
    ) -> int:
        """Records a completed sales touch, objection, or deal closure into memory."""
        cls.init_table()
        with cls._get_connection() as conn:
            cursor = conn.cursor()

            # If metadata not provided, pull from leads table
            if not clinic_name or not metro:
                cursor.execute("SELECT name, doctor_name, address, category FROM leads WHERE id = ?", (lead_id,))
                lead_row = cursor.fetchone()
                if lead_row:
                    clinic_name = clinic_name or lead_row["name"]
                    doctor_name = doctor_name or lead_row["doctor_name"]
                    addr = lead_row["address"] or ""
                    metro = metro or (addr.split(",")[-2].strip() if "," in addr else "Texas")
                    specialty = specialty or lead_row["category"] or "General Dentistry"

            cursor.execute("""
            INSERT INTO sales_memory (
                lead_id, clinic_name, doctor_name, metro, specialty, outcome,
                objection_category, objection_quote, effective_rebuttal, deal_value,
                lessons_learned, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                lead_id,
                clinic_name or "Dental Practice",
                doctor_name or "Doctor",
                metro or "Metro",
                specialty or "Dental Care",
                outcome.upper(),
                (objection_category or "NONE").upper(),
                objection_quote or "",
                effective_rebuttal or "",
                float(deal_value or 0.0),
                lessons_learned or "",
                datetime.now().isoformat()
            ))
            conn.commit()
            mem_id = cursor.lastrowid
            logger.info(f"Recorded sales memory #{mem_id} for lead {lead_id} ({outcome})")
            return mem_id

    @classmethod
    def get_learnings_for_lead(cls, lead: Dict[str, Any]) -> Dict[str, Any]:
        """
        Retrieves battle-tested conversational memory tailored to the target practice:
        - Objections frequently raised by similar clinics in the same metro.
        - The most effective rebuttals that led to WON deals.
        - Similar closed-won customer precedents.
        """
        cls.init_table()
        raw_addr = lead.get("address") or ""
        metro = raw_addr.split(",")[-2].strip() if ("," in raw_addr and len(raw_addr.split(",")) >= 2) else "Texas"
        specialty = lead.get("category") or "Dentists"

        with cls._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Query past wins in this metro or related specialties
            cursor.execute("""
            SELECT clinic_name, doctor_name, deal_value, lessons_learned, effective_rebuttal, objection_category
            FROM sales_memory
            WHERE outcome = 'WON' AND (metro LIKE ? OR specialty LIKE ?)
            ORDER BY id DESC LIMIT 3;
            """, (f"%{metro}%", f"%{specialty}%"))
            won_rows = cursor.fetchall()
            won_cases = [dict(r) for r in won_rows]

            # 2. Query top objections in this market
            cursor.execute("""
            SELECT objection_category, objection_quote, effective_rebuttal, lessons_learned, COUNT(*) as frequency
            FROM sales_memory
            WHERE objection_category != 'NONE' AND objection_category IS NOT NULL
            GROUP BY objection_category
            ORDER BY frequency DESC LIMIT 3;
            """, ())
            objection_rows = cursor.fetchall()
            top_objections = [dict(r) for r in objection_rows]

            # 3. Formulate conversational memory injection string
            memory_bullet_list = []
            if won_cases:
                latest_win = won_cases[0]
                memory_bullet_list.append(
                    f"[PRECEDENT] Similar practice '{latest_win['clinic_name']}' converted by proving after-hours revenue capture."
                )
            if top_objections:
                most_common = top_objections[0]
                rebuttal_tip = most_common.get("lessons_learned") or most_common.get("effective_rebuttal") or ""
                memory_bullet_list.append(
                    f"[KNOWN OBJECTION] In {metro}: Expect '{most_common['objection_category']}'. Best tactic: {rebuttal_tip[:120]}"
                )

            summary_text = " | ".join(memory_bullet_list) if memory_bullet_list else "No prior objection data for this metro. Standard consultative protocol."

            return {
                "metro": metro,
                "won_cases_count": len(won_cases),
                "won_precedents": won_cases,
                "top_market_objections": top_objections,
                "memory_summary_prompt": summary_text
            }

    @classmethod
    def get_memory_intelligence_summary(cls) -> Dict[str, Any]:
        """Returns macro intelligence metrics across all stored sales memory."""
        cls.init_table()
        with cls._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) as total_touches FROM sales_memory;")
            total_touches = cursor.fetchone()["total_touches"]

            cursor.execute("SELECT COUNT(*) as won_count, SUM(deal_value) as total_arr FROM sales_memory WHERE outcome = 'WON';")
            won_row = cursor.fetchone()
            won_count = won_row["won_count"] or 0
            total_arr = (won_row["total_arr"] or 0.0) * 12.0

            cursor.execute("""
            SELECT objection_category, COUNT(*) as count
            FROM sales_memory
            WHERE objection_category != 'NONE' AND objection_category IS NOT NULL
            GROUP BY objection_category
            ORDER BY count DESC;
            """)
            objections_distribution = [dict(r) for r in cursor.fetchall()]

            cursor.execute("""
            SELECT id, clinic_name, doctor_name, metro, outcome, objection_category, lessons_learned, created_at
            FROM sales_memory
            ORDER BY id DESC LIMIT 15;
            """)
            recent_memories = [dict(r) for r in cursor.fetchall()]

            win_rate_pct = round((won_count / max(1, total_touches)) * 100, 1)

            return {
                "total_memories_logged": total_touches,
                "total_interactions_logged": total_touches,
                "won_deals_count": won_count,
                "win_rate_pct": win_rate_pct,
                "tracked_arr_closed": total_arr,
                "total_revenue_won": total_arr,
                "objection_distribution": objections_distribution,
                "top_objection_categories": objections_distribution,
                "recent_memory_feed": recent_memories
            }
