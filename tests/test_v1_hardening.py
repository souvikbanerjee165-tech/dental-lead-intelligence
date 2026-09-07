import os
import gzip
import sqlite3
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app import app
from database import DatabaseManager
from data_quality import calculate_data_completeness
from backup_manager import BackupManager
from health_monitor import SystemHealthMonitor
from cost_tracker import CostTelemetryTracker
from settings_manager import SettingsManager
from security import SecurityHeadersMiddleware, validate_startup_security, human_jitter_delay


@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_leads.db"
    db = DatabaseManager(db_path=db_file)
    return db, db_file


def test_data_completeness_scoring():
    # 1. Full lead
    complete_lead = {
        "doctor_name": "Dr. Sarah Miller",
        "phone": "5125551234",
        "email": "sarah@austinsmiles.com",
        "website": "https://austinsmiles.com",
        "latitude": 30.2672,
        "longitude": -97.7431,
        "reviews_count": 45,
        "rating": 4.8
    }
    score, tier, missing = calculate_data_completeness(complete_lead)
    assert score == 100
    assert tier == "EXCELLENT"
    assert len(missing) == 0

    # 2. Minimal lead
    sparse_lead = {
        "name": "Unknown Clinic",
        "doctor_name": None,
        "phone": "",
        "email": None,
        "website": "",
        "reviews_count": 2,
        "rating": 3.5
    }
    score2, tier2, missing2 = calculate_data_completeness(sparse_lead)
    assert score2 < 50
    assert any("Doctor" in m for m in missing2)
    assert any("Email" in m for m in missing2)


def test_database_indexes_created(temp_db):
    db, db_file = temp_db
    with db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = {row[0] for row in cursor.fetchall()}

    expected_indexes = [
        "idx_leads_phone",
        "idx_leads_website",
        "idx_leads_stage",
        "idx_leads_buying_prob",
        "idx_leads_urgency",
        "idx_leads_ev",
        "idx_leads_doctor",
        "idx_timeline_lead_ts",
        "idx_triggers_lead_ts",
        "idx_audits_lead_ts"
    ]
    for idx in expected_indexes:
        assert idx in indexes, f"Index {idx} was not found in SQLite master"


def test_backup_and_disaster_recovery(tmp_path):
    # Setup test DB with data
    db_path = tmp_path / "production.db"
    backup_dir = tmp_path / "backups"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE test_items (id INTEGER PRIMARY KEY, name TEXT);")
    conn.execute("INSERT INTO test_items (name) VALUES ('Dental Apex Clinic');")
    conn.commit()
    conn.close()

    mgr = BackupManager(db_path=db_path, backup_dir=backup_dir)

    # 1. Create backup
    res = mgr.create_backup(label="test_run")
    assert res["success"] is True
    archive_name = res["archive_name"]
    archive_path = backup_dir / archive_name
    assert archive_path.exists()
    assert archive_name.endswith(".db.gz")
    assert res["compressed_size_bytes"] > 0

    # 2. List backups
    backups = mgr.list_backups()
    assert len(backups) >= 1
    assert backups[0]["filename"] == archive_name

    # 3. Restore to new target
    restore_target = tmp_path / "restored.db"
    restore_res = mgr.restore_backup(archive_name, target_db_path=restore_target)
    assert restore_res["success"] is True
    assert restore_target.exists()

    # Verify data integrity in restored DB
    r_conn = sqlite3.connect(restore_target)
    cursor = r_conn.cursor()
    cursor.execute("SELECT name FROM test_items WHERE id = 1")
    row = cursor.fetchone()
    r_conn.close()
    assert row[0] == "Dental Apex Clinic"


def test_health_monitor(temp_db, tmp_path):
    db, db_file = temp_db
    monitor = SystemHealthMonitor(db=db, output_dir=tmp_path)
    diag = monitor.run_full_diagnostic()

    assert "overall_status" in diag
    assert diag["overall_status"] in ["HEALTHY", "DEGRADED"]
    assert "components" in diag
    assert "database" in diag["components"]
    assert diag["components"]["database"]["status"] == "HEALTHY"
    assert "gemini_ai" in diag["components"]
    assert "storage" in diag["components"]


def test_cost_telemetry_tracker(tmp_path):
    telem_file = tmp_path / "telemetry.json"
    tracker = CostTelemetryTracker(telemetry_file=telem_file)

    # Record some usage
    tracker.record_activity(
        gemini_calls=10,
        playwright_runs=5,
        screenshots_saved=5,
        proposals_generated=2,
        simulator_turns=3
    )

    summary = tracker.get_summary(total_leads_in_db=10)
    assert summary["all_time"]["gemini_calls"] >= 10
    assert summary["all_time"]["playwright_runs"] >= 5
    assert summary["all_time"]["total_estimated_spend_usd"] > 0
    assert summary["all_time"]["cost_per_qualified_lead_usd"] > 0
    assert "$" in summary["all_time"]["cost_per_lead_formatted"]


def test_settings_manager(tmp_path):
    settings_file = tmp_path / "settings.json"
    mgr = SettingsManager(settings_file=settings_file)

    # Defaults load
    cfg = mgr.get_settings()
    assert "target_cities" in cfg
    assert len(cfg["target_cities"]) > 0

    # Updates persist
    mgr.update_settings({
        "min_reviews_threshold": 25,
        "default_case_value": 1200,
        "agency_name": "Apex Dental Systems"
    })

    updated = mgr.get_settings()
    assert updated["min_reviews_threshold"] == 25
    assert updated["default_case_value"] == 1200
    assert updated["agency_name"] == "Apex Dental Systems"


def test_security_hardening_middleware_and_checks():
    client = TestClient(app)
    resp = client.get("/api/health")
    assert resp.status_code == 200

    # Verify Security Response Headers injected by SecurityHeadersMiddleware
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert "Content-Security-Policy" in resp.headers
    assert "Permissions-Policy" in resp.headers
    assert resp.headers.get("X-XSS-Protection") is None
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    # Startup security validation
    sec_info = validate_startup_security()
    assert sec_info["status"] in ["PASS", "SECURE", "DEVELOPMENT"]
    assert "sql_injection_safe" in sec_info


def test_system_api_endpoints():
    client = TestClient(app)

    # 1. Health endpoint
    h_resp = client.get("/api/system/health")
    assert h_resp.status_code == 200
    h_data = h_resp.json()
    assert "overall_status" in h_data
    assert "components" in h_data

    # 2. Telemetry endpoint
    t_resp = client.get("/api/system/telemetry")
    assert t_resp.status_code == 200
    t_data = t_resp.json()
    assert "all_time" in t_data
    assert "cost_per_qualified_lead_usd" in t_data["all_time"]

    # 3. Backups endpoint
    b_resp = client.get("/api/system/backups")
    assert b_resp.status_code == 200
    b_data = b_resp.json()
    assert "backups" in b_data

    # 4. Settings endpoints
    s_resp = client.get("/api/settings")
    assert s_resp.status_code == 200
    s_data = s_resp.json()
    assert "target_cities" in s_data

    s_update = client.post("/api/settings", json={"min_reviews_threshold": 18})
    assert s_update.status_code == 200
    assert s_update.json()["settings"]["min_reviews_threshold"] == 18

    # 5. Security audit endpoint
    sec_resp = client.get("/api/system/security")
    assert sec_resp.status_code == 200
    assert "status" in sec_resp.json()
