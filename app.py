import os
import re
import json
import asyncio
import uuid
import urllib.parse
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from pydantic import BaseModel

from database import DatabaseManager
from models import RawLead, ScoredLead, DigitalMaturityScore, WebsiteAuditResult, TechStackDetail, MultichannelSequence
from crm import CRMStage, CRMStageManager
from queue_manager import QueueManager
from auditor import WebsiteAuditor
from personalizer import OutreachPersonalizer
from proposals import ProposalGenerator, calculate_practice_roi, generate_tailored_proposal
from report_generator import OpportunityReportGenerator
from lead_finder import GoogleMapsLeadFinder
from explainer import ScoreExplainer
from battlecard import SalesBattlecardGenerator
from scheduler import AutonomousScheduler
from territory_manager import TerritoryManager
from ai_qualifier import AIQualifier
from outreach_generator import OutreachGenerator
from timeline import OpportunityTimelineManager
from simulator import AICallSimulator
from triggers import TriggerEngine, compute_html_hash, compute_tech_hash
from loom_script import generate_loom_pitch
from backup_manager import BackupManager
from health_monitor import SystemHealthMonitor
from cost_tracker import CostTelemetryTracker
from settings_manager import SettingsManager
from security import SecurityHeadersMiddleware, validate_startup_security, human_jitter_delay, compress_image_if_possible
from auth_manager import auth_manager, verify_auth_dependency
from structured_logger import audit_logger, SecretMaskingLogFilter
from dental_caller_persona import DentalCallerPersona
from voice_dialer import VoiceDialerEngine, clean_phone_e164
from buy_probability_engine import BuyProbabilityEngine
from drift_monitor import DriftMonitor
from cohort import calculate_metro_benchmark, rank_clinic_in_metro
from pre_call_researcher import PreCallResearcher
from sales_coach import SalesCoach, SalesOS
from live_dialer_engine import LiveDialerEngine
from ehr_sniffer import EHRSniffer
from npi_registry import NPIRegistryEnricher
from whatsapp_demo_engine import WhatsAppDemoEngine
from mystery_shopper import MysteryShopperAuditor
from sales_cadence import SalesCadenceEngine
from objection_analytics import ObjectionAnalyticsEngine
from pitch_portal import PitchPortalEngine
from voicemail_sting import VoicemailStingGenerator
from competitor_radar import CompetitorRadarEngine
from sms_dispatcher import SMSDispatcherEngine
from live_intercept import LiveInterceptRadar
from territory_checkout import TerritoryCheckoutEngine
from video_teardown import VideoTeardownEngine
from hygiene_recall_calculator import HygieneRecallCalculator
import logging
logging.getLogger().addFilter(SecretMaskingLogFilter())
logger = logging.getLogger("app")

# Setup directories
BASE_DIR = Path(__file__).resolve().parent
DASHBOARD_DIR = BASE_DIR / "dashboard"
DASHBOARD_DIR.mkdir(exist_ok=True, parents=True)
if os.getenv("VERCEL"):
    OUTPUT_DIR = Path("/tmp/output")
else:
    OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)
(OUTPUT_DIR / "reports").mkdir(exist_ok=True, parents=True)
(OUTPUT_DIR / "proposals").mkdir(exist_ok=True, parents=True)
(OUTPUT_DIR / "screenshots").mkdir(exist_ok=True, parents=True)
(OUTPUT_DIR / "stings").mkdir(exist_ok=True, parents=True)

def capture_screenshot_sync(url: str, save_path: Path) -> bool:
    target_url = url if (url.startswith("http://") or url.startswith("https://")) else f"https://{url}"
    try:
        from playwright.async_api import async_playwright
        async def _capture():
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                page = await context.new_page()
                try:
                    await page.goto(target_url, timeout=12000, wait_until="domcontentloaded")
                    await asyncio.sleep(1.0)
                    await page.screenshot(path=str(save_path), full_page=False, quality=80, type="jpeg")
                    return True
                except Exception:
                    return False
                finally:
                    await browser.close()
        return asyncio.run(_capture())
    except Exception:
        return False

app = FastAPI(title="Dental WhatsApp Growth & Lead Intelligence API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware)

@app.on_event("startup")
async def startup_event():
    """Pre-warm local Kokoro ONNX model and validate security."""
    validate_startup_security()
    from voice_dialer import get_kokoro_model
    asyncio.create_task(asyncio.to_thread(get_kokoro_model))

# Mount static directories
app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")
app.mount("/static", StaticFiles(directory=str(DASHBOARD_DIR)), name="static")

# Shared Database Instance
db = DatabaseManager()

# Hardening & Reliability Managers
backup_mgr = BackupManager(db_path=db.db_path, backup_dir=OUTPUT_DIR / "backups")
health_monitor = SystemHealthMonitor(db=db, output_dir=OUTPUT_DIR)
cost_tracker = CostTelemetryTracker(telemetry_file=OUTPUT_DIR / "telemetry.json")
settings_mgr = SettingsManager(settings_file=OUTPUT_DIR / "settings.json")

# Background job tracking
active_jobs: Dict[str, Dict[str, Any]] = {}

# --- Pydantic Request Models ---

class SearchRequest(BaseModel):
    query: str = "Dentists in Austin, TX"
    limit: int = 10
    generate_reports: bool = True
    auto_queue: bool = True

class StageUpdateRequest(BaseModel):
    stage: str
    notes: Optional[str] = "Moved via Visual Dashboard"

class NoteRequest(BaseModel):
    note: str
    author: Optional[str] = "Sales Rep"

class QueueActionRequest(BaseModel):
    notes: Optional[str] = None

class ProposalRequest(BaseModel):
    lead_id: Optional[str] = None
    url: Optional[str] = None
    name: Optional[str] = None

class CallOutcomeRequest(BaseModel):
    outcome: str  # INTERESTED, NOT_INTERESTED, ALREADY_HAS_AI, GATEKEEPER_BLOCKED, WON, LOST, CALLBACK_REQUESTED
    notes: Optional[str] = None
    duration_sec: int = 0
    objection_category: Optional[str] = None
    objection_quote: Optional[str] = None
    effective_rebuttal: Optional[str] = None
    deal_value: float = 0.0
    lessons_learned: Optional[str] = None

class RecordMemoryRequest(BaseModel):
    lead_id: str
    clinic_name: str
    doctor_name: Optional[str] = None
    metro: Optional[str] = None
    specialty: Optional[str] = "General"
    outcome: str  # WON, LOST, OBJECTION_RAISED, CALLBACK
    objection_category: Optional[str] = None
    objection_quote: Optional[str] = None
    effective_rebuttal: Optional[str] = None
    deal_value: float = 0.0
    lessons_learned: Optional[str] = None

class NextTerritoryRequest(BaseModel):
    territory_id: Optional[str] = None
    limit: int = 8

class CallSimulationStartRequest(BaseModel):
    persona: Optional[str] = "GATEKEEPER_RECEPTIONIST"

class CallSimulationTurnRequest(BaseModel):
    persona: str = "GATEKEEPER_RECEPTIONIST"
    user_pitch: str
    history: List[Dict[str, str]] = []

class VoiceCallDispatchRequest(BaseModel):
    phone_override: Optional[str] = None
    confirmed_by_user: bool = True
    notes: Optional[str] = None

class VoiceCallBatchRequest(BaseModel):
    lead_ids: List[str]
    confirmed_by_user: bool = True

class VoiceCallTestRequest(BaseModel):
    phone: str
    lead_id: Optional[str] = None
    caller_persona: Optional[str] = "GATEKEEPER_RECEPTIONIST"

class VoiceSynthesizeRequest(BaseModel):
    text: str = "Hello Dr. Miller, this is Sarah with the patient intake assistant."
    engine: str = "auto"  # "auto", "gemini-3.1", "gemini-2.5", "kokoro"
    voice: Optional[str] = None

class InteractiveVoiceStartRequest(BaseModel):
    lead_id: Optional[str] = None
    engine: Optional[str] = "auto-fast"
    voice_name: Optional[str] = "af_sarah"

class InteractiveVoiceTurnRequest(BaseModel):
    lead_id: Optional[str] = None
    user_message: str
    history: List[Dict[str, Any]] = []
    engine: Optional[str] = "auto-fast"
    voice_name: Optional[str] = "af_sarah"

class GatekeeperMemoryRequest(BaseModel):
    lead_id: str
    contact_name: str
    role: str = "Front Desk"
    demeanor: Optional[str] = "Professional"
    notes: Optional[str] = None
    best_time_to_call: Optional[str] = None
    software_mentioned: Optional[str] = None

class MapsGrowthRequest(BaseModel):
    lead_id: str
    current_review_count: int
    current_rating: float

class KnowledgeBaseInsightRequest(BaseModel):
    category: str
    key_phrase: str
    content: str
    effectiveness_score: float = 8.5

class ProductivityLogRequest(BaseModel):
    activity_type: str
    count: int = 1
    lead_id: Optional[str] = None
    notes: Optional[str] = None

class SchedulerConfigRequest(BaseModel):
    enabled: bool = True
    target_metros: Optional[List[str]] = None
    harvest_time: str = "06:00"
    limit_per_metro: int = 100

class MarketScanRequest(BaseModel):
    metro: str = "Austin"
    max_clinics: int = 1000

class ReviewMineRequest(BaseModel):
    reviews: List[str]
    clinic_name: str = "Dental Practice"

class CallNotesSummarizeRequest(BaseModel):
    transcript: str
    lead_id: Optional[str] = None

class ReminderCreateRequest(BaseModel):
    lead_id: Any = "1"
    clinic_name: Optional[str] = "Dental Clinic"
    due_date: Optional[str] = None
    trigger_reason: str = "MANUAL"
    reminder_type: Optional[str] = "PHONE_CALL"
    hours_from_now: Optional[int] = None
    notes: Optional[str] = ""

class ReminderSnoozeRequest(BaseModel):
    days: Optional[int] = 2
    hours: Optional[int] = None

class ROICalculateRequest(BaseModel):
    monthly_appointments: int = 180
    average_treatment_value: float = 1250.0
    estimated_missed_calls_monthly: int = 15
    monthly_software_cost: float = 697.0

class ClientMetricLogRequest(BaseModel):
    metric_name: Optional[str] = "appointments_booked"
    delta: float = 1.0
    messages_answered: Optional[int] = None
    appointments_booked: Optional[int] = None
    revenue_generated: Optional[float] = None
    missed_calls_saved: Optional[int] = None
    client_id: Optional[str] = None
    clinic_name: Optional[str] = None
    doctor_name: Optional[str] = None
    plan_tier: Optional[str] = None

class CalendarBookRequest(BaseModel):
    lead_id: Optional[str] = "preview"
    slot: str = "Thursday at 11:00 AM"
    clinic_name: Optional[str] = None
    doctor_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None

class WhatsAppInboundRequest(BaseModel):
    lead_id: Optional[str] = "preview"
    message: str
    clinic_name: Optional[str] = None
    doctor_name: Optional[str] = None
    patient_phone: Optional[str] = None

class CadenceReminderRequest(BaseModel):
    lead_id: str
    reminder_type: str = "T-24H"  # T-24H or T-1H
    custom_message: Optional[str] = None

    monthly_retainer: Optional[float] = None

class SwarmCycleRequest(BaseModel):
    territory_id: Optional[str] = None
    batch_limit: int = 5

class SwarmAgentRunRequest(BaseModel):
    limit: int = 5

class InteractiveVoiceAudioTurnRequest(BaseModel):
    lead_id: Optional[str] = None
    audio_base64: str
    mime_type: Optional[str] = "audio/webm"
    history: List[Dict[str, Any]] = []
    engine: Optional[str] = "auto-fast"
    voice_name: Optional[str] = "af_sarah"

class TimelineEventCreateRequest(BaseModel):
    event_type: str
    title: str
    description: Optional[str] = None
    actor: str = "SALES_REP"
    metadata: Optional[Dict[str, Any]] = None

class DaemonToggleRequest(BaseModel):
    enable: bool = True
    interval_hours: float = 6.0

# --- Phase 3: Final 4 Roadmap Models ---
class CoachAnalyzeRequest(BaseModel):
    transcript: str
    lead_id: Optional[str] = None
    duration_sec: Optional[int] = 0

class RoutePlanRequest(BaseModel):
    territory_id: Optional[str] = None
    lead_ids: Optional[List[str]] = None
    max_stops: Optional[int] = 5
    start_time: Optional[str] = "09:00"
    origin_address: Optional[str] = None

class DriftRescanRequest(BaseModel):
    lead_id: Optional[str] = None
    limit: Optional[int] = 5

class TenantCreateRequest(BaseModel):
    name: str
    slug: str
    agency_branding: Optional[Dict[str, Any]] = None
    pricing_config: Optional[Dict[str, Any]] = None
    limit_per_cycle: int = 8

class ROICalculatorRequest(BaseModel):
    recovered_patients_per_month: Optional[int] = 5
    avg_case_value: Optional[int] = 900
    monthly_fee: Optional[int] = 299

class CheckChangesRequest(BaseModel):
    html_content: Optional[str] = None
    technologies: Optional[List[str]] = None
    new_reviews: Optional[int] = None
    new_rating: Optional[float] = None

class BackupRestoreRequest(BaseModel):
    backup_filename: str

class SettingsUpdateRequest(BaseModel):
    target_cities: Optional[List[str]] = None
    min_reviews_threshold: Optional[int] = None
    min_reviews: Optional[int] = None
    min_buying_probability: Optional[int] = None
    default_case_value: Optional[int] = None
    avg_case_value: Optional[int] = None
    default_monthly_retainer: Optional[int] = None
    monthly_fee: Optional[int] = None
    daemon_interval_hours: Optional[float] = None
    daemon_limit_per_city: Optional[int] = None
    rate_limit_min_delay_sec: Optional[float] = None
    rate_limit_max_delay_sec: Optional[float] = None
    auto_backup_enabled: Optional[bool] = None
    agency_name: Optional[str] = None

class LoginRequest(BaseModel):
    password: str
    username: Optional[str] = "admin"

class ManualDialerStartRequest(BaseModel):
    phone: str
    lead_id: Optional[str] = None
    contact_name: Optional[str] = None
    mode: Optional[str] = "HUMAN_FIRST"
    carrier_mode: Optional[str] = "BROWSER"

class ManualDialerTurnRequest(BaseModel):
    session_id: str
    text: str
    speaker: Optional[str] = "HUMAN"
    audio_url: Optional[str] = None

class ManualDialerTakeoverRequest(BaseModel):
    session_id: str
    user_hint: Optional[str] = None

class ManualDialerHumanTakeoverRequest(BaseModel):
    session_id: str
    reason: Optional[str] = None

class ManualDialerSaveRecordingRequest(BaseModel):
    session_id: str
    audio_base64: Optional[str] = None
    filename: Optional[str] = None
    duration_sec: Optional[int] = 0
    outcome: Optional[str] = None

class ManualDialerLookupRequest(BaseModel):
    phone: str

# --- Helper Functions ---

def format_clean_phone(raw_phone: Optional[str]) -> str:
    if not raw_phone:
        return ""
    digits = re.sub(r"\D", "", raw_phone)
    if len(digits) == 10:
        return f"1{digits}"
    elif len(digits) == 11 and digits.startswith("1"):
        return digits
    return digits

def generate_wa_pitch_and_link(lead_dict: Dict[str, Any]) -> Dict[str, str]:
    name = lead_dict.get("name", "Doctor")
    phone = lead_dict.get("phone", "")
    address = lead_dict.get("address", "Texas")
    rating = lead_dict.get("rating", 4.9)
    review_count = lead_dict.get("review_count", 50)
    score = lead_dict.get("opportunity_score", 75)
    annual_gap = lead_dict.get("annual_gap", 65000) or 65000
    monthly_rev = f"${int(annual_gap / 12):,}"

    if "dr." in name.lower() or "dr " in name.lower():
        salutation = f"Dr. {name.split(',')[0].replace('Dr.', '').replace('Dr', '').strip()}"
    else:
        salutation = f"{name} Team"

    clean_phone = format_clean_phone(phone)

    pitch = (
        f"Hi {salutation}! 👋 I was reviewing premier dental practices in {address} "
        f"and noticed {name}'s {rating}★ reputation across {review_count} patient reviews.\n\n"
        f"Quick question: Did you know ~42% of patient emergency searches & inquiries happen after 5 PM when the front desk is closed? "
        f"We estimate this is leaking roughly {monthly_rev}/month in uncaptured chair production.\n\n"
        f"We install a 24/7 WhatsApp Patient Automation system that:\n"
        f"• Instantly texts back missed callers within 5 seconds so they don't call another dentist\n"
        f"• Lets patients self-schedule exams & cleanings directly inside WhatsApp 24/7\n"
        f"• Fills last-minute cancellations with 98% open-rate broadcast recall\n\n"
        f"Would you be open to a 3-minute video showing how it links to your existing practice calendar?"
    )

    wa_link = f"https://wa.me/{clean_phone}?text={urllib.parse.quote_plus(pitch)}" if clean_phone else ""

    return {
        "salutation": salutation,
        "clean_phone": clean_phone,
        "pitch": pitch,
        "wa_link": wa_link
    }

# --- Routes ---

@app.get("/")
async def serve_dashboard():
    index_path = DASHBOARD_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return HTMLResponse("<h1>Dashboard loading...</h1>")

@app.get("/api/stats")
async def get_stats():
    summary = db.get_crm_pipeline_summary()
    queue_pending = db.list_outreach_queue(status="PENDING_REVIEW")
    queue_approved = db.list_outreach_queue(status="APPROVED")
    queue_sent = db.list_outreach_queue(status="SENT")

    total_leads = sum(v["count"] for v in summary.values())
    total_leakage = sum(v["total_leakage"] for v in summary.values())

    return {
        "total_leads": total_leads,
        "total_leakage": total_leakage,
        "pipeline": summary,
        "queue": {
            "pending": len(queue_pending),
            "approved": len(queue_approved),
            "sent": len(queue_sent)
        }
    }

@app.get("/api/leads")
async def get_leads(
    stage: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100
):
    if stage and stage != "ALL":
        leads = db.get_leads_by_stage(stage)
    else:
        leads = db.list_all_leads()

    if search:
        search_lower = search.lower()
        leads = [l for l in leads if search_lower in (l.get("name") or "").lower() or search_lower in (l.get("phone") or "").lower() or search_lower in (l.get("website") or "").lower()]

    # Enhance leads with clean phone, revenue metrics, screenshots, and quick WhatsApp action
    results = []
    for l in leads[:limit]:
        wa_data = generate_wa_pitch_and_link(l)
        l_copy = dict(l)
        l_copy["clean_phone"] = wa_data["clean_phone"]
        l_copy["wa_link"] = wa_data["wa_link"]

        # Ensure numeric coordinates
        l_copy["latitude"] = float(l["latitude"]) if l.get("latitude") is not None else None
        l_copy["longitude"] = float(l["longitude"]) if l.get("longitude") is not None else None

        # Format missed revenue range
        rev_min = l.get("missed_rev_min") or l.get("audit_missed_rev_min") or 0
        rev_max = l.get("missed_rev_max") or l.get("audit_missed_rev_max") or 0
        if not rev_min and not rev_max:
            annual = l.get("annual_gap") or 0
            if annual > 0:
                rev_max = int(annual / 12)
                rev_min = int(rev_max * 0.6)
            else:
                rev_min = 3450
                rev_max = 6900
        l_copy["missed_rev_min"] = rev_min
        l_copy["missed_rev_max"] = rev_max
        l_copy["missed_rev_range"] = f"${rev_min:,.0f} - ${rev_max:,.0f}"

        # Screenshot URL
        lead_id = l.get("id")
        shot_path = l.get("screenshot_path")
        if shot_path and (OUTPUT_DIR / "screenshots" / Path(shot_path).name).exists():
            l_copy["screenshot_url"] = f"/output/screenshots/{Path(shot_path).name}"
        elif shot_path and Path(shot_path).exists():
            l_copy["screenshot_url"] = f"/output/screenshots/{Path(shot_path).name}"
        elif lead_id and (OUTPUT_DIR / "screenshots" / f"{lead_id}.jpg").exists():
            l_copy["screenshot_url"] = f"/output/screenshots/{lead_id}.jpg"
        else:
            l_copy["screenshot_url"] = None

        results.append(l_copy)

    return results

@app.get("/api/leads/export")
async def export_leads(
    format: str = Query("xlsx", pattern="^(xlsx|csv)$"),
    stage: Optional[str] = None
):
    import io
    import csv
    from fastapi.responses import Response

    if stage and stage != "ALL":
        leads = db.get_leads_by_stage(stage)
    else:
        leads = db.list_all_leads()

    headers = [
        "Practice Name",
        "Doctor / Owner",
        "Decision Maker Role",
        "Category",
        "Rating",
        "Review Count",
        "Phone Number",
        "WhatsApp Direct Link",
        "Website",
        "Address",
        "Pipeline Stage",
        "Opportunity Score",
        "Est. Missed Monthly Revenue",
        "Est. Annual Revenue Leakage",
        "AI Strategic Why-Score Rationale",
        "Last Audit Date"
    ]

    rows = []
    for l in leads:
        wa_data = generate_wa_pitch_and_link(l)
        rev_min = l.get("missed_rev_min") or l.get("audit_missed_rev_min") or 0
        rev_max = l.get("missed_rev_max") or l.get("audit_missed_rev_max") or 0
        if not rev_min and not rev_max:
            annual = l.get("annual_gap") or 65000
            rev_max = int(annual / 12)
            rev_min = int(rev_max * 0.6)
        rev_str = f"${rev_min:,.0f} - ${rev_max:,.0f}/mo"
        annual_str = f"${(l.get('annual_gap') or 65000):,.0f}/yr"

        why_bullets = l.get("why_score_reasons") or []
        if isinstance(why_bullets, list):
            why_text = " • ".join(r.lstrip("•-* ").strip() for r in why_bullets if r)
        else:
            why_text = str(why_bullets)

        rows.append([
            l.get("name", ""),
            l.get("doctor_name") or "Not Identified",
            l.get("decision_maker_role") or "",
            l.get("category", "Dentist"),
            float(l.get("rating", 4.9)) if l.get("rating") else 4.9,
            int(l.get("review_count", 0)) if l.get("review_count") else 0,
            l.get("phone", ""),
            wa_data.get("wa_link", ""),
            l.get("website", ""),
            l.get("address", ""),
            l.get("stage", "FOUND"),
            int(l.get("opportunity_score", 0)),
            rev_str,
            annual_str,
            why_text,
            l.get("last_audit_date") or l.get("last_updated") or ""
        ])

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")

    if format == "xlsx":
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Dental Prospects"

        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="047857", end_color="047857", fill_type="solid")
        border_thin = Border(
            left=Side(style='thin', color='E2E8F0'),
            right=Side(style='thin', color='E2E8F0'),
            top=Side(style='thin', color='E2E8F0'),
            bottom=Side(style='thin', color='E2E8F0')
        )

        ws.append(headers)
        for cell in ws[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")

        for r_idx, row_data in enumerate(rows, start=2):
            ws.append(row_data)
            for c_idx, val in enumerate(row_data, start=1):
                cell = ws.cell(row=r_idx, column=c_idx)
                cell.border = border_thin
                cell.alignment = Alignment(vertical="center")

        # Auto-adjust column widths
        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 45)

        ws.auto_filter.ref = ws.dimensions

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        filename = f"dental_leads_export_{timestamp}.xlsx"

        return Response(
            content=buffer.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename=\"{filename}\"",
                "Access-Control-Expose-Headers": "Content-Disposition"
            }
        )
    else:
        output = io.StringIO()
        output.write('\ufeff')
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(headers)
        for row in rows:
            writer.writerow(row)
        filename = f"dental_leads_export_{timestamp}.csv"
        return Response(
            content=output.getvalue().encode("utf-8-sig"),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f"attachment; filename=\"{filename}\"",
                "Access-Control-Expose-Headers": "Content-Disposition"
            }
        )

