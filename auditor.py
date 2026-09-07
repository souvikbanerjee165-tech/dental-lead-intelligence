import re
import time
import urllib.parse
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import httpx
import yaml
from bs4 import BeautifulSoup

def compute_content_hash(html_content: str) -> str:
    """Calculates a deterministic SHA256 hash of webpage HTML with normalized whitespace."""
    if not html_content:
        return ""
    normalized = " ".join(html_content.split())
    return hashlib.sha256(normalized.encode("utf-8", errors="ignore")).hexdigest()

from config import USER_AGENT, BASE_DIR
from models import (
    RawLead, WebsiteAuditResult, ScoredLead, 
    TechStackDetail, SEOScoreResult, DigitalMaturityScore
)
from evidence import (
    EvidenceItem, Finding, EvidenceGraph, ConfidenceCalculator,
    DOMEvidence, ScriptEvidence, HeaderEvidence, NetworkEvidence, TextEvidence
)
from insights import InsightEngine
from prioritizer import DealPrioritizationEngine
from telemetry import TelemetryTracker, AuditTelemetry
from database import DatabaseManager
from decision_hunter import DecisionMakerHunter

RULES_DIR = BASE_DIR / "rules"
FINGERPRINTS_DIR = RULES_DIR / "fingerprints"
FRAMEWORKS_DIR = RULES_DIR / "frameworks"

