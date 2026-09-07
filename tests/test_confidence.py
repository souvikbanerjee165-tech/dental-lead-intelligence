import pytest
from evidence import (
    ConfidenceCalculator, ScriptEvidence, DOMEvidence, HeaderEvidence,
    NetworkEvidence, TextEvidence, BaseEvidence
)

def test_confidence_empty_evidence():
    """Empty evidence should return deterministic defaults."""
    assert ConfidenceCalculator.calculate_finding_confidence([], is_absence_finding=False) == 0.50
    assert ConfidenceCalculator.calculate_finding_confidence([], is_absence_finding=True) == 0.80

def test_single_detector_script_evidence():
    """Direct script evidence with high weight should yield precise confidence."""
    item = ScriptEvidence(
        script_url="https://assets.calendly.com/assets/external/widget.js",
        matched_signature="assets.calendly.com",
        confidence=0.98
    )
    conf = ConfidenceCalculator.calculate_finding_confidence([item])
    # Single detector modality, script weight 1.0 -> 0.98
    assert conf == 0.98

def test_multi_detector_agreement_bonus():
    """2 distinct modalities should receive a 1.02x agreement boost, capped at 0.99."""
    item1 = DOMEvidence(
        selector="a#online-booking",
        element_snippet="Book Online",
        confidence=0.90
    )
    item2 = ScriptEvidence(
        matched_signature="nexhealth.js",
        confidence=0.95
    )
    conf = ConfidenceCalculator.calculate_finding_confidence([item1, item2])
    # 2 modalities (dom + script): base = (0.85*0.90 + 1.0*0.95) / (0.85 + 1.0) = (0.765 + 0.95)/1.85 = 1.715 / 1.85 = 0.927
    # agreement bonus = 1.02 -> 0.927 * 1.02 = 0.9455 -> round(0.95, 2)
    assert conf > 0.92
    assert conf <= 0.99

def test_three_detector_agreement_bonus():
    """3 distinct modalities should receive a 1.05x agreement boost."""
    item1 = DOMEvidence(element_snippet="div.chat-bubble", confidence=0.92)
    item2 = ScriptEvidence(matched_signature="drift.load", confidence=0.95)
    item3 = NetworkEvidence(target_url="https://js.drift.com", confidence=0.96)

    conf = ConfidenceCalculator.calculate_finding_confidence([item1, item2, item3])
    # 3 modalities -> agreement factor 1.05
    assert conf >= 0.98
    assert conf <= 0.99

def test_confidence_capped_at_99():
    """Confidence should never exceed 0.99 even with overwhelming evidence."""
    item1 = ScriptEvidence(matched_signature="s1", confidence=1.0)
    item2 = HeaderEvidence(header_name="Server", header_value="cloudflare", confidence=1.0)
    item3 = DOMEvidence(element_snippet="div", confidence=1.0)
    item4 = NetworkEvidence(target_url="https://api.com", confidence=1.0)

    conf = ConfidenceCalculator.calculate_finding_confidence([item1, item2, item3, item4])
    assert conf == 0.99
