import os
import pytest
from pathlib import Path

from database import DatabaseManager
from tenant_manager import TenantManager
from fastapi.testclient import TestClient
from app import app

TEST_TENANT_DB = Path("test_tenant_foundation.db")

@pytest.fixture(autouse=True)
def setup_teardown_tenant_db():
    test_db = DatabaseManager(db_path=TEST_TENANT_DB)
    with test_db._get_connection() as conn:
        conn.execute("DELETE FROM tenants WHERE id != 'default';")
        conn.commit()
    yield
    try:
        if TEST_TENANT_DB.exists():
            TEST_TENANT_DB.unlink()
    except Exception:
        pass

def test_tenant_table_init_and_default_seed():
    """Verify TenantManager schema migration and default tenant seeding."""
    test_db = DatabaseManager(db_path=TEST_TENANT_DB)
    TenantManager.init_tenants_table(test_db)

    # 1. Check default tenant
    default_tenant = TenantManager.get_tenant(test_db, "default")
    assert default_tenant["id"] == "default"
    assert default_tenant["name"] == "Primary Agency Workspace"
    assert "agency_name" in default_tenant["agency_branding"]

    # 2. Check schema columns in core tables
    with test_db._get_connection() as conn:
        cursor = conn.cursor()
        for tbl in ["leads", "audits", "deals", "swarm_tasks"]:
            cursor.execute(f"PRAGMA table_info({tbl});")
            cols = {row["name"] for row in cursor.fetchall()}
            assert "tenant_id" in cols, f"Missing tenant_id in {tbl}"

def test_tenant_creation_and_retrieval():
    """Verify registering a new agency tenant with branding and custom pricing."""
    test_db = DatabaseManager(db_path=TEST_TENANT_DB)

    res = TenantManager.create_tenant(
        db=test_db,
        name="Apex Dental Media",
        slug="apex-dental",
        agency_branding={
            "agency_name": "Apex Dental Media",
            "tagline": "Specialized Dental Growth",
            "brand_color": "#8b5cf6"
        },
        pricing_config={
            "tier1_setup": 2000,
            "tier1_monthly": 699,
            "tier2_setup": 3500,
            "tier2_monthly": 1199
        }
    )

    assert res["status"] == "success"
    assert res["slug"] == "apex-dental"
    tenant_id = res["tenant_id"]

    # Fetch by ID
    t_by_id = TenantManager.get_tenant(test_db, tenant_id)
    assert t_by_id["name"] == "Apex Dental Media"
    assert t_by_id["pricing_config"]["tier1_monthly"] == 699

    # Fetch by Slug
    t_by_slug = TenantManager.get_tenant(test_db, "apex-dental")
    assert t_by_slug["id"] == tenant_id

    # List all
    all_tenants = TenantManager.list_tenants(test_db)
    assert len(all_tenants) >= 2

def test_tenant_api_endpoints():
    """Verify FastAPI routes /api/tenants and /api/tenants/{tenant_id}."""
    client = TestClient(app)

    # 1. GET /api/tenants
    res_list = client.get("/api/tenants")
    assert res_list.status_code == 200
    list_data = res_list.json()
    assert "tenants" in list_data
    assert list_data["count"] >= 1

    # 2. GET /api/tenants/default
    res_get = client.get("/api/tenants/default")
    assert res_get.status_code == 200
    assert res_get.json()["id"] == "default"

    # 3. POST /api/tenants
    res_create = client.post("/api/tenants", json={
        "name": "Pacific Dental OS",
        "slug": "pacific-dental",
        "agency_branding": {"agency_name": "Pacific Dental OS"},
        "pricing_config": {"tier1_monthly": 550}
    })
    assert res_create.status_code == 200
    assert res_create.json()["status"] == "success"
