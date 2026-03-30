import React, { useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useUser } from '../context/UserContext';
import CourseSidebar from '../components/CourseSidebar';
import InterventionTimeline from '../components/InterventionTimeline';
import { PlayCircle, Clock, BookOpen, GitBranch, Lock, Sparkles } from 'lucide-react';
import { API_URL } from '../config/runtime';
import { resolveStudentId } from '../utils/sessionIdentity';
import { apiFetchJson } from '../services/api';
import {
  buildGraphInterventionScope,
  readGraphIntervention,
  subscribeGraphIntervention,
} from '../services/graphIntervention';

const safeArray = (value) => (Array.isArray(value) ? value : []);

const statusStyles = {
  current: 'border-indigo-300 bg-indigo-50 text-indigo-700',
  ready: 'border-sky-300 bg-sky-50 text-sky-700',
  mastered: 'border-emerald-300 bg-emerald-50 text-emerald-700',
  locked: 'border-slate-200 bg-slate-50 text-slate-500',
  unmapped: 'border-amber-300 bg-amber-50 text-amber-800',
  pending: 'border-slate-200 bg-slate-50 text-slate-500',
};

const statusLabels = {
  current: 'Current focus',
  ready: 'Ready',
  mastered: 'Mastered',
  locked: 'Locked',
  unmapped: 'Mapping pending',
  pending: 'Pending',
};

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
    console.warn('Course recommendation prewarm skipped:', error);
  }
};

