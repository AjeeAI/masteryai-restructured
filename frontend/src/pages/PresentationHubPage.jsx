import React, { useEffect, useMemo, useState } from 'react';
import { ArrowRight, Bot, GitBranch, GraduationCap, Loader2, MonitorPlay, PlayCircle, School, Server, X } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import { useAuth } from '../context/AuthContext';
import { useUser } from '../context/UserContext';
import { AI_CORE_URL, API_URL } from '../config/runtime';
import { resolveStudentId } from '../utils/sessionIdentity';
import {
  createPresentationWalkthroughSteps,
  readPresentationWalkthrough,
  startPresentationWalkthrough,
  stopPresentationWalkthrough,
  subscribePresentationWalkthrough,
} from '../services/presentationWalkthrough';

const safeArray = (value) => (Array.isArray(value) ? value : []);

const statusTone = {
  ok: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  configured: 'border-indigo-200 bg-indigo-50 text-indigo-700',
  degraded: 'border-amber-200 bg-amber-50 text-amber-700',
  error: 'border-rose-200 bg-rose-50 text-rose-700',
  not_configured: 'border-slate-200 bg-slate-50 text-slate-600',
};

const toneClass = (status) => statusTone[status] || statusTone.not_configured;

const QuickLinkCard = ({ title, subtitle, label, onClick, icon: Icon, disabled = false }) => (
  <button
    type="button"
    disabled={disabled}
    onClick={onClick}
    className="w-full rounded-[1.75rem] border border-slate-200 bg-white p-5 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-md disabled:cursor-not-allowed disabled:opacity-55"
  >
    <div className="flex items-start justify-between gap-4">
      <div>
        <h3 className="text-lg font-black text-slate-900">{title}</h3>
        <p className="mt-2 text-sm leading-7 text-slate-600">{subtitle}</p>
      </div>
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600">
        <Icon className="h-5 w-5" />
      </div>
    </div>
    <div className="mt-4 inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-[11px] font-black uppercase tracking-[0.16em] text-slate-700">
      {label}
      <ArrowRight className="h-4 w-4" />
    </div>
  </button>
);

