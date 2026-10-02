"""
AI Video Teardown & Animated Motion Card Engine.
Generates personalized video teardown experiences and animated motion cards for dental prospects.
Combines practice website screenshots, simulated 8:14 PM patient WhatsApp triage chat bubbles,
pulsing Loom-style video scrubbers, and audio narration from the Voicemail Sting engine.
"""

import os
import re
from pathlib import Path
from typing import Dict, Any, Optional

from voicemail_sting import VoicemailStingGenerator

BASE_DIR = Path(__file__).resolve().parent


class VideoTeardownEngine:
    """Renders personalized animated video cards and dedicated video landing pages."""

    @classmethod
    def generate_video_metadata(
        cls,
        lead_dict: Dict[str, Any],
        base_app_url: str = "http://127.0.0.1:8000"
    ) -> Dict[str, Any]:
        """Returns video teaser parameters, video landing URL, and duration."""
        lead_id = lead_dict.get("id") or "preview"
        clinic_name = lead_dict.get("name") or "Your Practice"
        raw_doc = lead_dict.get("doctor_name") or "Doctor"
        clean_doc = raw_doc.replace("Dr.", "").replace("Dr", "").strip()
        doc_display = f"Dr. {clean_doc}" if clean_doc else "the Practice Owner"
        
        missed_min = lead_dict.get("missed_rev_min") or 3500
        missed_max = lead_dict.get("missed_rev_max") or 7200
        avg_leakage = int((missed_min + missed_max) / 2)

        video_url = f"{base_app_url}/video/{lead_id}"
        video_title = f"{doc_display}: 60-Second Practice Audit (After-Hours Revenue Teardown)"
        teaser_text = (
            f"📹 Confidential 60s Video Teardown prepared for {doc_display} at {clinic_name}: "
            f"Watch how {avg_leakage:,}/mo in unreturned weekend patient calls is recovered in 5s on WhatsApp: {video_url}"
        )

        return {
            "lead_id": lead_id,
            "clinic_name": clinic_name,
            "doctor_name": doc_display,
            "video_url": video_url,
            "video_title": video_title,
            "duration_sec": 48,
            "teaser_text": teaser_text,
            "teaser_sms": teaser_text,
            "monthly_leakage": avg_leakage
        }

    @classmethod
    def render_video_player_page_html(
        cls,
        lead_dict: Dict[str, Any],
        base_app_url: str = "http://127.0.0.1:8000"
    ) -> str:
        """
        Renders a full-screen, cinema-dark video landing page at `/video/{lead_id}`
        with play/pause controls, synchronized Voicemail Sting audio, animated triage demo,
        and instant 1-click 'Lock Territory ($1,500)' CTA.
        """
        meta = cls.generate_video_metadata(lead_dict, base_app_url=base_app_url)
        lead_id = meta["lead_id"]
        clinic_name = meta["clinic_name"]
        doc_display = meta["doctor_name"]
        leakage = meta["monthly_leakage"]
        audio_sting_url = f"/output/stings/sting_{lead_id}.wav"

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{doc_display} • 60-Second Practice Revenue Teardown</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    body {{ background-color: #0b1117; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
    .wa-bg {{ background-color: #0b141a; background-image: radial-gradient(#1f2c34 1px, transparent 1px); background-size: 16px 16px; }}
    .glow-play {{ box-shadow: 0 0 40px rgba(16, 185, 129, 0.4); }}
  </style>
</head>
<body class="text-slate-100 min-h-screen flex flex-col justify-between selection:bg-emerald-500 selection:text-black">

  <!-- Header -->
  <header class="border-b border-slate-800 bg-slate-950/80 backdrop-blur sticky top-0 z-40">
    <div class="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
      <div class="flex items-center gap-2.5">
        <span class="w-3 h-3 rounded-full bg-rose-500 animate-pulse"></span>
        <span class="text-xs font-black uppercase tracking-wider text-rose-400">Confidential Practice Video Teardown</span>
      </div>
      <a href="/pitch/{lead_id}" class="text-xs font-bold text-slate-300 hover:text-emerald-400 transition flex items-center gap-1">
        <span>View Full Audit Data</span> <i class="fa-solid fa-arrow-right text-[10px]"></i>
      </a>
    </div>
  </header>

  <!-- Video Main Stage -->
  <main class="max-w-4xl mx-auto px-4 py-8 space-y-6 flex-1 w-full">
    
    <div class="text-center space-y-2">
      <h1 class="text-2xl sm:text-3xl font-black text-white">{clinic_name}: After-Hours Patient Production Leakage</h1>
      <p class="text-xs text-slate-400">Prepared exclusively for <strong>{doc_display}</strong> &bull; Estimated Monthly Gap: <span class="text-rose-400 font-bold font-mono">${leakage:,}/mo</span></p>
    </div>

    <!-- Cinema Video Card Mockup -->
    <div class="relative bg-slate-900 border-2 border-slate-800 rounded-3xl overflow-hidden shadow-2xl group">
      
      <!-- Video Visual Screen Area -->
      <div class="relative aspect-video bg-gradient-to-tr from-slate-950 via-slate-900 to-slate-950 p-6 flex flex-col justify-between overflow-hidden">
        
        <!-- Top bar overlay -->
        <div class="flex items-center justify-between text-xs z-10">
          <div class="flex items-center gap-2 bg-slate-900/90 backdrop-blur px-3 py-1.5 rounded-full border border-slate-700">
            <span class="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
            <span class="font-bold text-slate-200 text-[11px]">{clinic_name} • Live Audit</span>
          </div>
          <span class="text-[11px] text-slate-400 font-mono bg-slate-900/80 px-2 py-1 rounded-md">1080p 60FPS</span>
        </div>

        <!-- Center Stage: Simulated Phone & Chat Overlay -->
        <div class="flex items-center justify-center my-auto z-10">
          <div id="video-chat-mock" class="wa-bg max-w-sm w-full p-4 rounded-2xl border border-emerald-500/30 shadow-2xl space-y-3">
            <div class="flex items-center justify-between border-b border-slate-800 pb-2 text-[11px]">
              <span class="font-bold text-emerald-400 flex items-center gap-1.5">
                <i class="fa-brands fa-whatsapp text-sm"></i> {clinic_name} Assistant
              </span>
              <span class="text-[9px] text-slate-400 font-mono">8:14 PM (Office Closed)</span>
            </div>
            
            <div class="space-y-2 text-xs">
              <div class="bg-emerald-900/60 text-slate-100 p-2.5 rounded-lg text-[11px]">
                "Hello, I cracked my back molar eating dinner and the pain is unbearable. Can I get in first thing tomorrow?"
              </div>
              <div class="bg-slate-800 text-slate-200 p-2.5 rounded-lg text-[11px] space-y-1">
                <p class="font-bold text-emerald-300">⚡ 5-Second Auto-Triage:</p>
                <p>"Hi there! Dr. Miller has an emergency chair open tomorrow at 9:30 AM. Tap below to hold this chair instantly."</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Play/Pause Big Center Button Overlay -->
        <div id="play-overlay" class="absolute inset-0 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center z-20 transition-all cursor-pointer" onclick="toggleTeardownVideoPlay()">
          <div class="w-20 h-20 rounded-full bg-gradient-to-tr from-emerald-500 to-teal-400 text-slate-950 flex items-center justify-center text-3xl font-black shadow-2xl glow-play hover:scale-110 transition cursor-pointer">
            <i class="fa-solid fa-play ml-1" id="video-play-icon"></i>
          </div>
        </div>

        <!-- Hidden Audio Element for Voicemail Sting Playback -->
        <audio id="video-sting-audio" src="{audio_sting_url}" preload="auto"></audio>

        <!-- Bottom Controls / Scrubber Bar -->
        <div class="z-10 space-y-2 pt-2">
          <div class="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden cursor-pointer" onclick="seekVideoAudio(event)">
            <div id="video-progress-bar" class="bg-gradient-to-r from-emerald-400 to-teal-400 h-full w-0 transition-all"></div>
          </div>
          <div class="flex items-center justify-between text-[11px] text-slate-400">
            <div class="flex items-center gap-3">
              <button onclick="toggleTeardownVideoPlay()" class="hover:text-white transition">
                <i class="fa-solid fa-play" id="btn-ctrl-play"></i>
              </button>
              <span id="video-time-display" class="font-mono">00:00 / 00:22</span>
            </div>
            <span class="text-emerald-400 font-bold">Empirical Auditory Evidence</span>
          </div>
        </div>

      </div>
    </div>

    <!-- High-Impact CTA Strip -->
    <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 flex flex-col sm:flex-row items-center justify-between gap-4 shadow-xl">
      <div>
        <h3 class="text-base font-extrabold text-white">Lock This Missed Call System for Your Practice</h3>
        <p class="text-xs text-slate-400 mt-0.5">Exclusive to 1 dental practice in your 3-mile radius &bull; $1,500 turnkey setup with 30-day single-patient guarantee.</p>
      </div>
      <div class="flex items-center gap-3 w-full sm:w-auto shrink-0 flex-wrap">
        <a href="/pitch/{lead_id}#book-walkthrough" class="flex-1 sm:flex-none px-6 py-3 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-slate-950 font-black text-xs shadow-lg transition flex items-center justify-center gap-2">
          <i class="fa-solid fa-lock"></i>
          <span>Lock 3-Mile Territory ($1,500)</span>
        </a>
        <a href="/agreement/{lead_id}" class="px-4 py-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 font-bold text-xs border border-slate-700 transition flex items-center justify-center gap-1.5" target="_blank">
          <i class="fa-solid fa-file-contract text-emerald-400"></i>
          <span>Review SLA</span>
        </a>
      </div>
    </div>

  </main>

  <footer class="border-t border-slate-800 py-4 text-center text-[11px] text-slate-500">
    Confidential Practice Video Audit &bull; All Rights Reserved
  </footer>

  <script>
    const audio = document.getElementById('video-sting-audio');
    const playIcon = document.getElementById('video-play-icon');
    const ctrlPlay = document.getElementById('btn-ctrl-play');
    const overlay = document.getElementById('play-overlay');
    const progressBar = document.getElementById('video-progress-bar');
    const timeDisplay = document.getElementById('video-time-display');

    function toggleTeardownVideoPlay() {{
      if (audio.paused) {{
        audio.play().then(() => {{
          overlay.classList.add('opacity-0', 'pointer-events-none');
          ctrlPlay.className = 'fa-solid fa-pause';
        }}).catch(() => {{}});
      }} else {{
        audio.pause();
        overlay.classList.remove('opacity-0', 'pointer-events-none');
        ctrlPlay.className = 'fa-solid fa-play';
      }}
    }}

    audio.ontimeupdate = () => {{
      if (!audio.duration) return;
      const pct = (audio.currentTime / audio.duration) * 100;
      progressBar.style.width = pct + '%';
      const cur = Math.floor(audio.currentTime);
      const dur = Math.floor(audio.duration);
      timeDisplay.innerText = `00:${{cur < 10 ? '0' : ''}}${{cur}} / 00:${{dur < 10 ? '0' : ''}}${{dur}}`;
    }};

    audio.onended = () => {{
      overlay.classList.remove('opacity-0', 'pointer-events-none');
      ctrlPlay.className = 'fa-solid fa-play';
      progressBar.style.width = '0%';
    }};
  </script>

</body>
</html>"""
