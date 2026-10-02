"""
Unit and Integration Tests for Lethal Sales Weapons:
1. Executive Practice Teardown Pitch Portal (/pitch/{lead_id})
2. "Voicemail Sting" Auditory Proof Generator (PCM telecom tones + AI teardown)
3. Local Competitor "Patient Steal" Radar (proximity scan & FOMO hooks)
4. 1-Click SMS & WhatsApp Dispatcher (native deep-links & view telemetry)
5. FastAPI Endpoints Integration
"""

import os
import wave
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app import app
from database import DatabaseManager
from pitch_portal import PitchPortalEngine
from voicemail_sting import VoicemailStingGenerator, _generate_telecom_tones_pcm
from competitor_radar import CompetitorRadarEngine
from sms_dispatcher import SMSDispatcherEngine
from live_intercept import LiveInterceptRadar
from territory_checkout import TerritoryCheckoutEngine
from video_teardown import VideoTeardownEngine
from hygiene_recall_calculator import HygieneRecallCalculator
from overnight_autopilot import OvernightAutopilot


@pytest.fixture
def test_client():
    return TestClient(app)


@pytest.fixture
def db():
    return DatabaseManager()


@pytest.fixture
def sample_lead(db):
    lead_id = "lead_test_lethal_vance"
    lead = {
        "id": lead_id,
        "name": "Barton Springs Dental Studio",
        "doctor_name": "Dr. Marcus Vance",
        "phone": "+1 (512) 555-4321",
        "address": "2200 S Lamar Blvd, Austin, TX 78704",
        "website": "https://bartonspringsdental.com",
        "rating": 4.8,
        "review_count": 142,
        "opportunity_score": 88,
        "missed_rev_min": 3500,
        "missed_rev_max": 7200,
        "detected_ehr": "Dentrix",
        "npi_number": "1942083115"
    }
    db.save_lead(lead)
    return db.get_lead(lead_id)


# -------------------------------------------------------------
# 1. Pitch Portal Engine Tests
# -------------------------------------------------------------

def test_pitch_portal_engine_renders_valid_html(sample_lead):
    html = PitchPortalEngine.render_pitch_page_html(sample_lead)
    assert "<!DOCTYPE html>" in html
    assert "Barton Springs Dental Studio" in html
    assert "Dr. Marcus Vance" in html
    assert "$1,500" in html
    assert "$399" in html
    assert "Dental Practice Intelligence Audit" in html
    assert "/api/pitch/" in html  # Tracking beacon included
    assert "simulator" in html.lower()


def test_pitch_portal_handles_fallback_gracefully():
    fallback_lead = {"name": "Solo Clinic"}
    html = PitchPortalEngine.render_pitch_page_html(fallback_lead)
    assert "<!DOCTYPE html>" in html
    assert "Solo Clinic" in html
    assert "$1,500" in html


# -------------------------------------------------------------
# 2. Voicemail Sting Auditory Proof Tests
# -------------------------------------------------------------

def test_telecom_tones_pcm_generation():
    pcm_bytes = _generate_telecom_tones_pcm(sample_rate=24000)
    assert len(pcm_bytes) > 0
    # Must be 16-bit mono PCM (multiples of 2 bytes)
    assert len(pcm_bytes) % 2 == 0
    # ~3.5s of audio at 24000 samples/sec * 2 bytes/sample ~ 160,000 bytes
    duration_approx = len(pcm_bytes) / (24000 * 2)
    assert 3.0 <= duration_approx <= 5.0


