import React, { useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  ArrowRight,
  BarChart3,
  BookOpenCheck,
  BrainCircuit,
  Download,
  Flame,
  GitBranch,
  Loader2,
  NotebookPen,
  Route,
  Sparkles,
  ShieldAlert,
  UserRoundSearch,
  Users,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { API_URL } from '../config/runtime';
import TeacherClassGraph from '../components/teacher/TeacherClassGraph';
import TeacherExportModal from '../components/teacher/TeacherExportModal';
import TeacherStudentFocusDrawer from '../components/teacher/TeacherStudentFocusDrawer';

const actionRefId = (action) => {
  const raw = String(action?.target_concept_id || action?.target_topic_id || action?.target_concept_label || action?.title || 'graph-action').trim().toLowerCase();
  return `graph-${String(action?.action_type || 'action').replace(/[^a-z0-9]+/gi, '-')}-${raw.replace(/[^a-z0-9]+/gi, '-').replace(/^-+|-+$/g, '')}`;
};

const isLikelyUuid = (value) => /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(String(value || '').trim());

const humanizeConceptId = (conceptId, fallback = 'Concept') => {
  const value = String(conceptId || '').trim();
  if (!value) return fallback;
  const cleaned = value.startsWith('topic:') ? value.replace(/^topic:/i, '') : value;
  if (isLikelyUuid(cleaned)) return fallback;
  const token = value.split(':').pop()?.trim() || value;
  return token
    .replace(/-(\d+)$/, '')
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase()) || fallback;
};

const formatStudyTime = (seconds) => {
  const total = Number(seconds || 0);
  if (!total) return '0m';
  const minutes = Math.round(total / 60);
  const hours = Math.floor(minutes / 60);
  const remaining = minutes % 60;
  return hours > 0 ? `${hours}h ${remaining}m` : `${remaining}m`;
};

const StatCard = ({ title, value, subtitle, icon: Icon, tone = 'indigo' }) => {
  const tones = {
    indigo: 'bg-indigo-50 text-indigo-600',
    amber: 'bg-amber-50 text-amber-600',
    emerald: 'bg-emerald-50 text-emerald-600',
    slate: 'bg-slate-100 text-slate-700',
  };
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h3 className="mb-2 text-sm font-semibold text-slate-500">{title}</h3>
          <span className="text-3xl font-black text-slate-800">{value}</span>
          {subtitle ? <p className="mt-2 text-xs font-medium text-slate-500">{subtitle}</p> : null}
        </div>
        <div className={`flex h-12 w-12 items-center justify-center rounded-xl ${tones[tone] || tones.indigo}`}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </div>
  );
};

