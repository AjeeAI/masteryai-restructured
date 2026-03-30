import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  BrainCircuit,
  CheckCheck,
  CheckCircle2,
  ClipboardList,
  Loader2,
  PlayCircle,
  Sparkles,
  Target,
  TimerReset,
} from 'lucide-react';

import { useAuth } from '../context/AuthContext';
import { useUser } from '../context/UserContext';
import {
  fetchDiagnosticStatus,
  startDiagnosticSession,
  submitDiagnosticSession,
} from '../services/api';

const SUBJECT_LABELS = {
  math: 'Mathematics',
  english: 'English Studies',
  civic: 'Civic Education',
};

const RUN_STATUS_STYLES = {
  pending: 'border-slate-200 bg-white text-slate-700',
  in_progress: 'border-amber-200 bg-amber-50 text-amber-800',
  completed: 'border-emerald-200 bg-emerald-50 text-emerald-800',
};

const RUN_STATUS_LABELS = {
  pending: 'Pending',
  in_progress: 'Resume',
  completed: 'Completed',
};

const storageKeyForDiagnostic = (diagnosticId) => `mastery_onboarding_diagnostic_${diagnosticId}`;

const readPersistedSession = (diagnosticId) => {
  if (!diagnosticId) return null;
  try {
    const raw = window.localStorage.getItem(storageKeyForDiagnostic(diagnosticId));
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return {
      answers: parsed?.answers && typeof parsed.answers === 'object' ? parsed.answers : {},
      currentIndex: Number.isFinite(Number(parsed?.currentIndex)) ? Number(parsed.currentIndex) : 0,
    };
  } catch (error) {
    console.warn('Failed to restore onboarding diagnostic progress:', error);
    return null;
  }
};

const persistSession = (diagnosticId, payload) => {
  if (!diagnosticId) return;
  window.localStorage.setItem(storageKeyForDiagnostic(diagnosticId), JSON.stringify(payload));
};

const clearPersistedSession = (diagnosticId) => {
  if (!diagnosticId) return;
  window.localStorage.removeItem(storageKeyForDiagnostic(diagnosticId));
};

const subjectLabel = (subject) => SUBJECT_LABELS[subject] || String(subject || '').toUpperCase();

const subjectAccent = (subject) => {
  switch (subject) {
    case 'english':
      return 'from-sky-500/15 via-cyan-500/10 to-white text-sky-700 border-sky-200';
    case 'math':
      return 'from-indigo-500/15 via-violet-500/10 to-white text-indigo-700 border-indigo-200';
    case 'civic':
      return 'from-emerald-500/15 via-teal-500/10 to-white text-emerald-700 border-emerald-200';
    default:
      return 'from-slate-500/10 via-slate-500/5 to-white text-slate-700 border-slate-200';
  }
};

const completionCount = (status, activeSession, answersById) => {
  const completedSubjects = Array.isArray(status?.completed_subjects) ? status.completed_subjects.length : 0;
  const activeAnswered = activeSession
    ? Math.min(
        Array.from(new Set(Object.keys(answersById || {}))).filter((questionId) =>
          activeSession.questions.some((question) => question.question_id === questionId),
        ).length,
        activeSession.questions.length,
      )
    : 0;
  return (completedSubjects * 10) + activeAnswered;
};

