import React, { useEffect, useMemo, useState } from 'react';
import {
  ArrowLeft,
  ArrowRight,
  Bot,
  Clipboard,
  ClipboardList,
  GraduationCap,
  Loader2,
  MonitorPlay,
  PlayCircle,
  School,
  Server,
  Sparkles,
} from 'lucide-react';
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

const readinessTone = {
  ready: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  attention: 'border-amber-200 bg-amber-50 text-amber-700',
  unavailable: 'border-slate-200 bg-slate-50 text-slate-600',
};

const noteTone = {
  dashboard: 'bg-indigo-50 text-indigo-700',
  lesson: 'bg-sky-50 text-sky-700',
  'graph-path': 'bg-emerald-50 text-emerald-700',
  'graph-briefing': 'bg-amber-50 text-amber-700',
  'teacher-presentation': 'bg-fuchsia-50 text-fuchsia-700',
};

const buildSpeakerNotes = ({ stepId, studentCourse, primaryTeacherClass }) => {
  const recommendationStory = studentCourse?.recommendation_story || null;
  const nextStep = studentCourse?.next_step || null;

  switch (stepId) {
    case 'dashboard':
      return [
        'Open with the graph-backed recommendation, not the chatbot.',
        'Point out that the app is reacting to real mastery evidence and intervention history.',
        'Use the hero and evidence timeline to explain why the next step changed.',
      ];
    case 'lesson':
      return [
        `Show that the lesson cockpit opens directly on the graph-recommended lesson${nextStep?.recommended_topic_title ? `: ${nextStep.recommended_topic_title}.` : '.'}`,
        'Highlight the graph rail, tutor quick actions, and checkpoint flow in one place.',
        'Explain that this is where Neo4j becomes visible to the student, not just hidden backend infrastructure.',
      ];
    case 'graph-path':
      return [
        recommendationStory?.headline || 'Show the full graph path, ready nodes, blockers, and latest evidence.',
        'Click a node to show that graph state leads directly into lesson and remediation actions.',
        'Use this page to prove the recommendation is graph-shaped, not hardcoded topic order.',
      ];
    case 'graph-briefing':
      return [
        'Show that the system can turn live graph state into a printable student briefing.',
        'Use the export and print controls to explain demo-day readiness and teacher/student communication value.',
        'This is the cleanest place to summarize "why this, why now, what next."',
      ];
    case 'teacher-presentation':
      return [
        `Switch to the teacher story${primaryTeacherClass?.name ? ` for ${primaryTeacherClass.name}` : ''} and show the class graph, queue, and outcomes together.`,
        'Call out that the same graph system powering the student side also supports teacher intervention planning.',
        'Use the queue and outcome snapshot to show that the graph is operational, not decorative.',
      ];
    default:
      return ['Walk through the live route and explain how it fits into the graph-first learning story.'];
  }
};

const buildRunSheet = ({ steps, studentCourse, primaryTeacherClass }) => {
  const lines = [
    'Graph-First Demo Run Sheet',
    '',
    'Opener',
    '- This is a graph-backed learning system, not a normal lesson page with a side chatbot.',
    '- The demo shows how graph state drives the student path, lesson behavior, tutor actions, and teacher intervention planning.',
    '',
    'Run of show',
  ];

  steps.forEach((step, index) => {
    lines.push(`${index + 1}. ${step.title}`);
    lines.push(`   Route: ${step.path}`);
    buildSpeakerNotes({ stepId: step.id, studentCourse, primaryTeacherClass }).forEach((note) => {
      lines.push(`   - ${note}`);
    });
    lines.push('');
  });

  return lines.join('\n');
};

const ReadinessCard = ({ title, status, description, icon: Icon }) => (
  <div className={`rounded-[1.5rem] border p-5 shadow-sm ${readinessTone[status] || readinessTone.unavailable}`}>
    <div className="flex items-start justify-between gap-3">
      <div>
        <p className="text-[10px] font-black uppercase tracking-[0.18em]">{title}</p>
        <p className="mt-3 text-lg font-black capitalize">{status}</p>
        <p className="mt-2 text-sm leading-6">{description}</p>
      </div>
      <Icon className="mt-1 h-5 w-5" />
    </div>
  </div>
);

