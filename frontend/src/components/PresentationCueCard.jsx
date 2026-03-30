import React, { useEffect, useState } from 'react';
import { ChevronDown, ChevronUp, MonitorPlay, Sparkles } from 'lucide-react';

import { readPresentationWalkthrough, subscribePresentationWalkthrough } from '../services/presentationWalkthrough';

export default function PresentationCueCard({ stepId, speakerNotes = [], nextClickLabel }) {
  const [walkthrough, setWalkthrough] = useState(() => readPresentationWalkthrough());
  const [isExpanded, setIsExpanded] = useState(true);

  useEffect(() => subscribePresentationWalkthrough(setWalkthrough), []);

  const currentStep = walkthrough?.steps?.[walkthrough?.currentStepIndex || 0] || null;
  const nextStep = walkthrough?.steps?.[(walkthrough?.currentStepIndex || 0) + 1] || null;

  if (!walkthrough?.active || currentStep?.id !== stepId) {
    return null;
  }

  return (
    <section className="rounded-[1.75rem] border border-indigo-200 bg-[linear-gradient(135deg,#eef2ff,_#ffffff)] p-5 shadow-sm print:hidden">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="max-w-3xl">
          <div className="inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-white px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em] text-indigo-700">
            <MonitorPlay className="h-3.5 w-3.5" />
            Live demo cue
          </div>
          <h2 className="mt-3 text-xl font-black text-slate-900">{currentStep.title}</h2>
          <p className="mt-2 text-sm leading-7 text-slate-600">{currentStep.description}</p>
          <div className="mt-4 flex flex-wrap gap-2">
            {nextClickLabel && (
              <span className="inline-flex items-center gap-2 rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-[11px] font-black uppercase tracking-[0.16em] text-amber-700">
                <Sparkles className="h-3.5 w-3.5" />
                Next click: {nextClickLabel}
              </span>
            )}
            {nextStep && (
              <span className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1 text-[11px] font-black uppercase tracking-[0.16em] text-slate-600">
                After this: {nextStep.title}
              </span>
            )}
          </div>
        </div>
        <button
          type="button"
          onClick={() => setIsExpanded((value) => !value)}
          className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-xs font-black uppercase tracking-[0.16em] text-slate-700 transition hover:bg-slate-50"
        >
          {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          {isExpanded ? 'Hide speaker notes' : 'Show speaker notes'}
        </button>
      </div>

      {isExpanded && speakerNotes.length > 0 && (
        <div className="mt-4 rounded-[1.5rem] border border-slate-200 bg-white p-4">
          <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Speaker notes</p>
          <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-700">
            {speakerNotes.map((note) => (
              <li key={note}>- {note}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