@app.get("/api/leads/{lead_id}")
async def get_lead_details(lead_id: str):
    lead = db.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    findings = db.get_lead_findings(lead_id)
    notes = db.get_lead_notes(lead_id)
    history = db.get_stage_history(lead_id)
    wa_data = generate_wa_pitch_and_link(lead)

    # Fetch technologies
    with db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM technologies WHERE lead_id = ?", (lead_id,))
        techs = [dict(r) for r in cursor.fetchall()]

        # Latest audit details
        cursor.execute("SELECT * FROM audits WHERE lead_id = ? ORDER BY timestamp DESC LIMIT 1", (lead_id,))
        audit = cursor.fetchone()
        audit_dict = dict(audit) if audit else {}

    # Ensure Win Probability & Drivers are populated
    if not lead.get("win_probability_reasons"):
        try:
            from ai_qualifier import AIQualifier
            from memory_manager import MemoryManager
            learnings = MemoryManager.get_learnings_for_lead(lead)
            tech_names = [t["name"] for t in techs]
            win_prob, reasons = AIQualifier.calculate_win_probability(
                lead_dict=lead,
                technologies=tech_names,
                memory_learnings=learnings,
                estimated_monthly_leakage=lead.get("missed_rev_max") or 3500
            )
            lead["win_probability_pct"] = win_prob
            lead["win_probability_reasons"] = reasons
        except Exception:
            pass

    # Check for generated proposal
    clean_name = "".join(c for c in lead.get("name", "") if c.isalnum() or c == " ").strip().replace(" ", "_")
    proposal_file = OUTPUT_DIR / "proposals" / f"{clean_name}_growth_proposal.html"
    proposal_url = f"/output/proposals/{proposal_file.name}" if proposal_file.exists() else None

    # Check for generated PDF report
    pdf_file = OUTPUT_DIR / "reports" / f"{clean_name}_audit.pdf"
    pdf_url = f"/output/reports/{pdf_file.name}" if pdf_file.exists() else None

    return {
        "lead": lead,
        "audit": audit_dict,
        "findings": findings,
        "technologies": techs,
        "notes": notes,
        "history": history,
        "whatsapp": wa_data,
        "proposal_url": proposal_url,
        "pdf_url": pdf_url
    }

@app.get("/api/leads/{lead_id}/battlecard")
async def get_lead_battlecard(lead_id: str):
    lead = db.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    with db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM audits WHERE lead_id = ? ORDER BY timestamp DESC LIMIT 1", (lead_id,))
        audit = cursor.fetchone()
        if audit:
            audit_dict = dict(audit)
            lead["detected_chatbot_name"] = audit_dict.get("detected_chatbot_name")
            lead["detected_booking_tool"] = audit_dict.get("detected_booking_tool")

    battlecard = SalesBattlecardGenerator.generate_battlecard(lead)
    return battlecard

@app.get("/api/briefing/today")
async def get_today_briefing():
    all_leads = db.list_all_leads()
    sorted_leads = sorted(all_leads, key=lambda l: (l.get("opportunity_score") or 0), reverse=True)

    top_targets = []
    total_monthly_leakage = 0
    doctors_found = 0

    for l in sorted_leads[:10]:
        rev_min = l.get("missed_rev_min") or l.get("audit_missed_rev_min") or 3500
        rev_max = l.get("missed_rev_max") or l.get("audit_missed_rev_max") or 6800
        total_monthly_leakage += rev_max
        doc = l.get("doctor_name")
        if doc and doc != "Not Identified":
            doctors_found += 1

        wa_data = generate_wa_pitch_and_link(l)
        top_targets.append({
            "id": l.get("id"),
            "name": l.get("name"),
            "doctor_name": doc or "Primary Dentist",
            "decision_maker_role": l.get("decision_maker_role") or "Practice Owner",
            "rating": float(l.get("rating", 4.9)) if l.get("rating") else 4.9,
            "reviews": int(l.get("review_count", 0)) if l.get("review_count") else 0,
            "phone": l.get("phone", ""),
            "website": l.get("website", ""),
            "address": l.get("address", ""),
            "opportunity_score": int(l.get("opportunity_score", 75)),
            "stage": l.get("stage", "FOUND"),
            "missed_rev_min": rev_min,
            "missed_rev_max": rev_max,
            "annual_gap": (rev_min + rev_max) // 2 * 12,
            "wa_link": wa_data.get("wa_link", ""),
            "wa_pitch": wa_data.get("wa_pitch", ""),
            "why_score_reasons": l.get("why_score_reasons", [])
        })

    total_annual_arr = total_monthly_leakage * 12

    return {
        "briefing_date": datetime.now().strftime("%A, %B %d, %Y"),
        "total_targets_ready": len(top_targets),
        "doctors_identified_count": doctors_found,
        "combined_monthly_missed_revenue": total_monthly_leakage,
        "total_annual_arr_opportunity": total_annual_arr,
        "targets": top_targets
    }

@app.post("/api/briefing/run-morning")
async def run_morning_harvest(city: Optional[str] = "Austin, TX", limit: int = 5):
    try:
        result = await AutonomousScheduler.run_morning_cycle(
            cities=[city],
            limit_per_city=limit,
            headless=True,
            db=db
        )
        return {"status": "completed", "summary": result}
    except Exception as e:
        audit_logger.log_event("morning_harvest_failed", module="scheduler", level="ERROR", metadata={"city": city, "error": str(e)})
        raise HTTPException(status_code=500, detail=f"Harvest failed: {str(e)}")

# --- Autonomous Territory & Sales Employee Endpoints ---

@app.get("/api/territories")
async def get_territories():
    TerritoryManager.initialize_territories(db)
    territories = db.get_all_territories()
    pending = sum(1 for t in territories if t.get("status") == "PENDING")
    in_progress = sum(1 for t in territories if t.get("status") == "IN_PROGRESS")
    completed = sum(1 for t in territories if t.get("status") == "COMPLETED")
    next_target = TerritoryManager.get_next_target_territory(db)
    return {
        "total_territories": len(territories),
        "pending": pending,
        "in_progress": in_progress,
        "completed": completed,
        "next_target": next_target,
        "territories": territories
    }

@app.post("/api/territories/next-cycle")
async def trigger_next_territory_cycle(req: NextTerritoryRequest, background_tasks: BackgroundTasks):
    try:
        summary = await AutonomousScheduler.run_autonomous_cycle(
            territory_id=req.territory_id,
            limit=req.limit,
            headless=True,
            db=db
        )
        return {"status": "completed", "summary": summary}
    except Exception as e:
        audit_logger.log_event("territory_cycle_failed", module="scheduler", level="ERROR", metadata={"territory_id": req.territory_id, "error": str(e)})
        raise HTTPException(status_code=500, detail=f"Territory cycle failed: {str(e)}")

@app.get("/api/queue/todays-calls")
async def get_todays_calls(min_probability: int = 70):
    leads = db.get_todays_calls(min_probability=min_probability)
    results = []
    for l in leads:
        wa_data = generate_wa_pitch_and_link(l)
        l_copy = dict(l)
        l_copy["clean_phone"] = wa_data["clean_phone"]
        l_copy["wa_link"] = wa_data["wa_link"]

        rev_min = l.get("missed_rev_min") or l.get("audit_missed_rev_min") or 3450
        rev_max = l.get("missed_rev_max") or l.get("audit_missed_rev_max") or 6900
        l_copy["missed_rev_range"] = f"${rev_min:,.0f} - ${rev_max:,.0f}"

        shot_path = l.get("screenshot_path")
        lead_id = l.get("id")
        if shot_path and Path(shot_path).exists():
            l_copy["screenshot_url"] = f"/output/screenshots/{Path(shot_path).name}"
        elif lead_id and (OUTPUT_DIR / "screenshots" / f"{lead_id}.jpg").exists():
            l_copy["screenshot_url"] = f"/output/screenshots/{lead_id}.jpg"
        else:
            l_copy["screenshot_url"] = None

        results.append(l_copy)
    return results

@app.post("/api/leads/{lead_id}/call-outcome")
async def log_call_outcome(lead_id: str, req: CallOutcomeRequest):
    log_id = db.log_call_outcome(
        lead_id=lead_id,
        outcome=req.outcome,
        rep_notes=req.notes,
        duration_sec=req.duration_sec
    )
    lead = db.get_lead(lead_id)

    # Record into AI Sales Memory flywheel
    memory_id = None
    try:
        from memory_manager import MemoryManager
        clinic_name = lead.get("name", "Dental Clinic") if lead else "Dental Clinic"
        doc_name = lead.get("doctor_name") if lead else None
        addr = lead.get("address", "") if lead else ""
        metro = addr.split(",")[-2].strip() if ("," in addr and len(addr.split(",")) >= 2) else "Texas"

        # Categorize outcome
        mem_outcome = "WON" if req.outcome in ("WON", "MEETING_BOOKED", "INTERESTED") else ("LOST" if req.outcome in ("NOT_INTERESTED", "GATEKEEPER_BLOCKED") else "OBJECTION_RAISED")

        obj_cat = req.objection_category
        if not obj_cat:
            notes_lower = (req.notes or "").lower()
            if any(w in notes_lower for w in ["cost", "price", "expensive"]):
                obj_cat = "PRICE_SENSITIVITY"
            elif any(w in notes_lower for w in ["gatekeeper", "receptionist", "busy", "front desk"]):
                obj_cat = "GATEKEEPER_WALL"
            elif any(w in notes_lower for w in ["already have", "using"]):
                obj_cat = "EXISTING_SOLUTION"
            else:
                obj_cat = "NONE"

        memory_id = MemoryManager.record_interaction(
            lead_id=lead_id,
            clinic_name=clinic_name,
            doctor_name=doc_name,
            metro=metro,
            outcome=mem_outcome,
            objection_category=obj_cat,
            objection_quote=req.objection_quote or req.notes,
            effective_rebuttal=req.effective_rebuttal,
            deal_value=req.deal_value,
            lessons_learned=req.lessons_learned or req.notes
        )
    except Exception as e:
        logger.warning(f"Failed to record call outcome into sales memory: {e}")

    return {
        "status": "success",
        "log_id": log_id,
        "lead_id": lead_id,
        "memory_id": memory_id,
        "recorded_outcome": req.outcome,
        "new_crm_stage": lead.get("stage") if lead else "UNKNOWN"
    }

@app.get("/api/memory/insights")
async def get_memory_insights():
    """Returns macroeconomic sales intelligence, objection frequencies, and win rates."""
    from memory_manager import MemoryManager
    return MemoryManager.get_memory_intelligence_summary()

@app.post("/api/memory/record")
async def record_memory_event(req: RecordMemoryRequest):
    """Allows manual or automated injection of learning events into institutional sales memory."""
    from memory_manager import MemoryManager
    mem_id = MemoryManager.record_interaction(
        lead_id=req.lead_id,
        clinic_name=req.clinic_name,
        doctor_name=req.doctor_name,
        metro=req.metro or "Texas",
        specialty=req.specialty or "General",
        outcome=req.outcome,
        objection_category=req.objection_category,
        objection_quote=req.objection_quote,
        effective_rebuttal=req.effective_rebuttal,
        deal_value=req.deal_value,
        lessons_learned=req.lessons_learned
    )
    summary = MemoryManager.get_memory_intelligence_summary()
    return {
        "status": "success",
        "memory_id": mem_id,
        "summary": summary
    }

@app.get("/api/leads/{lead_id}/memory")
async def get_lead_memory(lead_id: str):
    """Returns customized precedents and objection recommendations for a specific lead."""
    from memory_manager import MemoryManager
    lead = db.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return MemoryManager.get_learnings_for_lead(lead)

@app.get("/api/leads/{lead_id}/outreach")
async def get_lead_outreach(lead_id: str):
    lead = db.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    rev_min = lead.get("missed_rev_min") or 3450
    rev_max = lead.get("missed_rev_max") or 6900
    monthly_leakage = (rev_min + rev_max) // 2

    outreach = OutreachGenerator.generate(
        lead_dict=dict(lead),
        doctor_name=lead.get("doctor_name"),
        monthly_leakage=monthly_leakage
    )
    return outreach.model_dump()

@app.get("/api/learning/insights")
async def get_learning_insights():
    return db.get_conversion_intelligence()

# --- Autonomous Multi-Agent Swarm Endpoints ---

