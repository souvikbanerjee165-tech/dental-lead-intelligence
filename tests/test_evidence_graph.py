import pytest
from evidence import (
    EvidenceGraph, Finding, FindingStatus,
    DOMEvidence, ScriptEvidence, HeaderEvidence, NetworkEvidence, TextEvidence,
    ConfidenceCalculator
)

def test_polymorphic_evidence_creation():
    dom_ev = DOMEvidence(selector="div.hero", element_snippet="Book Today", confidence=0.88)
    script_ev = ScriptEvidence(script_url="https://tag.js", matched_signature="googletagmanager", confidence=0.99)
    header_ev = HeaderEvidence(header_name="Server", header_value="cloudflare", confidence=0.95)
    net_ev = NetworkEvidence(target_url="https://api.drift.com/chat", confidence=0.92)
    text_ev = TextEvidence(matched_phrase="emergency dental", confidence=0.80)

    assert dom_ev.evidence_type == "dom"
    assert script_ev.evidence_type == "script"
    assert header_ev.evidence_type == "header"
    assert net_ev.evidence_type == "network"
    assert text_ev.evidence_type == "text"

def test_evidence_graph_lifecycle():
    graph = EvidenceGraph()

    dom_ev = DOMEvidence(element_snippet="<form>", confidence=0.90)
    graph.add_evidence(dom_ev)
    assert len(graph.evidence) == 1

    finding = Finding(
        id="FIND-1",
        category="Patient Experience",
        title="No Online Booking",
        description="Patients cannot book",
        evidence=[dom_ev],
        confidence=0.92,
        severity="critical",
        status=FindingStatus.VERIFIED,
        recommendation="Install booking widget",
        projected_monthly_roi=1200.0
    )
    graph.add_finding(finding)

    assert len(graph.findings) == 1
    assert graph.get_overall_confidence() == 0.92
    proof_text = finding.explain()
    assert "Finding: No Online Booking" in proof_text
    assert "VERIFIED" in proof_text
    assert "92%" in proof_text
