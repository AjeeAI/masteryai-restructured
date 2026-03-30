import React from 'react';
import { ArrowUpRight, Clock3, Download, MessageSquareMore, Printer, ShieldAlert, TrendingUp, UserRound, X } from 'lucide-react';

const formatDateTime = (value) => {
  if (!value) return 'Not available';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Not available';
  return date.toLocaleString();
};

const formatDuration = (seconds) => {
  const total = Number(seconds || 0);
  if (!total) return '0m';
  const minutes = Math.round(total / 60);
  const hours = Math.floor(minutes / 60);
  const remaining = minutes % 60;
  return hours > 0 ? `${hours}h ${remaining}m` : `${remaining}m`;
};

const isLikelyUuid = (value) => /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(String(value || '').trim());

const humanizeRefId = (refId, fallback = 'scope item') => {
  const value = String(refId || '').trim();
  if (!value) return fallback;
  const cleaned = value.startsWith('topic:') ? value.replace(/^topic:/i, '') : value;
  if (isLikelyUuid(cleaned)) return fallback;
  const token = value.split(':').pop()?.trim() || value;
  return token
    .replace(/-(\d+)$/, '')
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase()) || fallback;
};

const resolveRefLabel = (details) => {
  if (!details) return 'scope item';
  const explicit = String(details.ref_label || '').trim();
  if (explicit) return explicit;
  return humanizeRefId(details.ref_id, 'scope item');
};

const timelineTitle = (event) => {
  if (event.event_type === 'activity') return event.details?.activity_type?.replace(/_/g, ' ') || 'activity';
  if (event.event_type === 'mastery_update') return 'mastery update';
  if (event.event_type === 'tutor_session') return 'tutor session';
  return event.event_type?.replace(/_/g, ' ') || 'event';
};

const timelineSummary = (event) => {
  if (event.event_type === 'activity') {
    return `${resolveRefLabel(event.details)} • ${formatDuration(event.details?.duration_seconds)}`;
  }
  if (event.event_type === 'mastery_update') {
    return `${event.details?.source || 'unknown source'} • ${event.details?.updated_concepts || 0} concepts`;
  }
  if (event.event_type === 'tutor_session') {
    return `${event.details?.status || 'unknown status'} • ${formatDuration(event.details?.duration_seconds)}`;
  }
  return 'No extra details';
};