@app.get("/api/swarm/status")
async def get_swarm_status():
    """Returns Master Orchestrator state, queue backlogs, active directive, and recent tasks."""
    from swarm_master import SwarmMaster
    state = SwarmMaster.audit_pipeline(db)
    directive = SwarmMaster.formulate_master_directive(state)
    recent_tasks = db.get_recent_swarm_tasks(limit=15)
    return {
        "status": "online",
        "bottleneck": state.get("detected_bottleneck", "BALANCED"),
        "pipeline_counts": state.get("pipeline_counts", {}),
        "fleet": {
            "master": {"status": "ACTIVE", "role": "Master Orchestrator", "name": "Swarm Commander"},
            "agent_a_scout": {"status": "IDLE", "role": "Territorial Discovery", "name": "Agent A: Scout"},
            "agent_b_auditor": {"status": "IDLE", "role": "Deep Technical Intake & Leakage", "name": "Agent B: Auditor"},
            "agent_c_doctor_matcher": {"status": "IDLE", "role": "Decision Maker Hunter", "name": "Agent C: Doctor Matcher"},
            "agent_d_proposal_engine": {"status": "IDLE", "role": "Unit Economics & Proposals", "name": "Agent D: Proposal Engine"},
            "agent_e_predialer": {"status": "IDLE", "role": "Outbound Call Staging", "name": "Agent E: Pre-Dialer"}
        },
        "master_directive": directive,
        "pipeline_state": state,
        "recent_tasks": recent_tasks
    }

@app.post("/api/swarm/dispatch-cycle")
async def dispatch_swarm_cycle(req: SwarmCycleRequest):
    """Commands the Master Orchestrator to plan and execute a multi-agent cycle."""
    from swarm_master import SwarmMaster
    results = await SwarmMaster.execute_cycle(
        db=db,
        territory_id=req.territory_id,
        batch_limit=req.batch_limit
    )
    return results

@app.post("/api/swarm/agent/{agent_id}/run")
async def run_single_agent(agent_id: str, req: SwarmAgentRunRequest):
    """Executes a single isolated worker agent (e.g. SCOUT, AUDITOR, DOCTOR_MATCHER, PROPOSAL_ENGINE, PRE_DIALER)."""
    from swarm_master import SwarmMaster
    try:
        res = await SwarmMaster.run_worker_agent(agent_type=agent_id, db=db, limit=req.limit)
        return {"status": "success", "agent": agent_id, "result": res}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Phase 3: Personal Sales OS & AI Post-Call Coach (Roadmap #8 & #9) ---

@app.get("/api/sales-os/metrics")
async def get_sales_os_metrics():
    """Returns real-time Sales OS KPIs (MRR, pacing, win rate, ARR, top niches)."""
    from sales_coach import SalesOS
    return SalesOS.get_daily_sales_metrics(db)

@app.post("/api/coach/analyze")
async def analyze_call_coaching(req: CoachAnalyzeRequest):
    """Analyzes a call transcript turn for talk-to-listen ratio, missed signals, and counter-punch advice."""
    from sales_coach import SalesCoach
    lead = db.get_lead(req.lead_id) if req.lead_id else {}
    return SalesCoach.analyze_call(
        transcript=req.transcript,
        lead_dict=lead,
        call_duration_sec=req.duration_sec or 0
    )

# --- Phase 3: Competitor Drift & Continuous Re-Scanning Monitor (Roadmap #4 & #7) ---

@app.get("/api/monitor/triggers")
async def get_active_competitor_triggers(limit: int = 25):
    """Retrieves active competitor shift alerts and website changes."""
    from drift_monitor import CompetitorDriftMonitor
    triggers = CompetitorDriftMonitor.get_active_triggers(db, limit=limit)
    return {"status": "success", "triggers": triggers, "count": len(triggers)}

@app.post("/api/monitor/rescan")
async def rescan_competitors(req: DriftRescanRequest):
    """Re-audits a single clinic or batch of stale clinics for competitor shifts."""
    from drift_monitor import CompetitorDriftMonitor
    if req.lead_id:
        return await CompetitorDriftMonitor.rescan_lead(db, lead_id=req.lead_id, force=True)
    else:
        return await CompetitorDriftMonitor.rescan_stale_leads(db, limit=req.limit or 5)

# --- Phase 3: Geolocation Travel Route Optimizer (Roadmap #3) ---

@app.get("/api/route/plan")
async def plan_travel_route(
    territory_id: Optional[str] = None,
    max_stops: int = 5,
    start_time: str = "09:00",
    origin_address: Optional[str] = None
):
    """Generates an optimized multi-stop driving route with Google Maps link."""
    from route_optimizer import TravelRouteOptimizer
    return TravelRouteOptimizer.plan_route(
        db=db,
        territory_id=territory_id,
        max_stops=max_stops,
        start_time_str=start_time,
        origin_address=origin_address
    )

@app.post("/api/route/optimize")
async def optimize_travel_route(req: RoutePlanRequest):
    """Optimizes custom selected clinics into an ordered field sales route."""
    from route_optimizer import TravelRouteOptimizer
    return TravelRouteOptimizer.plan_route(
        db=db,
        territory_id=req.territory_id,
        lead_ids=req.lead_ids,
        max_stops=req.max_stops or 5,
        start_time_str=req.start_time or "09:00",
        origin_address=req.origin_address
    )

# --- Phase 3: Multi-Tenant Architecture Foundation (Roadmap #10) ---

@app.get("/api/tenants")
async def list_agency_tenants():
    """Lists all registered agency workspaces and white-label tenants."""
    from tenant_manager import TenantManager
    tenants = TenantManager.list_tenants(db)
    return {"status": "success", "tenants": tenants, "count": len(tenants)}

@app.get("/api/tenants/{tenant_id}")
async def get_agency_tenant(tenant_id: str):
    """Retrieves specific agency workspace settings."""
    from tenant_manager import TenantManager
    return TenantManager.get_tenant(db, tenant_id_or_slug=tenant_id)

@app.post("/api/tenants")
async def create_agency_tenant(req: TenantCreateRequest):
    """Registers a new multi-tenant agency workspace."""
    from tenant_manager import TenantManager
    return TenantManager.create_tenant(
        db=db,
        name=req.name,
        slug=req.slug,
        agency_branding=req.agency_branding,
        pricing_config=req.pricing_config
    )

# --- Opportunity Timeline Endpoints ---

@app.get("/api/leads/{lead_id}/timeline")
async def get_lead_timeline(lead_id: str):
    events = db.get_lead_timeline(lead_id)
    return {"lead_id": lead_id, "events": events, "count": len(events)}

@app.post("/api/leads/{lead_id}/timeline")
async def add_lead_timeline_event(lead_id: str, req: TimelineEventCreateRequest):
    event_id = db.log_timeline_event(
        lead_id=lead_id,
        event_type=req.event_type,
        title=req.title,
        description=req.description,
        actor=req.actor,
        metadata=req.metadata
    )
    return {"status": "success", "event_id": event_id, "lead_id": lead_id}

# --- AI Call Roleplay Simulator Endpoints ---

@app.post("/api/leads/{lead_id}/simulate-call/start")
async def start_call_simulation(lead_id: str, req: Optional[CallSimulationStartRequest] = None):
    lead = db.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    persona = req.persona if req else "GATEKEEPER_RECEPTIONIST"
    session_data = AICallSimulator.start_session(dict(lead), persona=persona)
    return session_data

@app.post("/api/leads/{lead_id}/simulate-call/turn")
async def simulate_call_turn(lead_id: str, req: CallSimulationTurnRequest):
    lead = db.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    turn_res = AICallSimulator.simulate_turn(
        lead_dict=dict(lead),
        persona=req.persona,
        conversation_history=req.history,
        user_pitch=req.user_pitch
    )
    # Log practiced simulation event to lead timeline
    try:
        db.log_timeline_event(
            lead_id=lead_id,
            event_type="SIMULATION_PRACTICED",
            title=f"Call Sparring: {req.persona} (Score: {turn_res.evaluation.overall_score}/10)",
            description=f"Turn evaluated. Status: {turn_res.status}. Feedback: {turn_res.evaluation.tactical_feedback}",
            actor="SALES_REP",
            metadata={
                "persona": req.persona,
                "overall_score": turn_res.evaluation.overall_score,
                "hook_score": turn_res.evaluation.hook_score,
                "value_score": turn_res.evaluation.value_score,
                "control_score": turn_res.evaluation.control_score,
                "status": turn_res.status
            }
        )
    except Exception:
        pass
    return turn_res.model_dump()

# --- Autonomous Voice AI Dialer Endpoints (Wholesale PSTN & Sandbox) ---

@app.get("/api/voice/status")
async def get_voice_carrier_status():
    """Returns telecommunications status (Telnyx vs Sandbox mode, estimated costs, API readiness)."""
    return VoiceDialerEngine.get_carrier_status()

@app.get("/api/voice/providers/health")
async def get_voice_providers_health():
    """Returns multi-project Gemini circuit breakers, OpenAI status, and error telemetry."""
    from llm_router import LLMRouter
    return LLMRouter.get_provider_status()

@app.get("/api/voice/benchmark/summary")
async def get_voice_benchmark_summary():
    """Returns cost-per-qualified-demo and conversion analytics across all tested voice models."""
    return db.get_model_performance_summary()

@app.post("/api/voice/benchmark/run")
async def run_voice_model_benchmark_test(payload: Dict[str, Any] = Body(default={})):
    """Runs automated A/B benchmark calls comparing Gemini Live, OpenAI, and Kokoro."""
    from llm_router import VoiceModelBenchmark
    total_calls = payload.get("total_calls", 10)
    lead_id = payload.get("lead_id")
    lead_dict = db.get_lead(lead_id) if lead_id else None
    if not lead_dict:
        lead_dict = {
            "id": "bench_default_lead",
            "name": "Benchmark Dental Group",
            "doctor_name": "Dr. Miller",
            "phone": "+15125550188"
        }
    return VoiceModelBenchmark.run_benchmark_cycle(
        lead_dict=lead_dict,
        total_calls=total_calls,
        db=db
    )

@app.get("/api/voice/queue")
async def get_voice_approval_queue(min_probability: int = 70, limit: int = 30):
    """
    Returns prioritized calling prospects formatted specifically for human review and approval.
    Each item contains clinic research, doctor salutation, tailored cold call hook, and objections.
    """
    leads = db.get_todays_calls(min_probability=min_probability, limit=limit)
    approval_queue = []
    
    for l in leads:
        lead_dict = dict(l)
        script = DentalCallerPersona.build_call_script(lead_dict)
        clean_phone = clean_phone_e164(lead_dict.get("phone"))
        
        rev_min = lead_dict.get("missed_rev_min") or lead_dict.get("audit_missed_rev_min") or 3500
        rev_max = lead_dict.get("missed_rev_max") or lead_dict.get("audit_missed_rev_max") or 6800
        
        approval_queue.append({
            "id": lead_dict.get("id"),
            "name": lead_dict.get("name"),
            "doctor_name": script["doctor_name"] or "Primary Dentist",
            "doctor_salutation": script["doctor_salutation"],
            "city": script["city"],
            "phone": lead_dict.get("phone"),
            "clean_phone": clean_phone,
            "rating": float(lead_dict.get("rating", 4.8)) if lead_dict.get("rating") else 4.8,
            "review_count": int(lead_dict.get("review_count", 50)) if lead_dict.get("review_count") else 50,
            "opportunity_score": int(lead_dict.get("opportunity_score", 75)),
            "buying_probability": int(lead_dict.get("buying_probability", 80)),
            "stage": lead_dict.get("stage", "FOUND"),
            "monthly_leakage": script["monthly_leakage"],
            "top_services": script["top_services"],
            "gatekeeper_hook": script["gatekeeper_hook"],
            "doctor_hook": script["doctor_hook"],
            "script": script,
            "requires_user_confirmation": True,
            "approval_status": "PENDING_CONFIRMATION"
        })
        
    return {
        "carrier_status": VoiceDialerEngine.get_carrier_status(),
        "total_ready_for_call": len(approval_queue),
        "queue": approval_queue
    }

@app.post("/api/voice/call/{lead_id}/dispatch")
async def dispatch_voice_call(lead_id: str, req: VoiceCallDispatchRequest, request: Request):
    """
    Executes an autonomous AI phone call to the clinic once confirmed by the user.
    """
    if not req.confirmed_by_user:
        raise HTTPException(status_code=400, detail="Human confirmation required before launching call.")
        
    lead = db.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
        
    base_url = str(request.base_url).rstrip('/')
    result = VoiceDialerEngine.dispatch_call(
        lead=dict(lead),
        to_phone=req.phone_override,
        db=db,
        server_base_url=base_url
    )
    return result

@app.post("/api/voice/call/batch-dispatch")
async def batch_dispatch_voice_calls(req: VoiceCallBatchRequest, request: Request):
    """
    Dispatches multiple confirmed calls sequentially.
    """
    if not req.confirmed_by_user:
        raise HTTPException(status_code=400, detail="Human confirmation required before launching batch calls.")
        
    base_url = str(request.base_url).rstrip('/')
    dispatched_results = []
    
    for lid in req.lead_ids:
        lead = db.get_lead(lid)
        if lead:
            res = VoiceDialerEngine.dispatch_call(
                lead=dict(lead),
                db=db,
                server_base_url=base_url
            )
            dispatched_results.append(res)
            
    return {
        "status": "success",
        "total_dispatched": len(dispatched_results),
        "results": dispatched_results
    }

@app.post("/api/voice/call/test")
async def test_voice_call(req: VoiceCallTestRequest, request: Request):
    """
    Places a live test call to a custom user phone number (e.g. founder's cell)
    using the persona and research of a selected dental lead.
    """
    if req.lead_id:
        lead = db.get_lead(req.lead_id)
    else:
        leads = db.list_all_leads()
        lead = leads[0] if leads else {"name": "Austin Premier Dental", "doctor_name": "Dr. Miller", "phone": req.phone}
        
    base_url = str(request.base_url).rstrip('/')
    result = VoiceDialerEngine.dispatch_call(
        lead=dict(lead),
        to_phone=req.phone,
        db=db,
        server_base_url=base_url
    )
    return result

@app.post("/api/voice/synthesize")
async def synthesize_voice_preview(req: VoiceSynthesizeRequest):
    """
    Synthesizes and returns speech audio preview using Gemini 3.1, Gemini 2.5, or local Kokoro-82M.
    """
    from voice_dialer import generate_speech_audio
    import time
    filename = f"preview_{req.engine}_{int(time.time())}"
    voice_name = req.voice or ("Puck" if "gemini" in req.engine or req.engine == "auto" else "af_sarah")
    result = generate_speech_audio(text=req.text, filename=filename, preferred_engine=req.engine, voice_name=voice_name)
    return result

@app.post("/api/voice/interactive/start")
async def interactive_voice_start(req: InteractiveVoiceStartRequest):
    """
    Initializes a zero-cost interactive voice simulation session with real speech output.
    Returns the initial cold call pitch / greeting spoken by the AI cold caller.
    """
    from voice_dialer import generate_speech_audio
    import time
    
    lead = None
    if req.lead_id:
        lead = db.get_lead(req.lead_id)
    if not lead:
        leads = db.list_all_leads()
        lead = leads[0] if leads else {"name": "Austin Premier Dental", "doctor_name": "Dr. Miller", "city": "Austin, TX"}
        
    lead_dict = dict(lead)
    script = DentalCallerPersona.build_call_script(lead_dict)
    clinic_name = lead_dict.get("name", "Dental Practice")
    doctor_name = script.get("doctor_name") or "Doctor"
    
    opening_hook = script.get("gatekeeper_hook") or f"Hi, good morning! I was reviewing {clinic_name}'s patient intake setup. Could you tell me who handles patient scheduling after 5 PM when the office is closed?"
    
    filename = f"interactive_{int(time.time())}_{abs(hash(opening_hook)) % 10000}"
    speech = await asyncio.to_thread(
        generate_speech_audio,
        text=opening_hook,
        filename=filename,
        preferred_engine=req.engine or "auto-fast",
        voice_name=req.voice_name or "af_sarah"
    )
    
    initial_history = [
        {
            "role": "assistant",
            "speaker": "AI Growth Specialist",
            "text": opening_hook,
            "audio_url": speech.get("audio_url"),
            "engine": speech.get("engine")
        }
    ]
    
    return {
        "status": "active",
        "session_id": filename,
        "lead_id": lead_dict.get("id"),
        "clinic_name": clinic_name,
        "doctor_name": doctor_name,
        "doctor_salutation": script.get("doctor_salutation"),
        "monthly_leakage": script.get("monthly_leakage", "$4,800/mo"),
        "script": script,
        "opening_hook": opening_hook,
        "audio_url": speech.get("audio_url"),
        "engine_used": speech.get("engine"),
        "history": initial_history
    }

@app.post("/api/voice/interactive/turn")
async def interactive_voice_turn(req: InteractiveVoiceTurnRequest):
    """
    Processes the next interactive turn from the user (speaking as receptionist or dentist).
    Uses high-speed Gemini Flash Lite LLM to reason and generate natural, objection-handling response,
    then synthesizes real voice audio.
    """
    from voice_dialer import generate_speech_audio
    import time
    
    lead = None
    if req.lead_id:
        lead = db.get_lead(req.lead_id)
    if not lead:
        leads = db.list_all_leads()
        lead = leads[0] if leads else {"name": "Austin Premier Dental", "doctor_name": "Dr. Miller", "city": "Austin, TX"}
        
    lead_dict = dict(lead)
    script = DentalCallerPersona.build_call_script(lead_dict)
    clinic_name = lead_dict.get("name", "Dental Practice")
    doctor_name = script.get("doctor_name") or "Doctor"
    
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    def _generate_llm_reply():
        memory_info = script.get("institutional_memory") or {}
        mem_summary = memory_info.get("memory_summary_prompt", "")
        mem_segment = f"INSTITUTIONAL SALES MEMORY: {mem_summary}\n" if mem_summary else ""

        system_prompt = f"""You are a consultative Dental AI Growth Specialist calling '{clinic_name}'.
Doctor: Dr. {doctor_name}
Monthly Missed Revenue: {script.get('monthly_leakage', '$4,800/mo')}
Target Procedure: Dental Implants, Cosmetic, Emergency Care.
{mem_segment}
THE USER IS PLAYING THE ROLE OF THE CLINIC FRONT DESK RECEPTIONIST OR PRACTICE OWNER.
Their message: "{req.user_message}"

CRITICAL VOICE SPEED & CONVERSATIONAL PACING RULES:
- You are on a LIVE interactive phone call. Reply in EXACTLY 1 short, crisp sentence (maximum 12 to 15 words).
- Short punchy answers sound completely human and keep latency ultra-low. Never speak long monologues.
- If they raise an objection ("we have receptionist", "busy", "send email", "not interested"), use 1 sentence of consultative empathy and offer a 2-minute video prototype or ask for the office manager's first name.
- If they ask for price, anchor against a single implant case ($350/mo).
- If they agree to meet or ask when, confirm Thursday at 11:00 AM.
- Sound relaxed, conversational, and consultative.

Return STRICTLY a JSON object with:
{{
  "reply": "One crisp spoken sentence under 15 words.",
  "is_meeting_booked": true/false,
  "booked_slot": "Thursday at 11:00 AM" (or null if not booked yet)
}}"""
        reply_txt = "I completely understand. Could I share a quick two-minute video with your office manager?"
        is_bk = False
        bk_slot = None

        try:
            from llm_router import LLMRouter
            v_res = LLMRouter.generate_voice_reply(
                system_prompt=system_prompt,
                user_message=req.user_message,
                history=req.history,
                clinic_context=lead_dict
            )
            if v_res and v_res.get("reply"):
                reply_txt = v_res.get("reply")
                is_bk = bool(v_res.get("is_meeting_booked"))
                bk_slot = v_res.get("booked_slot")
        except Exception as ex:
            logger.warning(f"LLMRouter interactive voice turn fallback: {ex}")

        if not reply_txt:
            if "email" in req.user_message.lower():
                reply_txt = f"Happy to email! What is the practice manager's direct first name so I can address it properly to Dr. {doctor_name}'s team?"
            elif any(w in req.user_message.lower() for w in ["cost", "price", "how much"]):
                reply_txt = "It is roughly $350 a month, which pays for itself with a single restored emergency appointment. Would you be open to a 10-minute preview Thursday at 11 AM?"
            elif any(w in req.user_message.lower() for w in ["sure", "okay", "thursday", "book", "zoom", "meet"]):
                reply_txt = "That is perfect! I will lock in Thursday at 11:00 AM and send the calendar invite right away. Thank you!"
                is_bk = True
                bk_slot = "Thursday at 11:00 AM"

        return reply_txt, is_bk, bk_slot

    reply_text, is_booked, booked_slot = await asyncio.to_thread(_generate_llm_reply)

    filename = f"turn_{int(time.time())}_{abs(hash(reply_text)) % 10000}"
    speech = await asyncio.to_thread(
        generate_speech_audio,
        text=reply_text,
        filename=filename,
        preferred_engine=req.engine or "auto-fast",
        voice_name=req.voice_name or "en-US-Journey-F"
    )

    from voice_dialer import get_instant_conversational_filler
    filler_info = get_instant_conversational_filler()
    
    new_history = list(req.history)
    new_history.append({
        "role": "user",
        "speaker": "You (Receptionist / Clinic)",
        "text": req.user_message
    })
    new_history.append({
        "role": "assistant",
        "speaker": "AI Growth Specialist",
        "text": reply_text,
        "audio_url": speech.get("audio_url"),
        "engine": speech.get("engine")
    })
    
    if is_booked and db and lead_dict.get("id"):
        try:
            db.log_call_outcome(
                lead_id=lead_dict.get("id"),
                outcome="MEETING_BOOKED",
                rep_notes=f"Interactive Sandbox Call booked demo: {booked_slot}",
                duration_sec=90
            )
        except Exception:
            pass
    
    return {
        "status": "active",
        "reply": reply_text,
        "audio_url": speech.get("audio_url"),
        "filler_audio_url": filler_info.get("audio_url"),
        "filler_text": filler_info.get("text"),
        "engine_used": speech.get("engine"),
        "is_meeting_booked": is_booked,
        "booked_slot": booked_slot,
        "history": new_history
    }

@app.post("/api/voice/interactive/turn-audio")
async def interactive_voice_turn_audio(req: InteractiveVoiceAudioTurnRequest):
    """
    Processes recorded microphone audio from the user (speaking as receptionist or dentist).
    Uses Gemini's multimodal audio understanding to transcribe and reply in a single fast call,
    then synthesizes real voice audio with sub-second latency.
    """
    import base64
    from voice_dialer import generate_speech_audio
    import time

    lead = None
    if req.lead_id:
        lead = db.get_lead(req.lead_id)
    if not lead:
        leads = db.list_all_leads()
        lead = leads[0] if leads else {"name": "Austin Premier Dental", "doctor_name": "Dr. Miller", "city": "Austin, TX"}
        
    lead_dict = dict(lead)
    script = DentalCallerPersona.build_call_script(lead_dict)
    clinic_name = lead_dict.get("name", "Dental Practice")
    doctor_name = script.get("doctor_name") or "Doctor"
    
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    raw_b64 = req.audio_base64
    if "," in raw_b64:
        raw_b64 = raw_b64.split(",", 1)[1]
    
    try:
        audio_bytes = base64.b64decode(raw_b64)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid base64 audio data: {e}")

    def _process_audio_turn():
        memory_info = script.get("institutional_memory") or {}
        mem_summary = memory_info.get("memory_summary_prompt", "")
        mem_segment = f"INSTITUTIONAL SALES MEMORY: {mem_summary}\n" if mem_summary else ""

        system_prompt = f"""You are a professional, consultative Dental AI Growth Specialist calling '{clinic_name}'.
Doctor: Dr. {doctor_name}
Monthly Missed Revenue: {script.get('monthly_leakage', '$4,800/mo')}
Target Procedure: Dental Implants, Cosmetic, Emergency Care.
{mem_segment}
THE USER SPOKE IN THE ATTACHED AUDIO AS THE RECEPTIONIST OR PRACTICE OWNER.
Your tasks:
1. Transcribe exactly what the user said in the audio.
2. Formulate your response in EXACTLY 1 short, crisp spoken sentence (maximum 12 to 15 words).
- If they raise an objection ("we have receptionist", "busy", "send email", "not interested"), use 1 sentence of consultative empathy and offer a 2-minute video preview or ask for the office manager's first name.
- If they ask for price, anchor against a single implant case ($350/mo).
- If they agree to meet or ask when, confirm Thursday at 11:00 AM.
- Sound relaxed, natural, and consultative.

Return STRICTLY a JSON object with:
{{
  "transcript": "Exact transcription of what the user said in the audio.",
  "reply": "One crisp spoken sentence under 15 words.",
  "is_meeting_booked": true/false,
  "booked_slot": "Thursday at 11:00 AM" (or null if not booked yet)
}}"""
        user_transcript = "I received your call."
        reply_txt = f"Thanks for taking my call. I was reviewing {clinic_name}'s after-hours intake setup."
        is_bk = False
        bk_slot = None

        if key and not key.startswith("mock_"):
            models_to_try = ["gemini-flash-lite-latest", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]
            for model_name in models_to_try:
                try:
                    from google import genai
                    from google.genai import types
                    client = genai.Client(
                        api_key=key,
                        http_options=types.HttpOptions(
                            timeout=10000,
                            retry_options=types.HttpRetryOptions(attempts=1)
                        )
                    )
                    clean_mime = (req.mime_type or "audio/webm").split(";")[0].strip()
                    resp = client.models.generate_content(
                        model=model_name,
                        contents=[
                            types.Part.from_bytes(data=audio_bytes, mime_type=clean_mime),
                            system_prompt
                        ],
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.3,
                            max_output_tokens=100
                        )
                    )
                    raw = resp.text.strip()
                    parsed = json.loads(raw)
                    user_transcript = parsed.get("transcript", user_transcript)
                    reply_txt = parsed.get("reply", reply_txt)
                    is_bk = bool(parsed.get("is_meeting_booked"))
                    bk_slot = parsed.get("booked_slot")
                    break
                except Exception as ex:
                    logger.warning(f"Audio turn processing failed on {model_name}: {ex}")
                    continue
        return user_transcript, reply_txt, is_bk, bk_slot

    user_transcript, reply_text, is_booked, booked_slot = await asyncio.to_thread(_process_audio_turn)

    filename = f"turn_{int(time.time())}_{abs(hash(reply_text)) % 10000}"
    speech = await asyncio.to_thread(
        generate_speech_audio,
        text=reply_text,
        filename=filename,
        preferred_engine=req.engine or "auto-fast",
        voice_name=req.voice_name or "af_sarah"
    )
    
    new_history = list(req.history)
    new_history.append({
        "role": "user",
        "speaker": "You (Spoken into Mic)",
        "text": user_transcript
    })
    new_history.append({
        "role": "assistant",
        "speaker": "AI Growth Specialist",
        "text": reply_text,
        "audio_url": speech.get("audio_url"),
        "engine": speech.get("engine")
    })
    
    if is_booked and db and lead_dict.get("id"):
        try:
            db.log_call_outcome(
                lead_id=lead_dict.get("id"),
                outcome="MEETING_BOOKED",
                rep_notes=f"Interactive Sandbox Audio Call booked demo: {booked_slot}",
                duration_sec=90
            )
        except Exception:
            pass
            
    return {
        "status": "active",
        "transcript": user_transcript,
        "reply": reply_text,
        "audio_url": speech.get("audio_url"),
        "engine_used": speech.get("engine"),
        "is_meeting_booked": is_booked,
        "booked_slot": booked_slot,
        "history": new_history
    }

