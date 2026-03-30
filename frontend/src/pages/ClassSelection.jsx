import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useUser } from '../context/UserContext';
import { API_URL } from '../config/runtime';
import { fetchStudentProfileStatus, fetchUserProfile } from '../services/api';

const ClassSelection = () => {
  const [selectedGrade, setSelectedGrade] = useState('');
  const [selectedTerm, setSelectedTerm] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isFetchingMetadata, setIsFetchingMetadata] = useState(true);
  const [errorMsg, setErrorMsg] = useState(""); 
  
  const navigate = useNavigate();
  const { token } = useAuth();
  
  const { studentData, userData, replaceLocalStudent } = useUser(); 

  useEffect(() => {
    // Simulated fetch for available grades
    setTimeout(() => {
      setAvailableGrades([
        { id: 'SSS1', label: 'Grade 10', icon: '📖' },
        { id: 'SSS2', label: 'Grade 11', icon: '📘' },
        { id: 'SSS3', label: 'Grade 12', icon: '🎓' },
      ]);
      setAvailableTerms([1, 2, 3]);
      setIsFetchingMetadata(false);
    }, 600);
  }, []);

  const [availableGrades, setAvailableGrades] = useState([]);
  const [availableTerms, setAvailableTerms] = useState([]);

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
    if (!selectedGrade || !selectedTerm) {
      alert("Please select both your grade and your current term.");
      return;
    }

    setIsLoading(true);
    setErrorMsg("");

    try {
      const activeId = await resolveActiveId();

      if (!activeId) {
        throw new Error("User ID is missing. Please contact support or try logging in again.");
      }

      const headers = {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      };

      const termValue = parseInt(selectedTerm, 10);
      const profileStatus = await fetchStudentProfileStatus(token);
      const existingSubjects = Array.isArray(studentData?.subjects) ? studentData.subjects : [];

      const updatePayload = {
        sss_level: selectedGrade,
        current_term: termValue,
        subjects: existingSubjects,
      };

      const setupPayload = {
        student_id: activeId,
        sss_level: selectedGrade,
        term: termValue,
        subjects: existingSubjects,
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
        const errorMessage = await readErrorMessage(response, 'Failed to create your class profile.');
        if (String(errorMessage).toLowerCase().includes('already exists')) {
          response = await fetch(`${API_URL}/students/profile`, {
            method: 'PUT',
            headers,
            body: JSON.stringify(updatePayload),
          });
        }
      }

      if (!response.ok) {
        throw new Error(await readErrorMessage(response, 'Failed to save your class settings.'));
      }

      const savedProfile = await response.json();
      const normalizedStudent = {
        ...savedProfile,
        has_profile: false,
        student_id: savedProfile?.user_id || activeId,
      };

      localStorage.setItem('mastery_student_id', normalizedStudent.student_id);
      replaceLocalStudent(normalizedStudent);

      navigate('/subject-selection', { 
        state: { grade: normalizedStudent.sss_level, term: normalizedStudent.current_term } 
      });

    } catch (err) {
      console.error("Setup Error:", err);
      setErrorMsg(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen font-sans p-8" style={{ backgroundColor: '#F7FAFC' }}>
      <div className="flex items-center gap-2 mb-16">
        <div className="w-8 h-8 rounded-lg flex items-center justify-center text-white font-bold shadow-md" style={{ backgroundColor: '#635BFF' }}>M</div>
        <span className="text-xl font-bold tracking-tight" style={{ color: '#1A1F36' }}>MasteryAI</span>
      </div>

      <div className="max-w-4xl mx-auto text-center">
        <h1 className="text-4xl font-extrabold mb-4" style={{ color: '#1A1F36' }}>Tell us about your class</h1>
        <p className="mb-12 max-w-md mx-auto leading-relaxed" style={{ color: '#4F5668' }}>
          Select your current grade level to help us personalize your learning path.
        </p>

        {errorMsg && (
          <div className="mb-8 max-w-xl mx-auto p-4 bg-rose-50 border border-rose-200 text-rose-600 rounded-xl text-sm font-medium">
            Error: {errorMsg}
          </div>
        )}

        {isFetchingMetadata ? (
          <div className="mb-12 text-[#635BFF] font-bold animate-pulse">Loading curriculum levels...</div>
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-12">
              {availableGrades.map((grade) => {
                const isSelected = selectedGrade === grade.id;
                return (
                  <div
                    key={grade.id}
                    onClick={() => setSelectedGrade(grade.id)}
                    className={`relative p-8 rounded-[2.5rem] border-2 transition-all duration-300 cursor-pointer bg-white flex flex-col items-center ${isSelected ? 'shadow-2xl scale-[1.02]' : 'border-transparent shadow-sm hover:shadow-md'}`}
                    style={{ borderColor: isSelected ? '#635BFF' : 'transparent' }}
                  >
                    {isSelected && (
                      <div className="absolute top-4 right-6 text-white rounded-full w-6 h-6 flex items-center justify-center text-[10px] shadow-lg border-2 border-white" style={{ backgroundColor: '#635BFF' }}>✓</div>
                    )}
                    <div className="w-20 h-20 rounded-full flex items-center justify-center text-3xl mb-6 transition-colors" style={{ backgroundColor: isSelected ? '#635BFF' : '#F7FAFC', color: isSelected ? '#FFFFFF' : '#635BFF' }}>
                      {grade.icon}
                    </div>
                    <h3 className="text-2xl font-bold" style={{ color: '#1A1F36' }}>{grade.id}</h3>
                    <p className="font-medium mb-2" style={{ color: '#A3ACBF' }}>{grade.label}</p>
                  </div>
                );
              })}
            </div>

            <div className="bg-white p-10 rounded-[2.5rem] shadow-sm border max-w-xl mx-auto mb-10" style={{ borderColor: '#E3E8EE' }}>
              <div className="flex items-center gap-3 font-semibold mb-5 justify-center" style={{ color: '#4F566B' }}>
                <span className="text-xl">📅</span> Which term are you currently in?
              </div>
              <div className="relative">
                <select 
                  value={selectedTerm}
                  onChange={(e) => setSelectedTerm(e.target.value)}
                  className="w-full p-4 rounded-2xl border outline-none transition-all appearance-none cursor-pointer bg-[#F7FAFC] border-[#E3E8EE] text-[#4F566B]"
                >
                  <option value="">Select Current Term</option>
                  {availableTerms.map(term => (
                    <option key={term} value={term}>Term {term}</option>
                  ))}
                </select>
                <div className="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none text-[#A3ACBF]">
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7"></path></svg>
                </div>
              </div>
            </div>
          </>
        )}

        <button 
          onClick={handleContinue}
          disabled={isLoading || !selectedGrade || !selectedTerm} 
          className={`w-full max-w-xl py-5 text-white text-lg font-bold rounded-2xl shadow-xl transition-all transform ${!isLoading && 'active:scale-[0.97]'}`}
          style={{ 
            backgroundColor: (isLoading || !selectedGrade || !selectedTerm) ? '#A3ACBF' : '#635BFF',
            cursor: isLoading ? 'wait' : 'pointer'
          }}
        >
          {isLoading ? 'Saving...' : 'Continue'}
        </button>
      </div>
    </div>
  );
};

export default ClassSelection;