def test_voicemail_sting_generates_valid_wav(sample_lead):
    result = VoicemailStingGenerator.generate_voicemail_sting(
        lead_dict=sample_lead,
        voice_engine="auto-fast",
        voice_name="af_sarah"
    )
    assert result["status"] == "READY"
    assert result["lead_id"] == sample_lead["id"]
    assert "Dr. Marcus Vance" in result["doctor_name"]
    assert result["duration_sec"] > 2.0
    assert result["audio_url"].endswith(".wav")
    assert "/output/stings/" in result["audio_url"]

    # Verify physical file existence and valid WAV header
    wav_path = Path("output") / "stings" / f"sting_{sample_lead['id']}.wav"
    assert wav_path.exists()
    assert wav_path.stat().st_size > 1000

    with wave.open(str(wav_path), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() > 0
        assert wf.getnframes() > 0


# -------------------------------------------------------------
# 3. Local Competitor "Patient Steal" Radar Tests
# -------------------------------------------------------------

def test_competitor_radar_scans_and_finds_threats(sample_lead, db):
    # Insert competitor in same city
    competitor = {
        "id": "lead_test_competitor_soco",
        "name": "Austin South Congress Smile Center",
        "phone": "+1 (512) 555-9988",
        "address": "1400 S Congress Ave, Austin, TX 78704",
        "rating": 4.9,
        "review_count": 310,
        "opportunity_score": 70
    }
    db.save_lead(competitor)

    radar = CompetitorRadarEngine.scan_competitors(sample_lead, db=db)
    assert radar["lead_id"] == sample_lead["id"]
    assert radar["competitors_analyzed_count"] >= 1
    assert radar["primary_threat"] is not None
    assert "sales_fomo_quote" in radar
    assert "sunday" in radar["sales_fomo_quote"].lower() or "after-hours" in radar["sales_fomo_quote"].lower()
    assert len(radar["competitors"]) >= 1


# -------------------------------------------------------------
# 4. 1-Click SMS & WhatsApp Dispatcher Tests
# -------------------------------------------------------------

def test_sms_dispatcher_payload_and_deep_links(sample_lead):
    payload = SMSDispatcherEngine.generate_dispatch_payload(
        sample_lead,
        base_app_url="http://127.0.0.1:8000"
    )
    assert payload["lead_id"] == sample_lead["id"]
    assert "Dr. Marcus Vance" in payload["doctor_name"]
    assert payload["pitch_url"].startswith("http://127.0.0.1:8000/pitch/")
    assert payload["native_sms_url"].startswith("sms:")
    assert payload["whatsapp_url"].startswith("https://wa.me/")
    assert "weekend toothache" in payload["sms_text"]


def test_sms_dispatcher_records_touch_and_timeline(sample_lead, db):
    lead_id = sample_lead["id"]
    
    # Record SMS dispatch
    ok_sms = SMSDispatcherEngine.record_dispatch(lead_id=lead_id, channel="SMS", db=db)
    assert ok_sms is True

    # Record WhatsApp dispatch
    ok_wa = SMSDispatcherEngine.record_dispatch(lead_id=lead_id, channel="WHATSAPP", db=db)
    assert ok_wa is True

    # Record Pitch View
    ok_view = SMSDispatcherEngine.record_pitch_view(lead_id=lead_id, db=db)
    assert ok_view["status"] == "success"
    assert ok_view["lead_id"] == lead_id

    # Verify event appears in timeline
    events = db.get_lead_timeline(lead_id)
    event_types = [e["event_type"] for e in events]
    assert "DISPATCH_SENT" in event_types
    assert "PITCH_VIEWED" in event_types


# -------------------------------------------------------------
# 5. FastAPI Endpoints Integration Tests
# -------------------------------------------------------------

def test_get_executive_pitch_portal_endpoint(test_client, sample_lead):
    resp = test_client.get(f"/pitch/{sample_lead['id']}")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Barton Springs Dental Studio" in resp.text
    assert "$1,500" in resp.text


def test_post_pitch_portal_viewed_endpoint(test_client, sample_lead):
    resp = test_client.post(f"/api/pitch/{sample_lead['id']}/viewed")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["lead_id"] == sample_lead["id"]


def test_get_lead_voicemail_sting_endpoint(test_client, sample_lead):
    resp = test_client.get(f"/api/leads/{sample_lead['id']}/voicemail-sting")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "READY"
    assert "audio_url" in data
    assert data["duration_sec"] > 0


def test_get_lead_competitor_radar_endpoint(test_client, sample_lead):
    resp = test_client.get(f"/api/leads/{sample_lead['id']}/competitor-radar")
    assert resp.status_code == 200
    data = resp.json()
    assert data["lead_id"] == sample_lead["id"]
    assert "competitors" in data
    assert "sales_fomo_quote" in data


def test_get_lead_sms_dispatch_endpoint(test_client, sample_lead):
    resp = test_client.get(f"/api/leads/{sample_lead['id']}/sms-dispatch")
    assert resp.status_code == 200
    data = resp.json()
    assert data["lead_id"] == sample_lead["id"]
    assert data["native_sms_url"].startswith("sms:")
    assert data["whatsapp_url"].startswith("https://wa.me/")


def test_post_sms_dispatch_record_endpoint(test_client, sample_lead):
    resp = test_client.post(
        f"/api/leads/{sample_lead['id']}/sms-dispatch/record",
        json={"channel": "SMS"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["channel"] == "SMS"


# -------------------------------------------------------------
# 6. Live Radar Intercept Tests (Weapon 1)
# -------------------------------------------------------------

def test_live_intercept_radar_records_and_retrieves_viewers(sample_lead, db):
    # Record view
    record = LiveInterceptRadar.record_view(
        lead_id=sample_lead["id"],
        client_ip="192.168.1.100",
        user_agent="Mozilla/5.0 Test",
        db=db
    )
    assert record["lead_id"] == sample_lead["id"]
    assert "Dr. Marcus Vance" in record["doctor_name"]
    assert "recommended_hook" in record

    # Retrieve active viewers
    viewers = LiveInterceptRadar.get_active_viewers(ttl_seconds=90)
    assert len(viewers) >= 1
    found = [v for v in viewers if v["id"] == sample_lead["id"]]
    assert len(found) == 1
    top = found[0]
    assert top["id"] == sample_lead["id"]
    assert top["phone"] == sample_lead["phone"]

    # Dismiss viewer
    dismissed = LiveInterceptRadar.dismiss_viewer(sample_lead["id"])
    assert dismissed is True
    viewers_after = LiveInterceptRadar.get_active_viewers(ttl_seconds=90)
    assert sample_lead["id"] not in [v["id"] for v in viewers_after]


# -------------------------------------------------------------
# 7. Deposit Lock & 3-Mile Territory Exclusivity Tests (Weapon 2)
# -------------------------------------------------------------

def test_territory_availability_and_deposit_lock(sample_lead, db):
    # Check territory initially available
    avail = TerritoryCheckoutEngine.check_territory_availability(sample_lead, db=db)
    assert avail["is_available"] is True
    assert avail["radius_miles"] == 3.0

    # Create checkout payload
    payload = TerritoryCheckoutEngine.create_checkout_payload(sample_lead)
    assert payload["setup_fee_usd"] == 1500.0
    assert payload["monthly_fee_usd"] == 399.0
    assert "Single-Patient Break-Even Guarantee" in payload["break_even_guarantee_text"]

    # Lock territory deposit
    result = TerritoryCheckoutEngine.complete_deposit_lock(
        lead_id=sample_lead["id"],
        payment_ref="card_test_tok_9988",
        db=db
    )
    assert result["status"] == "LOCKED"
    assert result["setup_deposit_usd"] == 1500.0
    assert result["monthly_maintenance_usd"] == 399.0
    assert result["stage"] == "WON"

    # Verify updated database record
    updated = db.get_lead(sample_lead["id"])
    assert updated["territory_locked"] == 1
    assert updated["deposit_paid"] >= 1500.0
    assert updated["stage"] == "WON"

    # Verify formal digital SLA agreement HTML
    sla_html = TerritoryCheckoutEngine.render_digital_sla_html(sample_lead)
    assert "<!DOCTYPE html>" in sla_html
    assert "Barton Springs Dental Studio" in sla_html
    assert "$1,500" in sla_html
    assert "$399" in sla_html
    assert "Single-Patient Break-Even" in sla_html


# -------------------------------------------------------------
# 8. AI Video Teardown Generator & Player Tests (Weapon 3)
# -------------------------------------------------------------

def test_video_teardown_metadata_and_cinema_player(sample_lead):
    meta = VideoTeardownEngine.generate_video_metadata(sample_lead)
    assert meta["lead_id"] == sample_lead["id"]
    assert "Barton Springs Dental Studio" in meta["clinic_name"]
    assert meta["video_url"].endswith(f"/video/{sample_lead['id']}")
    assert meta["duration_sec"] > 0
    assert "60s Video Teardown" in meta["teaser_text"]

    html = VideoTeardownEngine.render_video_player_page_html(sample_lead)
    assert "<!DOCTYPE html>" in html
    assert "Barton Springs Dental Studio" in html
    assert "$1,500" in html
    assert "/pitch/" in html
    assert "/agreement/" in html


# -------------------------------------------------------------
# 9. Dormant Hygiene Recall Calculator Tests (Weapon 4)
# -------------------------------------------------------------

def test_dormant_hygiene_recall_calculator(sample_lead):
    metrics = HygieneRecallCalculator.calculate_hygiene_leakage(sample_lead)
    assert metrics["lead_id"] == sample_lead["id"]
    assert metrics["dormant_hygiene_charts"] > 0
    assert metrics["trapped_chart_value"] > 0
    assert metrics["month1_cash_injection"] > 10000
    assert metrics["setup_fee_usd"] == 1500.0
    assert metrics["month1_roi_multiplier"] > 5.0
    assert len(metrics["broadcast_scripts"]) == 3
    assert "Dr. Marcus Vance" in metrics["sales_pitch_quote"]


# -------------------------------------------------------------
# 10. FastAPI New Endpoints Integration Tests
# -------------------------------------------------------------

def test_fastapi_live_radar_endpoints(test_client, sample_lead):
    # View pitch to trigger radar
    view_resp = test_client.post(f"/api/pitch/{sample_lead['id']}/viewed")
    assert view_resp.status_code == 200

    # Get active viewers
    radar_resp = test_client.get("/api/radar/active-viewers")
    assert radar_resp.status_code == 200
    radar_data = radar_resp.json()
    assert isinstance(radar_data, list)
    assert len(radar_data) >= 1
    assert any(v["lead_id"] == sample_lead["id"] for v in radar_data)

    # Dismiss viewer
    dismiss_resp = test_client.post(f"/api/radar/dismiss/{sample_lead['id']}")
    assert dismiss_resp.status_code == 200


def test_fastapi_territory_and_agreement_endpoints(test_client, sample_lead):
    # Territory status
    status_resp = test_client.get(f"/api/leads/{sample_lead['id']}/territory-status")
    assert status_resp.status_code == 200
    assert "is_locked" in status_resp.json()

    # Checkout intent
    intent_resp = test_client.get(f"/api/leads/{sample_lead['id']}/checkout-intent")
    assert intent_resp.status_code == 200
    intent_data = intent_resp.json()
    assert intent_data["setup_fee_usd"] == 1500.0

    # Digital SLA Agreement page
    sla_resp = test_client.get(f"/agreement/{sample_lead['id']}")
    assert sla_resp.status_code == 200
    assert "text/html" in sla_resp.headers["content-type"]
    assert "Barton Springs Dental Studio" in sla_resp.text
    assert "$1,500" in sla_resp.text

    # Lock deposit
    lock_resp = test_client.post(
        f"/api/leads/{sample_lead['id']}/checkout/lock-deposit",
        json={"payment_ref": "stripe_ch_integration_test"}
    )
    assert lock_resp.status_code == 200
    lock_data = lock_resp.json()
    assert lock_data["status"] == "LOCKED"


def test_fastapi_video_and_hygiene_endpoints(test_client, sample_lead):
    # Video teardown metadata
    video_meta_resp = test_client.get(f"/api/leads/{sample_lead['id']}/video-teardown")
    assert video_meta_resp.status_code == 200
    video_meta = video_meta_resp.json()
    assert video_meta["lead_id"] == sample_lead["id"]
    assert "teaser_sms" in video_meta

    # Full cinema video player page
    video_page_resp = test_client.get(f"/video/{sample_lead['id']}")
    assert video_page_resp.status_code == 200
    assert "text/html" in video_page_resp.headers["content-type"]
    assert "Barton Springs Dental Studio" in video_page_resp.text

    # Dormant hygiene recall metrics
    hygiene_resp = test_client.get(f"/api/leads/{sample_lead['id']}/hygiene-recall")
    assert hygiene_resp.status_code == 200
    hygiene_data = hygiene_resp.json()
    assert hygiene_data["dormant_charts_count"] > 0
    assert hygiene_data["projected_month1_cash"] > 10000
    assert hygiene_data["month1_roi_multiple"] > 5.0


# -------------------------------------------------------------
# 11. Overnight Autopilot & State Checkpointing Tests
# -------------------------------------------------------------

def test_overnight_autopilot_state_and_persistence():
    # Reset to known clean state
    state = OvernightAutopilot.reset_state()
    assert state["status"] == "IDLE"
    assert "target_metros" in state
    assert len(state["target_metros"]) > 0

    # Test status retrieval
    status = OvernightAutopilot.get_status()
    assert status["status"] == "IDLE"
    assert status["leads_discovered_tonight"] == 0

    # Stop safety test
    stopped = OvernightAutopilot.stop()
    assert stopped["status"] == "PAUSED"


def test_fastapi_autopilot_endpoints(test_client):
    # GET status
    status_resp = test_client.get("/api/autopilot/status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert "status" in status_data
    assert "target_metros" in status_data

    # POST stop
    stop_resp = test_client.post("/api/autopilot/stop")
    assert stop_resp.status_code == 200
    assert stop_resp.json()["status"] == "PAUSED"

    # POST reset
    reset_resp = test_client.post("/api/autopilot/reset")
    assert reset_resp.status_code == 200
    assert reset_resp.json()["status"] == "IDLE"


