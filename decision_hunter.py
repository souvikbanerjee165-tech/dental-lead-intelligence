import re
import urllib.parse
from typing import List, Dict, Optional, Any, Set, Tuple
from bs4 import BeautifulSoup

# Common non-name phrases to discard
DISCARD_NAMES = {
    "dental care", "dental team", "our team", "about us", "contact us",
    "home page", "our doctors", "schedule appointment", "first visit",
    "emergency dental", "dentist", "oral surgery", "cosmetic dentistry",
    "pediatric dentistry", "family dentistry", "board certified", "general dentist",
    "general dentistry", "smile gallery", "patient info", "dental clinic",
    "front desk", "office hours", "insurance accepted", "financial options",
    "read more", "learn more", "view profile", "meet dr", "book online"
}

DOCTOR_PREFIX_REGEX = re.compile(
    r"(?:(?:Dr\.|Doctor)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})(?:,?\s*(?:DDS|DMD|BDS|FAGD|MAGD|MSD|FICOI|MD))?)",
    re.IGNORECASE
)

DOCTOR_SUFFIX_REGEX = re.compile(
    r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2}),?\s+(DDS|DMD|BDS|FAGD|MAGD|MSD|FICOI)\b"
)

OFFICE_MGR_REGEX = re.compile(
    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\s*(?:[-–—|:]\s*|\s+is\s+(?:our\s+)?)(Office Manager|Practice Manager|Patient Coordinator|Operations Director|Clinical Coordinator)",
    re.IGNORECASE
)

OFFICE_MGR_PREFIX_REGEX = re.compile(
    r"(?:Office Manager|Practice Manager|Patient Coordinator|Operations Director)[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})",
    re.IGNORECASE
)

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")

TEAM_URL_KEYWORDS = [
    "about", "team", "doctor", "dentist", "staff", "meet", "who-we-are", "provider", "bio"
]

