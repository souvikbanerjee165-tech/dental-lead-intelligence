from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class RawLead(BaseModel):
    """Lead extracted from Google Maps."""
    name: str
    category: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = 0
    phone: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None
    maps_url: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class TechStackDetail(BaseModel):
    """Categorized technology stack fingerprint."""
    cms_and_frameworks: List[str] = Field(default_factory=list)
    analytics: List[str] = Field(default_factory=list)
    tag_managers: List[str] = Field(default_factory=list)
    ad_pixels: List[str] = Field(default_factory=list)
    crm_and_marketing: List[str] = Field(default_factory=list)
    cloud_and_cdn: List[str] = Field(default_factory=list)
    booking_tools: List[str] = Field(default_factory=list)
    chatbots: List[str] = Field(default_factory=list)

    def summary_list(self) -> List[str]:
        """Returns all detected technologies as a flat list."""
        all_tech = []
        for v in [self.cms_and_frameworks, self.analytics, self.tag_managers, self.ad_pixels, 
                  self.crm_and_marketing, self.cloud_and_cdn, self.booking_tools, self.chatbots]:
            all_tech.extend(v)
        return list(dict.fromkeys(all_tech))

class SEOScoreResult(BaseModel):
    """SEO and on-page technical metrics."""
    page_title: Optional[str] = None
    title_length: int = 0
    has_meta_description: bool = False
    meta_description_length: int = 0
    h1_count: int = 0
    h2_count: int = 0
    has_opengraph: bool = False
    has_favicon: bool = False
    img_alt_coverage_pct: float = 100.0

class DigitalMaturityScore(BaseModel):
    """Holistic AI Business Health & Digital Maturity Score (0-100)."""
    overall_score: int = 0
    website_quality: int = 0         # Speed, SSL, Responsive, Modern stack
    patient_experience: int = 0      # Booking, 24/7 Live help, FAQs
    seo_readiness: int = 0           # Titles, H1/H2, meta description, OG tags
    automation_score: int = 0        # AI chatbot, CRM, Pixels, Analytics
    conversion_score: int = 0        # Click-to-call, prominent CTAs, emergency notice, insurance
    top_improvements: List[Dict[str, Any]] = Field(default_factory=list)

class MultichannelSequence(BaseModel):
    """4-Touch AI SDR Omnichannel Outreach Sequence with Cold Call Battlecards."""
    day1_email_subject: str = ""
    day1_email_body: str = ""
    day3_linkedin_message: str = ""
    day5_sms_message: str = ""
    day7_cold_call_script: str = ""
    whatsapp_pitch: str = ""
    whatsapp_link: str = ""
    objection_battlecards: Dict[str, str] = Field(default_factory=dict)

class WebsiteAuditResult(BaseModel):
    """Detailed audit metrics from website inspection."""
    reachable: bool = False
    status_code: Optional[int] = None
    has_ssl: bool = True
    load_time_seconds: Optional[float] = None
    
    # Feature detections
    has_ai_chatbot: bool = False
    detected_chatbot_name: Optional[str] = None
    
    has_online_booking: bool = False
    detected_booking_tool: Optional[str] = None
    
    has_faq_section: bool = False
    is_mobile_responsive: bool = True
    
    # Conversion & UX checks
    has_clickable_phone: bool = False
    has_emergency_notice: bool = False
    has_insurance_accepted_section: bool = False
    
    # Contact & Social extraction
    emails: List[str] = Field(default_factory=list)
    phones: List[str] = Field(default_factory=list)
    contact_page_url: Optional[str] = None
    social_links: Dict[str, str] = Field(default_factory=dict)
    has_whatsapp: bool = False
    
    # Decision-Maker & Staff Intelligence
    doctor_name: Optional[str] = None
    decision_maker_role: Optional[str] = None
    staff_roster: List[str] = Field(default_factory=list)

    # Deep Intelligence Modules
    tech_stack: TechStackDetail = Field(default_factory=TechStackDetail)
    seo_audit: SEOScoreResult = Field(default_factory=SEOScoreResult)
    page_title: Optional[str] = None
    screenshot_path: Optional[str] = None

from evidence import Finding
from insights import BusinessInsight
from prioritizer import DealPrioritizationResult

