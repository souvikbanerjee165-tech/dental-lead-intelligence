import pytest
from models import RawLead, WebsiteAuditResult, ScoredLead
from evidence import Finding, DOMEvidence
from insights import BusinessInsight
from traceability import TraceabilityEngine, DecisionTrace

def test_traceability_engine_provenance():
    dom_ev = DOMEvidence(
        id="EVD-TEST-BOOK",
        selector="a#book",
        element_snippet="No booking widget in navigation",
        confidence=0.96
    )
    finding = Finding(
        id="FIND-BOOKING-ABSENCE",
        category="Patient Experience",
        title="Absence of Direct Online Appointment Booking",
        description="Missing booking",
        evidence=[dom_ev],
        confidence=0.96,
        severity="critical"
    )
    insight = BusinessInsight(
        id="INSIGHT-MANUAL-INTAKE-BOTTLENECK",
        insight_type="operational",
        title="Manual Intake Bottleneck",
        executive_summary="Summary",
        impact_analysis="Impact",
        supporting_finding_ids=["FIND-BOOKING-ABSENCE"]
    )

    lead = ScoredLead(
        raw_lead=RawLead(name="Lone Star Dental", website="https://lonestardental.com", review_count=120),
        audit=WebsiteAuditResult(reachable=True, has_online_booking=False, has_ai_chatbot=False),
        findings=[finding],
        insights=[insight]
    )

    trace = TraceabilityEngine.trace_lead_campaign(lead)
    assert isinstance(trace, DecisionTrace)
    assert trace.lead_name == "Lone Star Dental"
    assert len(trace.nodes) >= 1

    node = trace.nodes[0]
    assert node.finding_id == "FIND-BOOKING-ABSENCE"
    assert node.insight_id == "INSIGHT-MANUAL-INTAKE-BOTTLENECK"
    assert node.evidence_id == "EVD-TEST-BOOK"
    assert node.confidence == 0.96

    summary = trace.summary()
    assert "Decision Trace Audit Log for Lone Star Dental" in summary
    assert "FIND-BOOKING-ABSENCE" in summary
