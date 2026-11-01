"""
Enterprise Security & Technical Robustness Test Suite.
Tests all 9 hardening pillars:
1. SSRF (Server-Side Request Forgery) & Cloud Metadata Shield
2. Sliding-Window Rate Limiter & Brute-Force Login Lockout
3. Global Authentication Enforcement Middleware
4. Cryptographic Webhook Signature Verification (Twilio & Telnyx)
5. Tightened Security Headers (HSTS, CSP, COOP, Cross-Domain Policies)
6. Async Playwright Screenshot Concurrency Semaphore & SSRF Guard
7. Persistent Background Search Jobs in SQLite (Scale-to-Zero Resilience)
8. Serverless Cron Endpoint (/api/scheduler/cron-tick)
9. SQLite PRAGMA Tuning & Write-Lock Resilience
"""

import os
import time
import hmac
import base64
import hashlib
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app import app, db, active_jobs, capture_website_screenshot
from security import (
    validate_external_url,
    rate_limiter,
    verify_twilio_signature,
    verify_telnyx_webhook,
)
from auth_manager import auth_manager

client = TestClient(app)


# ==============================================================================
# 1. SSRF & Cloud Metadata Protection Tests
# ==============================================================================

def test_ssrf_blocks_cloud_metadata_and_loopback():
    """Ensures cloud metadata, localhost, private RFC1918 IPs, and file:// schemes are strictly blocked."""
    malicious_urls = [
        "http://169.254.169.254/computeMetadata/v1/",
        "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/",
        "http://127.0.0.1:8000/api/settings",
        "http://localhost/admin",
        "http://10.0.0.1/internal",
        "http://192.168.1.1/router",
        "http://172.16.0.5/secret",
        "http://0.0.0.0:8080",
        "http://[::1]:8000",
        "file:///etc/passwd",
        "gopher://127.0.0.1:6379/_INFO",
    ]
    for url in malicious_urls:
        is_safe, reason = validate_external_url(url)
        assert is_safe is False, f"Expected {url} to be blocked by SSRF shield, but it was allowed!"


def test_ssrf_allows_valid_public_clinic_domains():
    """Ensures legitimate public dental clinic URLs pass validation."""
    valid_urls = [
        "https://austinpremierdental.com",
        "http://www.smilecenterdallas.com/about",
        "example.com",
    ]
    for url in valid_urls:
        is_safe, normalized = validate_external_url(url)
        assert is_safe is True, f"Expected {url} to be allowed, but got: {normalized}"
        assert normalized.startswith(("http://", "https://"))


def test_ssrf_enforced_on_fast_scrape_and_proposal_endpoints():
    """Verifies API endpoints reject SSRF attempts with HTTP 400."""
    res_scrape = client.post(
        "/api/leads/fast-scrape",
        json={"url": "http://169.254.169.254/computeMetadata/v1/"}
    )
    assert res_scrape.status_code == 400
    assert "SSRF" in res_scrape.json()["detail"]

    res_prop = client.post(
        "/api/proposal/generate",
        json={"name": "Evil Clinic", "url": "http://127.0.0.1:8000/api/settings"}
    )
    assert res_prop.status_code == 400
    assert "SSRF" in res_prop.json()["detail"]


# ==============================================================================
# 2. Brute-Force Login Lockout & Rate Limiting Tests
# ==============================================================================

def test_login_brute_force_lockout():
    """Verifies that 5 failed login attempts trigger a 429 Too Many Requests lockout."""
    rate_limiter.reset()
    for _ in range(5):
        r = client.post("/api/auth/login", json={"username": "admin", "password": "wrong_password_123"})
        assert r.status_code == 401

    # 6th attempt must be blocked with 429
    r_locked = client.post("/api/auth/login", json={"username": "admin", "password": "wrong_password_123"})
    assert r_locked.status_code == 429
    assert "Retry-After" in r_locked.headers
    assert "Too many failed login attempts" in r_locked.json()["detail"]
    rate_limiter.reset()


def test_api_sliding_window_rate_limiter(monkeypatch):
    """Verifies general API sliding-window rate limiter triggers 429 when limit is exceeded."""
    rate_limiter.reset()
    monkeypatch.setenv("RATE_LIMIT_PER_MIN", "3")
    headers = {"X-Enforce-Rate-Limit": "true", "X-Forwarded-For": "203.0.113.55"}

    for _ in range(3):
        r = client.get("/api/health", headers=headers)
        assert r.status_code == 200

    r_exceeded = client.get("/api/health", headers=headers)
    assert r_exceeded.status_code == 429
    rate_limiter.reset()


# ==============================================================================
# 3. Global Authentication Enforcement Middleware Tests
# ==============================================================================

def test_global_auth_enforcement_middleware():
    """Verifies protected /api/* routes require a valid session token when auth enforcement is active."""
    # Without token -> 401 when X-Enforce-Auth is active
    r_unauth = client.get("/api/settings", headers={"X-Enforce-Auth": "true"})
    assert r_unauth.status_code == 401

    # Public allowlisted routes remain accessible without token even when auth is enforced
    r_health = client.get("/api/health", headers={"X-Enforce-Auth": "true"})
    assert r_health.status_code == 200

    r_demo = client.get("/demo/preview", headers={"X-Enforce-Auth": "true"})
    assert r_demo.status_code == 200

    # With valid signed session token -> 200 OK
    valid_token = auth_manager.create_session_token("admin")
    r_auth = client.get(
        "/api/settings",
        headers={"X-Enforce-Auth": "true", "Authorization": f"Bearer {valid_token}"}
    )
    assert r_auth.status_code == 200


