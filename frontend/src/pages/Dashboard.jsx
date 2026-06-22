import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, Loader2, BookOpen } from 'lucide-react';

import HeroSection from '../components/HeroSection';
import DashboardStats from '../components/DashboardStats';
import LearningTasks from '../components/LearningTasks';
import Leaderboard from '../components/Leaderboard';
import { useAuth } from '../context/AuthContext';
import { useUser } from '../context/UserContext';
import { resolveStudentId } from '../utils/sessionIdentity';
import { apiFetchJson } from '../services/api';
import {
    applyGraphInterventionOverlay,
    buildGraphInterventionScope,
    readLatestGraphIntervention,
    readGraphIntervention,
    subscribeGraphIntervention,
} from '../services/graphIntervention';

// 1. Import the useQuery hook from TanStack
import { useQuery } from '@tanstack/react-query';

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
        console.warn('Dashboard lesson prewarm skipped:', error);
    }
};

const normalizeCourseBootstrap = (data) => ({
    nodes: Array.isArray(data?.nodes) ? data.nodes : [],
    edges: Array.isArray(data?.edges) ? data.edges : [],
    next_step: data?.next_step || null,
    recent_evidence: data?.recent_evidence || null,
    intervention_timeline: Array.isArray(data?.intervention_timeline) ? data.intervention_timeline : [],
    recommendation_story: data?.recommendation_story || null,
});

const EMPTY_MAP_DATA = {
    nodes: [],
    edges: [],
    next_step: null,
    recent_evidence: null,
    intervention_timeline: [],
    recommendation_story: null,
};

