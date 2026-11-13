/**
 * Multi-Line Call Switchboard HUD
 * Blueprint V1.0.0 Section 6 (Step 6) Specification
 * Renders 4-channel tabs, live timers, VAD state, and the Zero-Repetition Warm Transfer Card.
 */

import React, { useState, useEffect } from 'react';

export interface ChannelLine {
  id: string;
  status: 'ringing' | 'active_ai' | 'warm_transfer_pending' | 'completed' | 'on_hold';
  caller_name: string;
  caller_phone: string;
  member_id?: string;
  duration_seconds: number;
  triage_category: string | null;
  triage_priority: string | null;
  action_directive: string | null;
  context_briefing_card: {
    callerSummary: string;
    identifiedNeed: string;
    suggestedResolution: string;
    transferredTo: string;
    timestampIso: string;
  } | null;
  transcript: Array<{
    speaker: 'customer' | 'ai_agent' | 'human_receptionist';
    text: string;
    timestampIso: string;
  }>;
}

export const MultiLineCallSwitchboard: React.FC = () => {
  const [lines, setLines] = useState<ChannelLine[]>([]);
  const [activeLineId, setActiveLineId] = useState<string>('line-1');
  const [loading, setLoading] = useState<boolean>(false);

  // Poll switchboard line states every 1500ms
  useEffect(() => {
    const fetchLines = async () => {
      try {
        const res = await fetch('/api/v1/voice/triage/lines');
        if (res.ok) {
          const data = await res.json();
          if (data.lines) {
            setLines(data.lines);
          }
        }
      } catch (err) {
        console.error('Failed to poll lines:', err);
      }
    };

    fetchLines();
    const interval = setInterval(fetchLines, 1500);
    return () => clearInterval(interval);
  }, []);

  const activeLine = lines.find((l) => l.id === activeLineId) || lines[0];

  const handleSimulateCall = async () => {
    setLoading(true);
    try {
      await fetch('/api/v1/voice/triage/simulate-call', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          caller_name: 'Amanda Cole',
          caller_phone: '+1 555-332-9011',
          message: 'Hi, I have severe throbbing pain in my lower left molar and I cannot chew.',
          line_override: activeLineId,
        }),
      });
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleWarmTransfer = async () => {
    if (!activeLineId) return;
    setLoading(true);
    try {
      await fetch('/api/v1/voice/triage/transfer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ line_id: activeLineId }),
      });
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleCompleteCall = async () => {
    if (!activeLineId) return;
    setLoading(true);
    try {
      await fetch('/api/v1/voice/triage/complete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ line_id: activeLineId }),
      });
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const formatTimer = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'active_ai':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 animate-pulse">Active AI Call</span>;
      case 'warm_transfer_pending':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-400 border border-amber-500/40 animate-bounce">Warm Transfer Pending</span>;
      case 'ringing':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-cyan-500/20 text-cyan-400 border border-cyan-500/40 animate-ping">Ringing</span>;
      case 'on_hold':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/20 text-rose-400 border border-rose-500/40">On Hold</span>;
      default:
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-400 border border-slate-700">Idle / Completed</span>;
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 text-slate-100 shadow-2xl space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping"></span>
            <h2 className="text-lg font-black tracking-tight text-white uppercase">4-Channel Multi-Line Concurrency Switchboard</h2>
          </div>
          <p className="text-xs text-slate-400">Zero-repetition warm transfers & sub-400ms conversational turn triage.</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleSimulateCall}
            disabled={loading}
            className="px-3.5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-black text-xs transition cursor-pointer shadow-lg shadow-emerald-600/20"
          >
            + Simulate Inbound Call
          </button>
          <button
            onClick={handleWarmTransfer}
            disabled={loading || activeLine?.status !== 'active_ai'}
            className="px-3.5 py-2 rounded-xl bg-amber-600 hover:bg-amber-500 text-slate-950 font-black text-xs transition cursor-pointer disabled:opacity-40"
          >
            Warm Transfer
          </button>
          <button
            onClick={handleCompleteCall}
            disabled={loading || activeLine?.status === 'completed'}
            className="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-rose-400 font-bold text-xs border border-rose-500/30 transition cursor-pointer disabled:opacity-40"
          >
            Hangup
          </button>
        </div>
      </div>

      {/* 4-Channel Line Navigation Tabs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {lines.map((l) => (
          <button
            key={l.id}
            onClick={() => setActiveLineId(l.id)}
            className={`p-3 rounded-xl border text-left transition cursor-pointer ${
              activeLineId === l.id
                ? 'bg-slate-800/90 border-emerald-500 shadow-lg shadow-emerald-500/10'
                : 'bg-slate-950/60 border-slate-800 hover:border-slate-700'
            }`}
          >
            <div className="flex items-center justify-between text-xs font-bold text-slate-300">
              <span className="uppercase">{l.id}</span>
              <span className="font-mono text-[11px] text-emerald-400">{formatTimer(l.duration_seconds || 0)}</span>
            </div>
            <div className="pt-2">{getStatusBadge(l.status)}</div>
            <div className="text-[11px] text-slate-400 truncate pt-1">{l.caller_name || 'Line Available'}</div>
          </button>
        ))}
      </div>

      {/* Active Line Inspection Panel */}
      {activeLine && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Column 1 & 2: Active Transcript & VAD */}
          <div className="lg:col-span-2 bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-emerald-400 uppercase tracking-wider">{activeLine.id} Live Audio Stream</span>
                {getStatusBadge(activeLine.status)}
              </div>
              <div className="text-xs text-slate-400 font-mono">
                Caller: <span className="text-white font-bold">{activeLine.caller_name || 'No active caller'}</span> ({activeLine.caller_phone || 'None'})
              </div>
            </div>

            {/* Transcript Feed */}
            <div className="h-64 overflow-y-auto space-y-2.5 pr-2">
              {activeLine.transcript && activeLine.transcript.length > 0 ? (
                activeLine.transcript.map((t, idx) => (
                  <div
                    key={idx}
                    className={`p-2.5 rounded-xl text-xs max-w-[85%] ${
                      t.speaker === 'ai_agent'
                        ? 'bg-slate-800 text-slate-200 mr-auto border border-slate-700/60'
                        : t.speaker === 'human_receptionist'
                        ? 'bg-amber-950/40 text-amber-200 ml-auto border border-amber-500/40'
                        : 'bg-emerald-950/40 text-emerald-200 ml-auto border border-emerald-500/40'
                    }`}
                  >
                    <div className="flex items-center justify-between text-[10px] opacity-75 pb-1">
                      <span className="font-bold uppercase">
                        {t.speaker === 'ai_agent' ? 'Emily (AI Receptionist)' : t.speaker === 'human_receptionist' ? 'Sarah (Front Desk)' : 'Caller'}
                      </span>
                      <span>{t.timestampIso?.slice(11, 19)}</span>
                    </div>
                    <p>{t.text}</p>
                  </div>
                ))
              ) : (
                <div className="h-full flex items-center justify-center text-xs text-slate-500">
                  Line idle. Inbound calls will automatically stream live audio and transcript here.
                </div>
              )}
            </div>
          </div>

          {/* Column 3: Zero-Repetition Warm Transfer Card */}
          <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <span className="text-xs font-black text-amber-400 uppercase tracking-wider">Zero-Repetition Handoff Card</span>
              <span className="text-[10px] text-slate-500">Whispered to Operator</span>
            </div>

            {activeLine.context_briefing_card ? (
              <div className="space-y-3 text-xs">
                <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 space-y-1">
                  <span className="text-[10px] font-bold text-slate-400 uppercase">Caller Summary</span>
                  <p className="text-white font-medium">{activeLine.context_briefing_card.callerSummary}</p>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 space-y-1">
                  <span className="text-[10px] font-bold text-slate-400 uppercase">Identified Need</span>
                  <p className="text-amber-200 font-medium">{activeLine.context_briefing_card.identifiedNeed}</p>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 space-y-1">
                  <span className="text-[10px] font-bold text-slate-400 uppercase">Suggested Resolution</span>
                  <p className="text-emerald-300 font-medium">{activeLine.context_briefing_card.suggestedResolution}</p>
                </div>
                <div className="text-[10px] text-slate-500 pt-1">
                  Transferred to: <span className="text-slate-300 font-bold">{activeLine.context_briefing_card.transferredTo}</span>
                </div>
              </div>
            ) : (
              <div className="h-48 flex flex-col items-center justify-center text-center text-xs text-slate-500 space-y-2">
                <i className="fa-solid fa-headset text-2xl text-slate-700"></i>
                <p>When warm transfer is triggered, the AI whispers the complete context card so the patient never repeats themselves.</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