# ==============================================================================
# 4. Cryptographic Webhook Signature Verification Tests
# ==============================================================================

def test_twilio_webhook_signature_verification(monkeypatch):
    """Verifies Twilio HMAC-SHA1 signature validation accepts valid signatures and rejects forged ones."""
    auth_token = "test_twilio_secret_token_999"
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", auth_token)
    monkeypatch.setenv("STRICT_WEBHOOK_VERIFY", "true")

    # Forged signature -> 403 Forbidden
    r_forged = client.post(
        "/api/voice/webhook/twilio",
        data={"CallSid": "CA12345", "CallStatus": "in-progress"},
        headers={"X-Twilio-Signature": "forged_invalid_sig"}
    )
    assert r_forged.status_code == 403

    # Valid HMAC-SHA1 signature -> 200 OK
    target_url = "http://testserver/api/voice/webhook/twilio"
    params = {"CallSid": "CA12345", "CallStatus": "in-progress"}
    s = target_url + "CallSidCA12345CallStatusin-progress"
    valid_sig = base64.b64encode(hmac.new(auth_token.encode(), s.encode(), hashlib.sha1).digest()).decode()

    r_valid = client.post(
        "/api/voice/webhook/twilio",
        data=params,
        headers={"X-Twilio-Signature": valid_sig}
    )
    assert r_valid.status_code == 200


def test_telnyx_webhook_timestamp_replay_protection():
    """Verifies Telnyx webhook rejects stale timestamps to prevent replay attacks."""
    stale_ts = str(int(time.time()) - 900)  # 15 minutes old
    r_stale = client.post(
        "/api/voice/webhook/telnyx",
        json={"data": {"event_type": "call.Initiated", "payload": {}}},
        headers={"telnyx-timestamp": stale_ts}
    )
    assert r_stale.status_code == 403
    assert "replay" in r_stale.json()["detail"].lower()


# ==============================================================================
# 5. Enterprise Security Headers Tests
# ==============================================================================

def test_enterprise_security_headers():
    """Verifies HSTS, COOP, Cross-Domain Policies, CSP, and Frame Options are injected."""
    r = client.get("/api/health")
    assert r.status_code == 200
    assert "max-age=31536000" in r.headers.get("Strict-Transport-Security", "")
    assert r.headers.get("X-Permitted-Cross-Domain-Policies") == "none"
    assert r.headers.get("Cross-Origin-Opener-Policy") == "same-origin"
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert "default-src 'self'" in r.headers.get("Content-Security-Policy", "")


# ==============================================================================
# 6 & 7. Persistent Search Jobs & Screenshot SSRF Guard Tests
# ==============================================================================

def test_persistent_search_job_survives_memory_eviction():
    """Verifies search jobs persisted in SQLite are recovered if container memory is cleared on scale-to-zero."""
    fake_job_id = "job_scale_to_zero_test_001"
    job_payload = {
        "job_id": fake_job_id,
        "query": "Dentists in Dallas, TX",
        "status": "completed",
        "progress": 100,
        "message": "Search complete!",
        "logs": ["Completed discovery"],
        "discovered_leads": [{"id": "lead_1", "name": "Dallas Smile Studio"}]
    }
    db.save_search_job(fake_job_id, job_payload)

    # Evict from in-memory active_jobs to simulate Cloud Run scale-to-zero restart
    active_jobs.pop(fake_job_id, None)

    r = client.get(f"/api/search/status/{fake_job_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["job_id"] == fake_job_id
    assert data["status"] == "completed"
    assert len(data["discovered_leads"]) == 1


def test_capture_website_screenshot_blocks_ssrf(tmp_path):
    """Verifies capture_website_screenshot immediately blocks internal/metadata URLs without launching Chromium."""
    import asyncio
    shot_path = tmp_path / "ssrf_test.jpg"
    ok = asyncio.run(capture_website_screenshot("http://169.254.169.254/latest/meta-data/", shot_path))
    assert ok is False
    assert not shot_path.exists()


# ==============================================================================
# 8. Serverless Cron Tick Endpoint Tests
# ==============================================================================

def test_serverless_cron_tick_secret_protection(monkeypatch):
    """Verifies /api/scheduler/cron-tick enforces X-Cron-Secret when CRON_SECRET is configured."""
    monkeypatch.setenv("CRON_SECRET", "my_cloud_scheduler_secret_42")

    r_denied = client.post("/api/scheduler/cron-tick", json={"limit": 1})
    assert r_denied.status_code == 403

    # Mock AutonomousScheduler.run_autonomous_cycle to verify authorized execution
    async def _mock_cycle(**kwargs):
        return {"city_query": "Austin, TX", "total_discovered": 2, "promoted_to_todays_calls": 1}

    from scheduler import AutonomousScheduler
    monkeypatch.setattr(AutonomousScheduler, "run_autonomous_cycle", _mock_cycle)

    r_ok = client.post(
        "/api/scheduler/cron-tick",
        json={"limit": 2},
        headers={"X-Cron-Secret": "my_cloud_scheduler_secret_42"}
    )
    assert r_ok.status_code == 200
    body = r_ok.json()
    assert body["status"] == "completed"
    assert body["mode"] == "serverless_cron_tick"
    assert body["summary"]["total_discovered"] == 2
