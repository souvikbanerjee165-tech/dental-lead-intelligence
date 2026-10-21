# Telephony, Voice Synthesis & Audio Relay Guide

This guide covers setting up, configuring, and operating outbound telephony, real-time voice synthesis, turn-taking, and call lifecycle control in the application.

---

## 1. Prerequisites

- **Python Virtual Environment**: `.venv` activated with dependencies (`openai`, `httpx`, `fastapi`, `uvicorn`, `edge-tts`).
- **Telephony Carrier**:
  - **Telnyx** (Primary wholesale carrier: Call Control v2 REST API & Deepgram/Google real-time transcription), OR
  - **Twilio** (Supported secondary carrier with TwiML).
- **Primary LLM Brain**: **DeepSeek-V3** (`deepseek-chat`) configured in `.env` (`DEEPSEEK_API_KEY`).
- **Public HTTPS Domain**: Required for carrier webhooks. Automated via Cloudflare Quick Tunnel (`start_tunnel.py`).

---

## 2. Telnyx Setup (Primary Wholesale Carrier)

### Step 1: Obtain Credentials from Telnyx Portal
1. Create an account at [telnyx.com](https://telnyx.com).
2. Go to **API Keys** and generate a new API Key:
   ```env
   TELNYX_API_KEY=KEY018...
   ```
3. Purchase a US voice-capable telephone number (DID) under **Numbers**:
   ```env
   TELNYX_PHONE_NUMBER=+15125550199
   ```
4. Create a **Call Control Application** under **Voice ➔ Call Control / TeXML**:
   - Application Name: `Dental AI Outbound Dialer`
   - Webhook API Version: `API v2`
   - Webhook URL: `https://YOUR-PUBLIC-DOMAIN/api/voice/webhook/telnyx`
   - Webhook Method: `POST`
5. Retrieve the **Connection ID** (Application ID) and add it to your `.env`:
   ```env
   TELNYX_CONNECTION_ID=182947291048...
   ```

---

## 3. Twilio Setup (Secondary Fallback)

If using Twilio instead of Telnyx:
1. Log into [twilio.com/console](https://console.twilio.com).
2. Retrieve Account SID, Auth Token, and Twilio phone number:
   ```env
   TWILIO_ACCOUNT_SID=AC...
   TWILIO_AUTH_TOKEN=...
   TWILIO_PHONE_NUMBER=+15125550188
   ```
3. Set your Twilio Voice Webhook URL to:
   - `https://YOUR-PUBLIC-DOMAIN/api/voice/webhook/twilio` (HTTP POST)

---

## 4. Cloudflare Quick Tunnel Setup

For local development without a static public IP or port forwarding:
1. Ensure `cloudflared.exe` is located in the project root.
2. Launch the auto-registrar tunnel:
   ```powershell
   .venv\Scripts\python.exe start_tunnel.py
   ```
3. `start_tunnel.py` will:
   - Establish a secure HTTPS quick tunnel to `http://127.0.0.1:8000`.
   - Discover the assigned `https://*.trycloudflare.com` domain.
   - Automatically save the URL and webhook endpoints to `output/cloudflare_tunnel.json`.
   - Update `app.py` and Telnyx with the active public origin.

---

## 5. Call Lifecycle & Atomic Hangup Architecture

The platform implements an **Atomic Hangup Guard** across the frontend, FastAPI backend, and Telnyx Call Control:

```
[Browser Operator]                  [FastAPI Engine]                 [Telnyx PSTN Line]
        │                                   │                                 │
   Clicks "Launch Call"                     │                                 │
        ├──────────────────────────────────►│ POST /api/voice/call/dispatch   │
        │                                   ├────────────────────────────────►│ POST /v2/calls (Initiate Call)
        │                                   │ Pre-register session ID         │
        │◄──────────────────────────────────┤ Returns {call_id, session_id}   │
        │                                   │                                 │
   Ringing / Speaking                       │                                 │
        │                                   │◄────────────────────────────────┤ Webhook: call.answered
        │                                   ├────────────────────────────────►│ /actions/speak (Opening Hook)
        │                                   │                                 │
   Prospect Speaks                          │◄────────────────────────────────┤ Webhook: call.transcription
        │                                   ├────────────────────────────────►│ /actions/speak (AI Spoken Turn <350ms)
        │                                   │ Async synthesize MP3            │
        │◄──────────────────────────────────┤ Updates live transcript & audio │
        │                                   │                                 │
   Clicks "End Call" or Closes Modal        │                                 │
        ├──────────────────────────────────►│ POST /api/voice/call/hangup     │
        │                                   ├────────────────────────────────►│ POST /v2/calls/{id}/actions/hangup
        │                                   │ Atomic Sweep (terminates line)  │ (Carrier terminates call)
```

### Key Guarantees:
1. **Pre-Registration (Prevents Duplicate Dialing)**:
   - When an outbound call is dispatched, it is immediately registered in `LiveDialerEngine._active_sessions` under both its `session_id` and carrier `call_control_id`.
   - When the `call.transcription` webhook arrives, it re-attaches to the existing session with `dispatch_carrier=False`, preventing redundant re-dialing.
2. **Atomic Safety Sweep (Guaranteed Hangup)**:
   - If `/api/voice/call/hangup` receives an empty payload or untracked ID, `LiveDialerEngine.hangup_session()` sweeps all sessions with status `ACTIVE`, `DIALING`, or `CONNECTED` and fires `/actions/hangup` to Telnyx.
3. **Browser `beforeunload` Beacon**:
   - If the user closes the browser tab, refreshes, or navigates away, a `navigator.sendBeacon('/api/voice/call/hangup', ...)` automatically severs the PSTN connection.
4. **Acoustic Self-Echo Filtering**:
   - Incoming transcripts matching the AI's recent utterances are identified and ignored, preventing conversational feedback loops.
5. **Sub-Second Spoken Response**:
   - DeepSeek-V3 generates conversational replies within ~200ms.
   - The response is dispatched to `send_telnyx_speak()` immediately so the prospect hears it with sub-second latency, while audio synthesis for the web dashboard is handled asynchronously in the background.

---

## 6. Speech Synthesis (TTS) Configuration

### 1. Microsoft Edge Neural Voice (Default Web Audio)
- High-fidelity Microsoft Neural TTS (`en-US-AriaNeural` for AI, `en-US-ChristopherNeural` for prospect playback).
- Zero cloud API credentials needed; zero cost.
- Synthesized asynchronously into `output/calls/` and streamed to the operator's browser.

### 2. Telnyx Studio Voice (On-Call Phone Audio)
- Spoken through Telnyx Call Control `/actions/speak`.
- Utilizes studio-grade neural voices (`AWS.Polly.Joanna-Neural`, `Polly.Joanna`) for clear phone delivery over PSTN codecs.

### 3. Local Kokoro ONNX (Optional Offline Synthesis)
- High-quality 82M parameter neural TTS running locally on CPU.
- Operates offline with zero external cloud latency when model files are present in `models/kokoro/`.

---

## 7. Troubleshooting Telephony Issues

### 1. "Call connects, but no sound in PC speaker"
- **Cause**: Browser AudioContext is blocked by autoplay policy before user interaction.
- **Fix**: Click anywhere on the dashboard or interact with the call modal. When turns arrive, the audio plays through `AudioContext`.

### 2. "Call drops after 15–20 seconds"
- **Cause**: The carrier webhook URL returned HTTP 404 or timed out.
- **Fix**: Check `output/cloudflare_tunnel.json` to ensure the tunnel is active and that `GET /api/system/health` returns `HEALTHY`.

### 3. "Call kept ringing on phone after hanging up in browser"
- **Cause**: Outdated session ID or untracked carrier call control ID.
- **Fix**: Resolved by the Atomic Hangup Guard and fallback sweep in `LiveDialerEngine.hangup_session()`.

### 4. "AI speaks only once and does not reply to answers"
- **Cause**: Dead air from synchronous file generation or acoustic echo loop.
- **Fix**: Resolved by decoupling `send_telnyx_speak` from background MP3 generation and filtering acoustic self-echo.