const CoursePage = () => {
  const { subject } = useParams(); 
  const navigate = useNavigate();
  
  const { token } = useAuth();
  const { studentData, userData } = useUser();
  const activeId = resolveStudentId(studentData, userData);
  const currentLevel = studentData?.sss_level || 'SSS1';
  const currentTerm = studentData?.current_term || 1;

  const [topics, setTopics] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [nextStep, setNextStep] = useState(null);
  const [recentEvidence, setRecentEvidence] = useState(null);
  const [evidenceSummary, setEvidenceSummary] = useState(null);
  const [interventionTimeline, setInterventionTimeline] = useState([]);
  const [recommendationStory, setRecommendationStory] = useState(null);
  const [diagnosticStatus, setDiagnosticStatus] = useState(null);
  const [learningGapSummary, setLearningGapSummary] = useState(null);
  const [initialLessonPlan, setInitialLessonPlan] = useState(null);
  const [mapError, setMapError] = useState('');
  const [bootstrapError, setBootstrapError] = useState('');
  const [graphIntervention, setGraphIntervention] = useState(null);

  const apiUrl = API_URL;
  const interventionScope = useMemo(
    () => buildGraphInterventionScope({
      studentId: activeId,
      subject,
      sssLevel: currentLevel,
      term: currentTerm,
    }),
    [activeId, currentLevel, currentTerm, subject],
  );
  const effectiveNextStep = graphIntervention?.next_step || nextStep || null;
  const effectiveRecentEvidence = graphIntervention?.recent_evidence || recentEvidence || null;
  const effectiveRecommendationStory = graphIntervention?.recommendation_story || recommendationStory || null;
  const effectiveAnalytics = graphIntervention?.analytics || null;
  const effectiveTimeline = Array.isArray(interventionTimeline) ? interventionTimeline : [];

  useEffect(() => {
    if (!interventionScope) {
      setGraphIntervention(null);
      return () => {};
    }
    setGraphIntervention(readGraphIntervention(interventionScope));
    return subscribeGraphIntervention(interventionScope, setGraphIntervention);
  }, [interventionScope]);

  useEffect(() => {
    if (!activeId || !token || !subject) return;

    const fetchTopicsList = async () => {
      setIsLoading(true);
      setMapError('');
      setBootstrapError('');

      try {
        const bootstrapParams = new URLSearchParams({
          student_id: activeId,
          subject: subject,
          term: currentTerm,
        });
        const data = await apiFetchJson(`/learning/course/bootstrap?${bootstrapParams.toString()}`, {
          token,
        });
        localStorage.setItem('active_subject', subject);
        setTopics(safeArray(data?.topics));
        setNextStep(data?.next_step || null);
        setRecentEvidence(data?.recent_evidence || null);
        setEvidenceSummary(data?.evidence_summary || null);
        setInterventionTimeline(safeArray(data?.intervention_timeline));
        setRecommendationStory(data?.recommendation_story || null);
        setDiagnosticStatus(data?.diagnostic_status || null);
        setLearningGapSummary(data?.learning_gap_summary || null);
        setInitialLessonPlan(data?.initial_lesson_plan || null);
        setMapError(data?.map_error || '');

      } catch (err) {
        console.error("CoursePage Error:", err);
        setBootstrapError(err.message || 'Course bootstrap failed.');
        setTopics([]);
        setNextStep(null);
        setRecentEvidence(null);
        setEvidenceSummary(null);
        setInterventionTimeline([]);
        setRecommendationStory(null);
        setDiagnosticStatus(null);
        setLearningGapSummary(null);
        setInitialLessonPlan(null);
      } finally {
        setIsLoading(false);
      }
    };
    
    fetchTopicsList();
  }, [activeId, token, subject, currentLevel, currentTerm, apiUrl]);

  const displayTopics = useMemo(
    () => (Array.isArray(topics) ? topics : []).map((topic) => (
      effectiveNextStep?.recommended_topic_id && topic?.topic_id === effectiveNextStep.recommended_topic_id
        ? { ...topic, is_recommended: true }
        : topic
    )),
    [effectiveNextStep, topics],
  );

  return (
    <div className="flex min-h-[calc(100vh-64px)] flex-col bg-slate-50 lg:h-[calc(100vh-64px)] lg:flex-row lg:overflow-hidden">
      
      {/* Sidebar */}
      <CourseSidebar 
        activeStep={null} 
        subject={subject} 
        topics={displayTopics} 
        level={currentLevel}
      />
      
      {/* Main Content Area */}
      <div className="min-w-0 flex-1 px-4 py-5 sm:px-6 lg:overflow-y-auto lg:px-8">
        <div className="mx-auto max-w-5xl">
          
          <div className="mb-6">
            <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Subject path</p>
            <h1 className="mt-2 text-2xl font-black capitalize text-slate-900 sm:text-[2.5rem]">{subject} learning path</h1>
            <p className="mt-2 text-sm leading-6 text-slate-500">Graph-backed lessons for {currentLevel} {subject}, ordered by readiness and prerequisite strength.</p>
          </div>

          {effectiveAnalytics && (
            <div className="mb-5 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex flex-wrap items-center gap-2 text-[10px] font-black uppercase tracking-[0.18em] text-slate-500">
                <GitBranch className="h-3.5 w-3.5 text-indigo-500" />
                Current graph signal
                {effectiveAnalytics.source_label && (
                  <span className="rounded-full bg-indigo-50 px-2 py-1 text-[10px] text-indigo-700">
                    {effectiveAnalytics.source_label}
                  </span>
                )}
              </div>
              <div className="mt-3 grid gap-3 md:grid-cols-3">
                <div className="rounded-2xl bg-slate-50 p-3">
                  <div className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-400">Focus concept</div>
                  <p className="mt-1 text-sm font-bold text-slate-800">{effectiveAnalytics.focus_concept || 'Current course focus'}</p>
                </div>
                <div className="rounded-2xl bg-slate-50 p-3">
                  <div className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-400">Blocking prerequisite</div>
                  <p className="mt-1 text-sm font-bold text-slate-800">{effectiveAnalytics.blocking_prerequisite || 'No active prerequisite block'}</p>
                </div>
                <div className="rounded-2xl bg-slate-50 p-3">
                  <div className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-400">Best action</div>
                  <p className="mt-1 text-sm font-bold text-slate-800">{effectiveAnalytics.outcome || effectiveRecommendationStory?.action_label || 'Keep learning'}</p>
                </div>
              </div>
            </div>
          )}

          {(initialLessonPlan || learningGapSummary) && (
            <div className="mb-5 rounded-2xl border border-indigo-200 bg-gradient-to-r from-indigo-50 via-white to-sky-50 p-4 shadow-sm">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="max-w-2xl">
                  <div className="inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-white px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em] text-indigo-700">
                    <GitBranch className="h-3.5 w-3.5" />
                    Baseline lesson plan
                  </div>
                  <h2 className="mt-3 text-lg font-black text-slate-900 sm:text-xl">
                    {initialLessonPlan?.recommended_topic_title
                      || learningGapSummary?.recommended_start_topic_title
                      || `Start rebuilding ${subject}`}
                  </h2>
                  <p className="mt-2 text-sm leading-7 text-slate-600">
                    {initialLessonPlan?.rationale
                      || learningGapSummary?.rationale
                      || 'Your onboarding diagnostic has already shaped this subject path.'}
                  </p>
                  {initialLessonPlan?.prerequisite_repair_label && (
                    <p className="mt-3 text-sm font-semibold text-amber-700">
                      Repair first: {initialLessonPlan.prerequisite_repair_label}
                    </p>
                  )}
                </div>
                <div className="grid gap-3 sm:grid-cols-2 lg:w-[18rem]">
                  <div className="rounded-2xl border border-slate-200 bg-white p-4">
                    <div className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-400">Diagnostic status</div>
                    <p className="mt-2 text-sm font-black text-slate-900">
                      {diagnosticStatus?.status === 'completed' ? 'Completed' : diagnosticStatus?.status === 'in_progress' ? 'In progress' : 'Pending'}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-white p-4">
                    <div className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-400">Next action</div>
                    <p className="mt-2 text-sm font-black text-slate-900">
                      {initialLessonPlan?.next_best_action || learningGapSummary?.next_best_action || 'Open recommended lesson'}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {evidenceSummary && (
            <div className="mb-5 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex flex-wrap items-center gap-2 text-[10px] font-black uppercase tracking-[0.18em] text-slate-500">
                <GitBranch className="h-3.5 w-3.5 text-emerald-500" />
                Mastery evidence snapshot
              </div>
              <div className="mt-3 grid gap-3 md:grid-cols-3">
                {[
                  { label: 'Demonstrated', value: evidenceSummary.demonstrated, tone: 'text-emerald-700' },
                  { label: 'Needs review', value: evidenceSummary.needs_review, tone: 'text-amber-700' },
                  { label: 'Unassessed', value: evidenceSummary.unassessed, tone: 'text-slate-500' },
                ].map((item) => (
                  <div key={item.label} className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
                    <div className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-400">{item.label}</div>
                    <p className={`mt-1 text-sm font-bold ${item.tone}`}>{item.value}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {effectiveNextStep && (
            <div className="mb-5 rounded-2xl border border-indigo-200 bg-gradient-to-r from-indigo-50 via-white to-sky-50 p-4 shadow-sm">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="max-w-2xl">
                  <div className="inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-white px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em] text-indigo-700">
                    <GitBranch className="h-3.5 w-3.5" />
                    Next best move
                  </div>
                  <h2 className="mt-3 text-lg font-black text-slate-900 sm:text-xl">
                    {effectiveRecommendationStory?.headline || effectiveNextStep.recommended_topic_title || effectiveNextStep.recommended_concept_label || effectiveNextStep.reason || 'Graph recommendation unavailable'}
                  </h2>
                  <p className="mt-2 text-sm leading-7 text-slate-600">{effectiveRecommendationStory?.supporting_reason || effectiveNextStep.reason}</p>
                  {safeArray(effectiveNextStep.prereq_gap_labels).length > 0 && (
                    <p className="mt-3 text-sm font-semibold text-amber-700">
                      Blocking prerequisites: {effectiveNextStep.prereq_gap_labels.join(', ')}
                    </p>
                  )}
                  {effectiveRecommendationStory?.next_concept_label && (
                    <p className="mt-3 text-sm font-semibold text-cyan-700">
                      Best next concept: {effectiveRecommendationStory.next_concept_label}
                    </p>
                  )}
                  {effectiveRecommendationStory?.evidence_summary && (
                    <p className="mt-3 text-sm leading-7 text-slate-500">
                      {effectiveRecommendationStory.evidence_summary}
                    </p>
                  )}
                </div>
                <button
                  onClick={async () => {
                    if (effectiveNextStep.recommended_topic_id) {
                      await prewarmTopics({
                        apiUrl,
                        token,
                        studentId: activeId,
                        subject,
                        sssLevel: currentLevel,
                        term: currentTerm,
                        topicIds: [effectiveNextStep.recommended_topic_id],
                      });
                      navigate(`/lesson/${effectiveNextStep.recommended_topic_id}`);
                    }
                  }}
                  disabled={!effectiveNextStep.recommended_topic_id}
                  className={`inline-flex items-center justify-center gap-2 rounded-2xl px-5 py-3 text-sm font-black transition-colors ${
                    effectiveNextStep.recommended_topic_id
                      ? 'bg-indigo-600 text-white hover:bg-indigo-700'
                      : 'bg-slate-200 text-slate-500 cursor-not-allowed'
                  }`}
                >
                  {effectiveRecommendationStory?.action_label || 'Open Recommended Lesson'} <Sparkles className="h-4 w-4" />
                </button>
              </div>
              {mapError && (
                <p className="mt-4 text-xs font-semibold text-slate-500">{mapError}</p>
              )}
            </div>
          )}

          {effectiveRecentEvidence && (
            <div className="mb-5 rounded-2xl border border-indigo-100 bg-white p-4 shadow-sm">
              <div className="text-[10px] font-black uppercase tracking-[0.18em] text-indigo-600">Latest evidence</div>
              <p className="mt-2 text-sm leading-7 text-slate-700">{effectiveRecentEvidence.summary}</p>
              {(effectiveRecentEvidence.strongest_gain_concept_label || effectiveRecentEvidence.strongest_drop_concept_label) && (
                <p className="mt-3 text-xs font-semibold text-slate-500">
                  {effectiveRecentEvidence.strongest_gain_concept_label ? `Gain: ${effectiveRecentEvidence.strongest_gain_concept_label}` : 'No recent gain'}
                  {effectiveRecentEvidence.strongest_drop_concept_label ? ` - Gap: ${effectiveRecentEvidence.strongest_drop_concept_label}` : ''}
                </p>
              )}
            </div>
          )}

          {effectiveTimeline.length > 0 && (
            <div className="mb-5">
              <InterventionTimeline
                title="Evidence Timeline"
                subtitle="Recent quiz and checkpoint evidence guiding this subject path."
                timeline={effectiveTimeline}
              />
            </div>
          )}

          {mapError && !effectiveNextStep && (
            <div className="mb-6 rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4 text-sm font-semibold text-amber-800">
              {mapError}
            </div>
          )}

          {bootstrapError && !isLoading ? (
            <div className="rounded-2xl border border-rose-200 bg-white px-6 py-8 text-center shadow-sm">
              <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-rose-50 text-rose-400">
                <BookOpen className="h-10 w-10" />
              </div>
              <h3 className="text-lg font-bold text-slate-800">Course bootstrap failed</h3>
              <p className="mx-auto mt-3 max-w-xl text-sm leading-6 text-slate-500">{bootstrapError}</p>
              <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-slate-400">
                The subject path could not load from the backend for this scope, so we are not treating it as an empty syllabus.
              </p>
            </div>
          ) : isLoading ? (
            <div className="space-y-3 animate-pulse">
               {[1,2,3,4].map(i => (
                 <div key={i} className="h-24 w-full rounded-2xl border border-slate-200 bg-white"></div>
               ))}
            </div>
          ) : displayTopics.length > 0 ? (
            <div className="space-y-3">
              {displayTopics.map((topic, index) => {
                const targetId = topic.topic_id || topic.id;
                const currentStatus = topic.status || 'pending';
                const isLocked = currentStatus === 'locked';
                const isRecommended = Boolean(topic.is_recommended);
                const cardStyle = statusStyles[currentStatus] || statusStyles.pending;
                const openTopic = async () => {
                  if (isLocked || !targetId) return;
                  await prewarmTopics({
                    apiUrl,
                    token,
                    studentId: activeId,
                    subject,
                    sssLevel: currentLevel,
                    term: currentTerm,
                    topicIds: [targetId],
                  });
                  navigate(`/lesson/${targetId}`);
                };

                return (
                  <div 
                    key={targetId || index} 
                    onClick={openTopic}
                    className={`group flex flex-col justify-between gap-4 rounded-2xl border bg-white p-4 transition-all md:flex-row md:items-center ${
                      isLocked ? 'opacity-75 cursor-not-allowed border-slate-200' : 'cursor-pointer hover:shadow-md'
                    } ${
                      isRecommended ? 'border-indigo-300 shadow-[0_18px_50px_rgba(99,102,241,0.10)]' : cardStyle.includes('border-') ? cardStyle.split(' ')[0] : 'border-slate-200'
                    }`}
                  >
                    <div className="flex items-start gap-5">
                      <div className={`w-12 h-12 rounded-full flex items-center justify-center text-lg font-bold flex-shrink-0 mt-1 md:mt-0 ${
                        currentStatus === 'mastered'
                          ? 'bg-emerald-50 text-emerald-600'
                          : currentStatus === 'current'
                            ? 'bg-indigo-50 text-indigo-600'
                            : currentStatus === 'ready'
                              ? 'bg-sky-50 text-sky-600'
                              : 'bg-slate-100 text-slate-500'
                      }`}>
                          {index + 1}
                      </div>
                      <div>
                        <div className="mb-2 flex flex-wrap items-center gap-2">
                          <span className={`rounded-full px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.18em] ${cardStyle}`}>
                            {statusLabels[currentStatus] || 'Pending'}
                          </span>
                          {isRecommended && (
                            <span className="rounded-full bg-indigo-600 px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.18em] text-white">
                              Recommended now
                            </span>
                          )}
                        </div>
                        <h3 className="text-[15px] font-bold text-slate-900 transition-colors group-hover:text-indigo-600 md:text-base">
                            {topic.title || 'Untitled Topic'}
                        </h3>
                        <p className="text-sm text-slate-500 mt-1 line-clamp-2 max-w-xl">
                            {topic.graph_details || topic.description || topic.lesson_unavailable_reason || 'Topic context unavailable.'}
                        </p>
                        <div className="flex items-center gap-4 mt-3">
                           {topic.estimated_duration_minutes && (
                              <span className="flex items-center gap-1.5 text-xs font-bold text-slate-400">
                                 <Clock className="w-3.5 h-3.5" />
                                 ~{topic.estimated_duration_minutes} Mins
                              </span>
                           )}
                           {topic.lesson_title && (
                              <span className="flex items-center gap-1.5 text-xs font-bold text-slate-400 truncate max-w-[200px]">
                                 <BookOpen className="w-3.5 h-3.5" />
                                 {topic.lesson_title}
                              </span>
                           )}
                           <span className="text-xs font-bold text-slate-400">
                             {Math.round((topic.mastery_score || 0) * 100)}% mastery
                           </span>
                        </div>
                      </div>
                    </div>

                    <button className={`flex w-full items-center justify-center gap-2 rounded-xl px-5 py-3 text-sm font-bold transition-colors md:w-auto ${
                      isLocked
                        ? 'bg-slate-100 text-slate-400 cursor-not-allowed'
                        : 'bg-slate-100 text-slate-600 group-hover:bg-indigo-600 group-hover:text-white'
                    }`}>
                        {isLocked ? 'Locked in graph' : 'Start Lesson'} {isLocked ? <Lock className="w-4 h-4" /> : <PlayCircle className="w-4 h-4" />}
                    </button>
                  </div>
                );
              })}
            </div>
          ) : (
             <div className="rounded-2xl border border-slate-200 bg-white py-10 text-center shadow-sm">
                 <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-slate-50 text-slate-300">
                    <BookOpen className="w-10 h-10" />
                 </div>
                 <h3 className="mb-2 text-lg font-bold text-slate-800">No topics available</h3>
                 <p className="mx-auto max-w-md text-sm leading-6 text-slate-500">
                   No approved mapped topics were returned for {currentLevel} {subject} Term {currentTerm}. This scope needs real backend data before a lesson can open.
                 </p>
             </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default CoursePage;

