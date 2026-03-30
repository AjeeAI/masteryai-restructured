import React, { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { ArrowRight, Brain, GitBranch, PlayCircle, Route, ShieldAlert, Sparkles } from 'lucide-react';

const ROLE_X = {
  prerequisite: 136,
  current: 360,
  downstream: 584,
};

const ROLE_LABEL = {
  prerequisite: 'Build First',
  current: 'You Are Here',
  downstream: 'Unlocks Next',
};

const MASTERY_TONE = {
  demonstrated: {
    node: '#10b981',
    halo: 'rgba(16, 185, 129, 0.18)',
    fill: '#ecfdf5',
    text: '#065f46',
  },
  needs_review: {
    node: '#f59e0b',
    halo: 'rgba(245, 158, 11, 0.18)',
    fill: '#fffbeb',
    text: '#92400e',
  },
  unassessed: {
    node: '#64748b',
    halo: 'rgba(100, 116, 139, 0.14)',
    fill: '#f8fafc',
    text: '#334155',
  },
};

const roleOrder = ['prerequisite', 'current', 'downstream'];

const safeArray = (value) => (Array.isArray(value) ? value : []);

function wrapLabel(label) {
  const words = String(label || '').split(/\s+/).filter(Boolean);
  const lines = [];
  let current = '';

  for (const word of words) {
    const next = current ? `${current} ${word}` : word;
    if (next.length > 18 && current) {
      lines.push(current);
      current = word;
    } else {
      current = next;
    }
  }

  if (current) lines.push(current);
  return lines.slice(0, 3);
}

function buildLayout(graphContext) {
  const grouped = {
    prerequisite: safeArray(graphContext?.prerequisite_concepts),
    current: safeArray(graphContext?.current_concepts),
    downstream: safeArray(graphContext?.downstream_concepts),
  };

  const positions = {};
  const nodes = [];

  roleOrder.forEach((role) => {
    const column = grouped[role];
    const total = Math.max(column.length, 1);
    const startY = total === 1 ? 180 : Math.max(118, 210 - ((total - 1) * 84) / 2);

    column.forEach((node, index) => {
      const x = ROLE_X[role];
      const y = startY + (index * 84);
      positions[node.concept_id] = { x, y, role };
      nodes.push({ ...node, x, y });
    });
  });

  const renderedEdges = safeArray(graphContext?.graph_edges)
    .filter((edge) => positions[edge.source_concept_id] && positions[edge.target_concept_id])
    .map((edge) => {
      const from = positions[edge.source_concept_id];
      const to = positions[edge.target_concept_id];
      const curveOffset = Math.max(46, Math.abs(to.x - from.x) * 0.32);
      return {
        ...edge,
        d: `M ${from.x + 48} ${from.y} C ${from.x + curveOffset} ${from.y}, ${to.x - curveOffset} ${to.y}, ${to.x - 48} ${to.y}`,
      };
    });

  return { grouped, nodes, renderedEdges };
}

export default function LessonKnowledgeGraph({
  graphContext,
  nextUnlock,
  whyTopicDetail = null,
  onOpenTopic = null,
  onExplainConcept = null,
  onBridgeConcept = null,
  onDrillConcept = null,
  onSelectConcept = null,
}) {
  const graphUnavailable = !graphContext || graphContext.status === 'unavailable';
  const { grouped, nodes, renderedEdges } = useMemo(() => buildLayout(graphContext), [graphContext]);
  const [selectedConceptId, setSelectedConceptId] = useState(null);
  const preferredNode = nodes.find((node) => node.role === 'current') || nodes[0] || null;
  const selectedNode = nodes.find((node) => node.concept_id === selectedConceptId) || preferredNode || null;
  const whyUnavailable = whyTopicDetail?.status === 'unavailable';
  const selectedAction = useMemo(() => {
    if (!selectedNode) return null;
    if (selectedNode.recommended_topic_id) {
      return {
        topicId: selectedNode.recommended_topic_id,
        label: selectedNode.recommended_action_label || 'Open related lesson',
      };
    }
    if (selectedNode.topic_id) {
      return {
        topicId: selectedNode.topic_id,
        label: selectedNode.role === 'downstream' ? 'Open unlock lesson' : 'Open related lesson',
      };
    }
    return null;
  }, [selectedNode]);

  useEffect(() => {
    if (typeof onSelectConcept === 'function') {
      onSelectConcept(selectedNode || null);
    }
  }, [onSelectConcept, selectedNode]);

  if (graphUnavailable) {
    return (
      <div className="rounded-[2rem] border border-amber-200 bg-amber-50 p-5 text-sm text-amber-800">
        <div className="mb-2 flex items-center gap-2 text-amber-700">
          <ShieldAlert size={18} />
          <p className="text-xs font-black uppercase tracking-[0.2em]">Graph context unavailable</p>
        </div>
        <p className="text-xs leading-6">
          {graphContext?.unavailable_reason || 'No approved concept mappings are available for this topic yet.'}
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-[2rem] border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <GitBranch className="text-indigo-600" size={18} />
          <div>
            <h2 className="text-sm font-black uppercase tracking-[0.2em] text-slate-600">Knowledge Graph Rail</h2>
            <p className="text-xs text-slate-500">Live prerequisite flow around this lesson</p>
          </div>
        </div>
        <div className="rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-[10px] font-black uppercase tracking-[0.2em] text-indigo-700">
          Neo4j-backed
        </div>
      </div>

      <div className="overflow-hidden rounded-[1.5rem] border border-slate-100 bg-[linear-gradient(180deg,#f8fbff_0%,#ffffff_100%)] px-3 py-4">
        <div className="space-y-3 lg:hidden">
          {roleOrder.map((role) => {
            const columnNodes = grouped[role];
            return (
              <div key={role} className="rounded-2xl border border-slate-200 bg-white p-3">
                <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">{ROLE_LABEL[role]}</p>
                <div className="mt-3 space-y-2">
                  {columnNodes.length ? columnNodes.map((node) => {
                    const tone = MASTERY_TONE[node.mastery_state] || MASTERY_TONE.unassessed;
                    const isSelected = selectedNode?.concept_id === node.concept_id;
                    return (
                      <button
                        key={node.concept_id}
                        type="button"
                        onClick={() => setSelectedConceptId(node.concept_id)}
                        className={`w-full rounded-2xl border px-3 py-3 text-left transition ${
                          isSelected ? 'border-indigo-300 bg-indigo-50 shadow-sm' : 'border-slate-200 bg-slate-50'
                        }`}
                      >
                        <div className="flex items-start gap-3">
                          <div
                            className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border"
                            style={{ borderColor: tone.node, color: tone.text, backgroundColor: tone.fill }}
                          >
                            <Brain size={16} />
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="text-sm font-bold text-slate-900">{node.label}</p>
                              <span className="rounded-full border border-slate-200 bg-white px-2 py-1 text-[10px] font-black uppercase tracking-[0.14em] text-slate-500">
                                {node.is_unlocked ? 'Open' : 'Locked'}
                              </span>
                            </div>
                            <p className="mt-2 text-xs text-slate-500">{Math.round((node.mastery_score || 0) * 100)}% mastery</p>
                          </div>
                        </div>
                      </button>
                    );
                  }) : (
                    <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-3 py-3 text-xs text-slate-500">
                      No nodes in this slice yet.
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        <div className="hidden lg:block">
          <div className="mb-3 grid grid-cols-3 gap-2 px-2 text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">
            {roleOrder.map((role) => (
              <div key={role} className="text-center">{ROLE_LABEL[role]}</div>
            ))}
          </div>

          <svg viewBox="0 0 720 360" className="h-[360px] w-full">
            <defs>
              <linearGradient id="graphEdge" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#94a3b8" stopOpacity="0.36" />
                <stop offset="50%" stopColor="#6366f1" stopOpacity="0.7" />
                <stop offset="100%" stopColor="#22c55e" stopOpacity="0.44" />
              </linearGradient>
            </defs>

            {renderedEdges.map((edge, index) => (
              <motion.path
                key={`${edge.source_concept_id}-${edge.target_concept_id}`}
                d={edge.d}
                fill="none"
                stroke="url(#graphEdge)"
                strokeWidth="3"
                strokeLinecap="round"
                initial={{ pathLength: 0, opacity: 0 }}
                animate={{ pathLength: 1, opacity: 1 }}
                transition={{ duration: 0.65, delay: index * 0.06 }}
              />
            ))}

            {nodes.map((node, index) => {
              const tone = MASTERY_TONE[node.mastery_state] || MASTERY_TONE.unassessed;
              const labelLines = wrapLabel(node.label);
              const isSelected = selectedNode?.concept_id === node.concept_id;
              return (
                <motion.g
                  key={node.concept_id}
                  initial={{ opacity: 0, scale: 0.92, y: 12 }}
                  animate={{ opacity: 1, scale: 1, y: 0 }}
                  transition={{ duration: 0.34, delay: index * 0.05 }}
                  onClick={() => setSelectedConceptId(node.concept_id)}
                  className="cursor-pointer"
                >
                  <motion.circle
                    cx={node.x}
                    cy={node.y}
                    r={node.role === 'current' ? 42 : 34}
                    fill={tone.halo}
                    animate={node.role === 'current' ? { scale: [1, 1.08, 1] } : { scale: 1 }}
                    transition={node.role === 'current' ? { repeat: Infinity, duration: 2.4, ease: 'easeInOut' } : undefined}
                    style={{ transformOrigin: `${node.x}px ${node.y}px` }}
                  />
                  <circle
                    cx={node.x}
                    cy={node.y}
                    r={node.role === 'current' ? 34 : 28}
                    fill={tone.fill}
                    stroke={tone.node}
                    strokeDasharray={!node.is_unlocked && node.role === 'downstream' ? '6 5' : undefined}
                    strokeWidth={isSelected ? '3.5' : '2.4'}
                  />
                  <text x={node.x} y={node.y - 5} textAnchor="middle" fontSize="11" fontWeight="800" fill={tone.text}>
                    {labelLines.map((line, lineIndex) => (
                      <tspan key={`${node.concept_id}-${lineIndex}`} x={node.x} dy={lineIndex === 0 ? 0 : 13}>{line}</tspan>
                    ))}
                  </text>
                  <text x={node.x} y={node.y + 34} textAnchor="middle" fontSize="10" fontWeight="700" fill="#475569">
                    {Math.round((node.mastery_score || 0) * 100)}% mastery
                  </text>
                </motion.g>
              );
            })}
          </svg>
        </div>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-[1fr_auto_1fr]">
        <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <p className="text-[10px] font-black uppercase tracking-[0.2em] text-amber-600">Weak prerequisite</p>
          <p className="mt-1 font-semibold">{grouped.prerequisite[0]?.label || 'No blocking prerequisite detected yet.'}</p>
        </div>
        <div className="flex items-center justify-center text-slate-300">
          <ArrowRight size={18} />
        </div>
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
          <p className="text-[10px] font-black uppercase tracking-[0.2em] text-emerald-600">Unlocked next</p>
          <p className="mt-1 font-semibold">{nextUnlock?.topic_title || nextUnlock?.concept_label || 'Stay with this concept cluster a bit longer.'}</p>
        </div>
      </div>

      {selectedNode && (
        <div className="mt-4 rounded-[1.5rem] border border-slate-200 bg-white p-4">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <div className="flex items-center gap-2 text-slate-700">
                <Brain className="h-4 w-4 text-indigo-600" />
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Selected graph node</p>
              </div>
              <h3 className="mt-3 text-lg font-black text-slate-900">{selectedNode.label}</h3>
              <p className="mt-2 text-sm leading-7 text-slate-600">
                {selectedNode.lock_reason
                  || selectedNode.detail
                  || (selectedNode.topic_title
                    ? `${selectedNode.role === 'prerequisite' ? 'Supports' : selectedNode.role === 'downstream' ? 'Unlocks through' : 'Anchors'} ${selectedNode.topic_title}.`
                    : 'This concept is part of the current graph slice.')}
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-[11px] font-bold uppercase tracking-[0.16em] text-slate-600">
                  {selectedNode.role}
                </span>
                <span className="rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-[11px] font-bold text-indigo-700">
                  {Math.round((selectedNode.mastery_score || 0) * 100)}% mastery
                </span>
                <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-[11px] font-bold text-slate-600">
                  {selectedNode.is_unlocked ? 'Unlocked' : 'Still locked'}
                </span>
                {!!selectedNode.mastery_gap && selectedNode.mastery_gap > 0 && (
                  <span className="rounded-full border border-rose-200 bg-rose-50 px-3 py-1 text-[11px] font-bold text-rose-700">
                    {Math.round(selectedNode.mastery_gap * 100)}% gap to unlock
                  </span>
                )}
                {!selectedNode.is_unlocked && safeArray(selectedNode.blocking_prerequisite_labels).length > 0 && (
                  <span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-[11px] font-bold text-amber-800">
                    Blocked by {selectedNode.blocking_prerequisite_labels[0]}
                  </span>
                )}
              </div>
              {(selectedNode.lock_reason || (!selectedNode.is_unlocked && safeArray(selectedNode.blocking_prerequisite_labels).length > 0)) && (
                <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                  <p className="text-[10px] font-black uppercase tracking-[0.18em] text-amber-700">Why locked</p>
                  <p className="mt-2 font-semibold">
                    {selectedNode.lock_reason || `${selectedNode.blocking_prerequisite_labels.join(', ')} still needs more mastery before this node opens.`}
                  </p>
                  {(selectedNode.recommended_action_reason || selectedNode.blocking_prerequisite_topic_title) && (
                    <p className="mt-2 text-xs leading-6 text-amber-800">
                      {selectedNode.recommended_action_reason
                        || `Best repair lesson: ${selectedNode.blocking_prerequisite_topic_title}`}
                    </p>
                  )}
                </div>
              )}
              {selectedNode.is_unlocked && selectedNode.recommended_action_reason && (
                <div className="mt-4 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
                  <p className="text-[10px] font-black uppercase tracking-[0.18em] text-emerald-700">Best next move</p>
                  <p className="mt-2 font-semibold">{selectedNode.recommended_action_reason}</p>
                </div>
              )}
            </div>
            {selectedAction && typeof onOpenTopic === 'function' && (
              <div className="flex flex-col gap-3 lg:items-end">
                <button
                  type="button"
                  onClick={() => onOpenTopic(selectedAction.topicId)}
                  className="inline-flex items-center justify-center gap-2 rounded-2xl bg-indigo-600 px-4 py-3 text-sm font-black text-white hover:bg-indigo-700"
                >
                  {selectedAction.label}
                  <PlayCircle className="h-4 w-4" />
                </button>
                <div className="flex flex-wrap justify-end gap-2">
                  {typeof onExplainConcept === 'function' && (
                    <button
                      type="button"
                      onClick={() => onExplainConcept(selectedNode)}
                      className="rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs font-black uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
                    >
                      Explain node
                    </button>
                  )}
                  {typeof onBridgeConcept === 'function' && (
                    <button
                      type="button"
                      onClick={() => onBridgeConcept(selectedNode)}
                      className="rounded-2xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-black uppercase tracking-[0.14em] text-amber-800 hover:bg-amber-100"
                    >
                      Bridge blocker
                    </button>
                  )}
                  {typeof onDrillConcept === 'function' && (
                    <button
                      type="button"
                      onClick={() => onDrillConcept(selectedNode)}
                      className="rounded-2xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-black uppercase tracking-[0.14em] text-emerald-800 hover:bg-emerald-100"
                    >
                      Drill node
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {whyTopicDetail && (
        <div className="mt-4 rounded-[1.5rem] border border-slate-200 bg-slate-50 p-4">
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1.3fr)_minmax(280px,0.7fr)]">
            <div>
              <div className="flex items-center gap-2 text-slate-700">
                <Route className="h-4 w-4 text-indigo-600" />
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Why this topic now</p>
              </div>
              <p className="mt-3 text-sm leading-7 text-slate-700">
                {whyUnavailable
                  ? (whyTopicDetail.unavailable_reason || 'Graph context is unavailable for this topic right now.')
                  : whyTopicDetail.explanation}
              </p>
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                <div className="rounded-2xl border border-white bg-white px-4 py-3">
                  <div className="flex items-center gap-2 text-amber-700">
                    <ShieldAlert className="h-4 w-4" />
                    <p className="text-[10px] font-black uppercase tracking-[0.18em]">Build from</p>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {whyUnavailable ? (
                      <span className="text-xs text-slate-500">Graph context unavailable.</span>
                    ) : safeArray(whyTopicDetail.prerequisite_labels).length > 0 ? (
                      whyTopicDetail.prerequisite_labels.map((label) => (
                        <span key={label} className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-[11px] font-bold text-amber-800">
                          {label}
                        </span>
                      ))
                    ) : (
                      <span className="text-xs text-slate-500">No blocking prerequisite in this slice.</span>
                    )}
                  </div>
                </div>
                <div className="rounded-2xl border border-white bg-white px-4 py-3">
                  <div className="flex items-center gap-2 text-emerald-700">
                    <Sparkles className="h-4 w-4" />
                    <p className="text-[10px] font-black uppercase tracking-[0.18em]">Unlock next</p>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {whyUnavailable ? (
                      <span className="text-xs text-slate-500">Graph context unavailable.</span>
                    ) : safeArray(whyTopicDetail.unlock_labels).length > 0 ? (
                      whyTopicDetail.unlock_labels.map((label) => (
                        <span key={label} className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-[11px] font-bold text-emerald-800">
                          {label}
                        </span>
                      ))
                    ) : (
                      <span className="text-xs text-slate-500">No downstream unlock is visible yet.</span>
                    )}
                  </div>
                </div>
              </div>
            </div>
            <div className="space-y-3">
              {whyTopicDetail.weakest_prerequisite_label && !whyUnavailable && (
                <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                  <p className="text-[10px] font-black uppercase tracking-[0.18em] text-amber-700">Weakest prerequisite</p>
                  <p className="mt-2 font-semibold">{whyTopicDetail.weakest_prerequisite_label}</p>
                </div>
              )}
              {whyTopicDetail.recommended_next && !whyUnavailable && (
                <div className="rounded-2xl border border-indigo-200 bg-indigo-50 px-4 py-3 text-sm text-indigo-900">
                  <p className="text-[10px] font-black uppercase tracking-[0.18em] text-indigo-600">Recommended next move</p>
                  <p className="mt-2 font-semibold">
                    {whyTopicDetail.recommended_next.topic_title || whyTopicDetail.recommended_next.concept_label || 'Continue the current lesson'}
                  </p>
                  <p className="mt-2 text-xs leading-6 text-indigo-800">{whyTopicDetail.recommended_next.reason}</p>
                </div>
              )}
              {whyUnavailable && (
                <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                  <p className="text-[10px] font-black uppercase tracking-[0.18em] text-amber-700">Graph data missing</p>
                  <p className="mt-2 text-xs leading-6 text-amber-800">
                    We could not load the graph slice for this topic yet. Once curriculum mapping completes, this panel will show prerequisites and unlocks.
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
