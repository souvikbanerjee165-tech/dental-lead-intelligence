from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from evidence import Finding

class BusinessInsight(BaseModel):
    """Synthesized business conclusion bridging technical findings to executive revenue reality."""
    id: str
    insight_type: str
    title: str
    executive_summary: str
    impact_analysis: str
    supporting_finding_ids: List[str] = Field(default_factory=list)
    confidence: float = 0.95
    urgency: str = "immediate"  # immediate, near_term, strategic
    projected_annual_loss: float = 0.0
    strategic_recommendation: str = ""

    def summary_card(self) -> str:
        return (
            f"💡 [{self.urgency.upper()}] {self.title}\n"
            f"Summary: {self.executive_summary}\n"
            f"Impact: {self.impact_analysis} (Est. Annual Gap: ${self.projected_annual_loss:,.0f})\n"
            f"Strategic Fix: {self.strategic_recommendation}"
        )

class InsightEngine:
    """Layer 3: Synthesizes granular, technical findings into high-level business insights."""

    @classmethod
    def synthesize_insights(
        cls,
        findings: List[Finding],
        review_count: int = 50,
        rating: float = 4.9,
        has_pixels: bool = False
    ) -> List[BusinessInsight]:
        insights: List[BusinessInsight] = []

        finding_ids = {f.id: f for f in findings}
        no_chat = "FIND-CHAT-ABSENCE" in finding_ids
        no_booking = "FIND-BOOKING-ABSENCE" in finding_ids
        no_crm = "FIND-CRM-ABSENCE" in finding_ids

        # 1. Manual Intake Bottleneck
        if no_booking and no_chat:
            loss = finding_ids["FIND-CHAT-ABSENCE"].projected_monthly_roi * 12 + finding_ids["FIND-BOOKING-ABSENCE"].projected_monthly_roi * 12
            insights.append(BusinessInsight(
                id="INSIGHT-MANUAL-INTAKE-BOTTLENECK",
                insight_type="operational_friction",
                title="100% Reliance on Manual Telephone Intake Creates Severe After-Hours Drop-off",
                executive_summary="The practice currently operates zero digital self-scheduling or conversational intake channels.",
                impact_analysis="Over 42% of local healthcare searches occur after 5 PM. Without 24/7 AI triage or booking, after-hours visitors abandon to nearby practices offering instant booking.",
                supporting_finding_ids=["FIND-CHAT-ABSENCE", "FIND-BOOKING-ABSENCE"],
                confidence=0.98,
                urgency="immediate",
                projected_annual_loss=loss,
                strategic_recommendation="Deploy 24/7 AI Receptionist synchronized with practice management calendar."
            ))

        # 2. Blind Paid Acquisition Spend
        if has_pixels and (no_crm or no_chat):
            insights.append(BusinessInsight(
                id="INSIGHT-BLIND-AD-SPEND",
                insight_type="marketing_leakage",
                title="Advertising Traffic Captured Without Automated Conversion or CRM Attribution",
                executive_summary="Ad pixels (Meta / Google Ads) detected on site, but lead submissions lack automated CRM follow-up and instant chat response.",
                impact_analysis="Paid traffic costs $30–$80 per click in competitive dental markets. Driving paid traffic to a website without instant 24/7 capture burns ad budget with high drop-off.",
                supporting_finding_ids=[f.id for f in findings if "CRM" in f.id or "CHAT" in f.id],
                confidence=0.94,
                urgency="immediate",
                projected_annual_loss=24000.0,
                strategic_recommendation="Install conversational AI triage directly on landing pages and connect lead webhooks to CRM."
            ))

        # 3. Reputation vs. Digital Accessibility Asymmetry
        if review_count >= 100 and rating >= 4.7 and (no_chat or no_booking):
            insights.append(BusinessInsight(
                id="INSIGHT-REPUTATION-ASYMMETRY",
                insight_type="brand_asymmetry",
                title="Premier Clinical Reputation Bottlenecked by Legacy Patient Accessibility",
                executive_summary=f"Stellar public reputation ({rating}★ across {review_count} reviews) compromised by high-friction booking UX.",
                impact_analysis="Word-of-mouth and Google Maps referrals land on the website expecting premier modern service, but encounter 1990s telephone tag friction.",
                supporting_finding_ids=[f.id for f in findings if "ABSENCE" in f.id],
                confidence=0.96,
                urgency="near_term",
                projected_annual_loss=36000.0,
                strategic_recommendation="Modernize digital front door to match clinical excellence with frictionless self-serve scheduling."
            ))

        # Default insight if well optimized
        if not insights:
            insights.append(BusinessInsight(
                id="INSIGHT-OPTIMIZED-FOUNDATION",
                insight_type="optimization",
                title="Modern Patient Intake Foundation in Place",
                executive_summary="Practice features online scheduling and active digital patient communication.",
                impact_analysis="Digital infrastructure is ahead of local peers; focus shifts to conversion rate optimization and recall automation.",
                supporting_finding_ids=[f.id for f in findings if "ACTIVE" in f.id],
                confidence=0.95,
                urgency="strategic",
                projected_annual_loss=0.0,
                strategic_recommendation="Implement advanced AI voice reception for after-hours phone coverage."
            ))

        return insights
