# REST & WebSocket API Reference

The application exposes a high-performance FastAPI service running on port `8000` (and tunneled via Cloudflare). All endpoints accept and return JSON unless otherwise specified.

---

## 1. Practice Leads & Enterprise Qualification

### `GET /api/leads`
Retrieves practices discovered and audited in the system.
- **Query Parameters**:
  - `stage` (optional, string): Filter by CRM stage (`ALL`, `FOUND`, `AUDITED`, `EMAIL_PREPARED`, `SENT`, `REPLIED`, `MEETING`, `WON`).
  - `search` (optional, string): Case-insensitive match on clinic name, phone, or website.
  - `limit` (optional, integer, default: `100`): Maximum records returned.
- **Response**: Array of lead objects enriched with:
  - `bant_score` (0–100), `bant_rating` (`A_TIER`, `B_TIER`, `C_TIER`)
  - `meddic_pct` (0–100%), `meddic_tier` (`ENTERPRISE_READY`, `QUALIFIED`, `NURTURE`)
  - `clean_phone`, `wa_link`, `missed_rev_range`, `win_probability_pct`

---

### `GET /api/leads/{lead_id}`
Returns a 360-degree intelligence dossier on a single practice.
- **Path Parameters**:
  - `lead_id` (string): Unique identifier (e.g., `lead_austindentalcare_httpsaustindentalcarecom`).
- **Response**:
  ```json
  {
    "lead": { ... },
    "audit": { "tech_stack": ["Dentrix", "Weave"], "has_online_booking": false, ... },
    "findings": [ ... ],
    "technologies": [ ... ],
    "notes": [ ... ],
    "history": [ ... ],
    "whatsapp": { "pitch": "...", "wa_link": "..." },
    "bant_meddic": {
      "bant": { "total_score": 84, "rating": "A_TIER", "dimensions": { ... } },
      "meddic": { "overall_completeness_pct": 92, "tier": "ENTERPRISE_READY", "dimensions": { ... } },
      "recommendation": "IMMEDIATE_CALL: Perfect profile. Owner dentist identified..."
    },
    "dossier_pdf_url": "/api/leads/{lead_id}/download-pdf-dossier"
  }
  ```

---

### `GET /api/leads/{lead_id}/bant-meddic`
Dedicated endpoint returning standalone BANT and MEDDIC evaluation breakdowns.
- **Response**:
  ```json
  {
    "lead_id": "lead_sunsetdental_httpssunsetdentalcom",
    "clinic_name": "Sunset Dental Studio",
    "doctor_name": "Dr. Marcus Vance",
    "bant": {
      "total_score": 78,
      "max": 100,
      "rating": "B_TIER",
      "dimensions": {
        "budget": { "score": 21, "factors": [ ... ] },
        "authority": { "score": 22, "factors": [ ... ] },
        "need": { "score": 19, "factors": [ ... ] },
        "timeline": { "score": 16, "factors": [ ... ] }
      }
    },
    "meddic": {
      "overall_completeness_pct": 88,
      "tier": "ENTERPRISE_READY",
      "dimensions": {
        "metrics": { "pct": 100, "label": "Metrics", "detail": "Quantified $4,800/mo leakage" },
        "economic_buyer": { "pct": 100, "label": "Economic Buyer", "detail": "Dr. Marcus Vance" },
        "decision_criteria": { "pct": 90, "label": "Decision Criteria", "detail": "Integrates with Eaglesoft" },
        "decision_process": { "pct": 95, "label": "Decision Process", "detail": "Private practice owner: 1-step" },
        "identify_pain": { "pct": 100, "label": "Identify Pain", "detail": "Uncaptured after-hours emergency calls" },
        "champion": { "pct": 45, "label": "Champion", "detail": "Front desk coordinator to be engaged" }
      }
    },
    "recommendation": "DISCOVERY_CALL: High pain verified. Conduct consultative SPIN call."
  }
  ```

---

### `GET /api/leads/{lead_id}/download-pdf-dossier`
Generates and streams a vector PDF Opportunity Teardown dossier.
- **Response**: Binary stream (`application/pdf`) with `Content-Disposition: attachment; filename="dossier_{lead_id}_{date}.pdf"`.
- Generated in ~250ms via ReportLab with zero external headless browser overhead.

---

