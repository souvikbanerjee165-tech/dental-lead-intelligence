"""
US NPI (National Provider Identifier) Registry Enrichment Engine.
Queries the official, free US Centers for Medicare & Medicaid Services (CMS) open API
to extract verified dentist credentials, primary taxonomy/specialties, NPI numbers,
and practice leadership information with zero external API fees.
"""

import json
import logging
import urllib.request
import urllib.parse
from typing import Dict, Any, List, Optional

logger = logging.getLogger("npi_registry")

NPI_API_URL = "https://npiregistry.cms.hhs.gov/api/?version=2.1"


class NPIRegistryEnricher:
    """Enriches dental clinic prospects with official US Federal NPI credentials."""

    @classmethod
    def lookup_provider(
        cls,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        organization_name: Optional[str] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        postal_code: Optional[str] = None,
        taxonomy_description: str = "Dentist"
    ) -> Dict[str, Any]:
        """
        Queries CMS NPI Registry for individual dentists or dental practice organizations.
        """
        params: Dict[str, str] = {
            "version": "2.1",
            "limit": "5"
        }

        # Build query parameters
        if first_name:
            params["first_name"] = first_name.strip()
        if last_name:
            params["last_name"] = last_name.strip()
        if organization_name and not (first_name or last_name):
            # Clean common suffixes for cleaner search
            clean_org = (
                organization_name.replace("LLC", "")
                .replace("Inc", "")
                .replace("PLLC", "")
                .replace("P.A.", "")
                .replace("DDS", "")
                .replace("DMD", "")
                .strip(" ,.-")
            )
            params["organization_name"] = clean_org[:50]
        if city:
            params["city"] = city.strip()
        if state:
            clean_state = state.strip().upper()
            if len(clean_state) == 2:
                params["state"] = clean_state
        if postal_code:
            params["postal_code"] = postal_code.strip()[:5]

        # Filter to Dental Taxonomy code prefix (1223 = Dentists)
        params["taxonomy_description"] = taxonomy_description

        encoded_url = f"https://npiregistry.cms.hhs.gov/api/?{urllib.parse.urlencode(params)}"

        try:
            req = urllib.request.Request(
                encoded_url,
                headers={"User-Agent": "DentalLeadIntelligence/2.0 (Healthcare Prospecting)"}
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            results = data.get("results", [])
            if not results:
                return {
                    "found": False,
                    "verified": False,
                    "npi_number": None,
                    "doctor_name": None,
                    "credential": None,
                    "specialty": None,
                    "summary": "No matching NPI registry records found."
                }

            # Extract the best matching record
            match = results[0]
            basic = match.get("basic", {})
            taxonomies = match.get("taxonomies", [])

            # Determine primary specialty
            primary_tax = next((t for t in taxonomies if t.get("primary")), taxonomies[0] if taxonomies else {})
            specialty_desc = primary_tax.get("desc", "General Dental Practice")

            # Format name and credential (supports both Type 1 Individual and Type 2 Organization Authorized Official)
            doc_first = basic.get("first_name", "")
            doc_last = basic.get("last_name", "")
            auth_first = basic.get("authorized_official_first_name", "")
            auth_last = basic.get("authorized_official_last_name", "")
            credential = (
                basic.get("credential")
                or basic.get("authorized_official_credential")
                or "DDS"
            )

            if doc_last:
                full_name = f"Dr. {doc_first.title()} {doc_last.title()}".strip()
                doc_first, doc_last = doc_first.title(), doc_last.title()
            elif auth_last:
                full_name = f"Dr. {auth_first.title()} {auth_last.title()}".strip()
                doc_first, doc_last = auth_first.title(), auth_last.title()
            else:
                full_name = basic.get("organization_name", "Dental Practice")

            addresses = match.get("addresses", [{}])
            loc_addr = next((a for a in addresses if a.get("address_purpose") == "LOCATION"), addresses[0] if addresses else {})

            return {
                "found": True,
                "verified": True,
                "npi_number": str(match.get("number")),
                "doctor_name": full_name,
                "first_name": doc_first,
                "last_name": doc_last,
                "credential": credential or "DDS",
                "specialty": specialty_desc,
                "license_state": primary_tax.get("state", state),
                "license_number": primary_tax.get("license"),
                "gender": basic.get("gender"),
                "enumeration_date": basic.get("enumeration_date"),
                "address": loc_addr.get("address_1"),
                "phone": loc_addr.get("telephone_number"),
                "summary": f"Verified NPI #{match.get('number')} — {full_name}, {credential} ({specialty_desc})"
            }

        except Exception as e:
            logger.warning(f"NPI Registry query error: {e}")
            return {
                "found": False,
                "verified": False,
                "error": str(e),
                "summary": "NPI lookup temporarily unavailable."
            }
