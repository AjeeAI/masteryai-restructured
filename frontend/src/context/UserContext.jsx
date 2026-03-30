import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { useAuth } from './AuthContext';
import {
  fetchDiagnosticStatus,
  fetchStudentProfile,
  fetchStudentProfileStatus,
  fetchUserProfile,
} from '../services/api';

const UserContext = createContext();

const PROFILE_ONBOARDING_PATHS = [
  '/signup',
  '/register',
  '/login',
  '/class-selection',
  '/subject-selection',
  '/learning-preferences',
];

const DIAGNOSTIC_PATHS = ['/assessment-splash'];

const isOnboardingPath = (pathname) =>
  PROFILE_ONBOARDING_PATHS.includes(pathname) || DIAGNOSTIC_PATHS.includes(pathname);

export const UserProvider = ({ children }) => {
  const { token } = useAuth();
  const [userData, setUserData] = useState(null);
  const [studentData, setStudentData] = useState(null);
  const [diagnosticStatus, setDiagnosticStatus] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  const replaceLocalUser = useCallback((nextUserData) => {
    setUserData(nextUserData || null);
  }, []);

  const updateLocalUser = useCallback((nextUserData) => {
    setUserData((prev) => ({ ...(prev || {}), ...(nextUserData || {}) }));
  }, []);

  const replaceLocalStudent = useCallback((nextStudentData) => {
    setStudentData(nextStudentData || null);
  }, []);

  const updateLocalStudent = useCallback((nextStudentData) => {
    setStudentData((prev) => ({ ...(prev || {}), ...(nextStudentData || {}) }));
  }, []);

  const refreshDiagnostic = useCallback(
    async (studentId) => {
      if (!token || !studentId) {
        setDiagnosticStatus(null);
        return null;
      }
      const status = await fetchDiagnosticStatus(token, studentId);
      setDiagnosticStatus(status);
      return status;
    },
    [token],
  );

  const refreshUserContext = useCallback(async () => {
    if (!token) {
      setUserData(null);
      setStudentData(null);
      setDiagnosticStatus(null);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    try {
      const userResponse = await fetchUserProfile(token);
      const profileStatus = await fetchStudentProfileStatus(token);

      setUserData(userResponse);

      const resolvedUserId = profileStatus?.user_id || userResponse?.user_id || null;
      if (resolvedUserId) {
        localStorage.setItem('mastery_student_id', resolvedUserId);
      }

      if (userResponse?.role === 'teacher') {
        setStudentData(null);
        setDiagnosticStatus(null);
        return;
      }

      if (profileStatus?.has_profile) {
        const studentResponse = await fetchStudentProfile(token);
        const normalizedStudent = {
          ...studentResponse,
          has_profile: true,
          student_id:
            studentResponse?.student_id ||
            studentResponse?.user_id ||
            resolvedUserId,
        };
        if (normalizedStudent?.student_id) {
          localStorage.setItem('mastery_student_id', normalizedStudent.student_id);
        }
        setStudentData(normalizedStudent);
        await refreshDiagnostic(normalizedStudent.student_id);
      } else {
        setStudentData({
          has_profile: false,
          user_id: resolvedUserId,
          student_id: resolvedUserId,
          subjects: [],
        });
        setDiagnosticStatus(null);

        if (!isOnboardingPath(window.location.pathname)) {
          window.location.href = '/class-selection';
        }
      }
    } catch (error) {
      console.warn('UserContext refresh skipped:', error?.message || error);
    } finally {
      setIsLoading(false);
    }
  }, [refreshDiagnostic, token]);

  useEffect(() => {
    void refreshUserContext();
  }, [refreshUserContext]);

  return (
    <UserContext.Provider
      value={{
        userData,
        studentData,
        diagnosticStatus,
        isLoading,
        replaceLocalUser,
        updateLocalUser,
        replaceLocalStudent,
        updateLocalStudent,
        refreshDiagnosticStatus: refreshDiagnostic,
        refreshUserContext,
      }}
    >
      {children}
    </UserContext.Provider>
  );
};

export const useUser = () => useContext(UserContext);