export default function DemoModePage() {
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
  const [demoReadiness, setDemoReadiness] = useState(null);
  const [aiCoreHealth, setAiCoreHealth] = useState(null);
  const [studentBootstrap, setStudentBootstrap] = useState(null);
  const [teacherClasses, setTeacherClasses] = useState([]);
  const [error, setError] = useState('');
  const [copyState, setCopyState] = useState('idle');
  const [activeWalkthrough, setActiveWalkthrough] = useState(() => readPresentationWalkthrough());

  useEffect(() => subscribePresentationWalkthrough(setActiveWalkthrough), []);

  useEffect(() => {
    if (!token) return;

    const loadDemoMode = async () => {
      setIsLoading(true);
      setError('');
      try {
        const requests = [
          fetch(`${apiUrl}/system/health`, { headers: { Authorization: `Bearer ${token}` } }),
          fetch(`${apiUrl}/system/demo`, { headers: { Authorization: `Bearer ${token}` } }),
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
        } else {
          setBackendHealth(null);
        }

        const demoResponse = responses[index++];
        if (demoResponse.status === 'fulfilled' && demoResponse.value.ok) {
          setDemoReadiness(await demoResponse.value.json());
        } else {
          setDemoReadiness(null);
        }

        if (aiCoreUrl) {
          const aiCoreResponse = responses[index++];
          if (aiCoreResponse.status === 'fulfilled' && aiCoreResponse.value.ok) {
            setAiCoreHealth(await aiCoreResponse.value.json());
          } else {
            setAiCoreHealth(null);
          }
        } else {
          setAiCoreHealth(null);
        }

        if (studentData?.has_profile && studentId) {
          const studentResponse = responses[index++];
          if (studentResponse?.status === 'fulfilled' && studentResponse.value.ok) {
            setStudentBootstrap(await studentResponse.value.json());
          } else {
            setStudentBootstrap(null);
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
        setError(err.message || 'Failed to prepare demo mode.');
      } finally {
        setIsLoading(false);
      }
    };

    loadDemoMode();
  }, [aiCoreUrl, apiUrl, initialSubject, role, studentData, studentId, token]);

  const studentCourse = studentBootstrap?.course_bootstrap || null;
  const studentSubject = studentBootstrap?.active_subject || initialSubject;
  const primaryTeacherClass = teacherClasses[0] || null;
  const walkthroughSteps = useMemo(
    () => createPresentationWalkthroughSteps({
      subject: studentSubject,
      recommendedTopicId: studentCourse?.next_step?.recommended_topic_id || null,
      teacherClassId: primaryTeacherClass?.id || null,
    }),
    [primaryTeacherClass?.id, studentCourse?.next_step?.recommended_topic_id, studentSubject],
  );

  const demoMissing = useMemo(() => {
    const checks = demoReadiness?.checks || {};
    return Object.entries(checks)
      .filter(([key, value]) => key !== 'scope' && value && value.status && value.status !== 'ok')
      .map(([key, value]) => value.detail || `${key} not ready`);
  }, [demoReadiness]);

  const readinessItems = useMemo(() => ([
    {
      title: 'Backend runtime',
      status: backendHealth?.status === 'ok' ? 'ready' : backendHealth ? 'attention' : 'unavailable',
      description: backendHealth?.checks?.prewarm_queue?.status
        ? `Prewarm queue is ${backendHealth.checks.prewarm_queue.status}.`
        : 'Backend health snapshot is not available yet.',
      icon: Server,
    },
    {
      title: 'AI core runtime',
      status: aiCoreUrl ? (aiCoreHealth?.status === 'ok' ? 'ready' : 'attention') : 'unavailable',
      description: aiCoreUrl
        ? (aiCoreHealth?.runtime?.telemetry ? 'AI core telemetry is visible for the demo.' : 'AI core is configured but telemetry is missing.')
        : 'Set VITE_AI_CORE_URL to show AI core runtime details in the demo.',
      icon: Bot,
    },
    {
      title: 'Demo data',
      status: demoReadiness?.status === 'ready'
        ? 'ready'
        : demoReadiness?.status === 'attention'
          ? 'attention'
          : demoReadiness
            ? 'unavailable'
            : 'unavailable',
      description: demoReadiness
        ? (demoMissing.length > 0 ? demoMissing[0] : 'Demo seed is ready for the configured scope.')
        : 'Demo readiness snapshot is not available yet.',
      icon: ClipboardList,
    },
    {
      title: 'Student graph story',
      status: studentCourse?.next_step ? 'ready' : studentData ? 'attention' : 'unavailable',
      description: studentCourse?.recommendation_story?.headline || (studentData ? 'Student dashboard is available, but no next-step recommendation is loaded yet.' : 'Student session is not available in this account.'),
      icon: GraduationCap,
    },
    {
      title: 'Teacher graph story',
      status: primaryTeacherClass ? 'ready' : role === 'teacher' ? 'attention' : 'unavailable',
      description: primaryTeacherClass
        ? `${primaryTeacherClass.name} is available for teacher presentation mode.`
        : role === 'teacher'
          ? 'Teacher account is active, but no class is loaded yet.'
          : 'Teacher routes require a teacher account.',
      icon: School,
    },
  ]), [aiCoreHealth, aiCoreUrl, backendHealth, demoMissing, demoReadiness, primaryTeacherClass, role, studentCourse, studentData]);

  const runSheet = useMemo(
    () => buildRunSheet({
      steps: walkthroughSteps,
      studentCourse,
      primaryTeacherClass,
    }),
    [primaryTeacherClass, studentCourse, walkthroughSteps],
  );

  const handleStartWalkthrough = () => {
    const walkthrough = startPresentationWalkthrough({
      subject: studentSubject,
      recommendedTopicId: studentCourse?.next_step?.recommended_topic_id || null,
      teacherClassId: primaryTeacherClass?.id || null,
    });
    const firstPath = walkthrough?.steps?.[0]?.path;
    if (firstPath) {
      navigate(firstPath);
    }
  };

  const handleResumeWalkthrough = () => {
    const currentPath = activeWalkthrough?.steps?.[activeWalkthrough?.currentStepIndex || 0]?.path;
    if (currentPath) {
      navigate(currentPath);
    }
  };

  const handleCopyRunSheet = async () => {
    try {
      await navigator.clipboard.writeText(runSheet);
      setCopyState('success');
      window.setTimeout(() => setCopyState('idle'), 1800);
    } catch {
      setCopyState('error');
      window.setTimeout(() => setCopyState('idle'), 1800);
    }
  };

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(15,23,42,0.12),_transparent_34%),linear-gradient(180deg,#f8fafc_0%,#eef2ff_100%)] p-6 md:p-8">
      <div className="mx-auto max-w-7xl space-y-8">
        <section className="rounded-[2rem] border border-slate-200 bg-white p-8 shadow-sm">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-4xl">
              <button
                type="button"
                onClick={() => navigate('/presentation-hub')}
                className="inline-flex items-center gap-2 text-sm font-bold text-slate-500 transition hover:text-slate-800"
              >
                <ArrowLeft className="h-4 w-4" />
                Back to presentation hub
              </button>
              <div className="mt-4 inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em] text-slate-700">
                <MonitorPlay className="h-3.5 w-3.5" />
                Demo mode
              </div>
              <h1 className="mt-4 text-4xl font-black tracking-tight text-slate-900">Run the graph-first demo with one clear story</h1>
              <p className="mt-3 text-sm leading-7 text-slate-600">
                This page gives us the order, the speaker notes, and the launch controls for the strongest student and teacher flows already live in the product.
              </p>
            </div>
            <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50 px-5 py-4 lg:max-w-sm">
              <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-500">Suggested opener</p>
              <ul className="mt-3 space-y-2 text-sm font-semibold leading-6 text-slate-700">
                <li>We are not showing a normal chatbot product.</li>
                <li>The graph drives what the student sees next.</li>
                <li>The same graph also drives teacher intervention planning.</li>
              </ul>
            </div>
          </div>

          <div className="mt-6 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={handleStartWalkthrough}
              className="inline-flex items-center gap-2 rounded-2xl bg-slate-900 px-5 py-3 text-sm font-black text-white transition hover:bg-slate-800"
            >
              <PlayCircle className="h-4 w-4" />
              Start scripted demo
            </button>
            {activeWalkthrough?.active && (
              <>
                <button
                  type="button"
                  onClick={handleResumeWalkthrough}
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
                  Stop walkthrough
                </button>
              </>
            )}
            <button
              type="button"
              onClick={handleCopyRunSheet}
              className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-5 py-3 text-sm font-black text-slate-700 transition hover:bg-slate-50"
            >
              <Clipboard className="h-4 w-4" />
              {copyState === 'success' ? 'Copied run sheet' : copyState === 'error' ? 'Copy failed' : 'Copy run sheet'}
            </button>
          </div>
        </section>

        {isLoading ? (
          <div className="flex min-h-[280px] flex-col items-center justify-center rounded-[2rem] border border-slate-200 bg-white shadow-sm">
            <Loader2 className="h-10 w-10 animate-spin text-indigo-600" />
            <p className="mt-4 text-sm font-semibold text-slate-700">Preparing demo mode...</p>
          </div>
        ) : error ? (
          <div className="rounded-[2rem] border border-rose-200 bg-rose-50 p-6 text-sm font-semibold text-rose-700">
            {error}
          </div>
        ) : (
          <>
            <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              {readinessItems.map((item) => (
                <ReadinessCard
                  key={item.title}
                  title={item.title}
                  status={item.status}
                  description={item.description}
                  icon={item.icon}
                />
              ))}
            </section>

            {demoReadiness && demoMissing.length > 0 && (
              <section className="rounded-[2rem] border border-amber-200 bg-amber-50 p-6 text-sm text-amber-900">
                <p className="text-[10px] font-black uppercase tracking-[0.18em] text-amber-700">Demo readiness warnings</p>
                <div className="mt-3 space-y-2">
                  {demoMissing.map((note) => (
                    <div key={note} className="rounded-2xl border border-amber-200 bg-white px-4 py-2">
                      {note}
                    </div>
                  ))}
                </div>
              </section>
            )}

            <section className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
              <div className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">
                <div className="flex items-center gap-2">
                  <Sparkles className="h-5 w-5 text-indigo-600" />
                  <h2 className="text-lg font-black text-slate-900">Run of show</h2>
                </div>
                <p className="mt-2 text-sm leading-7 text-slate-600">
                  Each stop below is live, launchable, and tied to a specific story point so the demo feels deliberate.
                </p>
                <div className="mt-5 space-y-4">
                  {walkthroughSteps.map((step, index) => {
                    const notes = buildSpeakerNotes({
                      stepId: step.id,
                      studentCourse,
                      primaryTeacherClass,
                    });
                    const isActive = activeWalkthrough?.active && activeWalkthrough.steps?.[activeWalkthrough.currentStepIndex || 0]?.id === step.id;
                    return (
                      <div key={step.id} className="rounded-[1.75rem] border border-slate-200 bg-slate-50 p-5">
                        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                          <div className="max-w-3xl">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="inline-flex rounded-full border border-slate-200 bg-white px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em] text-slate-500">
                                Stop {index + 1}
                              </span>
                              {isActive && (
                                <span className="inline-flex rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em] text-indigo-700">
                                  Active walkthrough step
                                </span>
                              )}
                            </div>
                            <h3 className="mt-3 text-xl font-black text-slate-900">{step.title}</h3>
                            <p className="mt-2 text-sm leading-7 text-slate-600">{step.description}</p>
                            <div className={`mt-4 rounded-2xl px-4 py-3 text-sm ${noteTone[step.id] || 'bg-slate-100 text-slate-700'}`}>
                              <p className="text-[10px] font-black uppercase tracking-[0.18em]">Speaker notes</p>
                              <ul className="mt-3 space-y-2">
                                {notes.map((note) => (
                                  <li key={note} className="leading-6">- {note}</li>
                                ))}
                              </ul>
                            </div>
                          </div>
                          <button
                            type="button"
                            onClick={() => navigate(step.path)}
                            className="inline-flex items-center gap-2 rounded-2xl bg-slate-900 px-4 py-3 text-sm font-black text-white transition hover:bg-slate-800"
                          >
                            Open stop
                            <ArrowRight className="h-4 w-4" />
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div className="space-y-6">
                <div className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">
                  <div className="flex items-center gap-2">
                    <ClipboardList className="h-5 w-5 text-indigo-600" />
                    <h2 className="text-lg font-black text-slate-900">Live graph story to call out</h2>
                  </div>
                  <div className="mt-4 space-y-3 text-sm leading-7 text-slate-600">
                    <p>The recommendation should feel earned. Mention the evidence timeline, the next-step story, and the move from graph state into lesson action.</p>
                    <p>The lesson page should feel like a study cockpit. Mention graph rail, tutor actions, and checkpoint flow in the same breath.</p>
                    <p>On the teacher side, stress that graph blockers become queue items, interventions, and measurable outcomes.</p>
                  </div>
                </div>

                <div className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">
                  <div className="flex items-center gap-2">
                    <GraduationCap className="h-5 w-5 text-indigo-600" />
                    <h2 className="text-lg font-black text-slate-900">Current live context</h2>
                  </div>
                  <div className="mt-4 space-y-3 text-sm text-slate-600">
                    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                      <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Student subject</p>
                      <p className="mt-2 font-bold capitalize text-slate-900">{studentSubject || 'Not available'}</p>
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                      <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Recommended lesson</p>
                      <p className="mt-2 font-bold text-slate-900">{studentCourse?.next_step?.recommended_topic_title || 'Not available yet'}</p>
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                      <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Teacher class</p>
                      <p className="mt-2 font-bold text-slate-900">{primaryTeacherClass?.name || 'Teacher class not loaded'}</p>
                    </div>
                  </div>
                </div>
              </div>
            </section>
          </>
        )}
      </div>
    </main>
  );
}
