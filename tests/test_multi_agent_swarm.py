import os
import pytest
import asyncio
from pathlib import Path
import sqlite3
import json
from unittest.mock import patch, MagicMock

from database import DatabaseManager
from swarm_master import (
    SwarmMaster,
    AgentScout,
    AgentAuditor,
    AgentDoctorMatcher,
    AgentProposalEngine,
    AgentPreDialer
)
from fastapi.testclient import TestClient
from app import app, db

TEST_SWARM_DB = Path("test_swarm_fleet.db")

@pytest.fixture(autouse=True)
def setup_teardown_swarm_db():
    test_db = DatabaseManager(db_path=TEST_SWARM_DB)
    with test_db._get_connection() as conn:
        conn.execute("DELETE FROM leads;")
        conn.execute("DELETE FROM swarm_tasks;")
        conn.commit()
    yield
    try:
        with test_db._get_connection() as conn:
            conn.execute("DELETE FROM leads;")
            conn.execute("DELETE FROM swarm_tasks;")
            conn.commit()
    except Exception:
        pass

def test_swarm_task_ledger_operations():
    """Verify DatabaseManager log_swarm_task, update_swarm_task, and task retrieval."""
    test_db = DatabaseManager(db_path=TEST_SWARM_DB)
    
    # 1. Log a pending task
    task_id = test_db.log_swarm_task(
        agent_type="AUDITOR",
        lead_id="lead_test_001",
        input_payload={"url": "https://exampledental.com", "action": "deep_audit"},
        status="PENDING"
    )
    assert task_id is not None
    assert len(task_id) > 10

    # 2. Update task to SUCCESS
    updated = test_db.update_swarm_task(
        task_id=task_id,
        status="SUCCESS",
        output_payload={"has_chat": False, "missed_revenue": 4500, "tech_stack": ["WordPress"]}
    )
    assert updated is True

    # 3. Retrieve recent swarm tasks
    recent = test_db.get_recent_swarm_tasks(limit=10)
    assert len(recent) >= 1
    t0 = recent[0]
    assert t0["task_id"] == task_id
    assert t0["agent_type"] == "AUDITOR"
    assert t0["status"] == "SUCCESS"
    assert t0["lead_id"] == "lead_test_001"
    assert t0["output_payload"]["missed_revenue"] == 4500

    # 4. Pipeline counts check
    counts = test_db.get_swarm_pipeline_counts()
    assert "total_leads" in counts
    assert "needs_audit" in counts
    assert "needs_doctor_match" in counts
    assert "proposal_eligible" in counts
    assert "ready_to_call" in counts

def test_master_orchestrator_directive_formulation():
    """Verify SwarmMaster detects queue imbalances and formulates targeted directives."""
    test_db = DatabaseManager(db_path=TEST_SWARM_DB)
    master = SwarmMaster(db=test_db)

    # Empty pipeline: should flag DISCOVERY_DEFICIT
    directive_empty = master.formulate_directive({"needs_audit": 0, "needs_doctor_match": 0, "ready_to_call": 0, "total_leads": 0})
    assert directive_empty["bottleneck"] == "DISCOVERY_DEFICIT"
    assert "Agent A" in directive_empty["directive"]

    # Heavy audit backlog: should flag AUDIT_BACKLOG
    directive_audit = master.formulate_directive({"needs_audit": 12, "needs_doctor_match": 1, "ready_to_call": 0, "total_leads": 15})
    assert directive_audit["bottleneck"] == "AUDIT_BACKLOG"
    assert "Agent B" in directive_audit["directive"]

    # Decision maker bottleneck: should flag DECISION_MAKER_DEFICIT
    directive_doc = master.formulate_directive({"needs_audit": 1, "needs_doctor_match": 9, "ready_to_call": 0, "total_leads": 15})
    assert directive_doc["bottleneck"] == "DECISION_MAKER_DEFICIT"
    assert "Agent C" in directive_doc["directive"]

    # Ready to call opportunity: should flag OUTBOUND_CLOSING_OPPORTUNITY
    directive_call = master.formulate_directive({"needs_audit": 0, "needs_doctor_match": 0, "ready_to_call": 8, "total_leads": 15})
    assert directive_call["bottleneck"] == "OUTBOUND_CLOSING_OPPORTUNITY"
    assert "Agent E" in directive_call["directive"]

def test_agent_auditor_worker():
    """Verify AgentAuditor processes unaudited leads and logs task ledger entry."""
    test_db = DatabaseManager(db_path=TEST_SWARM_DB)
    
    # Seed a lead needing audit
    with test_db._get_connection() as conn:
        conn.execute("""
        INSERT INTO leads (id, name, website, stage)
        VALUES ('lead_audit_test', 'Oak Dental Group', 'https://oakdental.com', 'FOUND')
        """)
        conn.commit()

    class ScoredStub:
        opportunity_score = 78
        estimated_missed_revenue_monthly_max = 4200

    # Mock website inspection
    with patch("auditor.WebsiteAuditor.audit_lead", return_value=ScoredStub()):
        auditor = AgentAuditor(db=test_db)
        res = asyncio.run(auditor.execute({"batch_size": 1}))
        
        assert res["audited_count"] >= 1
        assert res["leads"][0]["lead_id"] == "lead_audit_test"
        assert res["leads"][0]["opportunity_score"] == 78

    # Verify task ledger has logged this audit
    recent = test_db.get_recent_swarm_tasks(limit=5)
    audit_tasks = [t for t in recent if t["agent_type"] == "AUDITOR"]
    assert len(audit_tasks) >= 1
    assert audit_tasks[0]["status"] == "COMPLETED"

