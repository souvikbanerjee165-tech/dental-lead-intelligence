"""
Structured JSON Audit Logger & Secret Masking Filter.
Provides tamper-resistant JSON Lines logging for operational traceability
and intercepts sensitive credentials to ensure secrets never leak into logs.
"""

import os
import re
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from config import OUTPUT_DIR

LOGS_DIR = OUTPUT_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_LOG_FILE = LOGS_DIR / "audit.jsonl"

# Regex patterns identifying API keys and sensitive credentials
SECRET_PATTERNS = [
    re.compile(r"(AIza[0-9A-Za-z-_]{35})", re.IGNORECASE),
    re.compile(r"(sk-[a-zA-Z0-9]{20,})", re.IGNORECASE),
    re.compile(r"(Bearer\s+[a-zA-Z0-9_\-\.]{20,})", re.IGNORECASE),
    re.compile(r"(key=[\"']?)([a-zA-Z0-9_\-]{16,})([\"']?)", re.IGNORECASE),
    re.compile(r"(password=[\"']?)([^&\"'\s]{4,})([\"']?)", re.IGNORECASE),
    re.compile(r"(pin=[\"']?)([0-9]{4,8})([\"']?)", re.IGNORECASE),
]


def sanitize_log_message(msg: str) -> str:
    """Replaces sensitive API tokens and credentials with masked placeholders."""
    if not isinstance(msg, str):
        return str(msg)
    
    sanitized = msg
    for pattern in SECRET_PATTERNS:
        sanitized = pattern.sub(r"[REDACTED_SECRET]", sanitized)
    return sanitized


class SecretMaskingLogFilter(logging.Filter):
    """Logging filter that scrubs sensitive keys and passwords from all log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = sanitize_log_message(record.msg)
        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(sanitize_log_message(str(a)) for a in record.args)
            elif isinstance(record.args, dict):
                record.args = {k: sanitize_log_message(str(v)) for k, v in record.args.items()}
        return True


class StructuredAuditLogger:
    """Appends structured JSON events to audit.jsonl for observability and future analytics."""

    def __init__(self, log_path: Path = AUDIT_LOG_FILE):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_event(
        self,
        event: str,
        module: str,
        level: str = "INFO",
        lead_id: Optional[str] = None,
        duration_ms: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Records an event with structured JSON metadata."""
        record = {
            "timestamp": datetime.now().isoformat(),
            "level": level.upper(),
            "module": module,
            "event": event,
            "lead_id": lead_id,
            "duration_ms": round(duration_ms, 2) if duration_ms is not None else None,
            "metadata": metadata or {}
        }

        # Ensure no sensitive fields exist in metadata
        sanitized_record = self._sanitize_dict(record)

        try:
            line = json.dumps(sanitized_record, ensure_ascii=False)
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception as e:
            # Fallback to standard logging if file write fails
            logging.getLogger("structured_logger").error(f"Audit log write failed: {e}")

    def _sanitize_dict(self, data: Any) -> Any:
        if isinstance(data, dict):
            clean = {}
            for k, v in data.items():
                if any(sec in k.lower() for sec in ["secret", "password", "api_key", "pin", "token"]):
                    clean[k] = "[REDACTED]"
                else:
                    clean[k] = self._sanitize_dict(v)
            return clean
        elif isinstance(data, list):
            return [self._sanitize_dict(item) for item in data]
        elif isinstance(data, str):
            return sanitize_log_message(data)
        return data

    def get_recent_events(self, limit: int = 50) -> list:
        """Reads recent structured events from audit.jsonl in reverse chronological order."""
        if not self.log_path.exists():
            return []
        
        events = []
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for line in reversed(lines[-limit:]):
                    line = line.strip()
                    if line:
                        try:
                            events.append(json.loads(line))
                        except Exception:
                            continue
        except Exception:
            pass
        return events


# Global singleton instance
audit_logger = StructuredAuditLogger()