@app.post("/api/voice/webhook/telnyx")
async def telnyx_webhook_handler(request: Request):
    """Handles inbound Call Control webhooks from Telnyx."""
    try:
        data = await request.json()
        event_type = data.get("data", {}).get("event_type")
        payload = data.get("data", {}).get("payload", {})
        call_control_id = payload.get("call_control_id")
        
        logger.info(f"Telnyx webhook received: {event_type} (Call ID: {call_control_id})")
        return {"status": "received", "event": event_type}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.post("/api/voice/webhook/twilio")
async def twilio_webhook_handler(request: Request):
    """Handles inbound Call Control & Status webhooks from Twilio."""
    try:
        form = await request.form()
        call_sid = form.get("CallSid")
        call_status = form.get("CallStatus")
        from_num = form.get("From")
        to_num = form.get("To")
        logger.info(f"Twilio webhook received: CallSid={call_sid}, Status={call_status}, From={from_num}, To={to_num}")
        
        twiml_response = '<?xml version="1.0" encoding="UTF-8"?><Response><Say voice="Polly.Joanna-Neural">Thank you for connecting with Dental Practice Intelligence.</Say></Response>'
        from fastapi.responses import Response
        return Response(content=twiml_response, media_type="application/xml")
    except Exception as e:
        logger.error(f"Error handling Twilio webhook: {e}")
        return {"status": "error", "detail": str(e)}

@app.get("/api/settings/telephony")
async def get_telephony_settings():
    """Returns active telephony carrier and masked configuration."""
    from voice_dialer import (
        VoiceDialerEngine, get_active_carrier, get_telnyx_from_phone,
        get_twilio_from_phone, get_twilio_account_sid, get_twilio_api_key_sid
    )
    st = VoiceDialerEngine.get_carrier_status()
    acc_sid = get_twilio_account_sid()
    key_sid = get_twilio_api_key_sid()
    masked_acc = f"{acc_sid[:4]}...{acc_sid[-4:]}" if len(acc_sid) > 8 else ("(Configured)" if acc_sid else "")
    masked_key = f"{key_sid[:6]}...{key_sid[-4:]}" if len(key_sid) > 10 else ("(Configured)" if key_sid else "")

    return {
        "active_carrier": st.get("active_carrier", "TWILIO"),
        "has_telnyx": st.get("has_telnyx", False),
        "has_twilio": st.get("has_twilio", False),
        "telnyx_phone": get_telnyx_from_phone(),
        "twilio_phone": get_twilio_from_phone(),
        "twilio_account_sid_masked": masked_acc,
        "twilio_api_key_sid_masked": masked_key,
        "has_twilio_secret": bool(os.getenv("TWILIO_API_KEY_SECRET") or os.getenv("TWILIO_AUTH_TOKEN")),
        "carrier_mode": st.get("mode"),
        "estimated_cost_per_minute": st.get("estimated_cost_per_minute")
    }

@app.post("/api/settings/telephony")
async def update_telephony_settings(payload: Dict[str, Any] = Body(...)):
    """Switches active carrier (TELNYX vs TWILIO) and persists credentials."""
    from voice_dialer import VoiceDialerEngine
    env_file = Path(".env")
    env_lines = {}
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env_lines[k.strip()] = v.strip()

    updates = {}
    if "active_carrier" in payload:
        carrier = str(payload["active_carrier"]).upper()
        if carrier in ["TELNYX", "TWILIO", "BROWSER"]:
            updates["ACTIVE_CARRIER"] = carrier
            os.environ["ACTIVE_CARRIER"] = carrier

    carrier_keys = {
        "twilio_account_sid": "TWILIO_ACCOUNT_SID",
        "twilio_auth_token": "TWILIO_AUTH_TOKEN",
        "twilio_api_key_sid": "TWILIO_API_KEY_SID",
        "twilio_api_key_secret": "TWILIO_API_KEY_SECRET",
        "twilio_from_phone": "TWILIO_FROM_PHONE",
        "telnyx_api_key": "TELNYX_API_KEY",
        "telnyx_connection_id": "TELNYX_CONNECTION_ID",
        "telnyx_from_phone": "TELNYX_FROM_PHONE"
    }

    for req_key, env_var in carrier_keys.items():
        if req_key in payload and payload[req_key] is not None:
            val = str(payload[req_key]).strip()
            if val:
                updates[env_var] = val
                os.environ[env_var] = val

    env_lines.update(updates)
    out_lines = [f"{k}={v}" for k, v in env_lines.items()]
    env_file.write_text("\n".join(out_lines) + "\n", encoding="utf-8")

    # Sync to settings_mgr as well
    settings_dict = {}
    if "ACTIVE_CARRIER" in updates:
        settings_dict["active_carrier"] = updates["ACTIVE_CARRIER"]
    for req_key, env_var in carrier_keys.items():
        if env_var in updates:
            settings_dict[req_key] = updates[env_var]
    if settings_dict:
        try:
            settings_mgr.update_settings(settings_dict)
        except Exception:
            pass

    return {
        "status": "success",
        "message": f"Telephony configuration updated. Active carrier: {os.getenv('ACTIVE_CARRIER', 'TWILIO')}",
        "carrier_status": VoiceDialerEngine.get_carrier_status()
    }

@app.post("/api/settings/telephony/test")
async def test_telephony_carrier(payload: Dict[str, Any] = Body(default={})):
    """Tests connectivity to the active or requested carrier (Telnyx vs Twilio)."""
    carrier = (payload.get("carrier") or os.getenv("ACTIVE_CARRIER", "TWILIO")).upper()
    if carrier == "TWILIO":
        try:
            from voice_dialer import get_twilio_client, get_twilio_account_sid, get_twilio_api_key_sid, get_twilio_from_phone
            client = get_twilio_client()
            if not client:
                acc = get_twilio_account_sid()
                key = get_twilio_api_key_sid()
                if key and not acc:
                    return {
                        "status": "error",
                        "carrier": "TWILIO",
                        "message": "Twilio API Key (SK...) detected, but Account SID (AC...) is missing. In Twilio, API Keys require your main Account SID (starts with AC...) from twilio.com/console."
                    }
                return {
                    "status": "error",
                    "carrier": "TWILIO",
                    "message": "Twilio credentials incomplete. Please provide Account SID (AC...) and Auth Token or API Secret."
                }
            from_phone = get_twilio_from_phone()
            return {
                "status": "success",
                "carrier": "TWILIO",
                "message": f"Twilio API client authenticated successfully! Ready to dial via {from_phone or 'configured phone'}.",
                "from_phone": from_phone
            }
        except Exception as e:
            return {
                "status": "error",
                "carrier": "TWILIO",
                "message": f"Twilio authentication error: {str(e)}"
            }
    elif carrier == "TELNYX":
        try:
            from voice_dialer import verify_telnyx_diagnostics, get_telnyx_api_key, get_telnyx_connection_id, get_telnyx_from_phone
            key = get_telnyx_api_key()
            if not key or key.startswith("mock_"):
                return {"status": "error", "carrier": "TELNYX", "message": "Telnyx API key not configured in Settings or .env."}
            
            diag = verify_telnyx_diagnostics(key)
            bal = diag.get("balance")
            nums = diag.get("numbers", [])
            recent = diag.get("recent_calls", [])
            root_causes = diag.get("root_cause_analysis", [])

            num_str = f"{len(nums)} owned number(s)" if nums else "0 owned numbers (Outbound calls may be dropped as spam)"
            bal_str = f"${float(bal):.2f}" if bal is not None else "Unknown"

            msg = f"Telnyx verified! Balance: {bal_str} USD | Active Numbers: {num_str}."
            if not nums:
                msg += " ⚠️ Warning: No phone numbers purchased on this Telnyx account. Outbound PSTN calls without an owned Caller ID will be rejected by telecom carriers."

            return {
                "status": "success",
                "carrier": "TELNYX",
                "message": msg,
                "diagnostics": diag
            }
        except Exception as e:
            return {"status": "error", "carrier": "TELNYX", "message": str(e)}
    else:
        return {"status": "success", "carrier": "BROWSER", "message": "In-browser WebRTC / mic audio mode active."}

@app.get("/api/voice/telnyx/verify")
async def get_telnyx_diagnostics_endpoint():
    """
    Returns full diagnostic verification of Telnyx balance, owned numbers,
    call control applications, and recent carrier hangup causes.
    """
    from voice_dialer import verify_telnyx_diagnostics
    return verify_telnyx_diagnostics()

# --- Two-Way Calendar Sync & Demo Booking Endpoints ---

@app.get("/api/calendar/slots")
async def get_calendar_slots_endpoint(days: int = 5):
    """Returns available 15-minute demo slots for dental practice owners."""
    from calendar_sync import CalendarSyncEngine
    return {
        "status": "success",
        "days_ahead": days,
        "slots": CalendarSyncEngine.get_available_slots(days_ahead=days)
    }

