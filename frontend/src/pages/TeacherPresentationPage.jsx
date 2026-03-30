import React, { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, ArrowLeft, ArrowRight, BrainCircuit, Clipboard, Download, Loader2, Presentation, Printer, Route, Sparkles, Target, TrendingUp, Users } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { API_URL } from '../config/runtime';
import PresentationCueCard from '../components/PresentationCueCard';
import TeacherClassGraph from '../components/teacher/TeacherClassGraph';

const formatDateTime = (value) => {
  if (!value) return 'Not available';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Not available';
  return date.toLocaleString();
};

const percent = (value) => (value == null ? 'Unassessed' : `${Math.round(Number(value) * 100)}%`);

const TeacherPresentationPage = () => {
  const { classId } = useParams();
  const { token } = useAuth();
  const apiUrl = API_URL;
  const [presentation, setPresentation] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [copyState, setCopyState] = useState('idle');

  useEffect(() => {
    const fetchPresentation = async () => {
      if (!token || !classId) {
        setIsLoading(false);
        setError('Presentation mode requires an authenticated teacher session.');
        return;
      }
      try {
        setIsLoading(true);
        setError('');
        const response = await fetch(`${apiUrl}/teachers/classes/${classId}/presentation`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!response.ok) {
          const detail = await response.json().catch(() => null);
          throw new Error(detail?.detail || 'Failed to load teacher presentation view.');
        }
        const data = await response.json();
        setPresentation(data || null);
      } catch (err) {
        setPresentation(null);
        setError(err.message || 'Teacher presentation view is unavailable right now.');
      } finally {
        setIsLoading(false);
      }
    };

    fetchPresentation();
  }, [apiUrl, classId, token]);

  const handleCopy = async () => {
    if (!presentation?.briefing?.markdown) return;
    try {
      await navigator.clipboard.writeText(presentation.briefing.markdown);
      setCopyState('success');
      window.setTimeout(() => setCopyState('idle'), 1800);
    } catch {
      setCopyState('error');
      window.setTimeout(() => setCopyState('idle'), 1800);
    }
  };

  const handleDownload = () => {
    if (!presentation?.briefing?.markdown) return;
    const blob = new Blob([presentation.briefing.markdown], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = presentation.briefing.file_name || 'teacher-presentation.md';
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const topQueueItems = useMemo(
    () => (Array.isArray(presentation?.intervention_queue?.items) ? presentation.intervention_queue.items.slice(0, 4) : []),
    [presentation?.intervention_queue?.items],
  );

  const presentationSignalCards = useMemo(() => {
    if (!presentation) return [];
    return [
      {
        id: 'blockers',
        label: 'Blocked concepts',
        value: presentation.graph_summary?.metrics?.blocked_concepts ?? 0,
        tone: 'text-amber-600',
        icon: AlertTriangle,
      },
      {
        id: 'ready',
        label: 'Ready to push',
        value: Array.isArray(presentation.graph_summary?.ready_to_push) ? presentation.graph_summary.ready_to_push.length : 0,
        tone: 'text-emerald-600',
        icon: TrendingUp,
      },
      {
        id: 'active',
        label: 'Active students 7d',
        value: presentation.dashboard?.active_students_7d ?? 0,
        tone: 'text-indigo-600',
        icon: Users,
      },
      {
        id: 'targeted',
        label: 'Student-targeted queue',
        value: presentation.intervention_queue?.student_targeted_items ?? 0,
        tone: 'text-slate-900',
        icon: Target,
      },
    ];
  }, [presentation]);

  const presentationTalkTrack = useMemo(() => {
    if (!presentation) return [];
    return [
      {
        id: 'signal',
        title: 'Start with the graph signal',
        detail: presentation.graph_summary?.graph_signal?.headline || 'Graph signal unavailable.',
        support: presentation.graph_summary?.graph_signal?.supporting_reason || 'No supporting reason available yet.',
      },
      {
        id: 'repair',
        title: 'Turn it into a repair plan',
        detail: presentation.next_cluster_plan?.headline || 'No cluster plan headline yet.',
        support: presentation.next_cluster_plan?.rationale || 'No cluster rationale available yet.',
      },
      {
        id: 'evidence',
        title: 'Close with outcomes',
        detail: `${presentation.intervention_outcomes?.improving_interventions ?? 0} interventions and ${presentation.assignment_outcomes?.improving_assignments ?? 0} assignments are already showing improvement.`,
        support: 'That gives the teacher story real evidence instead of a static dashboard.',
      },
    ];
  }, [presentation]);

  return (
    <main className="min-h-screen bg-slate-50 p-8 print:bg-white print:p-0">
      <div className="mx-auto max-w-7xl space-y-6">
        <PresentationCueCard
          stepId="teacher-presentation"
          nextClickLabel="Intervention queue"
          speakerNotes={[
            'Now switch the story from the student path to the teacher response layer.',
            'Start with the graph signal, then point to the intervention queue and the outcome snapshot.',
            'Use the next cluster plan to explain how the graph becomes a practical teaching plan.',
          ]}
        />

        <div className="flex flex-col gap-4 rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm print:hidden">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full bg-indigo-50 px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em] text-indigo-700">
                <Presentation className="h-3.5 w-3.5" />
                Presentation mode
              </div>
              <h1 className="mt-3 text-2xl font-black text-slate-900">Teacher presentation view</h1>
              <p className="mt-1 text-sm text-slate-500">
                Clean demo-ready summary of graph signal, intervention queue, cluster plan, and outcomes.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Link
                to="/teacher/analytics"
                className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-black uppercase tracking-[0.16em] text-slate-700 transition hover:bg-slate-100"
              >
                <ArrowLeft className="h-4 w-4" />
                Back
              </Link>
              <button
                type="button"
                onClick={handleCopy}
                disabled={!presentation?.briefing?.markdown}
                className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-black uppercase tracking-[0.16em] text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Clipboard className="h-4 w-4" />
                {copyState === 'success' ? 'Copied' : copyState === 'error' ? 'Copy failed' : 'Copy'}
              </button>
              <button
                type="button"
                onClick={handleDownload}
                disabled={!presentation?.briefing?.markdown}
                className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-black uppercase tracking-[0.16em] text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Download className="h-4 w-4" />
                Download
              </button>
              <button
                type="button"
                onClick={() => window.print()}
                disabled={!presentation}
                className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2 text-xs font-black uppercase tracking-[0.16em] text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Printer className="h-4 w-4" />
                Print
              </button>
            </div>
          </div>
        </div>

        {isLoading ? (
          <div className="flex min-h-[320px] flex-col items-center justify-center rounded-[28px] border border-slate-200 bg-white text-slate-400 shadow-sm">
            <Loader2 className="mb-3 h-10 w-10 animate-spin text-indigo-500" />
            <p className="text-sm font-semibold">Preparing presentation view...</p>
          </div>
        ) : error ? (
          <div className="rounded-[28px] border border-rose-200 bg-rose-50 p-6 text-sm font-semibold text-rose-700">
            {error}
          </div>
        ) : !presentation ? (
          <div className="rounded-[28px] border border-slate-200 bg-white p-6 text-sm font-semibold text-slate-500 shadow-sm">
            No presentation data is available for this class yet.
          </div>
        ) : (
          <>
            <section className="rounded-[28px] border border-slate-200 bg-[radial-gradient(circle_at_top_left,_rgba(99,102,241,0.14),_transparent_42%),linear-gradient(135deg,#ffffff,_#eef2ff)] p-8 shadow-sm print:shadow-none">
              <p className="text-[11px] font-black uppercase tracking-[0.2em] text-indigo-500">Live class story</p>
              <h2 className="mt-3 text-3xl font-black text-slate-900">{presentation.class_name}</h2>
              <p className="mt-2 text-sm leading-7 text-slate-600">
                {presentation.subject.toUpperCase()} {presentation.sss_level} Term {presentation.term} • Generated {formatDateTime(presentation.generated_at)}
              </p>
              <div className="mt-6 grid gap-4 md:grid-cols-4">
                <div className="rounded-2xl border border-slate-200 bg-white p-4">
                  <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Students</p>
                  <p className="mt-2 text-2xl font-black text-slate-900">{presentation.dashboard.total_students}</p>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-white p-4">
                  <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Average mastery</p>
                  <p className="mt-2 text-2xl font-black text-slate-900">{percent(presentation.dashboard.avg_mastery_score)}</p>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-white p-4">
                  <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Urgent queue items</p>
                  <p className="mt-2 text-2xl font-black text-rose-600">{presentation.intervention_queue.urgent_items}</p>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-white p-4">
                  <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Planning status</p>
                  <p className="mt-2 text-sm font-black text-slate-900">{presentation.next_cluster_plan.plan_status.replace('_', ' ')}</p>
                </div>
              </div>
            </section>

            <section className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
              <div className="rounded-[28px] border border-slate-900 bg-[radial-gradient(circle_at_top_left,_rgba(99,102,241,0.35),_transparent_38%),linear-gradient(135deg,#0f172a,#111827)] p-6 text-white shadow-sm print:border-slate-200 print:bg-white print:text-slate-900">
                <div className="flex items-center gap-2 text-indigo-200 print:text-indigo-600">
                  <BrainCircuit className="h-4 w-4" />
                  <p className="text-[10px] font-black uppercase tracking-[0.18em]">Presentation anchor</p>
                </div>
                <h3 className="mt-4 text-2xl font-black">{presentation.graph_summary.graph_signal.headline}</h3>
                <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-200 print:text-slate-600">
                  {presentation.graph_summary.graph_signal.supporting_reason}
                </p>
                <div className="mt-4 flex flex-wrap gap-2">
                  {presentation.graph_summary.graph_signal.focus_concept_label && (
                    <span className="rounded-full border border-white/15 bg-white/10 px-3 py-1 text-[11px] font-bold text-white print:border-indigo-200 print:bg-indigo-50 print:text-indigo-700">
                      Focus: {presentation.graph_summary.graph_signal.focus_concept_label}
                    </span>
                  )}
                  {presentation.graph_summary.graph_signal.blocking_prerequisite_label && (
                    <span className="rounded-full border border-white/15 bg-white/10 px-3 py-1 text-[11px] font-bold text-white print:border-amber-200 print:bg-amber-50 print:text-amber-800">
                      Blocker: {presentation.graph_summary.graph_signal.blocking_prerequisite_label}
                    </span>
                  )}
                  <span className="rounded-full border border-white/15 bg-white/10 px-3 py-1 text-[11px] font-bold text-white print:border-emerald-200 print:bg-emerald-50 print:text-emerald-700">
                    Action: {presentation.graph_summary.graph_signal.recommended_action}
                  </span>
                </div>
                <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  {presentationSignalCards.map((card) => {
                    const Icon = card.icon;
                    return (
                      <div key={card.id} className="rounded-2xl border border-white/10 bg-white/10 p-4 backdrop-blur print:border-slate-200 print:bg-white">
                        <div className="flex items-center gap-2 text-slate-200 print:text-slate-500">
                          <Icon className="h-4 w-4" />
                          <p className="text-[10px] font-black uppercase tracking-[0.18em]">{card.label}</p>
                        </div>
                        <p className={`mt-3 text-2xl font-black ${card.tone}`}>{card.value}</p>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm print:shadow-none">
                <div className="flex items-center gap-2 text-slate-700">
                  <Route className="h-4 w-4 text-indigo-500" />
                  <h3 className="text-sm font-black uppercase tracking-[0.18em] text-slate-500">Presenter talk track</h3>
                </div>
                <div className="mt-5 space-y-3">
                  {presentationTalkTrack.map((item, index) => (
                    <div key={item.id} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-black text-slate-900">{item.title}</p>
                        <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[10px] font-black uppercase tracking-[0.16em] text-slate-500">
                          Step {index + 1}
                        </span>
                      </div>
                      <p className="mt-2 text-sm font-semibold leading-6 text-slate-800">{item.detail}</p>
                      <p className="mt-2 text-xs leading-6 text-slate-500">{item.support}</p>
                    </div>
                  ))}
                </div>
                <div className="mt-4 rounded-2xl border border-indigo-200 bg-indigo-50 p-4 text-sm text-indigo-900">
                  <div className="flex items-center gap-2">
                    <ArrowRight className="h-4 w-4" />
                    <p className="text-[10px] font-black uppercase tracking-[0.18em] text-indigo-600">Why this lands</p>
                  </div>
                  <p className="mt-2 leading-7">
                    The same graph signal that shapes the student lesson becomes a teacher queue, a class plan, and measurable outcomes in one flow.
                  </p>
                </div>
              </div>
            </section>

            <section className="grid gap-6 xl:grid-cols-[1.3fr_0.9fr]">
              <div className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm print:shadow-none">
                <div className="mb-5 flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-indigo-500" />
                  <h3 className="text-sm font-black uppercase tracking-[0.18em] text-slate-500">Graph signal</h3>
                </div>
                <p className="text-2xl font-black text-slate-900">{presentation.graph_summary.graph_signal.headline}</p>
                <p className="mt-3 text-sm leading-7 text-slate-600">{presentation.graph_summary.graph_signal.supporting_reason}</p>
                <div className="mt-6">
                  <TeacherClassGraph
                    graphSummary={presentation.graph_summary}
                    selectedConceptId={presentation.graph_summary.weakest_blockers?.[0]?.concept_id || presentation.graph_summary.nodes?.[0]?.concept_id || ''}
                    onSelectNode={() => {}}
                  />
                </div>
              </div>

              <div className="space-y-6">
                <div className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm print:shadow-none">
                  <h3 className="text-sm font-black uppercase tracking-[0.18em] text-slate-500">Intervention queue</h3>
                  <div className="mt-4 space-y-3">
                    {topQueueItems.map((item) => (
                      <div key={item.queue_id} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                        <div className="flex items-center justify-between gap-3">
                          <p className="text-sm font-bold text-slate-900">{item.headline}</p>
                          <span className={`rounded-full px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.16em] ${
                            item.priority === 'urgent'
                              ? 'bg-rose-100 text-rose-700'
                              : item.priority === 'high'
                                ? 'bg-amber-100 text-amber-700'
                                : 'bg-slate-200 text-slate-700'
                          }`}>
                            {item.priority}
                          </span>
                        </div>
                        <p className="mt-2 text-xs leading-6 text-slate-600">{item.rationale}</p>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm print:shadow-none">
                  <h3 className="text-sm font-black uppercase tracking-[0.18em] text-slate-500">Outcome snapshot</h3>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2">
                    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                      <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Assignments improving</p>
                      <p className="mt-2 text-2xl font-black text-emerald-600">{presentation.assignment_outcomes.improving_assignments}</p>
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                      <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Interventions improving</p>
                      <p className="mt-2 text-2xl font-black text-indigo-600">{presentation.intervention_outcomes.improving_interventions}</p>
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                      <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Assignments no evidence</p>
                      <p className="mt-2 text-2xl font-black text-amber-600">{presentation.assignment_outcomes.no_evidence_assignments}</p>
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                      <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Interventions declining</p>
                      <p className="mt-2 text-2xl font-black text-rose-600">{presentation.intervention_outcomes.declining_interventions}</p>
                    </div>
                  </div>
                </div>
              </div>
            </section>

            <section className="grid gap-6 lg:grid-cols-2">
              <div className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm print:shadow-none">
                <h3 className="text-sm font-black uppercase tracking-[0.18em] text-slate-500">Next cluster plan</h3>
                <p className="mt-4 text-xl font-black text-slate-900">{presentation.next_cluster_plan.headline}</p>
                <p className="mt-2 text-sm leading-7 text-slate-600">{presentation.next_cluster_plan.rationale}</p>
                <div className="mt-5 grid gap-4 xl:grid-cols-3">
                  <div className="space-y-3">
                    <p className="text-[10px] font-black uppercase tracking-[0.18em] text-amber-600">Repair first</p>
                    {(presentation.next_cluster_plan.repair_first || []).slice(0, 3).map((item) => (
                      <div key={item.concept_id} className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
                        <p className="text-sm font-bold text-slate-900">{item.concept_label}</p>
                        <p className="mt-1 text-xs text-slate-600">{item.recommended_action}</p>
                      </div>
                    ))}
                  </div>
                  <div className="space-y-3">
                    <p className="text-[10px] font-black uppercase tracking-[0.18em] text-emerald-600">Teach next</p>
                    {(presentation.next_cluster_plan.teach_next || []).slice(0, 3).map((item) => (
                      <div key={item.concept_id} className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4">
                        <p className="text-sm font-bold text-slate-900">{item.concept_label}</p>
                        <p className="mt-1 text-xs text-slate-600">{item.recommended_action}</p>
                      </div>
                    ))}
                  </div>
                  <div className="space-y-3">
                    <p className="text-[10px] font-black uppercase tracking-[0.18em] text-indigo-600">Watchlist</p>
                    {(presentation.next_cluster_plan.watchlist || []).slice(0, 3).map((item) => (
                      <div key={item.concept_id} className="rounded-2xl border border-indigo-200 bg-indigo-50 p-4">
                        <p className="text-sm font-bold text-slate-900">{item.concept_label}</p>
                        <p className="mt-1 text-xs text-slate-600">{item.recommended_action}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <div className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm print:shadow-none">
                <h3 className="text-sm font-black uppercase tracking-[0.18em] text-slate-500">Briefing markdown</h3>
                <pre className="mt-4 max-h-[320px] overflow-auto whitespace-pre-wrap rounded-2xl bg-slate-950 p-4 text-xs leading-6 text-slate-200">
                  {presentation.briefing.markdown}
                </pre>
              </div>
            </section>
          </>
        )}
      </div>
    </main>
  );
};

export default TeacherPresentationPage;
