import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useUser } from '../context/UserContext';
import { API_URL } from '../config/runtime';
import { parseJsonResponse } from '../services/api';
import { resolveStudentId, resolveUserId } from '../utils/sessionIdentity';

const LearningPreferences = () => {
  const navigate = useNavigate();
  const { token } = useAuth();
  const { userData, studentData, replaceLocalStudent } = useUser();

  const [selectedStyles, setSelectedStyles] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const styles = [
    {
      id: 'step_by_step',
      icon: '1',
      title: 'Step-by-step explanations',
      desc: "Focus on logic and order. We'll break down complex topics into bite-sized, sequential pieces.",
    },
    {
      id: 'examples_first',
      icon: 'Ex',
      title: 'Examples first',
      desc: "Learn by seeing how it's done. We'll show you solved problems before diving into the theory.",
    },
    {
      id: 'practice_heavy',
      icon: 'Q',
      title: 'Practice questions',
      desc: "Learn by doing. We'll give you challenges immediately to test your understanding as you go.",
    },
    {
      id: 'visual',
      icon: 'V',
      title: 'Visual breakdowns',
      desc: "Use diagrams and charts. We'll prioritize infographics, mind maps, and visual aids for learning.",
    },
  ];

  const toggleStyle = (id) => {
    if (selectedStyles.includes(id)) {
      setSelectedStyles(selectedStyles.filter((styleId) => styleId !== id));
      return;
    }

    if (selectedStyles.length < 2) {
      setSelectedStyles([...selectedStyles, id]);
    }
  };

  const handleContinue = async () => {
    if (selectedStyles.length === 0) {
      alert('Please select at least one learning style.');
      return;
    }

    setIsLoading(true);
    setErrorMsg('');

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000);

    try {
      const preferencesPayload = {
        explanation_depth: selectedStyles.includes('step_by_step') ? 'detailed' : 'standard',
        examples_first: selectedStyles.includes('examples_first'),
        pace: selectedStyles.includes('practice_heavy') ? 'fast' : 'normal',
      };

      const response = await fetch(`${API_URL}/students/profile`, {
        method: 'PUT',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ preferences: preferencesPayload }),
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      const savedProfile = await parseJsonResponse(
        response,
        'Failed to save your preferences. Please try again.',
      );
      const resolvedUserId =
        savedProfile?.user_id ||
        resolveUserId(studentData, userData) ||
        resolveStudentId(studentData, userData);

      if (resolvedUserId) {
        localStorage.setItem('mastery_student_id', resolvedUserId);
      }

      replaceLocalStudent({
        ...savedProfile,
        has_profile: true,
        student_id: resolvedUserId,
      });

      navigate('/assessment-splash');
    } catch (err) {
      console.error('Preferences Save Error:', err);
      if (err.name === 'AbortError') {
        setErrorMsg('Your learning data is still syncing. Please refresh in a moment.');
      } else {
        setErrorMsg(err.message);
      }
    } finally {
      clearTimeout(timeoutId);
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen font-sans p-8" style={{ backgroundColor: '#F9FAFB' }}>
      <div className="flex items-center gap-2 mb-16">
        <div
          className="w-8 h-8 rounded-lg flex items-center justify-center text-white font-bold shadow-md"
          style={{ backgroundColor: '#635BFF' }}
        >
          M
        </div>
        <span className="text-xl font-bold tracking-tight" style={{ color: '#1A1F36' }}>
          MasteryAI
        </span>
      </div>

      <div className="max-w-4xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-extrabold" style={{ color: '#111827' }}>
            How do you prefer to learn?
          </h1>
          <p className="mt-4 text-sm" style={{ color: '#6B7280' }}>
            Choose up to 2 styles that help you understand best. This helps us customize your mastery path.
          </p>
        </div>

        {errorMsg && (
          <div className="mb-8 p-4 bg-rose-50 border border-rose-200 text-rose-600 rounded-xl text-sm font-medium text-center">
            {errorMsg}
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mb-12">
          {styles.map((style) => {
            const isSelected = selectedStyles.includes(style.id);

            return (
              <div
                key={style.id}
                onClick={() => toggleStyle(style.id)}
                className={`p-6 rounded-[1.5rem] border-2 transition-all duration-200 bg-white cursor-pointer ${
                  isSelected ? 'shadow-lg' : 'border-transparent shadow-sm hover:border-slate-200'
                }`}
                style={{ borderColor: isSelected ? '#5850EC' : 'transparent' }}
              >
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center text-sm font-bold mb-4"
                  style={{ backgroundColor: isSelected ? '#EEF2FF' : '#F3F4F6' }}
                >
                  {style.icon}
                </div>
                <h3 className="text-lg font-bold mb-2" style={{ color: '#111827' }}>
                  {style.title}
                </h3>
                <p className="text-xs leading-relaxed" style={{ color: '#6B7280' }}>
                  {style.desc}
                </p>
              </div>
            );
          })}
        </div>

        <div className="border-t pt-8 flex items-center justify-between" style={{ borderColor: '#E5E7EB' }}>
          <button
            type="button"
            onClick={() => navigate('/subject-selection')}
            disabled={isLoading}
            className="flex items-center gap-2 font-bold transition-colors hover:opacity-70 text-sm"
            style={{ color: '#6B7280', cursor: 'pointer' }}
          >
            <span>&larr;</span> Back
          </button>

          <button
            onClick={handleContinue}
            disabled={isLoading || selectedStyles.length === 0}
            className="px-10 py-3.5 text-white font-bold rounded-xl shadow-xl transition-all transform active:scale-95 flex items-center gap-2 text-sm"
            style={{
              backgroundColor: isLoading || selectedStyles.length === 0 ? '#A3ACBF' : '#5850EC',
              boxShadow:
                isLoading || selectedStyles.length === 0 ? 'none' : '0 10px 15px -3px rgba(88, 80, 236, 0.3)',
              cursor: isLoading ? 'wait' : selectedStyles.length === 0 ? 'not-allowed' : 'pointer',
            }}
          >
            {isLoading ? 'Saving...' : 'Finish Setup'} <span>&rarr;</span>
          </button>
        </div>
      </div>
    </div>
  );
};

export default LearningPreferences;