export default function AssessmentSplash() {
  const navigate = useNavigate();
  const { token } = useAuth();
  const {
    studentData,
    userData,
    diagnosticStatus,
    refreshDiagnosticStatus,
    replaceLocalStudent,
  } = useUser();


  // --- SMART ROUTING CASCADE (SAFETY NET) ---
  useEffect(() => {
    if (!studentData) return;

    // Step 1: Check for basic class level and term
    if (!studentData.sss_level || !studentData.current_term) {
      navigate('/class-selection', { replace: true });
      return;
    }

    // Step 2: Check if subjects are selected
    if (!Array.isArray(studentData.subjects) || studentData.subjects.length === 0) {
      navigate('/subject-selection', { replace: true });
      return;
    }

    // Step 3: Check if learning preferences are set
    if (!studentData.has_profile || !studentData.preferences) {
      navigate('/learning-preferences', { replace: true });
      return;
    }
  }, [studentData, navigate]);
  // ------------------------------------------
  
  const activeId =
    studentData?.student_id ||
    studentData?.user_id ||
    userData?.user_id ||
    userData?.id ||
    window.localStorage.getItem('mastery_student_id');
  const level = studentData?.sss_level || 'SSS1';
  const term = Number(studentData?.current_term || 1);
  const selectedSubjects = useMemo(
    () => (Array.isArray(studentData?.subjects) ? studentData.subjects : []).filter(Boolean),
    [studentData?.subjects],
  );

  const [status, setStatus] = useState(diagnosticStatus);
  const [statusError, setStatusError] = useState('');
  const [isLoadingStatus, setIsLoadingStatus] = useState(true);
  const [activeSession, setActiveSession] = useState(null);
  const [answersById, setAnswersById] = useState({});
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selectedAnswer, setSelectedAnswer] = useState('');
  const [isLaunching, setIsLaunching] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [launchError, setLaunchError] = useState('');
  const [latestSummary, setLatestSummary] = useState(null);

  const loadStatus = useCallback(async () => {
    if (!token || !activeId) {
      setStatus(null);
      setIsLoadingStatus(false);
      return null;
    }

    setIsLoadingStatus(true);
    setStatusError('');
    try {
      const nextStatus = await fetchDiagnosticStatus(token, activeId);
      setStatus(nextStatus);
      await refreshDiagnosticStatus(activeId);
      return nextStatus;
    } catch (error) {
      setStatusError(error.message || 'Unable to load onboarding diagnostic status.');
      return null;
    } finally {
      setIsLoadingStatus(false);
    }
  }, [activeId, refreshDiagnosticStatus, token]);

  useEffect(() => {
    setStatus(diagnosticStatus);
  }, [diagnosticStatus]);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  useEffect(() => {
    if (!activeSession) {
      setSelectedAnswer('');
      return;
    }
    const currentQuestion = activeSession.questions[currentIndex];
    setSelectedAnswer((currentQuestion && answersById[currentQuestion.question_id]) || '');
  }, [activeSession, answersById, currentIndex]);

  const hydrateSession = useCallback((session) => {
    const persisted = readPersistedSession(session?.diagnostic_id);
    const safeAnswers = persisted?.answers || {};
    const firstUnansweredIndex = session.questions.findIndex((question) => !safeAnswers[question.question_id]);
    const resolvedIndex =
      firstUnansweredIndex >= 0
        ? firstUnansweredIndex
        : Math.min(
            persisted?.currentIndex ?? session.questions.length - 1,
            Math.max(session.questions.length - 1, 0),
          );

    setActiveSession(session);
    setAnswersById(safeAnswers);
    setCurrentIndex(Math.max(resolvedIndex, 0));
  }, []);

  const launchSubjectDiagnostic = useCallback(
    async (subject) => {
      if (!token || !activeId || !subject) return;
      setIsLaunching(true);
      setLaunchError('');
      try {
        const session = await startDiagnosticSession(token, {
          student_id: activeId,
          subject,
          sss_level: level,
          term,
          num_questions: 10,
        });
        hydrateSession(session);
      } catch (error) {
        setLaunchError(error.message || 'Unable to start the onboarding diagnostic.');
      } finally {
        setIsLaunching(false);
      }
    },
    [activeId, hydrateSession, level, term, token],
  );

  const currentQuestion = activeSession?.questions?.[currentIndex] || null;
  const overallProgress = selectedSubjects.length
    ? Math.round((completionCount(status, activeSession, answersById) / (selectedSubjects.length * 10)) * 100)
    : 0;

  const handlePersistAndMove = (answerValue, direction = 'next') => {
    if (!activeSession || !currentQuestion) return;
    const nextAnswers = {
      ...answersById,
      [currentQuestion.question_id]: answerValue,
    };
    setAnswersById(nextAnswers);
    persistSession(activeSession.diagnostic_id, {
      answers: nextAnswers,
      currentIndex:
        direction === 'next'
          ? Math.min(currentIndex + 1, activeSession.questions.length - 1)
          : Math.max(currentIndex - 1, 0),
    });

    if (direction === 'next') {
      setCurrentIndex((prev) => Math.min(prev + 1, activeSession.questions.length - 1));
    } else {
      setCurrentIndex((prev) => Math.max(prev - 1, 0));
    }
  };

  const handleSubmitSubject = async (overrideAnswers = null) => {
    if (!token || !activeId || !activeSession) return;

    const finalAnswers = { ...answersById, ...(overrideAnswers || {}) };
    if (currentQuestion && selectedAnswer) {
      finalAnswers[currentQuestion.question_id] = selectedAnswer;
    }

    const payloadAnswers = activeSession.questions.map((question) => ({
      question_id: question.question_id,
      answer: finalAnswers[question.question_id] || 'SKIPPED',
    }));

    setIsSubmitting(true);
    setLaunchError('');

    try {
      const result = await submitDiagnosticSession(token, {
        diagnostic_id: activeSession.diagnostic_id,
        student_id: activeId,
        answers: payloadAnswers,
      });

      clearPersistedSession(activeSession.diagnostic_id);
      setLatestSummary({
        subject: activeSession.subject,
        result,
      });
      setActiveSession(null);
      setAnswersById({});
      setCurrentIndex(0);
      setSelectedAnswer('');

      const nextStatus = await loadStatus();
      if (nextStatus?.onboarding_complete) {
        replaceLocalStudent({
          ...(studentData || {}),
          has_profile: true,
        });
        return;
      }

      const nextRun = (nextStatus?.subject_runs || []).find((run) => run.status !== 'completed');
      if (nextRun?.subject) {
        await launchSubjectDiagnostic(nextRun.subject);
      }
    } catch (error) {
      setLaunchError(error.message || 'Unable to submit this diagnostic run.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const nextRun = useMemo(
    () => (status?.subject_runs || []).find((run) => run.status !== 'completed') || null,
    [status],
  );

  const answeredCurrentSubjectCount = activeSession
    ? activeSession.questions.filter((question) => {
        const answer = answersById[question.question_id];
        return typeof answer === 'string' && answer.length > 0;
      }).length
    : 0;

  const overallAnsweredCount = completionCount(status, activeSession, answersById);

  if (isLoadingStatus) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
        <div className="rounded-[2rem] border border-slate-200 bg-white px-8 py-10 text-center shadow-sm">
          <Loader2 className="mx-auto h-9 w-9 animate-spin text-indigo-600" />
          <p className="mt-4 text-sm font-semibold text-slate-600">Loading your onboarding diagnostic...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(56,189,248,0.12),_transparent_28%),radial-gradient(circle_at_top_right,_rgba(79,70,229,0.12),_transparent_24%),linear-gradient(180deg,#f8fbff_0%,#eef2ff_48%,#f8fafc_100%)] px-4 py-6 sm:px-6 sm:py-8">
      <main className="mx-auto max-w-[90rem]">
        <div className="mb-8 grid gap-5 xl:grid-cols-[1.4fr_0.8fr]">
          <section className="relative overflow-hidden rounded-[2rem] border border-slate-200/80 bg-white/90 p-6 shadow-[0_20px_60px_-35px_rgba(15,23,42,0.25)] backdrop-blur">
            <div className="absolute inset-x-0 top-0 h-24 bg-[linear-gradient(90deg,rgba(37,99,235,0.10),rgba(14,165,233,0.06),transparent)]" />
            <div className="relative">
              <div className="inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-white px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em] text-indigo-700 shadow-sm">
                <BrainCircuit className="h-3.5 w-3.5" />
                Graph-grounded onboarding
              </div>
              <h1 className="mt-5 max-w-4xl text-[2.2rem] font-black tracking-tight text-slate-950 sm:text-[2.8rem] lg:text-[3rem]">
                Build a real mastery baseline before your first lesson.
              </h1>
              <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-600 sm:text-[15px]">
                We run one focused diagnostic per subject, map your weak prerequisites into the knowledge graph, and
                use that evidence to shape your first lesson sequence, tutor interventions, and revision path.
              </p>

              <div className="mt-6 grid gap-3 sm:grid-cols-3">
                <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50/80 p-4">
                  <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Subjects selected</p>
                  <p className="mt-2 text-[1.65rem] font-black text-slate-900">{selectedSubjects.length || 0}</p>
                  <p className="mt-1 text-xs font-semibold text-slate-500">One diagnostic run per enrolled subject</p>
                </div>
                <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50/80 p-4">
                  <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Questions answered</p>
                  <p className="mt-2 text-[1.65rem] font-black text-slate-900">{overallAnsweredCount}</p>
                  <p className="mt-1 text-xs font-semibold text-slate-500">Baseline evidence already captured</p>
                </div>
                <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50/80 p-4">
                  <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Graph target</p>
                  <p className="mt-2 text-[1.65rem] font-black text-slate-900">{status?.completed_subjects?.length || 0}</p>
                  <p className="mt-1 text-xs font-semibold text-slate-500">Subjects already mapped into mastery</p>
                </div>
              </div>
            </div>
          </section>

          <aside className="rounded-[2rem] border border-slate-200/80 bg-slate-950 p-6 text-white shadow-[0_20px_60px_-35px_rgba(15,23,42,0.55)]">
            <div className="flex items-center justify-between gap-3">
              <div className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em] text-sky-200">
                <BrainCircuit className="h-3.5 w-3.5" />
                Progress pulse
              </div>
              <p className="text-[2.35rem] font-black text-white">{overallProgress}%</p>
            </div>
            <div className="mt-5 h-3 overflow-hidden rounded-full bg-white/10">
              <div
                className="h-full rounded-full bg-[linear-gradient(90deg,#22d3ee_0%,#6366f1_60%,#8b5cf6_100%)] transition-all duration-300"
                style={{ width: `${Math.max(overallProgress, 4)}%` }}
              />
            </div>
            <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
              <div className="rounded-[1.35rem] border border-white/10 bg-white/5 p-4">
                <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-300">Completion</p>
                <p className="mt-2 text-lg font-black text-white">
                  {status?.completed_subjects?.length || 0} / {selectedSubjects.length || 0} subjects
                </p>
                <p className="mt-1 text-xs font-semibold text-slate-300">Each subject writes its own diagnostic evidence trail.</p>
              </div>
              <div className="rounded-[1.35rem] border border-white/10 bg-white/5 p-4">
                <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-300">Current route</p>
                <p className="mt-2 text-lg font-black text-white">{nextRun ? subjectLabel(nextRun.subject) : 'All subjects complete'}</p>
                <p className="mt-1 text-xs font-semibold text-slate-300">
                  {nextRun?.status === 'in_progress' ? 'Resume where you stopped.' : 'Start the next subject in sequence.'}
                </p>
              </div>
            </div>
          </aside>
        </div>

        {(statusError || launchError) && (
          <div className="mb-6 flex items-start gap-3 rounded-[1.75rem] border border-rose-200 bg-rose-50 px-5 py-4 text-sm font-semibold text-rose-700 shadow-sm">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            {statusError || launchError}
          </div>
        )}

        {latestSummary && (
          <div className="mb-6 rounded-[2rem] border border-emerald-200 bg-[linear-gradient(135deg,rgba(16,185,129,0.14),rgba(255,255,255,0.95))] px-6 py-5 shadow-sm">
            <div className="flex items-center gap-3">
              <CheckCircle2 className="h-5 w-5 text-emerald-700" />
              <div>
                <p className="text-[10px] font-black uppercase tracking-[0.18em] text-emerald-700">
                  {subjectLabel(latestSummary.subject)} diagnostic submitted
                </p>
                <p className="mt-1 text-sm leading-6 text-emerald-900">
                  {latestSummary.result?.learning_gap_summary?.rationale || 'Your baseline mastery profile has been updated.'}
                </p>
              </div>
              </div>
            </div>
        )}
        <div className="grid gap-6 xl:grid-cols-[0.92fr_1.28fr]">
          <section className="space-y-6">
            <div className="rounded-[2rem] border border-slate-200/80 bg-white/90 p-6 shadow-[0_16px_50px_-32px_rgba(15,23,42,0.24)]">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <ClipboardList className="h-4 w-4 text-indigo-600" />
                  <p className="text-[10px] font-black uppercase tracking-[0.18em] text-indigo-600">Subject queue</p>
                </div>
                <div className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em] text-slate-500">
                  {status?.completed_subjects?.length || 0} completed
                </div>
              </div>
              <div className="mt-4 space-y-3">
                {(status?.subject_runs || []).map((run) => {
                  const isActiveRun = activeSession?.subject === run.subject;
                  return (
                    <div
                      key={run.subject}
                      className={`overflow-hidden rounded-[1.8rem] border bg-[linear-gradient(135deg,rgba(255,255,255,0.98),rgba(248,250,252,0.95))] p-4 transition ${RUN_STATUS_STYLES[run.status] || RUN_STATUS_STYLES.pending} ${isActiveRun ? 'ring-2 ring-indigo-200 shadow-[0_12px_35px_-24px_rgba(79,70,229,0.45)]' : 'shadow-sm'}`}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="min-w-0">
                          <div className="flex items-center gap-3">
                            <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border bg-gradient-to-br ${subjectAccent(run.subject)}`}>
                              {run.status === 'completed' ? (
                                <CheckCheck className="h-5 w-5" />
                              ) : run.status === 'in_progress' ? (
                                <TimerReset className="h-5 w-5" />
                              ) : (
                                <PlayCircle className="h-5 w-5" />
                              )}
                            </div>
                            <div className="min-w-0">
                              <p className="truncate text-[1.02rem] font-black text-slate-900 sm:text-[1.08rem]">{subjectLabel(run.subject)}</p>
                              <p className="mt-1 text-[11px] font-black uppercase tracking-[0.18em] text-slate-500">
                                {RUN_STATUS_LABELS[run.status]} - {run.question_count || 10} questions
                              </p>
                            </div>
                          </div>
                        </div>
                        {run.status !== 'completed' && (
                          <button
                            type="button"
                            onClick={() => launchSubjectDiagnostic(run.subject)}
                            disabled={isLaunching || isSubmitting}
                            className="shrink-0 rounded-2xl bg-slate-950 px-4 py-2.5 text-xs font-black text-white transition hover:bg-slate-800 disabled:opacity-60"
                          >
                            {run.status === 'in_progress' ? 'Resume' : 'Start'}
                          </button>
                        )}
                      </div>

                      <div className="mt-4 flex flex-wrap gap-2">
                        <span className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.16em] text-slate-500">
                          {run.status === 'completed' ? 'Baseline stored' : 'Awaiting evidence'}
                        </span>
                        {isActiveRun && (
                          <span className="rounded-full border border-indigo-200 bg-indigo-50 px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.16em] text-indigo-700">
                            Active now
                          </span>
                        )}
                      </div>

                      {run.recommended_start_topic_title && (
                        <p className="mt-4 text-sm leading-6 text-slate-600">
                          Recommended start: <span className="font-bold text-slate-900">{run.recommended_start_topic_title}</span>
                        </p>
                      )}
                      {run.blocking_prerequisite_label && (
                        <p className="mt-2 text-sm leading-6 text-amber-800">
                          Blocking prerequisite: <span className="font-bold">{run.blocking_prerequisite_label}</span>
                        </p>
                      )}
                      {Array.isArray(run.weakest_concepts) && run.weakest_concepts.length > 0 && (
                        <div className="mt-4 flex flex-wrap gap-2">
                          {run.weakest_concepts.slice(0, 3).map((concept) => (
                            <span
                              key={`${run.subject}-${concept.concept_id}`}
                              className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[10px] font-black uppercase tracking-[0.16em] text-slate-600"
                            >
                              {concept.concept_label}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="rounded-[2rem] border border-slate-200/80 bg-white/90 p-6 shadow-[0_16px_50px_-32px_rgba(15,23,42,0.24)]">
              <div className="flex items-center gap-2">
                <Target className="h-4 w-4 text-emerald-600" />
                <p className="text-[10px] font-black uppercase tracking-[0.18em] text-emerald-600">Why this matters</p>
              </div>
              <div className="mt-5 space-y-4">
                <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50/80 p-4">
                  <div className="flex items-start gap-3">
                    <div className="mt-0.5 rounded-2xl bg-emerald-100 p-2 text-emerald-700">
                      <CheckCircle2 className="h-4 w-4" />
                    </div>
                    <div>
                      <p className="text-sm font-black text-slate-900">Every answer becomes mastery evidence</p>
                      <p className="mt-1 text-sm leading-6 text-slate-600">
                        We write baseline confidence into your graph profile instead of treating onboarding like a throwaway quiz.
                      </p>
                    </div>
                  </div>
                </div>

                <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50/80 p-4">
                  <div className="flex items-start gap-3">
                    <div className="mt-0.5 rounded-2xl bg-amber-100 p-2 text-amber-700">
                      <Target className="h-4 w-4" />
                    </div>
                    <div>
                      <p className="text-sm font-black text-slate-900">Weak prerequisites become your first repair route</p>
                      <p className="mt-1 text-sm leading-6 text-slate-600">
                        The system uses weak concepts and blockers to decide what to reteach first.
                      </p>
                    </div>
                  </div>
                </div>

                <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50/80 p-4">
                  <div className="flex items-start gap-3">
                    <div className="mt-0.5 rounded-2xl bg-sky-100 p-2 text-sky-700">
                      <Sparkles className="h-4 w-4" />
                    </div>
                    <div>
                      <p className="text-sm font-black text-slate-900">Your dashboard is shaped by this result</p>
                      <p className="mt-1 text-sm leading-6 text-slate-600">
                        Recommended lessons, tutor actions, and starting topics after onboarding come from this baseline.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <section className="rounded-[2rem] border border-slate-200/80 bg-white/95 p-6 shadow-[0_20px_60px_-35px_rgba(15,23,42,0.24)] backdrop-blur">
            {!activeSession ? (
              status?.onboarding_complete ? (
                <div className="flex min-h-[34rem] flex-col items-center justify-center text-center">
                  <div className="rounded-[2rem] bg-emerald-100 p-4 text-emerald-700">
                    <CheckCircle2 className="h-12 w-12" />
                  </div>
                  <h2 className="mt-5 text-[2.1rem] font-black text-slate-900">Diagnostic complete</h2>
                  <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-600">
                    Your baseline graph profile is ready. We have stored weak concepts, blocking prerequisites, and recommended lesson starts for each subject.
                  </p>
                  <div className="mt-8 grid w-full max-w-3xl gap-3 sm:grid-cols-3">
                    <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50 p-4 text-left">
                      <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Subjects mapped</p>
                      <p className="mt-2 text-[1.65rem] font-black text-slate-900">{status?.completed_subjects?.length || 0}</p>
                    </div>
                    <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50 p-4 text-left">
                      <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Question total</p>
                      <p className="mt-2 text-[1.65rem] font-black text-slate-900">{selectedSubjects.length * 10 || 0}</p>
                    </div>
                    <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50 p-4 text-left">
                      <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Next step</p>
                      <p className="mt-2 text-lg font-black text-slate-900">Open dashboard</p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => navigate('/dashboard')}
                    className="mt-8 inline-flex items-center gap-2 rounded-2xl bg-indigo-600 px-5 py-3 text-sm font-black text-white transition hover:bg-indigo-700"
                  >
                    Open dashboard
                    <ArrowRight className="h-4 w-4" />
                  </button>
                </div>
              ) : (
                <div className="flex min-h-[34rem] flex-col justify-center">
                  <div className="inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em] text-indigo-700">
                    <Sparkles className="h-3.5 w-3.5" />
                    Ready to begin
                  </div>
                  <h2 className="mt-5 max-w-3xl text-[1.7rem] font-black leading-tight text-slate-900 sm:text-[1.95rem]">
                    {nextRun?.status === 'in_progress'
                      ? `Resume ${subjectLabel(nextRun.subject)} diagnostic`
                      : 'Start your subject diagnostics'}
                  </h2>
                  <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-600">
                    We will guide you through {selectedSubjects.length * 10 || 10} graph-grounded questions across your selected subjects. Your progress is saved, so a refresh brings you back to the current subject run.
                  </p>
                  <div className="mt-8 grid gap-3 sm:grid-cols-2">
                    <div className="rounded-[1.6rem] border border-slate-200 bg-slate-50/80 p-5">
                      <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Next subject</p>
                      <p className="mt-2 text-[1.18rem] font-black text-slate-900">
                        {nextRun?.subject ? subjectLabel(nextRun.subject) : subjectLabel(selectedSubjects[0])}
                      </p>
                      <p className="mt-1 text-sm leading-6 text-slate-600">
                        {nextRun?.status === 'in_progress'
                          ? 'Continue from the saved checkpoint.'
                          : 'Launch the first required diagnostic run.'}
                      </p>
                    </div>
                    <div className="rounded-[1.6rem] border border-slate-200 bg-slate-50/80 p-5">
                      <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Question format</p>
                      <p className="mt-2 text-[1.18rem] font-black text-slate-900">10 questions per subject</p>
                      <p className="mt-1 text-sm leading-6 text-slate-600">Grounded in approved mappings for {level} term {term}.</p>
                    </div>
                  </div>
                  <div className="mt-8 flex flex-wrap gap-3">
                    <button
                      type="button"
                      onClick={() => launchSubjectDiagnostic(nextRun?.subject || selectedSubjects[0])}
                      disabled={!nextRun?.subject || isLaunching}
                      className="inline-flex items-center gap-2 rounded-2xl bg-indigo-600 px-5 py-3 text-sm font-black text-white transition hover:bg-indigo-700 disabled:opacity-60"
                    >
                      {isLaunching ? <Loader2 className="h-4 w-4 animate-spin" /> : <PlayCircle className="h-4 w-4" />}
                      {nextRun?.status === 'in_progress' ? 'Resume diagnostic' : 'Start diagnostic'}
                    </button>
                    <button
                      type="button"
                      onClick={() => navigate('/learning-preferences')}
                      className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-5 py-3 text-sm font-black text-slate-700 transition hover:bg-slate-50"
                    >
                      <ArrowLeft className="h-4 w-4" />
                      Back to preferences
                    </button>
                  </div>
                </div>
              )
            ) : (
              <>
                <div className="rounded-[1.9rem] border border-slate-200 bg-[linear-gradient(135deg,rgba(241,245,249,0.78),rgba(255,255,255,0.98))] p-5">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                    <div className="min-w-0">
                      <div className="inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-white px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em] text-indigo-700 shadow-sm">
                        <BrainCircuit className="h-3.5 w-3.5" />
                        {subjectLabel(activeSession.subject)}
                      </div>
                      <h2 className="mt-4 text-[1.42rem] font-black text-slate-900 sm:text-[1.58rem]">
                        Question {currentIndex + 1} of {activeSession.question_count}
                      </h2>
                      <p className="mt-2 max-w-2xl text-sm leading-7 text-slate-600">
                        Each question is grounded in approved curriculum mappings for {level} term {term}, then written back into your graph profile as baseline evidence.
                      </p>
                    </div>
                    <div className="grid gap-3 sm:grid-cols-2">
                      <div className="rounded-[1.35rem] border border-slate-200 bg-white px-4 py-3 shadow-sm">
                        <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Answered</p>
                        <p className="mt-1 text-[1.28rem] font-black text-slate-900">
                          {answeredCurrentSubjectCount} / {activeSession.question_count}
                        </p>
                      </div>
                      <div className="rounded-[1.35rem] border border-slate-200 bg-white px-4 py-3 shadow-sm">
                        <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Subject progress</p>
                        <p className="mt-1 text-[1.28rem] font-black text-slate-900">
                          {Math.round(((currentIndex + 1) / activeSession.question_count) * 100)}%
                        </p>
                      </div>
                    </div>
                  </div>
                  <div className="mt-5 h-2.5 overflow-hidden rounded-full bg-slate-200">
                    <div
                      className="h-full rounded-full bg-[linear-gradient(90deg,#22d3ee_0%,#6366f1_65%,#8b5cf6_100%)] transition-all duration-300"
                      style={{ width: `${Math.max(Math.round(((currentIndex + 1) / activeSession.question_count) * 100), 6)}%` }}
                    />
                  </div>
                </div>

                <div className="mt-6 grid gap-5 2xl:grid-cols-[0.42fr_1fr]">
                  <div className="space-y-4">
                    <div className="rounded-[1.7rem] border border-slate-200 bg-slate-50/80 p-5">
                      <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Concept focus</p>
                      <p className="mt-3 text-[1.18rem] font-black leading-tight text-slate-900 sm:text-[1.28rem]">
                        {currentQuestion?.concept_label || 'Mapped concept'}
                      </p>
                      {currentQuestion?.topic_title && (
                        <p className="mt-3 text-sm font-semibold leading-6 text-slate-700">
                          {currentQuestion.topic_title}
                        </p>
                      )}
                    </div>
                  </div>

                  <div>
                    <div className="rounded-[1.9rem] border border-slate-200 bg-white p-6 shadow-sm">
                      <h3 className="text-[1.4rem] font-black leading-tight text-slate-950 sm:text-[1.55rem]">{currentQuestion?.prompt}</h3>

                      <div className="mt-6 grid gap-4 lg:grid-cols-2">
                        {(currentQuestion?.options || []).map((option, index) => {
                          const optionLetter = String.fromCharCode(65 + index);
                          const isSelected = selectedAnswer === optionLetter;
                          const optionDetail = currentQuestion?.option_details?.[index] || null;
                          return (
                            <button
                              key={`${currentQuestion?.question_id}-${optionLetter}`}
                              type="button"
                              onClick={() => setSelectedAnswer(optionLetter)}
                              className={`group flex min-h-[10.5rem] flex-col rounded-[1.75rem] border px-5 py-5 text-left transition-all duration-200 ${
                                isSelected
                                  ? 'border-indigo-300 bg-[linear-gradient(135deg,rgba(99,102,241,0.12),rgba(255,255,255,0.98))] text-indigo-950 shadow-[0_16px_38px_-28px_rgba(79,70,229,0.6)]'
                                  : 'border-slate-200 bg-slate-50/40 text-slate-700 hover:-translate-y-0.5 hover:border-slate-300 hover:bg-white hover:shadow-[0_16px_38px_-30px_rgba(15,23,42,0.24)]'
                              }`}
                            >
                              <div className="flex items-start justify-between gap-3">
                                <div className="inline-flex items-center gap-2 rounded-full border border-current/10 bg-white/80 px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em] text-slate-500">
                                  <span
                                    className={`flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-black ${
                                      isSelected ? 'bg-indigo-600 text-white' : 'bg-slate-200 text-slate-700 group-hover:bg-slate-300'
                                    }`}
                                  >
                                    {optionLetter}
                                  </span>
                                  Option {optionLetter}
                                </div>
                                {isSelected ? (
                                  <span className="rounded-full bg-indigo-600 px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.16em] text-white">
                                    Selected
                                  </span>
                                ) : null}
                              </div>
                              <p className="mt-4 break-words text-[0.98rem] font-semibold leading-7 text-slate-900">
                                {optionDetail?.label || option}
                              </p>
                              {optionDetail?.context_title ? (
                                <p className="mt-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
                                  Lesson area: {optionDetail.context_title}
                                </p>
                              ) : null}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                </div>

                <div className="mt-8 flex flex-col gap-3 border-t border-slate-100 pt-5 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex flex-wrap gap-3">
                    <button
                      type="button"
                      onClick={() => {
                        if (!activeSession) return;
                        const previousIndex = Math.max(currentIndex - 1, 0);
                        setCurrentIndex(previousIndex);
                        persistSession(activeSession.diagnostic_id, {
                          answers: answersById,
                          currentIndex: previousIndex,
                        });
                      }}
                      disabled={currentIndex === 0 || isSubmitting}
                      className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-black text-slate-700 transition hover:bg-slate-50 disabled:opacity-50"
                    >
                      <ArrowLeft className="h-4 w-4" />
                      Back
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        const skipValue = 'SKIPPED';
                        if (currentIndex === activeSession.question_count - 1) {
                          setSelectedAnswer(skipValue);
                          setAnswersById((prev) => ({ ...prev, [currentQuestion.question_id]: skipValue }));
                          persistSession(activeSession.diagnostic_id, {
                            answers: { ...answersById, [currentQuestion.question_id]: skipValue },
                            currentIndex,
                          });
                          void handleSubmitSubject({ [currentQuestion.question_id]: skipValue });
                          return;
                        }
                        handlePersistAndMove(skipValue, 'next');
                      }}
                      disabled={isSubmitting}
                      className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-black text-slate-700 transition hover:bg-slate-50 disabled:opacity-50"
                    >
                      Skip
                    </button>
                  </div>

                  <button
                    type="button"
                    onClick={() => {
                      if (!selectedAnswer) return;
                      if (currentIndex === activeSession.question_count - 1) {
                        void handleSubmitSubject();
                        return;
                      }
                      handlePersistAndMove(selectedAnswer, 'next');
                    }}
                    disabled={!selectedAnswer || isSubmitting}
                    className="inline-flex items-center justify-center gap-2 rounded-2xl bg-[linear-gradient(90deg,#4f46e5_0%,#7c3aed_100%)] px-5 py-3 text-sm font-black text-white transition hover:brightness-105 disabled:opacity-60"
                  >
                    {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                    {currentIndex === activeSession.question_count - 1 ? 'Submit subject diagnostic' : 'Next question'}
                    <ArrowRight className="h-4 w-4" />
                  </button>
                </div>
              </>
            )}
          </section>
        </div>
      </main>
    </div>
  );
}
