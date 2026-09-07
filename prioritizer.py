from __future__ import annotations
from enum import Enum
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from pydantic import BaseModel

if TYPE_CHECKING:
    from models import RawLead, WebsiteAuditResult, DigitalMaturityScore

class DealPriorityTier(str, Enum):
    TIER_1_CALL_TODAY = "TIER 1 (Call Today)"
    TIER_2_CALL_THIS_WEEK = "TIER 2 (Call This Week)"
    TIER_3_NURTURE = "TIER 3 (Nurture)"
    TIER_4_SKIP = "TIER 4 (Skip)"

class ScoreAttributionItem(BaseModel):
    factor: str
    points: int
    rationale: str

class DealPrioritizationResult(BaseModel):
    """Actionable sales prioritization metrics and tier assignment."""
    priority_score: int                 # 0 - 100
    tier: DealPriorityTier
    ranking_rationale: str
    icp_fit_score: int                 # 0 - 100
    revenue_opportunity_score: int     # 0 - 100
    maturity_gap_score: int            # 0 - 100
    buying_signals_score: int          # 0 - 100
    score_attribution: List[ScoreAttributionItem] = []

    def attribution_ledger(self) -> str:
        lines = [f"Priority {self.priority_score}/100 ({self.tier.value}) because:"]
        for item in self.score_attribution:
            sign = "+" if item.points >= 0 else ""
            lines.append(f"  {sign}{item.points:>2} pts | {item.factor:<25} ({item.rationale})")
        return "\n".join(lines)

class DealPrioritizationEngine:
    """Layer 4: Decision Engine - Prioritizes leads based on ICP fit, revenue leakage, and buying signals."""

    @classmethod
    def evaluate_deal(
        cls,
        raw_lead: RawLead,
        audit: WebsiteAuditResult,
        maturity: DigitalMaturityScore,
        estimated_monthly_loss: int
    ) -> DealPrioritizationResult:
        attribution: List[ScoreAttributionItem] = []

        # 1. ICP Fit (0-100): High reviews, confirmed medical/dental category, valid phone & address
        icp = 50
        if raw_lead.category and any(w in raw_lead.category.lower() for w in ["dent", "ortho", "surgery", "clinic"]):
            icp += 20
            attribution.append(ScoreAttributionItem(factor="Verified Healthcare ICP", points=15, rationale=f"Matches target specialty: {raw_lead.category}"))
        
        if raw_lead.review_count and raw_lead.review_count >= 100:
            icp += 20
            attribution.append(ScoreAttributionItem(factor="High Patient Volume", points=20, rationale=f"Strong patient base with {raw_lead.review_count} reviews"))
        elif raw_lead.review_count and raw_lead.review_count >= 50:
            icp += 20
            attribution.append(ScoreAttributionItem(factor="Established Patient Base", points=15, rationale=f"{raw_lead.review_count} patient reviews"))
        elif raw_lead.review_count and raw_lead.review_count >= 20:
            icp += 10
            attribution.append(ScoreAttributionItem(factor="Emerging Practice", points=10, rationale=f"{raw_lead.review_count} patient reviews"))
        
        if raw_lead.phone:
            icp += 10
        icp_score = min(100, icp)

        # 2. Revenue Opportunity Score (0-100): Proportional to monthly leakage size
        rev_score = min(100, int((estimated_monthly_loss / 7000.0) * 100))
        if not audit.has_online_booking:
            attribution.append(ScoreAttributionItem(factor="Missing Online Booking", points=18, rationale="Forces prospective patients into daytime phone tag"))
        if not audit.has_ai_chatbot:
            attribution.append(ScoreAttributionItem(factor="Missing 24/7 AI Triage", points=14, rationale="Zero conversational assistant for after-hours inquiries"))
        if estimated_monthly_loss >= 4000:
            attribution.append(ScoreAttributionItem(factor="Significant Financial Gap", points=12, rationale=f"Est. ${estimated_monthly_loss:,.0f}/mo after-hours leakage"))

        # 3. Digital Maturity Gap (0-100): High traffic + Low automation = High willingness to buy
        gap_score = max(0, min(100, 100 - maturity.automation_score))
        if maturity.automation_score <= 20:
            attribution.append(ScoreAttributionItem(factor="Manual Intake Bottleneck", points=10, rationale="Complete reliance on telephone & reception desk"))

        # 4. Buying Signals Score (0-100):
        signals = 20
        if audit.tech_stack.ad_pixels:
            signals += 40  # Already investing in customer acquisition
            attribution.append(ScoreAttributionItem(factor="Active Paid Advertising", points=14, rationale="Meta/Google Ads pixels detected (existing marketing budget)"))
        if audit.tech_stack.analytics:
            signals += 20
        if raw_lead.rating and raw_lead.rating >= 4.7:
            signals += 20
            attribution.append(ScoreAttributionItem(factor="Stellar Reputation", points=10, rationale=f"Premier clinical rating of {raw_lead.rating} stars"))
        signals_score = min(100, signals)

        # Composite Mathematical Priority Score
        composite = (
            0.30 * icp_score +
            0.35 * rev_score +
            0.20 * gap_score +
            0.15 * signals_score
        )
        final_priority = min(100, int(composite))

        # Assign Tier
        if final_priority >= 75 and estimated_monthly_loss >= 3000:
            tier = DealPriorityTier.TIER_1_CALL_TODAY
            rationale = f"Top-tier prospect: High patient volume with ~${estimated_monthly_loss:,.0f}/mo after-hours leakage and zero 24/7 AI intake."
        elif final_priority >= 60:
            tier = DealPriorityTier.TIER_2_CALL_THIS_WEEK
            rationale = f"Strong prospect: Solid patient reputation ({raw_lead.review_count or 0} reviews) with clear automation gaps."
        elif final_priority >= 40:
            tier = DealPriorityTier.TIER_3_NURTURE
            rationale = "Moderate opportunity: Suitable for automated email sequence before live SDR phone outreach."
        else:
            tier = DealPriorityTier.TIER_4_SKIP
            rationale = "Low fit: Either already equipped with modern intake or lacks patient volume."

        return DealPrioritizationResult(
            priority_score=final_priority,
            tier=tier,
            ranking_rationale=rationale,
            icp_fit_score=icp_score,
            revenue_opportunity_score=rev_score,
            maturity_gap_score=gap_score,
            buying_signals_score=signals_score,
            score_attribution=attribution
        )