### `POST /api/leads/{lead_id}/stage`
Updates the CRM Kanban stage of a practice.
- **Request Body**:
  ```json
  {
    "stage": "MEETING",
    "notes": "Booked discovery call with Dr. Vance for Thursday 10 AM"
  }
  ```
- Automatically records a timestamped transition event in `stage_transitions` and `opportunity_timeline`.

---

### `GET /api/leads/{lead_id}/battlecard`
Generates an instant pre-call sales battlecard tailored to the target practice's detected software stack and Google review complaints.

---

## 2. Today's Calls Hot Queue & Outbound Voice

### `GET /api/queue/todays-calls`
Retrieves AI-qualified target practices ready for outbound phone outreach.
- **Query Parameters**:
  - `min_probability` (optional, integer, default: `65`): Minimum closing probability cutoff.
- **Response**: Array of leads sorted by `expected_value` and `urgency_score`, with `why_now_reasons` and verified doctor names.

---

### `POST /api/voice/dial`
Initiates an outbound phone call to a practice.
- **Request Body**:
  ```json
  {
    "lead_id": "lead_austindentalcare_httpsaustindentalcarecom",
    "phone": "+15125550199",
    "initial_mode": "HUMAN_FIRST",
    "provider": "TELNYX"
  }
  ```
- **Response**:
  ```json
  {
    "success": true,
    "call_id": "call_20261013_182947_a1b2",
    "status": "DIALING",
    "provider": "TELNYX"
  }
  ```

---

### `POST /api/voice/hangup`
Terminates an ongoing phone call via carrier REST API.
- **Request Body**:
  ```json
  {
    "call_id": "call_20261013_182947_a1b2"
  }
  ```

---

### `GET /api/voice/status`
Returns real-time telephony subsystem health, active carrier configuration, and webhook connectivity status.

---

## 3. WebSockets & Telephony Webhooks

### `WebSocket /api/voice/stream/{call_id}`
Establishes bidirectional streaming between the telephony carrier/server and the operator dashboard:
- Client $\rightarrow$ Server:
  - Audio chunk packets (16kHz PCM base64 encoded)
  - Control events (`{"action": "HANDOVER_TO_AI"}`, `{"action": "WHISPER", "text": "..."}`)
- Server $\rightarrow$ Client:
  - Line status updates (`RINGING`, `CONNECTED`, `ENDED`)
  - Live real-time speech transcription (`party`: `RECEPTIONIST` | `AI_AGENT` | `OPERATOR`)
  - Inbound audio frames to play through browser speaker.

---

### `POST /api/voice/webhook/telnyx`
Receives TeXML webhook events from Telnyx when outbound calls connect or progress. Returns dynamic XML directing call audio into the bidirectional media stream.

---

### `POST /api/voice/webhook/twilio`
Receives TwiML voice webhook events from Twilio. Returns `<Response><Connect><Stream url="..."/></Connect></Response>`.

---

## 4. Multi-Provider LLM Router & Telemetry

### `GET /api/settings/llm-provider`
Returns active LLM provider, configured projects, and real-time circuit-breaker statistics.
- **Response**:
  ```json
  {
    "active_provider": "GEMINI",
    "gemini_projects_configured": 2,
    "providers": {
      "GEMINI": { "configured": true, "model": "gemini-2.5-flash" },
      "GROQ": { "configured": true, "model": "llama-3.3-70b-versatile" },
      "OPENAI": { "configured": true, "model": "gpt-4o-mini" },
      "DEEPSEEK": { "configured": false, "model": "deepseek-chat" },
      "OPENROUTER": { "configured": false, "model": "meta-llama/llama-3.3-70b-instruct:free" }
    },
    "circuit_breakers": {
      "GEMINI_PROJECT_A": { "status": "AVAILABLE", "requests": 142, "rate_limit_429_count": 0, "latency_p50_ms": 280 },
      "GROQ": { "status": "AVAILABLE", "requests": 8, "rate_limit_429_count": 0, "latency_p50_ms": 190 }
    }
  }
  ```

---

### `POST /api/settings/llm-provider`
Dynamically switches the active LLM brain at runtime.
- **Request Body**:
  ```json
  {
    "provider": "GROQ"
  }
  ```
- Valid providers: `GEMINI`, `GROQ`, `OPENAI`, `DEEPSEEK`, `OPENROUTER`.
