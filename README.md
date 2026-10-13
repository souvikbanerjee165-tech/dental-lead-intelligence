# 🏥 Enterprise Dental Sales Intelligence & Autonomous Telephony Platform

[![Python](https://img.shields.io/badge/Python-3.14-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![Telephony](https://img.shields.io/badge/Telnyx-TeXML%20%7C%20WebRTC-green.svg)](https://telnyx.com)
[![Voice](https://img.shields.io/badge/Edge--TTS%20%7C%20Kokoro-ONNX-orange.svg)](https://github.com/rany2/edge-tts)
[![Qualification](https://img.shields.io/badge/BANT%20%7C%20MEDDIC-Enterprise%20Scored-purple.svg)](docs/ARCHITECTURE.md)
[![Tests](https://img.shields.io/badge/Tests-Passed%20(100%25)-brightgreen.svg)](tests/)

An enterprise-grade B2B revenue acceleration engine and autonomous voice sales platform designed for high-ticket dental practices (implants, clear aligners, cosmetic veneers, and after-hours emergency capture).

Built with the **5-Layer Intelligence Stack**, **BANT + MEDDIC Qualification Engine**, **High-Velocity Vector PDF Reporting**, **Bidirectional Browser-to-Phone Audio Relay**, and **Multi-Provider LLM Quota Failover**.

---

## ⚡ Core Architecture

```
Layer 1: Empirical Evidence   ──► DOM elements, Script SDKs, HTTP headers, Network endpoints
           │
           ▼
Layer 2: Defensible Findings  ──► Deterministic confidence formula (e.g., 97%) with multi-detector bonuses
           │
           ▼
Layer 3: Business Insights    ──► Executive realities (Manual Intake Bottleneck, Blind Ad Spend, Chair Leakage)
           │
           ▼
Layer 4: Decision Engine      ──► Enterprise BANT (0–100) & MEDDIC (0–100%) Scoring & Deal Triage
           │
           ▼
Layer 5: Autonomous Action    ──► Live Telephony (Telnyx TeXML), Edge-TTS, Vector PDF Dossiers, WhatsApp
```

---

## 🚀 Key Capabilities

### 1. Enterprise BANT + MEDDIC Qualification ([`bant_meddic_scorer.py`](bant_meddic_scorer.py))
- **BANT Score (0–100)**: Evaluates Budget capability (tech spend + implant/aligner procedure mix), Authority (Dr./Owner verified vs generic), Need (unanswered after-hours patient flow), and Timeline (seasonal urgency).
- **MEDDIC Completeness (0–100%)**: Evaluates Metrics (\$EV financial leakage), Economic Buyer, Decision Criteria (PMS compatibility with Dentrix, Eaglesoft, Open Dental), Decision Process, Identify Pain, and Champion.

### 2. High-Speed Vector PDF Sales Dossiers ([`executive_pdf_reporter.py`](executive_pdf_reporter.py))
- Generates 2-page publication-grade executive teardowns via `reportlab` in **~250ms**.
- Zero headless browser or Playwright dependencies — completely crash-proof and memory-efficient.
- Features radar qualification breakdown, chair-time loss calculations, and a 30-Day Recovery Roadmap.

### 3. Autonomous Outbound Telephony & Audio Relay ([`live_dialer_engine.py`](live_dialer_engine.py), [`audio_bridge.py`](audio_bridge.py))
- Outbound calling through Telnyx TeXML (with Twilio fallback).
- **Dual Calling Modes**:
  - `HUMAN_FIRST`: Rings prospect, relays live call audio to PC speaker, transcribes in real-time, and supports operator whisper/takeover.
  - `AI_FIRST`: Conversational AI agent greets contact immediately on pickup.
- **Speech Synthesis**: Ultra-clear Microsoft Edge-TTS (`en-US-AvaNeural`) and local offline Kokoro ONNX.

### 4. Consultative SPIN Selling Voice Brain ([`empathy_voice_prompts.py`](empathy_voice_prompts.py))
- Bypasses gatekeeper friction using consultative SPIN Selling:
  $$\text{Situation} \longrightarrow \text{Problem} \longrightarrow \text{Implication} \longrightarrow \text{Need-Payoff}$$
- Automatically extracts structured call outcomes, gatekeeper objections, and follow-up triggers into SQLite institutional memory.

### 5. Multi-Provider LLM Resilience & Quota Failover ([`llm_router.py`](llm_router.py))
- Multi-provider cascade with circuit-breaker tracking:
  $$\text{Google Gemini 2.5 Flash} \xrightarrow{\text{429 Rate Limit}} \text{Groq (Llama-3.3-70b, <300ms)} \longrightarrow \text{OpenAI} \longrightarrow \text{DeepSeek} \longrightarrow \text{OpenRouter}$$
- Ensures live patient telephone calls never drop due to cloud API quota exhaustion.

### 6. Sales Enablement Playbooks ([`playbooks/`](playbooks/))
- [`dental-objection-playbook.md`](playbooks/dental-objection-playbook.md): LAER scripts for gatekeepers and dentists.
- [`dental-discovery-spin.md`](playbooks/dental-discovery-spin.md): Field-tested phone discovery frameworks.
- [`dental-meeting-prep.md`](playbooks/dental-meeting-prep.md): 15-minute executive demo protocol.

---

## 🛠️ Quickstart & Installation

### 1. Environment Setup
```powershell
# Clone or navigate to the repository
cd "H:\Lead Gen Web Scrapper"

# Activate Python virtual environment
.\.venv\Scripts\Activate.ps1

# Install requirements
pip install -r requirements.txt
```

### 2. Environment Variables (`.env`)
Create a `.env` file in the project root:
```env
# Primary LLM Brain
GEMINI_API_KEY=AIzaSy...

# Low-Latency Quota Failover (Optional but Recommended)
GROQ_API_KEY=gsk_...
OPENAI_API_KEY=sk-...

# Telephony Carrier (Telnyx)
TELNYX_API_KEY=KEY018...
TELNYX_PHONE_NUMBER=+15125550199
TELNYX_CONNECTION_ID=182947291048...

# Telephony Carrier (Twilio Fallback, Optional)
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+15125550188
```

### 3. Launching the System
In separate terminal tabs:

**Tab A — FastAPI Server & Visual Dashboard**:
```powershell
.venv\Scripts\python.exe app.py
```
*Access the visual dashboard at `http://127.0.0.1:8000`.*

**Tab B — Public Cloudflare Tunnel (for carrier webhooks)**:
```powershell
.venv\Scripts\python.exe start_tunnel.py
```
*Automatically registers assigned `https://*.trycloudflare.com` domain with Telnyx and `app.py`.*

---

## 🖥️ Visual Dashboard Highlights

Open `http://127.0.0.1:8000` in your browser:
- **Today's Calls Hot Queue**: Displays AI-ranked targets sorted by Expected Value (\$EV) and Urgency with 1-click **Launch AI Call** and **Dossier** buttons.
- **Lead 360 Modal**: Complete forensic breakdown with BANT and MEDDIC badge pill indicators, direct WhatsApp pitch generator, Google review complaints miner, and 1-click **Download PDF Dossier**.
- **Interactive ROI Simulator**: Drag-and-drop sliders calculating practice revenue recovery from captured after-hours patient calls.
- **Live Call Audio Console**: Full audio stream unlock, bidirectional call transcript timeline, and instant rep whisper controls.

---

## 💻 CLI Commands & Workflows

### 1. Scientific Accuracy Platform Benchmark
```powershell
.venv\Scripts\python.exe main.py benchmark
```

### 2. Live Deal Triage & Point Attribution
```powershell
.venv\Scripts\python.exe main.py prioritize --url "https://austindentalcare.com" --name "Austin Dental Care" --reviews 120 --rating 4.9
```

### 3. Hyper-Local Competitor Cohort Intelligence
```powershell
.venv\Scripts\python.exe main.py cohort --query "Dentists in Austin, TX" --limit 10
```

### 4. Deep Tech Stack Fingerprint (40+ Declarative YAML Rules)
```powershell
.venv\Scripts\python.exe main.py tech --url "https://austindentalcare.com"
```

### 5. Generate 1-Page Executive PDF Report
```powershell
.venv\Scripts\python.exe main.py report --url "https://austindentalcare.com" --name "Austin Dental Care" --reviews 120 --rating 4.9
```

### 6. Single Source of Truth CRM & Kanban Pipeline
```powershell
.venv\Scripts\python.exe main.py crm summary
.venv\Scripts\python.exe main.py crm list --stage FOUND
.venv\Scripts\python.exe main.py crm move --lead-id <lead_id> --stage AUDITED --notes "Reviewed practice profile"
```

### 7. Autonomous Multi-City Morning Scraping Cycle
```powershell
.venv\Scripts\python.exe main.py schedule run-now --limit 10
```

---

## 🧪 Automated Test Suite

Run the full pytest suite covering the 5-layer intelligence graph, BANT/MEDDIC scoring, vector PDF rendering, and live telephony endpoints:

```powershell
.venv\Scripts\pytest.exe tests/test_telnyx_and_pillars.py tests/test_bant_meddic_and_pdf.py -v
```

```text
tests/test_telnyx_and_pillars.py::test_verify_telnyx_diagnostics_unconfigured PASSED [ 10%]
tests/test_telnyx_and_pillars.py::test_api_voice_telnyx_verify_endpoint PASSED       [ 20%]
tests/test_telnyx_and_pillars.py::test_api_telephony_test_telnyx PASSED             [ 30%]
tests/test_telnyx_and_pillars.py::test_api_calendar_slots_and_booking PASSED        [ 40%]
tests/test_telnyx_and_pillars.py::test_api_whatsapp_sandbox_turn PASSED             [ 50%]
tests/test_telnyx_and_pillars.py::test_sales_state_machine_calendar_tool PASSED    [ 60%]
tests/test_bant_meddic_and_pdf.py::test_dental_bant_meddic_scorer PASSED            [ 70%]
tests/test_bant_meddic_and_pdf.py::test_executive_pdf_reporter_generation PASSED    [ 80%]
tests/test_bant_meddic_and_pdf.py::test_llm_router_provider_status_and_freellmapi_expansion PASSED [ 90%]
tests/test_bant_meddic_and_pdf.py::test_api_bant_meddic_and_pdf_endpoints PASSED    [100%]
=================================== 10 passed in 7.32s ===================================
```

---

## 📚 Technical Documentation Index

For in-depth architectural and developer documentation, see:
- 📖 [**System Architecture & Technical Specification**](docs/ARCHITECTURE.md)
- 📞 [**Telephony, Voice Synthesis & Audio Relay Guide**](docs/TELEPHONY_SETUP.md)
- 🔌 [**REST & WebSocket API Reference**](docs/API_REFERENCE.md)
- 📋 [**Dental Sales Enablement Playbooks**](playbooks/dental-objection-playbook.md)

---

## ⚖️ License & Attribution

This project is licensed under the MIT License. Portions of the BANT/MEDDIC scoring, vector PDF reporting, consultative telephony prompts, and multi-provider failover logic were adapted from open-source MIT-licensed repositories (`ai-sales-team-claude`, `ai-dialer`, `freellmapi`).
