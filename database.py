import json
import os
import re
import shutil
import sqlite3
from urllib.parse import urlparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
from config import BASE_DIR
from models import ScoredLead, RawLead
from evidence import Finding

if os.getenv("VERCEL"):
    DB_PATH = Path("/tmp/storage.db")
    seed_db = BASE_DIR / "storage.db"
    if seed_db.exists() and not DB_PATH.exists():
        try:
            shutil.copyfile(seed_db, DB_PATH)
        except Exception:
            pass
else:
    DB_PATH = BASE_DIR / "storage.db"

class DatabaseManager:
    """Persistent SQLite System of Record & Change Detection Engine."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.create_function("clean_digits", 1, lambda s: re.sub(r"\D", "", s) if s else "")
        return conn

    def _init_db(self):
        """Initialize database schema with tables for leads, audits, findings, technologies, and changes."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Leads Table (Master Entity)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT,
                rating REAL,
                review_count INTEGER,
                phone TEXT,
                address TEXT,
                website TEXT,
                maps_url TEXT,
                first_seen TEXT,
                last_updated TEXT
            );
            """)

            # 2. Audits Table (Historical Snapshots)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS audits (
                id TEXT PRIMARY KEY,
                lead_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                maturity_score INTEGER,
                opportunity_score INTEGER,
                missed_rev_min INTEGER,
                missed_rev_max INTEGER,
                annual_gap INTEGER,
                content_hash TEXT,
                screenshot_path TEXT,
                reachable INTEGER DEFAULT 1,
                has_ssl INTEGER DEFAULT 1,
                has_ai_chatbot INTEGER DEFAULT 0,
                has_online_booking INTEGER DEFAULT 0,
                FOREIGN KEY (lead_id) REFERENCES leads (id)
            );
            """)

            # 3. Findings Table (Granular Evidence)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS findings (
                id TEXT PRIMARY KEY,
                audit_id TEXT NOT NULL,
                lead_id TEXT NOT NULL,
                category TEXT,
                title TEXT,
                description TEXT,
                confidence REAL,
                severity TEXT,
                recommendation TEXT,
                projected_roi REAL,
                evidence_json TEXT,
                FOREIGN KEY (audit_id) REFERENCES audits (id),
                FOREIGN KEY (lead_id) REFERENCES leads (id)
            );
            """)

            # 4. Technologies Table (Detected Stack Tracking)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS technologies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                audit_id TEXT NOT NULL,
                lead_id TEXT NOT NULL,
                name TEXT NOT NULL,
                category TEXT,
                confidence REAL,
                detected_at TEXT,
                FOREIGN KEY (audit_id) REFERENCES audits (id),
                FOREIGN KEY (lead_id) REFERENCES leads (id)
            );
            """)

            # 5. Changes Table (Audit Delta Log)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id TEXT NOT NULL,
                change_type TEXT NOT NULL,
                summary TEXT NOT NULL,
                previous_val TEXT,
                new_val TEXT,
                detected_at TEXT,
                FOREIGN KEY (lead_id) REFERENCES leads (id)
            );
            """)

            # 6. Campaigns Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS campaigns (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                target_market TEXT,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL
            );
            """)

            # 7. Touches Table (Outbound Outreach)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS touches (
                id TEXT PRIMARY KEY,
                campaign_id TEXT,
                lead_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                sent_at TEXT NOT NULL,
                primary_finding_cited TEXT,
                FOREIGN KEY (lead_id) REFERENCES leads (id)
            );
            """)

            # 8. Engagements Table (Opened, Clicked, Replied)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS engagements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                touch_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                sentiment TEXT,
                FOREIGN KEY (touch_id) REFERENCES touches (id)
            );
            """)

            # 9. Meetings Table (Booked & Held)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS meetings (
                id TEXT PRIMARY KEY,
                lead_id TEXT NOT NULL,
                touch_id TEXT,
                scheduled_for TEXT NOT NULL,
                status TEXT NOT NULL,
                FOREIGN KEY (lead_id) REFERENCES leads (id)
            );
            """)

            # 10. Deals Table (Closed Revenue & Win/Loss)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS deals (
                id TEXT PRIMARY KEY,
                lead_id TEXT NOT NULL,
                status TEXT NOT NULL,
                deal_value REAL DEFAULT 0.0,
                mrr_value REAL DEFAULT 0.0,
                primary_finding_hook TEXT,
                loss_reason TEXT,
                closed_at TEXT,
                FOREIGN KEY (lead_id) REFERENCES leads (id)
            );
            """)

            # 11. Lead Notes Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS lead_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id TEXT NOT NULL,
                author TEXT DEFAULT 'Sales Rep',
                note_text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (lead_id) REFERENCES leads (id)
            );
            """)

            # 12. Stage Transitions Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS stage_transitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id TEXT NOT NULL,
                from_stage TEXT,
                to_stage TEXT NOT NULL,
                notes TEXT,
                transitioned_at TEXT NOT NULL,
                FOREIGN KEY (lead_id) REFERENCES leads (id)
            );
            """)

            # 13. Outreach Review Queue Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS outreach_queue (
                id TEXT PRIMARY KEY,
                lead_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING_REVIEW',
                subject TEXT NOT NULL,
                body TEXT NOT NULL,
                pdf_path TEXT,
                opportunity_score INTEGER DEFAULT 0,
                priority_tier TEXT DEFAULT 'TIER 2',
                created_at TEXT NOT NULL,
                reviewed_at TEXT,
                review_notes TEXT,
                FOREIGN KEY (lead_id) REFERENCES leads (id)
            );
            """)

            # Dynamic migrations for existing SQLite databases
            cursor.execute("PRAGMA table_info(leads);")
            existing_lead_cols = {row["name"] for row in cursor.fetchall()}
            if "stage" not in existing_lead_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN stage TEXT DEFAULT 'FOUND';")
            if "contact_status" not in existing_lead_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN contact_status TEXT DEFAULT 'UNCONTACTED';")
            if "content_hash" not in existing_lead_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN content_hash TEXT;")
            if "notes" not in existing_lead_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN notes TEXT;")
            if "opportunity_score" not in existing_lead_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN opportunity_score INTEGER DEFAULT 0;")
            if "last_audit_date" not in existing_lead_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN last_audit_date TEXT;")
            if "latitude" not in existing_lead_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN latitude REAL;")
            if "longitude" not in existing_lead_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN longitude REAL;")
            if "screenshot_path" not in existing_lead_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN screenshot_path TEXT;")
            if "why_score_reasons" not in existing_lead_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN why_score_reasons TEXT;")
            if "missed_rev_min" not in existing_lead_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN missed_rev_min INTEGER DEFAULT 0;")
            if "missed_rev_max" not in existing_lead_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN missed_rev_max INTEGER DEFAULT 0;")
            if "doctor_name" not in existing_lead_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN doctor_name TEXT;")
            if "decision_maker_role" not in existing_lead_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN decision_maker_role TEXT;")
            if "direct_emails" not in existing_lead_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN direct_emails TEXT;")
            if "staff_roster" not in existing_lead_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN staff_roster TEXT;")
            if "buying_probability" not in existing_lead_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN buying_probability INTEGER DEFAULT 75;")
            if "should_call" not in existing_lead_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN should_call TEXT DEFAULT 'YES';")
            if "pain_level" not in existing_lead_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN pain_level TEXT DEFAULT 'HIGH';")
            if "practice_type" not in existing_lead_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN practice_type TEXT DEFAULT 'INDEPENDENT_OWNER';")
            if "decision_accessibility" not in existing_lead_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN decision_accessibility TEXT DEFAULT 'DIRECT_DOCTOR';")
            if "buying_triggers" not in existing_lead_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN buying_triggers TEXT;")
            if "sales_verdict" not in existing_lead_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN sales_verdict TEXT;")
            if "territory_id" not in existing_lead_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN territory_id TEXT;")
            if "expected_value" not in existing_lead_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN expected_value REAL DEFAULT 0.0;")
            if "urgency_score" not in existing_lead_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN urgency_score INTEGER DEFAULT 75;")
            if "why_now_reasons" not in existing_lead_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN why_now_reasons TEXT DEFAULT '[]';")
            if "html_hash" not in existing_lead_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN html_hash TEXT;")
            if "tech_hash" not in existing_lead_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN tech_hash TEXT;")
            if "win_probability_pct" not in existing_lead_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN win_probability_pct INTEGER DEFAULT 75;")
            if "win_probability_reasons" not in existing_lead_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN win_probability_reasons TEXT DEFAULT '[]';")
            if "urgency_driver" not in existing_lead_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN urgency_driver TEXT;")
            if "expected_deal_value" not in existing_lead_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN expected_deal_value REAL DEFAULT 0.0;")
            if "buy_probability_pct" not in existing_lead_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN buy_probability_pct INTEGER DEFAULT 75;")
            if "previous_review_count" not in existing_lead_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN previous_review_count INTEGER DEFAULT 0;")
            if "review_growth_rate" not in existing_lead_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN review_growth_rate REAL DEFAULT 0.0;")
            if "last_maps_audit" not in existing_lead_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN last_maps_audit TEXT;")
            if "receptionist_name" not in existing_lead_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN receptionist_name TEXT;")
            if "gatekeeper_notes" not in existing_lead_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN gatekeeper_notes TEXT;")
            if "best_call_time" not in existing_lead_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN best_call_time TEXT;")

            cursor.execute("PRAGMA table_info(audits);")
            existing_audit_cols = {row["name"] for row in cursor.fetchall()}
            if "content_hash" not in existing_audit_cols:
                cursor.execute("ALTER TABLE audits ADD COLUMN content_hash TEXT;")
            if "screenshot_path" not in existing_audit_cols:
                cursor.execute("ALTER TABLE audits ADD COLUMN screenshot_path TEXT;")
            if "reachable" not in existing_audit_cols:
                cursor.execute("ALTER TABLE audits ADD COLUMN reachable INTEGER DEFAULT 1;")
            if "has_ssl" not in existing_audit_cols:
                cursor.execute("ALTER TABLE audits ADD COLUMN has_ssl INTEGER DEFAULT 1;")
            if "has_ai_chatbot" not in existing_audit_cols:
                cursor.execute("ALTER TABLE audits ADD COLUMN has_ai_chatbot INTEGER DEFAULT 0;")
            if "has_online_booking" not in existing_audit_cols:
                cursor.execute("ALTER TABLE audits ADD COLUMN has_online_booking INTEGER DEFAULT 0;")

            # 14. Territories Table (Autonomous Multi-Market Expansion)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS territories (
                id TEXT PRIMARY KEY,
                city TEXT NOT NULL,
                state TEXT NOT NULL,
                metro TEXT,
                population INTEGER,
                affluence_tier TEXT,
                avg_clinics INTEGER,
                status TEXT DEFAULT 'PENDING',
                last_scraped_at TEXT,
                leads_count INTEGER DEFAULT 0,
                qualified_count INTEGER DEFAULT 0
            );
            """)

            # 15. Call Logs & Closed-Loop Conversion Learning Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS call_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                outcome TEXT NOT NULL,
                rep_notes TEXT,
                call_duration_sec INTEGER DEFAULT 0,
                FOREIGN KEY (lead_id) REFERENCES leads (id)
            );
            """)

            # 16. Opportunity Timeline (Longitudinal Practice Lifecycle)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS opportunity_timeline (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                actor TEXT DEFAULT 'SYSTEM',
                metadata_json TEXT,
                FOREIGN KEY (lead_id) REFERENCES leads (id)
            );
            """)

            # 17. Trigger Events (Website Changes & Buying Signals)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS trigger_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                severity TEXT DEFAULT 'MEDIUM',
                detected_at TEXT NOT NULL,
                old_val TEXT,
                new_val TEXT,
                FOREIGN KEY (lead_id) REFERENCES leads (id)
            );
            """)

            # 18. AI Sales Memory & Institutional Objection Ledger
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

            # 20. Multi-Agent Swarm Task Ledger
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS swarm_tasks (
                task_id TEXT PRIMARY KEY,
                agent_type TEXT NOT NULL,
                lead_id TEXT,
                status TEXT NOT NULL DEFAULT 'PENDING',
                input_payload TEXT,
                output_payload TEXT,
                error_message TEXT,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                FOREIGN KEY (lead_id) REFERENCES leads (id)
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_swarm_agent ON swarm_tasks(agent_type);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_swarm_status ON swarm_tasks(status);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_swarm_lead ON swarm_tasks(lead_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_swarm_created ON swarm_tasks(created_at);")

            # 21. Relationship Memory Table (Staff & Gatekeeper Dossier)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS relationship_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id TEXT NOT NULL,
                contact_name TEXT NOT NULL,
                role TEXT DEFAULT 'RECEPTIONIST',
                demeanor TEXT DEFAULT 'FRIENDLY',
                notes TEXT,
                best_time_to_call TEXT,
                software_mentioned TEXT,
                last_contacted_at TEXT NOT NULL,
                FOREIGN KEY (lead_id) REFERENCES leads (id)
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_rel_mem_lead ON relationship_memory(lead_id);")

            # 22. Institutional Knowledge Base Table (Self-Learning Repository)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_base (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                key_phrase TEXT NOT NULL,
                content TEXT NOT NULL,
                effectiveness_score REAL DEFAULT 8.0,
                times_used INTEGER DEFAULT 1,
                times_succeeded INTEGER DEFAULT 1,
                created_at TEXT NOT NULL
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_kb_category ON knowledge_base(category);")

            # 23. Automated Follow-Up Reminders Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS followup_reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id TEXT NOT NULL,
                clinic_name TEXT NOT NULL,
                due_date TEXT NOT NULL,
                status TEXT DEFAULT 'PENDING',
                trigger_reason TEXT NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                FOREIGN KEY (lead_id) REFERENCES leads (id)
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_reminders_status_due ON followup_reminders(status, due_date);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_reminders_lead ON followup_reminders(lead_id);")

            # 24. Client Health & Retention Accounts Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS client_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id TEXT NOT NULL UNIQUE,
                clinic_name TEXT NOT NULL,
                doctor_name TEXT,
                plan_tier TEXT DEFAULT 'SILVER',
                monthly_retainer REAL DEFAULT 697.0,
                messages_answered INTEGER DEFAULT 0,
                appointments_booked INTEGER DEFAULT 0,
                revenue_generated REAL DEFAULT 0.0,
                patients_recovered INTEGER DEFAULT 0,
                missed_calls_saved INTEGER DEFAULT 0,
                ai_conversations INTEGER DEFAULT 0,
                human_takeovers INTEGER DEFAULT 0,
                avg_response_time_sec REAL DEFAULT 4.2,
                health_score INTEGER DEFAULT 95,
                status TEXT DEFAULT 'ACTIVE',
                joined_at TEXT NOT NULL,
                last_activity_at TEXT NOT NULL
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_client_accounts_status ON client_accounts(status);")

            # 25. Market Scanner Signals Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id TEXT NOT NULL UNIQUE,
                metro TEXT NOT NULL,
                total_scanned INTEGER DEFAULT 0,
                signals_found INTEGER DEFAULT 0,
                signals_json TEXT,
                scanned_at TEXT NOT NULL
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_market_scans_metro ON market_scans(metro);")

            # 26. Call Audio Recordings & Takeover Handoff Telemetry
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS call_recordings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                call_id TEXT NOT NULL UNIQUE,
                lead_id TEXT,
                phone_number TEXT NOT NULL,
                contact_name TEXT,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                duration_sec INTEGER DEFAULT 0,
                recording_file_path TEXT,
                recording_url TEXT,
                initial_mode TEXT DEFAULT 'HUMAN_FIRST',
                final_mode TEXT,
                handoff_count INTEGER DEFAULT 0,
                handoff_log_json TEXT,
                transcript_json TEXT,
                outcome TEXT DEFAULT 'IN_PROGRESS',
                learnings_json TEXT,
                created_at TEXT NOT NULL
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_call_rec_phone ON call_recordings(phone_number);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_call_rec_lead ON call_recordings(lead_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_call_rec_created ON call_recordings(created_at);")

            # Production Query Performance Indexes (v1.0 Hardening)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_leads_phone ON leads(phone);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_leads_website ON leads(website);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_leads_stage ON leads(stage);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_leads_buying_prob ON leads(buying_probability);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_leads_urgency ON leads(urgency_driver);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_leads_ev ON leads(expected_deal_value);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_leads_doctor ON leads(doctor_name);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_timeline_lead_ts ON opportunity_timeline(lead_id, timestamp);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_triggers_lead_ts ON trigger_events(lead_id, detected_at);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audits_lead_ts ON audits(lead_id, timestamp);")
            conn.commit()

        # Initialize multi-tenant isolation schema (Roadmap #10)
        try:
            from tenant_manager import TenantManager
            TenantManager.init_tenants_table(self)
        except Exception:
            pass

    @staticmethod
    def _make_lead_id(name: str, website: Optional[str]) -> str:
        clean_name = "".join(c.lower() for c in name if c.isalnum())
        clean_site = "".join(c.lower() for c in (website or "") if c.isalnum())
        return f"lead_{clean_name}_{clean_site[:20]}"

    def save_scored_lead(self, scored_lead: ScoredLead, findings: List[Finding]) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Persists a lead, audit snapshot, findings, and detected tech stack.
        Automatically detects and logs changes between this audit and previous audits.
        """
        raw = scored_lead.raw_lead
        audit = scored_lead.audit
        lead_id = self._make_lead_id(raw.name, raw.website)
        now_str = datetime.now().isoformat()
        audit_id = f"aud_{lead_id}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

        detected_changes = []

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Check if lead already exists
            cursor.execute("SELECT * FROM leads WHERE id = ?", (lead_id,))
            existing_lead = cursor.fetchone()

            content_hash = getattr(scored_lead, "content_hash", None)
            stage = getattr(scored_lead, "stage", "AUDITED")
            notes = getattr(scored_lead, "notes", None)
            lat = getattr(raw, "latitude", None)
            lng = getattr(raw, "longitude", None)
            screenshot = getattr(scored_lead, "screenshot_path", None) or (getattr(audit, "screenshot_path", None) if audit else None)
            why_reasons = getattr(scored_lead, "why_score_reasons", None)
            why_json = json.dumps(why_reasons) if isinstance(why_reasons, list) else (why_reasons or "[]")
            rev_min = scored_lead.estimated_missed_revenue_monthly_min or 0
            rev_max = scored_lead.estimated_missed_revenue_monthly_max or 0
            doc_name = getattr(scored_lead, "doctor_name", None) or (getattr(audit, "doctor_name", None) if audit else None)
            dm_role = getattr(scored_lead, "decision_maker_role", None) or (getattr(audit, "decision_maker_role", None) if audit else None)
            staff_roster = getattr(scored_lead, "staff_roster", None) or (getattr(audit, "staff_roster", None) if audit else None)
            staff_json = json.dumps(staff_roster) if isinstance(staff_roster, list) else (staff_roster or "[]")
            emails_list = getattr(audit, "emails", []) if audit else []
            emails_str = ", ".join(emails_list) if isinstance(emails_list, list) else (emails_list or "")

            if not existing_lead:
                cursor.execute("""
                INSERT INTO leads (
                    id, name, category, rating, review_count, phone, address, website, maps_url,
                    first_seen, last_updated, stage, contact_status, content_hash, notes,
                    opportunity_score, last_audit_date, latitude, longitude, screenshot_path,
                    why_score_reasons, missed_rev_min, missed_rev_max,
                    doctor_name, decision_maker_role, direct_emails, staff_roster
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    lead_id, raw.name, raw.category, raw.rating, raw.review_count,
                    raw.phone, raw.address, raw.website, raw.maps_url, now_str, now_str,
                    stage, "UNCONTACTED", content_hash, notes, scored_lead.opportunity_score, now_str,
                    lat, lng, screenshot, why_json, rev_min, rev_max,
                    doc_name, dm_role, emails_str, staff_json
                ))
                cursor.execute("""
                INSERT INTO stage_transitions (lead_id, from_stage, to_stage, notes, transitioned_at)
                VALUES (?, ?, ?, ?, ?)
                """, (lead_id, "FOUND", stage, "Initial automated audit completed", now_str))
            else:
                curr_stage = existing_lead["stage"] or "FOUND"
                new_stage = stage if curr_stage == "FOUND" else curr_stage
                if curr_stage == "FOUND":
                    cursor.execute("""
                    INSERT INTO stage_transitions (lead_id, from_stage, to_stage, notes, transitioned_at)
                    VALUES (?, ?, ?, ?, ?)
                    """, (lead_id, "FOUND", new_stage, "Automated audit completed", now_str))

                cursor.execute("""
                UPDATE leads SET
                    rating = COALESCE(?, rating),
                    review_count = COALESCE(?, review_count),
                    phone = COALESCE(?, phone),
                    address = COALESCE(?, address),
                    website = COALESCE(?, website),
                    maps_url = COALESCE(?, maps_url),
                    last_updated = ?,
                    stage = ?,
                    opportunity_score = ?,
                    last_audit_date = ?,
                    content_hash = COALESCE(?, content_hash),
                    latitude = COALESCE(?, latitude),
                    longitude = COALESCE(?, longitude),
                    screenshot_path = COALESCE(?, screenshot_path),
                    why_score_reasons = COALESCE(?, why_score_reasons),
                    missed_rev_min = COALESCE(?, missed_rev_min),
                    missed_rev_max = COALESCE(?, missed_rev_max),
                    doctor_name = COALESCE(?, doctor_name),
                    decision_maker_role = COALESCE(?, decision_maker_role),
                    direct_emails = COALESCE(?, direct_emails),
                    staff_roster = COALESCE(?, staff_roster)
                WHERE id = ?
                """, (
                    raw.rating, raw.review_count, raw.phone, raw.address,
                    raw.website, raw.maps_url, now_str,
                    new_stage, scored_lead.opportunity_score, now_str,
                    content_hash, lat, lng, screenshot, why_json, rev_min, rev_max,
                    doc_name, dm_role, emails_str, staff_json,
                    lead_id
                ))

            # Retrieve the most recent previous audit for change detection
            cursor.execute("SELECT * FROM audits WHERE lead_id = ? ORDER BY timestamp DESC LIMIT 1", (lead_id,))
            prev_audit = cursor.fetchone()

            if prev_audit:
                # Check for content change
                prev_hash = prev_audit["content_hash"] if "content_hash" in prev_audit.keys() else None
                if prev_hash and content_hash and prev_hash != content_hash:
                    change_item = {
                        "change_type": "CONTENT_CHANGED",
                        "summary": "Website HTML content modified (redesign, copy update, or tech changes)",
                        "previous_val": str(prev_hash)[:8],
                        "new_val": str(content_hash)[:8]
                    }
                    detected_changes.append(change_item)
                    cursor.execute("""
                    INSERT INTO changes (lead_id, change_type, summary, previous_val, new_val, detected_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """, (lead_id, change_item["change_type"], change_item["summary"], change_item["previous_val"], change_item["new_val"], now_str))

                # Check for score shifts
                prev_maturity = prev_audit["maturity_score"]
                new_maturity = scored_lead.maturity.overall_score
                if prev_maturity != new_maturity:
                    diff = new_maturity - prev_maturity
                    change_item = {
                        "change_type": "MATURITY_SCORE_SHIFT",
                        "summary": f"Digital Maturity Score shifted by {'+' if diff > 0 else ''}{diff} pts (from {prev_maturity} to {new_maturity})",
                        "previous_val": str(prev_maturity),
                        "new_val": str(new_maturity)
                    }
                    detected_changes.append(change_item)
                    cursor.execute("""
                    INSERT INTO changes (lead_id, change_type, summary, previous_val, new_val, detected_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """, (lead_id, change_item["change_type"], change_item["summary"], change_item["previous_val"], change_item["new_val"], now_str))

                # Check for tech stack additions / removals
                cursor.execute("SELECT DISTINCT name FROM technologies WHERE lead_id = ? AND audit_id = ?", (lead_id, prev_audit["id"]))
                prev_techs = set(row["name"] for row in cursor.fetchall())
                curr_techs = set(audit.tech_stack.summary_list())

                newly_added = curr_techs - prev_techs
                for t in newly_added:
                    change_item = {
                        "change_type": "TECH_ADDED",
                        "summary": f"Newly detected technology: {t}",
                        "previous_val": "None",
                        "new_val": t
                    }
                    detected_changes.append(change_item)
                    cursor.execute("""
                    INSERT INTO changes (lead_id, change_type, summary, previous_val, new_val, detected_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """, (lead_id, change_item["change_type"], change_item["summary"], change_item["previous_val"], change_item["new_val"], now_str))

            # Insert Audit Snapshot
            cursor.execute("""
            INSERT INTO audits (id, lead_id, timestamp, maturity_score, opportunity_score, missed_rev_min, missed_rev_max, annual_gap, content_hash, screenshot_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                audit_id, lead_id, now_str,
                scored_lead.maturity.overall_score,
                scored_lead.opportunity_score,
                scored_lead.estimated_missed_revenue_monthly_min,
                scored_lead.estimated_missed_revenue_monthly_max,
                scored_lead.estimated_missed_revenue_annual,
                content_hash,
                screenshot
            ))

            # Insert Findings
            for finding in findings:
                finding_db_id = f"{audit_id}_{finding.id}"
                evidence_blob = json.dumps([e.model_dump() for e in finding.evidence])
                cursor.execute("""
                INSERT INTO findings (id, audit_id, lead_id, category, title, description, confidence, severity, recommendation, projected_roi, evidence_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    finding_db_id, audit_id, lead_id,
                    finding.category, finding.title, finding.description,
                    finding.confidence, finding.severity, finding.recommendation,
                    finding.projected_monthly_roi, evidence_blob
                ))

            # Insert Executive Business Insights (Layer 3)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS insights (
                id TEXT PRIMARY KEY,
                audit_id TEXT NOT NULL,
                lead_id TEXT NOT NULL,
                insight_type TEXT,
                title TEXT,
                executive_summary TEXT,
                impact_analysis TEXT,
                confidence REAL,
                urgency TEXT,
                projected_annual_loss REAL,
                strategic_recommendation TEXT,
                supporting_finding_ids TEXT,
                FOREIGN KEY (audit_id) REFERENCES audits (id),
                FOREIGN KEY (lead_id) REFERENCES leads (id)
            );
            """)
            for ins in scored_lead.insights:
                ins_id = f"{audit_id}_{ins.id}"
                cursor.execute("""
                INSERT OR REPLACE INTO insights (
                    id, audit_id, lead_id, insight_type, title, executive_summary,
                    impact_analysis, confidence, urgency, projected_annual_loss,
                    strategic_recommendation, supporting_finding_ids
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    ins_id, audit_id, lead_id, ins.insight_type, ins.title, ins.executive_summary,
                    ins.impact_analysis, ins.confidence, ins.urgency, ins.projected_annual_loss,
                    ins.strategic_recommendation, json.dumps(ins.supporting_finding_ids)
                ))

            # Insert Detected Technologies
            for tech_cat, tech_list in [
                ("CMS", audit.tech_stack.cms_and_frameworks),
                ("Analytics", audit.tech_stack.analytics),
                ("Tag Managers", audit.tech_stack.tag_managers),
                ("Ad Pixels", audit.tech_stack.ad_pixels),
                ("CRM", audit.tech_stack.crm_and_marketing),
                ("Cloud & CDN", audit.tech_stack.cloud_and_cdn),
                ("Chatbots", audit.tech_stack.chatbots),
                ("Booking", audit.tech_stack.booking_tools),
            ]:
                for t_name in tech_list:
                    cursor.execute("""
                    INSERT INTO technologies (audit_id, lead_id, name, category, confidence, detected_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """, (audit_id, lead_id, t_name, tech_cat, 0.98, now_str))

            conn.commit()

        return lead_id, detected_changes

    @staticmethod
    def _format_lead_row(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
        if row is None:
            return None
        d = dict(row)
        if "why_score_reasons" in d and d["why_score_reasons"]:
            try:
                d["why_score_reasons"] = json.loads(d["why_score_reasons"])
            except Exception:
                d["why_score_reasons"] = [d["why_score_reasons"]]
        else:
            d["why_score_reasons"] = []
        return d

    def update_lead_visuals(self, lead_id: str, screenshot_path: Optional[str] = None, why_reasons: Optional[List[str]] = None) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            updates = []
            params = []
            if screenshot_path:
                updates.append("screenshot_path = ?")
                params.append(screenshot_path)
            if why_reasons is not None:
                updates.append("why_score_reasons = ?")
                params.append(json.dumps(why_reasons))
            if not updates:
                return True
            params.append(lead_id)
            cursor.execute(f"UPDATE leads SET {', '.join(updates)} WHERE id = ?", tuple(params))
            conn.commit()
            return cursor.rowcount > 0

    def list_all_leads(self) -> List[Dict[str, Any]]:
        """List all tracked leads with their latest audit scores."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT l.*, a.maturity_score, a.opportunity_score as audit_opportunity_score,
                   a.missed_rev_min as audit_missed_rev_min, a.missed_rev_max as audit_missed_rev_max,
                   a.annual_gap, a.timestamp as last_audit
            FROM leads l
            LEFT JOIN audits a ON a.lead_id = l.id AND a.timestamp = (SELECT MAX(a2.timestamp) FROM audits a2 WHERE a2.lead_id = l.id)
            ORDER BY COALESCE(l.opportunity_score, 0) DESC
            """)
            return [self._format_lead_row(row) for row in cursor.fetchall() if row]

    def get_lead_findings(self, lead_id: str) -> List[Dict[str, Any]]:
        """Retrieve all findings from the most recent audit of a lead."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT * FROM findings
            WHERE lead_id = ?
            ORDER BY confidence DESC
            """, (lead_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_lead_changes(self, lead_id: str) -> List[Dict[str, Any]]:
        """Retrieve change logs for a lead."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM changes WHERE lead_id = ? ORDER BY detected_at DESC", (lead_id,))
            return [dict(row) for row in cursor.fetchall()]

    # --- Closed-Loop Outcome Tracking Methods ---

    def record_touch(self, campaign_id: str, lead_id: str, channel: str, primary_finding_cited: Optional[str] = None) -> str:
        touch_id = f"tch_{datetime.now().strftime('%Y%m%d%H%M%S%f')[:18]}"
        now_str = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO touches (id, campaign_id, lead_id, channel, sent_at, primary_finding_cited)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (touch_id, campaign_id, lead_id, channel, now_str, primary_finding_cited))
            conn.commit()
        return touch_id

    def record_engagement(self, touch_id: str, event_type: str, sentiment: str = "neutral"):
        now_str = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO engagements (touch_id, event_type, timestamp, sentiment)
            VALUES (?, ?, ?, ?)
            """, (touch_id, event_type, now_str, sentiment))
            conn.commit()

    def record_meeting(self, lead_id: str, touch_id: Optional[str], scheduled_for: str, status: str = "scheduled") -> str:
        mtg_id = f"mtg_{datetime.now().strftime('%Y%m%d%H%M%S%f')[:18]}"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO meetings (id, lead_id, touch_id, scheduled_for, status)
            VALUES (?, ?, ?, ?, ?)
            """, (mtg_id, lead_id, touch_id, scheduled_for, status))
            conn.commit()
        return mtg_id

    def record_deal(
        self,
        lead_id: str,
        status: str,
        deal_value: float,
        mrr_value: float = 0.0,
        primary_finding_hook: Optional[str] = None,
        loss_reason: Optional[str] = None
    ) -> str:
        deal_id = f"deal_{datetime.now().strftime('%Y%m%d%H%M%S%f')[:18]}"
        now_str = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO deals (id, lead_id, status, deal_value, mrr_value, primary_finding_hook, loss_reason, closed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (deal_id, lead_id, status, deal_value, mrr_value, primary_finding_hook, loss_reason, now_str))
            conn.commit()
        return deal_id

    def get_all_touches_with_outcomes(self) -> List[Dict[str, Any]]:
        """Retrieve touches joined with engagements, meetings, and deals for closed-loop learning."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT 
                t.id as touch_id,
                t.lead_id,
                t.channel,
                t.primary_finding_cited,
                t.sent_at,
                (SELECT COUNT(*) FROM engagements e WHERE e.touch_id = t.id AND e.event_type = 'replied') as replied,
                (SELECT COUNT(*) FROM meetings m WHERE m.touch_id = t.id) as meeting_booked,
                d.status as deal_status,
                d.deal_value,
                d.mrr_value
            FROM touches t
            LEFT JOIN deals d ON d.lead_id = t.lead_id
            ORDER BY t.sent_at DESC
            """)
            return [dict(r) for r in cursor.fetchall()]

    def get_lead_technologies(self, lead_id: str) -> List[Dict[str, Any]]:
        """Retrieves detected technologies for a specific lead."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT name, category, confidence, detected_at
            FROM technologies
            WHERE lead_id = ?
            ORDER BY id DESC
            """, (lead_id,))
            return [dict(r) for r in cursor.fetchall()]

    # --- Phase 1 & 7: Permanent BI Records & Relationship Intelligence ---

    def get_leads_with_score_increase(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Finds practices whose Opportunity Score or Digital Maturity improved across audits."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT DISTINCT l.*, c.summary as change_summary, c.previous_val, c.new_val, c.detected_at
            FROM leads l
            JOIN changes c ON l.id = c.lead_id
            WHERE c.change_type IN ('MATURITY_SCORE_SHIFT', 'SCORE_INCREASED', 'OPPORTUNITY_UPDATED')
              AND CAST(c.new_val AS REAL) > CAST(c.previous_val AS REAL)
            ORDER BY c.detected_at DESC
            LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            if rows:
                return [self._format_lead_row(r) for r in rows]
            
            # Fallback: Query leads with high urgency/opportunity scores
            cursor.execute("""
            SELECT l.*, 'High Growth Opportunity' as change_summary
            FROM leads l
            WHERE l.opportunity_score >= 80 OR l.urgency_score >= 85
            ORDER BY l.opportunity_score DESC
            LIMIT ?
            """, (limit,))
            return [self._format_lead_row(r) for r in cursor.fetchall()]

    def get_leads_with_chatbot_removed(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Finds practices where a competitor chatbot or livechat widget was dropped."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT DISTINCT l.*, COALESCE(c.change_type, 'CHATBOT_REMOVED') as change_type, c.summary as change_summary, c.detected_at
            FROM leads l
            JOIN changes c ON l.id = c.lead_id
            WHERE c.change_type IN ('CHATBOT_REMOVED', 'TECH_REMOVED')
               OR c.summary LIKE '%chatbot%'
               OR c.summary LIKE '%widget dropped%'
            UNION
            SELECT DISTINCT l.*, t.title as change_type, COALESCE(t.description, t.title) as change_summary, t.detected_at
            FROM leads l
            JOIN trigger_events t ON l.id = t.lead_id
            WHERE t.event_type = 'COMPETITOR_DROPPED'
               OR t.title LIKE '%chatbot%'
               OR t.title LIKE '%chat%'
               OR t.title LIKE '%Podium%'
               OR t.title LIKE '%Birdeye%'
            ORDER BY detected_at DESC
            LIMIT ?
            """, (limit,))
            return [self._format_lead_row(r) for r in cursor.fetchall()]

    def get_full_lead_dossier(self, lead_id: str) -> Optional[Dict[str, Any]]:
        """Consolidates complete longitudinal Business Intelligence Record for a clinic."""
        lead = self.get_lead(lead_id)
        if not lead:
            return None

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Audits history
            cursor.execute("SELECT * FROM audits WHERE lead_id = ? ORDER BY timestamp DESC", (lead_id,))
            audits = [dict(r) for r in cursor.fetchall()]

            # Tech stack
            cursor.execute("SELECT DISTINCT name, category, confidence, detected_at FROM technologies WHERE lead_id = ? ORDER BY id DESC", (lead_id,))
            tech_stack = [dict(r) for r in cursor.fetchall()]

            # Findings
            cursor.execute("SELECT * FROM findings WHERE lead_id = ? ORDER BY id DESC", (lead_id,))
            findings = [dict(r) for r in cursor.fetchall()]

            # Call logs
            cursor.execute("SELECT * FROM call_logs WHERE lead_id = ? ORDER BY timestamp DESC", (lead_id,))
            call_logs = [dict(r) for r in cursor.fetchall()]

            # Changes log
            cursor.execute("SELECT * FROM changes WHERE lead_id = ? ORDER BY detected_at DESC", (lead_id,))
            changes = [dict(r) for r in cursor.fetchall()]

            # Triggers log
            cursor.execute("SELECT * FROM trigger_events WHERE lead_id = ? ORDER BY detected_at DESC", (lead_id,))
            triggers = [dict(r) for r in cursor.fetchall()]

            # Relationship Memory
            cursor.execute("SELECT * FROM relationship_memory WHERE lead_id = ? ORDER BY last_contacted_at DESC", (lead_id,))
            rel_rows = cursor.fetchall()
            relationships = [dict(r) for r in rel_rows]
            relationship = relationships[0] if relationships else None

        from timeline import OpportunityTimelineManager
        timeline = OpportunityTimelineManager.get_unified_timeline(self, lead_id)

        return {
            "lead": lead,
            "audits": audits,
            "audits_history": audits,
            "technologies": tech_stack,
            "findings": findings,
            "call_logs": call_logs,
            "changes": changes,
            "detected_changes": changes,
            "trigger_events": triggers,
            "relationship_memory": relationship,
            "relationships": relationships,
            "unified_timeline": timeline,
            "total_touches_count": len(call_logs) + len(triggers)
        }

    def record_relationship_memory(
        self,
        lead_id: str,
        contact_name: str,
        role: str = "RECEPTIONIST",
        demeanor: str = "FRIENDLY",
        notes: str = "",
        best_time: str = "",
        software: str = "",
        best_time_to_call: Optional[str] = None,
        software_mentioned: Optional[str] = None
    ) -> int:
        """Stores staff/gatekeeper intelligence in relationship_memory and updates master lead."""
        now_str = datetime.now().isoformat()
        call_time = best_time_to_call or best_time
        soft = software_mentioned or software
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO relationship_memory (lead_id, contact_name, role, demeanor, notes, best_time_to_call, software_mentioned, last_contacted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (lead_id, contact_name, role, demeanor, notes, call_time, soft, now_str))
            mem_id = cursor.lastrowid

            cursor.execute("""
            UPDATE leads
            SET receptionist_name = ?,
                gatekeeper_notes = ?,
                best_call_time = ?
            WHERE id = ?
            """, (contact_name, notes, call_time, lead_id))
            conn.commit()
            return mem_id

    def get_relationship_memory(self, lead_id: str) -> List[Dict[str, Any]]:
        """Retrieves recent gatekeeper intelligence for a practice."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT * FROM relationship_memory 
            WHERE lead_id = ? 
            ORDER BY last_contacted_at DESC
            """, (lead_id,))
            return [dict(r) for r in cursor.fetchall()]

    def update_lead_maps_metrics(
        self,
        lead_id: str,
        current_review_count: int,
        current_rating: float
    ) -> Dict[str, Any]:
        """Calculates review growth velocity and records Google Maps monitoring triggers."""
        now_str = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT review_count, rating, opportunity_score FROM leads WHERE id = ?", (lead_id,))
            row = cursor.fetchone()
            if not row:
                return {"error": "Lead not found"}

            old_reviews = row["review_count"] or 0
            old_rating = float(row["rating"] or current_rating)
            review_growth = max(0, current_review_count - old_reviews)
            growth_rate = round((review_growth / max(1, old_reviews)) * 100, 1)
            rating_velocity = round(current_rating - old_rating, 2)
            new_opp = (row["opportunity_score"] or 60) + (10 if review_growth >= 15 else 0)

            cursor.execute("""
            UPDATE leads
            SET previous_review_count = review_count,
                review_count = ?,
                rating = ?,
                review_growth_rate = ?,
                opportunity_score = ?,
                last_maps_audit = ?
            WHERE id = ?
            """, (current_review_count, current_rating, growth_rate, new_opp, now_str, lead_id))

            if review_growth >= 10:
                cursor.execute("""
                INSERT INTO trigger_events (lead_id, event_type, title, description, severity, detected_at, old_val, new_val)
                VALUES (?, 'RAPID_REVIEW_GROWTH', 'Rapid Google Review Acceleration', ?, 'HIGH', ?, ?, ?)
                """, (
                    lead_id,
                    f"Practice gained +{review_growth} Google reviews ({old_reviews} -> {current_review_count}). High-volume patient momentum.",
                    now_str,
                    str(old_reviews),
                    str(current_review_count)
                ))
            conn.commit()

            return {
                "lead_id": lead_id,
                "old_reviews": old_reviews,
                "new_reviews": current_review_count,
                "review_growth": review_growth,
                "delta_reviews": review_growth,
                "growth_rate_pct": growth_rate,
                "growth_rate": growth_rate,
                "rating": current_rating,
                "rating_velocity": rating_velocity
            }

    def log_knowledge_base_insight(
        self,
        category: str,
        key_phrase: str,
        content: str,
        effectiveness_score: float = 8.5
    ) -> int:
        """Stores or increments a proven sales tactic/objection rebuttal in the knowledge base."""
        now_str = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, times_used, times_succeeded FROM knowledge_base WHERE key_phrase = ?", (key_phrase,))
            existing = cursor.fetchone()
            if existing:
                cursor.execute("""
                UPDATE knowledge_base
                SET times_used = times_used + 1,
                    times_succeeded = times_succeeded + 1,
                    effectiveness_score = round(((effectiveness_score * 0.7) + (? * 0.3)), 1)
                WHERE id = ?
                """, (effectiveness_score, existing["id"]))
                conn.commit()
                return existing["id"]
            else:
                cursor.execute("""
                INSERT INTO knowledge_base (category, key_phrase, content, effectiveness_score, times_used, times_succeeded, created_at)
                VALUES (?, ?, ?, ?, 1, 1, ?)
                """, (category, key_phrase, content, effectiveness_score, now_str))
                conn.commit()
                return cursor.lastrowid

    def get_knowledge_base_insights(self, category: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieves top-performing tactics from the institutional knowledge base."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if category:
                cursor.execute("""
                SELECT * FROM knowledge_base 
                WHERE category = ? 
                ORDER BY effectiveness_score DESC, times_succeeded DESC 
                LIMIT ?
                """, (category, limit))
            else:
                cursor.execute("""
                SELECT * FROM knowledge_base 
                ORDER BY effectiveness_score DESC, times_succeeded DESC 
                LIMIT ?
                """, (limit,))
            return [dict(r) for r in cursor.fetchall()]

    # --- CRM Stage & Notes Management Methods ---

    def _format_lead_row(self, row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
        if not row:
            return None
        d = dict(row)
        if "why_score_reasons" in d and isinstance(d["why_score_reasons"], str):
            try:
                d["why_score_reasons"] = json.loads(d["why_score_reasons"])
            except Exception:
                pass
        if "staff_roster" in d and isinstance(d["staff_roster"], str):
            try:
                d["staff_roster"] = json.loads(d["staff_roster"])
            except Exception:
                pass
        # Calculate or normalize Expected Value ($EV = Contract LTV $3,979 * Buying Probability)
        if d.get("expected_value") is not None and float(d.get("expected_value") or 0.0) > 0:
            d["expected_value"] = float(d["expected_value"])
        else:
            prob = float(d.get("buying_probability") or 75)
            d["expected_value"] = round(3979.0 * (prob / 100.0), 2)

        # Parse or populate Why Now timing reasons
        if "why_now_reasons" in d and isinstance(d["why_now_reasons"], str):
            try:
                d["why_now_reasons"] = json.loads(d["why_now_reasons"])
            except Exception:
                pass
        if not d.get("why_now_reasons"):
            from triggers import TriggerEngine
            d["why_now_reasons"] = TriggerEngine.generate_why_now_reasons(d)

        # Calculate or normalize Urgency Score (0 - 100)
        if d.get("urgency_score") is None or d.get("urgency_score") == 0:
            from triggers import TriggerEngine
            d["urgency_score"] = TriggerEngine.calculate_urgency_score(d)
        else:
            d["urgency_score"] = int(d["urgency_score"])

        # Calculate Data Completeness & Quality Score (0 - 100%)
        from data_quality import DataQualityEngine
        dq = DataQualityEngine.evaluate(d)
        d["data_quality_score"] = dq["data_quality_score"]
        d["data_quality_tier"] = dq["quality_tier"]
        d["data_quality_missing"] = dq["missing_fields"]
        d["data_quality_badge"] = dq["badge_color"]

        # Win Probability & Reasoning
        if "win_probability_reasons" in d and isinstance(d["win_probability_reasons"], str):
            try:
                d["win_probability_reasons"] = json.loads(d["win_probability_reasons"])
            except Exception:
                d["win_probability_reasons"] = []
        elif "win_probability_reasons" not in d or d["win_probability_reasons"] is None:
            d["win_probability_reasons"] = []

        if d.get("win_probability_pct") is None or d.get("win_probability_pct") == 0:
            d["win_probability_pct"] = int(d.get("buying_probability") or 75)
        else:
            d["win_probability_pct"] = int(d["win_probability_pct"])

        return d

    def get_lead(self, lead_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM leads WHERE id = ?", (lead_id,))
            row = cursor.fetchone()
            return self._format_lead_row(row)

    def save_lead(self, lead_data: Dict[str, Any]) -> str:
        """Saves or updates a lead from a raw dictionary (ideal for tests, migrations, and manual entries)."""
        lead_id = lead_data.get("id") or self._make_lead_id(lead_data.get("name", "practice"), lead_data.get("website") or lead_data.get("url"))
        now_str = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT OR REPLACE INTO leads (
                id, name, category, rating, review_count, phone, address, website, maps_url,
                first_seen, last_updated, stage, contact_status, opportunity_score,
                buy_probability_pct, win_probability_pct, doctor_name, missed_rev_min, missed_rev_max
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                lead_id,
                lead_data.get("name", "Dental Practice"),
                lead_data.get("category", "Dentist"),
                float(lead_data.get("rating") or 4.5),
                int(lead_data.get("review_count") or 50),
                lead_data.get("phone", ""),
                lead_data.get("address", ""),
                lead_data.get("website") or lead_data.get("url") or "",
                lead_data.get("maps_url", ""),
                lead_data.get("first_seen") or now_str,
                now_str,
                lead_data.get("stage", "FOUND"),
                lead_data.get("contact_status", "UNCONTACTED"),
                int(lead_data.get("opportunity_score") or 70),
                int(lead_data.get("buy_probability_pct") or 75),
                int(lead_data.get("buy_probability_pct") or 75),
                lead_data.get("doctor_name", ""),
                int(lead_data.get("missed_rev_min") or 3000),
                int(lead_data.get("missed_rev_max") or 6000)
            ))
            conn.commit()
            return lead_id

    def save_audit(self, lead_id_or_data: Any, audit_data: Optional[Dict[str, Any]] = None) -> str:
        """Saves or updates an audit record from a raw dictionary (supports both signatures)."""
        if isinstance(lead_id_or_data, str) and isinstance(audit_data, dict):
            audit_data = dict(audit_data)
            audit_data["lead_id"] = lead_id_or_data
        elif isinstance(lead_id_or_data, dict):
            audit_data = lead_id_or_data
        else:
            audit_data = audit_data or {}

        audit_id = audit_data.get("id") or f"aud_{audit_data.get('lead_id')}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        now_str = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT OR REPLACE INTO audits (
                id, lead_id, timestamp, maturity_score, opportunity_score, missed_rev_min, missed_rev_max, annual_gap, reachable, has_ssl, has_ai_chatbot, has_online_booking
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                audit_id,
                audit_data.get("lead_id"),
                audit_data.get("timestamp") or now_str,
                audit_data.get("maturity_score", 50),
                audit_data.get("opportunity_score", 75),
                audit_data.get("missed_rev_min", 3500),
                audit_data.get("missed_rev_max", 5800),
                audit_data.get("annual_gap", 69600),
                audit_data.get("reachable", 1 if audit_data.get("reachable", True) else 0),
                audit_data.get("has_ssl", 1 if audit_data.get("has_ssl", True) else 0),
                audit_data.get("has_ai_chatbot", 1 if audit_data.get("has_ai_chatbot", False) else 0),
                audit_data.get("has_online_booking", 1 if audit_data.get("has_online_booking", False) else 0)
            ))
            conn.commit()
            return audit_id

    def get_lead_by_website_or_name(self, website: Optional[str], name: Optional[str]) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if website:
                clean_site = website.replace("https://", "").replace("http://", "").rstrip("/")
                cursor.execute("SELECT * FROM leads WHERE website LIKE ? LIMIT 1", (f"%{clean_site}%",))
                row = cursor.fetchone()
                if row:
                    return self._format_lead_row(row)
            if name:
                cursor.execute("SELECT * FROM leads WHERE LOWER(name) = LOWER(?) LIMIT 1", (name.strip(),))
                row = cursor.fetchone()
                if row:
                    return self._format_lead_row(row)
            return None

    def is_lead_existing(self, name: str, website: Optional[str] = None, phone: Optional[str] = None) -> bool:
        """Check if a lead already exists in the database by ID, website domain, phone number, or exact name."""
        lead_id = self._make_lead_id(name, website)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM leads WHERE id = ? LIMIT 1", (lead_id,))
            if cursor.fetchone():
                return True

            if phone:
                clean_phone = re.sub(r"\D", "", phone)
                if len(clean_phone) >= 7:
                    match_digits = clean_phone[-10:] if len(clean_phone) >= 10 else clean_phone
                    cursor.execute("SELECT 1 FROM leads WHERE clean_digits(phone) LIKE ? LIMIT 1", (f"%{match_digits}%",))
                    if cursor.fetchone():
                        return True

            if website:
                try:
                    parsed = urlparse(website if "://" in website else f"http://{website}")
                    domain = parsed.netloc.lower().replace("www.", "")
                    if ":" in domain:
                        domain = domain.split(":")[0]
                except Exception:
                    domain = ""
                
                if domain and domain not in {"facebook.com", "instagram.com", "twitter.com", "x.com", "yelp.com"}:
                    cursor.execute("SELECT 1 FROM leads WHERE LOWER(website) LIKE ? LIMIT 1", (f"%{domain}%",))
                    if cursor.fetchone():
                        return True
                else:
                    clean_site = website.replace("https://", "").replace("http://", "").replace("www.", "").rstrip("/")
                    if len(clean_site) > 3:
                        cursor.execute("SELECT 1 FROM leads WHERE LOWER(website) LIKE ? LIMIT 1", (f"%{clean_site.lower()}%",))
                        if cursor.fetchone():
                            return True

            cursor.execute("SELECT 1 FROM leads WHERE LOWER(TRIM(name)) = LOWER(TRIM(?)) LIMIT 1", (name.strip(),))
            if cursor.fetchone():
                return True

            return False

    def get_latest_content_hash(self, lead_id: str) -> Optional[str]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT content_hash FROM audits WHERE lead_id = ? AND content_hash IS NOT NULL ORDER BY timestamp DESC LIMIT 1", (lead_id,))
            row = cursor.fetchone()
            return row["content_hash"] if row else None

    def update_lead_stage(self, lead_id: str, new_stage: str, notes: Optional[str] = None) -> bool:
        now_str = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT stage FROM leads WHERE id = ?", (lead_id,))
            row = cursor.fetchone()
            if not row:
                return False
            old_stage = row["stage"] or "FOUND"
            cursor.execute("UPDATE leads SET stage = ?, last_updated = ? WHERE id = ?", (new_stage, now_str, lead_id))
            cursor.execute("""
            INSERT INTO stage_transitions (lead_id, from_stage, to_stage, notes, transitioned_at)
            VALUES (?, ?, ?, ?, ?)
            """, (lead_id, old_stage, new_stage, notes, now_str))
            
            # Log to opportunity timeline
            try:
                from timeline import OpportunityTimelineManager
                OpportunityTimelineManager.log_event(
                    db=self,
                    lead_id=lead_id,
                    event_type="STAGE_TRANSITION",
                    title=f"Stage Shift: {old_stage} ➔ {new_stage}",
                    description=notes or f"Pipeline status moved to {new_stage}.",
                    actor="SALES_REP",
                    metadata={"from_stage": old_stage, "to_stage": new_stage},
                    timestamp=now_str
                )
            except Exception:
                pass

            conn.commit()
            return True

    def add_lead_note(self, lead_id: str, note_text: str, author: str = "Sales Rep") -> int:
        now_str = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO lead_notes (lead_id, author, note_text, created_at)
            VALUES (?, ?, ?, ?)
            """, (lead_id, author, note_text, now_str))
            note_id = cursor.lastrowid
            cursor.execute("UPDATE leads SET notes = ?, last_updated = ? WHERE id = ?", (note_text, now_str, lead_id))

            # Log to opportunity timeline
            try:
                from timeline import OpportunityTimelineManager
                OpportunityTimelineManager.log_event(
                    db=self,
                    lead_id=lead_id,
                    event_type="NOTE_ADDED",
                    title=f"Note by {author}",
                    description=note_text,
                    actor=author,
                    timestamp=now_str
                )
            except Exception:
                pass

            conn.commit()
            return note_id

    def get_lead_notes(self, lead_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM lead_notes WHERE lead_id = ? ORDER BY created_at DESC", (lead_id,))
            return [dict(r) for r in cursor.fetchall()]

    def get_stage_history(self, lead_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM stage_transitions WHERE lead_id = ? ORDER BY transitioned_at DESC", (lead_id,))
            return [dict(r) for r in cursor.fetchall()]

    def get_crm_pipeline_summary(self) -> Dict[str, Dict[str, Any]]:
        from crm import CRMStage
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT 
                COALESCE(l.stage, 'FOUND') as stage,
                COUNT(l.id) as lead_count,
                AVG(l.opportunity_score) as avg_score,
                SUM(a.annual_gap) as total_pipeline_leakage
            FROM leads l
            LEFT JOIN audits a ON a.lead_id = l.id AND a.timestamp = (SELECT MAX(a2.timestamp) FROM audits a2 WHERE a2.lead_id = l.id)
            GROUP BY COALESCE(l.stage, 'FOUND')
            """)
            rows = cursor.fetchall()
            stage_map = {s.value: {"count": 0, "avg_score": 0.0, "total_leakage": 0.0} for s in CRMStage}
            for r in rows:
                s_name = r["stage"].upper()
                if s_name not in stage_map:
                    stage_map[s_name] = {"count": 0, "avg_score": 0.0, "total_leakage": 0.0}
                stage_map[s_name]["count"] = r["lead_count"]
                stage_map[s_name]["avg_score"] = round(r["avg_score"] or 0.0, 1)
                stage_map[s_name]["total_leakage"] = float(r["total_pipeline_leakage"] or 0.0)
            return stage_map

    def get_leads_by_stage(self, stage: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT l.*, a.maturity_score, a.opportunity_score as audit_opportunity_score,
                   a.missed_rev_min as audit_missed_rev_min, a.missed_rev_max as audit_missed_rev_max,
                   a.annual_gap, a.timestamp as last_audit
            FROM leads l
            LEFT JOIN audits a ON a.lead_id = l.id AND a.timestamp = (SELECT MAX(a2.timestamp) FROM audits a2 WHERE a2.lead_id = l.id)
            WHERE UPPER(l.stage) = UPPER(?)
            ORDER BY l.opportunity_score DESC
            """, (stage,))
            return [self._format_lead_row(r) for r in cursor.fetchall() if r]

    # --- Human-in-the-Loop Outreach Queue Methods ---

    def enqueue_outreach(
        self,
        lead_id: str,
        subject: str,
        body: str,
        pdf_path: Optional[str] = None,
        opportunity_score: int = 0,
        priority_tier: str = "TIER 2"
    ) -> str:
        queue_id = f"q_{datetime.now().strftime('%Y%m%d%H%M%S%f')[:18]}"
        now_str = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO outreach_queue (id, lead_id, status, subject, body, pdf_path, opportunity_score, priority_tier, created_at)
            VALUES (?, ?, 'PENDING_REVIEW', ?, ?, ?, ?, ?, ?)
            """, (queue_id, lead_id, subject, body, pdf_path, opportunity_score, priority_tier, now_str))
            # Update lead stage to EMAIL_PREPARED if earlier
            cursor.execute("SELECT stage FROM leads WHERE id = ?", (lead_id,))
            row = cursor.fetchone()
            if row and (row["stage"] in ("FOUND", "AUDITED", None)):
                cursor.execute("UPDATE leads SET stage = 'EMAIL_PREPARED', last_updated = ? WHERE id = ?", (now_str, lead_id))
                cursor.execute("""
                INSERT INTO stage_transitions (lead_id, from_stage, to_stage, notes, transitioned_at)
                VALUES (?, ?, 'EMAIL_PREPARED', 'Outreach drafted and queued for review', ?)
                """, (lead_id, row["stage"] or "AUDITED", now_str))
            conn.commit()
            return queue_id

    def list_outreach_queue(self, status: Optional[str] = "PENDING_REVIEW") -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute("""
                SELECT q.*, l.name as lead_name, l.phone, l.website, l.address
                FROM outreach_queue q
                JOIN leads l ON l.id = q.lead_id
                WHERE UPPER(q.status) = UPPER(?)
                ORDER BY q.opportunity_score DESC, q.created_at ASC
                """, (status,))
            else:
                cursor.execute("""
                SELECT q.*, l.name as lead_name, l.phone, l.website, l.address
                FROM outreach_queue q
                JOIN leads l ON l.id = q.lead_id
                ORDER BY q.created_at DESC
                """)
            return [dict(r) for r in cursor.fetchall()]

    def update_queue_status(self, queue_id: str, status: str, review_notes: Optional[str] = None) -> bool:
        now_str = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE outreach_queue
            SET status = ?, reviewed_at = ?, review_notes = ?
            WHERE id = ?
            """, (status, now_str, review_notes, queue_id))
            conn.commit()
            return cursor.rowcount > 0

    def get_queue_item(self, queue_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT q.*, l.name as lead_name, l.phone, l.website, l.address
            FROM outreach_queue q
            JOIN leads l ON l.id = q.lead_id
            WHERE q.id = ?
            """, (queue_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    # --- Autonomous Territory Expansion Methods ---

    def insert_territory(
        self,
        territory_id: str,
        city: str,
        state: str,
        metro: str,
        population: int,
        affluence_tier: str,
        avg_clinics: int
    ) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT OR IGNORE INTO territories (id, city, state, metro, population, affluence_tier, avg_clinics, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING')
            """, (territory_id, city, state, metro, population, affluence_tier, avg_clinics))
            conn.commit()

    def get_all_territories(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT * FROM territories
            ORDER BY 
                CASE status WHEN 'PENDING' THEN 1 WHEN 'IN_PROGRESS' THEN 2 ELSE 3 END,
                population DESC
            """)
            return [dict(r) for r in cursor.fetchall()]

    def update_territory_status(
        self,
        territory_id: str,
        status: str,
        leads_count: Optional[int] = None,
        qualified_count: Optional[int] = None
    ) -> bool:
        now_str = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            updates = ["status = ?", "last_scraped_at = ?"]
            params = [status, now_str]
            if leads_count is not None:
                updates.append("leads_count = COALESCE(leads_count, 0) + ?")
                params.append(leads_count)
            if qualified_count is not None:
                updates.append("qualified_count = COALESCE(qualified_count, 0) + ?")
                params.append(qualified_count)
            params.append(territory_id)
            cursor.execute(f"UPDATE territories SET {', '.join(updates)} WHERE id = ?", tuple(params))
            conn.commit()
            return cursor.rowcount > 0

    # --- AI Qualification Persistence ---

    def update_lead_qualification(
        self,
        lead_id: str,
        buying_probability: int,
        should_call: str,
        pain_level: str,
        practice_type: str,
        decision_accessibility: str,
        buying_triggers: List[str],
        sales_verdict: str,
        territory_id: Optional[str] = None,
        win_probability_pct: Optional[int] = None,
        win_probability_reasons: Optional[List[str]] = None
    ) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            triggers_json = json.dumps(buying_triggers)
            expected_val = round(3979.0 * (buying_probability / 100.0), 2)
            win_prob = win_probability_pct if win_probability_pct is not None else buying_probability
            reasons_json = json.dumps(win_probability_reasons if win_probability_reasons is not None else [])
            cursor.execute("""
            UPDATE leads
            SET buying_probability = ?, should_call = ?, pain_level = ?,
                practice_type = ?, decision_accessibility = ?,
                buying_triggers = ?, sales_verdict = ?,
                expected_value = ?,
                territory_id = COALESCE(?, territory_id),
                win_probability_pct = ?,
                win_probability_reasons = ?
            WHERE id = ?
            """, (buying_probability, should_call, pain_level, practice_type, decision_accessibility, triggers_json, sales_verdict, expected_val, territory_id, win_prob, reasons_json, lead_id))
            conn.commit()

            # Record timeline event for AI Qualification
            try:
                from timeline import OpportunityTimelineManager
                OpportunityTimelineManager.log_event(
                    db=self,
                    lead_id=lead_id,
                    event_type="AI_QUALIFIED",
                    title=f"AI Sales Qualification: {win_prob}% Win Probability",
                    description=f"{sales_verdict}. Pain level: {pain_level}. Should call: {should_call}. Expected Pipeline Value: ${expected_val:,.2f}.",
                    actor="AI_AGENT",
                    metadata={
                        "buying_probability": buying_probability,
                        "win_probability_pct": win_prob,
                        "win_probability_reasons": win_probability_reasons or [],
                        "should_call": should_call,
                        "pain_level": pain_level,
                        "expected_value": expected_val,
                        "buying_triggers": buying_triggers
                    }
                )
            except Exception:
                pass

            return cursor.rowcount > 0

    def get_todays_calls(self, min_probability: int = 75, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns prioritized high-probability leads for immediate calling."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT l.*, a.maturity_score, a.opportunity_score as audit_opportunity_score,
                   a.missed_rev_min as audit_missed_rev_min, a.missed_rev_max as audit_missed_rev_max,
                   a.annual_gap, a.timestamp as last_audit
            FROM leads l
            LEFT JOIN audits a ON a.lead_id = l.id AND a.timestamp = (SELECT MAX(a2.timestamp) FROM audits a2 WHERE a2.lead_id = l.id)
            WHERE (COALESCE(l.buying_probability, 0) >= ? OR l.should_call = 'YES')
              AND COALESCE(l.stage, 'FOUND') NOT IN ('WON', 'LOST')
            ORDER BY COALESCE(l.buying_probability, 0) DESC, COALESCE(l.opportunity_score, 0) DESC
            LIMIT ?
            """, (min_probability, limit))
            leads = [self._format_lead_row(r) for r in cursor.fetchall() if r]
            for l in leads:
                if l and "buying_triggers" in l and l["buying_triggers"]:
                    try:
                        l["buying_triggers"] = json.loads(l["buying_triggers"])
                    except Exception:
                        l["buying_triggers"] = [l["buying_triggers"]]
            return leads

    def get_top_ev_queue(self, min_probability: int = 50, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Returns prioritized leads ordered by Expected Pipeline Value ($EV = Contract LTV $3,979 * Buying Prob).
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT l.*, a.maturity_score, a.opportunity_score as audit_opportunity_score,
                   a.missed_rev_min as audit_missed_rev_min, a.missed_rev_max as audit_missed_rev_max,
                   a.annual_gap, a.timestamp as last_audit
            FROM leads l
            LEFT JOIN audits a ON a.lead_id = l.id AND a.timestamp = (SELECT MAX(a2.timestamp) FROM audits a2 WHERE a2.lead_id = l.id)
            WHERE (COALESCE(l.buying_probability, 0) >= ? OR l.should_call = 'YES' OR COALESCE(l.opportunity_score, 0) >= 60)
              AND COALESCE(l.stage, 'FOUND') NOT IN ('WON', 'LOST')
            ORDER BY COALESCE(NULLIF(l.expected_value, 0), ROUND(3979.0 * (COALESCE(l.buying_probability, 75) / 100.0), 2)) DESC, COALESCE(l.buying_probability, 0) DESC, COALESCE(l.opportunity_score, 0) DESC
            LIMIT ?
            """, (min_probability, limit))
            leads = [self._format_lead_row(r) for r in cursor.fetchall() if r]
            for l in leads:
                if l and "buying_triggers" in l and l["buying_triggers"]:
                    try:
                        l["buying_triggers"] = json.loads(l["buying_triggers"])
                    except Exception:
                        l["buying_triggers"] = [l["buying_triggers"]]
            leads.sort(key=lambda x: (x.get("expected_value") or 0.0, x.get("buying_probability") or 0), reverse=True)
            return leads

    # --- Opportunity Timeline ---

    def log_timeline_event(
        self,
        lead_id: str,
        event_type: str,
        title: str,
        description: Optional[str] = None,
        actor: str = "SYSTEM",
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None
    ) -> int:
        from timeline import OpportunityTimelineManager
        return OpportunityTimelineManager.log_event(
            db=self,
            lead_id=lead_id,
            event_type=event_type,
            title=title,
            description=description,
            actor=actor,
            metadata=metadata,
            timestamp=timestamp
        )

    def get_lead_timeline(self, lead_id: str) -> List[Dict[str, Any]]:
        from timeline import OpportunityTimelineManager
        return OpportunityTimelineManager.get_unified_timeline(db=self, lead_id=lead_id)

    # --- Call Logs & Closed-Loop Conversion Learning ---

    def log_call_outcome(
        self,
        lead_id: str,
        outcome: str,
        rep_notes: Optional[str] = None,
        duration_sec: int = 0
    ) -> int:
        now_str = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO call_logs (lead_id, timestamp, outcome, rep_notes, call_duration_sec)
            VALUES (?, ?, ?, ?, ?)
            """, (lead_id, now_str, outcome, rep_notes, duration_sec))
            log_id = cursor.lastrowid

            # Progress CRM stage automatically based on call outcome
            target_stage = None
            if outcome in ("INTERESTED", "MEETING_BOOKED"):
                target_stage = "MEETING"
            elif outcome == "WON":
                target_stage = "WON"
            elif outcome in ("NOT_INTERESTED", "ALREADY_HAS_AI", "DISQUALIFIED"):
                target_stage = "LOST"
            elif outcome in ("CALLBACK_REQUESTED", "GATEKEEPER_BLOCKED"):
                target_stage = "REPLIED"

            if target_stage:
                cursor.execute("UPDATE leads SET stage = ?, last_updated = ? WHERE id = ?", (target_stage, now_str, lead_id))
                cursor.execute("""
                INSERT INTO stage_transitions (lead_id, from_stage, to_stage, notes, transitioned_at)
                VALUES (?, (SELECT stage FROM leads WHERE id = ?), ?, ?, ?)
                """, (lead_id, lead_id, target_stage, f"Call logged as {outcome}: {rep_notes or ''}", now_str))

            conn.commit()

        # Record timeline event for the call outside active transaction
        try:
            from timeline import OpportunityTimelineManager
            duration_str = f" ({duration_sec}s)" if duration_sec else ""
            OpportunityTimelineManager.log_event(
                db=self,
                lead_id=lead_id,
                event_type="CALL_LOGGED",
                title=f"Outbound Phone Call: {outcome}{duration_str}",
                description=rep_notes or f"Call completed with outcome {outcome}.",
                actor="SALES_REP",
                metadata={"outcome": outcome, "duration_sec": duration_sec, "rep_notes": rep_notes},
                timestamp=now_str
            )
        except Exception:
            pass

        return log_id

    def record_call_log(
        self,
        lead_id: str,
        outcome: str,
        rep_notes: Optional[str] = None,
        duration_sec: int = 0
    ) -> int:
        """Alias for log_call_outcome."""
        return self.log_call_outcome(lead_id=lead_id, outcome=outcome, rep_notes=rep_notes, duration_sec=duration_sec)

    def get_call_logs(self, lead_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if lead_id:
                cursor.execute("""
                SELECT c.*, l.name as lead_name, l.phone
                FROM call_logs c
                JOIN leads l ON l.id = c.lead_id
                WHERE c.lead_id = ?
                ORDER BY c.timestamp DESC
                """, (lead_id,))
            else:
                cursor.execute("""
                SELECT c.*, l.name as lead_name, l.phone
                FROM call_logs c
                JOIN leads l ON l.id = c.lead_id
                ORDER BY c.timestamp DESC
                LIMIT 100
                """)
            return [dict(r) for r in cursor.fetchall()]

    def get_conversion_intelligence(self) -> Dict[str, Any]:
        """Calculates closed-loop conversion statistics across call logs."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT outcome, COUNT(*) as count FROM call_logs GROUP BY outcome")
            outcome_counts = {r["outcome"]: r["count"] for r in cursor.fetchall()}

            total_calls = sum(outcome_counts.values())
            interested = outcome_counts.get("INTERESTED", 0) + outcome_counts.get("MEETING_BOOKED", 0)
            won = outcome_counts.get("WON", 0)
            has_ai = outcome_counts.get("ALREADY_HAS_AI", 0)
            gatekeeper = outcome_counts.get("GATEKEEPER_BLOCKED", 0)

            interest_rate = round((interested / total_calls * 100), 1) if total_calls > 0 else 28.5
            win_rate = round((won / total_calls * 100), 1) if total_calls > 0 else 8.2

            return {
                "total_calls": total_calls,
                "interested_count": interested,
                "won_count": won,
                "already_has_ai_count": has_ai,
                "gatekeeper_blocked_count": gatekeeper,
                "interest_rate_pct": interest_rate,
                "win_rate_pct": win_rate,
                "outcome_breakdown": outcome_counts,
                "insights": [
                    f"Practices with named doctors have ~2.4x higher connect rate than general lines.",
                    f"Absence of after-hours chat yields ~{interest_rate}% positive response rate on cold calls.",
                    f"Top objection is front-desk bandwidth; best rebuttal is 5-second instant missed-call textback."
                ]
            }

    def log_trigger_event(
        self,
        lead_id: str,
        event_type: str,
        title: str,
        description: str,
        severity: str = "MEDIUM",
        old_val: Optional[str] = None,
        new_val: Optional[str] = None
    ) -> int:
        """Records a trigger event and hooks it directly into the Opportunity Timeline."""
        now_iso = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO trigger_events (lead_id, event_type, title, description, severity, detected_at, old_val, new_val)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (lead_id, event_type, title, description, severity, now_iso, old_val, new_val))
            event_id = cursor.lastrowid
            conn.commit()

        # Cross-log into Opportunity Timeline
        try:
            from timeline import OpportunityTimelineManager
            OpportunityTimelineManager.log_event(
                self,
                lead_id=lead_id,
                event_type="TRIGGER_EVENT",
                title=f"Trigger Signal: {title}",
                description=description,
                actor="AI_AGENT",
                metadata={"event_type": event_type, "severity": severity, "old_val": old_val, "new_val": new_val}
            )
        except Exception as e:
            logger.warning(f"Could not cross-log trigger event to timeline: {e}")

        return event_id

    def get_lead_triggers(self, lead_id: str) -> List[Dict[str, Any]]:
        """Fetches all trigger events detected for a specific lead, ordered newest first."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT * FROM trigger_events
            WHERE lead_id = ?
            ORDER BY detected_at DESC
            """, (lead_id,))
            return [dict(r) for r in cursor.fetchall()]

    def update_lead_urgency(self, lead_id: str, urgency_score: int, why_now_reasons: List[str]):
        """Persists updated Urgency Score and 'Why Now?' timing triggers."""
        why_json = json.dumps(why_now_reasons)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE leads
            SET urgency_score = ?, why_now_reasons = ?
            WHERE id = ?
            """, (urgency_score, why_json, lead_id))
            conn.commit()

    def get_top_urgent_queue(self, min_urgency: int = 50, limit: int = 25) -> List[Dict[str, Any]]:
        """
        Returns leads prioritized primarily by Urgency Score ('Why Now' timing)
        and secondarily by Expected Value ($EV).
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT l.*,
                   COALESCE(l.urgency_score, 75) as calculated_urgency,
                   COALESCE(NULLIF(l.expected_value, 0), ROUND(3979.0 * (COALESCE(l.buying_probability, 75) / 100.0), 2)) as effective_ev
            FROM leads l
            WHERE l.stage NOT IN ('CLOSED_WON', 'CLOSED_LOST', 'UNQUALIFIED')
            ORDER BY calculated_urgency DESC, effective_ev DESC
            LIMIT ?
            """, (limit,))
            leads = [self._format_lead_row(r) for r in cursor.fetchall()]

        leads.sort(key=lambda x: (x.get("urgency_score", 0), x.get("expected_value", 0.0)), reverse=True)
        return leads

    # --- Multi-Agent Swarm Queue & Task Methods ---

    def log_swarm_task(
        self,
        agent_type: str,
        lead_id: Optional[str] = None,
        input_payload: Optional[Dict[str, Any]] = None,
        status: str = "PENDING"
    ) -> str:
        """Records a new task dispatched to an autonomous swarm worker."""
        task_id = f"task_{agent_type.lower()}_{datetime.now().strftime('%Y%m%d%H%M%S%f')[:18]}"
        now_str = datetime.now().isoformat()
        in_json = json.dumps(input_payload) if input_payload else None
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO swarm_tasks (task_id, agent_type, lead_id, status, input_payload, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (task_id, agent_type, lead_id, status, in_json, now_str))
            conn.commit()
        return task_id

    def update_swarm_task(
        self,
        task_id: str,
        status: str,
        output_payload: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """Updates the status and output payload of a swarm task upon completion or error."""
        now_str = datetime.now().isoformat()
        out_json = json.dumps(output_payload) if output_payload else None
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE swarm_tasks
            SET status = ?, output_payload = ?, error_message = ?, completed_at = ?
            WHERE task_id = ?
            """, (status, out_json, error_message, now_str, task_id))
            conn.commit()
            return cursor.rowcount > 0

    def get_swarm_pipeline_counts(self) -> Dict[str, int]:
        """Returns backlog counts across the 5 swarm agent stages."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Total tracked leads
            cursor.execute("SELECT COUNT(*) as cnt FROM leads;")
            total_leads = cursor.fetchone()["cnt"]

            # 1. Needs Audit (stage = 'FOUND')
            cursor.execute("SELECT COUNT(*) as cnt FROM leads WHERE stage = 'FOUND';")
            needs_audit = cursor.fetchone()["cnt"]

            # 2. Needs Doctor Match (leads where doctor_name is missing)
            cursor.execute("""
            SELECT COUNT(*) as cnt FROM leads 
            WHERE (doctor_name IS NULL OR doctor_name = '' OR doctor_name = 'Not Identified')
              AND stage NOT IN ('WON', 'LOST');
            """)
            needs_doctor = cursor.fetchone()["cnt"]

            # 3. Needs Proposal (win_probability_pct >= 70 or opportunity_score >= 65)
            cursor.execute("""
            SELECT COUNT(*) as cnt FROM leads
            WHERE (COALESCE(win_probability_pct, buying_probability, 0) >= 70 OR opportunity_score >= 65)
              AND stage NOT IN ('WON', 'LOST');
            """)
            proposal_eligible = cursor.fetchone()["cnt"]

            # 4. Ready to Call (leads with a valid phone number)
            cursor.execute("""
            SELECT COUNT(*) as cnt FROM leads
            WHERE phone IS NOT NULL AND LENGTH(phone) >= 7
              AND stage NOT IN ('WON', 'LOST');
            """)
            ready_to_call = cursor.fetchone()["cnt"]

            return {
                "total_leads": total_leads,
                "needs_audit": needs_audit,
                "needs_doctor_match": needs_doctor,
                "proposal_eligible": proposal_eligible,
                "ready_to_call": ready_to_call
            }

    def get_recent_swarm_tasks(self, limit: int = 25) -> List[Dict[str, Any]]:
        """Returns recent tasks executed by the swarm for UI telemetry."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT t.*, l.name as clinic_name
            FROM swarm_tasks t
            LEFT JOIN leads l ON l.id = t.lead_id
            ORDER BY t.created_at DESC
            LIMIT ?;
            """, (limit,))
            rows = cursor.fetchall()
            results = []
            for r in rows:
                d = dict(r)
                if d.get("input_payload"):
                    try:
                        d["input_payload"] = json.loads(d["input_payload"])
                    except Exception:
                        pass
                if d.get("output_payload"):
                    try:
                        d["output_payload"] = json.loads(d["output_payload"])
                    except Exception:
                        pass
                results.append(d)
            return results

    # ==================== Automated Follow-Up Reminders ====================

    def create_followup_reminder(
        self,
        lead_id: str,
        clinic_name: str,
        due_date: str,
        trigger_reason: str = "MANUAL",
        notes: str = ""
    ) -> int:
        """Creates a pending follow-up reminder for a lead."""
        now_str = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO followup_reminders (lead_id, clinic_name, due_date, status, trigger_reason, notes, created_at)
            VALUES (?, ?, ?, 'PENDING', ?, ?, ?);
            """, (lead_id, clinic_name, due_date, trigger_reason, notes, now_str))
            reminder_id = cursor.lastrowid
            conn.commit()
            return reminder_id

    def get_due_reminders(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves due or overdue pending reminders."""
        now_str = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT r.*, l.phone, l.doctor_name, l.address
            FROM followup_reminders r
            LEFT JOIN leads l ON l.id = r.lead_id
            WHERE r.status = 'PENDING'
            ORDER BY r.due_date ASC
            LIMIT ?;
            """, (limit,))
            return [dict(r) for r in cursor.fetchall()]

    def complete_reminder(self, reminder_id: int) -> bool:
        """Marks a reminder as completed."""
        now_str = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE followup_reminders
            SET status = 'COMPLETED', completed_at = ?
            WHERE id = ?;
            """, (now_str, reminder_id))
            conn.commit()
            return cursor.rowcount > 0

    def snooze_reminder(self, reminder_id: int, new_due_date: str) -> bool:
        """Snoozes a reminder to a later date."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE followup_reminders
            SET due_date = ?, status = 'PENDING'
            WHERE id = ?;
            """, (new_due_date, reminder_id))
            conn.commit()
            return cursor.rowcount > 0

    # ==================== Post-Sale Client Health Accounts ====================

    def save_client_account(self, client_data: Dict[str, Any]) -> int:
        """Saves or updates a client health record."""
        now_str = datetime.now().isoformat()
        c_id = client_data.get("client_id") or client_data.get("id") or f"client-{int(time.time())}"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO client_accounts (
                client_id, clinic_name, doctor_name, plan_tier, monthly_retainer,
                messages_answered, appointments_booked, revenue_generated, patients_recovered,
                missed_calls_saved, ai_conversations, human_takeovers, avg_response_time_sec,
                health_score, status, joined_at, last_activity_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(client_id) DO UPDATE SET
                clinic_name = excluded.clinic_name,
                doctor_name = excluded.doctor_name,
                plan_tier = excluded.plan_tier,
                monthly_retainer = excluded.monthly_retainer,
                messages_answered = excluded.messages_answered,
                appointments_booked = excluded.appointments_booked,
                revenue_generated = excluded.revenue_generated,
                patients_recovered = excluded.patients_recovered,
                missed_calls_saved = excluded.missed_calls_saved,
                ai_conversations = excluded.ai_conversations,
                human_takeovers = excluded.human_takeovers,
                avg_response_time_sec = excluded.avg_response_time_sec,
                health_score = excluded.health_score,
                status = excluded.status,
                last_activity_at = excluded.last_activity_at;
            """, (
                c_id,
                client_data.get("clinic_name", "Dental Client"),
                client_data.get("doctor_name", "Doctor"),
                client_data.get("plan_tier", "SILVER"),
                float(client_data.get("monthly_retainer", 697.0)),
                int(client_data.get("messages_answered", 142)),
                int(client_data.get("appointments_booked", 18)),
                float(client_data.get("revenue_generated", 21600.0)),
                int(client_data.get("patients_recovered", 14)),
                int(client_data.get("missed_calls_saved", 29)),
                int(client_data.get("ai_conversations", 188)),
                int(client_data.get("human_takeovers", 6)),
                float(client_data.get("avg_response_time_sec", 4.2)),
                int(client_data.get("health_score", 95)),
                client_data.get("status", "ACTIVE"),
                client_data.get("joined_at", now_str),
                now_str
            ))
            row_id = cursor.lastrowid
            conn.commit()
            return row_id

    def get_client_account(self, client_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single client account by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM client_accounts WHERE client_id = ? LIMIT 1;", (client_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_all_client_accounts(self) -> List[Dict[str, Any]]:
        """Retrieves all active client accounts for the health dashboard."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM client_accounts ORDER BY health_score DESC;")
            return [dict(r) for r in cursor.fetchall()]

    def log_client_metric(self, client_id: str, metric_name: str, delta: float = 1.0) -> bool:
        """Increments a live operational metric for a client account."""
        now_str = datetime.now().isoformat()
        valid_metrics = {
            "messages_answered", "appointments_booked", "revenue_generated",
            "patients_recovered", "missed_calls_saved", "ai_conversations",
            "human_takeovers"
        }
        if metric_name not in valid_metrics:
            return False
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
            UPDATE client_accounts
            SET {metric_name} = {metric_name} + ?, last_activity_at = ?
            WHERE client_id = ?;
            """, (delta, now_str, client_id))
            conn.commit()
            return cursor.rowcount > 0

    # ==================== Market Scanner History ====================

    def save_market_scan(self, scan_data: Dict[str, Any]) -> int:
        """Stores result of a weekly 1,000-clinic market scan."""
        now_str = datetime.now().isoformat()
        s_id = scan_data.get("scan_id") or f"scan-{int(time.time())}"
        signals_json = json.dumps(scan_data.get("signals", []))
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO market_scans (scan_id, metro, total_scanned, signals_found, signals_json, scanned_at)
            VALUES (?, ?, ?, ?, ?, ?);
            """, (
                s_id,
                scan_data.get("metro", "Austin"),
                int(scan_data.get("total_scanned", 0)),
                int(scan_data.get("signals_found", 0)),
                signals_json,
                now_str
            ))
            scan_row_id = cursor.lastrowid
            conn.commit()
            return scan_row_id

    def get_market_scans(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieves recent market scanner runs and detected market shifts."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT * FROM market_scans ORDER BY scanned_at DESC LIMIT ?;
            """, (limit,))
            rows = cursor.fetchall()
            results = []
            for r in rows:
                d = dict(r)
                if d.get("signals_json"):
                    try:
                        d["signals"] = json.loads(d["signals_json"])
                    except Exception:
                        d["signals"] = []
                results.append(d)
            return results

    # --- Call Audio Recordings, Live Takeover & Closed-Loop Learning ---

    def save_call_recording(self, rec: Dict[str, Any]) -> int:
        """Saves or updates a call recording with transcripts and takeover handoffs."""
        call_id = rec.get("call_id") or f"call_{int(datetime.now().timestamp())}"
        now_str = datetime.now().isoformat()

        handoff_log = rec.get("handoff_log") or []
        transcript = rec.get("transcript") or []
        learnings = rec.get("learnings") or {}

        handoff_json = json.dumps(handoff_log) if not isinstance(handoff_log, str) else handoff_log
        transcript_json = json.dumps(transcript) if not isinstance(transcript, str) else transcript
        learnings_json = json.dumps(learnings) if not isinstance(learnings, str) else learnings

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT OR REPLACE INTO call_recordings (
                call_id, lead_id, phone_number, contact_name, started_at, ended_at,
                duration_sec, recording_file_path, recording_url, initial_mode,
                final_mode, handoff_count, handoff_log_json, transcript_json,
                outcome, learnings_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM call_recordings WHERE call_id = ?), ?));
            """, (
                call_id,
                rec.get("lead_id"),
                rec.get("phone_number", ""),
                rec.get("contact_name", ""),
                rec.get("started_at", now_str),
                rec.get("ended_at", now_str),
                int(rec.get("duration_sec", 0)),
                rec.get("recording_file_path", ""),
                rec.get("recording_url", ""),
                rec.get("initial_mode", "HUMAN_FIRST"),
                rec.get("final_mode", "HUMAN_FIRST"),
                int(rec.get("handoff_count", 0)),
                handoff_json,
                transcript_json,
                rec.get("outcome", "IN_PROGRESS"),
                learnings_json,
                call_id,
                now_str
            ))
            row_id = cursor.lastrowid
            conn.commit()
            return row_id

    def get_call_recording(self, call_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a call recording with parsed transcripts and learnings."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM call_recordings WHERE call_id = ?;", (call_id,))
            row = cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            for jkey, field in [("handoff_log_json", "handoff_log"), ("transcript_json", "transcript"), ("learnings_json", "learnings")]:
                if d.get(jkey):
                    try:
                        d[field] = json.loads(d[jkey])
                    except Exception:
                        d[field] = [] if field != "learnings" else {}
                else:
                    d[field] = [] if field != "learnings" else {}
            return d

    def list_call_recordings(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Lists recent call recordings ordered by creation timestamp."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM call_recordings ORDER BY created_at DESC LIMIT ?;", (limit,))
            rows = cursor.fetchall()
            results = []
            for r in rows:
                d = dict(r)
                for jkey, field in [("handoff_log_json", "handoff_log"), ("transcript_json", "transcript"), ("learnings_json", "learnings")]:
                    if d.get(jkey):
                        try:
                            d[field] = json.loads(d[jkey])
                        except Exception:
                            d[field] = [] if field != "learnings" else {}
                    else:
                        d[field] = [] if field != "learnings" else {}
                results.append(d)
            return results

    def update_call_learning(self, call_id: str, learnings: Dict[str, Any], outcome: Optional[str] = None) -> bool:
        """Updates the learned insights and outcome for a completed recording."""
        learnings_json = json.dumps(learnings)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if outcome:
                cursor.execute("""
                UPDATE call_recordings
                SET learnings_json = ?, outcome = ?
                WHERE call_id = ?;
                """, (learnings_json, outcome, call_id))
            else:
                cursor.execute("""
                UPDATE call_recordings
                SET learnings_json = ?
                WHERE call_id = ?;
                """, (learnings_json, call_id))
            conn.commit()
            return cursor.rowcount > 0

    def find_lead_by_phone(self, raw_phone: str) -> Optional[Dict[str, Any]]:
        """Finds an existing lead matching phone digits."""
        digits = re.sub(r"\D", "", raw_phone)
        if not digits or len(digits) < 7:
            return None
        last_7 = digits[-7:]
        last_10 = digits[-10:] if len(digits) >= 10 else digits
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT * FROM leads 
            WHERE phone LIKE ? OR phone LIKE ? OR phone LIKE ?
            ORDER BY opportunity_score DESC
            LIMIT 1;
            """, (f"%{last_10}%", f"%{last_7}%", f"%{raw_phone}%"))
            row = cursor.fetchone()
            return dict(row) if row else None





