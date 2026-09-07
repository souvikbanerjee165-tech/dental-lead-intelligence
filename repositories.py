import json
import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from config import BASE_DIR
from models import RawLead
from evidence import Finding
from insights import BusinessInsight

DB_PATH = BASE_DIR / "storage.db"

class ILeadRepository(ABC):
    @abstractmethod
    def save_lead(self, lead: RawLead, lead_id: str) -> str:
        pass

    @abstractmethod
    def get_lead(self, lead_id: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def list_leads(self) -> List[Dict[str, Any]]:
        pass

class IAuditRepository(ABC):
    @abstractmethod
    def save_audit(self, audit_id: str, lead_id: str, data: Dict[str, Any]) -> str:
        pass

    @abstractmethod
    def get_latest_audit(self, lead_id: str) -> Optional[Dict[str, Any]]:
        pass

class IFindingRepository(ABC):
    @abstractmethod
    def save_findings(self, audit_id: str, lead_id: str, findings: List[Finding]):
        pass

    @abstractmethod
    def get_findings(self, audit_id: str) -> List[Dict[str, Any]]:
        pass

class IInsightRepository(ABC):
    @abstractmethod
    def save_insights(self, audit_id: str, lead_id: str, insights: List[BusinessInsight]):
        pass

    @abstractmethod
    def get_insights(self, audit_id: str) -> List[Dict[str, Any]]:
        pass

from contextlib import contextmanager

# --- SQLite Concrete Implementations ---

class SQLiteLeadRepository(ILeadRepository):
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path

    @contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def save_lead(self, lead: RawLead, lead_id: str) -> str:
        now_str = datetime.now().isoformat()
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM leads WHERE id = ?", (lead_id,))
            exists = cursor.fetchone()
            if not exists:
                cursor.execute("""
                INSERT INTO leads (id, name, category, rating, review_count, phone, address, website, maps_url, first_seen, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    lead_id, lead.name, lead.category, lead.rating, lead.review_count,
                    lead.phone, lead.address, lead.website, lead.maps_url, now_str, now_str
                ))
            else:
                cursor.execute("""
                UPDATE leads SET
                    rating = COALESCE(?, rating),
                    review_count = COALESCE(?, review_count),
                    phone = COALESCE(?, phone),
                    address = COALESCE(?, address),
                    website = COALESCE(?, website),
                    last_updated = ?
                WHERE id = ?
                """, (lead.rating, lead.review_count, lead.phone, lead.address, lead.website, now_str, lead_id))
            conn.commit()
        return lead_id

    def get_lead(self, lead_id: str) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM leads WHERE id = ?", (lead_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_leads(self) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM leads ORDER BY last_updated DESC")
            return [dict(r) for r in cursor.fetchall()]

class SQLiteAuditRepository(IAuditRepository):
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path

    @contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def save_audit(self, audit_id: str, lead_id: str, data: Dict[str, Any]) -> str:
        now_str = datetime.now().isoformat()
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT OR REPLACE INTO audits (id, lead_id, timestamp, maturity_score, opportunity_score, missed_rev_min, missed_rev_max, annual_gap)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                audit_id, lead_id, now_str,
                data.get("maturity_score", 0),
                data.get("opportunity_score", 0),
                data.get("missed_rev_min", 0),
                data.get("missed_rev_max", 0),
                data.get("annual_gap", 0)
            ))
            conn.commit()
        return audit_id

    def get_latest_audit(self, lead_id: str) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM audits WHERE lead_id = ? ORDER BY timestamp DESC LIMIT 1", (lead_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

class SQLiteFindingRepository(IFindingRepository):
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path

    @contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def save_findings(self, audit_id: str, lead_id: str, findings: List[Finding]):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            for f in findings:
                f_id = f"{audit_id}_{f.id}"
                ev_blob = json.dumps([e.model_dump() for e in f.evidence])
                cursor.execute("""
                INSERT OR REPLACE INTO findings (id, audit_id, lead_id, category, title, description, confidence, severity, recommendation, projected_roi, evidence_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    f_id, audit_id, lead_id, f.category, f.title, f.description,
                    f.confidence, f.severity, f.recommendation, f.projected_monthly_roi, ev_blob
                ))
            conn.commit()

    def get_findings(self, audit_id: str) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM findings WHERE audit_id = ? ORDER BY confidence DESC", (audit_id,))
            return [dict(r) for r in cursor.fetchall()]

class SQLiteInsightRepository(IInsightRepository):
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path

    @contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def save_insights(self, audit_id: str, lead_id: str, insights: List[BusinessInsight]):
        with self._get_conn() as conn:
            cursor = conn.cursor()
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
            for ins in insights:
                ins_id = f"{audit_id}_{ins.id}"
                findings_json = json.dumps(ins.supporting_finding_ids)
                cursor.execute("""
                INSERT OR REPLACE INTO insights (
                    id, audit_id, lead_id, insight_type, title, executive_summary,
                    impact_analysis, confidence, urgency, projected_annual_loss,
                    strategic_recommendation, supporting_finding_ids
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    ins_id, audit_id, lead_id, ins.insight_type, ins.title, ins.executive_summary,
                    ins.impact_analysis, ins.confidence, ins.urgency, ins.projected_annual_loss,
                    ins.strategic_recommendation, findings_json
                ))
            conn.commit()

    def get_insights(self, audit_id: str) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
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
            cursor.execute("SELECT * FROM insights WHERE audit_id = ? ORDER BY projected_annual_loss DESC", (audit_id,))
            return [dict(r) for r in cursor.fetchall()]
