import React, { Suspense, lazy } from 'react';
import { Routes, Route, Navigate, Outlet } from 'react-router-dom';

// --- Providers & Guards (KEEP THESE STANDARD) ---
// These are needed immediately for the app to function
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import { UserProvider } from './context/UserContext';

// --- Layout Components (KEEP THESE STANDARD) ---
// Layouts are used across many pages, so keeping them standard is usually better
import Navbar from './components/Navbar';
import PresentationWalkthroughDock from './components/PresentationWalkthroughDock';
import RuntimeDebugDock from './components/RuntimeDebugDock';
import TeacherSidebar from './components/TeacherSidebar';
import LandingLayout from './layouts/LandingLayout'; 

// --- 🚀 LAZY LOADED PAGES ---
// Public Pages
const HomePage = lazy(() => import('./pages/HomePage'));
const AboutPage = lazy(() => import('./pages/AboutPage'));
const Contactpage = lazy(() => import('./pages/ContactPage'));
const LoginPage = lazy(() => import('./pages/LoginPage'));
const RegisterPage = lazy(() => import('./pages/RegisterPage'));

// Onboarding
const ClassSelection = lazy(() => import('./pages/ClassSelection'));
const SubjectSelection = lazy(() => import('./pages/SubjectSelection'));
const LearningPreferences = lazy(() => import('./pages/LearningPreferences'));
const AssessmentSplash = lazy(() => import('./pages/AssessmentSplash'));

// Core Student Pages
const Dashboard = lazy(() => import('./pages/Dashboard'));
const GraphPathPage = lazy(() => import('./pages/GraphPathPage'));
const GraphBriefingPage = lazy(() => import('./pages/GraphBriefingPage'));
const PresentationHubPage = lazy(() => import('./pages/PresentationHubPage'));
const DemoModePage = lazy(() => import('./pages/DemoModePage'));
const CoursePage = lazy(() => import('./pages/CoursePage')); 
const LessonPage = lazy(() => import('./pages/LessonPage'));
const QuizPage = lazy(() => import('./pages/QuizPage'));
const ProfilePage = lazy(() => import('./pages/ProfilePage'));
const ExplainMistakePage = lazy(() => import('./pages/ExplainMistakePage'));

// Diagnostic/Results
const InProgress = lazy(() => import('./pages/InProgress')); 
const Completed = lazy(() => import('./pages/Completed'));
const ModuleQuizPage = lazy(() => import('./pages/ModuleQuizPage'));
const ConceptAnalyticsPage = lazy(() => import('./pages/ConceptAnalyticsPage'));
const TeacherBriefingPage = lazy(() => import('./pages/TeacherBriefingPage'));
const TeacherStudentReportPage = lazy(() => import('./pages/TeacherStudentReportPage'));
const TeacherPresentationPage = lazy(() => import('./pages/TeacherPresentationPage'));

// --- Loading Fallback ---
const PageLoader = () => (
  <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center">
    <div className="w-12 h-12 border-4 border-indigo-100 border-t-indigo-600 rounded-full animate-spin mb-4"></div>
    <p className="text-slate-500 font-medium animate-pulse">Loading MasteryAI...</p>
  </div>
);

/* --- Layout Wrappers --- */
const StudentLayout = () => (
  <div className="min-h-screen overflow-x-hidden bg-slate-50 flex flex-col">
    <Navbar />
    <div className="flex-1"><Outlet /></div>
    <PresentationWalkthroughDock />
    <RuntimeDebugDock />
  </div>
);

const TeacherLayout = () => (
  <div className="flex min-h-screen overflow-x-hidden bg-slate-50">
    <TeacherSidebar />
    <div className="flex-1 h-screen overflow-y-auto">
      <Outlet />
      <PresentationWalkthroughDock />
    </div>
  </div>
);

function App() {
  return (
    <AuthProvider>
      <UserProvider>
        {/* 👇 Suspense handles the "Wait" while a new page chunk is being downloaded */}
        <Suspense fallback={<PageLoader />}>
          <Routes>
            
            {/* 🌐 PUBLIC LANDING PAGES */}
            <Route element={<LandingLayout />}>
              <Route path="/" element={<HomePage />} />
              <Route path="/about" element={<AboutPage />} />
              <Route path="/contact" element={<Contactpage />} />
            </Route>

            {/* 🔓 PUBLIC AUTH ROUTES */}
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            
            {/* 🔒 PROTECTED ROUTES */}
            <Route element={<ProtectedRoute />}>
              
              {/* Onboarding Flow */}
              <Route path="/class-selection" element={<ClassSelection />} />
              <Route path="/subject-selection" element={<SubjectSelection />} />
              <Route path="/learning-preferences" element={<LearningPreferences />} />
              <Route path="/assessment-splash" element={<AssessmentSplash />} />
              <Route path="/presentation-hub" element={<PresentationHubPage />} />
              <Route path="/demo-mode" element={<DemoModePage />} />

              {/* Student Layout */}
              <Route element={<StudentLayout />}>
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/graph-path" element={<GraphPathPage />} />
                <Route path="/graph-briefing" element={<GraphBriefingPage />} />
                <Route path="/course/:subject" element={<CoursePage />} /> 
                <Route path="/lesson/:topicId" element={<LessonPage />} />
                <Route path="/mastery-path" element={<ExplainMistakePage />} />
                <Route path="/profile" element={<ProfilePage />} />
                
                {/* Diagnostic & Mastery Quiz Flow */}
                <Route path="/quiz/:topicId" element={<QuizPage />} />
                <Route path="/quiz/:quizId/in-progress" element={<InProgress />} />
                <Route path="/quiz/:quizId/completed" element={<Completed />} />

                {/* Module Flow */}
                <Route path="/module-quiz" element={<ModuleQuizPage />} />
                <Route path="/module-quiz/:topicId" element={<ModuleQuizPage />} />
              </Route>

              {/* Teacher Layout */}
              <Route path="/teacher" element={<TeacherLayout />}>
                <Route index element={<Navigate to="analytics" />} />
                <Route path="analytics" element={<ConceptAnalyticsPage />} />
                <Route path="presentation/:classId" element={<TeacherPresentationPage />} />
                <Route path="briefing/:classId" element={<TeacherBriefingPage />} />
                <Route path="students/:classId/:studentId/concepts/:conceptId/report" element={<TeacherStudentReportPage />} />
              </Route>

            </Route>
          </Routes>
        </Suspense>
      </UserProvider>
    </AuthProvider>
  );
}

export default App;
