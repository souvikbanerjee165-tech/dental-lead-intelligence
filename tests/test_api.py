import pytest
from fastapi.testclient import TestClient
from app import app, db

client = TestClient(app)

def test_api_stats_endpoint():
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_leads" in data
    assert "total_leakage" in data
    assert "pipeline" in data
    assert "queue" in data

def test_api_leads_list():
    response = client.get("/api/leads?limit=5")
    assert response.status_code == 200
    leads = response.json()
    assert isinstance(leads, list)
    if leads:
        lead = leads[0]
        assert "name" in lead
        assert "clean_phone" in lead
        assert "wa_link" in lead

def test_api_queue_list():
    response = client.get("/api/queue?status=ALL")
    assert response.status_code == 200
    queue_items = response.json()
    assert isinstance(queue_items, list)

def test_api_proposal_generation(tmp_path):
    response = client.post("/api/proposal/generate", json={
        "name": "Austin Dental Center",
        "url": "https://austindentalcenter.com"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "proposal_url" in data
    assert data["tier1_setup"] > 0

def test_wa_pitch_and_phone_formatting():
    from app import format_clean_phone, generate_wa_pitch_and_link
    assert format_clean_phone("(512) 459-4347") == "15124594347"
    assert format_clean_phone("+1-512-459-4347") == "15124594347"
    
    wa_data = generate_wa_pitch_and_link({
        "name": "Dr. Miller Smiles",
        "phone": "(512) 459-4347",
        "address": "Austin, TX",
        "rating": 4.9,
        "review_count": 140,
        "opportunity_score": 85,
        "annual_gap": 79500
    })
    assert wa_data["clean_phone"] == "15124594347"
    assert wa_data["salutation"] == "Dr. Miller Smiles"
    assert "https://wa.me/15124594347" in wa_data["wa_link"]
    assert "WhatsApp" in wa_data["pitch"]
