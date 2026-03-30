import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  ArrowLeft,
  ArrowRight,
  Brain,
  ClipboardList,
  GitBranch,
  Loader2,
  Lock,
  Sparkles,
  Target,
} from 'lucide-react';

import LearningMap from '../components/LearningMap';
import InterventionTimeline from '../components/InterventionTimeline';
import { useAuth } from '../context/AuthContext';
import { useUser } from '../context/UserContext';
import { API_URL } from '../config/runtime';
import { resolveStudentId } from '../utils/sessionIdentity';

const EMPTY_MAP_DATA = {
  nodes: [],
  edges: [],
  next_step: null,
  recent_evidence: null,
  intervention_timeline: [],
  recommendation_story: null,
  topics: [],
  evidence_summary: null,
  map_error: null,
};

const safeArray = (value) => (Array.isArray(value) ? value : []);

const normalizeCourseBootstrap = (data) => ({
  nodes: Array.isArray(data?.nodes) ? data.nodes : [],
  edges: Array.isArray(data?.edges) ? data.edges : [],
  next_step: data?.next_step || null,
  recent_evidence: data?.recent_evidence || null,
  intervention_timeline: Array.isArray(data?.intervention_timeline) ? data.intervention_timeline : [],
  recommendation_story: data?.recommendation_story || null,
  topics: Array.isArray(data?.topics) ? data.topics : [],
  evidence_summary: data?.evidence_summary || null,
  map_error: data?.map_error || null,
});

const prewarmTopics = async ({ apiUrl, token, studentId, subject, sssLevel, term, topicIds }) => {
  const normalizedIds = Array.from(new Set((topicIds || []).filter(Boolean)));
  if (!normalizedIds.length) return;
  try {
    await fetch(`${apiUrl}/learning/lesson/prewarm`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        student_id: studentId,
        subject,
        sss_level: sssLevel,
        term,
        topic_ids: normalizedIds,
      }),
    });
  } catch (error) {
    console.warn('Graph path prewarm skipped:', error);
  }
};

const StatCard = ({ icon: Icon, label, value, subtext, tone = 'indigo' }) => {
  const tones = {
    indigo: 'bg-indigo-50 text-indigo-600',
    emerald: 'bg-emerald-50 text-emerald-600',
    amber: 'bg-amber-50 text-amber-600',
    slate: 'bg-slate-100 text-slate-600',
  };

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-3.5 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">{label}</p>
          <p className="mt-2 text-xl font-black text-slate-900 sm:text-2xl">{value}</p>
          {subtext ? <p className="mt-2 text-xs leading-6 text-slate-500">{subtext}</p> : null}
        </div>
        <div className={`flex h-11 w-11 items-center justify-center rounded-2xl ${tones[tone] || tones.indigo}`}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </div>
  );
};

