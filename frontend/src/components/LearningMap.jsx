import React, { useState } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  Brain,
  CheckCircle2,
  GitBranch,
  Lock,
  PlayCircle,
  Route,
  Sparkles,
  Target,
} from 'lucide-react';

const safeArray = (value) => (Array.isArray(value) ? value : []);

const statusStyles = {
  mastered: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  current: 'border-indigo-200 bg-indigo-50 text-indigo-700',
  ready: 'border-sky-200 bg-sky-50 text-sky-700',
  locked: 'border-slate-200 bg-slate-50 text-slate-500',
  unmapped: 'border-amber-200 bg-amber-50 text-amber-800',
};

const statusIcon = {
  mastered: CheckCircle2,
  current: Brain,
  ready: Sparkles,
  locked: Lock,
  unmapped: AlertTriangle,
};

const statusLabels = {
  mastered: 'Mastered',
  current: 'Current',
  ready: 'Ready',
  locked: 'Locked',
  unmapped: 'Needs mapping',
};

const sequenceLabel = (node, isRecommended) => {
  if (node.status === 'locked' && isRecommended) return 'Repair first';
  if (node.status === 'unmapped' && isRecommended) return 'Map first';
  if (node.status === 'ready' && isRecommended) return 'Next up';
  return statusLabels[node.status] || 'Pending';
};

const sequencePriority = (node, isRecommended) => {
  if (node.status === 'current') return 0;
  if (node.status === 'ready' && isRecommended) return 1;
  if (node.status === 'ready') return 2;
  if (node.status === 'mastered') return 3;
  if (node.status === 'locked' && isRecommended) return 4;
  if (node.status === 'locked') return 5;
  if (node.status === 'unmapped' && isRecommended) return 6;
  if (node.status === 'unmapped') return 7;
  return 8;
};

function MapNode({ node, isLast, isRecommended, isSelected, onSelectNode }) {
  const Icon = statusIcon[node.status] || Brain;
  const style = statusStyles[node.status] || statusStyles.locked;
  const badgeLabel = sequenceLabel(node, isRecommended);

  return (
    <div className="relative flex w-[72vw] min-w-0 shrink-0 snap-start flex-col items-center md:w-[230px] lg:w-[255px]">
      {!isLast && <div className="absolute left-1/2 top-5 hidden h-1 w-full bg-gradient-to-r from-indigo-200 via-slate-200 to-slate-200 md:block" />}
      <div className={`relative z-10 flex h-11 w-11 items-center justify-center rounded-full border-4 bg-white ${
        node.status === 'current'
          ? 'border-indigo-600 text-indigo-600 shadow-[0_0_0_6px_rgba(99,102,241,0.10)]'
          : node.status === 'mastered'
            ? 'border-emerald-500 text-emerald-600'
            : node.status === 'ready'
              ? 'border-sky-500 text-sky-600'
              : node.status === 'unmapped'
                ? 'border-amber-400 text-amber-600'
                : 'border-slate-200 text-slate-400'
      }`}>
        <Icon className="h-4.5 w-4.5" />
      </div>
      <button
        type="button"
        onClick={() => onSelectNode(node)}
        className={`mt-3 w-full rounded-2xl border px-4 py-3.5 text-left shadow-sm transition ${style} ${
          isRecommended ? 'ring-2 ring-indigo-200 ring-offset-2' : ''
        } ${isSelected ? 'ring-2 ring-slate-900/10 ring-offset-2' : ''}`}
      >
        <div className="flex items-start justify-between gap-3">
          <h4 className="line-clamp-2 text-[15px] font-black leading-tight">{node.title}</h4>
          <span className="rounded-full bg-white/75 px-2 py-1 text-[10px] font-black uppercase tracking-[0.14em]">
            {badgeLabel}
          </span>
        </div>
        <p className="mt-2 line-clamp-3 text-sm leading-6 opacity-90">{node.details || 'Graph state unavailable.'}</p>
        <div className="mt-3 flex items-center justify-between text-[11px] font-bold uppercase tracking-[0.12em]">
          <span>{Math.round((node.mastery_score || 0) * 100)}% mastery</span>
          {isSelected ? <Target className="h-4 w-4" /> : <PlayCircle className="h-4 w-4" />}
        </div>
      </button>
    </div>
  );
}

