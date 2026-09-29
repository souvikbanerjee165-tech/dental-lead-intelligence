"""
Multi-Tenant Architecture Foundation (Roadmap #10).
- Establishes workspace and agency tenant segregation across leads, CRM, proposals, and voice settings.
- Ensures 100% backward compatibility by defaulting to 'default' tenant.
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from database import DatabaseManager

logger = logging.getLogger("tenant_manager")


class TenantManager:
    """Manages agency workspaces, white-label configurations, and tenant isolation."""

    DEFAULT_TENANT_ID = "default"

    @classmethod
    def init_tenants_table(cls, db: DatabaseManager):
        """Initializes tenants table and runs non-destructive schema migrations across core tables."""
        with db._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Tenants Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS tenants (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                agency_branding TEXT,
                pricing_config TEXT,
                created_at TEXT NOT NULL,
                is_active INTEGER DEFAULT 1
            );
            """)

            # 2. Add tenant_id column to core tables if missing
            tables_to_migrate = ["leads", "audits", "touches", "deals", "swarm_tasks", "sales_memory", "settings"]
            for tbl in tables_to_migrate:
                try:
                    cursor.execute(f"PRAGMA table_info({tbl});")
                    cols = {row["name"] for row in cursor.fetchall()}
                    if cols and "tenant_id" not in cols:
                        cursor.execute(f"ALTER TABLE {tbl} ADD COLUMN tenant_id TEXT DEFAULT 'default';")
                except Exception as e:
                    logger.debug(f"Tenant migration note for {tbl}: {e}")

            # Performance Indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_leads_tenant ON leads(tenant_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_swarm_tenant ON swarm_tasks(tenant_id);")

            # 3. Seed Default Tenant if empty
            cursor.execute("SELECT COUNT(*) FROM tenants WHERE id = 'default'")
            if cursor.fetchone()[0] == 0:
                now_str = datetime.now().isoformat()
                branding = json.dumps({
                    "agency_name": "Dental WhatsApp Growth Engine",
                    "tagline": "Automated Clinic Lead Intelligence & AI Receptionist",
                    "contact_email": "team@dentalgrowth.ai",
                    "brand_color": "#10b981"
                })
                pricing = json.dumps({
                    "tier1_setup": 1500,
                    "tier1_monthly": 499,
                    "tier2_setup": 2500,
                    "tier2_monthly": 899
                })
                cursor.execute("""
                INSERT INTO tenants (id, name, slug, agency_branding, pricing_config, created_at, is_active)
                VALUES ('default', 'Primary Agency Workspace', 'default', ?, ?, ?, 1)
                """, (branding, pricing, now_str))

            conn.commit()

    @classmethod
    def list_tenants(cls, db: DatabaseManager) -> List[Dict[str, Any]]:
        """Lists all registered workspaces."""
        cls.init_tenants_table(db)
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tenants WHERE is_active = 1 ORDER BY created_at ASC")
            rows = cursor.fetchall()
            tenants = []
            for r in rows:
                t = dict(r)
                try:
                    t["agency_branding"] = json.loads(t["agency_branding"]) if t.get("agency_branding") else {}
                except Exception:
                    pass
                try:
                    t["pricing_config"] = json.loads(t["pricing_config"]) if t.get("pricing_config") else {}
                except Exception:
                    pass
                tenants.append(t)
            return tenants

    @classmethod
    def get_tenant(cls, db: DatabaseManager, tenant_id_or_slug: str = "default") -> Dict[str, Any]:
        """Retrieves a specific tenant workspace profile."""
        cls.init_tenants_table(db)
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tenants WHERE id = ? OR slug = ?", (tenant_id_or_slug, tenant_id_or_slug))
            row = cursor.fetchone()
            if not row:
                return {
                    "id": "default",
                    "name": "Default Workspace",
                    "slug": "default",
                    "agency_branding": {"agency_name": "Dental WhatsApp Growth Engine"},
                    "pricing_config": {"tier1_setup": 1500, "tier1_monthly": 499}
                }
            t = dict(row)
            try:
                t["agency_branding"] = json.loads(t["agency_branding"]) if t.get("agency_branding") else {}
            except Exception:
                pass
            try:
                t["pricing_config"] = json.loads(t["pricing_config"]) if t.get("pricing_config") else {}
            except Exception:
                pass
            return t

    @classmethod
    def create_tenant(
        cls,
        db: DatabaseManager,
        name: str,
        slug: str,
        agency_branding: Optional[Dict[str, Any]] = None,
        pricing_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Registers a new isolated tenant workspace."""
        cls.init_tenants_table(db)
        clean_slug = "".join(c.lower() for c in slug if c.isalnum() or c in "-_").strip()
        tenant_id = f"tenant_{clean_slug}"
        now_str = datetime.now().isoformat()

        branding_json = json.dumps(agency_branding or {
            "agency_name": name,
            "brand_color": "#0ea5e9"
        })
        pricing_json = json.dumps(pricing_config or {
            "tier1_setup": 1500,
            "tier1_monthly": 499,
            "tier2_setup": 2500,
            "tier2_monthly": 899
        })

        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO tenants (id, name, slug, agency_branding, pricing_config, created_at, is_active)
            VALUES (?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(slug) DO UPDATE SET
                name=excluded.name,
                agency_branding=excluded.agency_branding,
                pricing_config=excluded.pricing_config;
            """, (tenant_id, name, clean_slug, branding_json, pricing_json, now_str))
            conn.commit()

        return {
            "status": "success",
            "tenant_id": tenant_id,
            "name": name,
            "slug": clean_slug
        }
