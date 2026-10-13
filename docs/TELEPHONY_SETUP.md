# Telephony, Voice Synthesis & Audio Relay Guide

This guide covers setting up, configuring, and troubleshooting outbound telephony, bidirectional audio relay, and speech synthesis in the application.

---

## 1. Prerequisites

- **Python Virtual Environment**: `.venv` activated with all dependencies installed.
- **Telephony Provider**:
  - **Telnyx** (Recommended for native TeXML streaming and low latency), OR
  - **Twilio** (Supported secondary fallback).
- **Public HTTPS Domain**: Required for carrier webhooks. Can be a custom domain or the automated Cloudflare Quick Tunnel (`start_tunnel.py`).

---

## 2. Telnyx Setup (Recommended)

### Step 1: Obtain Credentials from Telnyx Portal
1. Create an account at [telnyx.com](https://telnyx.com).
2. Go to **API Keys** and generate a new API Key:
   ```env
   TELNYX_API_KEY=KEY018...
   ```
3. Purchase a US/CA voice-capable telephone number (DID) under **Numbers**:
   ```env
   TELNYX_PHONE_NUMBER=+15125550199
   ```
4. Create a **TeXML Application** under **Voice ➔ TeXML**:
   - Application Name: `Dental AI Outbound Dialer`
   - Voice URL: `https://YOUR-PUBLIC-DOMAIN/api/voice/webhook/telnyx`
   - Voice Method: `POST`
   - Status Callback URL: `https://YOUR-PUBLIC-DOMAIN/api/voice/webhook/telnyx/status`
5. Note the **Connection ID** (Application ID) and add it to your `.env`:
   ```env
   TELNYX_CONNECTION_ID=182947291048...
   ```

---

## 3. Twilio Setup (Secondary Fallback)

If using Twilio instead of Telnyx:
1. Log into [twilio.com/console](https://console.twilio.com).
2. Retrieve Account SID and Auth Token:
   ```env
   TWILIO_ACCOUNT_SID=AC...
   TWILIO_AUTH_TOKEN=...
   TWILIO_PHONE_NUMBER=+15125550188
   ```
3. In your Twilio Phone Number settings, set:
   - A CALL COMES IN: `Webhook`
   - URL: `https://YOUR-PUBLIC-DOMAIN/api/voice/webhook/twilio`
   - HTTP: `HTTP POST`

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
   - Update `app.py` with the active public origin.

---

## 5. Bidirectional Audio Bridge & PC Speaker Relay

### Architecture
```
[Prospect Phone] 
       ↕ (Cellular / PSTN)
[Telnyx Carrier]
       ↕ (RTP / TeXML Media Stream)
[FastAPI Server WebSocket: /api/voice/stream]
       ↕ (16kHz PCM Audio Chunks)
[Operator PC Browser Dashboard] ➔ Speaker & Microphone
```

### Browser Autoplay Policy & AudioContext Unlock
Modern browsers (Chrome, Edge, Firefox) block audio playback until user interaction occurs.
- The dashboard includes a dedicated **"Audio Stream"** control bar.
- Upon opening the Call Modal or clicking **"Unlock Audio"**, the dashboard creates an active `AudioContext` and resumes playback buffer queues.
- Received 16kHz PCM chunks from the telephony WebSocket are buffered and played through the PC speakers with <100ms jitter buffer.

### Dual Calling Modes
1. **Human First (`HUMAN_FIRST`)**:
   - The outbound call rings the prospect's phone.
   - The browser speaker plays the live line status.
   - The AI remains silent in whisper mode while transcribing both parties.
   - The operator can press **"Handover to AI"** at any moment.
2. **AI First (`AI_FIRST`)**:
   - As soon as the call connects, the conversational AI agent greets the contact.
   - Uses the consultative SPIN selling opening.

---

## 6. Speech Synthesis (TTS) Configuration

### Edge-TTS (Default Cloud Synthesis)
- Powered by Microsoft's neural TTS engine.
- Configured voice: `en-US-AvaNeural` (Expressive, warm, natural cadence).
- Execution: Asynchronous, streaming raw MP3 bytes converted to 16kHz mono PCM for telephony transmission.

### Kokoro ONNX (Optional Local Synthesis)
- High-quality 82M parameter neural TTS running locally on CPU.
- When `kokoro_onnx` is installed and model files are present in `models/kokoro/`, the engine runs completely offline with zero external cloud latency.

---

## 7. Troubleshooting Telephony Issues

### 1. "Call connects, but no sound in PC speaker"
- **Cause**: Browser AudioContext is suspended by autoplay policy.
- **Fix**: Click anywhere on the dashboard or press the **"Unlock Audio / Speaker"** button in the call modal. Verify system speaker output is set to the correct device.

### 2. "Call drops after 15–20 seconds"
- **Cause**: The carrier webhook URL returned HTTP 404 or did not return valid TeXML / TwiML within the initial ring timeout.
- **Fix**: Verify `output/cloudflare_tunnel.json` matches the running tunnel URL and that `GET /api/voice/webhook/telnyx` returns valid XML (`<Response>...</Response>`).

### 3. "Call keeps ringing on phone even after closing browser tab"
- **Cause**: The browser WebSocket disconnected without issuing an explicit hangup API call.
- **Fix**: `app.py` includes a WebSocket disconnection handler that automatically executes an outbound hangup via Telnyx/Twilio REST API when the client socket disconnects.

### 4. "Distorted or robotic voice on phone"
- **Cause**: Sample rate mismatch between 24kHz TTS output and 8kHz/16kHz telephony codec.
- **Fix**: `audio_bridge.py` automatically resamples all audio streams to 16,000 Hz, 16-bit linear PCM mono before packetizing into telephony frames.