function MobileNodeCard({ node, isRecommended, isSelected, onSelectNode, isLast }) {
  const Icon = statusIcon[node.status] || Brain;
  const style = statusStyles[node.status] || statusStyles.locked;
  const badgeLabel = sequenceLabel(node, isRecommended);

  return (
    <button
      type="button"
      onClick={() => onSelectNode(node)}
      className={`relative w-full rounded-2xl border px-4 py-4 text-left shadow-sm transition ${style} ${
        isRecommended ? 'ring-2 ring-indigo-200 ring-offset-2' : ''
      } ${isSelected ? 'ring-2 ring-slate-900/10 ring-offset-2' : ''}`}
    >
      {!isLast && <div className="absolute left-[1.8rem] top-full h-5 w-px bg-slate-200" />}
      <div className="flex items-start gap-3">
        <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border bg-white ${
          node.status === 'current'
            ? 'border-indigo-300 text-indigo-600'
            : node.status === 'mastered'
              ? 'border-emerald-300 text-emerald-600'
              : node.status === 'ready'
                ? 'border-sky-300 text-sky-600'
                : node.status === 'unmapped'
                  ? 'border-amber-300 text-amber-600'
                  : 'border-slate-200 text-slate-400'
        }`}>
          <Icon className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="text-sm font-black leading-tight">{node.title}</h4>
            <span className="rounded-full bg-white/80 px-2 py-1 text-[10px] font-black uppercase tracking-[0.14em]">
              {badgeLabel}
            </span>
          </div>
          <p className="mt-2 text-xs leading-6 opacity-90">{node.details || 'Graph state unavailable.'}</p>
          <div className="mt-3 flex items-center justify-between text-[11px] font-bold uppercase tracking-[0.12em]">
            <span>{Math.round((node.mastery_score || 0) * 100)}% mastery</span>
            <span>{isSelected ? 'Inspecting' : 'Inspect'}</span>
          </div>
        </div>
      </div>
    </button>
  );
}

export default function LearningMap({ classLevel = 'SSS 2', subject = 'Mathematics', mapData = {}, onSelectTopic = null }) {
  const nodes = safeArray(mapData?.nodes);
  const edges = safeArray(mapData?.edges);
  const nextStep = mapData?.next_step || null;
  const relationCount = edges.length;
  const scopeWarning = nextStep?.scope_warning || null;
  const unmappedTopics = safeArray(nextStep?.unmapped_topic_titles);
  const [selectedNodeId, setSelectedNodeId] = useState(null);

  const orderedNodes = nodes
    .map((node, index) => ({ ...node, __index: index }))
    .sort((left, right) => {
      const leftRecommended = Boolean(nextStep?.recommended_topic_id && nextStep.recommended_topic_id === left.topic_id);
      const rightRecommended = Boolean(nextStep?.recommended_topic_id && nextStep.recommended_topic_id === right.topic_id);
      const priorityDelta = sequencePriority(left, leftRecommended) - sequencePriority(right, rightRecommended);
      if (priorityDelta !== 0) return priorityDelta;
      return left.__index - right.__index;
    });

  const preferredNode =
    orderedNodes.find((node) => node.status === 'current')
    || orderedNodes.find((node) => node.status === 'ready' && nextStep?.recommended_topic_id && nextStep.recommended_topic_id === node.topic_id)
    || orderedNodes.find((node) => node.status === 'ready')
    || orderedNodes.find((node) => node.status === 'mastered')
    || orderedNodes.find((node) => nextStep?.recommended_topic_id && nextStep.recommended_topic_id === node.topic_id)
    || orderedNodes[0]
    || null;

  const activeNodeId = orderedNodes.some((node) => (node.topic_id || node.concept_id) === selectedNodeId)
    ? selectedNodeId
    : (preferredNode?.topic_id || preferredNode?.concept_id || null);

  const selectedNode = orderedNodes.find((node) => (node.topic_id || node.concept_id) === activeNodeId) || null;

  const selectedGraphMeta = selectedNode
    ? {
        incoming: edges.filter((edge) => edge.target_id === (selectedNode.concept_id || selectedNode.topic_id)),
        outgoing: edges.filter((edge) => edge.source_id === (selectedNode.concept_id || selectedNode.topic_id)),
        isRecommended: Boolean(nextStep?.recommended_topic_id && nextStep.recommended_topic_id === selectedNode.topic_id),
      }
    : null;

  const nextStepNode = orderedNodes.find((node) => nextStep?.recommended_topic_id && nextStep.recommended_topic_id === node.topic_id) || null;
  const recommendationLabel = selectedGraphMeta?.isRecommended && selectedNode
    ? sequenceLabel(selectedNode, true)
    : 'Recommended';
  const recommendationTone = nextStepNode?.status === 'locked' || nextStepNode?.status === 'unmapped'
    ? 'border-amber-200 bg-amber-50 text-amber-900'
    : 'border-emerald-200 bg-emerald-50 text-emerald-900';
  const nextStepLabel = nextStepNode
    ? sequenceLabel(nextStepNode, true)
    : 'Recommended next';

  return (
    <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white p-5 shadow-sm md:p-6">
      <div className="mb-5 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em] text-indigo-700">
            <GitBranch className="h-3.5 w-3.5" />
            Graph-first path
          </div>
          <h2 className="text-lg font-black text-slate-900 sm:text-xl">Learning map</h2>
          <p className="mt-1 text-sm leading-6 text-slate-500">
            {classLevel} {subject} - {relationCount} prerequisite link{relationCount === 1 ? '' : 's'}
          </p>
          <p className="mt-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
            Current and ready lessons come first. Blocked lessons follow after.
          </p>
        </div>
        {nextStep && (
          <div className={`rounded-2xl border px-4 py-3 text-sm ${recommendationTone}`}>
            <div className="text-[10px] font-black uppercase tracking-[0.18em]">{nextStepLabel}</div>
            <div className="mt-1 font-bold">{nextStep.recommended_topic_title || nextStep.recommended_concept_label || 'Next lesson unavailable'}</div>
          </div>
        )}
      </div>

      <div className="mb-5 space-y-3 lg:hidden">
        {orderedNodes.map((node, index) => (
          <MobileNodeCard
            key={node.topic_id || node.concept_id || index}
            node={node}
            isLast={index === orderedNodes.length - 1}
            isRecommended={Boolean(nextStep?.recommended_topic_id && nextStep.recommended_topic_id === node.topic_id)}
            isSelected={Boolean(selectedNode && (selectedNode.topic_id || selectedNode.concept_id) === (node.topic_id || node.concept_id))}
            onSelectNode={(nextNode) => setSelectedNodeId(nextNode.topic_id || nextNode.concept_id)}
          />
        ))}
        {orderedNodes.length === 0 && (
          <div className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-400">
            Learning map unavailable for this scope.
          </div>
        )}
      </div>

      <div className="mb-5 hidden snap-x gap-4 overflow-x-auto pb-4 lg:flex">
        {orderedNodes.map((node, index) => (
          <MapNode
            key={node.topic_id || node.concept_id || index}
            node={node}
            isLast={index === orderedNodes.length - 1}
            isRecommended={Boolean(nextStep?.recommended_topic_id && nextStep.recommended_topic_id === node.topic_id)}
            isSelected={Boolean(selectedNode && (selectedNode.topic_id || selectedNode.concept_id) === (node.topic_id || node.concept_id))}
            onSelectNode={(nextNode) => setSelectedNodeId(nextNode.topic_id || nextNode.concept_id)}
          />
        ))}
        {orderedNodes.length === 0 && (
          <div className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-400">
            Learning map unavailable for this scope.
          </div>
        )}
      </div>

      {nextStep && (
        <div className="grid gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div>
            <div className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Recommendation reason</div>
            <p className="mt-2 text-sm leading-6 text-slate-700">{nextStep.reason}</p>
            {nextStep.recommended_topic_id && typeof onSelectTopic === 'function' && (
              <button
                type="button"
                onClick={() => onSelectTopic(nextStep.recommended_topic_id)}
                className="mt-3 inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-xs font-black uppercase tracking-[0.14em] text-white hover:bg-indigo-700"
              >
                Open lesson
                <PlayCircle className="h-4 w-4" />
              </button>
            )}
          </div>
          <div>
            <div className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Blocking prerequisites</div>
            <p className="mt-2 text-sm leading-6 text-slate-700">
              {safeArray(nextStep.prereq_gap_labels).length ? nextStep.prereq_gap_labels.join(', ') : 'No active prerequisite gap.'}
            </p>
          </div>
        </div>
      )}

      {selectedNode && selectedGraphMeta && (
        <div className="mt-5 grid gap-4 rounded-2xl border border-slate-200 bg-slate-50 p-4 lg:grid-cols-[minmax(0,1.15fr)_minmax(280px,0.85fr)]">
          <div>
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <span className={`rounded-full px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.18em] ${statusStyles[selectedNode.status] || statusStyles.locked}`}>
                {sequenceLabel(selectedNode, false)}
              </span>
              {selectedGraphMeta.isRecommended && (
                <span className={`rounded-full px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.18em] ${
                  selectedNode.status === 'locked' || selectedNode.status === 'unmapped'
                    ? 'bg-amber-500 text-white'
                    : 'bg-indigo-600 text-white'
                }`}>
                  {recommendationLabel}
                </span>
              )}
            </div>
            <h3 className="text-lg font-black text-slate-900">{selectedNode.title}</h3>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              {selectedNode.details || 'This node is part of your graph-backed course path.'}
            </p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
                <div className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Concept</div>
                <p className="mt-2 text-sm font-semibold text-slate-800">{selectedNode.concept_label || 'Topic focus'}</p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
                <div className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Mastery</div>
                <p className="mt-2 text-sm font-semibold text-slate-800">{Math.round((selectedNode.mastery_score || 0) * 100)}%</p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
                <div className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Unlocks</div>
                <p className="mt-2 text-sm font-semibold text-slate-800">{selectedGraphMeta.outgoing.length} node(s)</p>
              </div>
            </div>
          </div>

          <div className="space-y-3">
            <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3">
              <div className="flex items-center gap-2 text-amber-700">
                <Route className="h-4 w-4" />
                <p className="text-[10px] font-black uppercase tracking-[0.18em]">What blocks this</p>
              </div>
              <p className="mt-2 text-sm font-semibold text-amber-900">
                {selectedGraphMeta.incoming.length ? `${selectedGraphMeta.incoming.length} prerequisite link(s)` : 'No blocking edge is visible right now.'}
              </p>
              {safeArray(nextStep?.prereq_gap_labels).length > 0 && (
                <p className="mt-2 text-xs leading-6 text-amber-800">{nextStep.prereq_gap_labels.join(', ')}</p>
              )}
            </div>
            <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3">
              <div className="flex items-center gap-2 text-emerald-700">
                <ArrowRight className="h-4 w-4" />
                <p className="text-[10px] font-black uppercase tracking-[0.18em]">What this unlocks</p>
              </div>
              <p className="mt-2 text-sm font-semibold text-emerald-900">
                {selectedGraphMeta.outgoing.length ? `${selectedGraphMeta.outgoing.length} downstream link(s)` : 'This is an end-point in the current graph slice.'}
              </p>
              {nextStep?.recommended_concept_label && (
                <p className="mt-2 text-xs leading-6 text-emerald-800">Next concept: {nextStep.recommended_concept_label}</p>
              )}
            </div>
            {selectedNode.topic_id && typeof onSelectTopic === 'function' && !['locked', 'unmapped'].includes(selectedNode.status) && (
              <button
                type="button"
                onClick={() => onSelectTopic(selectedNode.topic_id)}
                className="inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-indigo-600 px-4 py-3 text-sm font-black text-white hover:bg-indigo-700"
              >
                Open this lesson
                <PlayCircle className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>
      )}

      {(scopeWarning || unmappedTopics.length > 0) && (
        <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4 text-sm text-amber-900">
          <div className="text-[10px] font-black uppercase tracking-[0.18em] text-amber-700">Mapping status</div>
          <p className="mt-2 leading-6">
            {scopeWarning || 'Some topics are visible but still waiting for approved curriculum concept mapping.'}
          </p>
          {unmappedTopics.length > 0 && (
            <p className="mt-2 text-xs font-semibold text-amber-800">
              Pending topics: {unmappedTopics.join(', ')}
            </p>
          )}
        </div>
      )}
    </section>
  );
}
