import os
import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app import app, db
from llm_router import LLMRouter, PROVIDER_LM_STUDIO, PROVIDER_DEEPSEEK, PROVIDER_GEMINI
from database import DatabaseManager


client = TestClient(app)


def test_lm_studio_offline_detection():
    """Verify LM Studio offline detection is fast (no hanging) and returns False when server is down."""
    with patch("urllib.request.urlopen", side_effect=OSError("Connection refused")):
        assert LLMRouter.is_lm_studio_online() is False
        models = LLMRouter.get_lm_studio_models()
        assert models == []


def test_lm_studio_online_detection():
    """Verify LM Studio returns online=True and model list when 127.0.0.1:1234 responds."""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = json.dumps({
        "data": [{"id": "qwen2.5-14b-instruct"}, {"id": "llama-3.1-8b-instruct"}]
    }).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        assert LLMRouter.is_lm_studio_online() is True
        models = LLMRouter.get_lm_studio_models()
        assert "qwen2.5-14b-instruct" in models


def test_lm_studio_successful_generation():
    """Verify LLMRouter._call_lm_studio creates completions via OpenAI-compatible endpoint."""
    mock_choice = MagicMock()
    mock_choice.message.content = "Local RTX 3060 AI response for $0.00"
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_completion

    with patch("openai.OpenAI", return_value=mock_client):
        out = LLMRouter._call_lm_studio("Hello local model!", "You are helpful.", "qwen2.5-14b-instruct", 0.7, 500)
        assert "Local RTX 3060" in out
        mock_client.chat.completions.create.assert_called_once()


def test_lm_studio_fallback_cascade_when_offline():
    """Verify that when active provider is LM_STUDIO and local server is offline, it fails over to secondary."""
    with patch.object(LLMRouter, "is_lm_studio_online", return_value=False):
        with patch.object(LLMRouter, "_call_deepseek", return_value="DeepSeek Fallback Response"):
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-mock-key"}):
                LLMRouter.set_provider(PROVIDER_LM_STUDIO)
                resp = LLMRouter.generate_text("Audit practice website")
                assert "DeepSeek Fallback Response" in resp


def test_api_switch_to_lm_studio():
    """Test POST /api/llm/provider switches active provider to LM_STUDIO."""
    resp = client.post("/api/llm/provider", json={
        "provider": "LM_STUDIO",
        "lm_studio_base_url": "http://127.0.0.1:1234/v1",
        "lm_studio_model": "qwen2.5-14b-instruct"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["active_provider"] == "LM_STUDIO"
    assert "LM_STUDIO" in data["details"]["providers"]


def test_db_upsert_synced_lead(tmp_path):
    """Test DatabaseManager.upsert_synced_lead idempotency and schema mapping."""
    test_db = DatabaseManager(str(tmp_path / "sync_test.db"))

    lead_payload = {
        "id": "lead_cloud_test_123",
        "name": "Cloud Dr. Smile",
        "website": "https://cloudsmile.com",
        "phone": "+15551234567",
        "doctor_name": "Dr. Sarah Smile",
        "npi_number": "1234567890",
        "opportunity_score": 92,
        "stage": "AUDITED",
        "staff_roster": [{"name": "Jane", "role": "Hygienist"}]
    }

    # 1. First insert (new record)
    lead_id, is_new = test_db.upsert_synced_lead(lead_payload)
    assert lead_id == "lead_cloud_test_123"
    assert is_new is True

    fetched = test_db.get_lead(lead_id)
    assert fetched is not None
    assert fetched["name"] == "Cloud Dr. Smile"
    assert fetched["doctor_name"] == "Dr. Sarah Smile"
    assert fetched["npi_number"] == "1234567890"

    # 2. Update with modified stage and score (existing record)
    lead_payload["stage"] = "CONTACTED"
    lead_payload["opportunity_score"] = 98
    lead_id2, is_new2 = test_db.upsert_synced_lead(lead_payload)
    assert lead_id2 == lead_id
    assert is_new2 is False

    updated = test_db.get_lead(lead_id)
    assert updated["stage"] == "CONTACTED"
    assert updated["opportunity_score"] == 98


def test_pull_from_cloud_endpoint():
    """Test POST /api/sync/pull-from-cloud syncs remote leads into local DB."""
    mock_remote_leads = [
        {
            "id": "lead_remote_gcp_001",
            "name": "Austin Dental Center",
            "phone": "+15125550101",
            "website": "https://austindentalcenter.com",
            "stage": "FOUND",
            "opportunity_score": 85,
            "doctor_name": "Dr. Austin"
        },
        {
            "id": "lead_remote_gcp_002",
            "name": "Dallas Pediatric Smiles",
            "phone": "+12145550102",
            "website": "https://dallaspediatricsmiles.com",
            "stage": "AUDITED",
            "opportunity_score": 91,
            "doctor_name": "Dr. Dallas"
        }
    ]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_remote_leads

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        resp = client.post("/api/sync/pull-from-cloud", json={
            "cloud_url": "https://dental-lead-engine-240706308332.us-central1.run.app",
            "limit": 100
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["leads_received"] == 2
        assert data["new_leads_saved"] >= 0
        assert data["errors"] == 0

        # Clean up test rows
        with db._get_connection() as conn:
            conn.cursor().execute("DELETE FROM leads WHERE id IN ('lead_remote_gcp_001', 'lead_remote_gcp_002')")
            conn.commit()
