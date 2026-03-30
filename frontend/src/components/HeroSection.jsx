import React from 'react';
import { ArrowRight, BookOpen, GitBranch, PlayCircle, ShieldAlert, Sparkles } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import { useUser } from '../context/UserContext';

export default function HeroSection({
  enrolledSubjects,
  activeSubject,
  onSelectSubject,
  hasStartedLearning,
  graphSignal = null,
  signalSubject = null,
  onResumeSignal = null,
}) {
  const { userData } = useUser();
  const firstName = userData?.first_name || 'Student';
  const navigate = useNavigate();

  const handleStartLearning = () => {
    if (activeSubject) {
      navigate(`/course/${activeSubject}`);
    }
  };

  const signalPayload = graphSignal?.payload || graphSignal || null;
  const signalAnalytics = signalPayload?.analytics || null;
  const signalNextStep = signalPayload?.next_step || null;
  const signalRecommendation = signalPayload?.recommendation_story || null;
  const canResumeSignal = typeof onResumeSignal === 'function' && Boolean(signalNextStep?.recommended_topic_id);

  const handlePrimaryAction = () => {
    if (canResumeSignal) {
      onResumeSignal();
      return;
    }
    handleStartLearning();
  };

  return (
    <section className="relative flex-1 overflow-hidden rounded-2xl border border-slate-200 bg-white px-5 py-5 shadow-sm md:px-6 md:py-6">
      <div className="pointer-events-none absolute right-0 top-0 h-40 w-40 rounded-full bg-indigo-50 blur-3xl" />
      <div className="relative z-10">
        <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div>
            <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Student dashboard</p>
            <h1 className="mt-2 text-[1.75rem] font-black tracking-tight text-slate-900 md:text-[2.2rem]">
              Welcome back, {firstName}.
            </h1>
            <p className="mt-2 text-sm leading-6 text-slate-500">
              {activeSubject
                ? `Continue ${activeSubject} with the next graph-backed lesson.`
                : `Choose where to focus next across ${enrolledSubjects?.length || 0} enrolled subjects.`}
            </p>
          </div>
          {activeSubject && (
            <button
              type="button"
              onClick={handlePrimaryAction}
              className="inline-flex items-center justify-center gap-2 rounded-2xl bg-indigo-600 px-4 py-2.5 text-sm font-black text-white shadow-lg shadow-indigo-200 transition hover:bg-indigo-700"
            >
              <PlayCircle className="h-4 w-4" />
              {signalNextStep?.recommended_topic_id
                ? `Open ${signalSubject || activeSubject}`
                : hasStartedLearning ? 'Resume lesson' : 'Start first lesson'}
            </button>
          )}
        </div>

        {signalPayload && (
          <div className="mb-5 grid gap-3 rounded-2xl border border-indigo-200 bg-indigo-50/60 p-4 md:grid-cols-3">
            <div className="rounded-2xl bg-white px-3 py-3">
              <div className="mb-1 inline-flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.18em] text-indigo-600">
                <GitBranch className="h-3.5 w-3.5" />
                Focus now
              </div>
              <p className="text-sm font-bold text-slate-800">
                {signalAnalytics?.focus_concept
                  || signalPayload?.intervention_timeline?.[0]?.focus_concept_label
                  || signalNextStep?.recommended_concept_label
                  || signalNextStep?.recommended_topic_title
                  || 'Graph focus unavailable'}
              </p>
            </div>
            <div className="rounded-2xl bg-white px-3 py-3">
              <div className="mb-1 inline-flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.18em] text-amber-700">
                <ShieldAlert className="h-3.5 w-3.5" />
                Weakest blocker
              </div>
              <p className="text-sm font-bold text-slate-800">
                {signalAnalytics?.blocking_prerequisite
                  || signalRecommendation?.blocking_prerequisite_label
                  || signalNextStep?.prereq_gap_labels?.[0]
                  || 'No active blocker'}
              </p>
            </div>
            <div className="rounded-2xl bg-white px-3 py-3">
              <div className="mb-1 inline-flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.18em] text-emerald-700">
                <Sparkles className="h-3.5 w-3.5" />
                Next move
              </div>
              <p className="text-sm font-bold text-slate-800">
                {signalRecommendation?.action_label
                  || signalAnalytics?.outcome
                  || signalPayload?.intervention_timeline?.[0]?.action_label
                  || 'Open the recommended lesson'}
              </p>
            </div>
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          {(enrolledSubjects && enrolledSubjects.length > 0 ? enrolledSubjects : []).map((sub) => {
            const isActive = sub === activeSubject;
            return (
              <button
                key={sub}
                type="button"
                onClick={() => onSelectSubject(sub)}
                className={`inline-flex items-center gap-2 rounded-full border px-3 py-2 text-sm font-bold capitalize transition ${
                  isActive
                    ? 'border-indigo-200 bg-indigo-50 text-indigo-700'
                    : 'border-slate-200 bg-white text-slate-600 hover:border-indigo-200 hover:text-indigo-700'
                }`}
              >
                <BookOpen className="h-4 w-4" />
                {sub}
              </button>
            );
          })}
          {activeSubject && (
            <button
              type="button"
              onClick={() => onSelectSubject(null)}
              className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-500 transition hover:border-slate-300 hover:text-slate-700"
            >
              Switch subject
              <ArrowRight className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>
    </section>
  );
}
