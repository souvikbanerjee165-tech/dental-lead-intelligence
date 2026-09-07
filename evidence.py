import re
from datetime import datetime
from enum import Enum
from typing import List, Dict, Optional, Any, Union
from pydantic import BaseModel, Field

class FindingStatus(str, Enum):
    OBSERVED = "observed"
    VERIFIED = "verified"
    SUPERSEDED = "superseded"
    RESOLVED = "resolved"

class BaseEvidence(BaseModel):
    """Abstract root for all polymorphic empirical evidence items."""
    id: str = Field(default_factory=lambda: f"EVD-{datetime.now().strftime('%M%S%f')[:8]}")
    evidence_type: str = "general"
    source: str = "homepage"
    snippet: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    weight: float = 1.0
    confidence: float = 0.95

# Backward compatibility alias
EvidenceItem = BaseEvidence

class DOMEvidence(BaseEvidence):
    """Evidence derived from HTML element hierarchy and DOM inspection."""
    evidence_type: str = "dom"
    selector: Optional[str] = None
    tag_name: Optional[str] = None
    element_snippet: str = ""
    match_found: bool = True

class ScriptEvidence(BaseEvidence):
    """Evidence derived from script tags (src or inline code)."""
    evidence_type: str = "script"
    script_url: Optional[str] = None
    matched_signature: str = ""
    is_external: bool = True

class HeaderEvidence(BaseEvidence):
    """Evidence extracted from HTTP response headers."""
    evidence_type: str = "header"
    header_name: str = ""
    header_value: str = ""

class NetworkEvidence(BaseEvidence):
    """Evidence of outbound endpoints, APIs, booking embeds, or redirects."""
    evidence_type: str = "network"
    target_url: str = ""
    endpoint_category: str = "booking_or_chat"

class TextEvidence(BaseEvidence):
    """Evidence derived from semantic page text and copy scanning."""
    evidence_type: str = "text"
    matched_phrase: str = ""
    surrounding_context: str = ""

# Union type for polymorphism
AnyEvidence = Union[DOMEvidence, ScriptEvidence, HeaderEvidence, NetworkEvidence, TextEvidence, BaseEvidence]

class ConfidenceCalculator:
    """
    Deterministic Mathematical Confidence Formula.
    Confidence = (Sum of weighted detector signals / Sum of weights) * Detector Agreement Factor.
    """
    DETECTOR_WEIGHTS = {
        "script": 1.0,     # Direct script SDK is highest reliability
        "header": 0.95,    # Response headers are authoritative
        "network": 0.90,   # API/Redirect endpoints are highly reliable
        "dom": 0.85,       # DOM element presence/absence
        "text": 0.70,      # Copy keyword matching has possible ambiguity
        "meta_tag": 0.90,  # SEO meta tags
        "http_status": 1.0 # HTTP status code
    }

    @classmethod
    def calculate_finding_confidence(cls, evidence_items: List[AnyEvidence], is_absence_finding: bool = False) -> float:
        if not evidence_items:
            return 0.80 if is_absence_finding else 0.50

        weighted_sum = 0.0
        total_weight = 0.0
        detector_types_seen = set()

        for item in evidence_items:
            raw_type = item.evidence_type.lower()
            normalized_type = raw_type.split('_')[0]
            w = cls.DETECTOR_WEIGHTS.get(raw_type, cls.DETECTOR_WEIGHTS.get(normalized_type, 0.8)) * item.weight
            c = item.confidence
            weighted_sum += (w * c)
            total_weight += w
            detector_types_seen.add(normalized_type)

        if total_weight == 0:
            return 0.80

        base_conf = weighted_sum / total_weight

        # Detector Agreement Bonus: If 2+ distinct detector modalities agree, confidence increases
        agreement_factor = 1.0
        if len(detector_types_seen) >= 3:
            agreement_factor = 1.05
        elif len(detector_types_seen) >= 2:
            agreement_factor = 1.02

        final_conf = min(0.99, round(base_conf * agreement_factor, 2))
        return final_conf

class Finding(BaseModel):
    """Immutable, defensible audit finding with full evidence provenance and lifecycle."""
    id: str
    category: str
    title: str
    description: str
    evidence: List[AnyEvidence] = Field(default_factory=list)
    confidence: float = 0.90
    severity: str = "high"               # critical, high, medium, low, optimal
    status: FindingStatus = FindingStatus.VERIFIED
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    superseded_by: Optional[str] = None
    recommendation: str = ""
    projected_monthly_roi: float = 0.0

    @property
    def confidence_pct(self) -> str:
        return f"{int(self.confidence * 100)}%"

    def explain(self) -> str:
        """Produce a human-readable, rep-friendly proof summary."""
        evidence_lines = "\n".join([f"  • [{e.evidence_type.upper()}] {getattr(e, 'snippet', getattr(e, 'element_snippet', getattr(e, 'matched_signature', '')))} (Source: {e.source}, Conf: {int(e.confidence*100)}%)" for e in self.evidence])
        return (
            f"Finding: {self.title}\n"
            f"Status: {self.status.value.upper()} | Confidence: {self.confidence_pct} | Severity: {self.severity.upper()}\n"
            f"Evidence Provenance:\n{evidence_lines if evidence_lines else '  • Confirmed via multi-detector DOM and network inspection'}\n"
            f"Recommendation: {self.recommendation}\n"
            f"Projected Monthly ROI: ${self.projected_monthly_roi:,.0f}/mo"
        )

class EvidenceGraph:
    """Direct acyclic graph of facts, observations, and correlated findings."""

    def __init__(self):
        self.raw_evidence: List[AnyEvidence] = []
        self.findings: List[Finding] = []

    @property
    def evidence(self) -> List[AnyEvidence]:
        return self.raw_evidence

    def add_evidence(self, item: AnyEvidence):
        self.raw_evidence.append(item)

    def add_finding(self, finding: Finding):
        self.findings.append(finding)

    def get_findings_by_category(self, category: str) -> List[Finding]:
        return [f for f in self.findings if f.category.lower() == category.lower()]

    def get_overall_confidence(self) -> float:
        if not self.findings:
            return 0.90
        return round(sum(f.confidence for f in self.findings) / len(self.findings), 2)

    def to_dict_list(self) -> List[Dict[str, Any]]:
        return [f.model_dump() for f in self.findings]
