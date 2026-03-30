import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useLocation } from 'react-router-dom';
import {
  Activity,
  AlertTriangle,
  Bot,
  BrainCircuit,
  ChevronDown,
  ChevronUp,
  GitBranch,
  LoaderCircle,
  RefreshCcw,
  Server,
  ShieldCheck,
  Workflow,
  X,
} from 'lucide-react';

import { useAuth } from '../context/AuthContext';
import { useUser } from '../context/UserContext';
import { AI_CORE_URL, API_URL } from '../config/runtime';
import { readLatestGraphIntervention } from '../services/graphIntervention';
import { resolveStudentId } from '../utils/sessionIdentity';

const REFRESH_INTERVAL_MS = 15000;
const OPEN_STORAGE_KEY = 'mastery_runtime_dock_open';

const STATUS_STYLES = {
  ok: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  configured: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  degraded: 'border-amber-200 bg-amber-50 text-amber-700',
  error: 'border-rose-200 bg-rose-50 text-rose-700',
  disabled: 'border-slate-200 bg-slate-100 text-slate-600',
  not_configured: 'border-slate-200 bg-slate-100 text-slate-600',
};

const shortText = (value, fallback = 'n/a') => {
  const text = String(value || '').trim();
  return text || fallback;
};

const formatDuration = (value) => {
  const amount = Number(value);
  if (!Number.isFinite(amount)) return 'n/a';
  return `${amount.toFixed(amount >= 100 ? 0 : 1)} ms`;
};

const formatUpdatedAt = (value) => {
  if (!value) return 'n/a';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'n/a';
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
};

const sortEvents = (runtimeTelemetry, limit = 4) => {
  const events = Object.entries(runtimeTelemetry?.events || {});
  return events
    .sort((left, right) => Number(right[1]?.last_duration_ms || 0) - Number(left[1]?.last_duration_ms || 0))
    .slice(0, limit);
};

const resolveStatusTone = (status) => STATUS_STYLES[status] || 'border-slate-200 bg-slate-100 text-slate-600';

const readOpenState = () => {
  if (typeof window === 'undefined') return false;
  return window.localStorage.getItem(OPEN_STORAGE_KEY) === 'true';
};

const writeOpenState = (value) => {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(OPEN_STORAGE_KEY, value ? 'true' : 'false');
};

const shouldAutoEnable = (search = '', pathname = '') => {
  if (typeof window === 'undefined') return false;
  const params = new URLSearchParams(search || window.location.search || '');
  if (params.get('runtime') === '1') return true;
  return /^\/(teacher|presentation|presentation-hub|teacher-briefing|teacher-student-report|concept-analytics|demo-mode|graph-briefing)/.test(pathname || window.location.pathname || '');
};

const fetchHealth = async (url, options = {}) => {
  if (!url) {
    return { status: 'not_configured', detail: 'URL not configured', payload: null };
  }
  try {
    const response = await fetch(url, options);
    if (!response.ok) {
      return { status: 'error', detail: `HTTP ${response.status}`, payload: null };
    }
    const payload = await response.json();
    return { status: shortText(payload?.status, 'ok').toLowerCase(), detail: '', payload };
  } catch (error) {
    return { status: 'error', detail: error?.message || 'Request failed', payload: null };
  }
};