export default function Dashboard() {
    const { token } = useAuth();
    const { userData, studentData } = useUser();
    const navigate = useNavigate();

    const activeId = resolveStudentId(studentData, userData);
    const currentLevel = studentData?.sss_level || 'SSS1';
    const currentTerm = studentData?.current_term || 1;
    const enrolledSubjects = studentData?.subjects || [];
    const latestIntervention = useMemo(
        () => readLatestGraphIntervention(activeId),
        [activeId],
    );

    const [activeSubject, setActiveSubject] = useState(() => localStorage.getItem('active_subject') || null);
    const [graphIntervention, setGraphIntervention] = useState(null);
    const [isNavigating, setIsNavigating] = useState(false);

    // =========================================================
    // 🔥 THE TANSTACK CACHE ENGINE: REPLACES SEVERAL OLD STATES
    // =========================================================
    const { data: dashboardData, isLoading: isLoadingMap } = useQuery({
        // The queryKey behaves like a dependencies cache fingerprint
        queryKey: ['dashboardBootstrap', activeId, activeSubject],
        queryFn: async () => {
            const queryParams = new URLSearchParams({ student_id: activeId });
            if (activeSubject) {
                queryParams.set('subject', activeSubject);
            }
            return apiFetchJson(`/learning/dashboard/bootstrap?${queryParams.toString()}`, {
                token,
            });
        },
        // Only trigger network flights once auth credentials cross down safely
        enabled: !!activeId && !!token,
        // The 'select' transformer automatically formats incoming payload frames cleanly 
        select: (data) => ({
            warmed_subjects: Array.isArray(data?.warmed_subjects) ? data.warmed_subjects : [],
            failed_subjects: Array.isArray(data?.failed_subjects) ? data.failed_subjects : [],
            available_subjects: Array.isArray(data?.available_subjects) ? data.available_subjects : [],
            mapData: normalizeCourseBootstrap(data?.course_bootstrap || {}),
            backendActiveSubject: data?.active_subject || null,
        }),
    });

    // Reactive layout bindings extracted safely from TanStack's cache target
    const bootstrapInfo = dashboardData || { warmed_subjects: [], failed_subjects: [], available_subjects: [] };
    const resolvedMapData = dashboardData?.mapData || EMPTY_MAP_DATA;

    // Synchronize current subject context state smoothly if backend requests a fallback shift
    useEffect(() => {
        if (dashboardData?.backendActiveSubject && dashboardData.backendActiveSubject !== activeSubject) {
            setActiveSubject(dashboardData.backendActiveSubject);
        }
    }, [dashboardData?.backendActiveSubject, activeSubject]);

    const interventionScope = useMemo(
        () => buildGraphInterventionScope({
            studentId: activeId,
            subject: activeSubject,
            sssLevel: currentLevel,
            term: currentTerm,
        }),
        [activeId, activeSubject, currentLevel, currentTerm],
    );

    const effectiveMapData = useMemo(
        () => applyGraphInterventionOverlay(resolvedMapData, graphIntervention),
        [graphIntervention, resolvedMapData],
    );

    const dashboardSignal = useMemo(() => {
        if (latestIntervention?.payload) {
            return latestIntervention;
        }
        if (!activeSubject) {
            return null;
        }
        if (!effectiveMapData?.next_step && !effectiveMapData?.recent_evidence && !effectiveMapData?.recommendation_story) {
            return null;
        }
        return {
            subject: activeSubject,
            sssLevel: currentLevel,
            term: currentTerm,
            payload: {
                next_step: effectiveMapData?.next_step || null,
                recent_evidence: effectiveMapData?.recent_evidence || null,
                recommendation_story: effectiveMapData?.recommendation_story || null,
                intervention_timeline: Array.isArray(effectiveMapData?.intervention_timeline) ? effectiveMapData.intervention_timeline : [],
            },
        };
    }, [activeSubject, currentLevel, currentTerm, effectiveMapData, latestIntervention]);

    useEffect(() => {
        if (!studentData) return;

        if (!studentData.sss_level || !studentData.current_term) {
            navigate('/class-selection', { replace: true });
            return;
        }

        if (!Array.isArray(studentData.subjects) || studentData.subjects.length === 0) {
            navigate('/subject-selection', { replace: true });
            return;
        }

        if (!studentData.has_profile || !studentData.preferences) {
            navigate('/learning-preferences', { replace: true });
            return;
        }
    }, [studentData, navigate]);

    useEffect(() => {
        if (!activeSubject && latestIntervention?.subject) {
            setActiveSubject(latestIntervention.subject);
        }
    }, [activeSubject, latestIntervention]);

    useEffect(() => {
        if (activeSubject) {
            localStorage.setItem('active_subject', activeSubject);
        }
    }, [activeSubject]);

    useEffect(() => {
        if (!interventionScope) {
            setGraphIntervention(null);
            return () => {};
        }
        setGraphIntervention(readGraphIntervention(interventionScope));
        return subscribeGraphIntervention(interventionScope, setGraphIntervention);
    }, [interventionScope]);

    const openTopicFromGraph = useCallback((topicId) => {
        if (!topicId || isNavigating) return;
        setIsNavigating(true);
        
        setTimeout(async () => {
            try {
                await prewarmTopics({
                    apiUrl: '', // Derived automatically in your env configuration
                    token, studentId: activeId, subject: activeSubject,
                    sssLevel: currentLevel, term: currentTerm, topicIds: [topicId],
                });
                navigate(`/lesson/${topicId}`);
            } catch (err) {
                setIsNavigating(false);
            }
        }, 200);
    }, [activeId, activeSubject, currentLevel, currentTerm, navigate, token, isNavigating]);

    const resumeLatestIntervention = useCallback(() => {
        if (isNavigating) return;
        const topicId = dashboardSignal?.payload?.next_step?.recommended_topic_id;
        if (!topicId) return;
        
        setIsNavigating(true);
        
        setTimeout(async () => {
            try {
                await prewarmTopics({
                    apiUrl: '',
                    token, studentId: activeId,
                    subject: dashboardSignal?.subject || activeSubject,
                    sssLevel: dashboardSignal?.sssLevel || currentLevel,
                    term: Number(dashboardSignal?.term || currentTerm),
                    topicIds: [topicId],
                });
                navigate(`/lesson/${topicId}`);
            } catch (err) {
                setIsNavigating(false);
            }
        }, 200);
    }, [activeId, activeSubject, dashboardSignal, navigate, token, isNavigating]);

    const openGraphPath = useCallback(() => {
        if (isNavigating) return;
        setIsNavigating(true);
        
        setTimeout(() => {
            const query = activeSubject ? `?subject=${encodeURIComponent(activeSubject)}` : '';
            navigate(`/graph-path${query}`);
        }, 200);
    }, [activeSubject, navigate, isNavigating]);

    const dashboardTasks = useMemo(() => {
        const tasks = [];
        const nextStep = dashboardSignal?.payload?.next_step || effectiveMapData?.next_step || null;
        const recommendationStory = dashboardSignal?.payload?.recommendation_story || effectiveMapData?.recommendation_story || null;
        const timeline = Array.isArray(dashboardSignal?.payload?.intervention_timeline)
            ? dashboardSignal.payload.intervention_timeline
            : Array.isArray(effectiveMapData?.intervention_timeline)
                ? effectiveMapData.intervention_timeline
                : [];
        const hasPendingCheckpoint = recommendationStory?.status === 'resume_checkpoint';

        if (hasPendingCheckpoint) {
            tasks.push({
                id: 'resume-checkpoint',
                badge: 'Checkpoint',
                title: recommendationStory?.headline || nextStep?.recommended_topic_title || 'Resume your checkpoint',
                subtext: recommendationStory?.supporting_reason || 'A tutor checkpoint is waiting inside the current lesson.',
                actionLabel: isNavigating ? 'Loading...' : 'Resume checkpoint',
                onClick: resumeLatestIntervention,
                tone: 'emerald',
            });
        }

        if (!hasPendingCheckpoint && nextStep?.recommended_topic_id) {
            tasks.push({
                id: 'recommended-lesson',
                badge: recommendationStory?.status === 'bridge_prerequisite' ? 'Repair gap' : 'Next lesson',
                title: nextStep.recommended_topic_title || nextStep.recommended_concept_label || 'Continue your graph path',
                subtext: recommendationStory?.supporting_reason || nextStep.reason || 'Open the lesson the graph recommends next.',
                actionLabel: isNavigating ? 'Loading...' : (recommendationStory?.action_label || 'Open lesson'),
                onClick: resumeLatestIntervention,
                tone: recommendationStory?.status === 'bridge_prerequisite' ? 'amber' : 'indigo',
            });
        }

        if (timeline.length > 0) {
            tasks.push({
                id: 'latest-evidence',
                badge: timeline[0].source_label || 'Latest evidence',
                title: timeline[0].focus_concept_label || 'Review your latest intervention',
                subtext: timeline[0].summary,
                actionLabel: isNavigating ? 'Loading...' : 'Resume',
                onClick: resumeLatestIntervention,
                tone: 'slate',
            });
        }

        const alternateNode = Array.isArray(effectiveMapData?.nodes)
            ? effectiveMapData.nodes.find(
                (node) =>
                    node?.topic_id &&
                    node.status === 'ready' &&
                    node.topic_id !== nextStep?.recommended_topic_id,
            )
            : null;
        if (alternateNode?.topic_id) {
            tasks.push({
                id: 'alternate-ready-node',
                badge: 'Ready concept',
                title: alternateNode.concept_label || alternateNode.topic_title || 'Explore a ready concept',
                subtext: alternateNode.details || 'Open another graph-ready lesson in this scope.',
                actionLabel: isNavigating ? 'Loading...' : 'Open node',
                onClick: () => openTopicFromGraph(alternateNode.topic_id),
                tone: 'indigo',
            });
        }

        return tasks.slice(0, 3);
    }, [dashboardSignal, effectiveMapData, openTopicFromGraph, resumeLatestIntervention, isNavigating]);

    return (
        <div className="min-h-screen overflow-x-hidden bg-[#F8FAFC] font-sans">
            <main className="mx-auto max-w-[1440px] px-4 py-6 sm:px-6">
                <div className="mb-6">
                    <HeroSection
                        enrolledSubjects={bootstrapInfo.available_subjects.length ? bootstrapInfo.available_subjects : enrolledSubjects}
                        activeSubject={activeSubject}
                        onSelectSubject={setActiveSubject}
                        hasStartedLearning={false}
                        warmedSubjects={bootstrapInfo.warmed_subjects}
                        graphSignal={dashboardSignal}
                        signalSubject={dashboardSignal?.subject || activeSubject}
                        onResumeSignal={dashboardSignal?.payload?.next_step?.recommended_topic_id ? resumeLatestIntervention : null}
                        isNavigating={isNavigating} 
                    />
                </div>

                <DashboardStats />

                {!activeSubject ? (
                    <div className="mb-6 flex w-full flex-col items-center justify-center rounded-2xl border border-slate-200 bg-white p-6 text-center shadow-sm">
                        <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-indigo-50 text-indigo-400 shadow-inner">
                            <BookOpen className="h-10 w-10" strokeWidth={1.5} />
                        </div>
                        <h3 className="mb-3 text-lg font-bold text-slate-800">Choose a subject to launch</h3>
                        <p className="mx-auto max-w-md text-sm leading-6 text-slate-500">Select a subject above to load your active path and next tasks.</p>
                    </div>
                ) : isLoadingMap ? (
                    <div className="mb-6 flex w-full flex-col items-center rounded-2xl border border-slate-200 bg-white p-6 text-center font-medium text-indigo-500 shadow-sm animate-pulse">
                        <Loader2 className="mb-4 h-10 w-10 animate-spin" />
                        Syncing your {activeSubject} path...
                    </div>
                ) : (
                    <>
                        <div className="mb-6 rounded-2xl border border-indigo-100 bg-indigo-50/50 p-4 sm:p-6 flex flex-col sm:flex-row items-center justify-between gap-4 shadow-sm">
                            <div className="text-center sm:text-left">
                                <h3 className="text-lg font-bold text-slate-900">Curious why we recommended this?</h3>
                                <p className="mt-1 text-sm text-slate-600">Explore your full knowledge graph, mastery evidence, and upcoming unlocks.</p>
                            </div>
                            <button
                                type="button"
                                disabled={isNavigating}
                                onClick={openGraphPath}
                                className={`shrink-0 inline-flex items-center gap-2 rounded-xl bg-white px-5 py-3 text-sm font-bold text-indigo-600 shadow-sm border border-indigo-200 hover:bg-indigo-50 transition ${isNavigating ? 'opacity-50 cursor-not-allowed' : ''}`}
                            >
                                {isNavigating ? (
                                    <>
                                        <Loader2 className="h-4 w-4 animate-spin" />
                                        Loading...
                                    </>
                                ) : (
                                    <>
                                        View full path
                                        <ArrowRight className="h-4 w-4" />
                                    </>
                                )}
                            </button>
                        </div>
                        
                        <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
                            <LearningTasks tasks={dashboardTasks} />
                            <Leaderboard leagueName={studentData?.league_name || 'Current League'} />
                        </div>
                    </>
                )}
            </main>
        </div>
    );
}