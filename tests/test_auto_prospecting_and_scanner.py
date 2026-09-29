"""
Tests for Pillar 1: Auto Prospecting Scheduler & AI Market Scanner.
Verifies:
1. 6:00 AM auto-prospecting scheduler configuration & multi-metro rotation.
2. AI Market Scanner scanning up to 1,000 practices and extracting broken sites, dropped bots, review surges, and new owners.
"""

import os
import pytest
from database import DatabaseManager
from scheduler import AutonomousScheduler
from market_scanner import MarketScanner


@pytest.fixture
def clean_db(tmp_path):
    db_file = tmp_path / "test_pillar1.db"
    return DatabaseManager(db_path=str(db_file))


def test_auto_prospecting_scheduler_configuration():
    """Verifies morning harvester configuration, target metros, and scheduled time."""
    status = AutonomousScheduler.get_morning_harvest_status()
    assert "scheduled_time" in status
    assert status["scheduled_time"] == "06:00"

    # Configure new target metros (Dallas, Chicago, Miami, Houston)
    updated = AutonomousScheduler.configure_morning_harvest(
        enabled=True,
        target_metros=["Dallas, TX", "Chicago, IL", "Miami, FL", "Houston, TX"],
        harvest_time="06:00",
        limit_per_metro=125
    )
    assert updated["enabled"] is True
    assert len(updated["target_metros"]) == 4
    assert updated["total_daily_leads_target"] == 500
    assert updated["status"] == "ARMED_FOR_0600"


def test_ai_market_scanner_signal_detection(clean_db):
    """Verifies bulk market scan across practices and extraction of actionable signals."""
    # Seed representative clinics in Austin
    clean_db.save_lead({
        "id": "scan-clinic-1",
        "name": "Austin Broken Web Dental",
        "address": "101 Congress Ave, Austin, TX",
        "phone": "512-555-0101",
        "website": "https://broken-austin-dentist.com",
        "rating": 4.9,
        "review_count": 140,
        "missed_rev_max": 5800,
        "doctor_name": "Dr. Sarah Jenkins"
    })
    # Seed broken audit for clinic 1
    clean_db.save_audit("scan-clinic-1", {
        "reachable": False,
        "has_ssl": False,
        "has_ai_chatbot": False,
        "has_online_booking": False
    })

    clean_db.save_lead({
        "id": "scan-clinic-2",
        "name": "Downtown High Volume Dental",
        "address": "200 6th St, Austin, TX",
        "phone": "512-555-0202",
        "website": "https://downtownaustindental.com",
        "rating": 4.8,
        "review_count": 220,
        "missed_rev_max": 7200,
        "doctor_name": "Dr. Alan Stone",
        "detected_chatbot_name": None
    })
    clean_db.save_audit("scan-clinic-2", {
        "reachable": True,
        "has_ssl": True,
        "has_ai_chatbot": False,
        "has_online_booking": True
    })

    # Run Market Scan
    scan_result = MarketScanner.scan_metro(db=clean_db, metro="Austin", max_clinics=50)
    assert scan_result["metro"] == "Austin"
    assert scan_result["total_scanned"] >= 2
    assert scan_result["signals_found"] >= 2

    # Check signal types
    signal_types = [s["signal_type"] for s in scan_result["signals"]]
    assert "BROKEN_WEBSITE" in signal_types
    assert "NO_AFTER_HOURS_INTAKE" in signal_types
    assert "REVIEW_SURGE_OPPORTUNITY" in signal_types
    assert "NEW_DECISION_MAKER" in signal_types

    # Verify retrieval from database
    latest_signals = MarketScanner.get_latest_market_signals(clean_db)
    assert len(latest_signals) > 0
    assert latest_signals[0]["metro"] == "Austin"
