import React from 'react';
import { NavLink } from 'react-router-dom';
import { BarChart3, MonitorPlay, Presentation } from 'lucide-react';
import { useUser } from '../context/UserContext';

const menuItems = [
  { id: 'analytics', icon: BarChart3, label: 'Concept Analytics', path: '/teacher/analytics' },
  { id: 'presentation-hub', icon: Presentation, label: 'Presentation Hub', path: '/presentation-hub' },
  { id: 'demo-mode', icon: MonitorPlay, label: 'Demo Mode', path: '/demo-mode' },
];

const TeacherSidebar = () => {
  const { userData } = useUser();
  const displayName = `${userData?.first_name || ''} ${userData?.last_name || ''}`.trim() || 'Teacher';
  const displayEmail = userData?.email || 'Teacher session';

  return (
    <aside className="sticky top-0 flex h-screen w-64 flex-col border-r border-slate-200 bg-white">
      <div className="flex items-center gap-3 border-b border-slate-100 p-6">
        <div className="rounded-lg bg-indigo-600 p-1.5 text-white">
          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
          </svg>
        </div>
        <span className="text-xl font-bold tracking-tight text-indigo-900">MasteryAI</span>
      </div>

      <nav className="flex-1 space-y-1 p-4">
        {menuItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.id}
              to={item.path}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-indigo-50 text-indigo-700'
                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                }`
              }
            >
              <Icon className="h-5 w-5" />
              {item.label}
            </NavLink>
          );
        })}
      </nav>

      <div className="m-2 flex items-center gap-3 rounded-xl border-t border-slate-100 p-4 transition-colors hover:bg-slate-50">
        <img src="https://i.pravatar.cc/150?img=47" alt="Teacher" className="h-10 w-10 rounded-full border border-slate-200" />
        <div>
          <p className="text-sm font-bold leading-tight text-slate-800">{displayName}</p>
          <p className="text-xs text-slate-500">{displayEmail}</p>
        </div>
      </div>
    </aside>
  );
};

export default TeacherSidebar;
