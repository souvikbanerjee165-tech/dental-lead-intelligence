"""
Geolocation Travel Route Optimizer (Roadmap #3).
- Clusters high-probability dental practices for localized field sales blitzes.
- Sequences stops to minimize driving distance and generates scheduled arrival windows.
- Builds 1-click multi-waypoint Google Maps Navigation directions.
"""

import math
import urllib.parse
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta

from database import DatabaseManager

logger = logging.getLogger("route_optimizer")


class TravelRouteOptimizer:
    """Calculates efficient multi-stop field sales itineraries with Google Maps links."""

    @classmethod
    def _haversine_distance(cls, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculates distance between two coordinate pairs in kilometers."""
        R = 6371.0 # Earth radius in km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    @classmethod
    def plan_route(
        cls,
        db: DatabaseManager,
        territory_id: Optional[str] = None,
        lead_ids: Optional[List[str]] = None,
        max_stops: int = 5,
        start_time_str: str = "09:00",
        origin_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """Sequences target clinics into an optimized driving itinerary with scheduled arrival windows."""
        candidates = []

        # 1. Fetch Candidate Leads
        if lead_ids:
            for lid in lead_ids:
                l = db.get_lead(lid)
                if l and l.get("address"):
                    candidates.append(l)
        else:
            with db._get_connection() as conn:
                cursor = conn.cursor()
                if territory_id:
                    cursor.execute("""
                    SELECT * FROM leads 
                    WHERE territory_id = ? 
                      AND address IS NOT NULL AND address != ''
                      AND stage NOT IN ('WON', 'LOST')
                    ORDER BY COALESCE(win_probability_pct, buying_probability, 75) DESC
                    LIMIT ?
                    """, (territory_id, max_stops * 2))
                else:
                    cursor.execute("""
                    SELECT * FROM leads 
                    WHERE address IS NOT NULL AND address != ''
                      AND stage NOT IN ('WON', 'LOST')
                    ORDER BY COALESCE(win_probability_pct, buying_probability, 75) DESC
                    LIMIT ?
                    """, (max_stops * 2,))
                candidates = [dict(r) for r in cursor.fetchall()]

        if not candidates:
            return {
                "status": "empty",
                "message": "No practices with valid addresses found for route planning.",
                "stops": [],
                "google_maps_url": None
            }

        # 2. Sequence Stops via Nearest-Neighbor Path
        stops_pool = candidates[:max_stops]
        ordered_stops = []

        # Check if coordinates exist on all candidates
        has_coords = all(s.get("latitude") is not None and s.get("longitude") is not None for s in stops_pool)

        if has_coords and len(stops_pool) > 1:
            current = stops_pool[0]
            ordered_stops.append(current)
            remaining = stops_pool[1:]

            while remaining:
                curr_lat = current["latitude"]
                curr_lng = current["longitude"]
                nearest = min(remaining, key=lambda x: cls._haversine_distance(curr_lat, curr_lng, x["latitude"], x["longitude"]))
                ordered_stops.append(nearest)
                remaining.remove(nearest)
                current = nearest
        else:
            # Sort by postal code or address proximity
            stops_pool.sort(key=lambda s: s.get("address") or "")
            ordered_stops = stops_pool

        # 3. Calculate Scheduled Arrival Windows
        try:
            cur_time = datetime.strptime(start_time_str, "%H:%M")
        except Exception:
            cur_time = datetime.strptime("09:00", "%H:%M")

        itinerary = []
        for idx, clinic in enumerate(ordered_stops):
            if idx > 0:
                # Add 20 minutes travel time between stops
                cur_time += timedelta(minutes=20)

            arrival = cur_time.strftime("%I:%M %p")
            departure = (cur_time + timedelta(minutes=40)).strftime("%I:%M %p")

            # Advance current time to departure
            cur_time += timedelta(minutes=40)

            doc = clinic.get("doctor_name") or "Principal Dentist"
            leakage = clinic.get("missed_rev_max") or 4500
            rating = clinic.get("rating") or 4.8

            opening_hook = f"Hi, I'm stopping by for {doc}. We conducted a patient intake audit for {clinic['name']} - you're at {rating} stars but losing an estimated ${leakage:,}/mo in after-hours patient inquiries."

            itinerary.append({
                "stop_number": idx + 1,
                "lead_id": clinic["id"],
                "clinic_name": clinic["name"],
                "doctor_name": doc,
                "address": clinic["address"],
                "phone": clinic.get("phone", ""),
                "arrival_window": f"{arrival} - {departure}",
                "win_probability_pct": clinic.get("win_probability_pct") or 75,
                "missed_rev_max": leakage,
                "opening_hook": opening_hook
            })

        # 4. Generate Multi-Waypoint Google Maps URL
        # Format: https://www.google.com/maps/dir/?api=1&origin=...&destination=...&waypoints=...
        addresses = [s["address"] for s in itinerary]
        start_addr = origin_address or addresses[0]
        dest_addr = addresses[-1]

        if len(addresses) > 2:
            waypoints = "|".join(urllib.parse.quote(a) for a in addresses[1:-1])
            maps_url = f"https://www.google.com/maps/dir/?api=1&origin={urllib.parse.quote(start_addr)}&destination={urllib.parse.quote(dest_addr)}&waypoints={waypoints}&travelmode=driving"
        elif len(addresses) == 2:
            maps_url = f"https://www.google.com/maps/dir/?api=1&origin={urllib.parse.quote(start_addr)}&destination={urllib.parse.quote(dest_addr)}&travelmode=driving"
        else:
            maps_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(start_addr)}"

        total_duration_hours = round((len(itinerary) * 60) / 60, 1)

        return {
            "status": "success",
            "total_stops": len(itinerary),
            "estimated_duration_hours": total_duration_hours,
            "google_maps_url": maps_url,
            "itinerary": itinerary
        }
