from enum import Enum
from typing import List, Dict, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field

class CRMStage(str, Enum):
    FOUND = "FOUND"
    AUDITED = "AUDITED"
    EMAIL_PREPARED = "EMAIL_PREPARED"
    SENT = "SENT"
    OPENED = "OPENED"
    REPLIED = "REPLIED"
    MEETING = "MEETING"
    WON = "WON"
    LOST = "LOST"

class StageTransition(BaseModel):
    id: Optional[int] = None
    lead_id: str
    from_stage: Optional[str] = None
    to_stage: str
    notes: Optional[str] = None
    transitioned_at: str = Field(default_factory=lambda: datetime.now().isoformat())

class LeadNote(BaseModel):
    id: Optional[int] = None
    lead_id: str
    author: str = "Sales Rep"
    note_text: str
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

class CRMStageManager:
    """Manages lead qualification lifecycle, stage progression, and conversion analytics."""

    ORDERED_STAGES = [
        CRMStage.FOUND,
        CRMStage.AUDITED,
        CRMStage.EMAIL_PREPARED,
        CRMStage.SENT,
        CRMStage.OPENED,
        CRMStage.REPLIED,
        CRMStage.MEETING,
        CRMStage.WON,
    ]

    STAGE_DESCRIPTIONS = {
        CRMStage.FOUND: "Discovered via Maps/Search; awaiting technical inspection",
        CRMStage.AUDITED: "Evidence Graph and Digital Maturity audit complete",
        CRMStage.EMAIL_PREPARED: "Personalized omnichannel copy and PDF report staged in queue",
        CRMStage.SENT: "Outbound touch dispatched to practice decision maker",
        CRMStage.OPENED: "Prospect engagement detected (email opened or link clicked)",
        CRMStage.REPLIED: "Positive or inquiry reply received from clinic",
        CRMStage.MEETING: "Growth strategy demonstration meeting booked or held",
        CRMStage.WON: "Contract signed, recurring retainer and setup fee closed",
        CRMStage.LOST: "Disqualified, unresponsive, or opted out"
    }

    @classmethod
    def validate_stage(cls, stage_name: str) -> CRMStage:
        stage_upper = stage_name.upper().strip()
        try:
            return CRMStage(stage_upper)
        except ValueError:
            valid = [s.value for s in CRMStage]
            raise ValueError(f"Invalid CRM Stage '{stage_name}'. Valid stages: {valid}")