export default function PresentationHubPage() {
  const { token } = useAuth();
  const { userData, studentData } = useUser();
  const navigate = useNavigate();
  const apiUrl = API_URL;
  const aiCoreUrl = AI_CORE_URL;

  const studentId = resolveStudentId(studentData, userData);
  const role = userData?.role || null;
  const initialSubject = localStorage.getItem('active_subject') || studentData?.subjects?.[0] || null;

  const [isLoading, setIsLoading] = useState(true);
  const [backendHealth, setBackendHealth] = useState(null);
  const [aiCoreHealth, setAiCoreHealth] = useState(null);
  const [studentBootstrap, setStudentBootstrap] = useState(null);
  const [teacherClasses, setTeacherClasses] = useState([]);
  const [error, setError] = useState('');
  const [activeWalkthrough, setActiveWalkthrough] = useState(() => readPresentationWalkthrough());

  useEffect(() => subscribePresentationWalkthrough(setActiveWalkthrough), []);

  useEffect(() => {
    if (!token) return;

    const loadHub = async () => {
      setIsLoading(true);
      setError('');
      try {
        const requests = [
          fetch(`${apiUrl}/system/health`, { headers: { Authorization: `Bearer ${token}` } }),
        ];

        if (aiCoreUrl) {
          requests.push(fetch(`${aiCoreUrl.replace(/\/$/, '')}/health`));
        }
        if (studentData?.has_profile && studentId) {
          const query = new URLSearchParams({ student_id: String(studentId) });
          if (initialSubject) query.set('subject', initialSubject);
          requests.push(fetch(`${apiUrl}/learning/dashboard/bootstrap?${query.toString()}`, {
            headers: { Authorization: `Bearer ${token}` },
          }));
        }
        if (role === 'teacher') {
          requests.push(fetch(`${apiUrl}/teachers/classes`, {
            headers: { Authorization: `Bearer ${token}` },
          }));
        }

        const responses = await Promise.allSettled(requests);
        let index = 0;

        const backendResponse = responses[index++];
        if (backendResponse.status === 'fulfilled' && backendResponse.value.ok) {
          setBackendHealth(await backendResponse.value.json());
        }

        if (aiCoreUrl) {
          const aiCoreResponse = responses[index++];
          if (aiCoreResponse.status === 'fulfilled' && aiCoreResponse.value.ok) {
            setAiCoreHealth(await aiCoreResponse.value.json());
          }
        } else {
          setAiCoreHealth(null);
        }

        if (studentData?.has_profile && studentId) {
          const studentResponse = responses[index++];
          if (studentResponse?.status === 'fulfilled' && studentResponse.value.ok) {
            setStudentBootstrap(await studentResponse.value.json());
          }
        } else {
          setStudentBootstrap(null);
        }

        if (role === 'teacher') {
          const teacherResponse = responses[index++];
          if (teacherResponse?.status === 'fulfilled' && teacherResponse.value.ok) {
            const teacherData = await teacherResponse.value.json();
            setTeacherClasses(safeArray(teacherData?.classes));
          } else {
            setTeacherClasses([]);
          }
        } else {
          setTeacherClasses([]);
        }
      } catch (err) {
        setError(err.message || 'Failed to prepare presentation hub.');
      } finally {
        setIsLoading(false);
      }
    };

    loadHub();
  }, [aiCoreUrl, apiUrl, initialSubject, role, studentData, studentId, token]);

  const studentCourse = studentBootstrap?.course_bootstrap || null;
  const studentNextTopicId = studentCourse?.next_step?.recommended_topic_id || null;
  const studentSubject = studentBootstrap?.active_subject || initialSubject;
  const primaryTeacherClass = teacherClasses[0] || null;
  const walkthroughSteps = useMemo(() => createPresentationWalkthroughSteps({
    subject: studentSubject,
    recommendedTopicId: studentNextTopicId,
    teacherClassId: primaryTeacherClass?.id || null,
  }), [primaryTeacherClass?.id, studentNextTopicId, studentSubject]);

  const runtimeCards = useMemo(() => ([
    {
      key: 'backend',
      title: 'Backend runtime',
      status: backendHealth?.status || 'not_configured',
      subtitle: backendHealth?.checks?.prewarm_queue?.status
        ? `Prewarm queue: ${backendHealth.checks.prewarm_queue.status}`
        : 'Health snapshot unavailable.',
      icon: Server,
    },
    {
      key: 'ai-core',
      title: 'AI core runtime',
      status: aiCoreHealth?.status || (aiCoreUrl ? 'degraded' : 'not_configured'),
      subtitle: aiCoreUrl
        ? (aiCoreHealth?.runtime?.telemetry ? 'Live telemetry available.' : 'Health endpoint reachable but telemetry is missing.')
        : 'VITE_AI_CORE_URL is not configured in frontend env.',
      icon: Bot,
    },
    {
      key: 'student-graph',
      title: 'Student graph flow',
      status: studentCourse?.next_step ? 'ok' : studentData ? 'degraded' : 'not_configured',
      subtitle: studentCourse?.recommendation_story?.headline || (studentData ? 'No next-step recommendation yet.' : 'Student session unavailable in this account.'),
      icon: GraduationCap,
    },
    {
      key: 'teacher-graph',
      title: 'Teacher graph flow',
      status: primaryTeacherClass ? 'ok' : role === 'teacher' ? 'degraded' : 'not_configured',
      subtitle: primaryTeacherClass
        ? `${primaryTeacherClass.name} is ready for analytics and presentation mode.`
        : role === 'teacher'
          ? 'No teacher classes available yet.'
          : 'Teacher routes require a teacher account.',
      icon: School,
    },
  ]), [aiCoreHealth, aiCoreUrl, backendHealth, primaryTeacherClass, role, studentCourse, studentData]);

  const startWalkthrough = () => {
    const walkthrough = startPresentationWalkthrough({
      subject: studentSubject,
      recommendedTopicId: studentNextTopicId,
      teacherClassId: primaryTeacherClass?.id || null,
    });
    const firstPath = walkthrough?.steps?.[0]?.path;
    if (firstPath) {
      navigate(firstPath);
    }
  };

  const resumeWalkthrough = () => {
    const currentPath = activeWalkthrough?.steps?.[activeWalkthrough?.currentStepIndex || 0]?.path;
    if (currentPath) {
      navigate(currentPath);
    }
  };

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(99,102,241,0.12),_transparent_36%),linear-gradient(180deg,#f8fafc_0%,#eef2ff_100%)] p-6 md:p-8">
      <div className="mx-auto max-w-7xl space-y-8">
        <section className="rounded-[2rem] border border-slate-200 bg-white p-8 shadow-sm">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-3xl">
              <div className="inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em] text-indigo-700">
                <MonitorPlay className="h-3.5 w-3.5" />
                Presentation hub
              </div>
              <h1 className="mt-4 text-4xl font-black tracking-tight text-slate-900">One place to launch the strongest graph-backed demo flows</h1>
              <p className="mt-3 text-sm leading-7 text-slate-600">
                This hub ties together the student lesson graph story, the student printable briefing, the teacher analytics graph, and the live runtime health behind them.
              </p>
            </div>
            <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50 px-5 py-4">
              <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-500">Recommended walkthrough</p>
              <ol className="mt-3 space-y-2 text-sm font-semibold text-slate-700">
                {walkthroughSteps.map((step, index) => (
                  <li key={step.id}>{index + 1}. {step.title}</li>
                ))}
              </ol>
            </div>
          </div>
          <div className="mt-6 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={startWalkthrough}
              className="inline-flex items-center gap-2 rounded-2xl bg-slate-900 px-5 py-3 text-sm font-black text-white transition hover:bg-slate-800"
            >
              <PlayCircle className="h-4 w-4" />
              Start walkthrough
            </button>
            {activeWalkthrough?.active && (
              <>
                <button
                  type="button"
                  onClick={resumeWalkthrough}
                  className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-5 py-3 text-sm font-black text-slate-700 transition hover:bg-slate-50"
                >
                  <ArrowRight className="h-4 w-4" />
                  Resume walkthrough
                </button>
                <button
                  type="button"
                  onClick={() => {
                    stopPresentationWalkthrough();
                    setActiveWalkthrough(null);
                  }}
                  className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-5 py-3 text-sm font-black text-slate-700 transition hover:bg-slate-50"
                >
                  <X className="h-4 w-4" />
                  End walkthrough
                </button>
              </>
            )}
          </div>
        </section>

        {isLoading ? (
          <div className="flex min-h-[280px] flex-col items-center justify-center rounded-[2rem] border border-slate-200 bg-white shadow-sm">
            <Loader2 className="h-10 w-10 animate-spin text-indigo-600" />
            <p className="mt-4 text-sm font-semibold text-slate-700">Preparing presentation hub...</p>
          </div>
        ) : error ? (
          <div className="rounded-[2rem] border border-rose-200 bg-rose-50 p-6 text-sm font-semibold text-rose-700">
            {error}
          </div>
        ) : (
          <>
            <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              {runtimeCards.map((card) => (
                <div key={card.key} className={`rounded-[1.75rem] border p-5 shadow-sm ${toneClass(card.status)}`}>
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-[10px] font-black uppercase tracking-[0.18em]">{card.title}</p>
                    <card.icon className="h-5 w-5" />
                  </div>
                  <p className="mt-3 text-lg font-black capitalize">{String(card.status).replace('_', ' ')}</p>
                  <p className="mt-2 text-sm leading-6">{card.subtitle}</p>
                </div>
              ))}
            </section>

            <section className="grid gap-6 lg:grid-cols-2">
              <div className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">
                <div className="flex items-center gap-2">
                  <GraduationCap className="h-5 w-5 text-indigo-600" />
                  <h2 className="text-lg font-black text-slate-900">Student graph story</h2>
                </div>
                <p className="mt-2 text-sm leading-7 text-slate-600">
                  Launch the strongest student-side graph experience, then move into the printable briefing for the “why this, why now, what next” narrative.
                </p>
                <div className="mt-5 grid gap-4">
                  <QuickLinkCard
                    title="Demo mode"
                    subtitle="Open the speaker notes, live checks, and exact run-of-show for presentation day."
                    label="Open demo mode"
                    icon={PlayCircle}
                    onClick={() => navigate('/demo-mode')}
                  />
                  <QuickLinkCard
                    title="Student dashboard"
                    subtitle="Open the live dashboard where graph-backed recommendations and intervention timelines surface first."
                    label="Open dashboard"
                    icon={GitBranch}
                    onClick={() => navigate('/dashboard')}
                  />
                  <QuickLinkCard
                    title="Graph explorer"
                    subtitle={studentCourse?.recommendation_story?.headline || 'Inspect the full course graph, ready nodes, blockers, and evidence timeline.'}
                    label="Open graph explorer"
                    icon={MonitorPlay}
                    onClick={() => navigate(studentSubject ? `/graph-path?subject=${encodeURIComponent(studentSubject)}` : '/graph-path')}
                    disabled={!studentData}
                  />
                  <QuickLinkCard
                    title="Graph briefing"
                    subtitle="Open the printable student briefing generated from the live dashboard bootstrap."
                    label="Open graph briefing"
                    icon={Bot}
                    onClick={() => navigate(studentSubject ? `/graph-briefing?subject=${encodeURIComponent(studentSubject)}` : '/graph-briefing')}
                    disabled={!studentData}
                  />
                  <QuickLinkCard
                    title="Recommended lesson"
                    subtitle={studentCourse?.next_step?.reason || 'Jump directly into the lesson the graph recommends next.'}
                    label="Open lesson"
                    icon={ArrowRight}
                    onClick={() => navigate(`/lesson/${studentNextTopicId}`)}
                    disabled={!studentNextTopicId}
                  />
                </div>
              </div>

              <div className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">
                <div className="flex items-center gap-2">
                  <School className="h-5 w-5 text-indigo-600" />
                  <h2 className="text-lg font-black text-slate-900">Teacher graph story</h2>
                </div>
                <p className="mt-2 text-sm leading-7 text-slate-600">
                  Show the class graph, intervention queue, outcome analytics, and the clean presentation view built from the same live teacher data.
                </p>
                <div className="mt-5 grid gap-4">
                  <QuickLinkCard
                    title="Teacher analytics"
                    subtitle="Open the main teacher graph analytics workspace."
                    label="Open analytics"
                    icon={GitBranch}
                    onClick={() => navigate('/teacher/analytics')}
                  />
                  <QuickLinkCard
                    title="Teacher presentation"
                    subtitle={primaryTeacherClass ? `Open presentation mode for ${primaryTeacherClass.name}.` : 'Requires at least one teacher class.'}
                    label="Open presentation"
                    icon={MonitorPlay}
                    onClick={() => navigate(`/teacher/presentation/${primaryTeacherClass.id}`)}
                    disabled={!primaryTeacherClass}
                  />
                  <QuickLinkCard
                    title="Teacher briefing"
                    subtitle={primaryTeacherClass ? `Open printable briefing for ${primaryTeacherClass.name}.` : 'Requires at least one teacher class.'}
                    label="Open briefing"
                    icon={School}
                    onClick={() => navigate(`/teacher/briefing/${primaryTeacherClass.id}`)}
                    disabled={!primaryTeacherClass}
                  />
                  <QuickLinkCard
                    title="Teacher class graph"
                    subtitle={primaryTeacherClass ? `${primaryTeacherClass.subject.toUpperCase()} ${primaryTeacherClass.sss_level} Term ${primaryTeacherClass.term}` : 'No teacher class selected yet.'}
                    label="Open analytics"
                    icon={GraduationCap}
                    onClick={() => navigate('/teacher/analytics')}
                    disabled={!primaryTeacherClass}
                  />
                </div>
              </div>
            </section>
          </>
        )}
      </div>
    </main>
  );
}
