from typing import List, Dict, Any, Optional
from collections import Counter
from pydantic import BaseModel, Field

class CohortBenchmark(BaseModel):
    """Aggregate market adoption benchmarks across a localized competitive cohort."""
    geo_query: str
    total_competitors: int = 0
    booking_adoption_pct: float = 0.0
    chat_adoption_pct: float = 0.0
    pixel_adoption_pct: float = 0.0
    crm_adoption_pct: float = 0.0
    average_reviews: int = 0
    average_rating: float = 0.0
    popular_booking_tools: List[str] = Field(default_factory=list)
    popular_chatbots: List[str] = Field(default_factory=list)

    def summary_card(self) -> str:
        lines = [
            f"=== Local Competitive Cohort Benchmark ({self.total_competitors} Practices in {self.geo_query}) ===",
            f"- Online Booking Adoption: {int(self.booking_adoption_pct)}% (Tools: {', '.join(self.popular_booking_tools) or 'Custom'})",
            f"- AI Chat / Real-time Intake: {int(self.chat_adoption_pct)}% (Tools: {', '.join(self.popular_chatbots) or 'None'})",
            f"- Active Paid Advertising (Pixels): {int(self.pixel_adoption_pct)}%",
            f"- Automated CRM Pipelines: {int(self.crm_adoption_pct)}%",
            f"- Market Average Reviews: {self.average_reviews} (Avg Rating: {self.average_rating} stars)"
        ]
        return "\n".join(lines)

class MarketCohortAnalyzer:
    """Computes hyper-local market adoption statistics to produce high-urgency competitive sales hooks."""

    @classmethod
    def analyze_cohort(cls, scored_leads: List[Any], geo_query: str = "Local Market") -> CohortBenchmark:
        if not scored_leads:
            return CohortBenchmark(geo_query=geo_query)

        total = len(scored_leads)
        has_booking = sum(1 for l in scored_leads if l.audit.has_online_booking)
        has_chat = sum(1 for l in scored_leads if l.audit.has_ai_chatbot)
        has_pixels = sum(1 for l in scored_leads if bool(l.audit.tech_stack.ad_pixels))
        has_crm = sum(1 for l in scored_leads if bool(l.audit.tech_stack.crm_and_marketing))

        booking_tools = [l.audit.detected_booking_tool for l in scored_leads if l.audit.detected_booking_tool]
        chat_tools = [l.audit.detected_chatbot_name for l in scored_leads if l.audit.detected_chatbot_name]

        top_booking = [item for item, _ in Counter(booking_tools).most_common(3)]
        top_chat = [item for item, _ in Counter(chat_tools).most_common(3)]

        reviews = [l.raw_lead.review_count or 0 for l in scored_leads]
        ratings = [l.raw_lead.rating or 0.0 for l in scored_leads if l.raw_lead.rating]

        return CohortBenchmark(
            geo_query=geo_query,
            total_competitors=total,
            booking_adoption_pct=round((has_booking / total) * 100, 1),
            chat_adoption_pct=round((has_chat / total) * 100, 1),
            pixel_adoption_pct=round((has_pixels / total) * 100, 1),
            crm_adoption_pct=round((has_crm / total) * 100, 1),
            average_reviews=int(sum(reviews) / total) if total > 0 else 0,
            average_rating=round(sum(ratings) / len(ratings), 1) if ratings else 0.0,
            popular_booking_tools=top_booking,
            popular_chatbots=top_chat
        )

    @classmethod
    def generate_competitive_hook(cls, target_lead: Any, cohort: CohortBenchmark) -> Dict[str, str]:
        """Generates peer-comparison sales angles that expose the danger of falling behind local competitors."""
        hooks = {}
        lead_name = target_lead.raw_lead.name

        # 1. Booking Gap Hook
        if not target_lead.audit.has_online_booking and cohort.booking_adoption_pct >= 40:
            tools_str = f" ({', '.join(cohort.popular_booking_tools)})" if cohort.popular_booking_tools else ""
            hooks["booking_peer_comparison"] = (
                f"Out of {cohort.total_competitors} prominent dental practices analyzed across {cohort.geo_query}, "
                f"{int(cohort.booking_adoption_pct)}% now offer direct online scheduling{tools_str}. "
                f"{lead_name} is currently in the {100 - int(cohort.booking_adoption_pct)}% minority still forcing patients "
                f"into daytime telephone tag, leaking evening searchers to nearby competitors."
            )
        else:
            hooks["booking_peer_comparison"] = (
                f"With {cohort.total_competitors} clinics competing in {cohort.geo_query}, frictionless digital intake "
                f"is rapidly becoming the standard for patient acquisition."
            )

        # 2. Chat / Intake Gap Hook
        if not target_lead.audit.has_ai_chatbot and cohort.chat_adoption_pct >= 25:
            hooks["chat_peer_comparison"] = (
                f"{int(cohort.chat_adoption_pct)}% of local practices in {cohort.geo_query} have already deployed 24/7 conversational "
                f"intake to qualify procedure inquiries after 5 PM while your front desk is closed."
            )
        else:
            hooks["chat_peer_comparison"] = (
                f"Deploying 24/7 conversational triage gives {lead_name} an immediate competitive edge over the "
                f"{100 - int(cohort.chat_adoption_pct)}% of {cohort.geo_query} practices that ignore after-hours inquiries."
            )

        return hooks
