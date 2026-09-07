import pytest
import tempfile
from pathlib import Path
from database import DatabaseManager
from models import RawLead, ScoredLead, WebsiteAuditResult
from explainer import ScoreExplainer
from fastapi.testclient import TestClient
from app import app, active_jobs

@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)
    db = DatabaseManager(db_path=db_path)
    yield db
    try:
        if db_path.exists():
            db_path.unlink()
    except Exception:
        pass

def test_enterprise_data_persistence(temp_db):
    raw = RawLead(
        name='Austin Dental Arts',
        website='https://austindentalarts.com',
        phone='512-555-0199',
        address='123 Congress Ave, Austin, TX',
        rating=4.9,
        review_count=124,
        latitude=30.2672,
        longitude=-97.7431
    )
    scored = ScoredLead(
        raw_lead=raw,
        audit=WebsiteAuditResult(screenshot_path='output/screenshots/austin_art.jpg'),
        opportunity_score=82,
        estimated_missed_revenue_annual=65000,
        estimated_missed_revenue_monthly_min=3450,
        estimated_missed_revenue_monthly_max=6900,
        screenshot_path='output/screenshots/austin_art.jpg',
        why_score_reasons=[
            'No after-hours WhatsApp instant booking intake',
            'High patient review volume risking missed-call leakage',
            'Mobile booking friction'
        ]
    )

    lead_id, changes = temp_db.save_scored_lead(scored, [])
    assert lead_id is not None

    lead = temp_db.get_lead(lead_id)
    assert lead is not None
    assert lead['latitude'] == pytest.approx(30.2672)
    assert lead['longitude'] == pytest.approx(-97.7431)
    assert lead['screenshot_path'] == 'output/screenshots/austin_art.jpg'
    assert lead['missed_rev_min'] == 3450
    assert lead['missed_rev_max'] == 6900
    assert isinstance(lead['why_score_reasons'], list)
    assert len(lead['why_score_reasons']) == 3
    assert 'No after-hours' in lead['why_score_reasons'][0]

def test_score_explainer_fallback():
    raw = RawLead(name='Downtown Smile Spa', website='https://downtownsmiles.com', phone='512-444-1122')
    scored = ScoredLead(
        raw_lead=raw,
        audit=WebsiteAuditResult(),
        opportunity_score=85,
        estimated_missed_revenue_annual=72000
    )
    explainer = ScoreExplainer()
    reasons = explainer.fallback_reasons(scored)
    assert len(reasons) >= 3
    assert any('WhatsApp' in r or 'booking' in r or 'intake' in r for r in reasons)

def test_api_enterprise_lead_fields():
    client = TestClient(app)
    response = client.get('/api/leads')
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

def test_search_job_status_structure():
    job_id = 'test_job_123'
    active_jobs[job_id] = {
        'job_id': job_id,
        'query': 'Dentists in Austin, TX',
        'status': 'running',
        'progress': 50,
        'message': 'Testing...',
        'clinics_found': 15,
        'websites_analyzed': 10,
        'high_opportunity_count': 6,
        'logs': ['[12:00:00] Test log entry'],
        'discovered_leads': []
    }
    client = TestClient(app)
    res = client.get(f'/api/search/status/{job_id}')
    assert res.status_code == 200
    body = res.json()
    assert body['clinics_found'] == 15
    assert body['websites_analyzed'] == 10
    assert body['high_opportunity_count'] == 6
    assert len(body['logs']) == 1

def test_export_leads_excel_and_csv():
    client = TestClient(app)
    # Test XLSX export
    res_xlsx = client.get('/api/leads/export?format=xlsx')
    assert res_xlsx.status_code == 200
    assert 'spreadsheetml' in res_xlsx.headers.get('content-type', '')
    assert len(res_xlsx.content) > 500

    # Test CSV export
    res_csv = client.get('/api/leads/export?format=csv')
    assert res_csv.status_code == 200
    assert 'text/csv' in res_csv.headers.get('content-type', '')
    assert 'Practice Name' in res_csv.text

def test_database_deduplication(temp_db):
    raw = RawLead(
        name='Smile Craft Studio',
        website='https://smilecraftstudio.com',
        phone='512-555-8888',
        address='100 Main St, Austin, TX'
    )
    scored = ScoredLead(
        raw_lead=raw,
        audit=WebsiteAuditResult(),
        opportunity_score=75
    )
    temp_db.save_scored_lead(scored, [])

    # Exact name check
    assert temp_db.is_lead_existing(name='Smile Craft Studio') is True
    # Case-insensitive name check
    assert temp_db.is_lead_existing(name='smile craft studio') is True
    # Website domain check
    assert temp_db.is_lead_existing(name='Different Name', website='https://smilecraftstudio.com/about') is True
    # Phone number check
    assert temp_db.is_lead_existing(name='Different Name', phone='+1 (512) 555-8888') is True
    # Completely new practice
    assert temp_db.is_lead_existing(name='Unrelated Practice', website='https://unrelated.com', phone='555-111-2222') is False

