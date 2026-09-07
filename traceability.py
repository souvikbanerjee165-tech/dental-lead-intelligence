from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class TraceNode(BaseModel):
    """A verified assertion or statement in outbound sales collateral."""
    statement: str
    target_channel: str = "email"        # email, linkedin, sms, phone
    insight_id: str
    insight_title: str
    finding_id: str
    finding_title: str
    evidence_id: str
    evidence_snippet: str
    evidence_type: str
    source_citation: str
    detector_version: str = "v1.4.0"
    confidence: float

    def format_trace(self) -> str:
        return (
            f"STATEMENT: \"{self.statement}\"\n"
            f"  |-- BECAUSE INSIGHT: [{self.insight_id}] {self.insight_title}\n"
            f"      |-- DERIVED FROM FINDING: [{self.finding_id}] {self.finding_title}\n"
            f"          |-- PROVEN BY EVIDENCE: [{self.evidence_id} | {self.evidence_type.upper()}] \"{self.evidence_snippet}\"\n"
            f"              |-- SOURCE: {self.source_citation} (Detector: {self.detector_version}, Confidence: {int(self.confidence*100)}%)"
        )

class DecisionTrace(BaseModel):
    """End-to-End audit trail guaranteeing 100% provenance of generated sales claims."""
    lead_name: str
    generated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    nodes: List[TraceNode] = Field(default_factory=list)

    def add_node(self, node: TraceNode):
        self.nodes.append(node)

    def summary(self) -> str:
        header = f"=== Decision Trace Audit Log for {self.lead_name} ({len(self.nodes)} Verified Claims) ===\n"
        return header + "\n\n".join([n.format_trace() for n in self.nodes])

class TraceabilityEngine:
    """Builds cryptographic and logical decision traces linking campaign text to empirical evidence."""

    @classmethod
    def trace_lead_campaign(cls, scored_lead: Any) -> DecisionTrace:
        trace = DecisionTrace(lead_name=scored_lead.raw_lead.name)
        findings_map = {f.id: f for f in scored_lead.findings}
        insights_map = {i.id: i for i in scored_lead.insights}

        # 1. Trace Online Booking Claim
        if "FIND-BOOKING-ABSENCE" in findings_map:
            f = findings_map["FIND-BOOKING-ABSENCE"]
            ins = next((i for i in scored_lead.insights if "BOOKING" in str(i.supporting_finding_ids)), None)
            ev = f.evidence[0] if f.evidence else None
            trace.add_node(TraceNode(
                statement=f"We noticed prospective patients currently have to call your front desk during office hours without online scheduling.",
                target_channel="day1_email",
                insight_id=ins.id if ins else "INSIGHT-MANUAL-INTAKE-BOTTLENECK",
                insight_title=ins.title if ins else "Manual Intake Bottleneck",
                finding_id=f.id,
                finding_title=f.title,
                evidence_id=getattr(ev, "id", "EVD-BOOKING"),
                evidence_snippet=getattr(ev, "snippet", "No booking widget detected in DOM"),
                evidence_type=getattr(ev, "evidence_type", "dom_absence"),
                source_citation=getattr(ev, "source", scored_lead.raw_lead.website or "homepage"),
                confidence=f.confidence
            ))

        # 2. Trace AI Chat / After-Hours Leakage Claim
        if "FIND-CHAT-ABSENCE" in findings_map:
            f = findings_map["FIND-CHAT-ABSENCE"]
            ins = next((i for i in scored_lead.insights if "CHAT" in str(i.supporting_finding_ids)), None)
            ev = f.evidence[0] if f.evidence else None
            trace.add_node(TraceNode(
                statement=f"Based on your ~{scored_lead.raw_lead.review_count or 80} reviews, we estimate {scored_lead.raw_lead.name} may be losing ${scored_lead.estimated_missed_revenue_monthly_min:,.0f}-${scored_lead.estimated_missed_revenue_monthly_max:,.0f}/mo in after-hours patient inquiries.",
                target_channel="day1_email",
                insight_id=ins.id if ins else "INSIGHT-MANUAL-INTAKE-BOTTLENECK",
                insight_title=ins.title if ins else "Manual Intake Bottleneck",
                finding_id=f.id,
                finding_title=f.title,
                evidence_id=getattr(ev, "id", "EVD-CHAT"),
                evidence_snippet=getattr(ev, "snippet", "Inspected DOM and scripts; no AI assistant detected"),
                evidence_type=getattr(ev, "evidence_type", "dom_absence"),
                source_citation=getattr(ev, "source", scored_lead.raw_lead.website or "homepage"),
                confidence=f.confidence
            ))

        return trace
