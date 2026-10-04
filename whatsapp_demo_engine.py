"""
Dynamic 1-Click Interactive WhatsApp Demo Engine.
Generates clinic-branded interactive WhatsApp prototype simulations, QR codes,
and personalized WhatsApp deep-links so dentists can test the patient experience
directly on their phone during a live sales call or proposal review.
"""

import urllib.parse
from typing import Dict, Any, Optional


class WhatsAppDemoEngine:
    """Creates hyper-personalized WhatsApp trial experiences for any dental practice prospect."""

    @classmethod
    def generate_demo_assets(
        cls,
        lead_dict: Dict[str, Any],
        agency_phone: str = "+15125550199",
        base_app_url: str = "http://127.0.0.1:8000"
    ) -> Dict[str, Any]:
        """
        Builds live links, QR code, and simulation payload for the specific dental clinic.
        """
        lead_id = lead_dict.get("id") or "preview"
        clinic_name = lead_dict.get("name") or "Your Dental Practice"
        doctor_name = lead_dict.get("doctor_name") or "Primary Dentist"
        clean_doc = doctor_name.replace("Dr.", "").replace("Dr", "").strip()
        doc_display = f"Dr. {clean_doc}" if clean_doc else "the Practice Owner"
        
        raw_addr = lead_dict.get("address") or ""
        city = raw_addr.split(",")[-2].strip() if ("," in raw_addr and len(raw_addr.split(",")) >= 2) else "your area"

        services = lead_dict.get("high_value_services") or lead_dict.get("specialties") or [
            "Dental Implants", "Emergency Toothache Care", "Cosmetic Dentistry"
        ]
        if isinstance(services, str):
            services = [s.strip() for s in services.split(",") if s.strip()]

        top_service = services[0] if services else "Emergency Dental Care"

        # 1. WhatsApp Pre-filled Starter Message
        starter_text = (
            f"Hi {doc_display}! 👋 I was looking up {clinic_name} in {city}. "
            f"I have a painful toothache that started this evening. Are you open for emergency appointments?"
        )
        encoded_starter = urllib.parse.quote(starter_text)

        # 2. WhatsApp Direct Link to Rep's Demo Bot or Doctor's Number
        target_phone = "".join(c for c in agency_phone if c.isdigit())
        whatsapp_link = f"https://wa.me/{target_phone}?text={encoded_starter}" if target_phone else f"https://wa.me/?text={encoded_starter}"

        # 3. Dynamic QR Code for Zoom Screen Share or Proposals
        qr_code_url = f"https://api.qrserver.com/v1/create-qr-code/?size=220x220&data={urllib.parse.quote(whatsapp_link)}&color=059669"

        # 4. In-App Interactive Web Simulation URL
        web_simulation_url = f"{base_app_url}/demo/{lead_id}"

        # 5. One-Click SMS/Text Pitch Template
        sms_pitch = (
            f"Hi {doc_display}, test this 10-second WhatsApp patient intake prototype built for {clinic_name}: "
            f"{web_simulation_url} - Send 'Hi' to see how Sunday emergency callers are captured."
        )

        return {
            "lead_id": lead_id,
            "clinic_name": clinic_name,
            "doctor_name": doc_display,
            "city": city,
            "top_service": top_service,
            "whatsapp_link": whatsapp_link,
            "qr_code_url": qr_code_url,
            "web_simulation_url": web_simulation_url,
            "starter_message": starter_text,
            "sms_pitch": sms_pitch,
            "sample_turns": [
                {
                    "user": "Hi, I have a broken molar and sharp pain. Do you have appointments tomorrow morning?",
                    "bot": f"Hello! 👋 I'm the 24/7 Patient Assistant for {clinic_name}. We're so sorry you're in pain! {doc_display} has an emergency slot reserved tomorrow at 9:30 AM or 11:15 AM. Which time works better for you?"
                },
                {
                    "user": "9:30 AM works. Do you accept Delta Dental?",
                    "bot": f"Perfect, holding 9:30 AM for you! Yes, we work with Delta Dental. Could you share your full name and cell number so {doc_display}'s team can send your instant check-in confirmation?"
                }
            ]
        }

    @classmethod
    def render_demo_page_html(cls, lead_dict: Dict[str, Any]) -> str:
        """Renders an authentic, mobile-responsive interactive WhatsApp patient conversation simulator."""
        assets = cls.generate_demo_assets(lead_dict)
        clinic = assets["clinic_name"]
        doc = assets["doctor_name"]
        city = assets["city"]

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Live Patient WhatsApp Prototype • {clinic}</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    body {{ background-color: #0b141a; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
    .wa-bg {{ background-color: #0b141a; background-image: radial-gradient(#1f2c34 1px, transparent 1px); background-size: 20px 20px; }}
    .chat-bubble-bot {{ background-color: #202c33; border-radius: 8px 8px 8px 0px; }}
    .chat-bubble-user {{ background-color: #005c4b; border-radius: 8px 8px 0px 8px; }}
  </style>
</head>
<body class="min-h-screen flex flex-col justify-between text-slate-100">

  <!-- Top Banner for Practice Owner -->
  <div class="bg-emerald-950/90 border-b border-emerald-500/40 px-4 py-2 text-center text-xs text-emerald-200 flex items-center justify-center gap-2">
    <span class="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
    <span><strong>Interactive Prototype</strong>: Prepared exclusively for <strong>{doc}</strong> at <strong>{clinic}</strong></span>
  </div>

  <!-- WhatsApp Phone Container -->
  <div class="max-w-md w-full mx-auto flex-1 flex flex-col bg-[#111b21] shadow-2xl border-x border-slate-800">
    
    <!-- WhatsApp Header -->
    <div class="bg-[#202c33] px-4 py-3 flex items-center justify-between border-b border-slate-800">
      <div class="flex items-center gap-3">
        <a href="/" class="text-slate-400 hover:text-white"><i class="fa-solid fa-arrow-left"></i></a>
        <div class="w-10 h-10 rounded-full bg-emerald-700/80 flex items-center justify-center text-white font-bold text-lg shadow">
          <i class="fa-solid fa-tooth"></i>
        </div>
        <div>
          <h2 class="text-sm font-bold text-white leading-tight truncate max-w-[200px]">{clinic}</h2>
          <span class="text-[11px] text-emerald-400 flex items-center gap-1">
            <span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span> 24/7 AI Patient Assistant
          </span>
        </div>
      </div>
      <div class="flex items-center gap-3 text-slate-400 text-sm">
        <i class="fa-solid fa-phone cursor-pointer hover:text-white" title="Simulated Call"></i>
        <i class="fa-solid fa-ellipsis-vertical cursor-pointer hover:text-white"></i>
      </div>
    </div>

    <!-- Chat Messages Stream -->
    <div id="chat-stream" class="flex-1 p-4 overflow-y-auto space-y-3 wa-bg min-h-[380px]">
      
      <!-- Timestamp pill -->
      <div class="flex justify-center">
        <span class="px-2.5 py-0.5 rounded-md bg-[#182229] text-[10px] text-slate-400 uppercase font-bold tracking-wider">
          Sunday • 8:14 PM (After-Hours)
        </span>
      </div>

      <!-- Welcome Bot Turn -->
      <div class="flex items-start">
        <div class="chat-bubble-bot p-3 text-xs text-slate-200 max-w-[85%] shadow space-y-1">
          <p>Hello! 👋 Thanks for messaging <strong>{clinic}</strong>. I'm {doc}'s 24/7 Patient Assistant.</p>
          <p class="text-[11px] text-slate-300">How can we help your smile this evening?</p>
          <span class="text-[9px] text-slate-400 block text-right pt-0.5">8:14 PM &check;&check;</span>
        </div>
      </div>

    </div>

    <!-- Quick Action Patient Chips -->
    <div class="bg-[#182229] p-2 border-t border-slate-800 flex gap-2 overflow-x-auto text-[11px]">
      <button onclick="sendQuickPatientTurn('I have an emergency toothache and need an appointment tomorrow')" class="px-3 py-1.5 rounded-full bg-[#202c33] hover:bg-[#2a3942] text-slate-200 whitespace-nowrap cursor-pointer transition border border-slate-700">
        🚨 Emergency Toothache
      </button>
      <button onclick="sendQuickPatientTurn('How much does dental implant treatment cost?')" class="px-3 py-1.5 rounded-full bg-[#202c33] hover:bg-[#2a3942] text-slate-200 whitespace-nowrap cursor-pointer transition border border-slate-700">
        🦷 Dental Implants
      </button>
      <button onclick="sendQuickPatientTurn('Do you take Delta Dental or MetLife?')" class="px-3 py-1.5 rounded-full bg-[#202c33] hover:bg-[#2a3942] text-slate-200 whitespace-nowrap cursor-pointer transition border border-slate-700">
        📋 Insurance Check
      </button>
    </div>

    <!-- Input Bar -->
    <div class="bg-[#202c33] p-2.5 flex items-center gap-2 border-t border-slate-800">
      <input type="text" id="custom-input" placeholder="Type a patient message..." class="flex-1 bg-[#2a3942] text-white rounded-lg px-3 py-2 text-xs focus:outline-none placeholder-slate-400">
      <button onclick="submitCustomPatientTurn()" class="w-9 h-9 rounded-full bg-emerald-600 hover:bg-emerald-500 text-white flex items-center justify-center transition cursor-pointer">
        <i class="fa-solid fa-paper-plane text-xs"></i>
      </button>
    </div>

  </div>

  <!-- Bottom CTA Footer -->
  <div class="bg-slate-950 border-t border-slate-800 p-4 text-center text-xs space-y-1">
    <p class="text-slate-300">Like this patient experience for <strong>{clinic}</strong>?</p>
    <p class="text-emerald-400 font-bold">Installs in 48 hours for $1,500 setup + $399/mo maintenance • Recovers 8+ patients/month</p>
  </div>

  <script>
    const stream = document.getElementById('chat-stream');
    const input = document.getElementById('custom-input');
    const docName = "{doc}";
    const clinicName = "{clinic}";

    input.addEventListener('keydown', (e) => {{
      if (e.key === 'Enter') submitCustomPatientTurn();
    }});

    function submitCustomPatientTurn() {{
      const text = input.value.trim();
      if (!text) return;
      input.value = '';
      sendQuickPatientTurn(text);
    }}

    function sendQuickPatientTurn(text) {{
      appendMessage(text, 'user');
      
      // Show typing indicator
      const typing = document.createElement('div');
      typing.id = 'typing-indicator';
      typing.className = 'flex items-start text-xs text-slate-400 italic py-1';
      typing.innerHTML = `<span class="chat-bubble-bot px-3 py-1.5 text-[10px]"><i class="fa-solid fa-ellipsis animate-pulse"></i> Assistant typing...</span>`;
      stream.appendChild(typing);
      stream.scrollTop = stream.scrollHeight;

      setTimeout(() => {{
        const ind = document.getElementById('typing-indicator');
        if (ind) ind.remove();
        generateBotReply(text);
      }}, 700);
    }}

    function appendMessage(text, role) {{
      const div = document.createElement('div');
      const time = new Date().toLocaleTimeString([], {{ hour: '2-digit', minute: '2-digit' }});
      if (role === 'user') {{
        div.className = 'flex justify-end';
        div.innerHTML = `
          <div class="chat-bubble-user p-2.5 text-xs text-white max-w-[85%] shadow">
            <p>${{text}}</p>
            <span class="text-[9px] text-emerald-200 block text-right pt-0.5">${{time}} &check;&check;</span>
          </div>
        `;
      }} else {{
        div.className = 'flex items-start';
        div.innerHTML = `
          <div class="chat-bubble-bot p-3 text-xs text-slate-200 max-w-[85%] shadow space-y-1">
            <p>${{text}}</p>
            <span class="text-[9px] text-slate-400 block text-right pt-0.5">${{time}} &check;&check;</span>
          </div>
        `;
      }}
      stream.appendChild(div);
      stream.scrollTop = stream.scrollHeight;
    }}

    async function generateBotReply(patientText) {{
      const lower = patientText.toLowerCase();
      let reply = "";

      // Try live AI backend first
      try {{
        const res = await fetch('/api/whatsapp/turn', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{
            lead_id: '{assets["lead_id"]}',
            message: patientText,
            clinic_name: clinicName,
            doctor_name: docName
          }})
        }});
        if (res.ok) {{
          const data = await res.json();
          if (data.reply) {{
            appendMessage(data.reply, 'bot');
            return;
          }}
        }}
      }} catch (e) {{}}

      // Deterministic fallback rules
      if (lower.includes("emergency") || lower.includes("toothache") || lower.includes("pain") || lower.includes("broken")) {{
        reply = `We're so sorry you're in pain! ${{docName}} reserves emergency priority slots tomorrow morning at <strong>9:30 AM</strong> and <strong>11:15 AM</strong>. Which of those times works best to get you out of pain?`;
      }} else if (lower.includes("implant") || lower.includes("cost") || lower.includes("price")) {{
        reply = `${{docName}} specializes in gentle restorative dental implants. Every case is customized, but we offer a comprehensive 3D digital scan & consultation. Would you like to reserve our next opening on Thursday at 11:00 AM?`;
      }} else if (lower.includes("insurance") || lower.includes("delta") || lower.includes("metlife")) {{
        reply = `Yes, we accept and file with most major PPO insurances! What is your full name and cell number? We'll text your pre-appointment intake details right away.`;
      }} else if (lower.includes("9:30") || lower.includes("11:00") || lower.includes("tomorrow") || lower.includes("yes")) {{
        reply = `Excellent! We've held that slot for you at <strong>${{clinicName}}</strong>. You'll receive a confirmation text and directions shortly. See you tomorrow! 🎉`;
      }} else {{
        reply = `Thank you for reaching out! I've logged your request for ${{docName}}'s team. What is the best cell number to confirm your appointment?`;
      }}

      appendMessage(reply, 'bot');
    }}
  </script>
</body>
</html>"""
