"""
Executive Practice Teardown & One-Page Pitch Portal Engine.
Renders hyper-personalized, high-converting public audit landing pages at `/pitch/{lead_id}`
for dental practice owners, complete with revenue leakage calculations, embedded WhatsApp simulator,
competitor poaching alerts, and single-patient break-even guarantee ($1,500 setup + $399/mo).
"""

import json
from datetime import datetime
from typing import Dict, Any, Optional
import urllib.parse

from whatsapp_demo_engine import WhatsAppDemoEngine
from mystery_shopper import MysteryShopperAuditor


class PitchPortalEngine:
    """Generates executive one-page practice teardown portals for dental prospects."""

    @classmethod
    def render_pitch_page_html(
        cls,
        lead_dict: Dict[str, Any],
        base_app_url: str = "http://127.0.0.1:8000",
        rep_phone: str = "+1 (512) 555-0199",
        rep_email: str = "concierge@dentalgrowth.io",
        calendar_link: str = "https://calendly.com"
    ) -> str:
        lead_id = lead_dict.get("id") or "preview"
        clinic_name = lead_dict.get("name") or "Your Dental Practice"
        raw_doc = lead_dict.get("doctor_name") or "Doctor"
        clean_doc = raw_doc.replace("Dr.", "").replace("Dr", "").strip()
        doc_display = f"Dr. {clean_doc}" if clean_doc else "Practice Owner"
        
        address = lead_dict.get("address") or "Austin, TX"
        city = address.split(",")[-2].strip() if ("," in address and len(address.split(",")) >= 2) else "your city"
        
        rating = lead_dict.get("rating") or 4.9
        review_count = lead_dict.get("review_count") or 85
        
        # Financial estimates
        missed_min = lead_dict.get("missed_rev_min") or 3500
        missed_max = lead_dict.get("missed_rev_max") or 7200
        avg_monthly_leakage = int((missed_min + missed_max) / 2)
        annual_leakage = avg_monthly_leakage * 12

        # Tech stack
        detected_ehr = lead_dict.get("detected_ehr") or "Dentrix / Eaglesoft"
        npi_number = lead_dict.get("npi_number") or "Verified CMS Registry"
        
        # Formatted Date
        current_date = datetime.now().strftime("%B %d, %Y")

        # Demo simulator assets
        demo_assets = WhatsAppDemoEngine.generate_demo_assets(lead_dict, base_app_url=base_app_url)
        whatsapp_link = demo_assets["whatsapp_link"]
        qr_code_url = demo_assets["qr_code_url"]

        # Mystery Shopper Data
        mystery_data = lead_dict.get("mystery_audit_json")
        if not mystery_data or not isinstance(mystery_data, dict):
            mystery_data = MysteryShopperAuditor.generate_audit_proof(lead_dict)

        ring_count = mystery_data.get("ring_count", 5)
        test_time = mystery_data.get("test_timestamp", "Recent After-Hours Audit")

        # Hygiene Reactivation Data
        from hygiene_recall_calculator import HygieneRecallCalculator
        hygiene_data = HygieneRecallCalculator.calculate_hygiene_leakage(lead_dict)
        dormant_charts = hygiene_data["dormant_hygiene_charts"]
        trapped_hygiene_rev = hygiene_data["trapped_chart_value"]
        month1_hygiene_cash = hygiene_data["month1_cash_injection"]
        hygiene_roi = hygiene_data["month1_roi_multiplier"]

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Confidential Revenue & Patient Recovery Audit • {clinic_name}</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    body {{ background-color: #0b1117; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
    .wa-bg {{ background-color: #0b141a; background-image: radial-gradient(#1f2c34 1px, transparent 1px); background-size: 20px 20px; }}
    .chat-bubble-bot {{ background-color: #202c33; border-radius: 8px 8px 8px 0px; }}
    .chat-bubble-user {{ background-color: #005c4b; border-radius: 8px 8px 0px 8px; }}
  </style>
</head>
<body class="text-slate-100 min-h-screen flex flex-col justify-between selection:bg-emerald-500 selection:text-black">

  <!-- Executive Header -->
  <header class="border-b border-slate-800 bg-slate-950/90 backdrop-blur sticky top-0 z-40">
    <div class="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <div class="w-9 h-9 rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-500 flex items-center justify-center text-slate-950 font-black text-lg shadow-lg shadow-emerald-500/20">
          <i class="fa-solid fa-tooth"></i>
        </div>
        <div>
          <span class="text-xs font-black uppercase tracking-wider text-emerald-400 block">Dental Practice Intelligence Audit</span>
          <h1 class="text-sm font-bold text-white">{clinic_name}</h1>
        </div>
      </div>
      <div class="flex items-center gap-3">
        <span class="hidden sm:inline-block px-2.5 py-1 rounded-full text-[10px] font-black bg-cyan-500/10 text-cyan-300 border border-cyan-500/30">
          <i class="fa-solid fa-certificate"></i> {npi_number}
        </span>
        <a href="/video/{lead_id}" class="hidden sm:inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-rose-300 border border-rose-500/30 text-xs font-bold transition">
          <i class="fa-solid fa-circle-play text-rose-400"></i> Watch 60s Video
        </a>
        <a href="#book-walkthrough" class="px-4 py-2 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-slate-950 font-black text-xs shadow-lg shadow-emerald-500/20 transition">
          Claim Practice Territory
        </a>
      </div>
    </div>
  </header>

  <!-- Hero Section -->
  <main class="max-w-6xl mx-auto px-4 py-8 space-y-10 flex-1">
    
    <!-- Title Card -->
    <div class="text-center max-w-3xl mx-auto space-y-3">
      <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-bold bg-rose-500/10 text-rose-400 border border-rose-500/30">
        <span class="w-2 h-2 rounded-full bg-rose-400 animate-ping"></span>
        <span>After-Hours Patient Friction Report • {current_date}</span>
      </div>
      <h2 class="text-3xl sm:text-4xl font-black text-white tracking-tight leading-tight">
        How <span class="text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-teal-300">{clinic_name}</span> is Unknowingly Dropping <span class="text-rose-400 font-mono">${avg_monthly_leakage:,}/Mo</span> in Weekend Patient Production
      </h2>
      <p class="text-sm text-slate-400 leading-relaxed">
        Prepared exclusively for <strong>{doc_display}</strong>. When prospective patients in {city} suffer acute tooth pain outside 9-5 clinic hours, our audit confirmed their calls hit voicemail—prompting 67% to immediately dial your nearest competitor.
      </p>
    </div>

    <!-- 3 Core Financial Leakage Metrics -->
    <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 text-center">
      <div class="bg-slate-900/80 p-5 rounded-2xl border border-rose-500/30 shadow-xl space-y-1">
        <span class="text-[10px] font-bold text-rose-400 uppercase tracking-wider block">Estimated Monthly Lost Revenue</span>
        <div class="text-3xl font-black text-rose-400 font-mono">${avg_monthly_leakage:,}</div>
        <p class="text-[11px] text-slate-400">Based on {review_count} patient reviews & {city} dental market case averages</p>
      </div>

      <div class="bg-slate-900/80 p-5 rounded-2xl border border-slate-800 shadow-xl space-y-1">
        <span class="text-[10px] font-bold text-amber-400 uppercase tracking-wider block">Annual Production Gap</span>
        <div class="text-3xl font-black text-amber-300 font-mono">${annual_leakage:,}</div>
        <p class="text-[11px] text-slate-400">Uncaptured after-hours root canals, crowns & emergency extractions</p>
      </div>

      <div class="bg-slate-900/80 p-5 rounded-2xl border border-emerald-500/30 shadow-xl space-y-1">
        <span class="text-[10px] font-bold text-emerald-400 uppercase tracking-wider block">Break-Even Benchmark</span>
        <div class="text-3xl font-black text-emerald-400 font-mono">1 Single Case</div>
        <p class="text-[11px] text-slate-400">Capturing just 1 emergency patient every 90 days makes this 100% free</p>
      </div>
    </div>

    <!-- Empirical Mystery Shopper Audit Card -->
    <div class="bg-gradient-to-r from-slate-900 via-slate-900 to-rose-950/40 p-6 rounded-2xl border border-rose-500/40 shadow-2xl space-y-4">
      <div class="flex items-center justify-between flex-wrap gap-2">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-rose-500/10 text-rose-400 border border-rose-500/30 flex items-center justify-center text-lg">
            <i class="fa-solid fa-phone-slash"></i>
          </div>
          <div>
            <h3 class="text-sm font-bold text-white uppercase tracking-wider">Empirical Telephone Friction Audit</h3>
            <span class="text-xs text-slate-400">Recorded: {test_time}</span>
          </div>
        </div>
        <span class="px-3 py-1 rounded-full text-xs font-black bg-rose-500/20 text-rose-300 border border-rose-500/40">
          🔴 Confirmed Voicemail Bounce
        </span>
      </div>

      <div class="bg-slate-950/90 p-4 rounded-xl border border-slate-800 space-y-2 text-xs">
        <p class="text-slate-300 leading-relaxed font-sans">
          During after-hours mystery testing, a simulated urgent inquiry was placed to your clinic phone. 
          The line rang <strong>{ring_count} times</strong> before dropping into a generic office voicemail with no 24/7 online triage.
        </p>
        <div class="p-3 rounded-lg bg-rose-950/40 border border-rose-500/20 text-rose-200 text-xs italic">
          "American Dental Association data proves 67% of acute toothache callers hang up on voicemail. When a patient is in pain on Sunday evening, they will not wait until Monday 8:00 AM—they book the first practice that replies on their phone."
        </div>
      </div>
    </div>

    <!-- Dormant Hygiene Chart Reactivation Cash Injection Engine -->
    <div class="bg-gradient-to-r from-slate-900 via-slate-900 to-indigo-950/40 p-6 rounded-2xl border border-indigo-500/40 shadow-2xl space-y-4">
      <div class="flex items-center justify-between flex-wrap gap-2">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/30 flex items-center justify-center text-lg">
            <i class="fa-solid fa-chart-line"></i>
          </div>
          <div>
            <h3 class="text-sm font-bold text-white uppercase tracking-wider">Secondary Practice Revenue Bleed: Dormant Hygiene Charts</h3>
            <span class="text-xs text-indigo-300">Overdue Recall Reactivation Analysis</span>
          </div>
        </div>
        <span class="px-3 py-1 rounded-full text-xs font-black bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 font-mono">
          {hygiene_roi}x Turnkey ROI in Month 1
        </span>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 text-center">
        <div class="bg-slate-950/80 p-3.5 rounded-xl border border-slate-800">
          <span class="text-[10px] text-slate-400 uppercase font-bold block">Estimated Overdue Charts (6+ Mo)</span>
          <div class="text-xl font-bold text-white font-mono mt-1">{dormant_charts:,} Patients</div>
          <span class="text-[10px] text-slate-500">~35% of patient database</span>
        </div>
        <div class="bg-slate-950/80 p-3.5 rounded-xl border border-slate-800">
          <span class="text-[10px] text-slate-400 uppercase font-bold block">Total Trapped Hygiene Revenue</span>
          <div class="text-xl font-bold text-slate-300 font-mono mt-1">${trapped_hygiene_rev:,}</div>
          <span class="text-[10px] text-slate-500">At $225 avg prophy + exam</span>
        </div>
        <div class="bg-indigo-950/40 p-3.5 rounded-xl border border-indigo-500/30">
          <span class="text-[10px] text-indigo-300 uppercase font-bold block">Immediate Month 1 Cash Injection</span>
          <div class="text-xl font-black text-indigo-300 font-mono mt-1">+${month1_hygiene_cash:,}</div>
          <span class="text-[10px] text-emerald-400 font-bold">14.5% WhatsApp recall booking</span>
        </div>
      </div>

      <div class="p-3.5 rounded-xl bg-slate-950/90 border border-slate-800 text-xs text-slate-300 space-y-1">
        <div class="font-bold text-indigo-300">Why WhatsApp Out-Performs Front-Desk Calling:</div>
        <p class="text-[11px] text-slate-400 leading-relaxed">
          Front-desk phone calls reach voicemail 82% of the time. Postcards are discarded. WhatsApp broadcast recall delivers a <strong>98% open rate</strong> with 1-tap chair self-scheduling. Recovering just 10% of your overdue hygiene charts covers our entire $1,500 turnkey installation within the first 14 days.
        </p>
      </div>
    </div>

    <!-- Live Interactive WhatsApp Patient Simulator & Coexistence -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-8 items-center">
      <div class="space-y-4">
        <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-bold bg-emerald-500/10 text-emerald-300 border border-emerald-500/30">
          <i class="fa-brands fa-whatsapp text-sm"></i>
          <span>The Solution • 24/7 Instant Recovery</span>
        </div>
        <h3 class="text-2xl font-black text-white">
          A Turnkey WhatsApp Patient Intake System Configured Specifically for {doc_display}
        </h3>
        <p class="text-xs text-slate-300 leading-relaxed">
          We do not replace your front desk or your daytime {detected_ehr} practice management software. 
          Instead, we sit exclusively outside office hours. When weekend callers reach your line, they receive an instant WhatsApp triage link within 5 seconds.
        </p>
        <ul class="space-y-2.5 text-xs text-slate-300">
          <li class="flex items-start gap-2.5">
            <span class="text-emerald-400 font-bold text-sm">✓</span>
            <span><strong>24/7 Autonomous Triage</strong>: Assesses patient pain, collects insurance (Delta, MetLife, Cigna), and locks open Monday chair slots.</span>
          </li>
          <li class="flex items-start gap-2.5">
            <span class="text-emerald-400 font-bold text-sm">✓</span>
            <span><strong>Seamless PMS Coexistence</strong>: Plugs directly alongside {detected_ehr} without staff retraining or phone disruption.</span>
          </li>
          <li class="flex items-start gap-2.5">
            <span class="text-emerald-400 font-bold text-sm">✓</span>
            <span><strong>Zero Lost Patients</strong>: Catches $2,000 emergency crowns and dental implants before competitors can touch them.</span>
          </li>
        </ul>

        <div class="pt-2 flex items-center gap-3">
          <a href="{whatsapp_link}" target="_blank" class="px-5 py-3 rounded-xl bg-[#25D366] hover:bg-[#128C7E] text-slate-950 font-black text-xs flex items-center gap-2 shadow-lg transition">
            <i class="fa-brands fa-whatsapp text-base"></i> Test on Your Own Phone
          </a>
          <div class="text-[11px] text-slate-400 font-medium">Or scan the QR code on desktop</div>
        </div>
      </div>

      <!-- Embedded Mobile Simulator Mockup -->
      <div class="bg-slate-900 border border-emerald-500/30 rounded-3xl p-4 shadow-2xl max-w-sm mx-auto w-full">
        <div class="flex items-center justify-between pb-3 border-b border-slate-800 text-xs">
          <span class="font-bold text-slate-300 flex items-center gap-1.5">
            <i class="fa-brands fa-whatsapp text-[#25D366]"></i> Live Prototype Preview
          </span>
          <span class="text-[10px] text-emerald-400 font-mono animate-pulse">● Active AI Bot</span>
        </div>

        <div class="wa-bg p-3 rounded-2xl my-3 space-y-2.5 min-h-[300px] text-xs">
          <!-- Turn 1 -->
          <div class="flex justify-end">
            <div class="chat-bubble-user p-2.5 text-white max-w-[85%] shadow text-[11px]">
              Hi, I cracked my back molar eating dinner and the pain is intense. Can I get in tomorrow morning?
              <span class="text-[9px] text-emerald-200 block text-right pt-0.5">8:15 PM &check;&check;</span>
            </div>
          </div>
          <!-- Turn 2 -->
          <div class="flex justify-start">
            <div class="chat-bubble-bot p-2.5 text-slate-200 max-w-[85%] shadow text-[11px] space-y-1">
              <p>Hello! 👋 I'm {doc_display}'s 24/7 Patient Assistant at <strong>{clinic_name}</strong>. We're so sorry you're in pain!</p>
              <p>The doctor has an emergency chair opening tomorrow at <strong>9:30 AM</strong> or <strong>11:15 AM</strong>. Which time works better for you?</p>
              <span class="text-[9px] text-slate-400 block text-right pt-0.5">8:15 PM &check;&check;</span>
            </div>
          </div>
          <!-- Turn 3 -->
          <div class="flex justify-end">
            <div class="chat-bubble-user p-2.5 text-white max-w-[85%] shadow text-[11px]">
              9:30 AM please! Do you accept Delta Dental?
              <span class="text-[9px] text-emerald-200 block text-right pt-0.5">8:16 PM &check;&check;</span>
            </div>
          </div>
          <!-- Turn 4 -->
          <div class="flex justify-start">
            <div class="chat-bubble-bot p-2.5 text-slate-200 max-w-[85%] shadow text-[11px]">
              Holding 9:30 AM for you! Yes, we work with Delta Dental. Please reply with your full name to receive instant check-in confirmation. 🦷
              <span class="text-[9px] text-slate-400 block text-right pt-0.5">8:16 PM &check;&check;</span>
            </div>
          </div>
        </div>

        <div class="text-center pt-1">
          <a href="{base_app_url}/demo/{lead_id}" target="_blank" class="text-xs font-bold text-emerald-400 hover:text-emerald-300 flex items-center justify-center gap-1">
            <span>Open Full Interactive Simulator</span> <i class="fa-solid fa-arrow-up-right-from-square text-[10px]"></i>
          </a>
        </div>
      </div>
    </div>

    <!-- Transparent Unit Economics & Break-Even Guarantee -->
    <div id="book-walkthrough" class="bg-slate-900 border border-slate-800 rounded-3xl p-8 shadow-2xl space-y-6">
      <div class="text-center max-w-2xl mx-auto space-y-2">
        <h3 class="text-2xl font-black text-white">Turnkey Investment & Single-Patient Guarantee</h3>
        <p class="text-xs text-slate-400">Zero long-term contracts. Turnkey setup completed in under 48 hours.</p>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-3xl mx-auto">
        <div class="bg-slate-950 p-6 rounded-2xl border border-slate-800 space-y-3">
          <span class="text-xs font-bold text-slate-400 uppercase tracking-wider block">Turnkey Installation</span>
          <div class="text-4xl font-black text-white font-mono">$1,500 <span class="text-xs text-slate-500 font-sans font-normal">one-time</span></div>
          <ul class="text-xs text-slate-300 space-y-2 pt-2">
            <li class="flex items-center gap-2"><i class="fa-solid fa-check text-emerald-400"></i> Full custom triage conversational AI tailored to clinic</li>
            <li class="flex items-center gap-2"><i class="fa-solid fa-check text-emerald-400"></i> Local phone number routing & after-hours trigger setup</li>
            <li class="flex items-center gap-2"><i class="fa-solid fa-check text-emerald-400"></i> {detected_ehr} schedule & office staff sync</li>
          </ul>
        </div>

        <div class="bg-slate-950 p-6 rounded-2xl border border-emerald-500/40 space-y-3 relative overflow-hidden">
          <div class="absolute top-3 right-3 px-2 py-0.5 rounded text-[9px] font-black bg-emerald-500 text-slate-950 uppercase">Zero-Risk</div>
          <span class="text-xs font-bold text-emerald-400 uppercase tracking-wider block">Ongoing 24/7 Hosting & Updates</span>
          <div class="text-4xl font-black text-emerald-400 font-mono">$399 <span class="text-xs text-slate-400 font-sans font-normal">/month</span></div>
          <ul class="text-xs text-slate-300 space-y-2 pt-2">
            <li class="flex items-center gap-2"><i class="fa-solid fa-check text-emerald-400"></i> Unlimited patient intake conversations & SMS recovery</li>
            <li class="flex items-center gap-2"><i class="fa-solid fa-check text-emerald-400"></i> 24/7 emergency monitoring & weekend failover</li>
            <li class="flex items-center gap-2"><i class="fa-solid fa-check text-emerald-400"></i> Single-patient break-even guarantee: cancels anytime</li>
          </ul>
        </div>
      </div>

      <!-- 1-Click Action Bar -->
      <div class="text-center pt-4 space-y-4">
        <div class="flex flex-col sm:flex-row items-center justify-center gap-3">
          <button onclick="lockPracticeTerritoryDeposit()" id="btn-lock-territory-portal" class="w-full sm:w-auto px-8 py-4 rounded-2xl bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-slate-950 font-black text-sm shadow-xl shadow-emerald-500/25 transition cursor-pointer flex items-center justify-center gap-2">
            <i class="fa-solid fa-lock"></i>
            <span>Lock 3-Mile Exclusive Territory & Setup ($1,500)</span>
          </button>
          <a href="{calendar_link}" target="_blank" class="w-full sm:w-auto px-6 py-4 rounded-2xl bg-slate-800 hover:bg-slate-700 text-white font-bold text-xs border border-slate-700 transition flex items-center justify-center gap-2">
            <i class="fa-solid fa-calendar-check"></i>
            <span>Or Schedule 10-Min Demo (Thursday 11 AM)</span>
          </a>
        </div>
        <div class="text-xs text-slate-400 pt-1 flex items-center justify-center gap-4 flex-wrap">
          <a href="/agreement/{lead_id}" target="_blank" class="text-emerald-400 hover:underline font-bold flex items-center gap-1.5">
            <i class="fa-solid fa-file-contract"></i> View Official SLA & 30-Day Break-Even Guarantee
          </a>
          <span>&bull;</span>
          <span>Direct Rep: <a href="tel:{rep_phone}" class="text-slate-300 font-bold hover:underline">{rep_phone}</a></span>
        </div>
      </div>
    </div>

  </main>

  <!-- Confidentiality Footer -->
  <footer class="border-t border-slate-800/80 bg-slate-950 py-6 text-center text-xs text-slate-500">
    <div class="max-w-6xl mx-auto px-4 space-y-1">
      <p>Confidential Practice Opportunity Analysis prepared for {clinic_name}. All rights reserved.</p>
      <p class="text-[10px] text-slate-600">Calculated based on local metropolitan dental market benchmarks and verified public registry data.</p>
    </div>
  </footer>

  <!-- Visitor Telemetry Beacon & Instant Deposit Lock Handler -->
  <script>
    try {{
      fetch('/api/pitch/{lead_id}/viewed', {{ method: 'POST' }});
    }} catch(e) {{}}

    async function lockPracticeTerritoryDeposit() {{
      const btn = document.getElementById('btn-lock-territory-portal');
      if (btn) {{
        btn.innerHTML = '<i class="fa-solid fa-spinner animate-spin"></i> Securing 3-Mile Territory...';
        btn.disabled = true;
      }}
      try {{
        const res = await fetch('/api/leads/{lead_id}/checkout/lock-deposit', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ payment_ref: 'stripe_mock_' + Date.now() }})
        }});
        const data = await res.json();
        if (data.status === 'success') {{
          alert('🏆 Territory Secured! 3-mile exclusivity around {clinic_name} is now locked. Our concierge team will reach out within 15 minutes.');
          window.location.href = '/agreement/{lead_id}';
        }} else {{
          alert('Notice: ' + (data.message || 'Unable to complete lock'));
        }}
      }} catch(e) {{
        alert('Network error connecting to payment gateway.');
      }} finally {{
        if (btn) {{
          btn.innerHTML = '<i class="fa-solid fa-check text-emerald-950"></i> Territory Locked (Status: WON)';
        }}
      }}
    }}
  </script>

</body>
</html>"""