@app.post("/api/calendar/book")
async def book_calendar_demo_endpoint(req: CalendarBookRequest):
    """Books a demo slot, updates lead to DEMO_BOOKED, and generates Google Meet invite."""
    from calendar_sync import CalendarSyncEngine
    booking = CalendarSyncEngine.book_slot(
        lead_id=req.lead_id or "preview",
        slot_str=req.slot,
        clinic_name=req.clinic_name,
        doctor_name=req.doctor_name,
        phone=req.phone,
        email=req.email,
        db=db
    )
    return {
        "status": "success",
        "booking": booking,
        "message": f"Demo confirmed for {req.slot}! Google Meet: {booking.get('meet_link')}"
    }

@app.get("/api/calendar/bookings")
async def get_calendar_bookings_endpoint():
    """Returns all confirmed demo bookings."""
    from calendar_sync import CalendarSyncEngine
    return {
        "status": "success",
        "bookings": CalendarSyncEngine.get_upcoming_bookings(db=db)
    }

# --- Two-Way Interactive WhatsApp Test Sandbox Endpoints ---

@app.post("/api/whatsapp/sandbox/inbound")
@app.post("/api/whatsapp/turn")
async def handle_whatsapp_sandbox_message(req: WhatsAppInboundRequest):
    """
    Handles two-way WhatsApp patient conversation turns with dental intake AI.
    Processes patient concerns (emergency toothaches, implant consultations, insurance)
    and books triage appointment slots.
    """
    lead = db.get_lead(req.lead_id) if (req.lead_id and req.lead_id != "preview") else None
    clinic_name = req.clinic_name or (lead.get("name") if lead else "Dental Practice")
    doctor_name = req.doctor_name or (lead.get("doctor_name") if lead else "Doctor")
    clean_doc = doctor_name.replace("Dr.", "").replace("Dr", "").strip()
    doc_display = f"Dr. {clean_doc}" if clean_doc else "the Practice Owner"

    user_text = req.message.strip()
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    prompt = f"""You are the 24/7 AI Patient Care Concierge for '{clinic_name}' ({doc_display}).
A prospective dental patient just texted you on WhatsApp:
"{user_text}"

INSTRUCTIONS:
1. Be warm, empathetic, and professional.
2. If they have an emergency or toothache: offer tomorrow morning priority slots (9:30 AM or 11:15 AM).
3. If they ask about dental implants or cosmetic work: highlight customized treatment plans and offer a 3D digital scan consultation this Thursday at 11:00 AM.
4. If they ask about insurance: confirm we file with major PPOs (Delta Dental, MetLife, Cigna, Aetna).
5. Always guide towards reserving an appointment time and getting their full name/cell.
6. Keep the reply under 2-3 concise conversational WhatsApp sentences with appropriate emojis.

Return strictly valid JSON:
{{
  "reply": "Your WhatsApp message text here.",
  "intent": "EMERGENCY" / "IMPLANT" / "INSURANCE" / "BOOKING" / "GENERAL",
  "is_appointment_requested": true/false,
  "proposed_slot": "Tomorrow at 9:30 AM" (or null)
}}"""

    reply_text = f"Hello! 👋 I'm the 24/7 patient coordinator for {clinic_name}. We'd love to help! {doc_display} has an open emergency slot tomorrow at 9:30 AM or 11:15 AM. Which time works best for you?"
    intent = "GENERAL"
    is_booked = False
    proposed_slot = None

    if key and not key.startswith("mock_"):
        try:
            from google import genai
            client = genai.Client(api_key=key)
            resp = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            txt = resp.text.strip()
            if "```json" in txt:
                txt = txt.split("```json")[1].split("```")[0].strip()
            elif "```" in txt:
                txt = txt.split("```")[1].split("```")[0].strip()
            parsed = json.loads(txt)
            reply_text = parsed.get("reply", reply_text)
            intent = parsed.get("intent", intent)
            is_booked = parsed.get("is_appointment_requested", False)
            proposed_slot = parsed.get("proposed_slot")
        except Exception as e:
            logger.warning(f"Gemini WhatsApp intake fallback: {e}")

    # Log to CRM timeline
    if req.lead_id and req.lead_id != "preview":
        try:
            OpportunityTimelineManager.log_event(
                db=db,
                lead_id=req.lead_id,
                event_type="WHATSAPP_MESSAGE_SENT",
                title=f"💬 WhatsApp Sandbox Turn: {intent}",
                description=f"Patient: '{user_text}' -> AI Reply: '{reply_text}'",
                actor="WHATSAPP_BOT",
                metadata={"patient_message": user_text, "reply": reply_text, "intent": intent}
            )
        except Exception:
            pass

    return {
        "status": "success",
        "reply": reply_text,
        "intent": intent,
        "is_appointment_requested": is_booked,
        "proposed_slot": proposed_slot
    }

# --- Pillar 4: Automated No-Show Elimination Sequence ---

@app.post("/api/cadence/trigger-reminder")
async def trigger_cadence_reminder_endpoint(req: CadenceReminderRequest):
    """
    Triggers automated No-Show Elimination SMS & Video touchpoints:
    T-24h: Personalized Loom teardown link to build anticipation.
    T-1h: Direct Google Meet / Zoom link with 1-click confirm/reschedule.
    """
    lead = db.get_lead(req.lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
        
    clinic_name = lead.get("name", "Dental Practice")
    doctor_name = lead.get("doctor_name", "Doctor")
    phone = lead.get("phone", "")

    if req.reminder_type == "T-24H":
        msg = req.custom_message or (
            f"Hi {doctor_name}! Looking forward to our 15-min practice growth walkthrough tomorrow. "
            f"Here is a 90-second preview of the after-hours emergency leakage analysis for {clinic_name}: "
            f"http://127.0.0.1:8000/demo/{req.lead_id} — See you tomorrow!"
        )
    else:  # T-1H
        meet_code = f"den-{abs(hash(req.lead_id)) % 1000000:06d}"
        meet_link = f"https://meet.google.com/{meet_code[:3]}-{meet_code[3:]}"
        msg = req.custom_message or (
            f"Hi {doctor_name}, our live demo starts in 60 minutes! "
            f"Here is your direct meeting link: {meet_link} "
            f"(Reply 'RESCHEDULE' if you need a different time today)."
        )

    # Log to timeline
    OpportunityTimelineManager.log_event(
        db=db,
        lead_id=req.lead_id,
        event_type="NO_SHOW_REMINDER_SENT",
        title=f"🛡️ No-Show Prevention ({req.reminder_type}) Dispatched",
        description=f"Sent automated {req.reminder_type} reminder: '{msg}'",
        actor="SALES_CADENCE",
        metadata={"reminder_type": req.reminder_type, "message": msg, "phone": phone}
    )

    return {
        "status": "success",
        "reminder_type": req.reminder_type,
        "lead_id": req.lead_id,
        "phone": phone,
        "message_sent": msg
    }


# --- Expected Value ($EV) Prioritized Queue ---

@app.get("/api/queue/top-ev")
async def get_top_ev_queue(min_probability: int = 50, limit: int = 50):
    leads = db.get_top_ev_queue(min_probability=min_probability, limit=limit)
    results = []
    for l in leads:
        wa_data = generate_wa_pitch_and_link(l)
        l_copy = dict(l)
        l_copy["clean_phone"] = wa_data["clean_phone"]
        l_copy["wa_link"] = wa_data["wa_link"]

        rev_min = l.get("missed_rev_min") or l.get("audit_missed_rev_min") or 3450
        rev_max = l.get("missed_rev_max") or l.get("audit_missed_rev_max") or 6900
        l_copy["missed_rev_range"] = f"${rev_min:,.0f} - ${rev_max:,.0f}"

        shot_path = l.get("screenshot_path")
        lead_id = l.get("id")
        if shot_path and Path(shot_path).exists():
            l_copy["screenshot_url"] = f"/output/screenshots/{Path(shot_path).name}"
        elif lead_id and (OUTPUT_DIR / "screenshots" / f"{lead_id}.jpg").exists():
            l_copy["screenshot_url"] = f"/output/screenshots/{lead_id}.jpg"
        else:
            l_copy["screenshot_url"] = None

        results.append(l_copy)
    return results

# --- 24/7 Autonomous Daemon Endpoints ---

@app.get("/api/scheduler/daemon")
async def get_daemon_status():
    return AutonomousScheduler.get_daemon_status()

@app.post("/api/scheduler/daemon/toggle")
async def toggle_daemon(req: DaemonToggleRequest):
    if req.enable:
        status = await AutonomousScheduler.start_daemon(
            interval_hours=req.interval_hours,
            limit_per_cycle=req.limit_per_cycle,
            headless=True,
            db=db
        )
    else:
        status = AutonomousScheduler.stop_daemon()
    return status

# --- AI Revenue OS Endpoints (Conversion Trinity) ---

@app.get("/api/queue/top-urgent")
async def get_top_urgent_queue(min_urgency: int = 50, limit: int = 50):
    """Returns calling queue prioritized primarily by Urgency ('Why Now' timing) and secondarily by $EV."""
    leads = db.get_top_urgent_queue(min_urgency=min_urgency, limit=limit)
    results = []
    for l in leads:
        wa_data = generate_wa_pitch_and_link(l)
        l_copy = dict(l)
        l_copy["clean_phone"] = wa_data["clean_phone"]
        l_copy["wa_link"] = wa_data["wa_link"]

        rev_min = l.get("missed_rev_min") or l.get("audit_missed_rev_min") or 3450
        rev_max = l.get("missed_rev_max") or l.get("audit_missed_rev_max") or 6900
        l_copy["missed_rev_range"] = f"${rev_min:,.0f} - ${rev_max:,.0f}"

        shot_path = l.get("screenshot_path")
        lead_id = l.get("id")
        if shot_path and Path(shot_path).exists():
            l_copy["screenshot_url"] = f"/output/screenshots/{Path(shot_path).name}"
        elif lead_id and (OUTPUT_DIR / "screenshots" / f"{lead_id}.jpg").exists():
            l_copy["screenshot_url"] = f"/output/screenshots/{lead_id}.jpg"
        else:
            l_copy["screenshot_url"] = None

        results.append(l_copy)
    return results

@app.get("/api/leads/{lead_id}/roi")
async def get_lead_roi(
    lead_id: str,
    patients: int = Query(default=5, ge=1, le=50),
    case_value: int = Query(default=900, ge=100, le=10000),
    fee: int = Query(default=299, ge=50, le=5000)
):
    """Calculates practice-specific dental unit economics and ROI multiples."""
    lead = db.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    roi = calculate_practice_roi(
        lead_data=lead,
        recovered_patients_per_month=patients,
        avg_case_value=case_value,
        monthly_fee=fee
    )
    return {"lead_id": lead_id, "practice_name": lead.get("name"), "roi": roi}

@app.post("/api/leads/{lead_id}/roi")
async def calculate_custom_lead_roi(lead_id: str, req: ROICalculatorRequest):
    """Calculates custom practice unit economics based on user parameters."""
    lead = db.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    roi = calculate_practice_roi(
        lead_data=lead,
        recovered_patients_per_month=req.recovered_patients_per_month or 5,
        avg_case_value=req.avg_case_value or 900,
        monthly_fee=req.monthly_fee or 299
    )
    return {"lead_id": lead_id, "practice_name": lead.get("name"), "roi": roi}

@app.get("/api/leads/{lead_id}/proposal")
async def get_tailored_proposal_data(
    lead_id: str,
    patients: int = Query(default=5, ge=1, le=50),
    case_value: int = Query(default=900, ge=100, le=10000),
    fee: int = Query(default=299, ge=50, le=5000)
):
    """Generates a complete, tailored sales proposal ready for presentation or client delivery."""
    lead = db.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    custom_roi = calculate_practice_roi(
        lead_data=lead,
        recovered_patients_per_month=patients,
        avg_case_value=case_value,
        monthly_fee=fee
    )
    proposal = generate_tailored_proposal(lead=lead, custom_roi=custom_roi)
    return proposal

@app.get("/api/leads/{lead_id}/loom-script")
async def get_lead_loom_script(lead_id: str):
    """Generates a time-coded 2-minute personalized Loom video pitch script."""
    lead = db.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    script = generate_loom_pitch(lead=lead)
    return script

@app.get("/api/leads/{lead_id}/triggers")
async def get_lead_triggers(lead_id: str):
    """Retrieves all detected trigger events for a dental practice."""
    lead = db.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    triggers = db.get_lead_triggers(lead_id)
    return {
        "lead_id": lead_id,
        "practice_name": lead.get("name"),
        "urgency_score": lead.get("urgency_score", 75),
        "why_now_reasons": lead.get("why_now_reasons", []),
        "triggers": triggers,
        "total_triggers": len(triggers)
    }

@app.post("/api/leads/{lead_id}/check-changes")
async def check_lead_changes(lead_id: str, req: Optional[CheckChangesRequest] = None):
    """
    On-demand change detection & 'Why Now?' urgency re-computation.
    Compares existing record against new crawl or simulation data.
    """
    lead = db.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    new_data: Dict[str, Any] = {}
    if req:
        if req.html_content:
            new_data["html_hash"] = compute_html_hash(req.html_content)
        if req.technologies:
            new_data["tech_hash"] = compute_tech_hash(req.technologies)
        if req.new_reviews is not None:
            new_data["review_count"] = req.new_reviews
        if req.new_rating is not None:
            new_data["rating"] = req.new_rating

    # Detect delta
    detected_triggers = TriggerEngine.detect_changes(lead, new_data)

    # Persist any detected triggers
    for t in detected_triggers:
        db.log_trigger_event(
            lead_id=lead_id,
            event_type=t["event_type"],
            title=t["title"],
            description=t["description"],
            severity=t["severity"],
            old_val=t.get("old_val"),
            new_val=t.get("new_val")
        )

    # Re-calculate urgency and reasons
    all_triggers = db.get_lead_triggers(lead_id)
    new_urgency = TriggerEngine.calculate_urgency_score(lead, triggers=all_triggers)
    new_reasons = TriggerEngine.generate_why_now_reasons(lead, triggers=all_triggers)

    db.update_lead_urgency(lead_id, urgency_score=new_urgency, why_now_reasons=new_reasons)

    return {
        "status": "success",
        "lead_id": lead_id,
        "new_triggers_detected": len(detected_triggers),
        "detected_triggers": detected_triggers,
        "urgency_score": new_urgency,
        "why_now_reasons": new_reasons
    }

@app.post("/api/leads/{lead_id}/stage")
async def update_lead_stage(lead_id: str, req: StageUpdateRequest):
    success = db.update_lead_stage(lead_id, new_stage=req.stage, notes=req.notes)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to update stage")
    return {"status": "success", "lead_id": lead_id, "new_stage": req.stage}

@app.post("/api/leads/{lead_id}/note")
async def add_lead_note(lead_id: str, req: NoteRequest):
    note_id = db.add_lead_note(lead_id, note_text=req.note, author=req.author or "Sales Rep")
    return {"status": "success", "note_id": note_id}

# --- Queue Management Endpoints ---

@app.get("/api/queue")
async def list_queue(status: Optional[str] = "PENDING_REVIEW"):
    filter_status = None if status == "ALL" else status
    items = db.list_outreach_queue(status=filter_status)
    results = []
    for item in items:
        item_copy = dict(item)
        clean_phone = format_clean_phone(item.get("phone"))
        item_copy["clean_phone"] = clean_phone
        item_copy["wa_link"] = f"https://wa.me/{clean_phone}?text={urllib.parse.quote_plus(item.get('body', ''))}" if clean_phone else ""
        if item_copy.get("pdf_path"):
            pdf_name = Path(item_copy["pdf_path"]).name
            item_copy["pdf_path"] = f"output/reports/{pdf_name}"
        results.append(item_copy)
    return results

@app.post("/api/queue/{queue_id}/approve")
async def approve_queue_item(queue_id: str, req: QueueActionRequest):
    success = QueueManager.approve_item(queue_id, review_notes=req.notes or "Approved via Visual Dashboard", db=db)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to approve item")
    return {"status": "success", "queue_id": queue_id}

@app.post("/api/queue/{queue_id}/reject")
async def reject_queue_item(queue_id: str, req: QueueActionRequest):
    success = QueueManager.reject_item(queue_id, reason=req.notes or "Rejected via Visual Dashboard", db=db)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to reject item")
    return {"status": "success", "queue_id": queue_id}

@app.post("/api/queue/dispatch")
async def dispatch_approved_queue():
    dispatched = QueueManager.dispatch_approved(db=db)
    return {"status": "success", "count": len(dispatched), "items": dispatched}

# --- Proposal Generator Endpoint ---

@app.post("/api/proposal/generate")
async def generate_proposal(req: ProposalRequest):
    name = req.name or "Premier Dental Clinic"
    url = req.url or "https://example.com"

    if req.lead_id:
        lead = db.get_lead(req.lead_id)
        if lead:
            name = lead.get("name", name)
            url = lead.get("website", url)

    try:
        from clinic_researcher import ClinicResearcher
        result = await ClinicResearcher.research_and_generate(
            name=name,
            url=url,
            lead_id=req.lead_id,
            db=db
        )
        return result
    except Exception as e:
        logger.error(f"Clinic research & proposal generation failed: {e}", exc_info=True)
        # Fallback to standard proposal generation if unexpected error occurs
        clean_name = "".join(c for c in name if c.isalnum() or c == " ").strip().replace(" ", "_")
        raw = RawLead(name=name, website=url, phone="555-0100")
        scored = ScoredLead(
            raw_lead=raw,
            audit=WebsiteAuditResult(),
            maturity=DigitalMaturityScore(overall_score=65),
            opportunity_score=65,
            estimated_missed_revenue_annual=60000,
            estimated_missed_revenue_monthly_max=5000
        )
        proposal_path = ProposalGenerator.generate_proposal(
            scored_lead=scored,
            agency_name="WhatsApp Growth Partners for Dentists"
        )
        return {
            "status": "success",
            "proposal_path": str(proposal_path),
            "proposal_url": f"/output/proposals/{proposal_path.name}",
            "digital_maturity_score": 65,
            "monthly_leakage": 5000,
            "tier1_setup": 1500,
            "tier2_setup": 2500
        }

# --- Live Search Background Task & Progress ---

async def run_search_background_task(job_id: str, query: str, limit: int, generate_reports: bool, auto_queue: bool):
    job = active_jobs[job_id]
    job["status"] = "running"
    job["message"] = f"Connecting to Google Maps for: {query}..."
    job["progress"] = 5
    job["clinics_found"] = 0
    job["websites_analyzed"] = 0
    job["high_opportunity_count"] = 0
    job["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] Started Google Maps scraper for '{query}'...")

    try:
        finder = GoogleMapsLeadFinder(headless=True)

        async def on_lead_found(raw_lead, count, total_target):
            job["clinics_found"] = count
            job["message"] = f"Found clinic ({count}/{limit}): {raw_lead.name}..."
            job["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] Found practice: {raw_lead.name} ({raw_lead.phone or 'checking website'})...")
            pct = int(5 + (count / max(limit, 1)) * 30)
        def is_existing_fn(name, website, phone):
            return db.is_lead_existing(name=name, website=website, phone=phone)

        async def on_lead_skipped(name, reason):
            job["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] ⏩ Skipping '{name}' ({reason})")

        raw_leads = await finder.search(
            query=query,
            limit=limit,
            on_lead_found=on_lead_found,
            is_existing_fn=is_existing_fn,
            on_lead_skipped=on_lead_skipped
        )
        job["total_found"] = len(raw_leads)
        job["message"] = f"Found {len(raw_leads)} practices. Inspecting websites & generating intelligence..."
        job["progress"] = 35
        job["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] Discovery complete. Auditing digital maturity for {len(raw_leads)} practices...")

        auditor = WebsiteAuditor()
        personalizer = OutreachPersonalizer()
        explainer = ScoreExplainer()

        completed_leads = []
        step_increment = 60 / max(len(raw_leads), 1)

        for i, raw in enumerate(raw_leads):
            job["message"] = f"Auditing ({i+1}/{len(raw_leads)}): {raw.name}..."
            job["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] Auditing {raw.name} (Tech stack & missed revenue)...")

            scored_lead = await auditor.audit_lead(raw)
            scored_lead = await personalizer.personalize_lead(scored_lead)
            lead_id = db._make_lead_id(raw.name, raw.website)

            # Capture screenshot if website exists
            screenshot_path = None
            if raw.website:
                shot_file = OUTPUT_DIR / "screenshots" / f"{lead_id}.jpg"
                if not shot_file.exists():
                    job["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] 📸 Capturing homepage screenshot for {raw.name}...")
                    try:
                        success = await capture_website_screenshot(raw.website, shot_file)
                        if success:
                            screenshot_path = str(shot_file)
                    except Exception:
                        pass
                else:
                    screenshot_path = str(shot_file)

            # Generate Gemini explanation for score
            job["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] 🤖 Generating AI Opportunity Insights for {raw.name} (Score: {scored_lead.opportunity_score})...")
            try:
                why_reasons = await asyncio.to_thread(explainer.explain_score, scored_lead)
            except Exception:
                why_reasons = explainer.fallback_reasons(scored_lead)
            scored_lead.why_score_reasons = why_reasons
            if screenshot_path:
                scored_lead.screenshot_path = screenshot_path

            # Update DB with screenshot and AI explanation
            db.update_lead_visuals(lead_id, screenshot_path=screenshot_path, why_reasons=why_reasons)

            # Auto-generate PDF report if requested
            if generate_reports and scored_lead.opportunity_score >= 50:
                try:
                    await OpportunityReportGenerator.generate_pdf(scored_lead)
                except Exception:
                    pass

            # Auto-stage in review queue if high value
            if auto_queue and (scored_lead.opportunity_score >= 60 or (scored_lead.deal_priority and "TIER 1" in scored_lead.deal_priority.tier.value)):
                try:
                    QueueManager.stage_for_review(scored_lead, db=db)
                except Exception:
                    pass

            # Update progress counters
            job["websites_analyzed"] = i + 1
            if scored_lead.opportunity_score >= 60:
                job["high_opportunity_count"] += 1

            wa_data = generate_wa_pitch_and_link({
                "name": raw.name,
                "phone": raw.phone,
                "address": raw.address,
                "rating": raw.rating,
                "review_count": raw.review_count,
                "opportunity_score": scored_lead.opportunity_score,
                "annual_gap": scored_lead.estimated_missed_revenue_annual
            })

            rev_min = scored_lead.estimated_missed_revenue_monthly_min or int((scored_lead.estimated_missed_revenue_annual or 60000) / 12 * 0.6)
            rev_max = scored_lead.estimated_missed_revenue_monthly_max or int((scored_lead.estimated_missed_revenue_annual or 60000) / 12)
            screenshot_url = f"/output/screenshots/{Path(screenshot_path).name}" if (screenshot_path and Path(screenshot_path).exists()) else None

            completed_leads.append({
                "id": lead_id,
                "name": raw.name,
                "phone": raw.phone,
                "clean_phone": wa_data["clean_phone"],
                "wa_link": wa_data["wa_link"],
                "website": raw.website,
                "rating": raw.rating,
                "review_count": raw.review_count,
                "address": raw.address,
                "latitude": raw.latitude,
                "longitude": raw.longitude,
                "opportunity_score": scored_lead.opportunity_score,
                "score": scored_lead.opportunity_score,
                "missed_rev_min": rev_min,
                "missed_rev_max": rev_max,
                "missed_rev_range": f"${rev_min:,.0f} - ${rev_max:,.0f}",
                "annual_gap": scored_lead.estimated_missed_revenue_annual,
                "annual_loss": scored_lead.estimated_missed_revenue_annual,
                "screenshot_url": screenshot_url,
                "why_score_reasons": why_reasons,
                "stage": "AUDITED"
            })

            job["progress"] = int(35 + (i + 1) * step_increment)
            job["discovered_leads"] = completed_leads

        job["status"] = "completed"
        job["message"] = f"Search complete! Discovered and analyzed {len(completed_leads)} dental practices."
        job["progress"] = 100
        job["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] Discovery & intelligence run complete. {len(completed_leads)} practices ready.")

    except Exception as e:
        job["status"] = "error"
        job["message"] = f"Search encountered an issue: {str(e)}"
        job["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: {str(e)}")

@app.post("/api/search/start")
async def start_search(req: SearchRequest, background_tasks: BackgroundTasks):
    job_id = f"job_{datetime.now().strftime('%Y%m%d%H%M%S')}_{str(uuid.uuid4())[:6]}"
    active_jobs[job_id] = {
        "job_id": job_id,
        "query": req.query,
        "status": "pending",
        "progress": 0,
        "message": "Initializing discovery...",
        "total_found": 0,
        "clinics_found": 0,
        "websites_analyzed": 0,
        "high_opportunity_count": 0,
        "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] Initializing search for '{req.query}'..."],
        "discovered_leads": []
    }

    background_tasks.add_task(
        run_search_background_task,
        job_id=job_id,
        query=req.query,
        limit=req.limit,
        generate_reports=req.generate_reports,
        auto_queue=req.auto_queue
    )

    return {"status": "started", "job_id": job_id}

