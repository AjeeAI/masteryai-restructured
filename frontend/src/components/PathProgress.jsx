import { useNavigate } from 'react-router-dom';
import { ArrowRight, Map, Route } from 'lucide-react';

const storyStyles = {
  bridge_prerequisite: 'border-amber-400/30 bg-amber-500/10 text-amber-100',
  advance_to_next: 'border-emerald-400/30 bg-emerald-500/10 text-emerald-100',
  hold_current: 'border-indigo-400/30 bg-indigo-500/10 text-indigo-100',
};

const storyLabels = {
  bridge_prerequisite: 'Bridge prerequisite',
  advance_to_next: 'Advance next',
  hold_current: 'Hold current focus',
};

export default function PathProgress({
  nextTopic,
  nextTopicId,
  nextConcept,
  reason,
  blockingPrerequisite,
  story = null,
  actionLabel = null,
}) {
  const navigate = useNavigate();
  const storyTone = storyStyles[story?.status] || 'border-slate-500/20 bg-slate-500/10 text-slate-100';
  const isLikelyUuid = (value) => /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(String(value || '').trim());
  const normalizedNextTopic = (() => {
    const cleaned = String(nextTopic || '').trim();
    if (cleaned && !isLikelyUuid(cleaned)) return cleaned;
    if (nextTopicId) return 'Recommended lesson';
    return 'Stay on this lesson';
  })();

  return (
    <div className="bg-[#1c2438] rounded-2xl p-6 border border-slate-700 mt-6">
      <div className="flex items-center gap-2 text-white font-bold mb-6">
        <Map className="w-5 h-5 text-slate-400" />
        Path Progress
      </div>
      
      <div className="bg-[#2a3447] rounded-xl p-6 flex justify-between items-center relative mb-4">
        {/* Connecting Line */}
        <div className="absolute top-1/2 left-8 right-8 h-0.5 bg-slate-600 -translate-y-1/2 z-0"></div>
        
        {/* Progress Nodes */}
        <div className="w-4 h-4 rounded-full bg-emerald-500 z-10 shadow-[0_0_10px_rgba(16,185,129,0.5)]"></div>
        <div className="w-5 h-5 rounded-full bg-blue-500 border-4 border-[#2a3447] z-10 shadow-[0_0_10px_rgba(59,130,246,0.5)]"></div>
        <div className="w-4 h-4 rounded-full bg-slate-500 z-10"></div>
        <div className="w-4 h-4 rounded-full bg-slate-500 z-10"></div>
      </div>
      
      <div className="text-center">
        {story?.headline && (
          <div className={`mb-4 rounded-xl border px-4 py-3 text-left ${storyTone}`}>
            <div className="text-[10px] font-bold uppercase tracking-wider opacity-80">
              {storyLabels[story.status] || 'Graph guidance'}
            </div>
            <div className="mt-2 text-sm font-bold">{story.headline}</div>
            {story.supporting_reason && (
              <p className="mt-2 text-xs leading-6 opacity-90">{story.supporting_reason}</p>
            )}
          </div>
        )}
        <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Next Topic:</div>
        <div className="text-sm font-bold text-white">{normalizedNextTopic}</div>
        {nextConcept && (
          <div className="mt-3 inline-flex items-center gap-2 rounded-full border border-cyan-400/30 bg-cyan-500/10 px-3 py-1.5 text-[11px] font-semibold text-cyan-100">
            <Route className="h-3.5 w-3.5" />
            Next concept focus: {nextConcept}
          </div>
        )}
        {reason && <p className="mt-3 text-xs leading-6 text-slate-300">{reason}</p>}
        {blockingPrerequisite && (
          <div className="mt-3 rounded-xl border border-amber-400/30 bg-amber-500/10 px-3 py-2 text-xs font-semibold text-amber-100">
            Blocking prerequisite: {blockingPrerequisite}
          </div>
        )}
        {story?.evidence_summary && (
          <div className="mt-3 rounded-xl border border-slate-600 bg-slate-800/60 px-3 py-2 text-xs leading-6 text-slate-300">
            Latest evidence: {story.evidence_summary}
          </div>
        )}
        {nextTopicId && (
          <button
            type="button"
            onClick={() => navigate(`/lesson/${nextTopicId}`)}
            className="mt-4 inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-xs font-bold text-white transition hover:bg-indigo-500"
          >
            {actionLabel || 'Open recommended lesson'}
            <ArrowRight className="h-4 w-4" />
          </button>
        )}
      </div>
    </div>
  );
}
