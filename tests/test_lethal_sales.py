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