function StatusPill({ status, label }) {
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.18em] ${resolveStatusTone(status)}`}>
      {label}
    </span>
  );
}

function MetricCard({ label, value, tone = 'slate' }) {
  const toneMap = {
    slate: 'border-slate-200 bg-slate-50 text-slate-700',
    indigo: 'border-indigo-200 bg-indigo-50 text-indigo-700',
    emerald: 'border-emerald-200 bg-emerald-50 text-emerald-700',
    amber: 'border-amber-200 bg-amber-50 text-amber-700',
  };

  return (
    <div className={`rounded-2xl border px-3 py-3 ${toneMap[tone] || toneMap.slate}`}>
      <p className="text-[10px] font-black uppercase tracking-[0.18em] opacity-70">{label}</p>
      <p className="mt-1 text-sm font-bold">{value}</p>
    </div>
  );
}

function EventList({ title, icon: Icon, telemetry, emptyText }) {
  const events = useMemo(() => sortEvents(telemetry), [telemetry]);

  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-4">
      <div className="flex items-center gap-2 text-slate-700">
        <Icon size={16} />
        <h3 className="text-[11px] font-black uppercase tracking-[0.22em]">{title}</h3>
      </div>
      {events.length === 0 ? (
        <p className="mt-3 text-xs leading-6 text-slate-500">{emptyText}</p>
      ) : (
        <div className="mt-3 space-y-2">
          {events.map(([name, stats]) => (
            <div key={name} className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-xs font-bold text-slate-800">{name}</p>
                  <p className="mt-1 text-[11px] text-slate-500">
                    avg {formatDuration(stats.avg_duration_ms)} / last {formatDuration(stats.last_duration_ms)}
                  </p>
                </div>
                <span className="rounded-full border border-slate-200 bg-white px-2 py-1 text-[10px] font-black uppercase tracking-[0.15em] text-slate-500">
                  x{stats.count}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

export default function RuntimeDebugDock() {
  const { token } = useAuth();
  const { studentData, userData } = useUser();
  const location = useLocation();
  const studentId = resolveStudentId(studentData, userData);
  const [isManuallyEnabled, setIsManuallyEnabled] = useState(false);
  const isEnabled = shouldAutoEnable(location.search, location.pathname) || isManuallyEnabled;
  const [isOpen, setIsOpen] = useState(() => readOpenState());
  const [isLoading, setIsLoading] = useState(false);
  const [backendState, setBackendState] = useState({ status: 'not_configured', detail: '', payload: null });
  const [aiCoreState, setAiCoreState] = useState({ status: 'not_configured', detail: '', payload: null });
  const [refreshedAt, setRefreshedAt] = useState('');

  const latestIntervention = studentId ? readLatestGraphIntervention(studentId) : null;

  const toggleOpen = useCallback(() => {
    setIsOpen((current) => {
      const next = !current;
      writeOpenState(next);
      return next;
    });
  }, []);

  const hideDock = useCallback(() => {
    setIsManuallyEnabled(false);
    writeOpenState(false);
    setIsOpen(false);
  }, []);

  const refresh = useCallback(async () => {
    if (!token) return;
    setIsLoading(true);
    const [backendResult, aiCoreResult] = await Promise.all([
      fetchHealth(`${API_URL}/system/health`, {
        headers: { Authorization: `Bearer ${token}` },
      }),
      fetchHealth(AI_CORE_URL ? `${AI_CORE_URL.replace(/\/+$/, '')}/health` : ''),
    ]);
    setBackendState(backendResult);
    setAiCoreState(aiCoreResult);
    setRefreshedAt(new Date().toISOString());
    setIsLoading(false);
  }, [token]);

  useEffect(() => {
    if (!token || !isOpen || !isEnabled) return undefined;
    const initialTimer = window.setTimeout(() => {
      void refresh();
    }, 0);
    const interval = window.setInterval(refresh, REFRESH_INTERVAL_MS);
    return () => {
      window.clearInterval(interval);
      window.clearTimeout(initialTimer);
    };
  }, [isEnabled, isOpen, refresh, token]);

  useEffect(() => {
    const onKeyDown = (event) => {
      if (event.shiftKey && event.key.toLowerCase() === 'd') {
        event.preventDefault();
        if (!isEnabled) {
          setIsManuallyEnabled(true);
          writeOpenState(true);
          setIsOpen(true);
          return;
        }
        toggleOpen();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [isEnabled, toggleOpen]);

  if (!token || !isEnabled) return null;

  const backendChecks = backendState.payload?.checks || {};
  const backendRuntime = backendState.payload?.runtime || {};
  const backendTelemetry = backendRuntime.telemetry || {};
  const backendCaches = backendRuntime.caches || {};
  const prewarmQueue = backendChecks.prewarm_queue || {};
  const recommendation = latestIntervention?.payload?.recommendation_story || null;
  const nextStep = latestIntervention?.payload?.next_step || null;
  const recentEvidence = latestIntervention?.payload?.recent_evidence || null;

  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-[90] flex flex-col items-end gap-3">
      <button
        type="button"
        onClick={toggleOpen}
        className="pointer-events-auto inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-950 px-4 py-3 text-[11px] font-black uppercase tracking-[0.16em] text-white shadow-xl shadow-slate-950/20"
      >
        <Activity size={15} />
        Runtime
        {isOpen ? <ChevronDown size={15} /> : <ChevronUp size={15} />}
      </button>

      {isOpen && (
        <div
          className="pointer-events-auto flex w-[min(88vw,380px)] flex-col overflow-hidden rounded-[1.75rem] border border-slate-200 bg-white shadow-2xl shadow-slate-950/15"
          style={{ maxHeight: 'min(72dvh, 620px)' }}
        >
          <div className="sticky top-0 z-10 border-b border-slate-100 bg-[radial-gradient(circle_at_top_left,_rgba(99,102,241,0.16),_transparent_42%),linear-gradient(135deg,#ffffff,_#f8fafc)] px-4 py-3 backdrop-blur">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-white px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em] text-indigo-700">
                  <GitBranch size={13} />
                  Runtime
                </div>
                <h2 className="mt-2 text-base font-black tracking-tight text-slate-950">System runtime</h2>
                <p className="mt-1 text-xs leading-6 text-slate-500">
                  {location.pathname} - {refreshedAt ? formatUpdatedAt(refreshedAt) : 'not refreshed'}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={refresh}
                  disabled={isLoading}
                  className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
                >
                  {isLoading ? <LoaderCircle size={14} className="animate-spin" /> : <RefreshCcw size={14} />}
                  Refresh
                </button>
                <button
                  type="button"
                  onClick={hideDock}
                  className="inline-flex h-10 w-10 items-center justify-center rounded-2xl border border-slate-200 bg-white text-slate-500 hover:bg-slate-50"
                  aria-label="Hide runtime dock"
                >
                  <X size={15} />
                </button>
              </div>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <StatusPill status={backendState.status} label={`Backend ${shortText(backendState.status)}`} />
              <StatusPill status={aiCoreState.status} label={`AI Core ${shortText(aiCoreState.status)}`} />
              <StatusPill status={prewarmQueue.status || 'not_configured'} label={`Queue ${shortText(prewarmQueue.status, 'n/a')}`} />
            </div>
          </div>

          <div className="space-y-4 overflow-y-auto p-4">
            <section className="rounded-3xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-center gap-2 text-slate-700">
                <BrainCircuit size={16} />
                <h3 className="text-[11px] font-black uppercase tracking-[0.22em]">Latest graph signal</h3>
              </div>
              {latestIntervention?.payload ? (
                <div className="mt-3 space-y-3">
                  <p className="text-sm font-bold text-slate-900">
                    {recommendation?.headline || nextStep?.recommended_topic_title || nextStep?.recommended_concept_label || 'Latest graph step'}
                  </p>
                  <p className="text-xs leading-6 text-slate-600">
                    {recommendation?.supporting_reason || recentEvidence?.summary || 'Graph signal available.'}
                  </p>
                  <div className="grid gap-2 sm:grid-cols-2">
                    <MetricCard label="Subject" value={shortText(latestIntervention.subject)} tone="indigo" />
                    <MetricCard label="Focus concept" value={shortText(recentEvidence?.strongest_drop_concept_label || recentEvidence?.strongest_gain_concept_label)} tone="amber" />
                    <MetricCard label="Next topic" value={shortText(nextStep?.recommended_topic_title || nextStep?.recommended_concept_label)} tone="emerald" />
                    <MetricCard label="Updated" value={formatUpdatedAt(latestIntervention.updated_at)} />
                  </div>
                </div>
              ) : (
                <div className="mt-3 rounded-2xl border border-slate-200 bg-white p-3 text-xs leading-6 text-slate-500">
                  No persisted graph intervention yet for this student scope.
                </div>
              )}
            </section>

            <section className="rounded-3xl border border-slate-200 bg-white p-4">
              <div className="flex items-center gap-2 text-slate-700">
                <Server size={16} />
                <h3 className="text-[11px] font-black uppercase tracking-[0.22em]">Backend runtime</h3>
              </div>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                <MetricCard label="Queued jobs" value={String(prewarmQueue.counts?.queued ?? 0)} tone="indigo" />
                <MetricCard label="Completed jobs" value={String(prewarmQueue.counts?.completed ?? 0)} tone="emerald" />
                <MetricCard label="Worker alive" value={prewarmQueue.worker_alive ? 'Yes' : 'No'} tone={prewarmQueue.worker_alive ? 'emerald' : 'amber'} />
                <MetricCard label="Events tracked" value={String(backendTelemetry.event_count ?? 0)} />
              </div>
              <div className="mt-3 grid gap-2">
                <MetricCard label="Lesson snapshots" value={String(backendCaches.lesson_experience?.topic_snapshot_cache?.entries ?? 0)} />
                <MetricCard label="Lesson bootstraps" value={String(backendCaches.lesson_experience?.bootstrap_cache?.entries ?? 0)} />
                <MetricCard label="Cockpit cache" value={String(backendCaches.lesson_cockpit?.bootstrap_cache?.entries ?? 0)} />
                <MetricCard label="Course cache" value={String(backendCaches.course_experience?.bootstrap_cache?.entries ?? 0)} />
                <MetricCard label="Dashboard cache" value={String(backendCaches.dashboard_experience?.bootstrap_cache?.entries ?? 0)} />
              </div>
              {backendState.detail && (
                <div className="mt-3 rounded-2xl border border-rose-200 bg-rose-50 p-3 text-xs leading-6 text-rose-700">
                  {backendState.detail}
                </div>
              )}
            </section>

            <EventList
              title="Backend hot paths"
              icon={Workflow}
              telemetry={backendTelemetry}
              emptyText="No backend timing events captured yet in this process."
            />

            <section className="rounded-3xl border border-slate-200 bg-white p-4">
              <div className="flex items-center gap-2 text-slate-700">
                <Bot size={16} />
                <h3 className="text-[11px] font-black uppercase tracking-[0.22em]">AI core runtime</h3>
              </div>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                <MetricCard label="Status" value={shortText(aiCoreState.status)} tone={aiCoreState.status === 'ok' ? 'emerald' : 'amber'} />
                <MetricCard label="Events tracked" value={String(aiCoreState.payload?.runtime?.telemetry?.event_count ?? 0)} />
                <MetricCard label="Internal key" value={shortText(aiCoreState.payload?.checks?.internal_service_key)} />
                <MetricCard label="Backend RAG URL" value={shortText(aiCoreState.payload?.checks?.backend_internal_rag_url)} />
              </div>
              {aiCoreState.detail && (
                <div className="mt-3 rounded-2xl border border-amber-200 bg-amber-50 p-3 text-xs leading-6 text-amber-700">
                  <div className="mb-1 flex items-center gap-2 font-bold">
                    <AlertTriangle size={14} />
                    AI core detail
                  </div>
                  {aiCoreState.detail}
                </div>
              )}
              {!AI_CORE_URL && (
                <div className="mt-3 rounded-2xl border border-slate-200 bg-slate-50 p-3 text-xs leading-6 text-slate-600">
                  Set <code className="font-mono">VITE_AI_CORE_URL</code> or <code className="font-mono">localStorage.mastery_ai_core_url</code> to inspect live ai-core runtime here.
                </div>
              )}
            </section>

            <EventList
              title="AI core hot paths"
              icon={ShieldCheck}
              telemetry={aiCoreState.payload?.runtime?.telemetry}
              emptyText="No ai-core timing events captured yet in this process."
            />
          </div>
        </div>
      )}
    </div>
  );
}

