import pytest
from registry import DetectorRegistry, DetectorMetadata

def test_detector_registry_list():
    detectors = DetectorRegistry.list_detectors()
    assert len(detectors) >= 6
    ids = [d.detector_id for d in detectors]
    assert "detector.booking" in ids
    assert "detector.chatbot" in ids
    assert "detector.cms" in ids
    assert "detector.analytics" in ids
    assert "detector.pixels" in ids
    assert "detector.crm" in ids

def test_detector_registry_metadata():
    booking = DetectorRegistry.get_detector("detector.booking")
    assert booking is not None
    assert booking.name == "Online Appointment Scheduling Detector"
    assert booking.version == "1.4.0"
    assert booking.owner == "Core Engineering"
    assert booking.benchmark_sites == 5
    assert booking.benchmark_accuracy_pct == 100.0
    assert len(booking.changelog) >= 3
