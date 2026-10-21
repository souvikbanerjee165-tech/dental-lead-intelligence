# REST & WebSocket API Reference

The application exposes a high-performance FastAPI service running on port `8000` (and publicly accessible via Cloudflare Quick Tunnel). All endpoints accept and return JSON unless otherwise specified.

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
Generates and streams a 2-page publication-grade vector PDF Opportunity Teardown.
- **Response**: Binary stream (`application/pdf`) with `Content-Disposition: attachment; filename="dossier_{lead_id}_{date}.pdf"`.
- Generated in ~250ms via ReportLab with zero external headless browser dependencies.

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

## 2. Telephony & Live Voice Calling

### `POST /api/voice/call/{lead_id}/dispatch`
Dispatches an outbound AI phone call to a confirmed dental practice.
- **Request Body**:
  ```json
  {
    "phone_override": "+15125550199",
    "confirmed_by_user": true
  }
  ```
- **Response**:
  ```json
  {
    "status": "initiated",
    "mode": "TELNYX_LIVE",
    "call_id": "v3:vca_48a9b2...",
    "session_id": "call_telnyx_17912389...",
    "target_phone": "+15125550199",
    "clinic_name": "Austin Dental Care",
    "doctor_name": "Dr. Miller",
    "message": "Telnyx wholesale outbound call ringing +15125550199..."
  }
  ```

---

### `POST /api/voice/call/test`
Places a real PSTN test call to an operator/founder cell phone using the research dossier of a selected practice.
- **Request Body**:
  ```json
  {
    "phone": "+15125550199",
    "lead_id": "lead_austindentalcare_httpsaustindentalcarecom"
  }
  ```
- **Response**: Returns `{ "status": "initiated", "call_id": "...", "session_id": "..." }`.

---

### `POST /api/voice/call/hangup` and `POST /api/dialer/manual/hangup`
Commands Telnyx to immediately sever the telecom call leg on the PSTN network.
- **Request Body** (both parameters optional):
  ```json
  {
    "session_id": "call_telnyx_17912389...",
    "call_id": "v3:vca_48a9b2..."
  }
  ```
- **Atomic Hangup Guard**: If `session_id` and `call_id` are omitted (e.g., empty `{}` or beacon on page unload), the engine performs an atomic safety sweep across all active sessions and severs any live carrier lines.
- **Response**:
  ```json
  {
    "status": "hung_up",
    "target": "call_telnyx_17912389...",
    "detail": {
      "status": "hung_up",
      "terminated_calls": ["v3:vca_48a9b2..."]
    }
  }
  ```

---

### `GET /api/dialer/manual/session/{session_id}`
Returns live session state, updated transcript turns, talk metrics, audio URLs, and call status (`ACTIVE`, `CONNECTED`, `COMPLETED`, `HUNG_UP`).
- **Response**:
  ```json
  {
    "session_id": "call_telnyx_17912389...",
    "status": "CONNECTED",
    "phone_number": "+15125550199",
    "clinic_name": "Austin Dental Care",
    "transcript": [
      {
        "speaker": "AI Growth Specialist",
        "role": "assistant",
        "text": "Hi, good morning! Who handles weekend scheduling for Austin Dental Care?",
        "audio_url": "/output/calls/ai_17912390.mp3"
      },
      {
        "speaker": "Receptionist (Phone)",
        "role": "prospect",
        "text": "Yes, our office manager Sarah handles that on Mondays.",
        "audio_url": "/output/calls/prospect_17912392.mp3"
      }
    ],
    "talk_metrics": { "human_words": 0, "ai_words": 14, "prospect_words": 10 }
  }
  ```

---

### `POST /api/dialer/manual/ai-takeover`
Hands over live call control from Human Operator to AI. Generates immediate contextual speech turn.
- **Request Body**:
  ```json
  {
    "session_id": "call_telnyx_17912389...",
    "user_hint": "Ask for Sarah's direct email"
  }
  ```

---

### `POST /api/dialer/manual/human-takeover`
Hands over live call control from AI back to Human Operator. Halts AI speech playback.
- **Request Body**:
  ```json
  {
    "session_id": "call_telnyx_17912389...",
    "reason": "Rep took back microphone control"
  }
  ```

---

### `POST /api/voice/webhook/telnyx`
Inbound Call Control v2 webhook receiver from Telnyx:
- `call.answered`: Begins transcription and speaks the consultative opening hook.
- `call.transcription`: Ingests prospect speech, filters acoustic echo, triggers DeepSeek-V3 spoken response, and generates browser playback audio asynchronously.
- `call.hangup`: Finalizes duration, logs outcome (`CALL_COMPLETED` or `CALL_DROPPED`), and closes active session.

---

## 3. Multi-Provider LLM Router & Tiered Cost Routing

### `GET /api/settings/llm-provider`
Returns active primary LLM provider, configured projects, and circuit-breaker telemetry.
- **Response**:
  ```json
  {
    "active_provider": "DEEPSEEK",
    "gemini_projects_configured": 1,
    "providers": {
      "DEEPSEEK": { "configured": true, "model": "deepseek-chat" },
      "GEMINI": { "configured": true, "model": "gemini-2.5-flash" },
      "GROQ": { "configured": false, "model": "llama-3.3-70b-versatile" },
      "OPENAI": { "configured": false, "model": "gpt-4o-mini" },
      "OPENROUTER": { "configured": false, "model": "meta-llama/llama-3.3-70b-instruct:free" }
    },
    "circuit_breakers": {
      "DEEPSEEK": { "status": "AVAILABLE", "requests": 24, "rate_limit_429_count": 0 },
      "GEMINI_PROJECT_A": { "status": "AVAILABLE", "requests": 62, "rate_limit_429_count": 0 }
    }
  }
  ```

### Task Complexity Routing Table

| Complexity Tier | Target Provider | Max Tokens | Description |
| :--- | :--- | :--- | :--- |
| `TaskComplexity.EASY` | Google Gemini 2.5 Flash / Groq | $\le 250$ | Sentiment scoring, entity extraction, string sanitization ($0 free tier) |
| `TaskComplexity.CONVERSATION` | DeepSeek-V3 (`deepseek-chat`) | Dynamic | Live phone dialogue turns, objection rebuttals |
| `TaskComplexity.COMPLEX` | DeepSeek-V3 (`deepseek-chat`) | Full context | BANT/MEDDIC reasoning, financial loss models, executive teardowns |

---

## 4. Calendar & WhatsApp Tools

### `GET /api/calendar/slots`
Retrieves available demo booking slots for the next $N$ business days.
- **Query Parameters**: `days` (integer, default: `5`).

### `POST /api/calendar/book`
Locks in an executive demo appointment and generates a Google Meet link.
- **Request Body**:
  ```json
  {
    "lead_id": "lead_austindentalcare",
    "slot": "Thursday at 11:00 AM",
    "clinic_name": "Austin Dental Care",
    "doctor_name": "Dr. Miller",
    "phone": "+15125550199"
  }
  ```

### `POST /api/whatsapp/turn`
Generates consultative WhatsApp pitch message and direct `https://wa.me/...` click-to-chat URL.
