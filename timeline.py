"""
Opportunity Timeline Engine.
Tracks the longitudinal life story of every dental practice:
- Discovery & territory origin
- Initial & recurring website audits
- Tech stack additions, removals, and changes
- Decision-maker identifications (Doctor / Office Manager)
- AI qualification & buying triggers
- Personalized outreach generation
- Live phone calls and recorded outcomes
- Pipeline stage movements and rep notes
- AI roleplay simulation training
"""

import json
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field

logger = logging.getLogger("opportunity_timeline")


class TimelineEvent(BaseModel):
    id: Optional[int] = None
    lead_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    event_type: str  # FIRST_DISCOVERED, AUDIT_COMPLETED, STACK_CHANGE, DECISION_MAKER_MATCH, AI_QUALIFIED, OUTREACH_STAGED, CALL_LOGGED, STAGE_TRANSITION, NOTE_ADDED, SIMULATION_PRACTICED
    title: str
    description: Optional[str] = None
    actor: str = "SYSTEM"  # SYSTEM, AI_AGENT, SALES_REP
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OpportunityTimelineManager:
    """Manages recording and aggregating longitudinal events for a practice."""

    EVENT_ICONS = {
        "FIRST_DISCOVERED": "📍",
        "AUDIT_COMPLETED": "⚡",
        "STACK_CHANGE": "🔄",
        "DECISION_MAKER_MATCH": "👨‍⚕️",
        "AI_QUALIFIED": "🎯",
        "OUTREACH_STAGED": "✉️",
        "CALL_LOGGED": "📞",
        "STAGE_TRANSITION": "🚀",
        "NOTE_ADDED": "📝",
        "SIMULATION_PRACTICED": "🥋",
        "TRIGGER_EVENT": "🔥",
        "CHANGE_DETECTED": "🔍",
    }

    EVENT_BADGES = {
        "FIRST_DISCOVERED": "bg-slate-800 text-slate-300",
        "AUDIT_COMPLETED": "bg-blue-900/60 text-blue-300 border border-blue-500/30",
        "STACK_CHANGE": "bg-amber-900/60 text-amber-300 border border-amber-500/30",
        "DECISION_MAKER_MATCH": "bg-emerald-900/60 text-emerald-300 border border-emerald-500/30",
        "AI_QUALIFIED": "bg-indigo-900/60 text-indigo-300 border border-indigo-500/30",
        "OUTREACH_STAGED": "bg-purple-900/60 text-purple-300 border border-purple-500/30",
        "CALL_LOGGED": "bg-emerald-800 text-emerald-100",
        "STAGE_TRANSITION": "bg-pink-900/60 text-pink-300 border border-pink-500/30",
        "NOTE_ADDED": "bg-gray-800 text-gray-300",
        "SIMULATION_PRACTICED": "bg-cyan-900/60 text-cyan-300 border border-cyan-500/30",
        "TRIGGER_EVENT": "bg-rose-900/60 text-rose-300 border border-rose-500/30",
        "CHANGE_DETECTED": "bg-amber-900/60 text-amber-300 border border-amber-500/30",
    }

    @classmethod
    def log_event(
        cls,
        db: Any,
        lead_id: str,
        event_type: str,
        title: str,
        description: Optional[str] = None,
        actor: str = "SYSTEM",
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None
    ) -> int:
        """Records a timeline event in the database."""
        event_ts = timestamp or datetime.now().isoformat()
        meta_json = json.dumps(metadata or {})
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO opportunity_timeline (lead_id, timestamp, event_type, title, description, actor, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (lead_id, event_ts, event_type, title, description, actor, meta_json))
            conn.commit()
            return cursor.lastrowid

    @classmethod
    def get_unified_timeline(cls, db: Any, lead_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves a complete chronological story of the practice by uniting:
        1. Explicit opportunity_timeline records.
        2. Historical audits and changes.
        3. Phone call logs and outcomes.
        4. CRM stage transitions.
        5. Lead notes.
        Sorted newest first.
        """
        events = []

        with db._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Fetch explicit timeline events
            cursor.execute("""
            SELECT id, lead_id, timestamp, event_type, title, description, actor, metadata_json
            FROM opportunity_timeline
            WHERE lead_id = ?
            ORDER BY timestamp DESC
            """, (lead_id,))
            for row in cursor.fetchall():
                meta = {}
                if row["metadata_json"]:
                    try:
                        meta = json.loads(row["metadata_json"])
                    except Exception:
                        pass
                events.append({
                    "id": f"timeline_{row['id']}",
                    "timestamp": row["timestamp"],
                    "event_type": row["event_type"],
                    "title": row["title"],
                    "description": row["description"] or "",
                    "actor": row["actor"] or "SYSTEM",
                    "icon": cls.EVENT_ICONS.get(row["event_type"], "📌"),
                    "badge_class": cls.EVENT_BADGES.get(row["event_type"], "bg-slate-800 text-slate-300"),
                    "metadata": meta
                })

            # 2. Check audits if not already in timeline
            cursor.execute("""
            SELECT id, timestamp, maturity_score, opportunity_score, missed_rev_min, missed_rev_max, annual_gap
            FROM audits
            WHERE lead_id = ?
            """, (lead_id,))
            audits = cursor.fetchall()
            audit_timestamps = {e["timestamp"] for e in events if e["event_type"] == "AUDIT_COMPLETED"}
            for a in audits:
                if a["timestamp"] not in audit_timestamps:
                    events.append({
                        "id": f"audit_{a['id']}",
                        "timestamp": a["timestamp"],
                        "event_type": "AUDIT_COMPLETED",
                        "title": f"Digital Gap Audit Completed (Score: {a['opportunity_score']}/100)",
                        "description": f"Maturity score: {a['maturity_score']}/100. Estimated annual revenue leak: ${a['annual_gap']:,} (Range: ${a['missed_rev_min']:,} - ${a['missed_rev_max']:,}).",
                        "actor": "AI_AGENT",
                        "icon": cls.EVENT_ICONS["AUDIT_COMPLETED"],
                        "badge_class": cls.EVENT_BADGES["AUDIT_COMPLETED"],
                        "metadata": {
                            "opportunity_score": a["opportunity_score"],
                            "annual_gap": a["annual_gap"],
                            "maturity_score": a["maturity_score"]
                        }
                    })

            # 3. Check changes (stack updates / website changes)
            cursor.execute("""
            SELECT id, change_type, summary, previous_val, new_val, detected_at
            FROM changes
            WHERE lead_id = ?
            """, (lead_id,))
            changes = cursor.fetchall()
            for c in changes:
                events.append({
                    "id": f"change_{c['id']}",
                    "timestamp": c["detected_at"],
                    "event_type": "STACK_CHANGE",
                    "title": f"Change Detected: {c['change_type']}",
                    "description": c["summary"],
                    "actor": "AI_MONITOR",
                    "icon": cls.EVENT_ICONS["STACK_CHANGE"],
                    "badge_class": cls.EVENT_BADGES["STACK_CHANGE"],
                    "metadata": {
                        "previous": c["previous_val"],
                        "new": c["new_val"]
                    }
                })

            # 4. Check call logs
            cursor.execute("""
            SELECT id, timestamp, outcome, rep_notes, call_duration_sec
            FROM call_logs
            WHERE lead_id = ?
            """, (lead_id,))
            call_logs = cursor.fetchall()
            call_timestamps = {e["timestamp"] for e in events if e["event_type"] == "CALL_LOGGED"}
            for cl in call_logs:
                if cl["timestamp"] not in call_timestamps:
                    duration_str = f" ({cl['call_duration_sec']}s)" if cl["call_duration_sec"] else ""
                    events.append({
                        "id": f"call_{cl['id']}",
                        "timestamp": cl["timestamp"],
                        "event_type": "CALL_LOGGED",
                        "title": f"Phone Call: {cl['outcome']}{duration_str}",
                        "description": cl["rep_notes"] or f"Cold call completed with outcome {cl['outcome']}.",
                        "actor": "SALES_REP",
                        "icon": cls.EVENT_ICONS["CALL_LOGGED"],
                        "badge_class": cls.EVENT_BADGES["CALL_LOGGED"],
                        "metadata": {
                            "outcome": cl["outcome"],
                            "duration_sec": cl["call_duration_sec"]
                        }
                    })

            # 5. Check stage transitions
            cursor.execute("""
            SELECT id, from_stage, to_stage, notes, transitioned_at
            FROM stage_transitions
            WHERE lead_id = ?
            """, (lead_id,))
            transitions = cursor.fetchall()
            for st in transitions:
                events.append({
                    "id": f"trans_{st['id']}",
                    "timestamp": st["transitioned_at"],
                    "event_type": "STAGE_TRANSITION",
                    "title": f"Stage Shift: {st['from_stage'] or 'NEW'} ➔ {st['to_stage']}",
                    "description": st["notes"] or f"Pipeline status updated to {st['to_stage']}.",
                    "actor": "SALES_REP",
                    "icon": cls.EVENT_ICONS["STAGE_TRANSITION"],
                    "badge_class": cls.EVENT_BADGES["STAGE_TRANSITION"],
                    "metadata": {
                        "from_stage": st["from_stage"],
                        "to_stage": st["to_stage"]
                    }
                })

            # 6. Check lead notes
            cursor.execute("""
            SELECT id, author, note_text, created_at
            FROM lead_notes
            WHERE lead_id = ?
            """, (lead_id,))
            notes = cursor.fetchall()
            for n in notes:
                events.append({
                    "id": f"note_{n['id']}",
                    "timestamp": n["created_at"],
                    "event_type": "NOTE_ADDED",
                    "title": f"Note added by {n['author']}",
                    "description": n["note_text"],
                    "actor": n["author"] or "SALES_REP",
                    "icon": cls.EVENT_ICONS["NOTE_ADDED"],
                    "badge_class": cls.EVENT_BADGES["NOTE_ADDED"],
                    "metadata": {}
                })

            # 7. Check if FIRST_DISCOVERED event exists, if not synthesize from lead.first_seen
            cursor.execute("SELECT first_seen, name, category, website FROM leads WHERE id = ?", (lead_id,))
            lead_row = cursor.fetchone()
            if lead_row and lead_row["first_seen"]:
                has_first_seen = any(e["event_type"] == "FIRST_DISCOVERED" for e in events)
                if not has_first_seen:
                    events.append({
                        "id": f"disc_{lead_id}",
                        "timestamp": lead_row["first_seen"],
                        "event_type": "FIRST_DISCOVERED",
                        "title": f"Discovered on Google Maps ({lead_row['category'] or 'Dental Practice'})",
                        "description": f"Added to system repository. Target domain: {lead_row['website'] or 'No website'}",
                        "actor": "SYSTEM",
                        "icon": cls.EVENT_ICONS["FIRST_DISCOVERED"],
                        "badge_class": cls.EVENT_BADGES["FIRST_DISCOVERED"],
                        "metadata": {}
                    })

        # Sort all events chronologically newest first
        events.sort(key=lambda e: e["timestamp"] or "", reverse=True)
        return events
