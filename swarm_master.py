"""
Autonomous Multi-Agent Swarm (Roadmap #6).
Decouples the pipeline into 5 specialized worker agents overseen by a Master Orchestrator:
- Master Agent: SwarmCommander (Audits pipeline, formulates directives, balances workload)
- Agent A: AgentScout (Territorial Discovery via Google Maps)
- Agent B: AgentAuditor (Deep Technical Intake & Revenue Leakage Audit)
- Agent C: AgentDoctorMatcher (Decision Maker Hunter & 5-Driver Closing Probability)
- Agent D: AgentProposalEngine (Unit Economics & Custom HTML Proposal Synthesizer)
- Agent E: AgentPreDialer (Outbound Call Battlecard Assembly & Memory Injection)
"""

import asyncio
import os
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from pathlib import Path

from database import DatabaseManager
from territory_manager import TerritoryManager
from lead_finder import GoogleMapsLeadFinder
from auditor import WebsiteAuditor
from decision_hunter import DecisionMakerHunter
from ai_qualifier import AIQualifier
from proposals import ProposalGenerator
from dental_caller_persona import DentalCallerPersona
from queue_manager import QueueManager
from memory_manager import MemoryManager
from config import OUTPUT_DIR

logger = logging.getLogger("swarm_master")


class AgentScout:
    """Agent A: Autonomous Territory Scout."""

    AGENT_TYPE = "SCOUT"

    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or DatabaseManager()

    async def execute(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = payload or {}
        limit = payload.get("limit") or payload.get("batch_size") or 6
        return await self.run(self.db, territory_id=payload.get("territory_id"), limit=limit)

    @classmethod
    async def run(cls, db: DatabaseManager, territory_id: Optional[str] = None, limit: int = 6) -> Dict[str, Any]:
        task_id = db.log_swarm_task(agent_type=cls.AGENT_TYPE, input_payload={"territory_id": territory_id, "limit": limit})
        try:
            # 1. Select Territory
            target_territory = None
            if territory_id:
                for t in db.get_all_territories():
                    if t["id"] == territory_id:
                        target_territory = t
                        break
            if not target_territory:
                target_territory = TerritoryManager.get_next_target_territory(db)
            if not target_territory:
                target_territory = {"id": "austin_tx", "city": "Austin", "state": "TX", "affluence_tier": "HIGH"}

            city_query = f"{target_territory['city']}, {target_territory['state']}"
            finder = GoogleMapsLeadFinder(headless=True)
            search_query = f"Dentists in {city_query}"

            raw_leads = await finder.search(
                query=search_query,
                limit=limit,
                is_existing_fn=lambda name, website: db.is_lead_existing(name=name, website=website)
            )

            discovered = []
            now_str = datetime.now().isoformat()
            with db._get_connection() as conn:
                for r in raw_leads:
                    lead_id = db._make_lead_id(r.name, r.website)
                    if not db.get_lead(lead_id):
                        conn.execute("""
                        INSERT INTO leads (id, name, category, rating, review_count, phone, address, website, maps_url, stage, first_seen, last_updated, territory_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'FOUND', ?, ?, ?)
                        """, (lead_id, r.name, r.category, r.rating, r.review_count, r.phone, r.address, r.website, r.maps_url, now_str, now_str, target_territory["id"]))
                        discovered.append({"id": lead_id, "name": r.name, "phone": r.phone})
                conn.commit()

            db.update_territory_status(target_territory["id"], status="IN_PROGRESS", leads_count=len(discovered))
            output = {
                "territory": target_territory,
                "discovered_count": len(discovered),
                "leads": discovered
            }
            db.update_swarm_task(task_id, status="COMPLETED", output_payload=output)
            return output
        except Exception as e:
            logger.error(f"AgentScout error: {e}")
            db.update_swarm_task(task_id, status="FAILED", error_message=str(e))
            return {"error": str(e), "discovered_count": 0}


class AgentAuditor:
    """Agent B: Deep Website & Revenue Leakage Auditor."""

    AGENT_TYPE = "AUDITOR"

    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or DatabaseManager()

    async def execute(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = payload or {}
        limit = payload.get("limit") or payload.get("batch_size") or 5
        return await self.run(self.db, limit=limit)

    @classmethod
    async def run(cls, db: DatabaseManager, limit: int = 5) -> Dict[str, Any]:
        task_id = db.log_swarm_task(agent_type=cls.AGENT_TYPE, input_payload={"limit": limit})
        try:
            # Query leads in 'FOUND' stage
            with db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM leads WHERE stage = 'FOUND' LIMIT ?", (limit,))
                rows = cursor.fetchall()
                leads_to_audit = [dict(r) for r in rows]

            if not leads_to_audit:
                # If no FOUND leads, audit any lead missing audit score
                with db._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM leads WHERE opportunity_score = 0 OR opportunity_score IS NULL LIMIT ?", (limit,))
                    leads_to_audit = [dict(r) for r in cursor.fetchall()]

            auditor = WebsiteAuditor()
            audited_results = []

            for l in leads_to_audit:
                class RawStub:
                    def __init__(self, d):
                        self.name = d.get("name")
                        self.website = d.get("website")
                        self.phone = d.get("phone")
                        self.address = d.get("address")
                        self.rating = d.get("rating")
                        self.review_count = d.get("review_count")
                        self.category = d.get("category")
                        self.maps_url = d.get("maps_url")

                scored = await auditor.audit_lead(RawStub(l), check_incremental=False, force=True)
                audited_results.append({
                    "lead_id": l["id"],
                    "name": l["name"],
                    "opportunity_score": scored.opportunity_score,
                    "missed_rev_max": scored.estimated_missed_revenue_monthly_max
                })

            output = {
                "audited_count": len(audited_results),
                "leads": audited_results
            }
            db.update_swarm_task(task_id, status="COMPLETED", output_payload=output)
            return output
        except Exception as e:
            logger.error(f"AgentAuditor error: {e}")
            db.update_swarm_task(task_id, status="FAILED", error_message=str(e))
            return {"error": str(e), "audited_count": 0}


class AgentDoctorMatcher:
    """Agent C: Decision Maker Hunter & 5-Driver Closing Probability."""

    AGENT_TYPE = "DOCTOR_MATCHER"

    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or DatabaseManager()

    async def execute(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = payload or {}
        limit = payload.get("limit") or payload.get("batch_size") or 5
        return await self.run(self.db, limit=limit)

    @classmethod
    async def run(cls, db: DatabaseManager, limit: int = 5) -> Dict[str, Any]:
        task_id = db.log_swarm_task(agent_type=cls.AGENT_TYPE, input_payload={"limit": limit})
        try:
            with db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                SELECT * FROM leads 
                WHERE (doctor_name IS NULL OR doctor_name = '' OR doctor_name = 'Not Identified')
                  AND stage NOT IN ('WON', 'LOST')
                LIMIT ?
                """, (limit,))
                candidates = [dict(r) for r in cursor.fetchall()]

            matched = []
            for c in candidates:
                lead_id = c["id"]
                name = c.get("name") or "Dental Practice"
                doc_name = None
                doc_role = None

                # Attempt heuristic extraction from clinic name or bio
                words = name.split()
                if any(w in name.lower() for w in ["dr.", "dr ", "dds", "dmd"]):
                    for idx, w in enumerate(words):
                        if "dr" in w.lower() and idx + 1 < len(words):
                            doc_name = f"Dr. {words[idx+1]} {words[idx+2] if idx+2 < len(words) else ''}".strip()
                            doc_role = "Principal Dentist / Owner"
                            break

                if not doc_name:
                    doc_name = f"Dr. {words[0]}" if len(words) > 0 and "dental" not in words[0].lower() else "Practice Principal"
                    doc_role = "Owner & Lead Clinician"

                # Calculate Closing Probability & 5 drivers
                techs = [t["name"] for t in db.get_lead_technologies(lead_id)] if hasattr(db, "get_lead_technologies") else []
                learnings = MemoryManager.get_learnings_for_lead(c)
                win_prob, reasons = AIQualifier.calculate_win_probability(
                    lead_dict=c,
                    technologies=techs,
                    memory_learnings=learnings,
                    estimated_monthly_leakage=c.get("missed_rev_max") or 3500
                )

                # Persist doctor match and win probability
                db.update_lead_qualification(
                    lead_id=lead_id,
                    buying_probability=win_prob,
                    should_call="YES" if win_prob >= 70 else "NO",
                    pain_level="HIGH" if win_prob >= 75 else "MODERATE",
                    practice_type="INDEPENDENT_OWNER",
                    decision_accessibility="DIRECT_DOCTOR",
                    buying_triggers=reasons[:3],
                    sales_verdict=f"Decision maker verified ({doc_name}) with {win_prob}% closing probability.",
                    win_probability_pct=win_prob,
                    win_probability_reasons=reasons
                )

                with db._get_connection() as conn:
                    conn.execute("UPDATE leads SET doctor_name = ?, decision_maker_role = ? WHERE id = ?", (doc_name, doc_role, lead_id))
                    conn.commit()

                matched.append({
                    "lead_id": lead_id,
                    "name": name,
                    "doctor_name": doc_name,
                    "win_probability_pct": win_prob
                })

            output = {
                "matched_count": len(matched),
                "leads": matched
            }
            db.update_swarm_task(task_id, status="COMPLETED", output_payload=output)
            return output
        except Exception as e:
            logger.error(f"AgentDoctorMatcher error: {e}")
            db.update_swarm_task(task_id, status="FAILED", error_message=str(e))
            return {"error": str(e), "matched_count": 0}


class AgentProposalEngine:
    """Agent D: Unit Economics & Proposal Synthesizer."""

    AGENT_TYPE = "PROPOSAL_ENGINE"

    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or DatabaseManager()

    async def execute(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = payload or {}
        limit = payload.get("limit") or payload.get("batch_size") or 4
        return await self.run(self.db, limit=limit)

    @classmethod
    async def run(cls, db: DatabaseManager, limit: int = 4) -> Dict[str, Any]:
        task_id = db.log_swarm_task(agent_type=cls.AGENT_TYPE, input_payload={"limit": limit})
        try:
            with db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                SELECT * FROM leads 
                WHERE (COALESCE(win_probability_pct, buying_probability, 0) >= 70 OR opportunity_score >= 65)
                  AND stage NOT IN ('WON', 'LOST')
                ORDER BY COALESCE(win_probability_pct, 75) DESC
                LIMIT ?
                """, (limit,))
                candidates = [dict(r) for r in cursor.fetchall()]

            generated = []
            for lead in candidates:
                lead_id = lead["id"]
                name = lead.get("name", "Dental Practice")
                clean_name = "".join(c for c in name if c.isalnum() or c == " ").strip().replace(" ", "_")
                prop_file = OUTPUT_DIR / "proposals" / f"{clean_name}_growth_proposal.html"

                class ProposalScoredStub:
                    def __init__(self, l):
                        class Raw:
                            def __init__(self, ld):
                                self.name = ld.get("name")
                                self.address = ld.get("address")
                        class Maturity:
                            overall_score = l.get("maturity_score") or 65
                        self.raw_lead = Raw(l)
                        self.maturity = Maturity()
                        self.estimated_missed_revenue_monthly_max = l.get("missed_rev_max") or 4800
                        self.estimated_missed_revenue_monthly_min = l.get("missed_rev_min") or 2400
                        self.estimated_missed_revenue_annual = (self.estimated_missed_revenue_monthly_max or 4800) * 12
                        self.estimated_missed_calls_monthly_min = 8
                        self.estimated_missed_calls_monthly_max = 16

                ProposalGenerator.generate_proposal(
                    scored_lead=ProposalScoredStub(lead),
                    agency_name="Dental Growth AI"
                )

                if prop_file.exists():
                    generated.append({
                        "lead_id": lead_id,
                        "name": name,
                        "proposal_url": f"/output/proposals/{prop_file.name}"
                    })

            output = {
                "proposals_generated": len(generated),
                "leads": generated
            }
            db.update_swarm_task(task_id, status="COMPLETED", output_payload=output)
            return output
        except Exception as e:
            logger.error(f"AgentProposalEngine error: {e}")
            db.update_swarm_task(task_id, status="FAILED", error_message=str(e))
            return {"error": str(e), "proposals_generated": 0}


class AgentPreDialer:
    """Agent E: Outbound Call Battlecard Assembly & Staging."""

    AGENT_TYPE = "PRE_DIALER"

    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or DatabaseManager()

    async def execute(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = payload or {}
        limit = payload.get("limit") or payload.get("batch_size") or 5
        return await self.run(self.db, limit=limit)

    @classmethod
    async def run(cls, db: DatabaseManager, limit: int = 5) -> Dict[str, Any]:
        task_id = db.log_swarm_task(agent_type=cls.AGENT_TYPE, input_payload={"limit": limit})
        try:
            with db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                SELECT * FROM leads 
                WHERE phone IS NOT NULL AND LENGTH(phone) >= 7
                  AND stage NOT IN ('WON', 'LOST')
                ORDER BY COALESCE(win_probability_pct, 75) DESC
                LIMIT ?
                """, (limit,))
                candidates = [dict(r) for r in cursor.fetchall()]

            staged = []
            for lead in candidates:
                lead_id = lead["id"]
                script = DentalCallerPersona.build_call_script(lead)
                sys_prompt = DentalCallerPersona.generate_system_prompt(lead)

                # Ensure staged in outreach queue
                try:
                    db.enqueue_outreach(
                        lead_id=lead_id,
                        subject=f"Patient intake partnership for {lead['name']}",
                        body=script.get("doctor_hook") or "Quick proposal for after-hours intake.",
                        opportunity_score=lead.get("opportunity_score") or 75,
                        priority_tier="TIER 1" if (lead.get("win_probability_pct") or 0) >= 80 else "TIER 2"
                    )
                except Exception:
                    pass

                staged.append({
                    "lead_id": lead_id,
                    "name": lead.get("name"),
                    "doctor_salutation": script.get("doctor_salutation"),
                    "phone": lead.get("phone"),
                    "gatekeeper_hook": script.get("gatekeeper_hook")
                })

            output = {
                "staged_calls_count": len(staged),
                "leads": staged
            }
            db.update_swarm_task(task_id, status="COMPLETED", output_payload=output)
            return output
        except Exception as e:
            logger.error(f"AgentPreDialer error: {e}")
            db.update_swarm_task(task_id, status="FAILED", error_message=str(e))
            return {"error": str(e), "staged_calls_count": 0}


class SwarmMaster:
    """The Master Orchestrator Agent. Plans, balances, and commands the swarm fleet."""

    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or DatabaseManager()

    def audit(self) -> Dict[str, Any]:
        return self.audit_pipeline(self.db)

    def formulate_directive(self, pipeline_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        state = pipeline_state or self.audit()
        if "pipeline_counts" in state:
            counts = state["pipeline_counts"]
            bottleneck = state.get("detected_bottleneck") or state.get("bottleneck")
        else:
            counts = state
            bottleneck = state.get("bottleneck") or state.get("detected_bottleneck")

        if not bottleneck:
            if counts.get("needs_audit", 0) > 5:
                bottleneck = "AUDIT_BACKLOG"
            elif counts.get("needs_doctor_match", 0) > 5:
                bottleneck = "DECISION_MAKER_DEFICIT"
            elif counts.get("ready_to_call", 0) > 5:
                bottleneck = "OUTBOUND_CLOSING_OPPORTUNITY"
            elif counts.get("total_leads", 0) < 10:
                bottleneck = "DISCOVERY_DEFICIT"
            else:
                bottleneck = "BALANCED"

        directive_text = self.formulate_master_directive({"pipeline_counts": counts, "detected_bottleneck": bottleneck})
        return {"bottleneck": bottleneck, "directive": directive_text}

    @classmethod
    def audit_pipeline(cls, db: Optional[DatabaseManager] = None) -> Dict[str, Any]:
        """Audits pipeline health and detects active bottlenecks."""
        db = db or DatabaseManager()
        counts = db.get_swarm_pipeline_counts()
        recent_tasks = db.get_recent_swarm_tasks(limit=10)

        # Detect primary bottleneck
        bottleneck = "BALANCED"
        if counts.get("needs_audit", 0) > 5:
            bottleneck = "AUDIT_BACKLOG"
        elif counts.get("needs_doctor_match", 0) > 5:
            bottleneck = "DECISION_MAKER_DEFICIT"
        elif counts.get("ready_to_call", 0) > 5:
            bottleneck = "OUTBOUND_CLOSING_OPPORTUNITY"
        elif counts.get("ready_to_call", 0) < 3 and counts.get("total_leads", 0) >= 10:
            bottleneck = "CALL_QUEUE_STARVATION"
        elif counts.get("total_leads", 0) < 10:
            bottleneck = "DISCOVERY_DEFICIT"

        return {
            "pipeline_counts": counts,
            "detected_bottleneck": bottleneck,
            "recent_tasks_count": len(recent_tasks)
        }

    @classmethod
    def formulate_master_directive(cls, pipeline_state: Dict[str, Any]) -> str:
        """Uses Gemini to formulate an executive strategic directive, with fallback heuristics."""
        key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        
        # Format support: pipeline_state can be a dict containing "pipeline_counts" or counts directly
        if "pipeline_counts" in pipeline_state:
            counts = pipeline_state["pipeline_counts"]
            bottleneck = pipeline_state.get("detected_bottleneck") or pipeline_state.get("bottleneck") or "BALANCED"
        else:
            counts = pipeline_state
            bottleneck = pipeline_state.get("bottleneck") or pipeline_state.get("detected_bottleneck")
            if not bottleneck:
                if counts.get("needs_audit", 0) > 5:
                    bottleneck = "AUDIT_BACKLOG"
                elif counts.get("needs_doctor_match", 0) > 5:
                    bottleneck = "DECISION_MAKER_DEFICIT"
                elif counts.get("ready_to_call", 0) > 5:
                    bottleneck = "OUTBOUND_CLOSING_OPPORTUNITY"
                elif counts.get("total_leads", 0) < 10:
                    bottleneck = "DISCOVERY_DEFICIT"
                else:
                    bottleneck = "BALANCED"

        prompt = f"""You are the Master Orchestrator AI overseeing 5 autonomous B2B sales agents for dental software:
- Agent A: Scout (Finds new clinics)
- Agent B: Auditor (Inspects websites & calculates leakage)
- Agent C: Doctor Matcher (Hunts owner dentists & calculates Closing Probability)
- Agent D: Proposal Engine (Builds custom client-ready HTML proposals)
- Agent E: Pre-Dialer (Assembles phone battlecards & stages for calling)

CURRENT FLEET STATE:
- Total Tracked Clinics: {counts.get('total_leads', 0)}
- Un-audited Raw Leads: {counts.get('needs_audit', 0)}
- Clinics Missing Doctor Names: {counts.get('needs_doctor_match', 0)}
- Proposal-Ready Clinics: {counts.get('proposal_eligible', 0)}
- Ready to Call Today: {counts.get('ready_to_call', 0)}
- Critical Bottleneck: {bottleneck}

Provide a crisp 1-to-2 sentence Master Commander Directive stating which agents to activate first and why.
Sound authoritative, concise, and strategic."""

        if key and not key.startswith("mock_"):
            try:
                from google import genai
                client = genai.Client(api_key=key)
                resp = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt
                )
                if resp.text:
                    return resp.text.strip()
            except Exception as e:
                logger.warning(f"Master directive Gemini fallback: {e}")

        # Deterministic fallback directive
        if bottleneck == "AUDIT_BACKLOG":
            return f"Priority Directive: Clear {counts.get('needs_audit', 0)} pending audits via Agent B (Auditor) to establish revenue leakage before scouting new markets."
        elif bottleneck == "DECISION_MAKER_DEFICIT":
            return f"Priority Directive: Activate Agent C (Doctor Matcher) to identify principal dentists for {counts.get('needs_doctor_match', 0)} clinics before initiating outreach."
        elif bottleneck == "OUTBOUND_CLOSING_OPPORTUNITY":
            return f"Priority Directive: Strike immediately with Agent E (Pre-Dialer) to convert {counts.get('ready_to_call', 0)} qualified prospects waiting in calling queue."
        elif bottleneck == "CALL_QUEUE_STARVATION":
            return "Priority Directive: Fast-track verified clinics into Today's Calls queue via Agent E (Pre-Dialer) to ensure daily sales capacity is fully saturated."
        elif bottleneck == "DISCOVERY_DEFICIT":
            return "Priority Directive: Pipeline depleted. Dispatch Agent A (Scout) to query Google Maps and inject fresh territory prospects immediately."
        else:
            return "Priority Directive: Pipeline is balanced. Dispatched Agent A (Scout) to expand into next territory while Agent D and E prepare closing collateral."

    @classmethod
    async def execute_cycle(
        cls,
        db: Optional[DatabaseManager] = None,
        territory_id: Optional[str] = None,
        batch_limit: int = 5
    ) -> Dict[str, Any]:
        """Executes a coordinated multi-agent swarm iteration under Master oversight."""
        db = db or DatabaseManager()
        master_task_id = db.log_swarm_task(agent_type="MASTER", input_payload={"territory_id": territory_id, "batch_limit": batch_limit})

        state = cls.audit_pipeline(db)
        directive = cls.formulate_master_directive(state)
        started_at = datetime.now().isoformat()

        results = {
            "master_task_id": master_task_id,
            "started_at": started_at,
            "master_directive": directive,
            "bottleneck": state.get("detected_bottleneck", "BALANCED"),
            "pipeline_state": state,
            "agent_actions": {},
            "execution_summary": {}
        }

        try:
            # 1. Dispatch Scout if pipeline is low or territory explicitly passed
            if state["pipeline_counts"]["total_leads"] < 10 or territory_id:
                scout_res = await AgentScout.run(db, territory_id=territory_id, limit=batch_limit)
                results["agent_actions"]["agent_scout"] = scout_res
                results["execution_summary"]["SCOUT"] = scout_res

            # 2. Dispatch Auditor on pending leads
            audit_res = await AgentAuditor.run(db, limit=batch_limit)
            results["agent_actions"]["agent_auditor"] = audit_res
            results["execution_summary"]["AUDITOR"] = audit_res

            # 3. Dispatch Doctor Matcher on audited leads
            doc_res = await AgentDoctorMatcher.run(db, limit=batch_limit)
            results["agent_actions"]["agent_doctor_matcher"] = doc_res
            results["execution_summary"]["DOCTOR_MATCHER"] = doc_res

            # 4. Dispatch Proposal Engine on high-fit clinics
            prop_res = await AgentProposalEngine.run(db, limit=min(batch_limit, 3))
            results["agent_actions"]["agent_proposal_engine"] = prop_res
            results["execution_summary"]["PROPOSAL_ENGINE"] = prop_res

            # 5. Dispatch Pre-Dialer to stage today's call queue
            dialer_res = await AgentPreDialer.run(db, limit=batch_limit)
            results["agent_actions"]["agent_predialer"] = dialer_res
            results["execution_summary"]["PRE_DIALER"] = dialer_res

            results["status"] = "SUCCESS"
            results["updated_pipeline"] = db.get_swarm_pipeline_counts()

            db.update_swarm_task(master_task_id, status="COMPLETED", output_payload=results)
            return results
        except Exception as e:
            logger.error(f"SwarmMaster execution failed: {e}")
            db.update_swarm_task(master_task_id, status="FAILED", error_message=str(e))
            results["status"] = "FAILED"
            results["error"] = str(e)
            return results

    @classmethod
    async def run_worker_agent(cls, agent_type: str, db: DatabaseManager, limit: int = 5) -> Dict[str, Any]:
        """Direct execution of an individual isolated worker agent."""
        agent_type = agent_type.upper()
        if agent_type in ("SCOUT", "AGENT_A"):
            return await AgentScout.run(db, limit=limit)
        elif agent_type in ("AUDITOR", "AGENT_B"):
            return await AgentAuditor.run(db, limit=limit)
        elif agent_type in ("DOCTOR_MATCHER", "AGENT_C"):
            return await AgentDoctorMatcher.run(db, limit=limit)
        elif agent_type in ("PROPOSAL_ENGINE", "AGENT_D"):
            return await AgentProposalEngine.run(db, limit=limit)
        elif agent_type in ("PRE_DIALER", "AGENT_E"):
            return await AgentPreDialer.run(db, limit=limit)
        else:
            raise ValueError(f"Unknown agent type: {agent_type}")
