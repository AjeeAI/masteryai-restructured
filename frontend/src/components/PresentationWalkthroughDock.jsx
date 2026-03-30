import React, { useEffect, useMemo, useState } from 'react';
import { ArrowRight, MonitorPlay, Route, X } from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';

import {
  advancePresentationWalkthrough,
  readPresentationWalkthrough,
  stopPresentationWalkthrough,
  subscribePresentationWalkthrough,
  syncPresentationWalkthroughStep,
} from '../services/presentationWalkthrough';

export default function PresentationWalkthroughDock() {
  const location = useLocation();
  const navigate = useNavigate();
  const [walkthrough, setWalkthrough] = useState(() => readPresentationWalkthrough());

  const currentPath = `${location.pathname}${location.search || ''}`;

  useEffect(() => {
    return subscribePresentationWalkthrough(setWalkthrough);
  }, []);

  useEffect(() => {
    syncPresentationWalkthroughStep(currentPath);
  }, [currentPath]);

  const currentStep = walkthrough?.steps?.[walkthrough?.currentStepIndex || 0] || null;
  const nextStep = walkthrough?.steps?.[(walkthrough?.currentStepIndex || 0) + 1] || null;
  const isOnCurrentStep = currentStep?.path === currentPath;

  const progressLabel = useMemo(() => {
    if (!walkthrough?.steps?.length || !currentStep) return '';
    return `Stop ${Math.min((walkthrough.currentStepIndex || 0) + 1, walkthrough.steps.length)} of ${walkthrough.steps.length}`;
  }, [currentStep, walkthrough]);

  if (!walkthrough?.active || !currentStep) {
    return null;
  }

  const handlePrimaryAction = () => {
    if (isOnCurrentStep && nextStep) {
      const nextState = advancePresentationWalkthrough();
      const upcoming = nextState?.steps?.[nextState?.currentStepIndex || 0];
      if (upcoming?.path) {
        navigate(upcoming.path);
      }
      return;
    }

    if (isOnCurrentStep && !nextStep) {
      stopPresentationWalkthrough();
      setWalkthrough(null);
      navigate('/presentation-hub');
      return;
    }

    navigate(currentStep.path);
  };

  return (
    <div className="fixed bottom-6 right-6 z-[70] w-[min(360px,calc(100vw-2rem))] rounded-[1.75rem] border border-slate-200 bg-white/95 p-5 shadow-2xl backdrop-blur">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em] text-indigo-700">
            <MonitorPlay className="h-3.5 w-3.5" />
            Live walkthrough
          </div>
          <p className="mt-3 text-sm font-black uppercase tracking-[0.16em] text-slate-400">{progressLabel}</p>
          <h3 className="mt-2 text-lg font-black text-slate-900">{currentStep.title}</h3>
          <p className="mt-2 text-sm leading-6 text-slate-600">{currentStep.description}</p>
        </div>
        <button
          type="button"
          onClick={() => {
            stopPresentationWalkthrough();
            setWalkthrough(null);
          }}
          className="rounded-xl border border-slate-200 bg-white p-2 text-slate-500 transition hover:bg-slate-50 hover:text-slate-700"
          aria-label="End presentation walkthrough"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => navigate('/presentation-hub')}
          className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs font-black uppercase tracking-[0.16em] text-slate-700 transition hover:bg-slate-50"
        >
          <Route className="h-4 w-4" />
          Hub
        </button>
        <button
          type="button"
          onClick={handlePrimaryAction}
          className="inline-flex items-center gap-2 rounded-2xl bg-slate-900 px-3 py-2 text-xs font-black uppercase tracking-[0.16em] text-white transition hover:bg-slate-800"
        >
          {isOnCurrentStep
            ? nextStep
              ? `Next: ${nextStep.title}`
              : 'Finish walkthrough'
            : 'Open this stop'}
          <ArrowRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