const TeacherStudentFocusDrawer = ({
  isOpen,
  onClose,
  student,
  conceptLabel,
  conceptTrend,
  isLoadingTrend,
  timeline,
  isLoading,
  onExport,
  isExporting,
  onOpenReport,
}) => {
  if (!isOpen || !student) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-950/35 backdrop-blur-sm">
      <div className="flex h-full w-full max-w-xl flex-col border-l border-slate-200 bg-white shadow-2xl">
        <div className="flex items-start justify-between border-b border-slate-200 px-6 py-5">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em] text-slate-600">
              <UserRound className="h-3.5 w-3.5" />
              Student focus
            </div>
            <h2 className="mt-3 text-2xl font-black text-slate-900">{student.student_name}</h2>
            <p className="mt-1 text-sm text-slate-500">
              {student.status.replace('_', ' ')} on {conceptLabel}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onOpenReport}
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-[11px] font-black uppercase tracking-[0.16em] text-slate-600 transition hover:bg-slate-100 hover:text-slate-800"
            >
              <Printer className="h-4 w-4" />
              Report
            </button>
            <button
              type="button"
              onClick={onExport}
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-[11px] font-black uppercase tracking-[0.16em] text-slate-600 transition hover:bg-slate-100 hover:text-slate-800"
            >
              <Download className="h-4 w-4" />
              {isExporting ? 'Preparing...' : 'Export'}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="rounded-xl border border-slate-200 p-2 text-slate-500 transition hover:bg-slate-100 hover:text-slate-700"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        <div className="flex-1 space-y-6 overflow-y-auto px-6 py-6">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Concept mastery</p>
              <p className="mt-2 text-2xl font-black text-slate-900">
                {student.concept_score == null ? 'Unassessed' : `${Math.round(Number(student.concept_score) * 100)}%`}
              </p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Overall mastery</p>
              <p className="mt-2 text-2xl font-black text-slate-900">
                {student.overall_mastery_score == null ? 'Unassessed' : `${Math.round(Number(student.overall_mastery_score) * 100)}%`}
              </p>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <h3 className="flex items-center gap-2 text-sm font-black uppercase tracking-[0.18em] text-slate-600">
              <TrendingUp className="h-4 w-4 text-emerald-500" />
              Concept trend
            </h3>
            {isLoadingTrend ? (
              <p className="mt-4 text-sm text-slate-500">Loading concept trend...</p>
            ) : !conceptTrend ? (
              <p className="mt-4 text-sm text-slate-500">No concept trend evidence is available for this student yet.</p>
            ) : (
              <>
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <div className="rounded-xl border border-slate-200 bg-white px-3 py-3">
                    <p className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-400">Net delta (30d)</p>
                    <p className={`mt-2 text-xl font-black ${Number(conceptTrend.net_delta_30d || 0) >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
                      {Number(conceptTrend.net_delta_30d || 0) >= 0 ? '+' : ''}{Number(conceptTrend.net_delta_30d || 0).toFixed(2)}
                    </p>
                  </div>
                  <div className="rounded-xl border border-slate-200 bg-white px-3 py-3">
                    <p className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-400">Evidence events</p>
                    <p className="mt-2 text-xl font-black text-slate-900">{conceptTrend.evidence_event_count}</p>
                  </div>
                </div>

                <div className="mt-4 space-y-3">
                  {conceptTrend.tracked_concepts?.map((item) => (
                    <div key={`${item.role}-${item.concept_id}`} className="rounded-xl border border-slate-200 bg-white p-3">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-bold text-slate-900">{item.concept_label}</p>
                          <p className="mt-1 text-[11px] font-black uppercase tracking-[0.16em] text-slate-400">{item.role === 'focus' ? 'Focus concept' : 'Prerequisite'}</p>
                        </div>
                        <span className="text-sm font-black text-slate-800">
                          {item.current_score == null ? 'Unassessed' : `${Math.round(Number(item.current_score) * 100)}%`}
                        </span>
                      </div>
                      <p className="mt-2 text-[11px] text-slate-500">Last evaluated: {formatDateTime(item.last_evaluated_at)}</p>
                    </div>
                  ))}
                </div>

                {conceptTrend.recent_events?.length ? (
                  <div className="mt-4 space-y-2">
                    {conceptTrend.recent_events.map((event, index) => (
                      <div key={`${event.concept_id}-${event.occurred_at}-${index}`} className="rounded-xl border border-slate-200 bg-white px-3 py-3">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="text-sm font-semibold text-slate-900">{event.concept_label}</p>
                            <p className="mt-1 text-[11px] font-medium text-slate-500">{event.source}</p>
                          </div>
                          <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.16em] ${
                            Number(event.delta || 0) >= 0 ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'
                          }`}>
                            <ArrowUpRight className={`h-3 w-3 ${Number(event.delta || 0) >= 0 ? '' : 'rotate-90'}`} />
                            {Number(event.delta || 0) >= 0 ? '+' : ''}{Number(event.delta || 0).toFixed(2)}
                          </span>
                        </div>
                        <p className="mt-2 text-[11px] text-slate-500">{formatDateTime(event.occurred_at)}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="mt-4 text-sm text-slate-500">No recent mastery deltas were recorded for this concept path in the selected window.</p>
                )}
              </>
            )}
          </div>

          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <h3 className="flex items-center gap-2 text-sm font-black uppercase tracking-[0.18em] text-slate-600">
              <ShieldAlert className="h-4 w-4 text-amber-500" />
              Blocking prerequisites
            </h3>
            {student.blocking_prerequisite_labels?.length ? (
              <div className="mt-3 flex flex-wrap gap-2">
                {student.blocking_prerequisite_labels.map((label) => (
                  <span key={label} className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-amber-700 shadow-sm">
                    {label}
                  </span>
                ))}
              </div>
            ) : (
              <p className="mt-3 text-sm text-slate-500">No blocking prerequisite is currently holding this student back on this concept.</p>
            )}
            <p className="mt-4 text-sm leading-6 text-slate-600">{student.recommended_action}</p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <h3 className="flex items-center gap-2 text-sm font-black uppercase tracking-[0.18em] text-slate-600">
              <Clock3 className="h-4 w-4 text-indigo-500" />
              Recent activity
            </h3>
            <div className="mt-3 flex flex-wrap gap-3 text-xs font-semibold text-slate-600">
              <span className="rounded-full bg-white px-3 py-1 shadow-sm">{student.recent_activity_count_7d} activities in 7d</span>
              <span className="rounded-full bg-white px-3 py-1 shadow-sm">{formatDuration(student.recent_study_time_seconds_7d)} study time</span>
              <span className="rounded-full bg-white px-3 py-1 shadow-sm">Last evaluated: {formatDateTime(student.last_evaluated_at)}</span>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <h3 className="flex items-center gap-2 text-sm font-black uppercase tracking-[0.18em] text-slate-600">
              <MessageSquareMore className="h-4 w-4 text-emerald-500" />
              Timeline
            </h3>
            {isLoading ? (
              <p className="mt-4 text-sm text-slate-500">Loading student timeline...</p>
            ) : !timeline?.length ? (
              <p className="mt-4 text-sm text-slate-500">No timeline events are available for this student yet.</p>
            ) : (
              <div className="mt-4 space-y-3">
                {timeline.map((event, index) => (
                  <div key={`${event.event_type}-${event.occurred_at}-${index}`} className="rounded-2xl border border-slate-200 bg-white p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-bold capitalize text-slate-900">{timelineTitle(event)}</p>
                        <p className="mt-1 text-xs text-slate-500">{timelineSummary(event)}</p>
                      </div>
                      <span className="text-[11px] font-semibold text-slate-400">{formatDateTime(event.occurred_at)}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default TeacherStudentFocusDrawer;