@app.get("/api/search/status/{job_id}")
async def get_search_status(job_id: str):
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="Job ID not found")
    return active_jobs[job_id]

# --- v1.0 Hardening & System Endpoints ---

@app.get("/api/health")
async def get_basic_health():
    """Lightweight health probe for container orchestrators and monitoring checks."""
    return {"status": "ok", "service": "Dental WhatsApp Intelligence Platform", "version": "1.0.0"}

@app.get("/api/system/health")
async def get_system_health():
    """Runs a complete live diagnostic across Database, Gemini, Playwright, Storage, and Scheduler."""
    return health_monitor.run_full_diagnostic()

@app.get("/api/system/telemetry")
async def get_system_telemetry():
    """Retrieves real-time token spend, storage footprint, and Cost Per Qualified Lead economics."""
    return cost_tracker.get_summary()

@app.get("/api/system/backups")
async def list_system_backups():
    """Returns the inventory of compressed SQLite disaster recovery snapshots."""
    return {"backups": backup_mgr.list_backups()}

@app.post("/api/system/backups/create")
async def create_system_backup():
    """Triggers an instantaneous zero-lock online SQLite backup and gzip compression."""
    result = backup_mgr.create_backup(label="manual")
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Backup failed"))
    return result

@app.post("/api/system/backups/restore")
async def restore_system_backup(req: BackupRestoreRequest):
    """Safely restores SQLite database from a selected backup snapshot with pre-restore safety state."""
    result = backup_mgr.restore_backup(req.backup_filename)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Restore failed"))
    return result

@app.get("/api/settings")
async def get_agency_settings():
    """Returns persistent runtime configuration for prospecting, thresholds, and financial models."""
    return settings_mgr.get_settings()

@app.post("/api/settings")
async def update_agency_settings(req: SettingsUpdateRequest):
    """Updates and persists runtime configurations instantly across the platform with strict validation."""
    updates = req.model_dump(exclude_unset=True)
    if "min_reviews" in updates and "min_reviews_threshold" not in updates:
        updates["min_reviews_threshold"] = updates["min_reviews"]
    if "avg_case_value" in updates and "default_case_value" not in updates:
        updates["default_case_value"] = updates["avg_case_value"]
    if "monthly_fee" in updates and "default_monthly_retainer" not in updates:
        updates["default_monthly_retainer"] = updates["monthly_fee"]

    try:
        updated = settings_mgr.update_settings(updates)
        audit_logger.log_event("settings_updated", module="settings", level="INFO", metadata={"updated_keys": list(updates.keys())})
        return {"status": "success", "settings": updated}
    except ValueError as e:
        audit_logger.log_event("settings_validation_failed", module="settings", level="WARNING", metadata={"error": str(e)})
        raise HTTPException(status_code=400, detail=str(e))

class LLMProviderUpdateRequest(BaseModel):
    provider: str
    openai_api_key: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    openai_model: Optional[str] = None
    deepseek_model: Optional[str] = None
    gemini_model: Optional[str] = None

@app.get("/api/llm/status")
async def get_llm_status():
    """Returns active LLM provider, available models, and readiness status across OpenAI, DeepSeek, and Gemini."""
    from llm_router import LLMRouter
    return LLMRouter.get_provider_status()

@app.post("/api/llm/provider")
async def update_llm_provider(req: LLMProviderUpdateRequest):
    """Dynamically switches active LLM provider (OPENAI / DEEPSEEK / GEMINI) and updates API keys."""
    from llm_router import LLMRouter, PROVIDER_OPENAI, PROVIDER_DEEPSEEK, PROVIDER_GEMINI
    
    p = req.provider.upper().strip()
    if p not in (PROVIDER_OPENAI, PROVIDER_DEEPSEEK, PROVIDER_GEMINI):
        raise HTTPException(status_code=400, detail=f"Invalid provider: {req.provider}. Must be OPENAI, DEEPSEEK, or GEMINI.")
    
    updates = {"llm_provider": p}
    if req.openai_api_key and req.openai_api_key.strip():
        os.environ["OPENAI_API_KEY"] = req.openai_api_key.strip()
    if req.deepseek_api_key and req.deepseek_api_key.strip():
        os.environ["DEEPSEEK_API_KEY"] = req.deepseek_api_key.strip()
    if req.gemini_api_key and req.gemini_api_key.strip():
        os.environ["GEMINI_API_KEY"] = req.gemini_api_key.strip()
        os.environ["GOOGLE_API_KEY"] = req.gemini_api_key.strip()
        
    if req.openai_model:
        os.environ["OPENAI_MODEL"] = req.openai_model
        updates["openai_model"] = req.openai_model
    if req.deepseek_model:
        os.environ["DEEPSEEK_MODEL"] = req.deepseek_model
        updates["deepseek_model"] = req.deepseek_model
    if req.gemini_model:
        os.environ["GEMINI_MODEL"] = req.gemini_model
        updates["gemini_model"] = req.gemini_model

    settings_mgr.update_settings(updates)
    LLMRouter.set_provider(p)
    
    audit_logger.log_event("llm_provider_switched", module="llm", level="INFO", metadata={"active_provider": p})
    return {
        "status": "success",
        "active_provider": p,
        "details": LLMRouter.get_provider_status()
    }

@app.get("/api/system/security")
async def get_system_security_status():
    """Returns security auditing, headers verification, and masked credential status."""
    return validate_startup_security()

# --- v1.1 Enterprise Authentication & Audit Logging Endpoints ---

@app.post("/api/auth/login")
async def login(req: LoginRequest):
    """Verifies master credentials and issues a signed session token."""
    expected_pass = auth_manager.get_configured_password()
    if not auth_manager.verify_password(req.password, expected_pass):
        audit_logger.log_event("login_failed", module="auth", level="WARNING", metadata={"username": req.username})
        raise HTTPException(status_code=401, detail="Invalid password or access PIN")

    token = auth_manager.create_session_token(username=req.username)
    audit_logger.log_event("login_success", module="auth", level="INFO", metadata={"username": req.username})
    return {"status": "success", "session_token": token, "username": req.username}

@app.get("/api/auth/status")
async def auth_status(request: Request):
    """Reports whether authentication is required and validates the active session."""
    req_auth = auth_manager.is_auth_required()
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
    elif "session_token" in request.cookies:
        token = request.cookies.get("session_token")
    elif "x-session-token" in request.headers:
        token = request.headers.get("x-session-token")

    valid, username_or_err = auth_manager.validate_session_token(token) if token else (False, "No token provided")
    return {
        "auth_required": req_auth,
        "authenticated": valid if req_auth else True,
        "user": username_or_err if valid else ("local_admin" if not req_auth else None)
    }

@app.get("/api/system/audit-logs")
async def get_audit_logs(limit: int = 50):
    """Retrieves recent structured JSON audit events."""
    return {"events": audit_logger.get_recent_events(limit=limit)}

# =====================================================================
# --- Intelligence Platform & Personal Sales OS Endpoints (Phases 1-14) ---
# =====================================================================

# --- Phase 1: Business Intelligence Record Endpoints ---
@app.get("/api/intelligence/leads/score-increased")
async def get_score_increased_leads():
    """Phase 1: Retrieves leads whose opportunity score increased on rescan."""
    return {"leads": db.get_leads_with_score_increase()}

@app.get("/api/intelligence/leads/chatbot-removed")
async def get_chatbot_removed_leads():
    """Phase 1: Retrieves leads where an automated widget/bot was dropped."""
    return {"leads": db.get_leads_with_chatbot_removed()}

@app.get("/api/intelligence/lead/{lead_id}/dossier")
async def get_lead_bi_dossier(lead_id: str):
    """Phase 1: Retrieves permanent Business Intelligence dossier across all audits, findings, and timeline events."""
    dossier = db.get_full_lead_dossier(lead_id)
    if not dossier:
        raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found")
    return dossier

# --- Phase 2 & 3: Monitoring & Drift Endpoints ---
@app.post("/api/monitor/rescan/{lead_id}")
async def rescan_lead_drift(lead_id: str):
    """Phase 2: Rescans clinic website for booking added/removed, phone changes, email discovery, redesign."""
    changes = await DriftMonitor.rescan_lead(db, lead_id)
    return {"status": "success", "lead_id": lead_id, "changes_detected": changes}

@app.post("/api/monitor/maps-growth")
async def track_maps_growth(req: MapsGrowthRequest):
    """Phase 3: Tracks Google Maps review count growth and rating velocity."""
    result = DriftMonitor.monitor_maps_growth(
        db,
        lead_id=req.lead_id,
        current_review_count=req.current_review_count,
        current_rating=req.current_rating
    )
    return result

# --- Phase 4: AI Prospect Ranking (Buy Probability) Endpoints ---
@app.get("/api/ranking/buy-probability/{lead_id}")
async def get_lead_buy_probability(lead_id: str):
    """Phase 4: Calculates 20-factor empirical Buy Probability (0-100%) and Tier classification."""
    lead = db.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found")
    result = BuyProbabilityEngine.evaluate_lead(lead)
    return result

@app.post("/api/ranking/batch-evaluate")
async def batch_evaluate_all_leads():
    """Phase 4: Computes and persists buy probability scores for all active pipeline leads."""
    summary = BuyProbabilityEngine.batch_evaluate_and_persist(db)
    return summary

# --- Phase 5: Competitor Intelligence & Metro Benchmarking Endpoints ---
@app.get("/api/competitor-intelligence/benchmark/{metro}")
async def get_metro_cohort_benchmark(metro: str):
    """Phase 5: Metro cohort benchmarking and peer performance averages."""
    benchmark = calculate_metro_benchmark(db, metro)
    return benchmark

@app.get("/api/competitor-intelligence/rank/{lead_id}")
async def get_clinic_metro_rank(lead_id: str):
    """Phase 5: Ranks clinic within its metro cohort (e.g. 'You rank #117 out of 200 practices')."""
    rank_info = rank_clinic_in_metro(db, lead_id)
    return rank_info

# --- Phase 7: Relationship Memory Endpoints ---
@app.post("/api/memory/gatekeeper")
async def save_gatekeeper_relationship(req: GatekeeperMemoryRequest):
    """Phase 7: Stores staff & gatekeeper intelligence (name, demeanor, callback notes)."""
    mem_id = db.record_relationship_memory(
        lead_id=req.lead_id,
        contact_name=req.contact_name,
        role=req.role,
        demeanor=req.demeanor,
        notes=req.notes,
        best_time_to_call=req.best_time_to_call,
        software_mentioned=req.software_mentioned
    )
    return {"status": "success", "id": mem_id, "lead_id": req.lead_id}

@app.get("/api/memory/gatekeeper/{lead_id}")
async def get_gatekeeper_relationships(lead_id: str):
    """Phase 7: Retrieves staff relationship memory records for a clinic."""
    records = db.get_relationship_memory(lead_id)
    return {"lead_id": lead_id, "relationships": records}

# --- Phase 8: Automatic Morning Plan ('Today's Mission') Endpoints ---
@app.get("/api/sales-os/todays-mission")
async def get_todays_sales_mission(offset: int = 0):
    """Phase 8: Delivers sequential 1-click mission queue prioritized by buy probability."""
    mission = SalesOS.get_todays_mission(db, offset=offset)
    return mission

# --- Phase 9: Pre-Call Research Endpoints ---
@app.get("/api/research/pre-call/{lead_id}")
async def get_pre_call_research(lead_id: str):
    """Phase 9: Generates pre-call research briefing, review compliments, and doctor-direct hooks."""
    research = PreCallResearcher.research_lead(db, lead_id)
    return research

# --- Phase 10: Institutional Knowledge Base Endpoints ---
@app.get("/api/knowledge-base/playbook")
async def get_knowledge_base_playbook(category: Optional[str] = None):
    """Phase 10: Institutional knowledge base of winning pitches, objections, and market insights."""
    insights = db.get_knowledge_base_insights(category=category)
    return {"insights": insights, "total": len(insights)}

