import React from 'react';
import {
  BrainCircuit,
  FileBarChart2,
  GitBranch,
  ShieldAlert,
  Sparkles,
} from 'lucide-react';

const safeArray = (value) => (Array.isArray(value) ? value : []);

const iconByKind = {
  quiz: FileBarChart2,
  checkpoint: ShieldAlert,
  diagnostic: BrainCircuit,
  exam_prep: Sparkles,
  practice: GitBranch,
};

const formatTimestamp = (value) => {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return 'Recently';
  return parsed.toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
};

export default function InterventionTimeline({
  timeline = [],
  title = 'Intervention Timeline',
  subtitle = 'Recent mastery evidence across this scope.',
  compact = false,
}) {
  const items = safeArray(timeline).filter(Boolean);
  if (!items.length) return null;

  return (
    <section className="rounded-[2rem] border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center gap-2">
        <GitBranch className="text-indigo-600" size={18} />
        <div>
          <h2 className="text-sm font-black uppercase tracking-[0.2em] text-slate-600">{title}</h2>
          <p className="mt-1 text-xs text-slate-500">{subtitle}</p>
        </div>
      </div>

      <div className={`mt-4 ${compact ? 'space-y-3' : 'grid gap-3 lg:grid-cols-2'}`}>
        {items.map((item, index) => {
          const Icon = iconByKind[item.kind] || GitBranch;
          return (
            <div
              key={`${item.created_at || item.summary}-${index}`}
              className="rounded-[1.5rem] border border-slate-200 bg-slate-50 p-4"
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em] text-slate-600 shadow-sm">
                  <Icon className="h-3.5 w-3.5 text-indigo-500" />
                  {item.source_label || 'Evidence'}
                </div>
                <span className="text-[11px] font-semibold text-slate-400">
                  {formatTimestamp(item.created_at)}
                </span>
              </div>

              <p className="mt-3 text-sm font-semibold leading-7 text-slate-800">{item.summary}</p>

              <div className="mt-3 flex flex-wrap gap-2">
                {item.focus_concept_label && (
                  <span className="rounded-full border border-indigo-200 bg-white px-3 py-1 text-[11px] font-bold text-indigo-700">
                    Focus: {item.focus_concept_label}
                  </span>
                )}
                {item.strongest_gain_concept_label && (
                  <span className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-[11px] font-bold text-emerald-700">
                    Gain: {item.strongest_gain_concept_label}
                  </span>
                )}
                {item.strongest_drop_concept_label && (
                  <span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-[11px] font-bold text-amber-800">
                    Gap: {item.strongest_drop_concept_label}
                  </span>
                )}
              </div>

              <p className="mt-3 text-[11px] font-black uppercase tracking-[0.18em] text-slate-400">
                {item.action_label || 'Review latest evidence'}
              </p>
            </div>
          );
        })}
      </div>
    </section>
  );
}
