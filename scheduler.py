import asyncio
import time
from typing import List, Dict, Optional, Any
from datetime import datetime

from config import DEFAULT_MAX_RESULTS, HEADLESS_BROWSER
from lead_finder import GoogleMapsLeadFinder
from auditor import WebsiteAuditor
from queue_manager import QueueManager
from database import DatabaseManager

DEFAULT_CITIES = [
    "Austin, TX",
    "Dallas, TX",
    "Houston, TX",
    "San Antonio, TX",
    "Fort Worth, TX"
]

class AutonomousScheduler:
    """Autonomous multi-market search, incremental auditing, and outreach staging engine."""

    @classmethod
    async def run_morning_cycle(
        cls,
        cities: Optional[List[str]] = None,
        category: str = "Dentist",
        limit_per_city: int = 5,
        headless: bool = True,
        force: bool = False,
        db: Optional[DatabaseManager] = None
    ) -> Dict[str, Any]:
        target_cities = cities or DEFAULT_CITIES

        db = db or DatabaseManager()
        finder = GoogleMapsLeadFinder(headless=headless)
        auditor = WebsiteAuditor()

        cycle_summary = {
            "started_at": datetime.now().isoformat(),
            "target_cities": target_cities,
            "total_discovered": 0,
            "new_audited": 0,
            "unchanged_skipped": 0,
            "content_changed_updated": 0,
            "queued_for_review": 0,
            "city_breakdown": {}
        }

        for city in target_cities:
            query = f"{category} in {city}"
            raw_leads = await finder.search(query=query, limit=limit_per_city)
            city_stats = {
                "discovered": len(raw_leads),
                "new": 0,
                "skipped": 0,
                "updated": 0,
                "queued": 0
            }

            for r_lead in raw_leads:
                cycle_summary["total_discovered"] += 1
                lead_id = db._make_lead_id(r_lead.name, r_lead.website)
                existing = db.get_lead(lead_id)

                scored = await auditor.audit_lead(r_lead, check_incremental=True, force=force)

                if scored.was_cached:
                    cycle_summary["unchanged_skipped"] += 1
                    city_stats["skipped"] += 1
                else:
                    if existing:
                        cycle_summary["content_changed_updated"] += 1
                        city_stats["updated"] += 1
                    else:
                        cycle_summary["new_audited"] += 1
                        city_stats["new"] += 1

                    # Auto-stage high priority prospects into review queue
                    tier_str = scored.deal_priority.tier.value if scored.deal_priority else "TIER 2"
                    if scored.opportunity_score >= 65 or tier_str == "TIER 1":
                        QueueManager.stage_for_review(scored, db=db)
                        cycle_summary["queued_for_review"] += 1
                        city_stats["queued"] += 1

            cycle_summary["city_breakdown"][city] = city_stats


        cycle_summary["finished_at"] = datetime.now().isoformat()
        return cycle_summary
