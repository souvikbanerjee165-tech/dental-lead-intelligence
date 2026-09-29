import os
import pytest
from pathlib import Path

from database import DatabaseManager
from route_optimizer import TravelRouteOptimizer
from fastapi.testclient import TestClient
from app import app

TEST_ROUTE_DB = Path("test_route_optimizer.db")

@pytest.fixture(autouse=True)
def setup_teardown_route_db():
    test_db = DatabaseManager(db_path=TEST_ROUTE_DB)
    with test_db._get_connection() as conn:
        conn.execute("DELETE FROM leads;")
        conn.commit()
    yield
    try:
        if TEST_ROUTE_DB.exists():
            TEST_ROUTE_DB.unlink()
    except Exception:
        pass

def test_route_optimizer_planning_and_sequencing():
    """Verify route sequencing, arrival windows, and Google Maps URL synthesis."""
    test_db = DatabaseManager(db_path=TEST_ROUTE_DB)
    
    with test_db._get_connection() as conn:
        conn.execute("""
        INSERT INTO leads (id, name, doctor_name, address, phone, stage, win_probability_pct, missed_rev_max, territory_id)
        VALUES 
        ('lead_r1', 'Downtown Dental', 'Dr. Alice Smith', '100 Congress Ave, Austin, TX', '(512) 555-0101', 'IDENTIFIED', 90, 5500, 'austin_tx'),
        ('lead_r2', 'South Lamar Smiles', 'Dr. Bob Jones', '1200 S Lamar Blvd, Austin, TX', '(512) 555-0102', 'IDENTIFIED', 85, 4800, 'austin_tx'),
        ('lead_r3', 'Domain Dental Studio', 'Dr. Clara Vance', '11000 Century Oaks Ter, Austin, TX', '(512) 555-0103', 'IDENTIFIED', 80, 6200, 'austin_tx');
        """)
        conn.commit()

    route = TravelRouteOptimizer.plan_route(
        db=test_db,
        territory_id="austin_tx",
        max_stops=3,
        start_time_str="09:00"
    )

    assert route["status"] == "success"
    assert route["total_stops"] == 3
    assert route["estimated_duration_hours"] > 0
    assert "google_maps_url" in route
    assert "https://www.google.com/maps/dir/" in route["google_maps_url"]
    assert "travelmode=driving" in route["google_maps_url"]

    itinerary = route["itinerary"]
    assert len(itinerary) == 3
    assert itinerary[0]["stop_number"] == 1
    assert "09:00 AM" in itinerary[0]["arrival_window"]
    assert "10:00 AM" in itinerary[1]["arrival_window"] # 20m drive + 40m visit
    assert "Opening Hook:" in itinerary[0]["opening_hook"] or "stopping by" in itinerary[0]["opening_hook"]
    assert itinerary[0]["doctor_name"] in ["Dr. Alice Smith", "Dr. Bob Jones", "Dr. Clara Vance"]

def test_route_optimizer_empty_candidates():
    """Verify clean handling when no leads with addresses match."""
    test_db = DatabaseManager(db_path=TEST_ROUTE_DB)
    route = TravelRouteOptimizer.plan_route(db=test_db, territory_id="non_existent")
    assert route["status"] == "empty"
    assert route["total_stops"] if "total_stops" in route else len(route["stops"]) == 0
    assert route["google_maps_url"] is None

def test_route_optimizer_api_endpoints():
    """Verify FastAPI routes /api/route/plan and /api/route/optimize."""
    client = TestClient(app)

    # 1. GET /api/route/plan
    res_plan = client.get("/api/route/plan?max_stops=3")
    assert res_plan.status_code == 200
    plan_data = res_plan.json()
    assert "status" in plan_data

    # 2. POST /api/route/optimize
    res_opt = client.post("/api/route/optimize", json={
        "territory_id": None,
        "lead_ids": [],
        "max_stops": 3,
        "start_time": "10:00"
    })
    assert res_opt.status_code == 200
    assert "status" in res_opt.json()