def test_agent_doctor_matcher_worker():
    """Verify AgentDoctorMatcher enriches decision-maker details and win probability."""
    test_db = DatabaseManager(db_path=TEST_SWARM_DB)
    
    # Seed lead with audit done but missing doctor
    with test_db._get_connection() as conn:
        conn.execute("""
        INSERT INTO leads (id, name, stage, missed_rev_max, rating, review_count)
        VALUES ('lead_matcher_test', 'Dr. Angela Martin Family Dentistry', 'AUDITED', 5500, 4.8, 110)
        """)
        conn.commit()

    matcher = AgentDoctorMatcher(db=test_db)
    res = asyncio.run(matcher.execute({"batch_size": 1}))
    assert res["matched_count"] >= 1
    assert "Dr. Angela Martin" in res["leads"][0]["doctor_name"]
    assert res["leads"][0]["win_probability_pct"] >= 70

    # Verify lead in DB now has doctor and win probability
    saved = test_db.get_lead("lead_matcher_test")
    assert "Dr. Angela Martin" in saved["doctor_name"]
    assert saved["win_probability_pct"] >= 70

def test_agent_proposal_engine_worker():
    """Verify AgentProposalEngine synthesizes custom HTML proposal."""
    test_db = DatabaseManager(db_path=TEST_SWARM_DB)
    
    with test_db._get_connection() as conn:
        conn.execute("""
        INSERT INTO leads (id, name, stage, doctor_name, missed_rev_max)
        VALUES ('lead_prop_test', 'Barton Creek Dental', 'QUALIFIED', 'Dr. David Lee', 6000)
        """)
        conn.commit()

    prop_engine = AgentProposalEngine(db=test_db)
    with patch("proposals.ProposalGenerator.generate_proposal"):
        with patch.object(Path, "exists", return_value=True):
            res = asyncio.run(prop_engine.execute({"batch_size": 1}))
            assert res["proposals_generated"] >= 1
            assert "proposal_url" in res["leads"][0]

def test_agent_pre_dialer_worker():
    """Verify AgentPreDialer prepares call battlecard with institutional memory."""
    test_db = DatabaseManager(db_path=TEST_SWARM_DB)
    
    with test_db._get_connection() as conn:
        conn.execute("""
        INSERT INTO leads (id, name, stage, doctor_name, phone, address, missed_rev_max)
        VALUES ('lead_dial_test', 'Metro Smile Center', 'PROPOSED', 'Dr. Karen White', '(512) 555-1234', 'Austin, TX', 4500)
        """)
        conn.commit()

    pre_dialer = AgentPreDialer(db=test_db)
    res = asyncio.run(pre_dialer.execute({"batch_size": 1}))
    assert res["staged_calls_count"] >= 1
    assert res["leads"][0]["lead_id"] == "lead_dial_test"
    assert res["leads"][0]["phone"] == "(512) 555-1234"

def test_swarm_master_execute_cycle():
    """Verify SwarmMaster.execute_cycle coordinates the fleet according to bottleneck."""
    test_db = DatabaseManager(db_path=TEST_SWARM_DB)
    master = SwarmMaster(db=test_db)

    # Mock all agents to return clean payloads
    with patch.object(AgentScout, "run", return_value={"discovered_count": 2}), \
         patch.object(AgentAuditor, "run", return_value={"audited_count": 2}), \
         patch.object(AgentDoctorMatcher, "run", return_value={"matched_count": 2}), \
         patch.object(AgentProposalEngine, "run", return_value={"proposals_generated": 1}), \
         patch.object(AgentPreDialer, "run", return_value={"staged_calls_count": 1}):
        
        cycle_result = asyncio.run(master.execute_cycle(db=test_db, territory_id="austin_tx", batch_limit=2))
        assert cycle_result["status"] == "SUCCESS"
        assert "bottleneck" in cycle_result
        assert "master_directive" in cycle_result
        assert "execution_summary" in cycle_result
        assert "AUDITOR" in cycle_result["execution_summary"]

def test_swarm_api_endpoints():
    """Verify FastAPI endpoints /api/swarm/status, /api/swarm/agent/{agent_id}/run, and /api/swarm/dispatch-cycle."""
    client = TestClient(app)

    # 1. GET /api/swarm/status
    res_status = client.get("/api/swarm/status")
    assert res_status.status_code == 200
    status_data = res_status.json()
    assert "pipeline_counts" in status_data
    assert "master_directive" in status_data
    assert "bottleneck" in status_data
    assert "recent_tasks" in status_data

    # 2. POST /api/swarm/agent/SCOUT/run
    with patch("swarm_master.AgentScout.run", return_value={"discovered_count": 1, "leads": []}):
        res_agent = client.post("/api/swarm/agent/SCOUT/run", json={"limit": 1})
        assert res_agent.status_code == 200
        agent_data = res_agent.json()
        assert agent_data["status"] == "success"
        assert agent_data["agent"] == "SCOUT"

    # 3. POST /api/swarm/dispatch-cycle
    with patch("swarm_master.SwarmMaster.execute_cycle", return_value={
        "status": "SUCCESS",
        "bottleneck": "BALANCED",
        "master_directive": "Pipeline balanced.",
        "execution_summary": {"AUDITOR": {"audited_count": 1}}
    }):
        res_cycle = client.post("/api/swarm/dispatch-cycle", json={"batch_limit": 2})
        assert res_cycle.status_code == 200
        cycle_data = res_cycle.json()
        assert cycle_data["status"] == "SUCCESS"
        assert cycle_data["bottleneck"] == "BALANCED"
