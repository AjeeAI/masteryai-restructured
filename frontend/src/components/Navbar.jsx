import { useMemo, useState, useRef, useEffect } from 'react';
import { NavLink } from 'react-router-dom';
import NotificationModal from './NotificationModal';
import { useUser } from '../context/UserContext';
import { readLatestGraphIntervention } from '../services/graphIntervention';
import { resolveStudentId } from '../utils/sessionIdentity';

const Navbar = () => {
  const [showNotifications, setShowNotifications] = useState(false);
  const notifRef = useRef(null);
  const { userData, studentData } = useUser();
  const activeId = resolveStudentId(studentData, userData);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (notifRef.current && !notifRef.current.contains(event.target)) {
        setShowNotifications(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const displayName = userData
    ? `${userData.first_name || ''} ${userData.last_name || ''}`.trim()
    : 'Student';

  const displayLevel = studentData?.sss_level || 'Student';
  const displayLeague = studentData?.league_name || 'Current League';
  const avatarUrl = userData?.avatar_url || null;
  const latestIntervention = useMemo(
    () => (activeId ? readLatestGraphIntervention(activeId) : null),
    [activeId],
  );

  const getInitials = (name) => {
    if (!name || name === 'Student') return 'U';
    const nameParts = name.trim().split(' ');
    if (nameParts.length >= 2) {
      return `${nameParts[0][0]}${nameParts[nameParts.length - 1][0]}`.toUpperCase();
    }
    return nameParts[0][0].toUpperCase();
  };

  return (
    <nav className="sticky top-0 z-50 w-full border-b border-slate-200 bg-white shadow-sm">
      <div className="mx-auto flex max-w-[1440px] items-center gap-3 px-3 py-3 sm:gap-4 sm:px-5">
        <div className="flex min-w-0 flex-1 items-center justify-between gap-3">
          <NavLink to="/dashboard" className="flex min-w-0 flex-shrink items-center gap-2 transition-opacity hover:opacity-80">
            <div className="rounded-xl bg-indigo-600 p-1.5 text-white shadow-md sm:p-1.5">
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
              </svg>
            </div>
            <span className="truncate text-base font-black tracking-tight text-indigo-700 sm:text-xl">MasteryAI</span>
          </NavLink>

          <div className="relative hidden w-64 max-w-full flex-shrink-0 xl:block">
            <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400">
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
            </span>
            <input
              type="text"
              placeholder="Search topics..."
              className="w-full rounded-full border border-slate-200 bg-slate-50 py-2 pl-10 pr-4 text-sm shadow-inner transition-all focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
        </div>

        <div className="flex items-center gap-3 sm:gap-5">
          <div className="relative" ref={notifRef}>
            <button
              onClick={() => setShowNotifications(!showNotifications)}
              className={`relative transition-colors ${showNotifications ? 'text-indigo-600' : 'text-slate-400 hover:text-slate-600'}`}
            >
              <svg className="h-5 w-5 sm:h-6 sm:w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" /></svg>
              {latestIntervention ? <span className="absolute right-1 top-0 h-2 w-2 rounded-full border border-white bg-rose-500"></span> : null}
            </button>
            {showNotifications && <NotificationModal onClose={() => setShowNotifications(false)} />}
          </div>

          <div className="hidden h-7 w-px bg-slate-200 sm:block"></div>

          <NavLink to="/profile" className="group flex flex-shrink-0 cursor-pointer items-center gap-2 sm:gap-3">
            <div className="hidden text-right lg:block">
              <p className="text-sm font-bold text-slate-800 transition-colors group-hover:text-indigo-600">
                {displayName}
              </p>
              <p className="mt-0.5 inline-block rounded-full bg-indigo-50 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-indigo-500">
                {displayLevel} • {displayLeague}
              </p>
            </div>

            <div className="hidden rounded-full bg-indigo-50 px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.14em] text-indigo-600 sm:inline-flex lg:hidden">
              {displayLevel}
            </div>

            <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center overflow-hidden rounded-full border border-slate-200 bg-indigo-50 shadow-sm transition-colors group-hover:border-indigo-300 sm:h-10 sm:w-10">
              {avatarUrl ? (
                <img src={avatarUrl} alt="Profile" className="h-full w-full object-cover" />
              ) : (
                <span className="text-sm font-black tracking-widest text-indigo-600">
                  {getInitials(displayName)}
                </span>
              )}
            </div>
          </NavLink>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