export default function GraphPathPage() {
  const { token } = useAuth();
  const { userData, studentData } = useUser();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const apiUrl = API_URL;
  const activeId = resolveStudentId(studentData, userData);
  const currentLevel = studentData?.sss_level || 'SSS1';
  const currentTerm = Number(studentData?.current_term || 1);
  const enrolledSubjects = useMemo(
    () => (Array.isArray(studentData?.subjects) ? studentData.subjects : []),
    [studentData?.subjects],
  );

  const [activeSubject, setActiveSubject] = useState(() => searchParams.get('subject') || localStorage.getItem('active_subject') || enrolledSubjects[0] || null);
  const [availableSubjects, setAvailableSubjects] = useState([]);
  const [mapData, setMapData] = useState(EMPTY_MAP_DATA);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!activeSubject && enrolledSubjects.length) {
      setActiveSubject(enrolledSubjects[0]);
    }
  }, [activeSubject, enrolledSubjects]);

  useEffect(() => {
    if (activeSubject) {
      localStorage.setItem('active_subject', activeSubject);
      setSearchParams((current) => {
        const next = new URLSearchParams(current);
        next.set('subject', activeSubject);
        return next;
      }, { replace: true });
    }
  }, [activeSubject, setSearchParams]);

  useEffect(() => {
    if (!activeId || !token) return;

    const fetchGraphPath = async () => {
      setIsLoading(true);
      setError('');
      try {
        const queryParams = new URLSearchParams({ student_id: activeId });
        if (activeSubject) {
          queryParams.set('subject', activeSubject);
        }
        const response = await fetch(`${apiUrl}/learning/dashboard/bootstrap?${queryParams.toString()}`, {
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        });
        if (!response.ok) {
          const detail = await response.json().catch(() => null);
          throw new Error(detail?.detail || 'Failed to load graph path.');
        }
        const data = await response.json();
        const nextSubject = data?.active_subject || activeSubject;
        if (nextSubject && nextSubject !== activeSubject) {
          setActiveSubject(nextSubject);
        }
        setAvailableSubjects(Array.isArray(data?.available_subjects) ? data.available_subjects : []);
        setMapData(normalizeCourseBootstrap(data?.course_bootstrap || {}));
      } catch (err) {
        setMapData(EMPTY_MAP_DATA);
        setError(err.message || 'Graph path unavailable right now.');
      } finally {
        setIsLoading(false);
      }
    };

    fetchGraphPath();
  }, [activeId, activeSubject, apiUrl, token]);

  const recommendedTopic = mapData?.next_step || null;
  const recommendationStory = mapData?.recommendation_story || null;
  const readyTopics = useMemo(
    () => safeArray(mapData?.topics).filter((topic) => ['ready', 'current'].includes(topic.status)).slice(0, 5),
    [mapData?.topics],
  );
  const blockedTopics = useMemo(
    () => safeArray(mapData?.topics).filter((topic) => topic.status === 'locked').slice(0, 5),
    [mapData?.topics],
  );
  const graphStats = useMemo(() => ({
    readyCount: safeArray(mapData?.topics).filter((topic) => ['ready', 'current'].includes(topic.status)).length,
    blockerCount: safeArray(mapData?.topics).filter((topic) => topic.status === 'locked').length,
    relationCount: safeArray(mapData?.edges).length,
    evidenceCount: safeArray(mapData?.intervention_timeline).length,
  }), [mapData?.edges, mapData?.intervention_timeline, mapData?.topics]);
  const evidenceSummary = mapData?.evidence_summary || null;

  const openLesson = async (topicId) => {
    if (!topicId || !activeId || !token || !activeSubject) return;
    await prewarmTopics({
      apiUrl,
      token,
      studentId: activeId,
      subject: activeSubject,
      sssLevel: currentLevel,
      term: currentTerm,
      topicIds: [topicId],
    });
    navigate(`/lesson/${topicId}`);
  };

  return (
    <div className="min-h-screen overflow-x-hidden bg-[radial-gradient(circle_at_top_left,_rgba(99,102,241,0.08),_transparent_38%),linear-gradient(180deg,#f8fafc_0%,#eef2ff_100%)] px-4 py-5 sm:px-6">
      <main className="mx-auto max-w-[1440px]">
        <div className="mb-5 flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <button
              type="button"
              onClick={() => navigate('/dashboard')}
              className="inline-flex items-center gap-2 text-sm font-bold text-slate-500 transition hover:text-slate-800"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to dashboard
            </button>
            <div className="mt-4 inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-white/80 px-3 py-1 text-[10px] font-black uppercase tracking-[0.2em] text-indigo-700">
              <GitBranch className="h-3.5 w-3.5" />
              Path view
            </div>
            <h1 className="mt-4 max-w-4xl text-[1.9rem] font-black tracking-tight text-slate-900 sm:text-[2.45rem]">Your graph-backed learning path</h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">
              See what is open now, what is still blocked, and where the graph wants you to go next.
            </p>
            {mapData?.map_error && (
              <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-800">
                Graph data is incomplete: {mapData.map_error}
              </div>
            )}
          </div>
          <div className="flex flex-wrap gap-2 xl:max-w-[26rem] xl:justify-end">
            {(availableSubjects.length ? availableSubjects : enrolledSubjects).map((subject) => (
              <button
                key={subject}
                type="button"
                onClick={() => setActiveSubject(subject)}
                className={`rounded-2xl px-4 py-2 text-sm font-black capitalize transition ${
                  subject === activeSubject
                    ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-200'
                    : 'border border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
                }`}
              >
                {subject}
              </button>
            ))}
          </div>
        </div>

        {isLoading ? (
          <div className="flex min-h-[34vh] flex-col items-center justify-center rounded-[2rem] border border-slate-200 bg-white/90 px-6 text-center shadow-sm">
            <Loader2 className="h-10 w-10 animate-spin text-indigo-600" />
            <p className="mt-4 text-sm font-semibold text-slate-700">Loading your graph path...</p>
            <p className="mt-2 text-xs text-slate-500">We are pulling your latest mastery evidence and next graph recommendation.</p>
          </div>
        ) : error ? (
          <div className="rounded-[2rem] border border-rose-200 bg-white/90 p-6 shadow-sm">
            <p className="text-sm font-black uppercase tracking-[0.18em] text-rose-500">Graph unavailable</p>
            <p className="mt-3 text-lg font-bold text-slate-900">{error}</p>
          </div>
        ) : (
          <>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <StatCard
                icon={Sparkles}
                label="Ready nodes"
                value={graphStats.readyCount}
                subtext="Topics the graph says you can take on now."
                tone="indigo"
              />
              <StatCard
                icon={Lock}
                label="Blocked nodes"
                value={graphStats.blockerCount}
                subtext="Concepts still waiting on prerequisite repair."
                tone="amber"
              />
              <StatCard
                icon={GitBranch}
                label="Graph links"
                value={graphStats.relationCount}
                subtext="Prerequisite relationships shaping this scope."
                tone="slate"
              />
              <StatCard
                icon={Brain}
                label="Evidence events"
                value={graphStats.evidenceCount}
                subtext="Recent quiz and checkpoint events steering the path."
                tone="emerald"
              />
            </div>

            {evidenceSummary && (
              <div className="mt-5 grid gap-3 md:grid-cols-3">
                {[
                  { label: 'Demonstrated', value: evidenceSummary.demonstrated, tone: 'text-emerald-700' },
                  { label: 'Needs review', value: evidenceSummary.needs_review, tone: 'text-amber-700' },
                  { label: 'Unassessed', value: evidenceSummary.unassessed, tone: 'text-slate-500' },
                ].map((item) => (
                  <div key={item.label} className="rounded-2xl border border-slate-200 bg-white p-3.5 shadow-sm">
                    <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">{item.label}</p>
                    <p className={`mt-2 text-xl font-black ${item.tone}`}>{item.value}</p>
                    <p className="mt-2 text-xs text-slate-500">Graph-wide mastery evidence in this scope.</p>
                  </div>
                ))}
              </div>
            )}

            <div className="mt-5 grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_320px] 2xl:grid-cols-[minmax(0,1.2fr)_340px]">
              <div className="space-y-6">
                <LearningMap
                  classLevel={currentLevel}
                  subject={String(activeSubject || '').toUpperCase()}
                  mapData={mapData}
                  onSelectTopic={openLesson}
                />

                {safeArray(mapData?.intervention_timeline).length > 0 && (
                  <InterventionTimeline
                    title="Why the graph changed"
                    subtitle="Recent evidence from quiz and tutor checkpoints that moved your recommended next step."
                    timeline={mapData.intervention_timeline}
                  />
                )}
              </div>

              <div className="space-y-6">
                <div className="rounded-[1.75rem] border border-indigo-200 bg-white p-4 shadow-sm">
                  <p className="text-[10px] font-black uppercase tracking-[0.18em] text-indigo-500">Recommendation story</p>
                  <h2 className="mt-3 text-lg font-black text-slate-900 sm:text-xl">
                    {recommendationStory?.headline || recommendedTopic?.recommended_topic_title || 'Stay on the current graph path'}
                  </h2>
                  <p className="mt-3 text-sm leading-6 text-slate-600">
                    {recommendationStory?.supporting_reason || recommendedTopic?.reason || 'The graph is waiting for more evidence before changing your route.'}
                  </p>
                  {recommendationStory?.blocking_prerequisite_label && (
                    <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                      <p className="text-[10px] font-black uppercase tracking-[0.18em] text-amber-700">Blocking prerequisite</p>
                      <p className="mt-2 font-semibold">{recommendationStory.blocking_prerequisite_label}</p>
                    </div>
                  )}
                  {recommendedTopic?.recommended_topic_id && (
                    <button
                      type="button"
                      onClick={() => openLesson(recommendedTopic.recommended_topic_id)}
                      className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-indigo-600 px-4 py-3 text-sm font-black text-white hover:bg-indigo-700"
                    >
                      Open recommended lesson
                      <ArrowRight className="h-4 w-4" />
                    </button>
                  )}
                </div>

                <div className="rounded-[1.75rem] border border-slate-200 bg-white p-4 shadow-sm">
                  <div className="flex items-center gap-2">
                    <Target className="h-4 w-4 text-emerald-600" />
                    <p className="text-[10px] font-black uppercase tracking-[0.18em] text-emerald-600">Ready to move</p>
                  </div>
                  <div className="mt-4 space-y-3">
                    {readyTopics.length ? readyTopics.map((topic) => (
                      <button
                        key={topic.topic_id}
                        type="button"
                        onClick={() => openLesson(topic.topic_id)}
                        className="w-full rounded-2xl border border-emerald-100 bg-emerald-50 px-4 py-3 text-left transition hover:bg-emerald-100"
                      >
                        <p className="text-sm font-bold text-slate-900">{topic.title}</p>
                        <p className="mt-1 text-xs leading-6 text-emerald-900">{topic.graph_details || topic.description || 'Graph-ready lesson.'}</p>
                      </button>
                    )) : (
                      <p className="text-sm text-slate-500">No ready nodes are available in this scope yet.</p>
                    )}
                  </div>
                </div>

                <div className="rounded-[1.75rem] border border-slate-200 bg-white p-4 shadow-sm">
                  <div className="flex items-center gap-2">
                    <Lock className="h-4 w-4 text-amber-600" />
                    <p className="text-[10px] font-black uppercase tracking-[0.18em] text-amber-600">Still blocked</p>
                  </div>
                  <div className="mt-4 space-y-3">
                    {blockedTopics.length ? blockedTopics.map((topic) => (
                      <div key={topic.topic_id} className="rounded-2xl border border-amber-100 bg-amber-50 px-4 py-3">
                        <p className="text-sm font-bold text-slate-900">{topic.title}</p>
                        <p className="mt-1 text-xs leading-6 text-amber-900">{topic.graph_details || topic.lesson_unavailable_reason || 'Waiting on prerequisite mastery.'}</p>
                      </div>
                    )) : (
                      <p className="text-sm text-slate-500">No blocked nodes are visible in this scope right now.</p>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
