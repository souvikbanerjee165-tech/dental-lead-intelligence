import pytest
from auditor import compute_content_hash, WebsiteAuditor
from models import RawLead, WebsiteAuditResult, ScoredLead
from database import DatabaseManager
from evidence import EvidenceGraph

def test_compute_content_hash_normalization():
    h1 = compute_content_hash("<html>   <body>   <h1>Hello</h1>  </body> </html>")
    h2 = compute_content_hash("<html>\n<body>\n<h1>Hello</h1>\n</body>\n</html>")
    assert h1 == h2
    assert len(h1) == 64

    empty_h = compute_content_hash("")
    assert empty_h == ""

@pytest.mark.anyio
async def test_incremental_auditing_cache(tmp_path, monkeypatch):
    db_file = tmp_path / "test_incremental.db"
    db = DatabaseManager(db_path=db_file)

    auditor = WebsiteAuditor()
    auditor.db = db

    raw = RawLead(name="Cedar Dental", website="https://cedardental.com")

    # Mock crawl
    async def mock_crawl(url):
        return WebsiteAuditResult(has_online_booking=True), EvidenceGraph(), "mock_hash_123"

    monkeypatch.setattr(auditor, "_crawl_and_analyze", mock_crawl)

    # First audit - should not be cached
    res1 = await auditor.audit_lead(raw, check_incremental=True)
    assert res1.was_cached is False
    assert res1.content_hash == "mock_hash_123"

    # Second audit with same mock hash - should be cached
    res2 = await auditor.audit_lead(raw, check_incremental=True)
    assert res2.was_cached is True
    assert res2.content_hash == "mock_hash_123"

    # Third audit with force=True - should bypass cache
    res3 = await auditor.audit_lead(raw, check_incremental=True, force=True)
    assert res3.was_cached is False