class WebsiteAuditor:
    """Enterprise Auditor: Evaluates sites via declarative YAML rules, builds an Evidence Graph, and persists to SQLite."""

    def __init__(self, timeout: float = 12.0):
        self.timeout = timeout
        self.client_headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        self.db = DatabaseManager()
        self.fingerprints = self._load_fingerprints()
        self.framework = self._load_framework("dental.yaml")

    def _load_fingerprints(self) -> List[Dict[str, Any]]:
        """Load all YAML fingerprint rules from rules/fingerprints/ directory."""
        all_fps = []
        if FINGERPRINTS_DIR.exists():
            for yaml_path in FINGERPRINTS_DIR.glob("*.yaml"):
                try:
                    with open(yaml_path, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                        if data and "fingerprints" in data:
                            all_fps.extend(data["fingerprints"])
                except Exception:
                    pass
        return all_fps

    def _load_framework(self, framework_file: str) -> Dict[str, Any]:
        """Load scoring framework from rules/frameworks/."""
        path = FRAMEWORKS_DIR / framework_file
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    return data.get("framework", {})
            except Exception:
                pass
        return {}

    async def audit_lead(self, raw_lead: RawLead, check_incremental: bool = True, force: bool = False) -> ScoredLead:
        """Audits a raw lead's website, compiles the Evidence Graph, and saves to SQLite."""
        self._current_audit_start = time.time()
        if not raw_lead.website:
            audit_result = WebsiteAuditResult(
                reachable=False,
                has_ssl=False,
                has_ai_chatbot=False,
                has_online_booking=False,
                has_faq_section=False,
                is_mobile_responsive=False
            )
            scored = self._calculate_scores(raw_lead, audit_result, EvidenceGraph())
            self.db.save_scored_lead(scored, scored.findings)
            return scored

        lead_id = self.db._make_lead_id(raw_lead.name, raw_lead.website)
        prev_hash = self.db.get_latest_content_hash(lead_id) if check_incremental else None

        audit_result, evidence_graph, content_hash = await self._crawl_and_analyze(raw_lead.website)

        # Incremental check: If site content is identical and not forced, return cached representation
        if not force and check_incremental and prev_hash and content_hash and prev_hash == content_hash:
            existing_lead = self.db.get_lead(lead_id)
            if existing_lead:
                scored = self._calculate_scores(raw_lead, audit_result, evidence_graph)
                scored.content_hash = content_hash
                scored.was_cached = True
                return scored

        scored = self._calculate_scores(raw_lead, audit_result, evidence_graph)
        scored.content_hash = content_hash
        self.db.save_scored_lead(scored, scored.findings)
        return scored

    async def _crawl_and_analyze(self, website_url: str) -> Tuple[WebsiteAuditResult, EvidenceGraph, str]:
        """Crawl website, match declarative YAML fingerprints, and construct Evidence Graph."""
        if not website_url.startswith("http://") and not website_url.startswith("https://"):
            website_url = "https://" + website_url

        has_ssl = website_url.startswith("https://")
        start_time = time.time()
        graph = EvidenceGraph()

        try:
            async with httpx.AsyncClient(
                headers=self.client_headers,
                timeout=self.timeout,
                follow_redirects=True,
                verify=False
            ) as client:
                response = await client.get(website_url)
                load_time = round(time.time() - start_time, 2)
                
                if response.status_code >= 400:
                    graph.add_evidence(EvidenceItem(
                        evidence_type="http_status",
                        source=website_url,
                        snippet=f"HTTP {response.status_code} Error",
                        confidence=1.0
                    ))
                    return WebsiteAuditResult(
                        reachable=False,
                        status_code=response.status_code,
                        has_ssl=has_ssl,
                        load_time_seconds=load_time
                    ), graph, ""

                html_content = response.text
                final_url = str(response.url)
                soup = BeautifulSoup(html_content, "html.parser")

                # 1. Match Declarative Fingerprints
                tech_detail = self._match_declarative_fingerprints(html_content, soup, response.headers, graph, final_url)

                # 2. Chatbot & Booking
                has_chatbot = len(tech_detail.chatbots) > 0
                chatbot_name = tech_detail.chatbots[0] if has_chatbot else None

                has_booking = len(tech_detail.booking_tools) > 0
                booking_tool = tech_detail.booking_tools[0] if has_booking else None
                if not has_booking:
                    has_booking, booking_tool, booking_snippet = self._check_booking_links(soup)
                    if has_booking and booking_tool:
                        tech_detail.booking_tools.append(booking_tool)
                        graph.add_evidence(EvidenceItem(
                            evidence_type="dom_presence",
                            source=final_url,
                            snippet=f"Found appointment link: '{booking_snippet}'",
                            confidence=0.88
                        ))

                # 3. SEO Audit
                seo_audit = self._audit_seo(soup, html_content, graph, final_url)

                # 4. Conversion & UX checks
                phone_links = soup.find_all("a", href=re.compile(r"^tel:"))
                clickable_phone = len(phone_links) > 0
                if clickable_phone:
                    graph.add_evidence(EvidenceItem(
                        evidence_type="dom_presence",
                        source=final_url,
                        snippet=f"Found {len(phone_links)} clickable tel: button(s)",
                        confidence=1.0
                    ))

                has_emergency = bool(re.search(r"emergency|urgent\s+dental|same-day|pain\s+relief", html_content, re.IGNORECASE))
                has_insurance = bool(re.search(r"insurance|financing|payment\s+options|carecredit|in-network", html_content, re.IGNORECASE))

                # 5. Contacts & Socials
                emails = self._extract_emails(html_content, soup)
                phones = self._extract_phones(html_content, soup)
                social_links = self._extract_socials(soup)
                has_whatsapp = "whatsapp" in social_links or "api.whatsapp.com" in html_content or "wa.me" in html_content
                contact_page = self._find_contact_page(soup, final_url)

                if contact_page and len(emails) == 0:
                    try:
                        contact_resp = await client.get(contact_page)
                        if contact_resp.status_code == 200:
                            contact_soup = BeautifulSoup(contact_resp.text, "html.parser")
                            extra_emails = self._extract_emails(contact_resp.text, contact_soup)
                            for em in extra_emails:
                                if em not in emails:
                                    emails.append(em)
                    except Exception:
                        pass

                # 6. Decision-Maker & Doctor/Email Hunter
                dm_info = await DecisionMakerHunter.crawl_and_extract(
                    client=client,
                    base_url=final_url,
                    homepage_html=html_content,
                    homepage_soup=soup
                )
                for em in dm_info.get("emails", []):
                    if em not in emails:
                        emails.append(em)

                primary_doctor = dm_info.get("primary_doctor")
                primary_manager = dm_info.get("practice_manager")
                staff_roster = dm_info.get("doctors", []) + dm_info.get("managers", [])

                has_faq = self._detect_faq(html_content, soup)
                viewport_meta = soup.find("meta", attrs={"name": "viewport"})
                is_mobile_responsive = viewport_meta is not None

                return WebsiteAuditResult(
                    reachable=True,
                    status_code=response.status_code,
                    has_ssl=has_ssl,
                    load_time_seconds=load_time,
                    has_ai_chatbot=has_chatbot,
                    detected_chatbot_name=chatbot_name,
                    has_online_booking=has_booking,
                    detected_booking_tool=booking_tool,
                    has_faq_section=has_faq,
                    is_mobile_responsive=is_mobile_responsive,
                    has_clickable_phone=clickable_phone,
                    has_emergency_notice=has_emergency,
                    has_insurance_accepted_section=has_insurance,
                    emails=emails,
                    phones=phones,
                    contact_page_url=contact_page,
                    social_links=social_links,
                    has_whatsapp=has_whatsapp,
                    tech_stack=tech_detail,
                    seo_audit=seo_audit,
                    page_title=seo_audit.page_title,
                    doctor_name=primary_doctor,
                    decision_maker_role=primary_manager,
                    staff_roster=staff_roster
                ), graph, compute_content_hash(html_content)

        except Exception:
            return WebsiteAuditResult(
                reachable=False,
                has_ssl=has_ssl,
                load_time_seconds=round(time.time() - start_time, 2)
            ), graph, ""

    def _match_declarative_fingerprints(
        self, html: str, soup: BeautifulSoup, headers: Any, graph: EvidenceGraph, url: str
    ) -> TechStackDetail:
        """Evaluates all declarative YAML rules against page text, scripts, and HTTP headers."""
        html_lower = html.lower()
        scripts = " ".join([s.get("src", "") + " " + s.get_text() for s in soup.find_all("script")]).lower()
        headers_str = " ".join([f"{k}:{v}" for k, v in headers.items()]).lower()

        detail = TechStackDetail()

        for fp in self.fingerprints:
            name = fp["name"]
            category = fp["category"]
            patterns = fp.get("patterns", [])
            header_patterns = fp.get("headers", [])
            base_conf = fp.get("confidence", 0.95)

            matched = False
            match_snippet = ""
            match_type = "script_signature"

            # Check regex patterns
            for pat in patterns:
                m = re.search(pat, scripts)
                if m:
                    matched = True
                    match_snippet = f"Matched script pattern: '{pat}'"
                    match_type = "script_signature"
                    break
                m = re.search(pat, html_lower)
                if m:
                    matched = True
                    match_snippet = f"Matched HTML token: '{pat}'"
                    match_type = "dom_presence"
                    break

            # Check header patterns
            if not matched and header_patterns:
                for hpat in header_patterns:
                    if re.search(hpat.lower(), headers_str):
                        matched = True
                        match_snippet = f"Matched HTTP header: '{hpat}'"
                        match_type = "http_header"
                        break

            if matched:
                ev = EvidenceItem(
                    evidence_type=match_type,
                    source=url,
                    snippet=f"Detected {name} ({match_snippet})",
                    confidence=base_conf
                )
                graph.add_evidence(ev)

                # Categorize into TechStackDetail
                cat_lower = category.lower()
                if "cms" in cat_lower or "framework" in cat_lower:
                    if name not in detail.cms_and_frameworks: detail.cms_and_frameworks.append(name)
                elif "analytics" in cat_lower:
                    if name not in detail.analytics: detail.analytics.append(name)
                elif "tag" in cat_lower:
                    if name not in detail.tag_managers: detail.tag_managers.append(name)
                elif "pixel" in cat_lower or "ad" in cat_lower:
                    if name not in detail.ad_pixels: detail.ad_pixels.append(name)
                elif "crm" in cat_lower:
                    if name not in detail.crm_and_marketing: detail.crm_and_marketing.append(name)
                elif "cloud" in cat_lower:
                    if name not in detail.cloud_and_cdn: detail.cloud_and_cdn.append(name)
                elif "chat" in cat_lower:
                    if name not in detail.chatbots: detail.chatbots.append(name)
                elif "book" in cat_lower:
                    if name not in detail.booking_tools: detail.booking_tools.append(name)

        return detail

    def _audit_seo(self, soup: BeautifulSoup, html: str, graph: EvidenceGraph, url: str) -> SEOScoreResult:
        title_tag = soup.find("title")
        page_title = title_tag.get_text().strip() if title_tag else None
        title_len = len(page_title) if page_title else 0

        meta_desc = soup.find("meta", attrs={"name": re.compile(r"description", re.I)})
        has_desc = meta_desc is not None and bool(meta_desc.get("content", "").strip())
        desc_len = len(meta_desc.get("content", "").strip()) if has_desc else 0

        h1s = soup.find_all("h1")
        h2s = soup.find_all("h2")
        has_og = bool(soup.find("meta", property=re.compile(r"^og:")))
        has_favicon = bool(soup.find("link", rel=re.compile(r"icon", re.I)))

        images = soup.find_all("img")
        if images:
            with_alt = sum(1 for img in images if bool(img.get("alt", "").strip()))
            alt_coverage = round((with_alt / len(images)) * 100, 1)
        else:
            alt_coverage = 100.0

        graph.add_evidence(EvidenceItem(
            evidence_type="meta_tag",
            source=url,
            snippet=f"SEO: Title ({title_len} chars), Meta Desc ({'Present' if has_desc else 'Missing'}), {len(h1s)} H1(s), {len(h2s)} H2(s)",
            confidence=1.0
        ))

        return SEOScoreResult(
            page_title=page_title,
            title_length=title_len,
            has_meta_description=has_desc,
            meta_description_length=desc_len,
            h1_count=len(h1s),
            h2_count=len(h2s),
            has_opengraph=has_og,
            has_favicon=has_favicon,
            img_alt_coverage_pct=alt_coverage
        )

    def _check_booking_links(self, soup: BeautifulSoup) -> Tuple[bool, Optional[str], Optional[str]]:
        booking_keywords = ["book online", "schedule online", "book appointment", "request appointment", "schedule now"]
        for a in soup.find_all("a", href=True):
            text = a.get_text().strip().lower()
            href = a.get("href", "").lower()
            for kw in booking_keywords:
                if kw in text or kw.replace(" ", "-") in href or kw.replace(" ", "_") in href:
                    return True, "Direct Booking Link / Form", a.get_text().strip() or href
        return False, None, None

    def _extract_emails(self, html: str, soup: BeautifulSoup) -> List[str]:
        emails = set()
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if href.startswith("mailto:"):
                clean_email = href.replace("mailto:", "").split("?")[0].strip()
                if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', clean_email):
                    emails.add(clean_email.lower())
        for match in re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html):
            clean = match.strip().lower()
            if not any(clean.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".js", ".css"]):
                emails.add(clean)
        return list(emails)[:5]

    def _extract_phones(self, html: str, soup: BeautifulSoup) -> List[str]:
        phones = set()
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if href.startswith("tel:"):
                phones.add(href.replace("tel:", "").strip())
        return list(phones)[:3]

    def _extract_socials(self, soup: BeautifulSoup) -> Dict[str, str]:
        socials = {}
        platforms = {
            "facebook": r"facebook\.com/(?!sharer)",
            "instagram": r"instagram\.com/",
            "linkedin": r"linkedin\.com/(company|in)/",
            "twitter": r"(twitter\.com|x\.com)/",
            "youtube": r"youtube\.com/(c/|channel/|user/|@)",
            "whatsapp": r"(wa\.me|api\.whatsapp\.com)"
        }
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            for platform, pattern in platforms.items():
                if platform not in socials and re.search(pattern, href, re.IGNORECASE):
                    socials[platform] = href
        return socials

    def _find_contact_page(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        for a in soup.find_all("a", href=True):
            text = a.get_text().strip().lower()
            href = a.get("href", "")
            if text in ["contact", "contact us", "get in touch", "locations"] or "contact" in href.lower():
                return urllib.parse.urljoin(base_url, href)
        return None

    def _detect_faq(self, html: str, soup: BeautifulSoup) -> bool:
        if "faq" in html.lower() or "schema.org/faqpage" in html.lower():
            return True
        if soup.find("details") or soup.find(class_=re.compile(r"accordion|faq", re.I)):
            return True
        return False

    def _calculate_scores(
        self, raw_lead: RawLead, audit: WebsiteAuditResult, graph: EvidenceGraph
    ) -> ScoredLead:
        """
        Synthesizes the Evidence Graph into:
        1. Explicit Findings (with citations and confidence)
        2. Opportunity Score (0-100)
        3. Digital Maturity Pillars (0-100)
        4. Defensible Revenue Leakage Model
        """
        findings: List[Finding] = []

        # Revenue Leakage Parameters from Framework
        reviews = raw_lead.review_count or 15
        if reviews >= 200:
            base_min, base_max = 30, 55
        elif reviews >= 50:
            base_min, base_max = 18, 35
        else:
            base_min, base_max = 10, 20

        # Finding 1: AI Chatbot Inspection
        if not audit.has_ai_chatbot:
            findings.append(Finding(
                id="FIND-CHAT-ABSENCE",
                category="Automation & AI Intake",
                title="Absence of 24/7 AI Chatbot & Intake Assistant",
                description="Prospective patients visiting after 5 PM have no conversational assistant to ask insurance or procedure questions.",
                evidence=[EvidenceItem(
                    evidence_type="dom_absence",
                    source="homepage.html",
                    snippet="Inspected script tags and DOM containers; no AI chatbot signature detected",
                    confidence=0.97
                )],
                confidence=0.97,
                severity="critical",
                recommendation="Deploy 24/7 conversational AI receptionist to answer insurance questions and capture after-hours patients.",
                projected_monthly_roi=base_min * 150.0
            ))
        else:
            findings.append(Finding(
                id="FIND-CHAT-ACTIVE",
                category="Automation & AI Intake",
                title=f"Active Chatbot Widget ({audit.detected_chatbot_name})",
                description=f"Website offers real-time messaging via {audit.detected_chatbot_name}.",
                evidence=[EvidenceItem(
                    evidence_type="script_signature",
                    source="homepage.html",
                    snippet=f"Detected active {audit.detected_chatbot_name} script",
                    confidence=0.99
                )],
                confidence=0.99,
                severity="optimal",
                recommendation="Ensure conversational AI answers clinical FAQs and syncs directly into PMS.",
                projected_monthly_roi=0.0
            ))

        # Finding 2: Online Booking Inspection
        if not audit.has_online_booking:
            findings.append(Finding(
                id="FIND-BOOKING-ABSENCE",
                category="Patient Experience & Accessibility",
                title="Absence of Direct Online Appointment Booking",
                description="Patients must call office during business hours. Over 42% of patients search after hours and abandon without self-serve booking.",
                evidence=[EvidenceItem(
                    evidence_type="dom_absence",
                    source="homepage.html",
                    snippet="No NexHealth, LocalMed, Zocdoc, or direct booking embed detected in navigation or action buttons",
                    confidence=0.96
                )],
                confidence=0.96,
                severity="critical",
                recommendation="Integrate real-time patient appointment scheduling to eliminate telephone friction.",
                projected_monthly_roi=base_min * 200.0
            ))
        else:
            findings.append(Finding(
                id="FIND-BOOKING-ACTIVE",
                category="Patient Experience & Accessibility",
                title=f"Online Booking System Active ({audit.detected_booking_tool})",
                description=f"Practice offers appointment self-scheduling via {audit.detected_booking_tool}.",
                evidence=[EvidenceItem(
                    evidence_type="dom_presence",
                    source="homepage.html",
                    snippet=f"Detected {audit.detected_booking_tool} signature in DOM",
                    confidence=0.98
                )],
                confidence=0.98,
                severity="optimal",
                recommendation="Maintain calendar availability and sync with AI intake.",
                projected_monthly_roi=0.0
            ))

        # Finding 3: CRM / Marketing Automation
        if not audit.tech_stack.crm_and_marketing:
            findings.append(Finding(
                id="FIND-CRM-ABSENCE",
                category="Automation & AI Intake",
                title="Missing CRM / Automated Patient Nurture Pipeline",
                description="Lead submissions and inquiry forms are not connected to GoHighLevel, HubSpot, or automated CRM tracking.",
                evidence=[EvidenceItem(
                    evidence_type="script_absence",
                    source="homepage.html",
                    snippet="No CRM tracking scripts detected",
                    confidence=0.95
                )],
                confidence=0.95,
                severity="high",
                recommendation="Connect web intake forms to automated SMS / email follow-up sequences.",
                projected_monthly_roi=1500.0
            ))

        # Finding 4: Local SEO & Metadata
        if not audit.seo_audit.has_meta_description or audit.seo_audit.h1_count != 1:
            findings.append(Finding(
                id="FIND-SEO-DEFICIT",
                category="SEO & Discoverability",
                title="Sub-optimal On-Page SEO Architecture",
                description=f"Missing meta description ({'No' if not audit.seo_audit.has_meta_description else 'Present'}) or non-standard H1 hierarchy ({audit.seo_audit.h1_count} H1 tags).",
                evidence=[EvidenceItem(
                    evidence_type="meta_tag",
                    source="homepage.html",
                    snippet=f"H1 count: {audit.seo_audit.h1_count}, Meta desc: {audit.seo_audit.has_meta_description}",
                    confidence=1.0
                )],
                confidence=1.0,
                severity="medium",
                recommendation="Optimize single target H1 and add high-converting meta description with phone number.",
                projected_monthly_roi=1000.0
            ))

        for f in findings:
            f.confidence = ConfidenceCalculator.calculate_finding_confidence(f.evidence, is_absence_finding="ABSENCE" in f.id)
            graph.add_finding(f)

        # Compute Opportunity Score (Fit)
        opp_score = 0
        breakdown = {}
        if not audit.has_ai_chatbot:
            opp_score += 25
            breakdown["No AI Chatbot"] = 25
        if not audit.has_online_booking:
            opp_score += 20
            breakdown["No Online Booking Widget"] = 20
        if not audit.reachable or (audit.load_time_seconds and audit.load_time_seconds > 3.5) or not audit.is_mobile_responsive:
            opp_score += 20
            breakdown["Outdated / Slow / Non-responsive"] = 20
        if (raw_lead.review_count and raw_lead.review_count < 50) or not audit.has_faq_section:
            opp_score += 15
            breakdown["Low Reviews or No FAQ"] = 15
        if not audit.has_whatsapp or len(audit.social_links) == 0:
            opp_score += 10
            breakdown["Missing Mobile Channels"] = 10
        if not audit.has_ssl:
            opp_score += 10
            breakdown["Insecure (No SSL)"] = 10

        total_opp_score = min(100, opp_score)
        high_value = total_opp_score >= 60

        # Compute 5 Digital Maturity Pillars
        wq = 30 if audit.reachable else 0
        if audit.has_ssl: wq += 25
        if audit.is_mobile_responsive: wq += 25
        if audit.load_time_seconds and audit.load_time_seconds <= 2.5: wq += 20
        elif audit.load_time_seconds and audit.load_time_seconds <= 4.0: wq += 10

        px = 10
        if audit.has_online_booking: px += 40
        if audit.has_ai_chatbot: px += 35
        if audit.has_faq_section: px += 15

        seo = 10
        if audit.seo_audit.has_meta_description: seo += 25
        if audit.seo_audit.h1_count == 1: seo += 20
        elif audit.seo_audit.h1_count > 1: seo += 10
        if audit.seo_audit.h2_count >= 2: seo += 15
        if audit.seo_audit.has_opengraph: seo += 15
        if audit.seo_audit.img_alt_coverage_pct >= 70: seo += 15

        auto = 5
        if audit.has_ai_chatbot: auto += 35
        if audit.tech_stack.crm_and_marketing: auto += 25
        if audit.tech_stack.analytics: auto += 20
        if audit.tech_stack.ad_pixels: auto += 15

        conv = 10
        if audit.has_clickable_phone: conv += 25
        if audit.has_online_booking: conv += 25
        if audit.has_emergency_notice: conv += 20
        if audit.has_insurance_accepted_section: conv += 20

        overall_maturity = int((wq + px + seo + auto + conv) / 5)

        # Top 5 Ranked Improvements
        improvements = []
        rank_idx = 1
        for f in findings:
            if f.severity in ["critical", "high", "medium"]:
                improvements.append({
                    "rank": rank_idx,
                    "title": f.recommendation,
                    "impact": f"High (Solves: {f.title})",
                    "effort": "Low (Turnkey)",
                    "estimated_roi": f"${f.projected_monthly_roi * 12:,.0f} / year"
                })
                rank_idx += 1

        maturity_result = DigitalMaturityScore(
            overall_score=overall_maturity,
            website_quality=wq,
            patient_experience=px,
            seo_readiness=seo,
            automation_score=auto,
            conversion_score=conv,
            top_improvements=improvements[:5]
        )

        # Revenue Leakage Model
        if not audit.has_online_booking and not audit.has_ai_chatbot:
            leak_factor = 1.0
        elif not audit.has_ai_chatbot and audit.has_online_booking:
            leak_factor = 0.5
        elif audit.has_ai_chatbot and not audit.has_online_booking:
            leak_factor = 0.35
        else:
            leak_factor = 0.05

        missed_min = max(0, int(base_min * leak_factor))
        missed_max = max(missed_min, int(base_max * leak_factor))
        avg_patient_val = 250

        monthly_loss_min = missed_min * avg_patient_val
        monthly_loss_max = missed_max * avg_patient_val
        annual_loss = int(((monthly_loss_min + monthly_loss_max) / 2) * 12)

        # Wire Layer 3: Executive Business Insights
        insights = InsightEngine.synthesize_insights(
            findings=findings,
            review_count=raw_lead.review_count or 0,
            rating=raw_lead.rating or 0.0,
            has_pixels=bool(audit.tech_stack.ad_pixels)
        )

        # Wire Layer 4: Decisions & Deal Prioritization
        monthly_loss_avg = int((monthly_loss_min + monthly_loss_max) / 2)
        deal_priority = DealPrioritizationEngine.evaluate_deal(
            raw_lead=raw_lead,
            audit=audit,
            maturity=maturity_result,
            estimated_monthly_loss=monthly_loss_avg
        )

        # Wire Structured Telemetry
        audit_duration = int((time.time() - getattr(self, "_current_audit_start", time.time())) * 1000)
        telem = AuditTelemetry(
            lead_name=raw_lead.name,
            target_url=raw_lead.website,
            duration_ms=audit_duration,
            http_status=audit.status_code,
            detectors_evaluated=len(self.fingerprints) + 5,
            evidence_collected_count=len(graph.raw_evidence),
            findings_count=len(findings),
            insights_count=len(insights),
            confidence_score=graph.get_overall_confidence(),
            deal_priority_tier=deal_priority.tier.value
        )
        TelemetryTracker.record(telem)

        return ScoredLead(
            raw_lead=raw_lead,
            audit=audit,
            opportunity_score=total_opp_score,
            score_breakdown=breakdown,
            high_value_target=high_value,
            findings=findings,
            evidence_confidence=graph.get_overall_confidence(),
            insights=insights,
            deal_priority=deal_priority,
            maturity=maturity_result,
            estimated_missed_calls_monthly_min=missed_min,
            estimated_missed_calls_monthly_max=missed_max,
            estimated_missed_revenue_monthly_min=monthly_loss_min,
            estimated_missed_revenue_monthly_max=monthly_loss_max,
            estimated_missed_revenue_annual=annual_loss,
            doctor_name=audit.doctor_name,
            decision_maker_role=audit.decision_maker_role,
            staff_roster=audit.staff_roster
        )