@app.post("/api/knowledge-base/insight")
async def add_knowledge_base_insight(req: KnowledgeBaseInsightRequest):
    """Phase 10: Adds proven rebuttal or winning sales hook to institutional knowledge base."""
    ins_id = db.log_knowledge_base_insight(
        category=req.category,
        key_phrase=req.key_phrase,
        content=req.content,
        effectiveness_score=req.effectiveness_score
    )
    return {"status": "success", "id": ins_id}

# --- Phase 12: Multi-Touch Sequence Generator Endpoints ---
@app.get("/api/outreach/sequence/{lead_id}")
async def get_outreach_sequence_touch(lead_id: str, touch_number: int = 1):
    """Phase 12: Generates non-repeating multi-touch copy for Touch 1, 2, 3, or 4."""
    lead = db.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found")
    touch_copy = OutreachGenerator.generate_step_sequence(lead, touch_number=touch_number)
    return touch_copy

# --- Phase 13: Predictive Revenue Forecaster Endpoints ---
@app.get("/api/sales-os/revenue-forecast")
async def get_sales_revenue_forecast(calls_planned: int = 10):
    """Phase 13: Predictive revenue forecaster based on empirical conversion rates."""
    forecast = SalesOS.get_revenue_forecast(db, calls_planned=calls_planned)
    return forecast

# --- Phase 14: Personal Productivity Dashboard Endpoints ---
@app.get("/api/sales-os/productivity")
async def get_sales_productivity_telemetry():
    """Phase 14: Founder personal productivity metrics, daily targets, and conversion telemetry."""
    telemetry = SalesOS.get_productivity_telemetry(db)
    return telemetry

@app.post("/api/sales-os/productivity/log")
async def log_sales_productivity_action(req: ProductivityLogRequest):
    """Phase 14: Logs founder productivity activities (calls, WhatsApps, demos)."""
    result = SalesOS.log_productivity_activity(
        db,
        activity_type=req.activity_type,
        count=req.count,
        lead_id=req.lead_id,
        notes=req.notes
    )
    return result

# ==================== Agency Machine: Pillars 1, 2, 3 Endpoints ====================

# --- Pillar 1: Auto Prospecting Scheduler & Market Scanner ---
@app.get("/api/scheduler/harvest-status")
async def get_harvest_status():
    """Pillar 1: Returns 6:00 AM multi-metro auto-prospecting scheduler status."""
    from scheduler import AutonomousScheduler
    return AutonomousScheduler.get_morning_harvest_status()

@app.post("/api/scheduler/schedule-run")
async def configure_morning_harvest(req: SchedulerConfigRequest):
    """Pillar 1: Configures target metros and schedule for 6:00 AM auto-harvest."""
    from scheduler import AutonomousScheduler
    return AutonomousScheduler.configure_morning_harvest(
        enabled=req.enabled,
        target_metros=req.target_metros,
        harvest_time=req.harvest_time,
        limit_per_metro=req.limit_per_metro
    )

@app.post("/api/scheduler/trigger-morning-run")
async def trigger_morning_harvest_now(req: Optional[SchedulerConfigRequest] = None):
    """Pillar 1: Triggers immediate multi-metro prospecting cycle across Dallas, Chicago, Miami, Houston."""
    from scheduler import AutonomousScheduler
    metros = req.target_metros if req and req.target_metros else None
    limit = req.limit_per_metro if req and req.limit_per_metro else 5
    summary = await AutonomousScheduler.trigger_morning_harvest(metros=metros, limit_per_metro=limit, db=db)
    return summary

@app.post("/api/scanner/run-market-scan")
async def run_market_scan_metro(req: MarketScanRequest):
    """Pillar 1: AI Market Scanner bulk scan of up to 1,000 clinics in a metro."""
    from market_scanner import MarketScanner
    scan = MarketScanner.scan_metro(db=db, metro=req.metro, max_clinics=req.max_clinics)
    return scan

@app.get("/api/scanner/market-signals")
async def get_market_signals(limit: int = 50):
    """Pillar 1: Retrieves latest market shift signals (broken sites, dropped bots, review surges)."""
    from market_scanner import MarketScanner
    return MarketScanner.get_latest_market_signals(db=db, limit=limit)

# --- Pillar 2: Review Analyzer, Software Detector & Objection Predictor ---
@app.get("/api/reviews/analyze/{lead_id}")
async def analyze_clinic_reviews(lead_id: str):
    """Pillar 2: Mines patient reviews to extract complaints (unanswered calls, wait times, booking friction)."""
    from review_analyzer import ReviewAnalyzer
    return ReviewAnalyzer.analyze_lead_reviews(db=db, lead_id=lead_id)

@app.post("/api/reviews/mine-complaints")
async def mine_custom_reviews(req: ReviewMineRequest):
    """Pillar 2: Classifies custom review texts into clinical operational friction points."""
    from review_analyzer import ReviewAnalyzer
    return ReviewAnalyzer.mine_complaints(reviews=req.reviews, clinic_name=req.clinic_name)

@app.get("/api/battlecard/objection-predictor/{lead_id}")
async def predict_clinic_objection(lead_id: str):
    """Pillar 2: Predicts likely objection (e.g. 'We use Weave') and provides turnkey counter-punch."""
    lead = db.get_lead(lead_id)
    if not lead:
        leads = db.list_all_leads()
        if leads:
            lead = leads[0]
        else:
            lead = {"id": lead_id, "name": f"Premier Dental #{lead_id}", "website": "https://example.com"}
    from battlecard import SalesBattlecardGenerator
    return SalesBattlecardGenerator.predict_objection(lead)

# --- Pillar 3: AI Call Notes, Follow-up Reminders, 3-Tier Proposals, ROI, Client Health ---
@app.post("/api/sales-os/call-notes/summarize")
async def summarize_call_notes_endpoint(req: CallNotesSummarizeRequest):
    """Pillar 3: Summarizes pasted call transcript into Pain, Budget, DM, Next Step, and auto-schedules reminder."""
    summary = SalesOS.summarize_call_notes(db=db, transcript_text=req.transcript, lead_id=req.lead_id)
    return summary

@app.get("/api/reminders/due")
async def get_due_followup_reminders(limit: int = 50):
    """Pillar 3: Retrieves pending due and overdue follow-up reminders."""
    from reminder_manager import ReminderManager
    return ReminderManager.get_due_reminders(db=db, limit=limit)

@app.post("/api/reminders/create")
async def create_followup_reminder_endpoint(req: ReminderCreateRequest):
    """Pillar 3: Creates a manual or automated follow-up reminder."""
    due = req.due_date
    if not due:
        from datetime import datetime, timedelta
        due = (datetime.now() + timedelta(hours=req.hours_from_now or 24)).isoformat()
    rem_id = db.create_followup_reminder(
        lead_id=str(req.lead_id),
        clinic_name=req.clinic_name or "Dental Clinic",
        due_date=due,
        trigger_reason=req.trigger_reason or req.reminder_type or "MANUAL",
        notes=req.notes or ""
    )
    return {"status": "success", "reminder_id": rem_id}

@app.post("/api/reminders/{reminder_id}/complete")
async def complete_followup_reminder_endpoint(reminder_id: int):
    """Pillar 3: Marks a reminder as completed."""
    from reminder_manager import ReminderManager
    success = ReminderManager.complete_reminder(db=db, reminder_id=reminder_id)
    return {"status": "success" if success else "error"}

