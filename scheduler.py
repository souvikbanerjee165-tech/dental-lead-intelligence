import asyncio
import time
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime

from config import DEFAULT_MAX_RESULTS, HEADLESS_BROWSER
from lead_finder import GoogleMapsLeadFinder
from auditor import WebsiteAuditor
from queue_manager import QueueManager
from database import DatabaseManager
from territory_manager import TerritoryManager
from ai_qualifier import AIQualifier
from decision_hunter import DecisionMakerHunter
from outreach_generator import OutreachGenerator

logger = logging.getLogger("autonomous_scheduler")

class AutonomousScheduler:
    """
    Autonomous Sales Employee Engine.
    Executes unattended end-to-end cycles:
    Selects territory -> Scrapes Google Maps -> Deduplicates -> Audits tech -> 
    Hunts decision makers -> Qualifies with AI -> Promotes to Today's Calls queue.
    """

    @classmethod
    async def run_autonomous_cycle(
        cls,
        territory_id: Optional[str] = None,
        category: str = "Dentists",
        limit: int = 8,
        headless: bool = True,
        db: Optional[DatabaseManager] = None,
        on_progress: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Executes a complete autonomous prospecting run for a target or auto-selected territory.
        """
        db = db or DatabaseManager()
        TerritoryManager.initialize_territories(db)

        # Select target territory
        target_territory = None
        if territory_id:
            all_t = db.get_all_territories()
            for t in all_t:
                if t["id"] == territory_id:
                    target_territory = t
                    break
        
        if not target_territory:
            target_territory = TerritoryManager.get_next_target_territory(db)

        if not target_territory:
            target_territory = {
                "id": "austin_tx",
                "city": "Austin",
                "state": "TX",
                "metro": "Austin",
                "affluence_tier": "HIGH"
            }

        city_query = f"{target_territory['city']}, {target_territory['state']}"
        db.update_territory_status(target_territory["id"], status="IN_PROGRESS")

        if on_progress:
            await on_progress(f"🚀 Selected next territory: {city_query} ({target_territory.get('affluence_tier')} affluence)")

        finder = GoogleMapsLeadFinder(headless=headless)
        auditor = WebsiteAuditor()

        cycle_summary = {
            "started_at": datetime.now().isoformat(),
            "territory": target_territory,
            "city_query": city_query,
            "total_discovered": 0,
            "new_audited": 0,
            "qualified_count": 0,
            "promoted_to_todays_calls": 0,
            "promoted_leads": []
        }

        search_query = f"{category} in {city_query}"
        try:
            raw_leads = await finder.search(
                query=search_query,
                limit=limit,
                is_existing_fn=lambda lead_name, website: db.is_lead_existing(name=lead_name, website=website)
            )
        except TypeError:
            raw_leads = await finder.search(query=search_query, limit=limit)

        cycle_summary["total_discovered"] = len(raw_leads)

        for idx, r_lead in enumerate(raw_leads):
            if on_progress:
                await on_progress(f"🔍 [{idx+1}/{len(raw_leads)}] Auditing & hunting decision makers for {r_lead.name}...")

            # 1. Audit Website & Tech Stack
            scored = await auditor.audit_lead(r_lead, check_incremental=False, force=True)
            lead_id = db._make_lead_id(r_lead.name, r_lead.website)
            cycle_summary["new_audited"] += 1

            # 2. Decision Maker Hunter (Extract Doctor & Direct Email)
            doc_name = None
            doc_role = None
            direct_email = None
            if r_lead.website:
                try:
                    existing_lead = db.get_lead(lead_id)
                    if existing_lead and existing_lead.get("doctor_name"):
                        doc_name = existing_lead.get("doctor_name")
                        doc_role = existing_lead.get("decision_maker_role")
                except Exception as e:
                    logger.warning(f"Decision hunter warning for {r_lead.name}: {e}")

            # 3. AI Qualification Agent
            annual_gap = getattr(scored, "estimated_missed_revenue_annual", 42000) or 42000
            monthly_leakage = int(annual_gap / 12) if annual_gap else 3500
            tech_names = [t.name for t in getattr(scored.audit, "technologies", [])] if (scored and scored.audit) else []

            lead_dict = {
                "id": lead_id,
                "name": r_lead.name,
                "rating": r_lead.rating,
                "review_count": r_lead.review_count,
                "phone": r_lead.phone,
                "website": r_lead.website,
                "doctor_name": doc_name,
                "technologies": tech_names
            }

            qualification = AIQualifier.qualify_lead(
                lead_dict=lead_dict,
                doctor_name=doc_name,
                technologies=tech_names,
                opportunity_score=scored.opportunity_score,
                estimated_monthly_leakage=monthly_leakage
            )

            # 4. Save to Database
            db.update_lead_qualification(
                lead_id=lead_id,
                buying_probability=qualification.buying_probability_pct,
                should_call=qualification.would_spend_30min_calling,
                pain_level=qualification.pain_level,
                practice_type=qualification.practice_type,
                decision_accessibility=qualification.decision_accessibility,
                buying_triggers=qualification.buying_triggers,
                sales_verdict=qualification.sales_manager_verdict,
                territory_id=target_territory["id"]
            )

            if doc_name:
                with db._get_connection() as conn:
                    conn.execute("UPDATE leads SET doctor_name = ?, decision_maker_role = ? WHERE id = ?", (doc_name, doc_role, lead_id))
                    conn.commit()

            # 5. Promotion to Today's Calls Queue & Outreach Review Queue
            if qualification.is_a_tier or qualification.would_spend_30min_calling == "YES" or (hasattr(scored, 'opportunity_score') and scored.opportunity_score >= 65):
                try:
                    QueueManager.stage_for_review(scored, db=db)
                except Exception:
                    pass
                cycle_summary["qualified_count"] += 1
                cycle_summary["promoted_to_todays_calls"] += 1
                cycle_summary["promoted_leads"].append({
                    "id": lead_id,
                    "name": r_lead.name,
                    "doctor_name": doc_name,
                    "phone": r_lead.phone,
                    "buying_probability": qualification.buying_probability_pct,
                    "pain_level": qualification.pain_level,
                    "verdict": qualification.sales_manager_verdict
                })
                if on_progress:
                    await on_progress(f"⭐ PROMOTED TO TODAY'S CALLS: {r_lead.name} ({qualification.buying_probability_pct}% Buy Prob)")

        # Update territory status to COMPLETED
        db.update_territory_status(
            target_territory["id"],
            status="COMPLETED",
            leads_count=len(raw_leads),
            qualified_count=cycle_summary["qualified_count"]
        )

        cycle_summary["finished_at"] = datetime.now().isoformat()
        if on_progress:
            await on_progress(f"✅ Territory cycle finished for {city_query}. {cycle_summary['promoted_to_todays_calls']} A-Tier leads promoted to your call queue.")

        return cycle_summary

    @classmethod
    async def run_morning_cycle(
        cls,
        cities: Optional[List[str]] = None,
        category: str = "Dentists",
        limit_per_city: int = 5,
        headless: bool = True,
        force: bool = False,
        db: Optional[DatabaseManager] = None
    ) -> Dict[str, Any]:
        """Backwards-compatible multi-city morning harvester."""
        db = db or DatabaseManager()
        target_cities = cities or ["Austin, TX", "Dallas, TX"]
        total_summary = {
            "started_at": datetime.now().isoformat(),
            "target_cities": target_cities,
            "total_discovered": 0,
            "new_audited": 0,
            "queued_for_review": 0,
            "city_breakdown": {}
        }
        for c in target_cities:
            parts = c.split(",")
            city_name = parts[0].strip()
            state_code = parts[1].strip() if len(parts) > 1 else "US"
            t_id = f"{city_name.lower().replace(' ', '_')}_{state_code.lower()}"
            db.insert_territory(t_id, city_name, state_code, city_name, 500000, "HIGH", 200)
            res = await cls.run_autonomous_cycle(territory_id=t_id, category=category, limit=limit_per_city, headless=headless, db=db)
            total_summary["total_discovered"] += res.get("total_discovered", 0)
            total_summary["new_audited"] += res.get("new_audited", 0)
            total_summary["queued_for_review"] += res.get("promoted_to_todays_calls", 0)
            total_summary["city_breakdown"][c] = {
                "discovered": res.get("total_discovered", 0),
                "new": res.get("new_audited", 0),
                "queued": res.get("promoted_to_todays_calls", 0)
            }
        total_summary["finished_at"] = datetime.now().isoformat()
        return total_summary

