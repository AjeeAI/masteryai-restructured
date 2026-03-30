import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useUser } from '../context/UserContext';
import { Loader2, AlertCircle, ArrowRight, BrainCircuit } from 'lucide-react';

import AIExplanationArea from '../components/AIExplanationArea';
import { API_URL } from '../config/runtime';
import { resolveStudentId } from '../utils/sessionIdentity';

const ExplainMistakePage = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { token } = useAuth();
  const { studentData, userData } = useUser();
  const activeId = resolveStudentId(studentData, userData);

  const currentSubject = localStorage.getItem('active_subject') || studentData?.subjects?.[0] || 'math';
  const currentLevel = studentData?.sss_level || 'SSS3';
  const currentTerm = studentData?.current_term || 1;

  const apiUrl = API_URL;

  // We expect the previous page to pass these via route state
  const {
    question,
    studentAnswer,
    correctAnswer,
    topicId,
  } = location.state || {};

  // --- API STATES ---
  const [explanationData, setExplanationData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    // Safety check
    if (!question || !studentAnswer || !correctAnswer) {
      setError("Missing mistake context. Open this page from a real quiz or tutor remediation flow.");
      setIsLoading(false);
      return;
    }

    const fetchExplanation = async () => {
      setIsLoading(true);
      setError("");

      try {
        const response = await fetch(`${apiUrl}/tutor/explain-mistake`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            student_id: activeId,
            subject: currentSubject,
            sss_level: currentLevel,
            term: currentTerm,
            topic_id: topicId || null,
            question: question,
            student_answer: studentAnswer,
            correct_answer: correctAnswer
          })
        });

        if (!response.ok) throw new Error("Failed to fetch AI explanation.");

        const data = await response.json();
        
        // Map the backend response to the shape AIExplanationArea expects
        setExplanationData({
          explanationText: data.explanation,
          improvementTip: data.improvement_tip,
          // Storing original inputs so the component can display them if needed
          questionText: question,
          studentAnswer: studentAnswer,
          correctAnswer: correctAnswer
        });

      } catch (err) {
        setError(err.message);
      } finally {
        setIsLoading(false);
      }
    };

    fetchExplanation();
  }, [question, studentAnswer, correctAnswer, topicId, activeId, currentSubject, currentLevel, currentTerm, token, apiUrl]);


  return (
    <div className="min-h-screen bg-slate-50">
      <main className="max-w-7xl mx-auto px-4 py-6">
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
          <aside className="space-y-6">
            <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="mb-3 flex items-center gap-2 text-indigo-600">
                <BrainCircuit className="h-5 w-5" />
                <p className="text-xs font-black uppercase tracking-[0.2em]">Question context</p>
              </div>
              <h3 className="text-lg font-bold text-slate-900">{question || 'Unavailable question'}</h3>
              <div className="mt-5 space-y-3">
                <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4">
                  <p className="text-[10px] font-black uppercase tracking-[0.2em] text-rose-500">Your answer</p>
                  <p className="mt-2 text-sm leading-6 text-slate-700">{studentAnswer || 'Unavailable'}</p>
                </div>
                <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4">
                  <p className="text-[10px] font-black uppercase tracking-[0.2em] text-emerald-500">Correct answer</p>
                  <p className="mt-2 text-sm leading-6 text-slate-700">{correctAnswer || 'Unavailable'}</p>
                </div>
              </div>
              <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">Current scope</p>
                <p className="mt-2 text-sm font-semibold text-slate-800">
                  {currentLevel} {String(currentSubject || '').toUpperCase()} Term {currentTerm}
                </p>
                {topicId && <p className="mt-1 text-xs text-slate-500">Topic-linked remediation is enabled for this mistake.</p>}
              </div>
            </div>

            <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">Next move</p>
              <p className="mt-2 text-sm leading-7 text-slate-600">
                Use this explanation to repair the misconception, then return to the lesson or ask the tutor for a checkpoint question.
              </p>
              <div className="mt-4 flex flex-wrap gap-3">
                {topicId && (
                  <button
                    type="button"
                    onClick={() => navigate(`/lesson/${topicId}`)}
                    className="inline-flex items-center gap-2 rounded-2xl bg-indigo-600 px-4 py-3 text-sm font-bold text-white hover:bg-indigo-700"
                  >
                    Back to lesson
                    <ArrowRight className="h-4 w-4" />
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => navigate('/dashboard')}
                  className="rounded-2xl border border-slate-200 px-4 py-3 text-sm font-bold text-slate-700 hover:bg-slate-50"
                >
                  Dashboard
                </button>
              </div>
            </div>
          </aside>

          <div>
            {isLoading ? (
              <div className="bg-white rounded-2xl border border-slate-200 p-12 flex flex-col items-center justify-center min-h-[400px]">
                 <Loader2 className="w-10 h-10 text-indigo-600 animate-spin mb-4" />
                 <p className="text-slate-500 font-medium">AI Tutor is analyzing your mistake...</p>
              </div>
            ) : error ? (
              <div className="bg-rose-50 rounded-2xl border border-rose-100 p-8 flex flex-col items-center justify-center min-h-[400px] text-center">
                 <AlertCircle className="w-10 h-10 text-rose-500 mb-4" />
                 <p className="text-rose-700 font-bold mb-4">{error}</p>
                 <button onClick={() => navigate(-1)} className="text-rose-600 font-semibold hover:underline">← Go Back</button>
              </div>
            ) : (
              <AIExplanationArea explanationData={explanationData} />
            )}
          </div>
        </div>
      </main>
    </div>
  );
};

export default ExplainMistakePage;
