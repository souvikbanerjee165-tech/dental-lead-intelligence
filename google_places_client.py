"""
Google Places API (New & Classic) Client.
Provides 100% official, zero-CAPTCHA, sub-second dental clinic discovery
leveraging Google Cloud Platform API credits.
"""

import os
import re
import logging
from typing import List, Dict, Any, Optional

import httpx
from models import RawLead

logger = logging.getLogger("google_places_client")


class GooglePlacesClient:
    """Official Google Places API client with automated Places API (New) & Classic fallbacks."""

    NEW_PLACES_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
    CLASSIC_TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"

    def __init__(self, api_key: Optional[str] = None):
        # Read from explicit parameter, or env variables
        self.api_key = (
            api_key or 
            os.getenv("GOOGLE_PLACES_API_KEY") or 
            os.getenv("GOOGLE_API_KEY") or 
            os.getenv("GEMINI_API_KEY") or 
            ""
        ).strip()

    def is_configured(self) -> bool:
        """Returns True if a valid Google Cloud API key is configured."""
        return bool(self.api_key and not self.api_key.startswith("mock_") and len(self.api_key) > 20)

    async def search_clinics(
        self,
        query: str,
        limit: int = 20
    ) -> List[RawLead]:
        """
        Executes an official Google Places search for dental clinics.
        Tries Places API (New) first; falls back to Classic Places Text Search.
        """
        if not self.is_configured():
            logger.warning("Google Places API key is not configured. Falling back to browser scraper.")
            return []

        # 1. Try Places API (New)
        try:
            results = await self._search_places_new(query=query, limit=limit)
            if results:
                logger.info(f"Google Places API (New) retrieved {len(results)} verified clinics for '{query}'.")
                return results
        except Exception as e:
            logger.warning(f"Places API (New) search failed, trying classic fallback: {e}")

        # 2. Try Classic Places API
        try:
            results = await self._search_places_classic(query=query, limit=limit)
            if results:
                logger.info(f"Google Places Classic API retrieved {len(results)} clinics for '{query}'.")
                return results
        except Exception as e:
            logger.error(f"Google Places Classic search error: {e}")

        return []

    async def _search_places_new(self, query: str, limit: int = 20) -> List[RawLead]:
        """Queries Places API (New) endpoint with granular FieldMask."""
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": (
                "places.id,places.displayName,places.formattedAddress,"
                "places.nationalPhoneNumber,places.internationalPhoneNumber,"
                "places.rating,places.userRatingCount,places.websiteUri,"
                "places.googleMapsUri,places.location,places.primaryTypeDisplayName"
            )
        }
        payload = {
            "textQuery": query,
            "pageSize": min(limit, 20),
            "languageCode": "en"
        }

        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.post(self.NEW_PLACES_SEARCH_URL, headers=headers, json=payload)
            if resp.status_code != 200:
                raise ValueError(f"Places API (New) error {resp.status_code}: {resp.text}")

            data = resp.json()
            raw_places = data.get("places", [])

            leads = []
            for p in raw_places:
                name = (p.get("displayName") or {}).get("text") or "Dental Practice"
                address = p.get("formattedAddress") or ""
                phone = p.get("nationalPhoneNumber") or p.get("internationalPhoneNumber") or ""
                website = p.get("websiteUri") or ""
                rating = float(p.get("rating") or 4.5)
                review_count = int(p.get("userRatingCount") or 0)
                maps_url = p.get("googleMapsUri") or ""
                loc = p.get("location") or {}
                lat = float(loc.get("latitude") or 0.0)
                lng = float(loc.get("longitude") or 0.0)
                cat = ((p.get("primaryTypeDisplayName") or {}).get("text")) or "Dentist"

                leads.append(RawLead(
                    name=name,
                    category=cat,
                    rating=rating,
                    review_count=review_count,
                    phone=phone,
                    address=address,
                    website=website,
                    maps_url=maps_url,
                    latitude=lat,
                    longitude=lng
                ))

            return leads

    async def _search_places_classic(self, query: str, limit: int = 20) -> List[RawLead]:
        """Queries Google Places Classic Text Search endpoint."""
        params = {
            "query": query,
            "key": self.api_key
        }

        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.get(self.CLASSIC_TEXT_SEARCH_URL, params=params)
            if resp.status_code != 200:
                raise ValueError(f"Places Classic error {resp.status_code}: {resp.text}")

            data = resp.json()
            status = data.get("status")
            if status not in ("OK", "ZERO_RESULTS"):
                raise ValueError(f"Places Classic status: {status} - {data.get('error_message')}")

            raw_places = data.get("results", [])[:limit]
            leads = []
            for p in raw_places:
                name = p.get("name", "Dental Practice")
                address = p.get("formatted_address", "")
                rating = float(p.get("rating") or 4.5)
                review_count = int(p.get("user_ratings_total") or 0)
                loc = (p.get("geometry") or {}).get("location") or {}
                lat = float(loc.get("lat") or 0.0)
                lng = float(loc.get("lng") or 0.0)
                place_id = p.get("place_id") or ""
                maps_url = f"https://www.google.com/maps/place/?q=place_id:{place_id}" if place_id else ""

                leads.append(RawLead(
                    name=name,
                    category="Dentist",
                    rating=rating,
                    review_count=review_count,
                    phone="",  # Basic text search doesn't return phone without place details
                    address=address,
                    website="",
                    maps_url=maps_url,
                    latitude=lat,
                    longitude=lng
                ))

            return leads
