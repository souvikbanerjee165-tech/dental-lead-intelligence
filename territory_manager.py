"""
Territory Expansion & Management Engine.
Maintains curated directory of high-yield US dental markets, tracks scraping lifecycle,
and provides autonomous next-market selection for unattended 24/7 prospecting.
"""

from typing import List, Dict, Optional, Any
from datetime import datetime
from pydantic import BaseModel

TOP_US_DENTAL_MARKETS = [
    # Tier 1: High-Density Affluent Metros & Suburbs
    {"city": "Scottsdale", "state": "AZ", "metro": "Phoenix", "population": 258000, "affluence_tier": "VERY_HIGH", "avg_clinics": 210},
    {"city": "Austin", "state": "TX", "metro": "Austin", "population": 978000, "affluence_tier": "HIGH", "avg_clinics": 450},
    {"city": "Plano", "state": "TX", "metro": "Dallas", "population": 288000, "affluence_tier": "VERY_HIGH", "avg_clinics": 230},
    {"city": "Boca Raton", "state": "FL", "metro": "Miami", "population": 99000, "affluence_tier": "VERY_HIGH", "avg_clinics": 180},
    {"city": "Naples", "state": "FL", "metro": "Naples", "population": 22000, "affluence_tier": "ULTRA_HIGH", "avg_clinics": 120},
    {"city": "Denver", "state": "CO", "metro": "Denver", "population": 715000, "affluence_tier": "HIGH", "avg_clinics": 390},
    {"city": "Bellevue", "state": "WA", "metro": "Seattle", "population": 151000, "affluence_tier": "VERY_HIGH", "avg_clinics": 170},
    {"city": "Charlotte", "state": "NC", "metro": "Charlotte", "population": 897000, "affluence_tier": "HIGH", "avg_clinics": 340},
    {"city": "Franklin", "state": "TN", "metro": "Nashville", "population": 85000, "affluence_tier": "VERY_HIGH", "avg_clinics": 130},
    {"city": "Alpharetta", "state": "GA", "metro": "Atlanta", "population": 67000, "affluence_tier": "VERY_HIGH", "avg_clinics": 140},
    {"city": "Overland Park", "state": "KS", "metro": "Kansas City", "population": 197000, "affluence_tier": "HIGH", "avg_clinics": 160},
    {"city": "Carmel", "state": "IN", "metro": "Indianapolis", "population": 101000, "affluence_tier": "VERY_HIGH", "avg_clinics": 125},
    {"city": "Irvine", "state": "CA", "metro": "Orange County", "population": 311000, "affluence_tier": "VERY_HIGH", "avg_clinics": 290},
    {"city": "Newport Beach", "state": "CA", "metro": "Orange County", "population": 85000, "affluence_tier": "ULTRA_HIGH", "avg_clinics": 160},
    {"city": "Frisco", "state": "TX", "metro": "Dallas", "population": 210000, "affluence_tier": "VERY_HIGH", "avg_clinics": 190},
    {"city": "The Woodlands", "state": "TX", "metro": "Houston", "population": 118000, "affluence_tier": "VERY_HIGH", "avg_clinics": 145},
    {"city": "Gilbert", "state": "AZ", "metro": "Phoenix", "population": 273000, "affluence_tier": "HIGH", "avg_clinics": 180},
    {"city": "Tampa", "state": "FL", "metro": "Tampa Bay", "population": 398000, "affluence_tier": "MODERATE_HIGH", "avg_clinics": 310},
    {"city": "Orlando", "state": "FL", "metro": "Orlando", "population": 307000, "affluence_tier": "MODERATE_HIGH", "avg_clinics": 280},
    {"city": "Raleigh", "state": "NC", "metro": "Research Triangle", "population": 467000, "affluence_tier": "HIGH", "avg_clinics": 260},
    {"city": "Salt Lake City", "state": "UT", "metro": "Salt Lake", "population": 200000, "affluence_tier": "HIGH", "avg_clinics": 210},
    {"city": "Boise", "state": "ID", "metro": "Boise", "population": 235000, "affluence_tier": "MODERATE_HIGH", "avg_clinics": 190},
    {"city": "San Diego", "state": "CA", "metro": "San Diego", "population": 1386000, "affluence_tier": "HIGH", "avg_clinics": 580},
    {"city": "Dallas", "state": "TX", "metro": "Dallas", "population": 1304000, "affluence_tier": "HIGH", "avg_clinics": 520},
    {"city": "Houston", "state": "TX", "metro": "Houston", "population": 2304000, "affluence_tier": "MODERATE_HIGH", "avg_clinics": 890},
    {"city": "Phoenix", "state": "AZ", "metro": "Phoenix", "population": 1608000, "affluence_tier": "MODERATE_HIGH", "avg_clinics": 640},
    {"city": "Nashville", "state": "TN", "metro": "Nashville", "population": 689000, "affluence_tier": "HIGH", "avg_clinics": 310},
    {"city": "Atlanta", "state": "GA", "metro": "Atlanta", "population": 498000, "affluence_tier": "HIGH", "avg_clinics": 380},
    {"city": "Fort Worth", "state": "TX", "metro": "DFW", "population": 935000, "affluence_tier": "MODERATE", "avg_clinics": 310},
    {"city": "San Antonio", "state": "TX", "metro": "San Antonio", "population": 1434000, "affluence_tier": "MODERATE", "avg_clinics": 460}
]

class Territory(BaseModel):
    id: str
    city: str
    state: str
    metro: str
    population: int
    affluence_tier: str
    avg_clinics: int
    status: str = "PENDING"  # PENDING, IN_PROGRESS, COMPLETED, SCHEDULED
    last_scraped_at: Optional[str] = None
    leads_count: int = 0
    qualified_count: int = 0

class TerritoryManager:
    """Manages multi-market expansion queue and tracks autonomous scraping state."""

    @classmethod
    def get_market_catalog(cls) -> List[Dict[str, Any]]:
        return TOP_US_DENTAL_MARKETS

    @classmethod
    def initialize_territories(cls, db_manager) -> None:
        """Seed territory tracking table if empty."""
        existing = db_manager.get_all_territories()
        if existing:
            return

        for m in TOP_US_DENTAL_MARKETS:
            t_id = f"{m['city'].lower().replace(' ', '_')}_{m['state'].lower()}"
            db_manager.insert_territory(
                territory_id=t_id,
                city=m["city"],
                state=m["state"],
                metro=m["metro"],
                population=m["population"],
                affluence_tier=m["affluence_tier"],
                avg_clinics=m["avg_clinics"]
            )

    @classmethod
    def get_next_target_territory(cls, db_manager) -> Optional[Dict[str, Any]]:
        """
        Picks the optimal next territory:
        1. PENDING territory with highest affluence tier
        2. Or territory with oldest last_scraped_at
        """
        cls.initialize_territories(db_manager)
        all_t = db_manager.get_all_territories()

        # Check pending first
        pending = [t for t in all_t if t.get("status") == "PENDING"]
        if pending:
            tier_weights = {"ULTRA_HIGH": 4, "VERY_HIGH": 3, "HIGH": 2, "MODERATE_HIGH": 1, "MODERATE": 0}
            pending.sort(key=lambda x: tier_weights.get(x.get("affluence_tier"), 0), reverse=True)
            return pending[0]

        # Round-robin: oldest scraped territory
        all_t.sort(key=lambda x: x.get("last_scraped_at") or "1970-01-01T00:00:00")
        return all_t[0] if all_t else None
