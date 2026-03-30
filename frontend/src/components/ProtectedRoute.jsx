import React from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';

import { useAuth } from '../context/AuthContext';
import { useUser } from '../context/UserContext';

const PROFILE_ONBOARDING_PATHS = ['/class-selection', '/subject-selection', '/learning-preferences'];
const DIAGNOSTIC_PATHS = ['/assessment-splash'];

const isTeacherRoute = (pathname) => pathname.startsWith('/teacher');
const isStudentAppRoute = (pathname) =>
  pathname.startsWith('/dashboard')
  || pathname.startsWith('/graph-path')
  || pathname.startsWith('/graph-briefing')
  || pathname.startsWith('/course/')
  || pathname.startsWith('/lesson/')
  || pathname.startsWith('/mastery-path')
  || pathname.startsWith('/profile')
  || pathname.startsWith('/quiz/')
  || pathname.startsWith('/module-quiz');

const FullScreenLoader = () => (
  <div className="flex min-h-screen items-center justify-center bg-slate-50">
    <div className="rounded-3xl border border-slate-200 bg-white px-8 py-6 shadow-sm">
      <p className="text-sm font-semibold text-slate-500">Loading your learning workspace...</p>
    </div>
  </div>
);

const ProtectedRoute = () => {
  const location = useLocation();
  const { token } = useAuth();
  const { isLoading, userData, studentData, diagnosticStatus } = useUser();

  if (!token) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (isLoading) {
    return <FullScreenLoader />;
  }

  if (isTeacherRoute(location.pathname) && userData?.role !== 'teacher') {
    return <Navigate to="/dashboard" replace />;
  }

  if (userData?.role === 'teacher') {
    if (isStudentAppRoute(location.pathname)) {
      return <Navigate to="/teacher/analytics" replace />;
    }
    if (PROFILE_ONBOARDING_PATHS.includes(location.pathname) || DIAGNOSTIC_PATHS.includes(location.pathname)) {
      return <Navigate to={isTeacherRoute(location.pathname) ? location.pathname : '/teacher/analytics'} replace />;
    }
    return <Outlet />;
  }

  if (!studentData?.has_profile) {
    if (PROFILE_ONBOARDING_PATHS.includes(location.pathname)) {
      return <Outlet />;
    }
    return <Navigate to="/class-selection" replace />;
  }

  const diagnosticComplete = Boolean(diagnosticStatus?.onboarding_complete);

  if (!diagnosticComplete) {
    if (DIAGNOSTIC_PATHS.includes(location.pathname)) {
      return <Outlet />;
    }
    return <Navigate to="/assessment-splash" replace />;
  }

  if (PROFILE_ONBOARDING_PATHS.includes(location.pathname) || DIAGNOSTIC_PATHS.includes(location.pathname)) {
    return <Navigate to="/dashboard" replace />;
  }

  return <Outlet />;
};

export default ProtectedRoute;