const ConceptAnalyticsPage = () => {
  const { token } = useAuth();
  const apiUrl = API_URL;

  const [classes, setClasses] = useState([]);
  const [activeClassId, setActiveClassId] = useState('');
  const [dashboard, setDashboard] = useState(null);
  const [heatmap, setHeatmap] = useState([]);
  const [graphSummary, setGraphSummary] = useState(null);
  const [graphPlaybook, setGraphPlaybook] = useState([]);
  const [interventionQueue, setInterventionQueue] = useState(null);
  const [nextClusterPlan, setNextClusterPlan] = useState(null);
  const [selectedConceptId, setSelectedConceptId] = useState('');
  const [compareConceptId, setCompareConceptId] = useState('');
  const [conceptStudents, setConceptStudents] = useState(null);
  const [conceptCompare, setConceptCompare] = useState(null);
  const [primaryCompareStudentId, setPrimaryCompareStudentId] = useState('');
  const [secondaryCompareStudentId, setSecondaryCompareStudentId] = useState('');
  const [primaryCompareTrend, setPrimaryCompareTrend] = useState(null);
  const [secondaryCompareTrend, setSecondaryCompareTrend] = useState(null);
  const [interventionOutcomes, setInterventionOutcomes] = useState(null);
  const [assignmentOutcomes, setAssignmentOutcomes] = useState(null);
  const [repeatRisk, setRepeatRisk] = useState(null);
  const [riskMatrix, setRiskMatrix] = useState(null);
  const [selectedStudent, setSelectedStudent] = useState(null);
  const [studentTimeline, setStudentTimeline] = useState([]);
  const [studentConceptTrend, setStudentConceptTrend] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [exportState, setExportState] = useState({ isOpen: false, isLoading: false, error: '', data: null, target: '' });
  const [assignmentStatus, setAssignmentStatus] = useState({});
  const [interventionStatus, setInterventionStatus] = useState({});
  const [interventionUpdateStatus, setInterventionUpdateStatus] = useState({});
  const [bulkInterventionStatus, setBulkInterventionStatus] = useState(null);
  const [bulkAssignmentStatus, setBulkAssignmentStatus] = useState(null);
  const [queueActionStatus, setQueueActionStatus] = useState({});
  const [queueAssignmentStatus, setQueueAssignmentStatus] = useState({});
  const [isLoadingClasses, setIsLoadingClasses] = useState(true);
  const [isLoadingDetails, setIsLoadingDetails] = useState(false);
  const [isLoadingConceptStudents, setIsLoadingConceptStudents] = useState(false);
  const [isLoadingConceptCompare, setIsLoadingConceptCompare] = useState(false);
  const [isLoadingStudentCompare, setIsLoadingStudentCompare] = useState(false);
  const [isLoadingStudentTimeline, setIsLoadingStudentTimeline] = useState(false);
  const [isLoadingStudentConceptTrend, setIsLoadingStudentConceptTrend] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchClasses = async () => {
      if (!token) {
        setIsLoadingClasses(false);
        setError('Teacher analytics requires an authenticated teacher account.');
        return;
      }

      try {
        setError('');
        const response = await fetch(`${apiUrl}/teachers/classes`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!response.ok) {
          const detail = await response.json().catch(() => null);
          throw new Error(detail?.detail || 'Failed to load teacher classes.');
        }
        const data = await response.json();
        const classList = Array.isArray(data?.classes) ? data.classes : [];
        setClasses(classList);
        if (classList.length > 0) {
          setActiveClassId((current) => current || classList[0].id);
        }
      } catch (err) {
        setClasses([]);
        setError(err.message || 'Teacher analytics is unavailable right now.');
      } finally {
        setIsLoadingClasses(false);
      }
    };

    fetchClasses();
  }, [apiUrl, token]);

  useEffect(() => {
    const fetchAnalytics = async () => {
      if (!token || !activeClassId) {
        setDashboard(null);
        setHeatmap([]);
        setGraphSummary(null);
        setGraphPlaybook([]);
        setInterventionQueue(null);
        setNextClusterPlan(null);
        setSelectedConceptId('');
        setConceptStudents(null);
        setInterventionOutcomes(null);
        setAssignmentOutcomes(null);
        setRepeatRisk(null);
        setRiskMatrix(null);
        setSelectedStudent(null);
        setStudentTimeline([]);
        setStudentConceptTrend(null);
        setAlerts([]);
        return;
      }

      try {
        setIsLoadingDetails(true);
        setError('');
        const [dashboardRes, heatmapRes, graphRes, playbookRes, interventionQueueRes, nextClusterRes, alertsRes, outcomesRes, assignmentOutcomesRes, repeatRiskRes, riskMatrixRes] = await Promise.all([
          fetch(`${apiUrl}/teachers/classes/${activeClassId}/dashboard`, { headers: { Authorization: `Bearer ${token}` } }),
          fetch(`${apiUrl}/teachers/classes/${activeClassId}/heatmap`, { headers: { Authorization: `Bearer ${token}` } }),
          fetch(`${apiUrl}/teachers/classes/${activeClassId}/graph-summary`, { headers: { Authorization: `Bearer ${token}` } }),
          fetch(`${apiUrl}/teachers/classes/${activeClassId}/graph-playbook`, { headers: { Authorization: `Bearer ${token}` } }),
          fetch(`${apiUrl}/teachers/classes/${activeClassId}/intervention-queue`, { headers: { Authorization: `Bearer ${token}` } }),
          fetch(`${apiUrl}/teachers/classes/${activeClassId}/next-cluster-plan`, { headers: { Authorization: `Bearer ${token}` } }),
          fetch(`${apiUrl}/teachers/classes/${activeClassId}/alerts`, { headers: { Authorization: `Bearer ${token}` } }),
          fetch(`${apiUrl}/teachers/classes/${activeClassId}/intervention-outcomes`, { headers: { Authorization: `Bearer ${token}` } }),
          fetch(`${apiUrl}/teachers/classes/${activeClassId}/assignment-outcomes`, { headers: { Authorization: `Bearer ${token}` } }),
          fetch(`${apiUrl}/teachers/classes/${activeClassId}/repeat-risk`, { headers: { Authorization: `Bearer ${token}` } }),
          fetch(`${apiUrl}/teachers/classes/${activeClassId}/risk-matrix`, { headers: { Authorization: `Bearer ${token}` } }),
        ]);

        if (!dashboardRes.ok || !heatmapRes.ok || !graphRes.ok || !playbookRes.ok || !interventionQueueRes.ok || !nextClusterRes.ok || !alertsRes.ok || !outcomesRes.ok || !assignmentOutcomesRes.ok || !repeatRiskRes.ok || !riskMatrixRes.ok) {
          const firstFailure = [dashboardRes, heatmapRes, graphRes, playbookRes, interventionQueueRes, nextClusterRes, alertsRes, outcomesRes, assignmentOutcomesRes, repeatRiskRes, riskMatrixRes].find((response) => !response.ok);
          const detail = await firstFailure.json().catch(() => null);
          throw new Error(detail?.detail || 'Failed to load teacher analytics.');
        }

        const [dashboardData, heatmapData, graphData, playbookData, interventionQueueData, nextClusterData, alertsData, outcomesData, assignmentOutcomesData, repeatRiskData, riskMatrixData] = await Promise.all([
          dashboardRes.json(),
          heatmapRes.json(),
          graphRes.json(),
          playbookRes.json(),
          interventionQueueRes.json(),
          nextClusterRes.json(),
          alertsRes.json(),
          outcomesRes.json(),
          assignmentOutcomesRes.json(),
          repeatRiskRes.json(),
          riskMatrixRes.json(),
        ]);

        setDashboard(dashboardData);
        setHeatmap(Array.isArray(heatmapData?.points) ? heatmapData.points : []);
        setGraphSummary(graphData || null);
        setGraphPlaybook(Array.isArray(playbookData?.actions) ? playbookData.actions : []);
        setInterventionQueue(interventionQueueData || null);
        setNextClusterPlan(nextClusterData || null);
        setSelectedConceptId(
          graphData?.weakest_blockers?.[0]?.concept_id ||
            graphData?.nodes?.[0]?.concept_id ||
            ''
        );
        setCompareConceptId('');
        setPrimaryCompareStudentId('');
        setSecondaryCompareStudentId('');
        setConceptStudents(null);
        setConceptCompare(null);
        setPrimaryCompareTrend(null);
        setSecondaryCompareTrend(null);
        setInterventionOutcomes(outcomesData || null);
        setAssignmentOutcomes(assignmentOutcomesData || null);
        setRepeatRisk(repeatRiskData || null);
        setRiskMatrix(riskMatrixData || null);
        setSelectedStudent(null);
        setStudentTimeline([]);
        setStudentConceptTrend(null);
        setAlerts(Array.isArray(alertsData?.alerts) ? alertsData.alerts : []);
      } catch (err) {
        setDashboard(null);
        setHeatmap([]);
        setGraphSummary(null);
        setGraphPlaybook([]);
        setInterventionQueue(null);
        setNextClusterPlan(null);
        setSelectedConceptId('');
        setCompareConceptId('');
        setPrimaryCompareStudentId('');
        setSecondaryCompareStudentId('');
        setConceptStudents(null);
        setConceptCompare(null);
        setPrimaryCompareTrend(null);
        setSecondaryCompareTrend(null);
        setInterventionOutcomes(null);
        setAssignmentOutcomes(null);
        setRepeatRisk(null);
        setRiskMatrix(null);
        setSelectedStudent(null);
        setStudentTimeline([]);
        setStudentConceptTrend(null);
        setAlerts([]);
        setError(err.message || 'Teacher analytics is unavailable right now.');
      } finally {
        setIsLoadingDetails(false);
      }
    };

    fetchAnalytics();
  }, [activeClassId, apiUrl, token]);

  useEffect(() => {
    const nodes = Array.isArray(graphSummary?.nodes) ? graphSummary.nodes : [];
    if (!nodes.length || !selectedConceptId) {
      setCompareConceptId('');
      return;
    }
    if (compareConceptId && compareConceptId !== selectedConceptId && nodes.some((node) => node.concept_id === compareConceptId)) {
      return;
    }
    setCompareConceptId(nodes.find((node) => node.concept_id !== selectedConceptId)?.concept_id || '');
  }, [compareConceptId, graphSummary?.nodes, selectedConceptId]);

  useEffect(() => {
    const fetchConceptStudents = async () => {
      if (!token || !activeClassId || !selectedConceptId) {
        setConceptStudents(null);
        setBulkAssignmentStatus(null);
        setBulkInterventionStatus(null);
        setSelectedStudent(null);
        setStudentTimeline([]);
        setStudentConceptTrend(null);
        return;
      }

      try {
        setIsLoadingConceptStudents(true);
        const response = await fetch(
          `${apiUrl}/teachers/classes/${activeClassId}/concepts/${encodeURIComponent(selectedConceptId)}/students`,
          { headers: { Authorization: `Bearer ${token}` } },
        );
        if (!response.ok) {
          const detail = await response.json().catch(() => null);
          throw new Error(detail?.detail || 'Failed to load concept student drilldown.');
        }
        const data = await response.json();
        setConceptStudents(data || null);
        setBulkAssignmentStatus(null);
        setBulkInterventionStatus(null);
        setSelectedStudent(null);
        setStudentTimeline([]);
        setStudentConceptTrend(null);
        const studentIds = Array.isArray(data?.students) ? data.students.map((student) => student.student_id) : [];
        setPrimaryCompareStudentId(studentIds[0] || '');
        setSecondaryCompareStudentId(studentIds.find((studentId) => studentId !== studentIds[0]) || '');
        setPrimaryCompareTrend(null);
        setSecondaryCompareTrend(null);
      } catch (err) {
        setConceptStudents(null);
        setBulkAssignmentStatus(null);
        setBulkInterventionStatus(null);
        setSelectedStudent(null);
        setStudentTimeline([]);
        setStudentConceptTrend(null);
        setPrimaryCompareStudentId('');
        setSecondaryCompareStudentId('');
        setPrimaryCompareTrend(null);
        setSecondaryCompareTrend(null);
        setError(err.message || 'Failed to load concept student drilldown.');
      } finally {
        setIsLoadingConceptStudents(false);
      }
    };

    fetchConceptStudents();
  }, [activeClassId, apiUrl, selectedConceptId, token]);

  useEffect(() => {
    const fetchConceptCompare = async () => {
      if (!token || !activeClassId || !selectedConceptId || !compareConceptId || selectedConceptId === compareConceptId) {
        setConceptCompare(null);
        return;
      }

      try {
        setIsLoadingConceptCompare(true);
        const response = await fetch(
          `${apiUrl}/teachers/classes/${activeClassId}/concept-compare?left_concept_id=${encodeURIComponent(selectedConceptId)}&right_concept_id=${encodeURIComponent(compareConceptId)}`,
          { headers: { Authorization: `Bearer ${token}` } },
        );
        if (!response.ok) {
          const detail = await response.json().catch(() => null);
          throw new Error(detail?.detail || 'Failed to load concept comparison.');
        }
        const data = await response.json();
        setConceptCompare(data || null);
      } catch (err) {
        setConceptCompare(null);
        setError(err.message || 'Failed to load concept comparison.');
      } finally {
        setIsLoadingConceptCompare(false);
      }
    };

    fetchConceptCompare();
  }, [activeClassId, apiUrl, compareConceptId, selectedConceptId, token]);

  useEffect(() => {
    const fetchStudentCompare = async () => {
      if (!token || !activeClassId || !selectedConceptId || !primaryCompareStudentId || !secondaryCompareStudentId || primaryCompareStudentId === secondaryCompareStudentId) {
        setPrimaryCompareTrend(null);
        setSecondaryCompareTrend(null);
        return;
      }

      try {
        setIsLoadingStudentCompare(true);
        const [primaryResponse, secondaryResponse] = await Promise.all([
          fetch(
            `${apiUrl}/teachers/classes/${activeClassId}/students/${primaryCompareStudentId}/concepts/${encodeURIComponent(selectedConceptId)}/trend?days=30`,
            { headers: { Authorization: `Bearer ${token}` } },
          ),
          fetch(
            `${apiUrl}/teachers/classes/${activeClassId}/students/${secondaryCompareStudentId}/concepts/${encodeURIComponent(selectedConceptId)}/trend?days=30`,
            { headers: { Authorization: `Bearer ${token}` } },
          ),
        ]);
        if (!primaryResponse.ok || !secondaryResponse.ok) {
          const firstFailure = [primaryResponse, secondaryResponse].find((response) => !response.ok);
          const detail = await firstFailure.json().catch(() => null);
          throw new Error(detail?.detail || 'Failed to load student comparison trends.');
        }
        const [primaryData, secondaryData] = await Promise.all([primaryResponse.json(), secondaryResponse.json()]);
        setPrimaryCompareTrend(primaryData || null);
        setSecondaryCompareTrend(secondaryData || null);
      } catch (err) {
        setPrimaryCompareTrend(null);
        setSecondaryCompareTrend(null);
        setError(err.message || 'Failed to load student comparison trends.');
      } finally {
        setIsLoadingStudentCompare(false);
      }
    };

    fetchStudentCompare();
  }, [activeClassId, apiUrl, primaryCompareStudentId, secondaryCompareStudentId, selectedConceptId, token]);

  useEffect(() => {
    const fetchStudentTimeline = async () => {
      if (!token || !activeClassId || !selectedStudent?.student_id) {
        setStudentTimeline([]);
        return;
      }
      try {
        setIsLoadingStudentTimeline(true);
        const response = await fetch(
          `${apiUrl}/teachers/classes/${activeClassId}/students/${selectedStudent.student_id}/timeline?limit=20`,
          { headers: { Authorization: `Bearer ${token}` } },
        );
        if (!response.ok) {
          const detail = await response.json().catch(() => null);
          throw new Error(detail?.detail || 'Failed to load student timeline.');
        }
        const data = await response.json();
        setStudentTimeline(Array.isArray(data?.timeline) ? data.timeline : []);
      } catch (err) {
        setStudentTimeline([]);
        setError(err.message || 'Failed to load student timeline.');
      } finally {
        setIsLoadingStudentTimeline(false);
      }
    };

    fetchStudentTimeline();
  }, [activeClassId, apiUrl, selectedStudent?.student_id, token]);

  useEffect(() => {
    const fetchStudentConceptTrend = async () => {
      if (!token || !activeClassId || !selectedStudent?.student_id || !selectedConceptId) {
        setStudentConceptTrend(null);
        return;
      }
      try {
        setIsLoadingStudentConceptTrend(true);
        const response = await fetch(
          `${apiUrl}/teachers/classes/${activeClassId}/students/${selectedStudent.student_id}/concepts/${encodeURIComponent(selectedConceptId)}/trend?days=30`,
          { headers: { Authorization: `Bearer ${token}` } },
        );
        if (!response.ok) {
          const detail = await response.json().catch(() => null);
          throw new Error(detail?.detail || 'Failed to load concept trend.');
        }
        const data = await response.json();
        setStudentConceptTrend(data || null);
      } catch (err) {
        setStudentConceptTrend(null);
        setError(err.message || 'Failed to load concept trend.');
      } finally {
        setIsLoadingStudentConceptTrend(false);
      }
    };

    fetchStudentConceptTrend();
  }, [activeClassId, apiUrl, selectedConceptId, selectedStudent?.student_id, token]);

  useEffect(() => {
    const fetchConceptScopedOutcomes = async () => {
      if (!token || !activeClassId) {
        setInterventionOutcomes(null);
        setAssignmentOutcomes(null);
        return;
      }
      try {
        const query = selectedConceptId ? `?concept_id=${encodeURIComponent(selectedConceptId)}` : '';
        const [interventionsRes, assignmentsRes] = await Promise.all([
          fetch(`${apiUrl}/teachers/classes/${activeClassId}/intervention-outcomes${query}`, {
            headers: { Authorization: `Bearer ${token}` },
          }),
          fetch(`${apiUrl}/teachers/classes/${activeClassId}/assignment-outcomes${query}`, {
            headers: { Authorization: `Bearer ${token}` },
          }),
        ]);
        if (!interventionsRes.ok || !assignmentsRes.ok) {
          const firstFailure = [interventionsRes, assignmentsRes].find((response) => !response.ok);
          const detail = await firstFailure.json().catch(() => null);
          throw new Error(detail?.detail || 'Failed to load concept-scoped outcomes.');
        }
        const [interventionsData, assignmentsData] = await Promise.all([
          interventionsRes.json(),
          assignmentsRes.json(),
        ]);
        setInterventionOutcomes(interventionsData || null);
        setAssignmentOutcomes(assignmentsData || null);
      } catch (err) {
        setError(err.message || 'Failed to load concept-scoped outcomes.');
      }
    };

    fetchConceptScopedOutcomes();
  }, [activeClassId, apiUrl, selectedConceptId, token]);

  const activeClass = useMemo(
    () => classes.find((item) => item.id === activeClassId) || null,
    [activeClassId, classes],
  );
  const weakestConcepts = useMemo(
    () => [...heatmap].sort((a, b) => Number(a.avg_score || 0) - Number(b.avg_score || 0)).slice(0, 8),
    [heatmap],
  );
  const compareOptions = useMemo(() => {
    const nodes = Array.isArray(graphSummary?.nodes) ? graphSummary.nodes : [];
    return nodes.map((node) => ({
      value: node.concept_id,
      label: node.concept_label || humanizeConceptId(node.concept_id),
      status: node.status,
    }));
  }, [graphSummary?.nodes]);
  const studentCompareOptions = useMemo(() => {
    const students = Array.isArray(conceptStudents?.students) ? conceptStudents.students : [];
    return students.map((student) => ({
      value: student.student_id,
      label: student.student_name,
      status: student.status,
    }));
  }, [conceptStudents?.students]);

  const graphMetrics = graphSummary?.metrics || null;
  const graphSignal = graphSummary?.graph_signal || null;
  const graphBlockers = Array.isArray(graphSummary?.weakest_blockers) ? graphSummary.weakest_blockers : [];
  const readyToPush = Array.isArray(graphSummary?.ready_to_push) ? graphSummary.ready_to_push : [];
  const nextClusterRepairFirst = Array.isArray(nextClusterPlan?.repair_first) ? nextClusterPlan.repair_first : [];
  const nextClusterTeachNext = Array.isArray(nextClusterPlan?.teach_next) ? nextClusterPlan.teach_next : [];
  const nextClusterWatchlist = Array.isArray(nextClusterPlan?.watchlist) ? nextClusterPlan.watchlist : [];
  const nextClusterActions = Array.isArray(nextClusterPlan?.suggested_actions) ? nextClusterPlan.suggested_actions : [];
  const filteredAssignmentOutcomeRows = useMemo(() => {
    const rows = Array.isArray(assignmentOutcomes?.outcomes) ? assignmentOutcomes.outcomes : [];
    if (!selectedStudent?.student_id) return rows;
    return rows.filter((item) => item.student_id === selectedStudent.student_id);
  }, [assignmentOutcomes?.outcomes, selectedStudent?.student_id]);
  const filteredInterventionOutcomeRows = useMemo(() => {
    const rows = Array.isArray(interventionOutcomes?.outcomes) ? interventionOutcomes.outcomes : [];
    if (!selectedStudent?.student_id) return rows;
    return rows.filter((item) => item.student_id === selectedStudent.student_id);
  }, [interventionOutcomes?.outcomes, selectedStudent?.student_id]);
  const filteredAssignmentOutcomeSummary = useMemo(() => ({
    improving: filteredAssignmentOutcomeRows.filter((item) => item.outcome_status === 'improving').length,
    noEvidence: filteredAssignmentOutcomeRows.filter((item) => item.outcome_status === 'no_evidence').length,
    declining: filteredAssignmentOutcomeRows.filter((item) => item.outcome_status === 'declining').length,
    avgDelta: filteredAssignmentOutcomeRows.length
      ? Number(filteredAssignmentOutcomeRows.reduce((sum, item) => sum + Number(item.net_mastery_delta || 0), 0) / filteredAssignmentOutcomeRows.length).toFixed(2)
      : Number(0).toFixed(2),
  }), [filteredAssignmentOutcomeRows]);
  const filteredInterventionOutcomeSummary = useMemo(() => ({
    improving: filteredInterventionOutcomeRows.filter((item) => item.outcome_status === 'improving').length,
    noEvidence: filteredInterventionOutcomeRows.filter((item) => item.outcome_status === 'no_evidence').length,
    declining: filteredInterventionOutcomeRows.filter((item) => item.outcome_status === 'declining').length,
    avgDelta: filteredInterventionOutcomeRows.length
      ? Number(filteredInterventionOutcomeRows.reduce((sum, item) => sum + Number(item.net_mastery_delta || 0), 0) / filteredInterventionOutcomeRows.length).toFixed(2)
      : Number(0).toFixed(2),
  }), [filteredInterventionOutcomeRows]);
  const studentCompareNarrative = useMemo(() => {
    if (!primaryCompareTrend || !secondaryCompareTrend) return null;
    const primaryLabel = studentCompareOptions.find((item) => item.value === primaryCompareStudentId)?.label || 'Primary student';
    const secondaryLabel = studentCompareOptions.find((item) => item.value === secondaryCompareStudentId)?.label || 'Secondary student';
    const primaryScore = Number(primaryCompareTrend.current_score ?? -1);
    const secondaryScore = Number(secondaryCompareTrend.current_score ?? -1);
    const primaryBlocked = primaryCompareTrend.status === 'blocked';
    const secondaryBlocked = secondaryCompareTrend.status === 'blocked';

    if (primaryBlocked && secondaryBlocked) {
      return {
        headline: 'Both students are blocked on this concept.',
        rationale: 'Use the prerequisite lists to split support instead of assigning them the same repair path blindly.',
      };
    }
    if (primaryBlocked || primaryScore < secondaryScore) {
      return {
        headline: `${primaryLabel} needs deeper repair first.`,
        rationale: 'Their concept path is weaker on the current node, so they should get the prerequisite-first intervention.',
      };
    }
    if (secondaryBlocked || secondaryScore < primaryScore) {
      return {
        headline: `${secondaryLabel} needs deeper repair first.`,
        rationale: 'Their concept path is weaker on the current node, so they should get the prerequisite-first intervention.',
      };
    }
    return {
      headline: 'Both students are tracking similarly on this concept.',
      rationale: 'You can use the delta and blocker details to decide whether to group them or differentiate the next task.',
    };
  }, [
    primaryCompareStudentId,
    primaryCompareTrend,
    secondaryCompareStudentId,
    secondaryCompareTrend,
    studentCompareOptions,
  ]);

  const createSuggestedAssignment = async (action) => {
    if (!activeClassId || !activeClass || !token) return;
    const key = `${action.action_type}-${action.target_concept_id || action.target_topic_id || action.target_concept_label || action.title}`;
    try {
      setAssignmentStatus((current) => ({ ...current, [key]: { state: 'loading', message: 'Creating assignment...' } }));
      const response = await fetch(`${apiUrl}/teachers/assignments`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          class_id: activeClassId,
          student_id: null,
          assignment_type: action.suggested_assignment_type || 'revision',
          concept_id: action.target_concept_id || null,
          concept_label: action.target_concept_label || null,
          ref_id: actionRefId(action),
          title: action.title,
          instructions: action.summary,
          subject: activeClass.subject,
          sss_level: activeClass.sss_level,
          term: activeClass.term,
          due_at: null,
        }),
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.detail || 'Failed to create assignment.');
      }
      setAssignmentStatus((current) => ({ ...current, [key]: { state: 'success', message: 'Assignment created for this class.' } }));
    } catch (err) {
      setAssignmentStatus((current) => ({ ...current, [key]: { state: 'error', message: err.message || 'Failed to create assignment.' } }));
    }
  };

  const openClusterPlanExport = async () => {
    if (!activeClassId || !token) return;
    setExportState({ isOpen: true, isLoading: true, error: '', data: null, target: 'plan' });
    try {
      const response = await fetch(`${apiUrl}/teachers/classes/${activeClassId}/next-cluster-plan/export`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.detail || 'Failed to prepare cluster plan export.');
      }
      const data = await response.json();
      setExportState({ isOpen: true, isLoading: false, error: '', data, target: 'plan' });
    } catch (err) {
      setExportState({ isOpen: true, isLoading: false, error: err.message || 'Failed to prepare cluster plan export.', data: null, target: 'plan' });
    }
  };

  const openClassBriefingExport = async () => {
    if (!activeClassId || !token) return;
    setExportState({ isOpen: true, isLoading: true, error: '', data: null, target: 'briefing' });
    try {
      const response = await fetch(`${apiUrl}/teachers/classes/${activeClassId}/briefing/export`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.detail || 'Failed to prepare class briefing export.');
      }
      const data = await response.json();
      setExportState({ isOpen: true, isLoading: false, error: '', data, target: 'briefing' });
    } catch (err) {
      setExportState({ isOpen: true, isLoading: false, error: err.message || 'Failed to prepare class briefing export.', data: null, target: 'briefing' });
    }
  };

  const openClassBriefingPage = () => {
    if (!activeClassId) return;
    window.open(`/teacher/briefing/${activeClassId}`, '_blank', 'noopener,noreferrer');
  };

  const openTeacherPresentationPage = () => {
    if (!activeClassId) return;
    window.open(`/teacher/presentation/${activeClassId}`, '_blank', 'noopener,noreferrer');
  };

  const openStudentFocusExport = async () => {
    if (!activeClassId || !token || !selectedStudent?.student_id || !selectedConceptId) return;
    setExportState({ isOpen: true, isLoading: true, error: '', data: null, target: 'student' });
    try {
      const response = await fetch(
        `${apiUrl}/teachers/classes/${activeClassId}/students/${selectedStudent.student_id}/concepts/${encodeURIComponent(selectedConceptId)}/export`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.detail || 'Failed to prepare student focus export.');
      }
      const data = await response.json();
      setExportState({ isOpen: true, isLoading: false, error: '', data, target: 'student' });
    } catch (err) {
      setExportState({ isOpen: true, isLoading: false, error: err.message || 'Failed to prepare student focus export.', data: null, target: 'student' });
    }
  };

  const openStudentReportPage = () => {
    if (!activeClassId || !selectedStudent?.student_id || !selectedConceptId) return;
    window.open(
      `/teacher/students/${activeClassId}/${selectedStudent.student_id}/concepts/${encodeURIComponent(selectedConceptId)}/report`,
      '_blank',
      'noopener,noreferrer',
    );
  };

  const openConceptCompareExport = async () => {
    if (!activeClassId || !token || !selectedConceptId || !compareConceptId || selectedConceptId === compareConceptId) return;
    setExportState({ isOpen: true, isLoading: true, error: '', data: null, target: 'compare' });
    try {
      const response = await fetch(
        `${apiUrl}/teachers/classes/${activeClassId}/concept-compare/export?left_concept_id=${encodeURIComponent(selectedConceptId)}&right_concept_id=${encodeURIComponent(compareConceptId)}`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.detail || 'Failed to prepare concept comparison export.');
      }
      const data = await response.json();
      setExportState({ isOpen: true, isLoading: false, error: '', data, target: 'compare' });
    } catch (err) {
      setExportState({ isOpen: true, isLoading: false, error: err.message || 'Failed to prepare concept comparison export.', data: null, target: 'compare' });
    }
  };

  const createStudentIntervention = async (student) => {
    if (!activeClassId || !activeClass || !token || !conceptStudents) return;
    const key = `${student.student_id}-${conceptStudents.concept_id}`;
    try {
      setInterventionStatus((current) => ({ ...current, [key]: { state: 'loading', message: 'Creating intervention...' } }));
      const response = await fetch(`${apiUrl}/teachers/interventions`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          class_id: activeClassId,
          student_id: student.student_id,
          intervention_type: 'support_plan',
          concept_id: conceptStudents.concept_id,
          concept_label: conceptStudents.concept_label,
          severity: student.status === 'blocked' ? 'high' : 'medium',
          subject: activeClass.subject,
          sss_level: activeClass.sss_level,
          term: activeClass.term,
          notes: `Target ${student.student_name} on ${conceptStudents.concept_label}. ${student.recommended_action}`,
          action_plan: student.blocking_prerequisite_labels?.length
            ? `Repair prerequisite(s): ${student.blocking_prerequisite_labels.join(', ')} before reteaching ${conceptStudents.concept_label}.`
            : `Run a focused checkpoint and follow-up practice on ${conceptStudents.concept_label}.`,
        }),
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.detail || 'Failed to create intervention.');
      }
      setInterventionStatus((current) => ({ ...current, [key]: { state: 'success', message: 'Intervention created.' } }));
    } catch (err) {
      setInterventionStatus((current) => ({ ...current, [key]: { state: 'error', message: err.message || 'Failed to create intervention.' } }));
    }
  };

  const createRepeatRiskIntervention = async (student) => {
    const focusConcept = student?.driving_concepts?.[0];
    if (!activeClassId || !activeClass || !token || !focusConcept) return;
    const key = `${student.student_id}-${focusConcept.concept_id}`;
    try {
      setInterventionStatus((current) => ({ ...current, [key]: { state: 'loading', message: 'Creating intervention...' } }));
      const response = await fetch(`${apiUrl}/teachers/interventions`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          class_id: activeClassId,
          student_id: student.student_id,
          intervention_type: 'support_plan',
          concept_id: focusConcept.concept_id,
          concept_label: focusConcept.concept_label,
          severity: student.risk_status === 'repeat_blocker' ? 'high' : 'medium',
          subject: activeClass.subject,
          sss_level: activeClass.sss_level,
          term: activeClass.term,
          notes: `Target ${student.student_name} on repeated graph risk around ${focusConcept.concept_label}. ${student.recommended_action}`,
          action_plan: focusConcept.blocking_prerequisite_labels?.length
            ? `Repair prerequisite(s): ${focusConcept.blocking_prerequisite_labels.join(', ')} before reteaching ${focusConcept.concept_label}.`
            : `Run a focused checkpoint and short practice set on ${focusConcept.concept_label}.`,
        }),
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.detail || 'Failed to create intervention.');
      }
      setInterventionStatus((current) => ({ ...current, [key]: { state: 'success', message: 'Intervention created.' } }));
    } catch (err) {
      setInterventionStatus((current) => ({ ...current, [key]: { state: 'error', message: err.message || 'Failed to create intervention.' } }));
    }
  };

  const createQueueIntervention = async (item) => {
    if (!activeClassId || !activeClass || !token || !item?.student_id) return;
    const key = item.queue_id;
    try {
      setQueueActionStatus((current) => ({ ...current, [key]: { state: 'loading', message: 'Creating intervention...' } }));
      const response = await fetch(`${apiUrl}/teachers/interventions`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          class_id: activeClassId,
          student_id: item.student_id,
          intervention_type: item.suggested_intervention_type || 'support_plan',
          concept_id: item.concept_id,
          concept_label: item.concept_label,
          severity: item.priority === 'urgent' ? 'high' : 'medium',
          subject: activeClass.subject,
          sss_level: activeClass.sss_level,
          term: activeClass.term,
          notes: item.headline,
          action_plan: item.rationale,
        }),
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.detail || 'Failed to create intervention.');
      }
      setQueueActionStatus((current) => ({ ...current, [key]: { state: 'success', message: 'Intervention created.' } }));
    } catch (err) {
      setQueueActionStatus((current) => ({ ...current, [key]: { state: 'error', message: err.message || 'Failed to create intervention.' } }));
    }
  };

  const createQueueAssignment = async (item) => {
    if (!activeClassId || !activeClass || !token || !item?.suggested_assignment_type) return;
    const key = item.queue_id;
    try {
      setQueueAssignmentStatus((current) => ({ ...current, [key]: { state: 'loading', message: 'Creating assignment...' } }));
      const response = await fetch(`${apiUrl}/teachers/assignments`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          class_id: activeClassId,
          student_id: item.student_id || null,
          assignment_type: item.suggested_assignment_type,
          concept_id: item.concept_id || null,
          concept_label: item.concept_label || null,
          ref_id: item.queue_id,
          title: item.headline,
          instructions: item.rationale,
          subject: activeClass.subject,
          sss_level: activeClass.sss_level,
          term: activeClass.term,
          due_at: null,
        }),
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.detail || 'Failed to create assignment.');
      }
      setQueueAssignmentStatus((current) => ({ ...current, [key]: { state: 'success', message: 'Assignment created.' } }));
    } catch (err) {
      setQueueAssignmentStatus((current) => ({ ...current, [key]: { state: 'error', message: err.message || 'Failed to create assignment.' } }));
    }
  };

  const openStudentFocus = (student, focusConcept = null, cell = null) => {
    const resolvedConcept = focusConcept || student?.driving_concepts?.[0] || null;
    if (resolvedConcept?.concept_id) {
      setSelectedConceptId(resolvedConcept.concept_id);
    }
    setStudentConceptTrend(null);
    setSelectedStudent({
      ...student,
      status: cell?.status || resolvedConcept?.status || student?.status || 'needs_attention',
      concept_score:
        cell?.concept_score ??
        resolvedConcept?.concept_score ??
        student?.concept_score ??
        null,
      blocking_prerequisite_labels:
        cell?.blocking_prerequisite_labels ||
        resolvedConcept?.blocking_prerequisite_labels ||
        student?.blocking_prerequisite_labels ||
        [],
      recommended_action:
        student?.recommended_action ||
        (cell?.status === 'blocked'
          ? `Repair the blocking prerequisite before reteaching ${resolvedConcept?.concept_label || 'this concept'}.`
          : `Run a focused checkpoint on ${resolvedConcept?.concept_label || 'this concept'}.`),
      recent_activity_count_7d: student?.recent_activity_count_7d ?? 0,
      recent_study_time_seconds_7d: student?.recent_study_time_seconds_7d ?? 0,
      last_evaluated_at: student?.last_evaluated_at || null,
    });
  };

  const createBulkConceptInterventions = async () => {
    if (!activeClassId || !activeClass || !token || !conceptStudents?.students?.length) return;
    const targetStudents = conceptStudents.students.filter((student) =>
      ['blocked', 'needs_attention'].includes(student.status),
    );
    if (targetStudents.length === 0) {
      setBulkInterventionStatus({ state: 'error', message: 'No blocked or weak students are available for a bulk intervention.' });
      return;
    }

    try {
      setBulkInterventionStatus({ state: 'loading', message: 'Creating bulk intervention...' });
      const response = await fetch(`${apiUrl}/teachers/interventions/bulk`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          class_id: activeClassId,
          student_ids: targetStudents.map((student) => student.student_id),
          intervention_type: 'support_plan',
          concept_id: conceptStudents.concept_id,
          concept_label: conceptStudents.concept_label,
          severity: targetStudents.some((student) => student.status === 'blocked') ? 'high' : 'medium',
          subject: activeClass.subject,
          sss_level: activeClass.sss_level,
          term: activeClass.term,
          notes: `Target ${conceptStudents.concept_label} for ${targetStudents.length} at-risk students. Repair blockers before reteaching the concept.`,
          action_plan: conceptStudents.students.some((student) => student.blocking_prerequisite_labels?.length)
            ? `Repair prerequisite blockers before reteaching ${conceptStudents.concept_label}.`
            : `Run a focused checkpoint and short support cycle on ${conceptStudents.concept_label}.`,
        }),
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.detail || 'Failed to create bulk interventions.');
      }
      const data = await response.json();
      setBulkInterventionStatus({
        state: 'success',
        message: `Created ${data.created_count} interventions for ${conceptStudents.concept_label}.`,
      });
    } catch (err) {
      setBulkInterventionStatus({ state: 'error', message: err.message || 'Failed to create bulk interventions.' });
    }
  };

  const createBulkConceptAssignments = async () => {
    if (!activeClassId || !activeClass || !token || !conceptStudents?.students?.length) return;
    const targetStudents = conceptStudents.students.filter((student) =>
      ['blocked', 'needs_attention'].includes(student.status),
    );
    if (targetStudents.length === 0) {
      setBulkAssignmentStatus({ state: 'error', message: 'No blocked or weak students are available for a bulk assignment.' });
      return;
    }

    try {
      setBulkAssignmentStatus({ state: 'loading', message: 'Creating bulk assignment...' });
      const response = await fetch(`${apiUrl}/teachers/assignments/bulk`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          class_id: activeClassId,
          student_ids: targetStudents.map((student) => student.student_id),
          assignment_type: 'revision',
          concept_id: conceptStudents.concept_id,
          concept_label: conceptStudents.concept_label,
          ref_id: `${conceptStudents.concept_id}-repair-pack`,
          title: `${conceptStudents.concept_label} Repair Pack`,
          instructions: `Repair the blocker and revisit ${conceptStudents.concept_label}. Complete the follow-up questions after revision.`,
          subject: activeClass.subject,
          sss_level: activeClass.sss_level,
          term: activeClass.term,
          due_at: null,
        }),
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.detail || 'Failed to create bulk assignments.');
      }
      const data = await response.json();
      setBulkAssignmentStatus({
        state: 'success',
        message: `Created ${data.created_count} revision assignments for ${conceptStudents.concept_label}.`,
      });
    } catch (err) {
      setBulkAssignmentStatus({ state: 'error', message: err.message || 'Failed to create bulk assignments.' });
    }
  };

  const updateInterventionStatus = async (outcome, status) => {
    if (!token) return;
    const key = `${outcome.intervention_id}-${status}`;
    try {
      setInterventionUpdateStatus((current) => ({ ...current, [key]: { state: 'loading', message: `${status}...` } }));
      const response = await fetch(`${apiUrl}/teachers/interventions/${outcome.intervention_id}`, {
        method: 'PATCH',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ status }),
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.detail || 'Failed to update intervention.');
      }
      const updated = await response.json();
      setInterventionOutcomes((current) => {
        if (!current) return current;
        return {
          ...current,
          open_interventions: Math.max(
            0,
            current.open_interventions - (outcome.status === 'open' ? 1 : 0),
          ),
          outcomes: current.outcomes.map((item) =>
            item.intervention_id === updated.id
              ? {
                  ...item,
                  status: updated.status,
                  created_at: item.created_at,
                  resolved_at: updated.resolved_at,
                }
              : item
          ),
        };
      });
      setInterventionUpdateStatus((current) => ({ ...current, [key]: { state: 'success', message: `Marked ${status}.` } }));
    } catch (err) {
      setInterventionUpdateStatus((current) => ({ ...current, [key]: { state: 'error', message: err.message || 'Failed to update intervention.' } }));
    }
  };

  return (
    <main className="space-y-8 p-8">
      <header className="flex flex-col gap-6 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Teacher Analytics Hub</h1>
          <p className="mt-1 text-sm text-slate-500">
            {activeClass
              ? `${activeClass.name} - ${activeClass.subject.toUpperCase()} ${activeClass.sss_level} term ${activeClass.term}`
              : 'Track real class mastery, blockers, and graph-driven next steps.'}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => window.open('/presentation-hub', '_blank', 'noopener,noreferrer')}
            className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-xs font-black uppercase tracking-[0.16em] text-slate-700 transition hover:bg-slate-100"
          >
            <Route className="h-4 w-4" />
            Presentation hub
          </button>
          <button
            type="button"
            onClick={openTeacherPresentationPage}
            disabled={!activeClassId}
            className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2.5 text-xs font-black uppercase tracking-[0.16em] text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Sparkles className="h-4 w-4" />
            Presentation mode
          </button>
          <button
            type="button"
            onClick={openClassBriefingPage}
            disabled={!activeClassId}
            className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-xs font-black uppercase tracking-[0.16em] text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <NotebookPen className="h-4 w-4" />
            Open briefing
          </button>
          <button
            type="button"
            onClick={openClassBriefingExport}
            disabled={!activeClassId}
            className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-xs font-black uppercase tracking-[0.16em] text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Download className="h-4 w-4" />
            Export briefing
          </button>
          <select
            value={activeClassId}
            onChange={(event) => setActiveClassId(event.target.value)}
            className="min-w-[260px] rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 outline-none focus:border-indigo-500"
            disabled={isLoadingClasses || classes.length === 0}
          >
            {classes.length === 0 ? (
              <option value="">No classes available</option>
            ) : (
              classes.map((teacherClass) => (
                <option key={teacherClass.id} value={teacherClass.id}>
                  {teacherClass.name} - {teacherClass.subject.toUpperCase()} {teacherClass.sss_level} T{teacherClass.term}
                </option>
              ))
            )}
          </select>
        </div>
      </header>

      {isLoadingClasses || isLoadingDetails ? (
        <div className="flex min-h-[320px] flex-col items-center justify-center rounded-3xl border border-slate-200 bg-white text-slate-400 shadow-sm">
          <Loader2 className="mb-3 h-10 w-10 animate-spin text-indigo-500" />
          <p className="text-sm font-semibold">Loading teacher analytics...</p>
        </div>
      ) : error ? (
        <div className="flex min-h-[320px] flex-col items-center justify-center rounded-3xl border border-rose-200 bg-white text-center shadow-sm">
          <AlertCircle className="mb-3 h-10 w-10 text-rose-500" />
          <p className="max-w-xl text-sm font-semibold text-rose-700">{error}</p>
        </div>
      ) : classes.length === 0 ? (
        <div className="flex min-h-[320px] flex-col items-center justify-center rounded-3xl border border-slate-200 bg-white text-center text-slate-400 shadow-sm">
          <Users className="mb-3 h-10 w-10" />
          <p className="text-sm font-semibold">No teacher classes are available yet.</p>
        </div>
      ) : (
        <>
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4">
          <StatCard title="Students" value={dashboard?.total_students ?? 0} subtitle="Enrolled in this class" icon={Users} tone="indigo" />
          <StatCard title="Active in 7 days" value={dashboard?.active_students_7d ?? 0} subtitle="Recent learning activity" icon={Flame} tone="amber" />
          <StatCard title="Average mastery" value={`${Math.round(Number(dashboard?.avg_mastery_score || 0) * 100)}%`} subtitle="Across mapped concepts" icon={BookOpenCheck} tone="emerald" />
          <StatCard title="Study time" value={formatStudyTime(dashboard?.avg_study_time_seconds_7d)} subtitle="Average in the last 7 days" icon={BarChart3} tone="slate" />
        </div>

          {selectedStudent ? (
            <section className="rounded-3xl border border-emerald-200 bg-[linear-gradient(135deg,#ecfdf5,_#ffffff)] p-5 shadow-sm">
              <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div>
                  <div className="inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-white px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em] text-emerald-700">
                    <UserRoundSearch className="h-3.5 w-3.5" />
                    Student focus
                  </div>
                  <h2 className="mt-3 text-xl font-black text-slate-900">{selectedStudent.student_name}</h2>
                  <p className="mt-2 text-sm leading-7 text-slate-600">
                    Intervention outcomes, assignment outcomes, and the focus drawer are currently narrowed to this student.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setSelectedStudent(null)}
                  className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-black uppercase tracking-[0.16em] text-slate-700 transition hover:bg-slate-100"
                >
                  Clear student focus
                </button>
              </div>
            </section>
          ) : null}

          {graphSignal && (
            <section className="rounded-3xl border border-indigo-200 bg-[radial-gradient(circle_at_top_left,_rgba(99,102,241,0.18),_transparent_42%),linear-gradient(135deg,#ffffff,_#eef2ff)] p-6 shadow-sm">
              <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
                <div className="max-w-3xl">
                  <div className="inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-white px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em] text-indigo-700">
                    <GitBranch className="h-3.5 w-3.5" />
                    Class graph signal
                  </div>
                  <h2 className="mt-3 text-2xl font-black tracking-tight text-slate-900">{graphSignal.headline}</h2>
                  <p className="mt-2 text-sm leading-7 text-slate-600">{graphSignal.supporting_reason}</p>
                  <div className="mt-4 flex flex-wrap gap-3">
                    {graphSignal.focus_concept_label && (
                      <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-xs shadow-sm">
                        <p className="font-black uppercase tracking-[0.18em] text-slate-400">Focus concept</p>
                        <p className="mt-1 text-sm font-semibold text-slate-800">{graphSignal.focus_concept_label}</p>
                      </div>
                    )}
                    {graphSignal.blocking_prerequisite_label && (
                      <div className="rounded-2xl border border-amber-200 bg-white px-4 py-3 text-xs shadow-sm">
                        <p className="font-black uppercase tracking-[0.18em] text-amber-500">Blocking prerequisite</p>
                        <p className="mt-1 text-sm font-semibold text-slate-800">{graphSignal.blocking_prerequisite_label}</p>
                      </div>
                    )}
                    <div className="rounded-2xl border border-emerald-200 bg-white px-4 py-3 text-xs shadow-sm">
                      <p className="font-black uppercase tracking-[0.18em] text-emerald-500">Teacher action</p>
                      <p className="mt-1 text-sm font-semibold text-slate-800">{graphSignal.recommended_action}</p>
                    </div>
                  </div>
                </div>

                {graphMetrics && (
                  <div className="grid min-w-[280px] grid-cols-2 gap-3">
                    <StatCard title="Mapped concepts" value={graphMetrics.mapped_concepts} subtitle="In this scope" icon={BrainCircuit} tone="slate" />
                    <StatCard title="Blocked" value={graphMetrics.blocked_concepts} subtitle="Prereq barriers" icon={Route} tone="amber" />
                    <StatCard title="Needs attention" value={graphMetrics.weak_concepts} subtitle="Below mastery" icon={ShieldAlert} tone="indigo" />
                    <StatCard title="Mastered" value={graphMetrics.mastered_concepts} subtitle="Ready to push" icon={BookOpenCheck} tone="emerald" />
                  </div>
                )}
              </div>
            </section>
          )}

          <div className="grid grid-cols-1 gap-8 xl:grid-cols-3">
            <section className="xl:col-span-2 space-y-8">
              <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <div className="mb-6 flex items-center justify-between">
                  <div>
                    <h2 className="text-lg font-bold text-slate-800">Class Concept Graph</h2>
                    <p className="text-xs text-slate-500">Interactive prerequisite map showing where the class is blocked, weak, or ready to advance.</p>
                  </div>
                  <span className="rounded-full bg-slate-100 px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em] text-slate-500">
                    {graphSummary?.nodes?.length || 0} nodes
                  </span>
                </div>

                <TeacherClassGraph
                  graphSummary={graphSummary}
                  selectedConceptId={selectedConceptId}
                  onSelectNode={(node) => setSelectedConceptId(node?.concept_id || '')}
                />
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <div className="mb-6 flex items-center justify-between">
                  <div>
                    <h2 className="text-lg font-bold text-slate-800">Recommended Teacher Playbook</h2>
                    <p className="text-xs text-slate-500">Graph-derived next actions for this class based on blockers, weak clusters, and active alerts.</p>
                  </div>
                  <span className="rounded-full bg-slate-100 px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em] text-slate-500">
                    {graphPlaybook.length} actions
                  </span>
                </div>

                {graphPlaybook.length === 0 ? (
                  <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-8 text-center text-sm font-semibold text-slate-400">
                    No graph playbook actions are available for this class yet.
                  </div>
                ) : (
                  <div className="grid gap-3 lg:grid-cols-2">
                    {graphPlaybook.map((action, index) => (
                      <div key={`${action.action_type}-${index}`} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className={`inline-flex items-center gap-2 rounded-full px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.16em] ${
                              action.severity === 'high'
                                ? 'bg-rose-100 text-rose-700'
                                : action.severity === 'medium'
                                  ? 'bg-amber-100 text-amber-700'
                                  : 'bg-emerald-100 text-emerald-700'
                            }`}>
                              <NotebookPen className="h-3.5 w-3.5" />
                              {action.action_type.replace('_', ' ')}
                            </div>
                            <h3 className="mt-3 text-base font-bold text-slate-900">{action.title}</h3>
                            <p className="mt-2 text-sm leading-6 text-slate-600">{action.summary}</p>
                          </div>
                          <span className="rounded-full bg-white px-3 py-1 text-[11px] font-black uppercase tracking-[0.16em] text-slate-500 shadow-sm">
                            {action.severity}
                          </span>
                        </div>

                        <div className="mt-4 grid gap-2 text-xs text-slate-500 sm:grid-cols-2">
                          <div className="rounded-xl border border-slate-200 bg-white px-3 py-2">
                            <p className="font-black uppercase tracking-[0.16em] text-slate-400">Concept</p>
                            <p className="mt-1 text-sm font-semibold text-slate-800">{action.target_concept_label || 'Class scope'}</p>
                          </div>
                          <div className="rounded-xl border border-slate-200 bg-white px-3 py-2">
                            <p className="font-black uppercase tracking-[0.16em] text-slate-400">Suggested move</p>
                            <p className="mt-1 text-sm font-semibold text-slate-800">
                              {[action.suggested_assignment_type, action.suggested_intervention_type].filter(Boolean).join(' + ') || 'Teacher follow-up'}
                            </p>
                          </div>
                        </div>
                        {action.suggested_assignment_type ? (
                          <div className="mt-4 flex flex-wrap items-center gap-3">
                            <button
                              type="button"
                              onClick={() => createSuggestedAssignment(action)}
                              className="rounded-xl bg-slate-900 px-4 py-2 text-xs font-black uppercase tracking-[0.16em] text-white transition hover:bg-slate-800"
                            >
                              Create {action.suggested_assignment_type}
                            </button>
                            {assignmentStatus[`${action.action_type}-${action.target_concept_id || action.target_topic_id || action.target_concept_label || action.title}`] ? (
                              <span
                                className={`text-xs font-semibold ${
                                  assignmentStatus[`${action.action_type}-${action.target_concept_id || action.target_topic_id || action.target_concept_label || action.title}`].state === 'error'
                                    ? 'text-rose-600'
                                    : assignmentStatus[`${action.action_type}-${action.target_concept_id || action.target_topic_id || action.target_concept_label || action.title}`].state === 'success'
                                      ? 'text-emerald-600'
                                      : 'text-slate-500'
                                }`}
                              >
                                {assignmentStatus[`${action.action_type}-${action.target_concept_id || action.target_topic_id || action.target_concept_label || action.title}`].message}
                              </span>
                            ) : null}
                          </div>
                        ) : null}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <div className="mb-6 flex items-center justify-between">
                  <div>
                    <h2 className="text-lg font-bold text-slate-800">Intervention Queue</h2>
                    <p className="text-xs text-slate-500">Prioritized next actions from graph blockers and repeat-risk evidence.</p>
                  </div>
                  <span className="rounded-full bg-slate-100 px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em] text-slate-500">
                    {interventionQueue?.total_items || 0} items
                  </span>
                </div>

                {!interventionQueue?.items?.length ? (
                  <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-8 text-center text-sm font-semibold text-slate-400">
                    No intervention queue items are active for this class right now.
                  </div>
                ) : (
                  <>
                    <div className="mb-4 grid gap-3 sm:grid-cols-4">
                      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                        <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Urgent</p>
                        <p className="mt-2 text-2xl font-black text-rose-600">{interventionQueue.urgent_items || 0}</p>
                      </div>
                      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                        <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Student-targeted</p>
                        <p className="mt-2 text-2xl font-black text-indigo-600">{interventionQueue.student_targeted_items || 0}</p>
                      </div>
                      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                        <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Class-scope</p>
                        <p className="mt-2 text-2xl font-black text-slate-900">{interventionQueue.class_scope_items || 0}</p>
                      </div>
                      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                        <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Top focus</p>
                        <p className="mt-2 text-sm font-black text-slate-900">{interventionQueue.items[0]?.concept_label || 'None'}</p>
                      </div>
                    </div>

                    <div className="space-y-3">
                      {interventionQueue.items.map((item) => (
                        <div key={item.queue_id} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <div className={`inline-flex items-center gap-2 rounded-full px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.16em] ${
                                item.priority === 'urgent'
                                  ? 'bg-rose-100 text-rose-700'
                                  : item.priority === 'high'
                                    ? 'bg-amber-100 text-amber-700'
                                    : 'bg-slate-200 text-slate-700'
                              }`}>
                                {item.recommendation_type.replace('_', ' ')}
                              </div>
                              <h3 className="mt-3 text-base font-bold text-slate-900">{item.headline}</h3>
                              <p className="mt-2 text-sm leading-6 text-slate-600">{item.rationale}</p>
                            </div>
                            <span className="rounded-full bg-white px-3 py-1 text-[10px] font-black uppercase tracking-[0.16em] text-slate-500 shadow-sm">
                              {item.priority}
                            </span>
                          </div>

                          <div className="mt-4 grid gap-2 text-xs text-slate-500 sm:grid-cols-3">
                            <div className="rounded-xl border border-slate-200 bg-white px-3 py-2">
                              <p className="font-black uppercase tracking-[0.16em] text-slate-400">Student</p>
                              <p className="mt-1 text-sm font-semibold text-slate-800">{item.student_name || 'Class scope'}</p>
                            </div>
                            <div className="rounded-xl border border-slate-200 bg-white px-3 py-2">
                              <p className="font-black uppercase tracking-[0.16em] text-slate-400">Concept</p>
                              <p className="mt-1 text-sm font-semibold text-slate-800">{item.concept_label || 'Unmapped'}</p>
                            </div>
                            <div className="rounded-xl border border-slate-200 bg-white px-3 py-2">
                              <p className="font-black uppercase tracking-[0.16em] text-slate-400">Blockers</p>
                              <p className="mt-1 text-sm font-semibold text-slate-800">
                                {item.blocking_prerequisite_labels?.length ? item.blocking_prerequisite_labels.join(', ') : 'None'}
                              </p>
                            </div>
                          </div>

                          <div className="mt-4 flex flex-wrap items-center gap-3">
                            {item.concept_id ? (
                              <button
                                type="button"
                                onClick={() => setSelectedConceptId(item.concept_id)}
                                className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-black uppercase tracking-[0.16em] text-slate-700 transition hover:bg-slate-100"
                              >
                                Focus node
                              </button>
                            ) : null}
                            {item.suggested_assignment_type ? (
                              <button
                                type="button"
                                onClick={() => createQueueAssignment(item)}
                                className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-black uppercase tracking-[0.16em] text-slate-700 transition hover:bg-slate-100"
                              >
                                Assign {item.suggested_assignment_type}
                              </button>
                            ) : null}
                            {item.student_id ? (
                              <button
                                type="button"
                                onClick={() => createQueueIntervention(item)}
                                className="rounded-xl bg-slate-900 px-4 py-2 text-xs font-black uppercase tracking-[0.16em] text-white transition hover:bg-slate-800"
                              >
                                Create intervention
                              </button>
                            ) : null}
                            {queueAssignmentStatus[item.queue_id] ? (
                              <span
                                className={`text-xs font-semibold ${
                                  queueAssignmentStatus[item.queue_id].state === 'error'
                                    ? 'text-rose-600'
                                    : queueAssignmentStatus[item.queue_id].state === 'success'
                                      ? 'text-emerald-600'
                                      : 'text-slate-500'
                                }`}
                              >
                                {queueAssignmentStatus[item.queue_id].message}
                              </span>
                            ) : null}
                            {queueActionStatus[item.queue_id] ? (
                              <span
                                className={`text-xs font-semibold ${
                                  queueActionStatus[item.queue_id].state === 'error'
                                    ? 'text-rose-600'
                                    : queueActionStatus[item.queue_id].state === 'success'
                                      ? 'text-emerald-600'
                                      : 'text-slate-500'
                                }`}
                              >
                                {queueActionStatus[item.queue_id].message}
                              </span>
                            ) : null}
                          </div>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <div className="mb-6 flex items-center justify-between">
                  <div>
                    <h2 className="text-lg font-bold text-slate-800">Next Lesson Cluster Plan</h2>
                    <p className="text-xs text-slate-500">Use the class graph to decide what to repair first, what to teach next, and what to monitor while you move the class forward.</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <button
                      type="button"
                      onClick={openClusterPlanExport}
                      disabled={!nextClusterPlan}
                      className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-[11px] font-black uppercase tracking-[0.16em] text-slate-600 transition hover:bg-slate-100 hover:text-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      <Download className="h-4 w-4" />
                      Export plan
                    </button>
                    <span className="rounded-full bg-slate-100 px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em] text-slate-500">
                      {String(nextClusterPlan?.plan_status || 'collect_evidence').replace('_', ' ')}
                    </span>
                  </div>
                </div>

                {!nextClusterPlan ? (
                  <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-8 text-center text-sm font-semibold text-slate-400">
                    Next-cluster planning is unavailable for this class right now.
                  </div>
                ) : (
                  <>
                    <div className="rounded-2xl border border-indigo-100 bg-indigo-50/70 p-5">
                      <p className="text-[10px] font-black uppercase tracking-[0.18em] text-indigo-500">Planning headline</p>
                      <h3 className="mt-2 text-xl font-black text-slate-900">{nextClusterPlan.headline}</h3>
                      <p className="mt-2 text-sm leading-7 text-slate-600">{nextClusterPlan.rationale}</p>
                    </div>

                    <div className="mt-6 grid gap-4 xl:grid-cols-3">
                      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                        <div className="flex items-center gap-2">
                          <Route className="h-4 w-4 text-amber-500" />
                          <h3 className="text-sm font-bold text-slate-800">Repair first</h3>
                        </div>
                        <div className="mt-4 space-y-3">
                          {nextClusterRepairFirst.length ? nextClusterRepairFirst.map((item) => (
                            <div key={item.concept_id} className="rounded-xl border border-slate-200 bg-white p-3">
                              <p className="text-sm font-bold text-slate-900">{item.concept_label}</p>
                              <p className="mt-1 text-xs text-slate-500">{item.topic_title || 'Mapped concept node'}</p>
                              <p className="mt-2 text-xs leading-6 text-slate-600">{item.recommended_action}</p>
                            </div>
                          )) : (
                            <p className="text-sm font-medium text-slate-400">No repair-first concepts are blocking the class right now.</p>
                          )}
                        </div>
                      </div>

                      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                        <div className="flex items-center gap-2">
                          <ArrowRight className="h-4 w-4 text-indigo-500" />
                          <h3 className="text-sm font-bold text-slate-800">Teach next</h3>
                        </div>
                        <div className="mt-4 space-y-3">
                          {nextClusterTeachNext.length ? nextClusterTeachNext.map((item) => (
                            <div key={item.concept_id} className="rounded-xl border border-slate-200 bg-white p-3">
                              <div className="flex items-start justify-between gap-3">
                                <div>
                                  <p className="text-sm font-bold text-slate-900">{item.concept_label}</p>
                                  <p className="mt-1 text-xs text-slate-500">{item.topic_title || 'Mapped concept node'}</p>
                                </div>
                                <span className="text-xs font-black text-slate-500">{Math.round(Number(item.avg_score || 0) * 100)}%</span>
                              </div>
                              {item.blocking_prerequisite_labels?.length ? (
                                <p className="mt-2 text-[11px] font-semibold text-amber-700">Blocked by {item.blocking_prerequisite_labels.join(', ')}</p>
                              ) : null}
                              <p className="mt-2 text-xs leading-6 text-slate-600">{item.recommended_action}</p>
                            </div>
                          )) : (
                            <p className="text-sm font-medium text-slate-400">No teach-next cluster is ready yet. Collect more evidence first.</p>
                          )}
                        </div>
                      </div>

                      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                        <div className="flex items-center gap-2">
                          <ShieldAlert className="h-4 w-4 text-rose-500" />
                          <h3 className="text-sm font-bold text-slate-800">Watchlist</h3>
                        </div>
                        <div className="mt-4 space-y-3">
                          {nextClusterWatchlist.length ? nextClusterWatchlist.map((item) => (
                            <div key={item.concept_id} className="rounded-xl border border-slate-200 bg-white p-3">
                              <p className="text-sm font-bold text-slate-900">{item.concept_label}</p>
                              <p className="mt-1 text-xs text-slate-500">{item.topic_title || 'Mapped concept node'}</p>
                              <p className="mt-2 text-xs leading-6 text-slate-600">{item.recommended_action}</p>
                            </div>
                          )) : (
                            <p className="text-sm font-medium text-slate-400">No extra watchlist concepts are active for this cluster yet.</p>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="mt-6">
                      <div className="mb-3 flex items-center gap-2">
                        <NotebookPen className="h-4 w-4 text-slate-500" />
                        <h3 className="text-sm font-bold text-slate-800">Suggested actions for this cluster</h3>
                      </div>
                      {nextClusterActions.length ? (
                        <div className="grid gap-3 lg:grid-cols-2">
                          {nextClusterActions.map((action, index) => (
                            <div key={`${action.action_type}-${index}-cluster`} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                              <div className="flex items-start justify-between gap-3">
                                <div>
                                  <p className="text-sm font-bold text-slate-900">{action.title}</p>
                                  <p className="mt-2 text-xs leading-6 text-slate-600">{action.summary}</p>
                                </div>
                                <span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.16em] text-slate-500">
                                  {action.severity}
                                </span>
                              </div>
                              {action.suggested_assignment_type ? (
                                <div className="mt-4 flex flex-wrap items-center gap-3">
                                  <button
                                    type="button"
                                    onClick={() => createSuggestedAssignment(action)}
                                    className="rounded-xl bg-slate-900 px-4 py-2 text-xs font-black uppercase tracking-[0.16em] text-white transition hover:bg-slate-800"
                                  >
                                    Create {action.suggested_assignment_type}
                                  </button>
                                  {assignmentStatus[`${action.action_type}-${action.target_concept_id || action.target_topic_id || action.target_concept_label || action.title}`] ? (
                                    <span
                                      className={`text-xs font-semibold ${
                                        assignmentStatus[`${action.action_type}-${action.target_concept_id || action.target_topic_id || action.target_concept_label || action.title}`].state === 'error'
                                          ? 'text-rose-600'
                                          : assignmentStatus[`${action.action_type}-${action.target_concept_id || action.target_topic_id || action.target_concept_label || action.title}`].state === 'success'
                                            ? 'text-emerald-600'
                                            : 'text-slate-500'
                                      }`}
                                    >
                                      {assignmentStatus[`${action.action_type}-${action.target_concept_id || action.target_topic_id || action.target_concept_label || action.title}`].message}
                                    </span>
                                  ) : null}
                                </div>
                              ) : null}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-6 text-center text-sm font-semibold text-slate-400">
                          No cluster-specific actions are available for this class yet.
                        </div>
                      )}
                    </div>
                  </>
                )}
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <div className="mb-6 flex items-center justify-between">
                  <div>
                    <h2 className="text-lg font-bold text-slate-800">Graph Blockers</h2>
                    <p className="text-xs text-slate-500">The concept and prerequisite combinations currently slowing the class down.</p>
                  </div>
                  <span className="rounded-full bg-slate-100 px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em] text-slate-500">
                    {graphBlockers.length} blockers
                  </span>
                </div>

                {graphBlockers.length === 0 ? (
                  <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-8 text-center text-sm font-semibold text-slate-400">
                    No active graph blockers detected for this class.
                  </div>
                ) : (
                  <div className="space-y-3">
                    {graphBlockers.map((node) => {
                      const score = Math.round(Number(node.avg_score || 0) * 100);
                      return (
                        <div key={node.concept_id} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                          <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                            <div>
                              <div className="inline-flex items-center gap-2 rounded-full bg-white px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.16em] text-amber-700">
                                <Route className="h-3.5 w-3.5" />
                                {node.status.replace('_', ' ')}
                              </div>
                              <h3 className="mt-3 text-base font-bold text-slate-900">{node.concept_label}</h3>
                              <p className="mt-1 text-xs font-semibold text-slate-500">{node.topic_title || 'Mapped concept node'}</p>
                              {node.blocking_prerequisite_labels?.length > 0 && (
                                <p className="mt-2 text-xs leading-6 text-amber-700">
                                  Blocked by: {node.blocking_prerequisite_labels.join(', ')}
                                </p>
                              )}
                            </div>
                            <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-right text-xs shadow-sm">
                              <p className="font-black uppercase tracking-[0.18em] text-slate-400">Class mastery</p>
                              <p className="mt-1 text-lg font-black text-slate-800">{score}%</p>
                              <p className="mt-1 text-[11px] font-medium text-slate-500">{node.student_count} student{node.student_count === 1 ? '' : 's'}</p>
                            </div>
                          </div>
                          <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-200">
                            <div className="h-full rounded-full bg-amber-500" style={{ width: `${Math.max(score, 4)}%` }} />
                          </div>
                          <div className="mt-3 flex items-start gap-2 text-xs leading-6 text-slate-600">
                            <ArrowRight className="mt-0.5 h-3.5 w-3.5 text-indigo-500" />
                            <span>{node.recommended_action}</span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <div className="mb-6 flex items-center justify-between">
                  <div>
                    <h2 className="text-lg font-bold text-slate-800">Weakest Concepts</h2>
                    <p className="text-xs text-slate-500">Real mastery averages from the graph-backed class heatmap.</p>
                  </div>
                  <span className="rounded-full bg-slate-100 px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em] text-slate-500">
                    {weakestConcepts.length} concepts
                  </span>
                </div>

                {weakestConcepts.length === 0 ? (
                  <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-8 text-center text-sm font-semibold text-slate-400">
                    No concept heatmap data is available for this class yet.
                  </div>
                ) : (
                  <div className="space-y-3">
                    {weakestConcepts.map((point) => {
                      const score = Math.round(Number(point.avg_score || 0) * 100);
                      const tone = score < 40 ? 'bg-rose-500' : score < 70 ? 'bg-amber-500' : 'bg-emerald-500';
                      return (
                        <div key={point.concept_id} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                          <div className="flex items-center justify-between gap-4">
                            <div>
                              <h3 className="text-sm font-bold text-slate-900">{humanizeConceptId(point.concept_id)}</h3>
                              <p className="mt-1 text-xs text-slate-500">{point.student_count} student{point.student_count === 1 ? '' : 's'} contributing</p>
                            </div>
                            <span className="text-sm font-black text-slate-700">{score}%</span>
                          </div>
                          <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-200">
                            <div className={`h-full rounded-full ${tone}`} style={{ width: `${Math.max(score, 4)}%` }} />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </section>

            <section className="space-y-6">
              <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <h2 className="flex items-center gap-2 text-lg font-bold text-slate-800">
                      <UserRoundSearch className="h-5 w-5 text-indigo-500" />
                      Students Driving This Node
                    </h2>
                    <p className="mt-1 text-xs text-slate-500">
                      Student-level mastery and prerequisite evidence for the currently selected concept graph node.
                    </p>
                  </div>
                  {conceptStudents?.students?.some((student) => ['blocked', 'needs_attention'].includes(student.status)) ? (
                    <div className="flex flex-wrap items-center gap-3">
                      <button
                        type="button"
                        onClick={createBulkConceptAssignments}
                        className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-black uppercase tracking-[0.16em] text-slate-700 transition hover:bg-slate-100"
                      >
                        Bulk repair assignment
                      </button>
                      <button
                        type="button"
                        onClick={createBulkConceptInterventions}
                        className="rounded-xl bg-slate-900 px-4 py-2 text-xs font-black uppercase tracking-[0.16em] text-white transition hover:bg-slate-800"
                      >
                        Bulk support this node
                      </button>
                    </div>
                  ) : null}
                </div>
                {bulkAssignmentStatus ? (
                  <p
                    className={`mt-4 text-xs font-semibold ${
                      bulkAssignmentStatus.state === 'error'
                        ? 'text-rose-600'
                        : bulkAssignmentStatus.state === 'success'
                          ? 'text-emerald-600'
                          : 'text-slate-500'
                    }`}
                  >
                    {bulkAssignmentStatus.message}
                  </p>
                ) : null}
                {bulkInterventionStatus ? (
                  <p
                    className={`mt-4 text-xs font-semibold ${
                      bulkInterventionStatus.state === 'error'
                        ? 'text-rose-600'
                        : bulkInterventionStatus.state === 'success'
                          ? 'text-emerald-600'
                          : 'text-slate-500'
                    }`}
                  >
                    {bulkInterventionStatus.message}
                  </p>
                ) : null}

                <div className="mt-6 space-y-3">
                  {isLoadingConceptStudents ? (
                    <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-6 text-center text-sm font-semibold text-slate-400">
                      Loading student drilldown...
                    </div>
                  ) : !conceptStudents?.students?.length ? (
                    <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-6 text-center text-sm font-semibold text-slate-400">
                      Select a mapped node to inspect the affected students.
                    </div>
                  ) : (
                    conceptStudents.students.slice(0, 8).map((student) => (
                      <div key={student.student_id} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="text-sm font-bold text-slate-900">{student.student_name}</p>
                            <p className="mt-1 text-xs text-slate-500">
                              {student.status.replace('_', ' ')} on {conceptStudents.concept_label}
                            </p>
                          </div>
                          <span className={`rounded-full px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.16em] ${
                            student.status === 'blocked'
                              ? 'bg-amber-100 text-amber-700'
                              : student.status === 'needs_attention'
                                ? 'bg-indigo-100 text-indigo-700'
                                : student.status === 'mastered'
                                  ? 'bg-emerald-100 text-emerald-700'
                                  : 'bg-slate-200 text-slate-700'
                          }`}>
                            {student.status.replace('_', ' ')}
                          </span>
                        </div>

                        <div className="mt-4 grid gap-2 text-xs text-slate-500 sm:grid-cols-2">
                          <div className="rounded-xl border border-slate-200 bg-white px-3 py-2">
                            <p className="font-black uppercase tracking-[0.16em] text-slate-400">Concept score</p>
                            <p className="mt-1 text-sm font-semibold text-slate-800">
                              {student.concept_score == null ? 'Unassessed' : `${Math.round(Number(student.concept_score) * 100)}%`}
                            </p>
                          </div>
                          <div className="rounded-xl border border-slate-200 bg-white px-3 py-2">
                            <p className="font-black uppercase tracking-[0.16em] text-slate-400">Overall mastery</p>
                            <p className="mt-1 text-sm font-semibold text-slate-800">
                              {student.overall_mastery_score == null ? 'Unassessed' : `${Math.round(Number(student.overall_mastery_score) * 100)}%`}
                            </p>
                          </div>
                        </div>

                        {student.blocking_prerequisite_labels?.length ? (
                          <p className="mt-3 text-xs leading-6 text-amber-700">
                            Blocked by: {student.blocking_prerequisite_labels.join(', ')}
                          </p>
                        ) : null}

                        <div className="mt-3 flex flex-wrap gap-3 text-[11px] font-medium text-slate-500">
                          <span>{student.recent_activity_count_7d} activities in 7d</span>
                          <span>{formatStudyTime(student.recent_study_time_seconds_7d)} study time</span>
                        </div>
                        <p className="mt-3 text-xs leading-6 text-slate-600">{student.recommended_action}</p>
                        <div className="mt-4 flex flex-wrap items-center gap-3">
                          <button
                            type="button"
                            onClick={() => setSelectedStudent(student)}
                            className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-black uppercase tracking-[0.16em] text-slate-700 transition hover:bg-slate-100"
                          >
                            View student
                          </button>
                          <button
                            type="button"
                            onClick={() => createStudentIntervention(student)}
                            className="rounded-xl bg-indigo-600 px-4 py-2 text-xs font-black uppercase tracking-[0.16em] text-white transition hover:bg-indigo-500"
                          >
                            Create intervention
                          </button>
                          {interventionStatus[`${student.student_id}-${conceptStudents.concept_id}`] ? (
                            <span
                              className={`text-xs font-semibold ${
                                interventionStatus[`${student.student_id}-${conceptStudents.concept_id}`].state === 'error'
                                  ? 'text-rose-600'
                                  : interventionStatus[`${student.student_id}-${conceptStudents.concept_id}`].state === 'success'
                                    ? 'text-emerald-600'
                                    : 'text-slate-500'
                              }`}
                            >
                              {interventionStatus[`${student.student_id}-${conceptStudents.concept_id}`].message}
                            </span>
                          ) : null}
                        </div>
                      </div>
                    ))
                  )}
                </div>

                <div className="mt-6 rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                      <h3 className="text-sm font-black uppercase tracking-[0.18em] text-slate-600">Compare students on this concept</h3>
                      <p className="mt-2 text-xs leading-6 text-slate-500">
                        Compare two students on the selected graph node to see whether they need the same intervention or different next steps.
                      </p>
                    </div>
                    <div className="grid gap-3 sm:grid-cols-2">
                      <label className="flex flex-col gap-1 text-[11px] font-black uppercase tracking-[0.16em] text-slate-500">
                        Student A
                        <select
                          value={primaryCompareStudentId}
                          onChange={(event) => setPrimaryCompareStudentId(event.target.value)}
                          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold normal-case tracking-normal text-slate-700"
                        >
                          {studentCompareOptions.map((option) => (
                            <option key={option.value} value={option.value}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="flex flex-col gap-1 text-[11px] font-black uppercase tracking-[0.16em] text-slate-500">
                        Student B
                        <select
                          value={secondaryCompareStudentId}
                          onChange={(event) => setSecondaryCompareStudentId(event.target.value)}
                          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold normal-case tracking-normal text-slate-700"
                        >
                          {studentCompareOptions
                            .filter((option) => option.value !== primaryCompareStudentId)
                            .map((option) => (
                              <option key={option.value} value={option.value}>
                                {option.label}
                              </option>
                            ))}
                        </select>
                      </label>
                    </div>
                  </div>

                  {isLoadingStudentCompare ? (
                    <div className="mt-4 flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-4 text-sm font-semibold text-slate-500">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Comparing student concept paths...
                    </div>
                  ) : !primaryCompareTrend || !secondaryCompareTrend ? (
                    <div className="mt-4 rounded-2xl border border-dashed border-slate-200 bg-white p-6 text-center text-sm font-semibold text-slate-400">
                      Choose two different students from this node to compare their concept trend.
                    </div>
                  ) : (
                    <>
                      <div className="mt-4 rounded-2xl border border-violet-100 bg-violet-50 p-4">
                        <p className="text-sm font-black text-slate-900">{studentCompareNarrative?.headline}</p>
                        <p className="mt-2 text-sm leading-6 text-slate-600">{studentCompareNarrative?.rationale}</p>
                      </div>
                      <div className="mt-4 grid gap-4 lg:grid-cols-2">
                        {[{
                          key: 'primary',
                          studentId: primaryCompareStudentId,
                          trend: primaryCompareTrend,
                        }, {
                          key: 'secondary',
                          studentId: secondaryCompareStudentId,
                          trend: secondaryCompareTrend,
                        }].map(({ key, studentId, trend }) => {
                          const studentLabel = studentCompareOptions.find((item) => item.value === studentId)?.label || 'Student';
                          return (
                            <div key={key} className="rounded-2xl border border-slate-200 bg-white p-4">
                              <div className="flex items-start justify-between gap-3">
                                <div>
                                  <p className="text-sm font-bold text-slate-900">{studentLabel}</p>
                                  <p className="mt-1 text-xs text-slate-500">{trend.status.replace('_', ' ')} on {trend.concept_label}</p>
                                </div>
                                <button
                                  type="button"
                                  onClick={() => {
                                    const sourceStudent = conceptStudents?.students?.find((item) => item.student_id === studentId);
                                    if (sourceStudent) openStudentFocus(sourceStudent, { concept_id: selectedConceptId, concept_label: trend.concept_label, status: trend.status }, { status: trend.status, concept_score: trend.current_score, blocking_prerequisite_labels: trend.blocking_prerequisite_labels });
                                  }}
                                  className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-[11px] font-black uppercase tracking-[0.16em] text-slate-600 transition hover:bg-slate-100 hover:text-slate-800"
                                >
                                  Open focus
                                </button>
                              </div>
                              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                                <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
                                  <p className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-400">Current score</p>
                                  <p className="mt-2 text-xl font-black text-slate-900">
                                    {trend.current_score == null ? 'Unassessed' : `${Math.round(Number(trend.current_score) * 100)}%`}
                                  </p>
                                </div>
                                <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
                                  <p className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-400">Net delta (30d)</p>
                                  <p className={`mt-2 text-xl font-black ${Number(trend.net_delta_30d || 0) >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
                                    {Number(trend.net_delta_30d || 0) >= 0 ? '+' : ''}{Number(trend.net_delta_30d || 0).toFixed(2)}
                                  </p>
                                </div>
                              </div>
                              {trend.blocking_prerequisite_labels?.length ? (
                                <p className="mt-4 text-xs leading-6 text-amber-700">
                                  Blocked by: {trend.blocking_prerequisite_labels.join(', ')}
                                </p>
                              ) : (
                                <p className="mt-4 text-xs leading-6 text-slate-500">No blocking prerequisite is currently holding this student back.</p>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </>
                  )}
                </div>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <h2 className="flex items-center gap-2 text-lg font-bold text-slate-800">
                  <UserRoundSearch className="h-5 w-5 text-indigo-500" />
                  Repeat-Risk Students
                </h2>
                <p className="mt-1 text-xs text-slate-500">Students repeatedly driving blocked or weak concepts across the mapped class graph.</p>

                <div className="mt-6 grid gap-3 sm:grid-cols-3">
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">At risk</p>
                    <p className="mt-2 text-2xl font-black text-slate-900">{repeatRisk?.at_risk_student_count ?? 0}</p>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Repeat blockers</p>
                    <p className="mt-2 text-2xl font-black text-amber-600">{repeatRisk?.repeat_blocker_students ?? 0}</p>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Repeat weakness</p>
                    <p className="mt-2 text-2xl font-black text-indigo-600">{repeatRisk?.repeat_weakness_students ?? 0}</p>
                  </div>
                </div>

                <div className="mt-6 space-y-3">
                  {repeatRisk?.students?.length ? (
                    repeatRisk.students.map((student) => {
                      const focusConcept = student.driving_concepts?.[0] || null;
                      const interventionKey = focusConcept ? `${student.student_id}-${focusConcept.concept_id}` : null;
                      return (
                        <div key={student.student_id} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <p className="text-sm font-bold text-slate-900">{student.student_name}</p>
                              <p className="mt-1 text-xs text-slate-500">
                                {student.blocked_concept_count} blocked • {student.weak_concept_count} weak • {student.flagged_concept_count} flagged concepts
                              </p>
                            </div>
                            <span className={`rounded-full px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.16em] ${
                              student.risk_status === 'repeat_blocker'
                                ? 'bg-amber-100 text-amber-700'
                                : 'bg-indigo-100 text-indigo-700'
                            }`}>
                              {student.risk_status.replace('_', ' ')}
                            </span>
                          </div>

                          <div className="mt-4 grid gap-2 text-xs text-slate-500 sm:grid-cols-3">
                            <div className="rounded-xl border border-slate-200 bg-white px-3 py-2">
                              <p className="font-black uppercase tracking-[0.16em] text-slate-400">Overall mastery</p>
                              <p className="mt-1 text-sm font-semibold text-slate-800">
                                {student.overall_mastery_score == null ? 'Unassessed' : `${Math.round(Number(student.overall_mastery_score) * 100)}%`}
                              </p>
                            </div>
                            <div className="rounded-xl border border-slate-200 bg-white px-3 py-2">
                              <p className="font-black uppercase tracking-[0.16em] text-slate-400">Activity in 7d</p>
                              <p className="mt-1 text-sm font-semibold text-slate-800">{student.recent_activity_count_7d} events</p>
                            </div>
                            <div className="rounded-xl border border-slate-200 bg-white px-3 py-2">
                              <p className="font-black uppercase tracking-[0.16em] text-slate-400">Study time</p>
                              <p className="mt-1 text-sm font-semibold text-slate-800">{formatStudyTime(student.recent_study_time_seconds_7d)}</p>
                            </div>
                          </div>

                          <p className="mt-3 text-xs leading-6 text-slate-600">{student.recommended_action}</p>

                          <div className="mt-4 flex flex-wrap gap-2">
                            {student.driving_concepts?.map((concept) => (
                              <button
                                key={`${student.student_id}-${concept.concept_id}`}
                                type="button"
                                onClick={() => setSelectedConceptId(concept.concept_id)}
                                className={`rounded-full border px-3 py-1.5 text-[11px] font-black uppercase tracking-[0.14em] transition ${
                                  concept.status === 'blocked'
                                    ? 'border-amber-200 bg-amber-50 text-amber-700 hover:bg-amber-100'
                                    : 'border-indigo-200 bg-indigo-50 text-indigo-700 hover:bg-indigo-100'
                                }`}
                              >
                                {concept.concept_label}
                              </button>
                            ))}
                          </div>

                          <div className="mt-4 flex flex-wrap items-center gap-3">
                            <button
                              type="button"
                              onClick={() => openStudentFocus(student, focusConcept)}
                              className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-black uppercase tracking-[0.16em] text-slate-700 transition hover:bg-slate-100"
                            >
                              View student
                            </button>
                            <button
                              type="button"
                              onClick={() => createRepeatRiskIntervention(student)}
                              className="rounded-xl bg-indigo-600 px-4 py-2 text-xs font-black uppercase tracking-[0.16em] text-white transition hover:bg-indigo-500"
                            >
                              Create intervention
                            </button>
                            {interventionKey && interventionStatus[interventionKey] ? (
                              <span
                                className={`text-xs font-semibold ${
                                  interventionStatus[interventionKey].state === 'error'
                                    ? 'text-rose-600'
                                    : interventionStatus[interventionKey].state === 'success'
                                      ? 'text-emerald-600'
                                      : 'text-slate-500'
                                }`}
                              >
                                {interventionStatus[interventionKey].message}
                              </span>
                            ) : null}
                          </div>
                        </div>
                      );
                    })
                  ) : (
                    <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-6 text-center text-sm font-semibold text-slate-400">
                      No repeat-risk students are active in this class right now.
                    </div>
                  )}
                </div>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <h2 className="flex items-center gap-2 text-lg font-bold text-slate-800">
                  <BrainCircuit className="h-5 w-5 text-violet-500" />
                  Student Risk Matrix
                </h2>
                <p className="mt-1 text-xs text-slate-500">Compare the same at-risk students against the same blocked and weak concepts in one view.</p>

                {!riskMatrix?.concepts?.length || !riskMatrix?.students?.length ? (
                  <div className="mt-6 rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-6 text-center text-sm font-semibold text-slate-400">
                    No class risk matrix is available yet for this scope.
                  </div>
                ) : (
                  <div className="mt-6 overflow-x-auto">
                    <table className="min-w-full border-separate border-spacing-y-2">
                      <thead>
                        <tr>
                          <th className="px-3 py-2 text-left text-[10px] font-black uppercase tracking-[0.16em] text-slate-400">Student</th>
                          {riskMatrix.concepts.map((concept) => (
                            <th key={concept.concept_id} className="px-3 py-2 text-left text-[10px] font-black uppercase tracking-[0.16em] text-slate-400">
                              {concept.concept_label}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {riskMatrix.students.map((student) => (
                          <tr key={student.student_id} className="rounded-2xl bg-slate-50">
                            <td className="rounded-l-2xl border border-slate-200 bg-white px-3 py-3 align-top">
                              <button
                                type="button"
                                onClick={() => openStudentFocus(student, riskMatrix.concepts[0], student.cells?.[0] || null)}
                                className="text-left"
                              >
                                <p className="text-sm font-bold text-slate-900">{student.student_name}</p>
                                <p className="mt-1 text-[11px] font-medium text-slate-500">
                                  {student.blocked_concept_count} blocked • {student.weak_concept_count} weak
                                </p>
                              </button>
                            </td>
                            {riskMatrix.concepts.map((concept, index) => {
                              const cell = student.cells.find((item) => item.concept_id === concept.concept_id);
                              const tone =
                                cell?.status === 'blocked'
                                  ? 'border-amber-200 bg-amber-50 text-amber-700'
                                  : cell?.status === 'needs_attention'
                                    ? 'border-indigo-200 bg-indigo-50 text-indigo-700'
                                    : cell?.status === 'mastered'
                                      ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                                      : 'border-slate-200 bg-white text-slate-400';

                              return (
                                <td
                                  key={`${student.student_id}-${concept.concept_id}`}
                                  className={`${index === riskMatrix.concepts.length - 1 ? 'rounded-r-2xl' : ''} border border-slate-200 bg-white px-3 py-3 align-top`}
                                >
                                  <button
                                    type="button"
                                    onClick={() => openStudentFocus(student, concept, cell)}
                                    className={`w-full rounded-xl border px-3 py-3 text-left transition ${tone}`}
                                  >
                                    <p className="text-[10px] font-black uppercase tracking-[0.16em]">
                                      {cell?.status ? cell.status.replace('_', ' ') : 'unassessed'}
                                    </p>
                                    <p className="mt-2 text-sm font-semibold">
                                      {cell?.concept_score == null ? 'No score yet' : `${Math.round(Number(cell.concept_score) * 100)}%`}
                                    </p>
                                    {cell?.blocking_prerequisite_labels?.length ? (
                                      <p className="mt-2 text-[11px] leading-5">
                                        Blocked by {cell.blocking_prerequisite_labels.join(', ')}
                                      </p>
                                    ) : null}
                                  </button>
                                </td>
                              );
                            })}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <h2 className="flex items-center gap-2 text-lg font-bold text-slate-800">
                      <BarChart3 className="h-5 w-5 text-violet-500" />
                      Compare Two Concepts
                    </h2>
                    <p className="mt-1 text-xs text-slate-500">
                      Compare two mapped graph concepts across the same class roster and see which one is the stronger blocker.
                    </p>
                  </div>
                  <div className="space-y-3">
                    <button
                      type="button"
                      onClick={openConceptCompareExport}
                      disabled={!conceptCompare}
                      className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-[11px] font-black uppercase tracking-[0.16em] text-slate-600 transition hover:bg-slate-100 hover:text-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      <Download className="h-4 w-4" />
                      Export compare
                    </button>
                    <div className="grid gap-3 sm:grid-cols-2">
                    <label className="flex flex-col gap-1 text-[11px] font-black uppercase tracking-[0.16em] text-slate-500">
                      Focus concept
                      <select
                        value={selectedConceptId}
                        onChange={(event) => setSelectedConceptId(event.target.value)}
                        className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold normal-case tracking-normal text-slate-700"
                      >
                        {compareOptions.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="flex flex-col gap-1 text-[11px] font-black uppercase tracking-[0.16em] text-slate-500">
                      Compare against
                      <select
                        value={compareConceptId}
                        onChange={(event) => setCompareConceptId(event.target.value)}
                        className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold normal-case tracking-normal text-slate-700"
                      >
                        {compareOptions
                          .filter((option) => option.value !== selectedConceptId)
                          .map((option) => (
                            <option key={option.value} value={option.value}>
                              {option.label}
                            </option>
                          ))}
                      </select>
                    </label>
                    </div>
                  </div>
                </div>

                {isLoadingConceptCompare ? (
                  <div className="mt-6 flex items-center gap-2 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 text-sm font-semibold text-slate-500">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Comparing graph evidence...
                  </div>
                ) : !conceptCompare ? (
                  <div className="mt-6 rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-6 text-center text-sm font-semibold text-slate-400">
                    Select two different mapped concepts to compare their class impact.
                  </div>
                ) : (
                  <>
                    <div className="mt-6 grid gap-4 lg:grid-cols-[1.2fr_1fr_1fr]">
                      <div className="rounded-2xl border border-violet-100 bg-violet-50 p-4">
                        <p className="text-[10px] font-black uppercase tracking-[0.18em] text-violet-500">Recommendation</p>
                        <p className="mt-2 text-lg font-black text-slate-900">{conceptCompare.summary.headline}</p>
                        <p className="mt-2 text-sm leading-6 text-slate-600">{conceptCompare.summary.rationale}</p>
                      </div>
                      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                        <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">{conceptCompare.left.concept_label}</p>
                        <p className="mt-2 text-2xl font-black text-slate-900">
                          {conceptCompare.summary.avg_left_score == null ? 'Unassessed' : `${Math.round(Number(conceptCompare.summary.avg_left_score) * 100)}%`}
                        </p>
                        <p className="mt-2 text-xs font-semibold text-slate-500">{conceptCompare.summary.left_weaker_count} students weaker here</p>
                      </div>
                      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                        <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">{conceptCompare.right.concept_label}</p>
                        <p className="mt-2 text-2xl font-black text-slate-900">
                          {conceptCompare.summary.avg_right_score == null ? 'Unassessed' : `${Math.round(Number(conceptCompare.summary.avg_right_score) * 100)}%`}
                        </p>
                        <p className="mt-2 text-xs font-semibold text-slate-500">{conceptCompare.summary.right_weaker_count} students weaker here</p>
                      </div>
                    </div>

                    <div className="mt-4 grid gap-3 sm:grid-cols-4">
                      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                        <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Students compared</p>
                        <p className="mt-2 text-2xl font-black text-slate-900">{conceptCompare.summary.students_compared}</p>
                      </div>
                      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                        <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Both blocked</p>
                        <p className="mt-2 text-2xl font-black text-rose-600">{conceptCompare.summary.both_blocked_count}</p>
                      </div>
                      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                        <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Left weaker</p>
                        <p className="mt-2 text-2xl font-black text-amber-600">{conceptCompare.summary.left_weaker_count}</p>
                      </div>
                      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                        <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Right weaker</p>
                        <p className="mt-2 text-2xl font-black text-indigo-600">{conceptCompare.summary.right_weaker_count}</p>
                      </div>
                    </div>

                    <div className="mt-6 overflow-x-auto rounded-2xl border border-slate-200">
                      <table className="min-w-full divide-y divide-slate-200">
                        <thead className="bg-slate-50">
                          <tr>
                            <th className="px-4 py-3 text-left text-[11px] font-black uppercase tracking-[0.18em] text-slate-400">Student</th>
                            <th className="px-4 py-3 text-left text-[11px] font-black uppercase tracking-[0.18em] text-slate-400">{conceptCompare.left.concept_label}</th>
                            <th className="px-4 py-3 text-left text-[11px] font-black uppercase tracking-[0.18em] text-slate-400">{conceptCompare.right.concept_label}</th>
                            <th className="px-4 py-3 text-left text-[11px] font-black uppercase tracking-[0.18em] text-slate-400">Signal</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100 bg-white">
                          {conceptCompare.students.map((student) => (
                            <tr key={student.student_id}>
                              <td className="px-4 py-4 align-top">
                                <button
                                  type="button"
                                  onClick={() => setSelectedStudent({
                                    student_id: student.student_id,
                                    student_name: student.student_name,
                                    concept_score: student.left.concept_score,
                                    overall_mastery_score: student.overall_mastery_score,
                                    status: student.left.status,
                                    blocking_prerequisite_labels: student.left.blocking_prerequisite_labels,
                                    recent_activity_count_7d: student.recent_activity_count_7d,
                                    recent_study_time_seconds_7d: student.recent_study_time_seconds_7d,
                                    recommended_action: student.comparison_signal === 'right_weaker'
                                      ? `Focus ${conceptCompare.right.concept_label} before ${conceptCompare.left.concept_label}.`
                                      : student.comparison_signal === 'both_ready'
                                        ? `This student is ready across both compared concepts.`
                                        : `Focus ${conceptCompare.left.concept_label} before ${conceptCompare.right.concept_label}.`,
                                    last_evaluated_at: null,
                                  })}
                                  className="text-left"
                                >
                                  <p className="text-sm font-bold text-slate-900 transition hover:text-indigo-600">{student.student_name}</p>
                                  <p className="mt-1 text-[11px] font-semibold text-slate-500">
                                    Overall {student.overall_mastery_score == null ? 'Unassessed' : `${Math.round(Number(student.overall_mastery_score) * 100)}%`}
                                  </p>
                                </button>
                              </td>
                              <td className="px-4 py-4 align-top">
                                <p className="text-sm font-bold text-slate-900">
                                  {student.left.concept_score == null ? 'Unassessed' : `${Math.round(Number(student.left.concept_score) * 100)}%`}
                                </p>
                                <p className="mt-1 text-[11px] font-semibold text-slate-500">{student.left.status.replace('_', ' ')}</p>
                                {student.left.blocking_prerequisite_labels.length ? (
                                  <p className="mt-2 text-[11px] text-amber-700">Blocked by {student.left.blocking_prerequisite_labels.join(', ')}</p>
                                ) : null}
                              </td>
                              <td className="px-4 py-4 align-top">
                                <p className="text-sm font-bold text-slate-900">
                                  {student.right.concept_score == null ? 'Unassessed' : `${Math.round(Number(student.right.concept_score) * 100)}%`}
                                </p>
                                <p className="mt-1 text-[11px] font-semibold text-slate-500">{student.right.status.replace('_', ' ')}</p>
                                {student.right.blocking_prerequisite_labels.length ? (
                                  <p className="mt-2 text-[11px] text-amber-700">Blocked by {student.right.blocking_prerequisite_labels.join(', ')}</p>
                                ) : null}
                              </td>
                              <td className="px-4 py-4 align-top">
                                <span className={`inline-flex rounded-full px-3 py-1 text-[10px] font-black uppercase tracking-[0.16em] ${
                                  student.comparison_signal === 'both_blocked'
                                    ? 'bg-rose-100 text-rose-700'
                                    : student.comparison_signal === 'left_weaker'
                                      ? 'bg-amber-100 text-amber-700'
                                      : student.comparison_signal === 'right_weaker'
                                        ? 'bg-indigo-100 text-indigo-700'
                                        : student.comparison_signal === 'both_ready'
                                          ? 'bg-emerald-100 text-emerald-700'
                                          : 'bg-slate-200 text-slate-700'
                                }`}>
                                  {student.comparison_signal.replace('_', ' ')}
                                </span>
                                <p className="mt-2 text-[11px] font-medium text-slate-500">
                                  {student.comparison_signal === 'left_weaker'
                                    ? `${conceptCompare.left.concept_label} needs attention first.`
                                    : student.comparison_signal === 'right_weaker'
                                      ? `${conceptCompare.right.concept_label} needs attention first.`
                                      : student.comparison_signal === 'both_blocked'
                                        ? 'Both concepts are blocked and need sequencing support.'
                                        : student.comparison_signal === 'both_ready'
                                          ? 'This student is ready across both compared concepts.'
                                          : 'Use the scores and blockers to decide the best next support move.'}
                                </p>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </>
                )}
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <h2 className="flex items-center gap-2 text-lg font-bold text-slate-800">
                  <NotebookPen className="h-5 w-5 text-indigo-500" />
                  Assignment Outcomes
                </h2>
                <p className="mt-1 text-xs text-slate-500">Whether teacher assignments are followed by real student engagement and mastery movement.</p>
                {selectedStudent ? (
                  <div className="mt-4 rounded-2xl border border-indigo-100 bg-indigo-50 px-4 py-3 text-xs font-semibold text-indigo-700">
                    Showing student-targeted assignment outcomes for {selectedStudent.student_name}. Class-wide assignments are hidden in this focused view.
                  </div>
                ) : null}
                {selectedConceptId ? (
                  <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs font-semibold text-slate-600">
                    Exact concept filter: {conceptStudents?.concept_label || humanizeConceptId(selectedConceptId)}
                  </div>
                ) : null}

                <div className="mt-6 grid gap-3 sm:grid-cols-2">
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Improving</p>
                    <p className="mt-2 text-2xl font-black text-emerald-600">{selectedStudent ? filteredAssignmentOutcomeSummary.improving : (assignmentOutcomes?.improving_assignments ?? 0)}</p>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">No evidence</p>
                    <p className="mt-2 text-2xl font-black text-amber-600">{selectedStudent ? filteredAssignmentOutcomeSummary.noEvidence : (assignmentOutcomes?.no_evidence_assignments ?? 0)}</p>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Declining</p>
                    <p className="mt-2 text-2xl font-black text-rose-600">{selectedStudent ? filteredAssignmentOutcomeSummary.declining : (assignmentOutcomes?.declining_assignments ?? 0)}</p>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Avg mastery delta</p>
                    <p className="mt-2 text-2xl font-black text-slate-900">
                      {selectedStudent ? filteredAssignmentOutcomeSummary.avgDelta : Number(assignmentOutcomes?.avg_net_mastery_delta || 0).toFixed(2)}
                    </p>
                  </div>
                </div>

                <div className="mt-6 space-y-3">
                  {filteredAssignmentOutcomeRows.length ? (
                    filteredAssignmentOutcomeRows.slice(0, 6).map((outcome) => (
                      <div key={outcome.assignment_id} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="text-sm font-bold text-slate-900">{outcome.title}</p>
                            <p className="mt-1 text-xs text-slate-500">
                              {outcome.assignment_type} • {outcome.target_scope} assignment • {outcome.status}
                            </p>
                            {outcome.concept_label ? <p className="mt-1 text-[11px] font-semibold text-amber-700">{outcome.concept_label}</p> : null}
                            {outcome.student_name ? <p className="mt-1 text-[11px] font-semibold text-indigo-600">{outcome.student_name}</p> : null}
                          </div>
                          <span className={`rounded-full px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.16em] ${
                            outcome.outcome_status === 'improving'
                              ? 'bg-emerald-100 text-emerald-700'
                              : outcome.outcome_status === 'declining'
                                ? 'bg-rose-100 text-rose-700'
                                : outcome.outcome_status === 'no_evidence'
                                  ? 'bg-amber-100 text-amber-700'
                                  : 'bg-slate-200 text-slate-700'
                          }`}>
                            {outcome.outcome_status.replace('_', ' ')}
                          </span>
                        </div>
                        <div className="mt-3 flex flex-wrap gap-3 text-[11px] font-medium text-slate-500">
                          <span>{outcome.engaged_student_count}/{outcome.target_student_count} students engaged</span>
                          <span>{outcome.evidence_event_count} mastery event{outcome.evidence_event_count === 1 ? '' : 's'}</span>
                          <span>Net delta {Number(outcome.net_mastery_delta || 0).toFixed(2)}</span>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-6 text-center text-sm font-semibold text-slate-400">
                      {selectedStudent ? `No student-targeted assignment outcomes are available for ${selectedStudent.student_name} yet.` : 'No assignment outcomes are available for this class yet.'}
                    </div>
                  )}
                </div>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <h2 className="flex items-center gap-2 text-lg font-bold text-slate-800">
                  <Flame className="h-5 w-5 text-rose-500" />
                  Intervention Outcomes
                </h2>
                <p className="mt-1 text-xs text-slate-500">Whether recent teacher interventions are followed by real mastery movement.</p>
                {selectedStudent ? (
                  <div className="mt-4 rounded-2xl border border-rose-100 bg-rose-50 px-4 py-3 text-xs font-semibold text-rose-700">
                    Showing intervention outcomes for {selectedStudent.student_name}.
                  </div>
                ) : null}
                {selectedConceptId ? (
                  <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs font-semibold text-slate-600">
                    Exact concept filter: {conceptStudents?.concept_label || humanizeConceptId(selectedConceptId)}
                  </div>
                ) : null}

                <div className="mt-6 grid gap-3 sm:grid-cols-2">
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Improving</p>
                    <p className="mt-2 text-2xl font-black text-emerald-600">{selectedStudent ? filteredInterventionOutcomeSummary.improving : (interventionOutcomes?.improving_interventions ?? 0)}</p>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">No evidence</p>
                    <p className="mt-2 text-2xl font-black text-amber-600">{selectedStudent ? filteredInterventionOutcomeSummary.noEvidence : (interventionOutcomes?.no_evidence_interventions ?? 0)}</p>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Declining</p>
                    <p className="mt-2 text-2xl font-black text-rose-600">{selectedStudent ? filteredInterventionOutcomeSummary.declining : (interventionOutcomes?.declining_interventions ?? 0)}</p>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Avg mastery delta</p>
                    <p className="mt-2 text-2xl font-black text-slate-900">
                      {selectedStudent ? filteredInterventionOutcomeSummary.avgDelta : Number(interventionOutcomes?.avg_net_mastery_delta || 0).toFixed(2)}
                    </p>
                  </div>
                </div>

                <div className="mt-6 space-y-3">
                  {filteredInterventionOutcomeRows.length ? (
                    filteredInterventionOutcomeRows.slice(0, 6).map((outcome) => (
                      <div key={outcome.intervention_id} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="text-sm font-bold text-slate-900">{outcome.student_name}</p>
                            {outcome.concept_label ? (
                              <p className="mt-1 text-[11px] font-semibold text-amber-700">{outcome.concept_label}</p>
                            ) : null}
                            <p className="mt-1 text-xs text-slate-500">{outcome.intervention_type.replace('_', ' ')} • {outcome.status}</p>
                          </div>
                          <span className={`rounded-full px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.16em] ${
                            outcome.outcome_status === 'improving'
                              ? 'bg-emerald-100 text-emerald-700'
                              : outcome.outcome_status === 'declining'
                                ? 'bg-rose-100 text-rose-700'
                                : outcome.outcome_status === 'no_evidence'
                                  ? 'bg-amber-100 text-amber-700'
                                  : 'bg-slate-200 text-slate-700'
                          }`}>
                            {outcome.outcome_status.replace('_', ' ')}
                          </span>
                        </div>
                        <p className="mt-3 text-xs leading-6 text-slate-600">{outcome.notes}</p>
                        <div className="mt-3 flex flex-wrap gap-3 text-[11px] font-medium text-slate-500">
                          <span>Net delta {Number(outcome.net_mastery_delta || 0).toFixed(2)}</span>
                          <span>{outcome.evidence_event_count} evidence event{outcome.evidence_event_count === 1 ? '' : 's'}</span>
                        </div>
                        {outcome.status === 'open' ? (
                          <div className="mt-4 flex flex-wrap items-center gap-3">
                            <button
                              type="button"
                              onClick={() => updateInterventionStatus(outcome, 'resolved')}
                              className="rounded-xl bg-emerald-600 px-4 py-2 text-xs font-black uppercase tracking-[0.16em] text-white transition hover:bg-emerald-500"
                            >
                              Resolve
                            </button>
                            <button
                              type="button"
                              onClick={() => updateInterventionStatus(outcome, 'dismissed')}
                              className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-black uppercase tracking-[0.16em] text-slate-700 transition hover:bg-slate-100"
                            >
                              Dismiss
                            </button>
                            {['resolved', 'dismissed'].map((statusKey) => {
                              const state = interventionUpdateStatus[`${outcome.intervention_id}-${statusKey}`];
                              if (!state) return null;
                              return (
                                <span
                                  key={statusKey}
                                  className={`text-xs font-semibold ${
                                    state.state === 'error'
                                      ? 'text-rose-600'
                                      : state.state === 'success'
                                        ? 'text-emerald-600'
                                        : 'text-slate-500'
                                  }`}
                                >
                                  {state.message}
                                </span>
                              );
                            })}
                          </div>
                        ) : (
                          <p className="mt-4 text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
                            Intervention {outcome.status}
                          </p>
                        )}
                      </div>
                    ))
                  ) : (
                    <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-6 text-center text-sm font-semibold text-slate-400">
                      {selectedStudent ? `No intervention outcomes are available for ${selectedStudent.student_name} yet.` : 'No intervention outcomes are available for this class yet.'}
                    </div>
                  )}
                </div>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <h2 className="flex items-center gap-2 text-lg font-bold text-slate-800">
                  <BookOpenCheck className="h-5 w-5 text-emerald-500" />
                  Ready To Push
                </h2>
                <p className="mt-1 text-xs text-slate-500">Concept clusters the class is strong enough to build on next.</p>
                <div className="mt-6 space-y-3">
                  {readyToPush.length === 0 ? (
                    <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-6 text-center text-sm font-semibold text-slate-400">
                      No mastered concept cluster is strong enough yet to push forward confidently.
                    </div>
                  ) : (
                    readyToPush.map((node) => (
                      <div key={node.concept_id} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                        <div className="flex items-center justify-between gap-4">
                          <div>
                            <p className="text-sm font-bold text-slate-900">{node.concept_label}</p>
                            <p className="mt-1 text-xs text-slate-500">{node.topic_title || 'Mapped concept node'}</p>
                          </div>
                          <span className="text-sm font-black text-emerald-600">{Math.round(Number(node.avg_score || 0) * 100)}%</span>
                        </div>
                        <p className="mt-3 text-xs leading-6 text-slate-600">{node.recommended_action}</p>
                      </div>
                    ))
                  )}
                </div>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <h2 className="flex items-center gap-2 text-lg font-bold text-slate-800">
                  <ShieldAlert className="h-5 w-5 text-rose-500" />
                  At-Risk Alerts
                </h2>
                <p className="mt-1 text-xs text-slate-500">Real inactivity, decline, and prerequisite alerts from backend analytics.</p>

                <div className="mt-6 space-y-3">
                  {alerts.length === 0 ? (
                    <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-6 text-center text-sm font-semibold text-slate-400">
                      No alerts are active for this class.
                    </div>
                  ) : (
                    alerts.map((alert, index) => (
                      <div key={`${alert.student_id}-${alert.alert_type}-${index}`} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                        <div className="flex items-center justify-between gap-3">
                          <span className={`rounded-full px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.18em] ${
                            alert.severity === 'high'
                              ? 'bg-rose-100 text-rose-700'
                              : alert.severity === 'medium'
                                ? 'bg-amber-100 text-amber-700'
                                : 'bg-slate-200 text-slate-700'
                          }`}>
                            {alert.alert_type.replace('_', ' ')}
                          </span>
                          <span className="text-[11px] font-semibold text-slate-400">Student {String(alert.student_id).slice(0, 8)}</span>
                        </div>
                        <p className="mt-3 text-sm leading-6 text-slate-700">{alert.message}</p>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </section>
          </div>
        </>
      )}

      <TeacherStudentFocusDrawer
        isOpen={Boolean(selectedStudent)}
        onClose={() => {
          setSelectedStudent(null);
          setStudentConceptTrend(null);
        }}
        student={selectedStudent}
        conceptLabel={conceptStudents?.concept_label || humanizeConceptId(selectedConceptId)}
        conceptTrend={studentConceptTrend}
        isLoadingTrend={isLoadingStudentConceptTrend}
        timeline={studentTimeline}
        isLoading={isLoadingStudentTimeline}
        onExport={openStudentFocusExport}
        isExporting={exportState.isOpen && exportState.isLoading && exportState.target === 'student' && Boolean(selectedStudent)}
        onOpenReport={openStudentReportPage}
      />
      <TeacherExportModal
        isOpen={exportState.isOpen}
        onClose={() => setExportState({ isOpen: false, isLoading: false, error: '', data: null, target: '' })}
        exportData={exportState.data}
        isLoading={exportState.isLoading}
        error={exportState.error}
      />
    </main>
  );
};

export default ConceptAnalyticsPage;

