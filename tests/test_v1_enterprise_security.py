import time
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app import app
from auth_manager import AuthManager
from structured_logger import SecretMaskingLogFilter, StructuredAuditLogger, sanitize_log_message
from settings_manager import SettingsManager
from security import validate_startup_security


def test_password_hashing_and_verification():
    mgr = AuthManager(secret_key="test-secret-key-1234")
    hashed = mgr.hash_password("SuperSecretPass123!")

    assert hashed.startswith("pbkdf2_sha256$100000$")
    assert mgr.verify_password("SuperSecretPass123!", hashed) is True
    assert mgr.verify_password("WrongPassword!", hashed) is False


def test_session_token_lifecycle():
    mgr = AuthManager(secret_key="test-secret-key-1234")

    # 1. Valid token
    token = mgr.create_session_token(username="sales_rep_1", duration_sec=3600)
    valid, user = mgr.validate_session_token(token)
    assert valid is True
    assert user == "sales_rep_1"

    # 2. Tampered token
    tampered = token[:-4] + "abcd"
    valid_t, err = mgr.validate_session_token(tampered)
    assert valid_t is False

    # 3. Expired token
    expired_token = mgr.create_session_token(username="expired_rep", duration_sec=-10)
    valid_e, err_e = mgr.validate_session_token(expired_token)
    assert valid_e is False
    assert "expired" in err_e.lower()


def test_secret_log_sanitization():
    # Test API key pattern redaction
    raw_log = "Initializing Gemini with key AIzaSyA1234567890abcdefghijklmnopqrstuv and sk-1234567890abcdefghijklmnopqr"
    sanitized = sanitize_log_message(raw_log)

    assert "AIzaSy" not in sanitized
    assert "sk-" not in sanitized
    assert "[REDACTED_SECRET]" in sanitized


def test_structured_audit_logger(tmp_path):
    audit_file = tmp_path / "test_audit.jsonl"
    logger = StructuredAuditLogger(log_path=audit_file)

    logger.log_event(
        event="clinic_qualified",
        module="ai_qualifier",
        lead_id="lead_99",
        duration_ms=1150.5,
        metadata={
            "score": 85,
            "api_key": "AIzaSySecretKey",
            "notes": "Qualified for WhatsApp intake"
        }
    )

    events = logger.get_recent_events(limit=10)
    assert len(events) == 1
    ev = events[0]
    assert ev["event"] == "clinic_qualified"
    assert ev["lead_id"] == "lead_99"
    assert ev["duration_ms"] == 1150.5
    # Ensure sensitive metadata was masked
    assert ev["metadata"]["api_key"] == "[REDACTED]"
    assert ev["metadata"]["score"] == 85


def test_configuration_boundary_validation(tmp_path):
    settings_file = tmp_path / "test_settings.json"
    mgr = SettingsManager(settings_file=settings_file)

    # 1. Invalid Buying Probability (e.g. 180%)
    with pytest.raises(ValueError, match="between 0% and 100%"):
        mgr.update_settings({"min_buying_probability": 180})

    # 2. Inverted Delays (min > max)
    with pytest.raises(ValueError, match="cannot exceed maximum delay"):
        mgr.update_settings({
            "rate_limit_min_delay_sec": 8.0,
            "rate_limit_max_delay_sec": 2.0
        })

    # 3. Excessive Case Value
    with pytest.raises(ValueError, match="between \\$50 and \\$50,000"):
        mgr.update_settings({"default_case_value": 900000})

    # 4. Valid settings succeed
    valid_res = mgr.update_settings({
        "min_buying_probability": 75,
        "default_case_value": 1200,
        "rate_limit_min_delay_sec": 2.0,
        "rate_limit_max_delay_sec": 4.0
    })
    assert valid_res["min_buying_probability"] == 75
    assert valid_res["default_case_value"] == 1200


def test_auth_and_audit_api_endpoints():
    client = TestClient(app)

    # 1. Auth Status Endpoint
    status_resp = client.get("/api/auth/status")
    assert status_resp.status_code == 200
    assert "auth_required" in status_resp.json()

    # 2. Login with correct password
    from auth_manager import auth_manager
    configured_pass = auth_manager.get_configured_password()

    login_resp = client.post("/api/auth/login", json={"password": configured_pass, "username": "lead_rep"})
    assert login_resp.status_code == 200
    data = login_resp.json()
    assert data["status"] == "success"
    assert "session_token" in data

    # 3. Login with wrong password
    bad_resp = client.post("/api/auth/login", json={"password": "TotallyWrongPassword!", "username": "lead_rep"})
    assert bad_resp.status_code == 401

    # 4. Audit logs endpoint
    audit_resp = client.get("/api/system/audit-logs")
    assert audit_resp.status_code == 200
    assert "events" in audit_resp.json()

    # 5. Invalid Settings Update returns 400 Bad Request
    bad_settings_resp = client.post("/api/settings", json={"min_buying_probability": 250})
    assert bad_settings_resp.status_code == 400
    assert "between 0% and 100%" in bad_settings_resp.json()["detail"]


def test_modern_security_headers_and_csp():
    client = TestClient(app)
    resp = client.get("/api/health")
    assert resp.status_code == 200

    # Modern CSP present
    assert "Content-Security-Policy" in resp.headers
    assert "default-src 'self'" in resp.headers["Content-Security-Policy"]
    assert "Permissions-Policy" in resp.headers

    # Deprecated X-XSS-Protection MUST NOT be present
    assert resp.headers.get("X-XSS-Protection") is None
