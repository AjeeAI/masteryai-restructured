import React, { useMemo } from 'react';
import { AlertCircle, Bell, BrainCircuit, GitBranch } from 'lucide-react';
import { useUser } from '../context/UserContext';
import { readLatestGraphIntervention } from '../services/graphIntervention';
import { resolveStudentId } from '../utils/sessionIdentity';

const formatRelativeTime = (timestamp) => {
  const value = Number(timestamp || 0);
  if (!value) return 'Recently';
  const minutes = Math.max(1, Math.round((Date.now() - value) / 60000));
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? '' : 's'} ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? '' : 's'} ago`;
  const days = Math.round(hours / 24);
  return `${days} day${days === 1 ? '' : 's'} ago`;
};

const NotificationModal = ({ onClose }) => {
  const { userData, studentData } = useUser();
  const activeId = resolveStudentId(studentData, userData);
  const latestIntervention = useMemo(
    () => (activeId ? readLatestGraphIntervention(activeId) : null),
    [activeId],
  );

  const recommendationStory = latestIntervention?.payload?.recommendation_story || null;
  const nextStep = latestIntervention?.payload?.next_step || null;
  const recentEvidence = latestIntervention?.payload?.recent_evidence || null;

  const notifications = latestIntervention ? [
    {
      id: 'graph-intervention',
      icon: GitBranch,
      tone: 'bg-indigo-100 text-indigo-600',
      title: recommendationStory?.headline || 'Graph intervention updated',
      body: recommendationStory?.supporting_reason || nextStep?.reason || recentEvidence?.summary || 'A new next step is available.',
      timestamp: formatRelativeTime(latestIntervention.updated_at),
    },
    recentEvidence?.summary ? {
      id: 'recent-evidence',
      icon: BrainCircuit,
      tone: 'bg-emerald-100 text-emerald-600',
      title: 'Latest evidence recorded',
      body: recentEvidence.summary,
      timestamp: formatRelativeTime(latestIntervention.updated_at),
    } : null,
  ].filter(Boolean) : [];

  return (
    <div className="absolute right-0 mt-4 w-80 bg-white rounded-2xl shadow-xl border border-slate-100 overflow-hidden z-50 animate-in fade-in slide-in-from-top-2 duration-200">
      <div className="p-4 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
        <h3 className="font-bold text-slate-800">Notifications</h3>
        <span className="text-[10px] font-bold text-indigo-700 bg-indigo-100 px-2 py-1 rounded-full uppercase tracking-wider">
          {notifications.length > 0 ? `${notifications.length} New` : 'Live'}
        </span>
      </div>

      <div className="max-h-[320px] overflow-y-auto">
        {notifications.length === 0 ? (
          <div className="p-6 text-center text-slate-400">
            <Bell className="mx-auto mb-3 h-8 w-8" />
            <p className="text-sm font-semibold">No live notifications yet.</p>
            <p className="mt-2 text-xs leading-6 text-slate-500">
              Quiz results, tutor checkpoints, and graph interventions will appear here when they happen.
            </p>
          </div>
        ) : (
          notifications.map((item) => {
            const Icon = item.icon;
            return (
              <div
                key={item.id}
                onClick={onClose}
                className="p-4 border-b border-slate-50 hover:bg-slate-50 transition-colors cursor-pointer flex gap-3"
              >
                <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${item.tone}`}>
                  <Icon className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-sm text-slate-800 font-bold">{item.title}</p>
                  <p className="text-xs text-slate-500 mt-0.5 leading-relaxed">{item.body}</p>
                  <p className="text-[10px] text-slate-400 mt-2 font-bold uppercase tracking-widest">{item.timestamp}</p>
                </div>
              </div>
            );
          })
        )}
      </div>

      <div className="p-3 text-center border-t border-slate-100 bg-slate-50/50">
        <button
          onClick={onClose}
          className="text-xs font-bold text-indigo-600 hover:text-indigo-800 transition-colors"
        >
          Close
        </button>
      </div>
    </div>
  );
};

export default NotificationModal;
