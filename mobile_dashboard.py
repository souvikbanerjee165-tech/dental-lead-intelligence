"""
Mobile-First iPhone PWA Dashboard for On-the-Go Lead Intercepts & Calling.
Optimized for mobile Safari, standalone home-screen shortcut, and 1-touch AI SDR dispatch.
"""

def render_mobile_dashboard_html(base_url: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
  <title>LeadRadar - Dental Intercept Cockpit</title>
  
  <!-- Apple Home Screen PWA Meta Tags -->
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="apple-mobile-web-app-title" content="LeadRadar">
  <meta name="theme-color" content="#090d16">
  <link rel="manifest" href="/manifest.json">
  <link rel="apple-touch-icon" href="https://cdn-icons-png.flaticon.com/512/3063/3063822.png">

  <!-- Tailwind CSS & FontAwesome -->
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    body {{
      background-color: #090d16;
      color: #f1f5f9;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      -webkit-tap-highlight-color: transparent;
    }}
    .pulse-dot {{
      animation: pulse-ring 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
    }}
    @keyframes pulse-ring {{
      0%, 100% {{ opacity: 1; transform: scale(1); }}
      50% {{ opacity: 0.4; transform: scale(1.15); }}
    }}
    .safe-top {{ padding-top: env(safe-area-inset-top, 16px); }}
    .safe-bottom {{ padding-bottom: env(safe-area-inset-bottom, 20px); }}
  </style>
</head>
<body class="safe-top safe-bottom flex flex-col min-h-screen">

  <!-- Toast Notification -->
  <div id="toast" class="fixed top-4 left-4 right-4 z-50 transform -translate-y-20 opacity-0 transition-all duration-300 pointer-events-none">
    <div id="toast-inner" class="bg-slate-900 border border-emerald-500/80 rounded-2xl p-3.5 shadow-2xl flex items-center gap-3">
      <i id="toast-icon" class="fa-solid fa-circle-check text-emerald-400 text-lg"></i>
      <div class="flex-1 text-xs text-white font-medium" id="toast-msg">Alert</div>
    </div>
  </div>

  <!-- Top Sticky Header -->
  <header class="sticky top-0 z-40 bg-slate-950/90 backdrop-blur-md border-b border-slate-800/80 px-4 py-3 flex items-center justify-between">
    <div class="flex items-center gap-2.5">
      <div class="w-9 h-9 rounded-xl bg-gradient-to-tr from-emerald-500 to-teal-400 flex items-center justify-center text-slate-950 font-black shadow-lg shadow-emerald-500/20">
        <i class="fa-solid fa-satellite-dish text-base"></i>
      </div>
      <div>
        <h1 class="text-base font-black tracking-tight leading-none text-white">Lead<span class="text-emerald-400">Radar</span></h1>
        <div class="flex items-center gap-1.5 pt-0.5">
          <span class="w-2 h-2 rounded-full bg-emerald-400 pulse-dot inline-block"></span>
          <span class="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">Live Intercept & AI SDR</span>
        </div>
      </div>
    </div>

    <!-- Quick Stat & Refresh -->
    <div class="flex items-center gap-2">
      <button onclick="simulateTestClick()" title="Test Live Alert" class="px-2.5 py-1.5 rounded-lg bg-slate-800 text-xs text-slate-300 border border-slate-700 active:scale-95 transition">
        <i class="fa-solid fa-flask text-emerald-400 mr-1"></i>Test
      </button>
      <button onclick="fetchData()" class="w-8 h-8 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-300 active:scale-95 transition">
        <i class="fa-solid fa-rotate text-xs" id="refresh-icon"></i>
      </button>
    </div>
  </header>

  <!-- Navigation Segment Tabs -->
  <div class="px-4 pt-3 pb-1">
    <div class="grid grid-cols-2 p-1 bg-slate-900 border border-slate-800 rounded-xl">
      <button id="tab-btn-hand-raisers" onclick="switchTab('hand_raisers')" class="py-2 text-xs font-bold rounded-lg transition text-slate-950 bg-emerald-400 shadow flex items-center justify-center gap-1.5">
        <i class="fa-solid fa-fire text-amber-900"></i>
        <span>Hand-Raisers</span>
        <span id="badge-hand-raisers" class="px-1.5 py-0.2 rounded-full text-[10px] font-black bg-slate-950 text-emerald-400 ml-0.5">0</span>
      </button>
      <button id="tab-btn-top-targets" onclick="switchTab('top_targets')" class="py-2 text-xs font-bold rounded-lg transition text-slate-400 hover:text-white flex items-center justify-center gap-1.5">
        <i class="fa-solid fa-bullseye"></i>
        <span>Top Targets</span>
        <span id="badge-top-targets" class="px-1.5 py-0.2 rounded-full text-[10px] font-black bg-slate-800 text-slate-300 ml-0.5">0</span>
      </button>
    </div>
  </div>

  <!-- Value Anchor & Winning Offer Note Banner -->
  <div class="px-4 py-2">
    <div class="bg-gradient-to-r from-emerald-950/60 to-slate-900 border border-emerald-500/30 rounded-xl p-3 text-xs space-y-1">
      <div class="font-bold text-emerald-400 flex items-center gap-1.5">
        <i class="fa-solid fa-shield-halved"></i> The Zero-Risk Closer Formula
      </div>
      <p class="text-[11px] text-slate-300 leading-snug">
        <strong>$1,200 setup transparently anchored</strong>, but deferred: <em>"Pay $0 setup fee upfront today. The $1,200 is covered out of the first high-value patient the AI captures ($1,200+)."</em>
      </p>
    </div>
  </div>

  <!-- Main Feed Container -->
  <main class="flex-1 px-4 py-2 space-y-3 pb-8" id="cards-container">
    <div class="text-center py-12 text-slate-500 text-xs">
      <i class="fa-solid fa-circle-notch fa-spin text-xl text-emerald-400 mb-2 block"></i>
      Loading live radar targets...
    </div>
  </main>

  <!-- Speed-to-Lead Script Modal Bottom Sheet -->
  <div id="script-modal" class="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm hidden flex items-end">
    <div class="w-full bg-slate-900 border-t border-slate-700 rounded-t-3xl p-5 space-y-4 max-h-[85vh] overflow-y-auto safe-bottom">
      <div class="flex items-center justify-between border-b border-slate-800 pb-3">
        <div>
          <span class="text-[10px] uppercase font-bold text-emerald-400">Door-Opener & Playbook</span>
          <h3 class="text-sm font-black text-white" id="modal-clinic-name">Clinic Name</h3>
        </div>
        <button onclick="closeScriptModal()" class="w-8 h-8 rounded-full bg-slate-800 text-slate-400 flex items-center justify-center">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>

      <div class="bg-slate-950 border border-slate-800 rounded-xl p-3.5 space-y-2">
        <div class="text-[11px] font-bold text-amber-400 flex items-center gap-1.5">
          <i class="fa-solid fa-bolt"></i> Speed-to-Lead 20s Opener:
        </div>
        <p class="text-xs text-slate-200 leading-relaxed font-mono" id="modal-script-text">
          "Hey Dr. [Name]! I noticed your team was just reviewing the after-hours emergency patient teardown for [Clinic]..."
        </p>
      </div>

      <div class="bg-slate-950 border border-slate-800 rounded-xl p-3.5 space-y-2">
        <div class="text-[11px] font-bold text-indigo-400 flex items-center gap-1.5">
          <i class="fa-solid fa-shield-halved"></i> Gatekeeper Bypass Rebuttal:
        </div>
        <p class="text-xs text-slate-300 leading-relaxed font-mono" id="modal-gatekeeper-text">
          "We audit after-hours revenue loss for local independent practices. We noticed emergency weekend calls hit voicemail..."
        </p>
      </div>

      <div class="space-y-2 pt-1">
        <a id="modal-btn-call" href="#" class="w-full py-3.5 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 text-slate-950 font-black text-sm flex items-center justify-center gap-2 shadow-lg shadow-emerald-500/25 active:scale-95 transition">
          <i class="fa-solid fa-phone"></i> Call Doctor Directly
        </a>
        <div class="grid grid-cols-2 gap-2">
          <button id="modal-btn-ai-call" onclick="" class="py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs flex items-center justify-center gap-1.5 active:scale-95 transition shadow">
            <i class="fa-solid fa-robot"></i> AI SDR Call
          </button>
          <button id="modal-btn-ai-sms" onclick="" class="py-2.5 rounded-xl bg-teal-600 hover:bg-teal-500 text-white font-bold text-xs flex items-center justify-center gap-1.5 active:scale-95 transition shadow">
            <i class="fa-solid fa-paper-plane"></i> Send Telnyx SMS
          </button>
        </div>
        <a id="modal-btn-wa" href="#" target="_blank" class="w-full py-2.5 rounded-xl bg-slate-800 border border-slate-700 text-slate-200 font-bold text-xs flex items-center justify-center gap-2 active:scale-95 transition">
          <i class="fa-brands fa-whatsapp text-emerald-400"></i> Open WhatsApp Web
        </a>
      </div>
    </div>
  </div>

  <script>
    let activeTab = 'hand_raisers';
    let cachedData = {{ hand_raisers: [], top_targets: [] }};
    let currentModalLeadId = '';

    function showToast(msg, isSuccess = true) {{
      const toast = document.getElementById('toast');
      const inner = document.getElementById('toast-inner');
      const icon = document.getElementById('toast-icon');
      const msgEl = document.getElementById('toast-msg');

      msgEl.textContent = msg;
      if (isSuccess) {{
        inner.className = 'bg-slate-900 border border-emerald-500/80 rounded-2xl p-3.5 shadow-2xl flex items-center gap-3';
        icon.className = 'fa-solid fa-circle-check text-emerald-400 text-lg';
      }} else {{
        inner.className = 'bg-slate-900 border border-rose-500/80 rounded-2xl p-3.5 shadow-2xl flex items-center gap-3';
        icon.className = 'fa-solid fa-circle-exclamation text-rose-400 text-lg';
      }}
      toast.classList.remove('-translate-y-20', 'opacity-0');
      toast.classList.add('translate-y-0', 'opacity-100');
      setTimeout(() => {{
        toast.classList.add('-translate-y-20', 'opacity-0');
        toast.classList.remove('translate-y-0', 'opacity-100');
      }}, 3500);
    }}

    async function fetchData() {{
      const icon = document.getElementById('refresh-icon');
      if (icon) icon.classList.add('fa-spin');
      try {{
        const [resHR, resTargets] = await Promise.all([
          fetch('/api/hand-raisers').then(r => r.json()).catch(() => ({{ hand_raisers: [] }})),
          fetch('/api/high-intent/top-targets?limit=20').then(r => r.json()).catch(() => ({{ top_targets: [] }}))
        ]);
        cachedData.hand_raisers = resHR.hand_raisers || [];
        cachedData.top_targets = resTargets.top_targets || [];

        document.getElementById('badge-hand-raisers').textContent = cachedData.hand_raisers.length;
        document.getElementById('badge-top-targets').textContent = cachedData.top_targets.length;

        renderCurrentTab();
      }} catch (e) {{
        console.error(e);
      }} finally {{
        if (icon) icon.classList.remove('fa-spin');
      }}
    }}

    function switchTab(tab) {{
      activeTab = tab;
      const btnHR = document.getElementById('tab-btn-hand-raisers');
      const btnTargets = document.getElementById('tab-btn-top-targets');

      if (tab === 'hand_raisers') {{
        btnHR.className = 'py-2 text-xs font-bold rounded-lg transition text-slate-950 bg-emerald-400 shadow flex items-center justify-center gap-1.5';
        btnTargets.className = 'py-2 text-xs font-bold rounded-lg transition text-slate-400 hover:text-white flex items-center justify-center gap-1.5';
      }} else {{
        btnTargets.className = 'py-2 text-xs font-bold rounded-lg transition text-slate-950 bg-emerald-400 shadow flex items-center justify-center gap-1.5';
        btnHR.className = 'py-2 text-xs font-bold rounded-lg transition text-slate-400 hover:text-white flex items-center justify-center gap-1.5';
      }}
      renderCurrentTab();
    }}

    async function triggerSdrCall(leadId, clinicName) {{
      showToast(`Initiating AI SDR call to ${{clinicName}}...`);
      try {{
        const res = await fetch(`/api/sdr/launch-call/${{leadId}}`, {{ method: 'POST' }});
        const data = await res.json();
        if (res.ok && data.status === 'success') {{
          showToast(`AI SDR call placed via Telnyx! (${{data.target_phone}})`);
        }} else {{
          showToast(data.detail || data.error || 'Failed to dispatch AI call', false);
        }}
      }} catch (e) {{
        showToast('Call dispatch error: ' + e.message, false);
      }}
    }}

    async function triggerSdrSms(leadId, clinicName) {{
      showToast(`Dispatching Telnyx SMS teardown to ${{clinicName}}...`);
      try {{
        const res = await fetch(`/api/sdr/dispatch-sms/${{leadId}}`, {{ method: 'POST' }});
        const data = await res.json();
        if (res.ok && data.success) {{
          showToast(`Teardown link sent to ${{data.to}} via Telnyx!`);
        }} else {{
          showToast(data.detail || data.error || 'Failed to send SMS', false);
        }}
      }} catch (e) {{
        showToast('SMS dispatch error: ' + e.message, false);
      }}
    }}

    function renderCurrentTab() {{
      const container = document.getElementById('cards-container');
      const list = activeTab === 'hand_raisers' ? cachedData.hand_raisers : cachedData.top_targets;

      if (!list || list.length === 0) {{
        if (activeTab === 'hand_raisers') {{
          container.innerHTML = `
            <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 text-center space-y-3">
              <div class="w-12 h-12 rounded-full bg-slate-800 flex items-center justify-center mx-auto text-emerald-400 text-xl">
                <i class="fa-solid fa-satellite-dish"></i>
              </div>
              <h3 class="text-sm font-bold text-white">No Active Hand-Raisers Right Now</h3>
              <p class="text-xs text-slate-400 leading-relaxed">
                When a doctor opens their custom audit link or tests their simulator, they will instantly light up here with a 1-tap call button!
              </p>
              <button onclick="simulateTestClick()" class="px-4 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 text-xs font-black shadow-lg active:scale-95 transition">
                <i class="fa-solid fa-play mr-1"></i> Simulate Test Doctor Intercept
              </button>
            </div>
          `;
        }} else {{
          container.innerHTML = `<div class="text-center py-8 text-slate-500 text-xs">No targets loaded.</div>`;
        }}
        return;
      }}

      let html = '';
      list.forEach((item, index) => {{
        const isHR = activeTab === 'hand_raisers';
        const clinic = item.clinic_name || 'Dental Practice';
        const doc = item.doctor_display || item.doctor_salutation || 'Practice Owner';
        const phone = item.phone || '';
        const digits = phone.replace(/\\D/g, '');
        const cleanPhone = digits.length === 10 ? '1' + digits : digits;
        const leaked = item.monthly_leaked_usd || (item.unit_economics && item.unit_economics.monthly_leaked_revenue_usd) || 9600;
        const score = item.high_intent_score || 90;
        const isLive = item.is_live_now || false;
        const timeLabel = item.time_label || (isHR ? 'Hand-Raiser' : 'Prime Target');
        const script = item.speed_to_lead_hook || item.call_playbook?.step2_doctor_opener_20s?.hook_script || '';
        const gatekeeper = item.gatekeeper_opener || item.call_playbook?.step1_gatekeeper_bypass?.rebuttal || '';
        const waUrl = item.whatsapp_url || item.call_playbook?.whatsapp_one_click_url || '#';
        const pitchUrl = item.pitch_portal_url || `/pitch/${{item.lead_id}}`;

        html += `
          <div class="bg-slate-900 border ${{isLive ? 'border-emerald-500/80 shadow-lg shadow-emerald-500/10' : 'border-slate-800'}} rounded-2xl p-4 space-y-3 relative overflow-hidden">
            ${{isLive ? '<div class="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-emerald-500 to-teal-400"></div>' : ''}}
            
            <div class="flex items-start justify-between gap-2">
              <div>
                <div class="flex items-center gap-1.5 flex-wrap">
                  <span class="px-2 py-0.5 rounded text-[10px] font-black ${{isLive ? 'bg-emerald-500 text-slate-950 animate-pulse' : 'bg-slate-800 text-emerald-400'}}">
                    ${{isLive ? '🔥 ACTIVE NOW' : timeLabel}}
                  </span>
                  <span class="text-[10px] font-bold text-slate-400">${{item.city || 'Austin'}}, ${{item.region || 'TX'}}</span>
                </div>
                <h2 class="text-sm font-black text-white pt-1 leading-snug">${{clinic}}</h2>
                <div class="text-xs text-slate-300 font-medium">${{doc}}</div>
              </div>
              <div class="text-right flex-shrink-0">
                <span class="text-[10px] text-slate-500 block uppercase font-bold">Leaked</span>
                <span class="text-xs font-mono font-black text-rose-400">-${{Number(leaked).toLocaleString()}}/mo</span>
              </div>
            </div>

            <!-- 1-Tap Action Row: Human Direct Call -->
            <div class="grid grid-cols-2 gap-2 pt-1">
              <a href="tel:+${{cleanPhone}}" class="py-2.5 px-3 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 text-slate-950 font-black text-xs flex items-center justify-center gap-1.5 shadow-md shadow-emerald-500/20 active:scale-95 transition">
                <i class="fa-solid fa-phone text-xs"></i>
                <span>Call Doctor</span>
              </a>
              <button onclick="openScriptModal('${{encodeURIComponent(clinic)}}', '${{encodeURIComponent(script)}}', '+${{cleanPhone}}', '${{encodeURIComponent(waUrl)}}', '${{encodeURIComponent(gatekeeper)}}', '${{item.lead_id}}')" class="py-2.5 px-3 rounded-xl bg-slate-800 border border-slate-700 text-slate-200 font-bold text-xs flex items-center justify-center gap-1.5 active:scale-95 transition">
                <i class="fa-solid fa-file-lines text-emerald-400"></i>
                <span>20s Script</span>
              </button>
            </div>

            <!-- AI SDR 1-Click Action Row -->
            <div class="grid grid-cols-2 gap-2 pt-0.5">
              <button onclick="triggerSdrCall('${{item.lead_id}}', '${{clinic.replace(/'/g, "\\\\'")}}')" class="py-2 px-2.5 rounded-xl bg-slate-800/90 hover:bg-slate-700 border border-indigo-500/40 text-indigo-300 font-bold text-[11px] flex items-center justify-center gap-1.5 active:scale-95 transition">
                <i class="fa-solid fa-robot text-indigo-400"></i>
                <span>AI SDR Call</span>
              </button>
              <button onclick="triggerSdrSms('${{item.lead_id}}', '${{clinic.replace(/'/g, "\\\\'")}}')" class="py-2 px-2.5 rounded-xl bg-slate-800/90 hover:bg-slate-700 border border-teal-500/40 text-teal-300 font-bold text-[11px] flex items-center justify-center gap-1.5 active:scale-95 transition">
                <i class="fa-solid fa-paper-plane text-teal-400"></i>
                <span>Send SMS Link</span>
              </button>
            </div>

            <div class="flex items-center justify-between text-[11px] text-slate-400 pt-1 border-t border-slate-800/80">
              <a href="${{pitchUrl}}" target="_blank" class="text-emerald-400 hover:underline flex items-center gap-1">
                <i class="fa-solid fa-arrow-up-right-from-square text-[10px]"></i> View Teardown
              </a>
              <a href="${{waUrl}}" target="_blank" class="text-slate-300 hover:text-white flex items-center gap-1">
                <i class="fa-brands fa-whatsapp text-emerald-400 text-xs"></i> WhatsApp
              </a>
            </div>
          </div>
        `;
      }});

      container.innerHTML = html;
    }}

    function openScriptModal(encodedClinic, encodedScript, phone, encodedWa, encodedGatekeeper, leadId) {{
      currentModalLeadId = leadId;
      const clinic = decodeURIComponent(encodedClinic);
      document.getElementById('modal-clinic-name').textContent = clinic;
      document.getElementById('modal-script-text').textContent = decodeURIComponent(encodedScript);
      document.getElementById('modal-gatekeeper-text').textContent = decodeURIComponent(encodedGatekeeper) || 'No gatekeeper rebuttal needed.';
      document.getElementById('modal-btn-call').href = 'tel:' + phone;
      document.getElementById('modal-btn-wa').href = decodeURIComponent(encodedWa);

      const aiCallBtn = document.getElementById('modal-btn-ai-call');
      aiCallBtn.onclick = () => triggerSdrCall(leadId, clinic);

      const aiSmsBtn = document.getElementById('modal-btn-ai-sms');
      aiSmsBtn.onclick = () => triggerSdrSms(leadId, clinic);

      document.getElementById('script-modal').classList.remove('hidden');
    }}

    function closeScriptModal() {{
      document.getElementById('script-modal').classList.add('hidden');
    }}

    async function simulateTestClick() {{
      const firstTarget = (cachedData.top_targets && cachedData.top_targets[0]) || (cachedData.hand_raisers && cachedData.hand_raisers[0]);
      const leadId = firstTarget ? firstTarget.lead_id : 'lead_sanfranciscodentaloffice_httpwwwsanfrandental';
      try {{
        await fetch(`/api/hand-raisers/test-trigger/${{leadId}}`, {{ method: 'POST' }});
        switchTab('hand_raisers');
        fetchData();
        showToast('Simulated live doctor click! Target moved to Hand-Raisers.');
      }} catch (e) {{
        console.error(e);
      }}
    }}

    // Initial fetch and auto-polling every 8 seconds
    fetchData();
    setInterval(fetchData, 8000);
  </script>
</body>
</html>
"""