class ScoredLead(BaseModel):
    """Unified enterprise lead data with health scores, revenue leakage, and SDR sequence."""
    raw_lead: RawLead
    audit: WebsiteAuditResult
    opportunity_score: int = 0
    score_breakdown: Dict[str, int] = Field(default_factory=dict)
    high_value_target: bool = False
    
    # Layer 1 & 2: Evidence & Findings
    findings: List[Finding] = Field(default_factory=list)
    evidence_confidence: float = 0.90

    # Layer 3: Executive Business Insights
    insights: List[BusinessInsight] = Field(default_factory=list)

    # Layer 4: Decisions & Deal Prioritization
    deal_priority: Optional[DealPrioritizationResult] = None

    # Digital Maturity & Business Health
    maturity: DigitalMaturityScore = Field(default_factory=DigitalMaturityScore)

    # Financial Leakage & Missed Patient Metrics
    estimated_missed_calls_monthly_min: int = 0
    estimated_missed_calls_monthly_max: int = 0
    estimated_missed_revenue_monthly_min: int = 0
    estimated_missed_revenue_monthly_max: int = 0
    estimated_missed_revenue_annual: int = 0

    # AI SDR & Multichannel Sequence
    sequence: MultichannelSequence = Field(default_factory=MultichannelSequence)
    personalized_angle: Optional[str] = None
    outreach_subject: Optional[str] = None
    outreach_body: Optional[str] = None
    pdf_report_path: Optional[str] = None
    screenshot_path: Optional[str] = None
    why_score_reasons: List[str] = Field(default_factory=list)
    content_hash: Optional[str] = None
    doctor_name: Optional[str] = None
    decision_maker_role: Optional[str] = None
    staff_roster: List[str] = Field(default_factory=list)
    stage: str = "AUDITED"
    notes: Optional[str] = None
    was_cached: bool = False

    def to_flat_dict(self) -> Dict[str, Any]:
        """Flatten nested lead data into a clean single-row dict for CSV/Excel export."""
        return {
            "Deal Priority Tier": self.deal_priority.tier.value if self.deal_priority else "TIER 2",
            "Deal Priority Score": self.deal_priority.priority_score if self.deal_priority else self.opportunity_score,
            "Doctor / Owner": self.doctor_name or self.audit.doctor_name or "Not Identified",
            "Decision Maker Role": self.decision_maker_role or self.audit.decision_maker_role or "",
            "Digital Maturity (0-100)": self.maturity.overall_score,
            "Opportunity Score (0-100)": self.opportunity_score,
            "High Value Target": "YES" if self.high_value_target else "NO",
            "Key Strategic Insight": self.insights[0].title if self.insights else "Standard Review",
            "Est. Missed Patients / Mo": f"{self.estimated_missed_calls_monthly_min}-{self.estimated_missed_calls_monthly_max}" if self.estimated_missed_calls_monthly_max > 0 else "0",
            "Est. Monthly Lost Revenue": f"${self.estimated_missed_revenue_monthly_min:,.0f} - ${self.estimated_missed_revenue_monthly_max:,.0f}" if self.estimated_missed_revenue_monthly_max > 0 else "$0",
            "Est. Annual Lost Revenue": f"${self.estimated_missed_revenue_annual:,.0f}" if self.estimated_missed_revenue_annual > 0 else "$0",
            "Business Name": self.raw_lead.name,
            "Category": self.raw_lead.category or "",
            "Rating": self.raw_lead.rating or "",
            "Reviews": self.raw_lead.review_count or 0,
            "Phone": self.raw_lead.phone or (self.audit.phones[0] if self.audit.phones else ""),
            "Website": self.raw_lead.website or "",
            "Emails": ", ".join(self.audit.emails) if self.audit.emails else "",
            "Address": self.raw_lead.address or "",
            # Pillars
            "Website Quality Score": self.maturity.website_quality,
            "Patient Experience Score": self.maturity.patient_experience,
            "SEO Score": self.maturity.seo_readiness,
            "Automation Score": self.maturity.automation_score,
            "Conversion Score": self.maturity.conversion_score,
            # Tech Stack
            "CMS / Framework": ", ".join(self.audit.tech_stack.cms_and_frameworks) or "Custom/Legacy",
            "Analytics": ", ".join(self.audit.tech_stack.analytics) or "None",
            "Tag Manager": ", ".join(self.audit.tech_stack.tag_managers) or "None",
            "Ad Pixels": ", ".join(self.audit.tech_stack.ad_pixels) or "None",
            "CRM / Marketing": ", ".join(self.audit.tech_stack.crm_and_marketing) or "None",
            "Cloud / CDN": ", ".join(self.audit.tech_stack.cloud_and_cdn) or "Standard",
            "Has AI Chatbot": "YES" if self.audit.has_ai_chatbot else "NO",
            "Detected Chatbot": self.audit.detected_chatbot_name or "None",
            "Has Online Booking": "YES" if self.audit.has_online_booking else "NO",
            "Detected Booking System": self.audit.detected_booking_tool or "None",
            "Has FAQ": "YES" if self.audit.has_faq_section else "NO",
            "Has WhatsApp": "YES" if self.audit.has_whatsapp else "NO",
            "Facebook": self.audit.social_links.get("facebook", ""),
            "Instagram": self.audit.social_links.get("instagram", ""),
            "LinkedIn": self.audit.social_links.get("linkedin", ""),
            "Contact Page": self.audit.contact_page_url or "",
            "Google Maps URL": self.raw_lead.maps_url or "",
            # Outreach Hooks
            "Outreach Pitch Angle": self.personalized_angle or "",
            "Day 1 Email Subject": self.sequence.day1_email_subject or self.outreach_subject or "",
            "Day 1 Email Body": self.sequence.day1_email_body or self.outreach_body or "",
            "Day 3 LinkedIn InMail": self.sequence.day3_linkedin_message or "",
            "Day 5 SMS Hook": self.sequence.day5_sms_message or "",
            "Day 7 Phone Script": self.sequence.day7_cold_call_script or "",
            "Audit Report PDF": self.pdf_report_path or ""
        }
