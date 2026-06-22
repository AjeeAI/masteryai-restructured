import React from 'react';
import { useNavigate } from 'react-router-dom';

const statusLabels = {
  current: 'Current',
  ready: 'Ready',
  mastered: 'Mastered',
  locked: 'Locked',
  unmapped: 'Pending',
  pending: 'Pending',
};

const badgeStyles = {
  current: 'bg-indigo-50 text-indigo-700 border-indigo-100',
  ready: 'bg-sky-50 text-sky-700 border-sky-100',
  mastered: 'bg-emerald-50 text-emerald-700 border-emerald-100',
  locked: 'bg-slate-100 text-slate-500 border-slate-200',
  unmapped: 'bg-amber-50 text-amber-700 border-amber-100',
  pending: 'bg-slate-100 text-slate-500 border-slate-200',
};

export default function CourseSidebar({ activeStep, subject = 'Subject', topics = [], level = 'Level' }) {
  const navigate = useNavigate();

  const completedCount = topics.filter((topic) => topic.status === 'mastered').length;
  const totalCount = topics.length > 0 ? topics.length : 1;
  const progressPercent = Math.round((completedCount / totalCount) * 100);

  return (
    <aside className="flex w-full flex-col h-full bg-white">
      {/* FIXED HEADER SECTION */}
      <div className="shrink-0 p-4 border-b border-slate-100">
        <button
          onClick={() => navigate('/dashboard')}
          className="mb-4 flex items-center gap-2 text-sm font-bold text-indigo-600 transition-colors hover:text-indigo-800"
        >
          <span>&larr;</span> Back to dashboard
        </button>

        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <p className="mb-1 text-[10px] font-black uppercase tracking-[0.16em] text-slate-400">Current syllabus</p>
          <h2 className="text-lg font-black capitalize text-slate-900">{level} {subject}</h2>
          
          <div className="mt-3 mb-2 flex items-center justify-between text-xs font-bold text-indigo-600">
            <span>{progressPercent}% complete</span>
            <span className="text-slate-400">{completedCount}/{topics.length} units</span>
          </div>
          
          <div className="h-1.5 overflow-hidden rounded-full bg-slate-200">
            <div
              className="h-full rounded-full bg-indigo-600 transition-all duration-700"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>
      </div>

      {/* SCROLLABLE LIST SECTION */}
      <div className="flex-1 overflow-y-auto p-4 scroll-smooth">
        <p className="mb-3 text-[10px] font-black uppercase tracking-[0.16em] text-slate-400">Lesson list</p>
        <div className="space-y-2 pb-6">
          {topics.length > 0 ? (
            topics.map((topic, index) => {
              const targetId = topic.topic_id || topic.id;
              const currentStatus = topic.status || 'pending';
              const isLocked = currentStatus === 'locked';
              const isMastered = currentStatus === 'mastered';
              const isActive = activeStep === targetId || currentStatus === 'current';
              const badgeStyle = badgeStyles[currentStatus] || badgeStyles.pending;

              return (
                <button
                  key={targetId || index}
                  type="button"
                  onClick={() => {
                    if (!isLocked && targetId) navigate(`/lesson/${targetId}`);
                  }}
                  disabled={isLocked || !targetId}
                  className={`flex w-full items-start gap-3 rounded-2xl border p-3 text-left transition ${
                    isLocked ? 'cursor-not-allowed opacity-70' : 'cursor-pointer'
                  } ${
                    isActive
                      ? 'border-indigo-200 bg-indigo-50'
                      : 'border-transparent bg-white hover:border-slate-200 hover:bg-slate-50'
                  }`}
                >
                  <div className={`mt-0.5 flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-2xl text-sm font-black ${
                    isMastered
                      ? 'bg-emerald-100 text-emerald-600'
                      : isActive
                        ? 'bg-indigo-600 text-white shadow-md shadow-indigo-200'
                        : isLocked
                          ? 'bg-slate-200 text-slate-500'
                          : 'bg-slate-100 text-slate-500'
                  }`}>
                    {isMastered ? 'OK' : isLocked ? 'L' : index + 1}
                  </div>

                  <div className="min-w-0 flex-1">
                    <h4 className={`line-clamp-2 text-[14px] font-bold leading-tight ${
                      isActive ? 'text-indigo-900' : 'text-slate-800'
                    }`}>
                      {topic.title || 'Untitled topic'}
                    </h4>
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <span className={`rounded-full border px-2 py-1 text-[10px] font-black uppercase tracking-[0.12em] ${badgeStyle}`}>
                        {statusLabels[currentStatus] || 'Pending'}
                      </span>
                      <span className="text-[11px] font-semibold text-slate-400">
                        {Math.round((topic.mastery_score || 0) * 100)}%
                      </span>
                    </div>
                  </div>
                </button>
              );
            })
          ) : (
            <p className="text-xs text-slate-400">Loading lessons...</p>
          )}
        </div>
      </div>
    </aside>
  );
}