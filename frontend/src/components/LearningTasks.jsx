import React from 'react';
import { ArrowRight, CalendarCheck2, GitBranch, Inbox, Route, ShieldAlert, Target } from 'lucide-react';

const TONE_STYLES = {
  indigo: {
    chip: 'border-indigo-200 bg-indigo-50 text-indigo-700',
    button: 'bg-indigo-600 text-white hover:bg-indigo-700',
    icon: GitBranch,
  },
  amber: {
    chip: 'border-amber-200 bg-amber-50 text-amber-700',
    button: 'bg-amber-500 text-white hover:bg-amber-600',
    icon: ShieldAlert,
  },
  slate: {
    chip: 'border-slate-200 bg-slate-50 text-slate-700',
    button: 'bg-slate-900 text-white hover:bg-slate-800',
    icon: Route,
  },
  emerald: {
    chip: 'border-emerald-200 bg-emerald-50 text-emerald-700',
    button: 'bg-emerald-600 text-white hover:bg-emerald-700',
    icon: Target,
  },
};

const TaskItem = ({ task }) => {
  const tone = TONE_STYLES[task.tone] || TONE_STYLES.indigo;
  const Icon = tone.icon;

  return (
    <div className="mb-3 rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className={`inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.18em] ${tone.chip}`}>
            <Icon className="h-3.5 w-3.5" />
            {task.badge}
          </div>
          <h4 className="mt-3 text-sm font-bold text-slate-900">{task.title}</h4>
          <p className="mt-2 text-xs leading-6 text-slate-600">{task.subtext}</p>
        </div>
        <button
          type="button"
          onClick={task.onClick}
          disabled={!task.onClick}
          className={`inline-flex shrink-0 items-center gap-2 rounded-xl px-3 py-2 text-xs font-bold transition-colors ${
            task.onClick ? tone.button : 'cursor-not-allowed bg-slate-200 text-slate-500'
          }`}
        >
          {task.actionLabel}
          <ArrowRight className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
};

export default function LearningTasks({ tasks = [] }) {
  return (
    <div className="bg-white p-6 rounded-3xl shadow-sm border border-gray-100 flex flex-col h-full">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-bold text-gray-900 flex items-center gap-2">
          <CalendarCheck2 className="w-5 h-5 text-indigo-600" />
          Next Actions
        </h3>
        <span className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">
          Graph guided
        </span>
      </div>

      <div className="flex-1 overflow-y-auto pr-1">
        {tasks.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-slate-400 bg-slate-50 rounded-2xl border border-dashed border-slate-200">
            <Inbox className="w-8 h-8 mb-2 opacity-50" />
            <p className="text-sm font-medium">No graph-backed action is available yet.</p>
          </div>
        ) : (
          tasks.map((task) => <TaskItem key={task.id} task={task} />)
        )}
      </div>
    </div>
  );
}
