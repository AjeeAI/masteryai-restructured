import React, { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useUser } from '../context/UserContext';
import { useQuery } from '@tanstack/react-query';
import CourseSidebar from '../components/CourseSidebar';
import { Menu, MessageSquare } from 'lucide-react';

import LessonContent from '../components/lesson/LessonContent';
import AITutorPanel from '../components/tutor/AITutorPanel';

import { API_URL as RUNTIME_API_URL } from '../config/runtime';
import { resolveStudentId } from '../utils/sessionIdentity';
import { useActivityTracker } from '../hooks/useActivityTracker';

const API_URL = RUNTIME_API_URL;
const safeArray = (value) => (Array.isArray(value) ? value : []);

const LessonPage = () => {
  const navigate = useNavigate();
  const { topicId } = useParams(); 
  const { token } = useAuth();
  const { studentData, userData } = useUser();
  const activeId = resolveStudentId(studentData, userData);

  const currentSubject = localStorage.getItem('active_subject') || studentData?.subjects?.[0] || 'math';
  const currentLevel = studentData?.sss_level || 'SSS1';
  const currentTerm = studentData?.current_term || 1;

  // --- UI STATE ---
  const [isSidebarOpen, setIsSidebarOpen] = useState(window.innerWidth > 1024);
  const [isChatOpen, setIsChatOpen] = useState(window.innerWidth > 1280); 
  const [isChatMaximized, setIsChatMaximized] = useState(false);

  useActivityTracker(
    activeId, 
    token, 
    'tutor_session', 
    topicId, 
    currentSubject, 
    currentTerm
  );

  // 🔥 Upgraded to TanStack Query
  const { data: cockpitData, isLoading } = useQuery({
    // The query key ensures unique caching per topic and student
    queryKey: ['lessonCockpit', activeId, currentSubject, currentLevel, currentTerm, topicId],
    queryFn: async () => {
      const response = await fetch(`${API_URL}/learning/lesson/cockpit`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          student_id: activeId, subject: currentSubject,
          sss_level: currentLevel, term: currentTerm,
          topic_id: topicId, preferences: studentData?.preferences || {}
        })
      });

      if (!response.ok) throw new Error('Failed to load lesson cockpit.');
      return response.json();
    },
    // Only run if we have the critical identifiers
    enabled: !!(activeId && token && topicId),
    // Cache the data for 5 minutes (adjust as needed)
    staleTime: 1000 * 60 * 5 
  });

  // Extract data safely based on TanStack's response
  const bootstrap = cockpitData?.tutor_bootstrap || null;
  const sidebarTopics = safeArray(cockpitData?.topics);

  return (
    <div className="flex bg-slate-50 h-[calc(100vh-64px)] overflow-hidden relative">
      
      {/* MOBILE SIDEBAR OVERLAY */}
      {isSidebarOpen && (
        <div 
          className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-40 lg:hidden animate-in fade-in duration-200"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}

      {/* SIDEBAR */}
      <div className={`bg-white border-r border-slate-200 transition-all duration-300 flex-shrink-0 fixed inset-y-0 left-0 z-50 lg:relative lg:z-auto ${
        isSidebarOpen 
          ? 'w-[280px] sm:w-72 translate-x-0 shadow-2xl lg:shadow-none' 
          : 'w-0 -translate-x-full lg:translate-x-0 overflow-hidden'
      }`}>
        <CourseSidebar activeStep={topicId} subject={currentSubject} level={currentLevel} topics={sidebarTopics} />
      </div>

      {/* MAIN CONTENT AREA */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <div className="h-14 border-b border-slate-200 bg-white flex items-center justify-between px-4 flex-shrink-0">
          <button onClick={() => setIsSidebarOpen(!isSidebarOpen)} className="p-2 hover:bg-slate-100 rounded-lg text-slate-500 transition-colors flex items-center gap-2">
            <Menu size={20} />
            <span className="hidden sm:inline text-xs font-bold uppercase tracking-wider">Syllabus</span>
          </button>
          {!isChatOpen && (
            <button onClick={() => setIsChatOpen(true)} className="p-2 hover:bg-indigo-50 rounded-lg text-indigo-600 transition-colors flex items-center gap-2">
              <span className="hidden sm:inline text-xs font-bold uppercase tracking-wider">AI Tutor</span>
              <MessageSquare size={20} />
            </button>
          )}
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-8 md:px-12 scroll-smooth">
          <div className="max-w-3xl mx-auto">
            {isLoading ? (
               <div className="animate-pulse space-y-8 mt-10">
                 <div className="h-8 bg-slate-200 rounded w-1/2"></div>
                 <div className="h-4 bg-slate-200 rounded w-full"></div>
                 <div className="h-4 bg-slate-200 rounded w-5/6"></div>
                 <div className="aspect-video bg-slate-200 rounded-3xl w-full"></div>
               </div>
            ) : (
              <>
                <LessonContent lessonData={bootstrap?.lesson} />
                {bootstrap?.lesson && (
                    <div className="flex flex-col sm:flex-row justify-between items-center gap-4 pt-12 border-t border-slate-200 pb-20 mt-16">
                      <button onClick={() => navigate(`/course/${currentSubject}`)} className="text-sm text-slate-500 font-bold hover:text-slate-800">← Back to Syllabus</button>
                      <button onClick={() => navigate(`/quiz/${topicId}`)} className="bg-indigo-600 text-white px-8 py-3 rounded-xl font-bold hover:bg-indigo-700 shadow-lg shadow-indigo-100">Take Mastery Quiz →</button>
                    </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>

      {/* AI CHAT PANEL */}
      <div className={`bg-white border-l border-slate-200 transition-all duration-300 flex flex-col right-0 ${
        isChatMaximized 
          ? 'fixed inset-0 z-[9999] w-full h-full' 
          : `fixed inset-y-0 z-50 lg:relative flex-shrink-0 ${isChatOpen ? 'w-full sm:w-[400px] translate-x-0' : 'w-0 translate-x-full lg:hidden'}`
      }`}>
        {bootstrap && (
            <AITutorPanel 
                activeId={activeId}
                token={token}
                sessionId={bootstrap.session_id}
                currentSubject={currentSubject}
                currentLevel={currentLevel}
                currentTerm={currentTerm}
                topicId={topicId}
                initialGreeting={bootstrap.greeting}
                initialPendingAssessment={bootstrap.pending_assessment}
                isMaximized={isChatMaximized}
                onToggleMaximize={() => setIsChatMaximized(!isChatMaximized)}
                onClose={() => {
                  setIsChatOpen(false);
                  setIsChatMaximized(false);
                }}
            />
        )}
      </div>
    </div>
  );

}
export default LessonPage;