class DecisionMakerHunter:
    """Extracts Doctor names, Practice Managers, and direct staff emails from practice websites."""

    @classmethod
    def clean_name(cls, name: str) -> str:
        """Strip extraneous punctuation, whitespace, and normalize casing."""
        if not name:
            return ""
        name = name.strip(" ,.-–—|:\t\r\n")
        # Remove multiple spaces
        return re.sub(r"\s+", " ", name)

    @classmethod
    def is_valid_person_name(cls, name: str) -> bool:
        """Validate that a candidate string is likely an actual human name and not a page title."""
        if not name or len(name) < 4 or len(name) > 40:
            return False
        lower = name.lower()
        if any(term in lower for term in DISCARD_NAMES):
            return False
        # Must have at least 2 words
        parts = name.split()
        if len(parts) < 2 or len(parts) > 4:
            return False
        # Each part should start with uppercase
        if not all(p[0].isupper() for p in parts if p):
            return False
        return True

    @classmethod
    def extract_from_html(cls, html: str, soup: Optional[BeautifulSoup] = None) -> Dict[str, Any]:
        """Scans page text, headings, and meta tags for Doctor and Manager signatures."""
        if not soup:
            soup = BeautifulSoup(html, "html.parser")

        doctors: List[str] = []
        managers: List[str] = []
        emails: List[str] = []

        # 1. Look in headings (h1, h2, h3, h4, strong) which often feature staff bios
        for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "strong", "b", "p"]):
            text = tag.get_text(" ", strip=True)
            if not text or len(text) > 120:
                continue

            # Doctor suffix check: John Smith, DDS
            for match in DOCTOR_SUFFIX_REGEX.finditer(text):
                full_name = cls.clean_name(match.group(1))
                credential = match.group(2).upper()
                if cls.is_valid_person_name(full_name):
                    doc_entry = f"Dr. {full_name}, {credential}"
                    if doc_entry not in doctors:
                        doctors.append(doc_entry)

            # Doctor prefix check: Dr. John Smith
            for match in DOCTOR_PREFIX_REGEX.finditer(text):
                full_name = cls.clean_name(match.group(1))
                if cls.is_valid_person_name(full_name):
                    # Avoid double adding if already present
                    if not any(full_name in d for d in doctors):
                        doctors.append(f"Dr. {full_name}")

            # Office Manager check
            for match in OFFICE_MGR_REGEX.finditer(text):
                name = cls.clean_name(match.group(1))
                role = match.group(2).title()
                if cls.is_valid_person_name(name):
                    entry = f"{name} ({role})"
                    if entry not in managers:
                        managers.append(entry)

            for match in OFFICE_MGR_PREFIX_REGEX.finditer(text):
                name = cls.clean_name(match.group(1))
                if cls.is_valid_person_name(name):
                    entry = f"{name} (Office Manager)"
                    if entry not in managers:
                        managers.append(entry)

        # 2. Extract mailto: links
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if href.lower().startswith("mailto:"):
                raw_email = href.split(":", 1)[1].split("?")[0].strip()
                if EMAIL_REGEX.match(raw_email):
                    clean_em = raw_email.lower()
                    if not any(clean_em.endswith(ext) for ext in [".png", ".jpg", ".svg", ".webp", ".gif"]) and \
                       not any(ign in clean_em for ign in ["sentry", "wix", "example.com", "domain.com", "schema.org"]):
                        if clean_em not in emails:
                            emails.append(clean_em)

        # 3. Text regex fallback for emails
        for em in EMAIL_REGEX.findall(html):
            clean_em = em.lower()
            if not any(clean_em.endswith(ext) for ext in [".png", ".jpg", ".svg", ".webp", ".gif"]) and \
               not any(ign in clean_em for ign in ["sentry", "wix", "example.com", "domain.com", "schema.org"]):
                if clean_em not in emails:
                    emails.append(clean_em)

        # Select primary doctor
        primary_doctor = doctors[0] if doctors else None
        primary_manager = managers[0] if managers else None

        return {
            "primary_doctor": primary_doctor,
            "practice_manager": primary_manager,
            "doctors": doctors,
            "managers": managers,
            "emails": emails[:5]
        }

    @classmethod
    def find_team_subpages(cls, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Find candidate subpages like /about, /our-team, /meet-the-doctor."""
        candidates = []
        parsed_base = urllib.parse.urlparse(base_url)
        base_domain = parsed_base.netloc.lower()

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            link_text = a.get_text(" ", strip=True).lower()
            href_lower = href.lower()

            # Check if keyword is in href or link text
            is_match = any(kw in href_lower for kw in TEAM_URL_KEYWORDS) or \
                       any(kw in link_text for kw in ["meet the doctor", "our team", "our doctors", "about dr", "meet our team", "about us"])

            if is_match:
                # Resolve full URL
                full_url = urllib.parse.urljoin(base_url, href)
                parsed_full = urllib.parse.urlparse(full_url)
                
                # Must be on the same domain and not an anchor/file download
                if parsed_full.netloc.lower() == base_domain:
                    # Strip fragment and query
                    clean_target = f"{parsed_full.scheme}://{parsed_full.netloc}{parsed_full.path}".rstrip("/")
                    if clean_target and clean_target not in candidates and clean_target != base_url.rstrip("/"):
                        if not any(clean_target.endswith(ext) for ext in [".pdf", ".jpg", ".png", ".zip"]):
                            candidates.append(clean_target)

        # Sort candidate subpages to prioritize /doctor, /team, /about
        def score_url(u: str) -> int:
            u_low = u.lower()
            if "doctor" in u_low: return 3
            if "team" in u_low: return 2
            if "about" in u_low: return 1
            return 0

        candidates.sort(key=score_url, reverse=True)
        return candidates[:3]

    @classmethod
    async def crawl_and_extract(
        cls,
        client: Any,
        base_url: str,
        homepage_html: str,
        homepage_soup: BeautifulSoup
    ) -> Dict[str, Any]:
        """Extract decision makers from homepage, and if incomplete, inspect up to 2 team subpages."""
        results = cls.extract_from_html(homepage_html, homepage_soup)

        # If primary doctor not found on homepage, crawl subpages
        subpages = cls.find_team_subpages(homepage_soup, base_url)
        for sub_url in subpages[:2]:
            try:
                resp = await client.get(sub_url)
                if resp.status_code == 200:
                    sub_soup = BeautifulSoup(resp.text, "html.parser")
                    sub_res = cls.extract_from_html(resp.text, sub_soup)

                    # Merge doctors
                    for doc in sub_res["doctors"]:
                        if doc not in results["doctors"]:
                            results["doctors"].append(doc)

                    # Merge managers
                    for mgr in sub_res["managers"]:
                        if mgr not in results["managers"]:
                            results["managers"].append(mgr)

                    # Merge emails
                    for em in sub_res["emails"]:
                        if em not in results["emails"]:
                            results["emails"].append(em)

                    if not results["primary_doctor"] and results["doctors"]:
                        results["primary_doctor"] = results["doctors"][0]
                    if not results["practice_manager"] and results["managers"]:
                        results["practice_manager"] = results["managers"][0]

                    # If we found a primary doctor, we can stop crawling
                    if results["primary_doctor"]:
                        break
            except Exception:
                pass

        return results
