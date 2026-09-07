import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class AuditTelemetry(BaseModel):
    """Structured observability telemetry for every audit run."""
    lead_name: str
    target_url: Optional[str]
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    duration_ms: int = 0
    http_status: Optional[int] = 200
    detectors_evaluated: int = 0
    evidence_collected_count: int = 0
    findings_count: int = 0
    insights_count: int = 0
    confidence_score: float = 0.95
    deal_priority_tier: str = "TIER 2"

class TelemetryTracker:
    """Collects and displays in-memory telemetry logs."""
    _logs: List[AuditTelemetry] = []

    @classmethod
    def record(cls, telemetry: AuditTelemetry):
        cls._logs.append(telemetry)

    @classmethod
    def get_logs(cls) -> List[AuditTelemetry]:
        return cls._logs

    @classmethod
    def get_summary(cls) -> Dict[str, Any]:
        if not cls._logs:
            return {"total_audits": 0}
        total_time = sum(l.duration_ms for l in cls._logs)
        avg_time = int(total_time / len(cls._logs))
        avg_conf = round(sum(l.confidence_score for l in cls._logs) / len(cls._logs), 2)
        return {
            "total_audits": len(cls._logs),
            "avg_duration_ms": avg_time,
            "avg_confidence": avg_conf,
            "total_findings_generated": sum(l.findings_count for l in cls._logs),
            "total_insights_generated": sum(l.insights_count for l in cls._logs)
        }
