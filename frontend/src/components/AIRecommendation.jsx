import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertCircle, Brain, ChevronRight, GitBranch, Loader2, Lock, Sparkles } from 'lucide-react';

import { useAuth } from '../context/AuthContext';
import { useUser } from '../context/UserContext';
import { API_URL } from '../config/runtime';
import { resolveStudentId } from '../utils/sessionIdentity';
import { apiFetchJson } from '../services/api';

const safeArray = (value) => (Array.isArray(value) ? value : []);

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
    console.warn('Dashboard recommendation prewarm skipped:', error);
  }
};

export default function AIRecommendation({
  recommendation: recommendationOverride = null,
  activeSubject: activeSubjectProp = null,
  recentEvidence: recentEvidenceOverride = null,
  recommendationStory: recommendationStoryOverride = null,
  errorOverride = '',
  disableAutoFetch = false,
}) {
  const navigate = useNavigate();
  const { token } = useAuth();
  const { studentData, userData } = useUser();
  const activeId = resolveStudentId(studentData, userData);

  const currentSubject = activeSubjectProp || localStorage.getItem('active_subject') || studentData?.subjects?.[0] || 'math';
  const currentLevel = studentData?.sss_level || 'SSS1';
  const currentTerm = studentData?.current_term || 1;
  const apiUrl = API_URL;

  const [recommendation, setRecommendation] = useState(null);
  const [recentEvidence, setRecentEvidence] = useState(null);
  const [recommendationStory, setRecommendationStory] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (recommendationOverride) {
      setRecommendation(recommendationOverride);
      setRecentEvidence(recentEvidenceOverride || null);
      setRecommendationStory(recommendationStoryOverride || null);
      setError('');
      setIsLoading(false);
      return;
    }

    if (errorOverride) {
      setRecommendation(null);
      setRecentEvidence(null);
      setRecommendationStory(null);
      setError(errorOverride);
      setIsLoading(false);
      return;
    }

    if (disableAutoFetch) {
      setRecommendation(null);
      setRecentEvidence(null);
      setRecommendationStory(null);
      setError('');
      setIsLoading(false);
      return;
    }

    if (!activeId || !token) return;

    const fetchNextStep = async () => {
      setIsLoading(true);
      setError('');

      try {
        const queryParams = new URLSearchParams({
          student_id: activeId,
          subject: currentSubject,
          term: currentTerm,
        });

        const data = await apiFetchJson(`/learning/course/bootstrap?${queryParams.toString()}`, {
          token,
          timeoutMs: 40000,
        });

        if (!data?.next_step) {
          throw new Error(data?.map_error || 'Graph recommendation unavailable.');
        }

        setRecommendation(data.next_step);
        setRecentEvidence(data.recent_evidence || null);
        setRecommendationStory(data.recommendation_story || null);
      } catch (err) {
        setError(err.message || 'Graph recommendation unavailable.');
      } finally {
        setIsLoading(false);
      }
    };

    void fetchNextStep();
  }, [
    activeId,
    currentSubject,
    currentTerm,
    token,
    recommendationOverride,
    recentEvidenceOverride,
    recommendationStoryOverride,
    errorOverride,
    disableAutoFetch,
  ]);

  if (isLoading) {
    return (
      <div className="flex min-h-[220px] w-full flex-col items-center justify-center rounded-2xl border border-slate-200 bg-white p-5 text-center shadow-sm lg:w-[320px]">
        <Loader2 className="mb-3 h-7 w-7 animate-spin text-indigo-600" />
        <p className="text-sm font-semibold text-slate-600">Preparing your next graph move...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-[220px] w-full flex-col items-center justify-center rounded-2xl border border-amber-200 bg-amber-50/60 p-5 text-center shadow-sm lg:w-[320px]">
        <AlertCircle className="mb-3 h-7 w-7 text-amber-500" />
        <p className="text-[10px] font-black uppercase tracking-[0.18em] text-amber-700">Recommendation warming up</p>
        <p className="mt-2 text-sm font-semibold text-amber-900">{error}</p>
      </div>
    );
  }

  if (!recommendation) {
    return (
      <div className="flex min-h-[220px] w-full flex-col items-center justify-center rounded-2xl border border-slate-200 bg-white p-5 text-center shadow-sm lg:w-[320px]">
        <Lock className="mb-3 h-7 w-7 text-slate-300" />
        <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Graph recommendation</p>
        <p className="mt-2 text-sm font-semibold text-slate-600">No recommendation is ready for this subject yet.</p>
      </div>
    );
  }

  const hasPrereqGap = safeArray(recommendation.prereq_gaps).length > 0;
  const blockingLabels = safeArray(recommendation.prereq_gap_labels);
  const recommendedTopicId = recommendation.recommended_topic_id || null;
  const story = recommendationStory || null;

  const title = story?.headline
    || recommendation.recommended_topic_title
    || recommendation.recommended_concept_label
    || 'Recommended next lesson';

  const subtitle = story?.supporting_reason
    || recommendation.reason
    || 'Use this next graph-backed move to keep progressing.';

  const actionLabel = story?.action_label || (hasPrereqGap ? 'Repair first' : 'Open lesson');

  return (
    <aside className="w-full overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm lg:w-[320px]">
      <div className="border-b border-slate-100 px-5 py-4">
        <div className="flex items-center justify-between gap-3">
          <div className="inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em] text-indigo-700">
            <GitBranch className="h-3.5 w-3.5" />
            Graph recommendation
          </div>
          <span className="text-[11px] font-semibold text-slate-400">Now</span>
        </div>
        <h3 className="mt-3 text-lg font-black text-slate-900">{title}</h3>
        <p className="mt-2 text-sm leading-6 text-slate-600">{subtitle}</p>
      </div>

      <div className="space-y-4 px-5 py-4">
        {hasPrereqGap && (
          <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3">
            <div className="text-[10px] font-black uppercase tracking-[0.18em] text-amber-700">Repair blocker</div>
            <p className="mt-2 text-sm font-semibold text-amber-900">{blockingLabels[0] || 'Prerequisite gap detected'}</p>
          </div>
        )}

        {!hasPrereqGap && recommendation.recommended_concept_label && (
          <div className="rounded-2xl border border-indigo-200 bg-indigo-50 px-4 py-3">
            <div className="inline-flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.18em] text-indigo-700">
              <Brain className="h-3.5 w-3.5" />
              Focus concept
            </div>
            <p className="mt-2 text-sm font-semibold text-indigo-900">{recommendation.recommended_concept_label}</p>
          </div>
        )}

        {recentEvidence && (
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
            <div className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-500">Latest evidence</div>
            <p className="mt-2 text-sm leading-6 text-slate-700">{recentEvidence.summary}</p>
          </div>
        )}

        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
            <div className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Threshold</div>
            <p className="mt-2 text-base font-black text-slate-900">70% mastery</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
            <div className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Subject</div>
            <p className="mt-2 text-base font-black capitalize text-slate-900">{currentSubject}</p>
          </div>
        </div>

        <button
          type="button"
          onClick={async () => {
            if (!recommendedTopicId) return;
            await prewarmTopics({
              apiUrl,
              token,
              studentId: activeId,
              subject: currentSubject,
              sssLevel: currentLevel,
              term: currentTerm,
              topicIds: [recommendedTopicId],
            });
            navigate(`/lesson/${recommendedTopicId}`);
          }}
          disabled={!recommendedTopicId}
          className={`inline-flex w-full items-center justify-center gap-2 rounded-2xl px-4 py-3 text-sm font-black transition ${
            recommendedTopicId
              ? 'bg-indigo-600 text-white hover:bg-indigo-700'
              : 'cursor-not-allowed bg-slate-100 text-slate-400'
          }`}
        >
          {recommendedTopicId ? (
            <>
              <Sparkles className="h-4 w-4" />
              {actionLabel}
              <ChevronRight className="h-4 w-4" />
            </>
          ) : (
            <>
              <Lock className="h-4 w-4" />
              No lesson ready
            </>
          )}
        </button>
      </div>
    </aside>
  );
}