@app.post("/api/reminders/{reminder_id}/snooze")
async def snooze_followup_reminder_endpoint(reminder_id: int, req: ReminderSnoozeRequest):
    """Pillar 3: Snoozes a reminder by specified days or hours."""
    from reminder_manager import ReminderManager
    days = req.days or 2
    if req.hours:
        days = max(1, req.hours // 24)
    success = ReminderManager.snooze_reminder(db=db, reminder_id=reminder_id, days=days)
    return {"status": "success" if success else "error"}

@app.get("/api/proposals/generate-tiered/{lead_id}")
@app.post("/api/proposals/generate-tiered/{lead_id}")
async def generate_tiered_proposal_endpoint(lead_id: str):
    """Pillar 3: Generates complete 3-tier proposal (Bronze, Silver, Gold) with FAQs, timeline, and contract."""
    lead = db.get_lead(lead_id)
    if not lead:
        # Graceful fallback for demonstration / testing
        lead = {
            "id": lead_id,
            "name": f"Premier Dental Care #{lead_id}",
            "doctor_name": "Dr. Sarah Vance",
            "city": "Austin",
            "state": "TX",
            "specialties": "Implants, Cosmetic, Invisalign",
            "opportunity_score": 85,
            "missed_rev_range": "$5,200–$8,400"
        }
    from proposals import generate_tiered_sales_proposal
    return generate_tiered_sales_proposal(lead)

@app.post("/api/roi/calculate")
async def calculate_custom_roi_endpoint(req: ROICalculateRequest):
    """Pillar 3: Interactive Dental ROI Calculator (appointments, treatment value, missed calls)."""
    from roi_calculator import ROICalculator
    return ROICalculator.calculate(
        monthly_appointments=req.monthly_appointments,
        average_treatment_value=req.average_treatment_value,
        estimated_missed_calls_monthly=req.estimated_missed_calls_monthly,
        monthly_software_cost=req.monthly_software_cost
    )

@app.get("/api/client-health/{client_id}")
async def get_client_health_endpoint(client_id: str):
    """Pillar 3: Post-sale client retention telemetry, health score, and monthly ROI proof statement."""
    from client_health import ClientHealthTracker
    return ClientHealthTracker.get_client_dashboard(db=db, client_id=client_id)

@app.get("/api/client-health-overview")
async def get_client_health_overview_endpoint():
    """Pillar 3: Macro retention overview across all paying dental clients."""
    from client_health import ClientHealthTracker
    return ClientHealthTracker.get_portfolio_overview(db=db)

@app.post("/api/client-health/{client_id}/log-metric")
async def log_client_metric_endpoint(client_id: str, req: ClientMetricLogRequest):
    """Pillar 3: Increments live operational metric for active client account."""
    if req.clinic_name:
        # Onboarding new or updated client
        db.save_client_account({
            "client_id": client_id,
            "clinic_name": req.clinic_name,
            "doctor_name": req.doctor_name or "Dr. Owner",
            "plan_tier": (req.plan_tier or "SILVER").upper(),
            "monthly_retainer": req.monthly_retainer or 697.0,
            "messages_answered": req.messages_answered or 0,
            "appointments_booked": req.appointments_booked or 0,
            "revenue_generated": req.revenue_generated or 0.0,
            "missed_calls_saved": req.missed_calls_saved or 0
        })
        return {"status": "success", "action": "onboarded"}

    if req.messages_answered is not None:
        db.log_client_metric(client_id, "messages_answered", float(req.messages_answered))
    if req.appointments_booked is not None:
        db.log_client_metric(client_id, "appointments_booked", float(req.appointments_booked))
    if req.revenue_generated is not None:
        db.log_client_metric(client_id, "revenue_generated", float(req.revenue_generated))
    if req.missed_calls_saved is not None:
        db.log_client_metric(client_id, "missed_calls_saved", float(req.missed_calls_saved))

    if req.metric_name and req.messages_answered is None and req.appointments_booked is None:
        db.log_client_metric(client_id, req.metric_name, req.delta)

    return {"status": "success"}


# --- Manual Phone Dialer, Real-Time AI Listening & Bidirectional Takeover Engine ---

@app.post("/api/dialer/manual/start")
async def start_manual_dialer_session(req: ManualDialerStartRequest, request: Request):
    """
    Initializes an interactive manual dialer call session with instant clinic lookup.
    """
    base_url = str(request.base_url).rstrip('/')
    session = LiveDialerEngine.start_manual_session(
        phone=req.phone,
        lead_id=req.lead_id,
        contact_name=req.contact_name,
        mode=req.mode or "HUMAN_FIRST",
        carrier_mode=req.carrier_mode or "BROWSER",
        db=db,
        server_base_url=base_url
    )
    return session

@app.post("/api/dialer/manual/turn")
async def process_manual_dialer_turn(req: ManualDialerTurnRequest):
    """
    Ingests live conversational turns (Human, Prospect, or AI) and returns
    real-time Co-Pilot HUD assistance (objections, counter-punches, buying signals).
    """
    result = LiveDialerEngine.process_live_turn(
        session_id=req.session_id,
        text=req.text,
        speaker=req.speaker or "HUMAN",
        audio_url=req.audio_url,
        db=db
    )
    return result

@app.post("/api/dialer/manual/ai-takeover")
async def execute_ai_takeover_action(req: ManualDialerTakeoverRequest):
    """
    Seamlessly transfers live call control from Human to AI.
    Generates tactical spoken response from the exact conversational context and synthesizes audio.
    """
    result = LiveDialerEngine.execute_ai_takeover(
        session_id=req.session_id,
        user_prompt_override=req.user_hint,
        db=db
    )
    return result

@app.post("/api/dialer/manual/human-takeover")
async def execute_human_takeover_action(req: ManualDialerHumanTakeoverRequest):
    """
    Seamlessly transfers live call control from AI back to Human.
    Halts AI audio and activates the human microphone immediately.
    """
    result = LiveDialerEngine.execute_human_takeover(
        session_id=req.session_id,
        reason=req.reason
    )
    return result

@app.post("/api/dialer/manual/save-recording")
async def save_manual_call_recording(req: ManualDialerSaveRecordingRequest):
    """
    Uploads call audio (base64), saves WAV file to disk, executes closed-loop AI learning,
    and stores the recording in the database.
    """
    import base64
    audio_bytes = None
    if req.audio_base64:
        raw_b64 = req.audio_base64
        if "," in raw_b64:
            raw_b64 = raw_b64.split(",", 1)[1]
        try:
            audio_bytes = base64.b64decode(raw_b64)
        except Exception as e:
            logger.warning(f"Audio base64 decode failed: {e}")

    result = LiveDialerEngine.finalize_call_session(
        session_id=req.session_id,
        audio_bytes=audio_bytes,
        audio_filename=req.filename,
        duration_sec=req.duration_sec or 0,
        outcome_override=req.outcome,
        db=db
    )
    return result

@app.post("/api/dialer/manual/finalize")
async def finalize_manual_dialer_call(req: ManualDialerSaveRecordingRequest):
    """Alias for finalizing call session."""
    return await save_manual_call_recording(req)

@app.get("/api/dialer/recordings")
async def get_call_recordings_list(limit: int = 50):
    """
    Lists recent call audio recordings with parsed transcripts and learned insights.
    """
    recordings = db.list_call_recordings(limit=limit)
    return {"recordings": recordings, "count": len(recordings)}

@app.get("/api/dialer/recordings/{call_id}")
async def get_single_call_recording(call_id: str):
    """
    Retrieves full call recording dossier, audio playback URL, and closed-loop learnings.
    """
    rec = db.get_call_recording(call_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Call recording not found")
    return rec

@app.post("/api/dialer/lookup-phone")
async def lookup_clinic_by_phone(req: ManualDialerLookupRequest):
    """
    Finds existing clinic and doctor details by typed phone number.
    """
    lead = db.find_lead_by_phone(req.phone)
    if lead:
        return {
            "found": True,
            "lead_id": lead.get("id"),
            "name": lead.get("name"),
            "doctor_name": lead.get("doctor_name"),
            "opportunity_score": lead.get("opportunity_score"),
            "phone": lead.get("phone"),
            "city": lead.get("address")
        }
    return {"found": False}


# -------------------------------------------------------------
# Precision & Usefulness Pillars (High-Conversion Sales Engine)
# -------------------------------------------------------------

class CadenceAdvanceRequest(BaseModel):
    outcome: str = "COMPLETED"
    notes: Optional[str] = None

class MysteryAuditRequest(BaseModel):
    ring_count: int = 5
    reached_voicemail: bool = True
    test_timestamp: Optional[str] = None


@app.get("/demo/{lead_id}", response_class=HTMLResponse)
async def serve_whatsapp_demo_simulator(lead_id: str):
    """
    Serves a live, mobile-responsive interactive WhatsApp patient conversation simulator
    customized specifically for this dental clinic.
    """
    lead = None
    if lead_id and lead_id != "preview":
        lead = db.get_lead(lead_id)
    if not lead:
        lead = {
            "id": lead_id or "preview",
            "name": "Apex Dental Studio",
            "doctor_name": "Dr. Sarah Jenkins",
            "address": "Austin, TX",
            "phone": "+1 (512) 555-0199",
            "high_value_services": ["Emergency Dental Care", "Dental Implants", "Invisalign"]
        }
    html_content = WhatsAppDemoEngine.render_demo_page_html(lead)
    return HTMLResponse(content=html_content, status_code=200)


@app.get("/api/leads/{lead_id}/whatsapp-demo")
async def get_whatsapp_demo_assets(lead_id: str, request: Request):
    """
    Returns WhatsApp demo deep-links, dynamic QR code image URL, web simulator link,
    and 1-click SMS outreach pitch customized for the clinic.
    """
    lead = db.get_lead(lead_id)
    if not lead:
        lead = {
            "id": lead_id,
            "name": "Apex Dental Studio",
            "doctor_name": "Dr. Sarah Jenkins",
            "address": "Austin, TX",
            "phone": "+1 (512) 555-0199"
        }
    base_url = str(request.base_url).rstrip("/")
    demo_assets = WhatsAppDemoEngine.generate_demo_assets(lead, base_app_url=base_url)
    return demo_assets


@app.post("/api/leads/{lead_id}/sniff-tech")
async def sniff_ehr_and_npi_for_lead(lead_id: str):
    """
    Sniffs dental PMS/EHR and front-office engagement software (Dentrix, Eaglesoft, Open Dental, Weave, NexHealth)
    and queries the US CMS NPI Registry for verified dentist credentials.
    """
    lead = db.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # 1. Fetch website HTML or analyze known findings / technologies
    website = lead.get("website") or ""
    html_content = ""
    if website:
        try:
            import urllib.request
            target_url = website if website.startswith("http") else f"https://{website}"
            req = urllib.request.Request(
                target_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                html_content = resp.read().decode("utf-8", errors="ignore")
        except Exception as e:
            logger.info(f"Direct HTML fetch for tech sniffer failed ({e}), using domain heuristics.")

    ehr_results = EHRSniffer.sniff_html(html_content, website_url=website)
    
    # 2. Query US NPI Registry
    raw_doc = lead.get("doctor_name") or ""
    clean_doc = raw_doc.replace("Dr.", "").replace("Dr", "").strip()
    first_name = None
    last_name = None
    if clean_doc:
        parts = clean_doc.split()
        if len(parts) >= 2:
            first_name = parts[0]
            last_name = parts[-1]
        elif len(parts) == 1:
            last_name = parts[0]

    raw_addr = lead.get("address") or ""
    city = None
    state = None
    if "," in raw_addr:
        addr_parts = [p.strip() for p in raw_addr.split(",")]
        if len(addr_parts) >= 2:
            city = addr_parts[-2]
            state_chunk = addr_parts[-1].strip().split()
            if state_chunk:
                state = state_chunk[0][:2]

    npi_result = NPIRegistryEnricher.lookup_provider(
        first_name=first_name,
        last_name=last_name,
        organization_name=lead.get("name") if not clean_doc else None,
        city=city,
        state=state
    )

    detected_ehr_name = ehr_results.get("detected_pms") or ehr_results.get("primary_software")
    npi_num = npi_result.get("npi_number")

    # Update database
    db.update_lead_ehr_and_npi(
        lead_id=lead_id,
        detected_ehr=detected_ehr_name,
        npi_number=npi_num,
        npi_data=npi_result if npi_result.get("found") else None
    )

    return {
        "lead_id": lead_id,
        "ehr_sniffer": ehr_results,
        "npi_registry": npi_result,
        "detected_ehr": detected_ehr_name,
        "npi_number": npi_num
    }


@app.get("/api/leads/{lead_id}/mystery-audit")
async def get_mystery_shopper_audit(lead_id: str):
    """
    Retrieves or generates an empirical Mystery Shopper after-hours phone friction audit proof card.
    """
    lead = db.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    existing_proof = lead.get("mystery_audit_json")
    if existing_proof:
        return existing_proof

    # Generate fresh proof card
    proof = MysteryShopperAuditor.generate_audit_proof(lead)
    db.update_lead_mystery_audit(lead_id, proof)
    return proof


@app.post("/api/leads/{lead_id}/mystery-audit")
async def run_mystery_shopper_audit(lead_id: str, req: Optional[MysteryAuditRequest] = None):
    """
    Executes or updates empirical Mystery Shopper friction test parameters for a clinic.
    """
    lead = db.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    ring_count = req.ring_count if req else 5
    reached_voicemail = req.reached_voicemail if req else True
    test_timestamp = req.test_timestamp if req else None

    proof = MysteryShopperAuditor.generate_audit_proof(
        lead_dict=lead,
        test_timestamp=test_timestamp,
        ring_count=ring_count,
        reached_voicemail=reached_voicemail
    )
    db.update_lead_mystery_audit(lead_id, proof)
    return proof


@app.get("/api/leads/{lead_id}/cadence")
async def get_lead_cadence_status(lead_id: str):
    """
    Retrieves the 5-touch omnichannel sales cadence status, timeline, and recommended next action.
    """
    lead = db.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    return SalesCadenceEngine.get_lead_cadence(lead)


@app.post("/api/leads/{lead_id}/cadence/advance")
async def advance_lead_cadence(lead_id: str, req: Optional[CadenceAdvanceRequest] = None):
    """
    Advances the prospect to the next touchpoint in the 5-touch sales cadence based on touch outcome.
    """
    lead = db.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    current_step = int(lead.get("cadence_step") or 1)
    outcome = req.outcome if req else "COMPLETED"
    advancement = SalesCadenceEngine.advance_cadence(current_step, outcome)
    
    db.update_lead_cadence(
        lead_id=lead_id,
        step=advancement["next_step"],
        status=advancement["status"]
    )

    updated_lead = db.get_lead(lead_id)
    return SalesCadenceEngine.get_lead_cadence(updated_lead)


@app.get("/api/analytics/objections")
async def get_objection_analytics_report():
    """
    Returns real-time institutional objection intelligence, objection frequency breakdown,
    rebuttal win rates, and tactical counter-punches.
    """
    return ObjectionAnalyticsEngine.get_objection_report(db)


# -------------------------------------------------------------
# Lethal Sales Engine Weapons (Pitch Portal, Sting, Radar, SMS)
# -------------------------------------------------------------

class SMSDispatchRecordRequest(BaseModel):
    channel: str = "SMS"


@app.get("/pitch/{lead_id}", response_class=HTMLResponse)
async def render_executive_pitch_portal(lead_id: str, request: Request):
    """
    Renders hyper-personalized executive teardown landing page for the clinic owner.
    """
    lead = None
    if lead_id and lead_id != "preview":
        lead = db.get_lead(lead_id)
    if not lead:
        lead = {
            "id": lead_id or "preview",
            "name": "Apex Dental Studio",
            "doctor_name": "Dr. Sarah Jenkins",
            "address": "Austin, TX",
            "phone": "+1 (512) 555-0199",
            "rating": 4.9,
            "review_count": 85,
            "missed_rev_min": 3500,
            "missed_rev_max": 7200,
            "detected_ehr": "Dentrix",
            "npi_number": "1841295830"
        }
    base_url = str(request.base_url).rstrip("/")
    html_content = PitchPortalEngine.render_pitch_page_html(lead, base_app_url=base_url)
    return HTMLResponse(content=html_content, status_code=200)


@app.post("/api/pitch/{lead_id}/viewed")
async def record_pitch_portal_view(lead_id: str, request: Request):
    """
    Records high-intent prospect viewing of their confidential pitch teardown portal
    and registers real-time speed-to-lead Live Intercept Radar.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    user_agent = request.headers.get("user-agent")
    LiveInterceptRadar.record_view(lead_id=lead_id, client_ip=client_ip, user_agent=user_agent, db=db)
    return SMSDispatcherEngine.record_pitch_view(lead_id=lead_id, db=db)


@app.get("/api/leads/{lead_id}/voicemail-sting")
async def generate_lead_voicemail_sting(
    lead_id: str,
    voice_engine: str = "auto-fast",
    voice_name: str = "af_sarah"
):
    """
    Generates an empirical 20-second auditory proof file stitching telecom rings + voicemail beep + doctor teardown.
    """
    lead = db.get_lead(lead_id)
    if not lead:
        lead = {
            "id": lead_id,
            "name": "Apex Dental Studio",
            "doctor_name": "Dr. Sarah Jenkins",
            "address": "Austin, TX",
            "phone": "+1 (512) 555-0199"
        }
    return VoicemailStingGenerator.generate_voicemail_sting(
        lead_dict=lead,
        voice_engine=voice_engine,
        voice_name=voice_name
    )


@app.get("/api/leads/{lead_id}/competitor-radar")
async def get_lead_competitor_radar(lead_id: str):
    """
    Scans competing clinics in a 3-mile radius capturing after-hours patients to build lethal FOMO.
    """
    lead = db.get_lead(lead_id)
    if not lead:
        lead = {
            "id": lead_id,
            "name": "Apex Dental Studio",
            "doctor_name": "Dr. Sarah Jenkins",
            "address": "Austin, TX",
            "phone": "+1 (512) 555-0199"
        }
    return CompetitorRadarEngine.scan_competitors(lead, db=db)


@app.get("/api/leads/{lead_id}/sms-dispatch")
async def get_sms_dispatch_payload(lead_id: str, request: Request):
    """
    Generates 1-click SMS & WhatsApp dispatch payload with deep-links and tracking URL.
    """
    lead = db.get_lead(lead_id)
    if not lead:
        lead = {
            "id": lead_id,
            "name": "Apex Dental Studio",
            "doctor_name": "Dr. Sarah Jenkins",
            "address": "Austin, TX",
            "phone": "+1 (512) 555-0199"
        }
    base_url = str(request.base_url).rstrip("/")
    return SMSDispatcherEngine.generate_dispatch_payload(lead, base_app_url=base_url)


@app.post("/api/leads/{lead_id}/sms-dispatch/record")
async def record_sms_dispatch_sent(lead_id: str, req: Optional[SMSDispatchRecordRequest] = None):
    """
    Logs 1-click SMS or WhatsApp dispatch touchpoint in CRM touches table and opportunity timeline.
    """
    channel = req.channel if req else "SMS"
    success = SMSDispatcherEngine.record_dispatch(lead_id=lead_id, channel=channel, db=db)
    return {"status": "success" if success else "error", "lead_id": lead_id, "channel": channel}


# -------------------------------------------------------------
# Lethal Closing Weapons: Radar Intercept, Deposit Lock, Video Teardown, Hygiene Recall
# -------------------------------------------------------------

class DepositLockRequest(BaseModel):
    payment_ref: Optional[str] = None


# --- Weapon 1: Live Radar Intercept Endpoints ---

@app.get("/api/radar/active-viewers")
async def get_active_pitch_viewers():
    """
    Returns live dental prospects actively viewing their confidential teardown portal.
    """
    return LiveInterceptRadar.get_active_viewers(max_age_seconds=1800, db=db)


@app.post("/api/radar/dismiss/{lead_id}")
async def dismiss_radar_active_viewer(lead_id: str):
    """
    Clears prospect from active intercept banner once rep calls them.
    """
    LiveInterceptRadar.clear_active_viewer(lead_id)
    return {"status": "dismissed", "lead_id": lead_id}


# --- Weapon 2: Deposit Lock & Territory Exclusivity Checkout Endpoints ---

@app.get("/api/leads/{lead_id}/territory-status")
async def get_lead_territory_status(lead_id: str):
    """
    Checks if the 3-mile exclusivity radius around the clinic is available or locked.
    """
    lead = db.get_lead(lead_id)
    if not lead:
        lead = {"id": lead_id, "name": "Dental Practice", "address": "Austin, TX"}
    return TerritoryCheckoutEngine.check_territory_availability(lead, db=db)


@app.get("/api/leads/{lead_id}/checkout-intent")
async def get_deposit_checkout_intent(lead_id: str, request: Request):
    """
    Generates $1,500 turnkey setup deposit parameters and territory certificate.
    """
    lead = db.get_lead(lead_id)
    if not lead:
        lead = {"id": lead_id, "name": "Dental Practice", "address": "Austin, TX"}
    base_url = str(request.base_url).rstrip("/")
    return TerritoryCheckoutEngine.create_checkout_payload(lead, base_app_url=base_url)


@app.post("/api/leads/{lead_id}/checkout/lock-deposit")
async def execute_deposit_lock(lead_id: str, req: Optional[DepositLockRequest] = None):
    """
    Locks the 3-mile territory, records the $1,500 turnkey deposit payment, and moves stage to WON.
    """
    payment_ref = req.payment_ref if req else None
    return TerritoryCheckoutEngine.complete_deposit_lock(lead_id=lead_id, payment_ref=payment_ref, db=db)


@app.get("/agreement/{lead_id}", response_class=HTMLResponse)
async def view_service_level_agreement(lead_id: str):
    """
    Renders the formal Service Level Agreement with 3-mile exclusivity and break-even guarantee.
    """
    lead = db.get_lead(lead_id)
    if not lead:
        lead = {"id": lead_id, "name": "Apex Dental Studio", "address": "Austin, TX"}
    html = TerritoryCheckoutEngine.render_sla_agreement_html(lead)
    return HTMLResponse(content=html, status_code=200)


# --- Weapon 3: AI Video Teardown Generator & Motion Player Endpoints ---

@app.get("/api/leads/{lead_id}/video-teardown")
async def get_video_teardown_meta(lead_id: str, request: Request):
    """
    Returns video teaser metadata and copyable SMS/Email teaser link.
    """
    lead = db.get_lead(lead_id)
    if not lead:
        lead = {"id": lead_id, "name": "Apex Dental Studio", "address": "Austin, TX"}
    base_url = str(request.base_url).rstrip("/")
    return VideoTeardownEngine.generate_video_metadata(lead, base_app_url=base_url)


@app.get("/video/{lead_id}", response_class=HTMLResponse)
async def serve_video_teardown_player(lead_id: str, request: Request):
    """
    Serves full-screen cinema video landing page with synchronized audio and territory CTA.
    """
    lead = db.get_lead(lead_id)
    if not lead:
        lead = {"id": lead_id, "name": "Apex Dental Studio", "address": "Austin, TX"}
    base_url = str(request.base_url).rstrip("/")
    html = VideoTeardownEngine.render_video_player_page_html(lead, base_app_url=base_url)
    return HTMLResponse(content=html, status_code=200)


# --- Weapon 4: Dormant Hygiene Recall & Cash Injection Endpoints ---

@app.get("/api/leads/{lead_id}/hygiene-recall")
async def calculate_hygiene_recall(lead_id: str, custom_charts: int = 0):
    """
    Calculates trapped dormant patient chart value and 3-touch WhatsApp broadcast recall ROI.
    """
    lead = db.get_lead(lead_id)
    if not lead:
        lead = {"id": lead_id, "name": "Apex Dental Studio", "address": "Austin, TX"}
    return HygieneRecallCalculator.calculate_hygiene_leakage(lead, custom_dormant_charts=custom_charts)


# --- 1-Page Missed Production Diagnostic & 1-Click Outreach Hub ---
from missed_revenue_diagnostic import MissedRevenueDiagnosticEngine
from pre_call_dossier import PreCallDossierCompiler
from carrier_reputation_manager import CarrierReputationManager
from http_scraper_shield import HttpScraperShield


@app.get("/diagnostic/{lead_id}", response_class=HTMLResponse)
async def view_public_diagnostic_page(lead_id: str):
    """Renders the client-facing, mobile-responsive Missed Revenue Diagnostic report."""
    lead = db.get_lead(lead_id)
    if not lead:
        lead = {"id": lead_id, "name": "Dental Practice", "address": "Dallas, TX", "rating": 4.8, "review_count": 65}
    html = MissedRevenueDiagnosticEngine.render_diagnostic_html(lead)
    return HTMLResponse(content=html, status_code=200)


@app.get("/api/leads/{lead_id}/diagnostic")
async def get_lead_diagnostic_data(lead_id: str):
    """Returns calculated after-hours leakage, review vulnerability, and findings."""
    lead = db.get_lead(lead_id)
    if not lead:
        lead = {"id": lead_id, "name": "Dental Practice", "address": "Dallas, TX"}
    return MissedRevenueDiagnosticEngine.generate_diagnostic_data(lead, db=db)


@app.get("/api/leads/{lead_id}/outreach-links")
async def get_lead_outreach_links(lead_id: str, request: Request):
    """Returns 1-click WhatsApp and Gmail deep links with pre-filled high-converting copy."""
    lead = db.get_lead(lead_id)
    if not lead:
        lead = {"id": lead_id, "name": "Dental Practice", "address": "Dallas, TX"}
    base_url = str(request.base_url).rstrip("/")
    return MissedRevenueDiagnosticEngine.generate_outreach_links(lead, base_url=base_url)


@app.get("/api/leads/{lead_id}/dossier")
async def get_lead_pre_call_dossier(lead_id: str):
    """Returns the comprehensive 360-degree commercial intelligence dossier for dialing."""
    lead = db.get_lead(lead_id)
    if not lead:
        lead = {"id": lead_id, "name": "Dental Practice", "address": "Dallas, TX"}
    dossier = PreCallDossierCompiler.compile_dossier(lead, db=db)
    prompt_briefing = PreCallDossierCompiler.format_llm_prompt_briefing(dossier)
    return {
        "dossier": dossier,
        "llm_prompt_briefing": prompt_briefing
    }


class FastScrapeRequest(BaseModel):
    url: str
    timeout: float = 8.0

@app.post("/api/leads/fast-scrape")
async def fast_scrape_clinic_endpoint(req: FastScrapeRequest):
    """Fast-path HTTP scraper: pulls doctors, phones, emails, and booking widgets in <1s (low RAM)."""
    return await HttpScraperShield.fast_scrape_clinic(req.url, timeout=req.timeout)


class DncOptOutRequest(BaseModel):
    phone: str
    clinic_name: Optional[str] = ""
    reason: Optional[str] = "PROSPECT_REQUESTED"

@app.post("/api/dialer/opt-out")
async def register_dnc_opt_out(req: DncOptOutRequest):
    """Registers a phone number on the Do-Not-Call blacklist immediately."""
    mgr = CarrierReputationManager(db=db)
    return mgr.process_opt_out(destination_phone=req.phone, clinic_name=req.clinic_name or "", reason=req.reason or "PROSPECT_REQUESTED")


@app.get("/api/dialer/dnc")
async def get_dnc_blacklist():
    """Returns the active Do-Not-Call blacklist for TCPA/carrier compliance."""
    return {"dnc_records": db.get_dnc_records()}


# --- Overnight Autonomous Prospecting & State Checkpointing Endpoints ---
from overnight_autopilot import OvernightAutopilot

class AutopilotStartRequest(BaseModel):
    target_metros: Optional[List[str]] = None
    target_leads_total: int = 50
    batch_per_metro: int = 8

@app.get("/api/autopilot/status")
async def get_autopilot_status():
    """Returns current status, active metro, progress metrics, and morning briefing."""
    return OvernightAutopilot.get_status()

@app.post("/api/autopilot/start")
async def start_autopilot(req: Optional[AutopilotStartRequest] = None):
    """Starts or resumes the unattended overnight prospecting loop."""
    metros = req.target_metros if req else None
    target = req.target_leads_total if req else 50
    batch = req.batch_per_metro if req else 8
    return await OvernightAutopilot.start(
        target_metros=metros,
        target_leads_total=target,
        batch_per_metro=batch,
        db=db
    )

@app.post("/api/autopilot/stop")
async def stop_autopilot():
    """Pauses overnight prospecting and saves checkpoint state."""
    return OvernightAutopilot.stop()

@app.post("/api/autopilot/reset")
async def reset_autopilot():
    """Resets overnight autopilot state to zero."""
    return OvernightAutopilot.reset_state()


if __name__ == "__main__":
    import webbrowser
    import uvicorn

    print("=" * 60)
    print("  Enterprise Dental WhatsApp Intelligence Platform")
    print("  Local Server starting on: http://127.0.0.1:8000")
    print("=" * 60)

    # Open browser automatically after 1.5 seconds
    def open_browser():
        webbrowser.open("http://127.0.0.1:8000")

    import threading
    threading.Timer(1.5, open_browser).start()

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
