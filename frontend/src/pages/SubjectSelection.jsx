import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useUser } from '../context/UserContext';
import { API_URL } from '../config/runtime';
import { fetchStudentProfileStatus, fetchUserProfile } from '../services/api';

const SubjectSelection = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { token } = useAuth();
  const { studentData, userData, replaceLocalStudent } = useUser();
  
  const [selectedSubjects, setSelectedSubjects] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [availableSubjects, setAvailableSubjects] = useState([]);
  const [isFetchingMetadata, setIsFetchingMetadata] = useState(true);
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    // --- FRONTEND DEMO MODE: Hardcoded Subjects ---
    setTimeout(() => {
      setAvailableSubjects([
        { id: 'math', label: 'MATHEMATICS', icon: '➕', description: 'Algebra, Geometry, and Data Analysis tailored to you.' },
        { id: 'english', label: 'ENGLISH STUDIES', icon: '📖', description: 'Grammar, Literature, and Creative Writing mastery.' },
        { id: 'civic', label: 'CIVIC EDUCATION', icon: '🌍', description: 'Civic rights, and History of modern society.' }
      ]);
      setIsFetchingMetadata(false);
    }, 600);
  }, []);

  const toggleSubject = (id) => {
    if (selectedSubjects.includes(id)) {
      setSelectedSubjects(selectedSubjects.filter((item) => item !== id));
    } else {
      setSelectedSubjects([...selectedSubjects, id]);
    }
  };

  const readErrorMessage = async (response, fallbackMessage) => {
    const errData = await response.json().catch(() => ({}));
    if (Array.isArray(errData?.detail)) {
      return errData.detail[0]?.msg || fallbackMessage;
    }
    return errData?.detail || fallbackMessage;
  };

  const resolveActiveId = async () => {
    const localId = localStorage.getItem('mastery_student_id');
    let activeId =
      studentData?.user_id ||
      studentData?.student_id ||
      userData?.user_id ||
      userData?.student_id ||
      userData?.id ||
      localId;

    if (!activeId) {
      const userMeData = await fetchUserProfile(token);
      activeId = userMeData?.user_id || userMeData?.id || null;
    }

    if (activeId) {
      localStorage.setItem('mastery_student_id', activeId);
    }

    return activeId;
  };

  const handleContinue = async () => {
    if (selectedSubjects.length === 0) {
      alert("Please select at least one subject to continue.");
      return;
    }

    setIsLoading(true);
    setErrorMsg("");

    try {
      const activeId = await resolveActiveId();

      if (!activeId) {
        throw new Error("User ID is missing. Please contact support or try logging in again.");
      }

      const grade = location.state?.grade || studentData?.sss_level || "SSS1";
      const term = parseInt(location.state?.term || studentData?.current_term || 1, 10);

      const headers = {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      };

      const profileStatus = await fetchStudentProfileStatus(token);
      const updatePayload = {
        sss_level: grade,
        current_term: term,
        subjects: selectedSubjects
      };

      const setupPayload = {
        student_id: activeId,
        sss_level: grade,
        term,
        subjects: selectedSubjects,
      };

      let response = await fetch(
        `${API_URL}${profileStatus?.has_profile ? '/students/profile' : '/students/profile/setup'}`,
        {
          method: profileStatus?.has_profile ? 'PUT' : 'POST',
          headers,
          body: JSON.stringify(profileStatus?.has_profile ? updatePayload : setupPayload),
        }
      );

      if (!response.ok && profileStatus?.has_profile && response.status === 404) {
        response = await fetch(`${API_URL}/students/profile/setup`, {
          method: 'POST',
          headers,
          body: JSON.stringify(setupPayload),
        });
      } else if (!response.ok && !profileStatus?.has_profile) {
        const errorMessage = await readErrorMessage(response, 'Failed to save your subjects.');
        if (String(errorMessage).toLowerCase().includes('already exists')) {
          response = await fetch(`${API_URL}/students/profile`, {
            method: 'PUT',
            headers,
            body: JSON.stringify(updatePayload),
          });
        }
      }

      if (!response.ok) {
        throw new Error(await readErrorMessage(response, 'Failed to save your subjects.'));
      }

      const savedProfile = await response.json();
      const normalizedStudent = {
        ...savedProfile,
        has_profile: false,
        student_id: savedProfile?.user_id || activeId,
      };

      localStorage.setItem('mastery_student_id', normalizedStudent.student_id);
      replaceLocalStudent(normalizedStudent);
      navigate('/learning-preferences');

    } catch (err) {
      console.error("Subject Save Error:", err);
      setErrorMsg(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen font-sans p-8" style={{ backgroundColor: '#F9FAFB' }}>
      <div className="flex items-center gap-2 mb-16">
        <div className="w-8 h-8 rounded-lg flex items-center justify-center text-white font-bold shadow-md" style={{ backgroundColor: '#635BFF' }}>M</div>
        <span className="text-xl font-bold tracking-tight" style={{ color: '#1A1F36' }}>MasteryAI</span>
      </div>

      <div className="max-w-6xl mx-auto text-center mb-12">
        <h1 className="text-4xl font-extrabold mb-4" style={{ color: '#111827' }}>Which subjects do you want help with?</h1>
        <p className="max-w-2xl mx-auto text-lg" style={{ color: '#6B7280' }}>
          Pick the subjects you'd like to focus on for SSS1-SSS3. You can personalize your learning path for each choice later.
        </p>
      </div>

      {errorMsg && (
        <div className="mb-8 max-w-xl mx-auto p-4 bg-rose-50 border border-rose-200 text-rose-600 rounded-xl text-sm font-medium text-center animate-bounce">
          {errorMsg}
        </div>
      )}

      {isFetchingMetadata ? (
        <div className="text-center font-bold text-[#5850EC] animate-pulse mb-16">
          Fetching available subjects...
        </div>
      ) : (
        <div className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-6 mb-16">
          {availableSubjects.map((subject) => {
            const isSelected = selectedSubjects.includes(subject.id);
            return (
              <div
                key={subject.id}
                onClick={() => toggleSubject(subject.id)}
                className={`relative p-8 rounded-[2rem] border-2 transition-all duration-300 cursor-pointer bg-white flex flex-col items-start min-h-[280px]
                  ${isSelected ? 'shadow-2xl scale-[1.02]' : 'border-transparent shadow-sm hover:shadow-md'}`}
                style={{ borderColor: isSelected ? '#5850EC' : 'transparent' }}
              >
                {isSelected && (
                  <div className="absolute top-6 right-6 rounded-full w-6 h-6 flex items-center justify-center text-[10px] border-2 border-white shadow-sm text-white" style={{ backgroundColor: '#5850EC' }}>✓</div>
                )}
                <div className="w-14 h-14 rounded-2xl flex items-center justify-center text-2xl mb-6 shadow-inner" style={{ backgroundColor: isSelected ? '#EEF2FF' : '#F3F4F6' }}>
                  {subject.icon}
                </div>
                <h3 className="text-xl font-bold mb-3" style={{ color: '#111827' }}>{subject.label}</h3>
                <p className="text-sm leading-relaxed mb-6" style={{ color: '#6B7280' }}>{subject.description}</p>
                <div className="mt-auto px-4 py-1.5 rounded-full text-[10px] font-bold uppercase tracking-wider flex items-center gap-1.5" style={{ backgroundColor: '#EEF2FF', color: '#5850EC' }}>
                  <span>⚡</span> Adaptive Enabled
                </div>
              </div>
            );
          })}
        </div>
      )}

      <div className="max-w-6xl mx-auto border-t pt-8 flex items-center justify-between" style={{ borderColor: '#E5E7EB' }}>
        <button onClick={() => navigate(-1)} disabled={isLoading} className="flex items-center gap-2 font-bold transition-colors hover:opacity-70 disabled:opacity-50" style={{ color: '#6B7280' }}>
          <span>←</span> Back
        </button>
        <button 
          onClick={handleContinue}
          disabled={isLoading || selectedSubjects.length === 0}
          className="px-10 py-4 text-white font-bold rounded-2xl shadow-xl transition-all transform active:scale-95 flex items-center gap-2"
          style={{ 
            backgroundColor: (isLoading || selectedSubjects.length === 0) ? '#A3ACBF' : '#5850EC',
            boxShadow: (isLoading || selectedSubjects.length === 0) ? 'none' : '0 10px 15px -3px rgba(88, 80, 236, 0.3)',
            cursor: isLoading ? 'wait' : (selectedSubjects.length === 0 ? 'not-allowed' : 'pointer')
          }}
        >
          {isLoading ? 'Saving...' : 'Continue'} <span>→</span>
        </button>
      </div>
    </div>
  );
};

export default SubjectSelection;
