import React, { useMemo, useState } from 'react';
import { ArrowRight, GitBranch, Lock, Sparkles } from 'lucide-react';

const STATUS_ORDER = ['blocked', 'needs_attention', 'mastered', 'unassessed'];
const STATUS_LABELS = {
  blocked: 'Blocked',
  needs_attention: 'Needs Attention',
  mastered: 'Mastered',
  unassessed: 'Unassessed',
};
const STATUS_STYLES = {
  blocked: {
    column: 'bg-amber-50 border-amber-200',
    pill: 'bg-amber-100 text-amber-800',
    card: 'border-amber-300 bg-white shadow-[0_0_0_1px_rgba(245,158,11,0.08)]',
    edge: '#f59e0b',
  },
  needs_attention: {
    column: 'bg-indigo-50 border-indigo-200',
    pill: 'bg-indigo-100 text-indigo-800',
    card: 'border-indigo-300 bg-white shadow-[0_0_0_1px_rgba(99,102,241,0.08)]',
    edge: '#6366f1',
  },
  mastered: {
    column: 'bg-emerald-50 border-emerald-200',
    pill: 'bg-emerald-100 text-emerald-800',
    card: 'border-emerald-300 bg-white shadow-[0_0_0_1px_rgba(16,185,129,0.08)]',
    edge: '#10b981',
  },
  unassessed: {
    column: 'bg-slate-50 border-slate-200',
    pill: 'bg-slate-200 text-slate-700',
    card: 'border-slate-300 bg-white shadow-[0_0_0_1px_rgba(148,163,184,0.08)]',
    edge: '#94a3b8',
  },
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

const GRAPH_LAYOUT = {
  cardWidth: 224,
  cardHeight: 112,
  columnGap: 56,
  rowGap: 28,
  paddingX: 28,
  paddingY: 28,
};

const percent = (value) => `${Math.round(Number(value || 0) * 100)}%`;

const TeacherClassGraph = ({ graphSummary, selectedConceptId = '', onSelectNode }) => {
  const nodes = useMemo(() => (Array.isArray(graphSummary?.nodes) ? graphSummary.nodes : []), [graphSummary]);
  const edges = useMemo(() => (Array.isArray(graphSummary?.edges) ? graphSummary.edges : []), [graphSummary]);
  const [localSelectedConceptId, setLocalSelectedConceptId] = useState('');

  const grouped = useMemo(() => {
    const map = new Map(STATUS_ORDER.map((status) => [status, []]));
    nodes.forEach((node) => {
      const bucket = map.get(node.status) || map.get('unassessed');
      bucket.push(node);
    });
    STATUS_ORDER.forEach((status) => {
      const bucket = map.get(status) || [];
      bucket.sort((left, right) => {
        if (status === 'mastered') return Number(right.avg_score || 0) - Number(left.avg_score || 0);
        if (status === 'unassessed') {
          const leftLabel = left.concept_label || humanizeConceptId(left.concept_id);
          const rightLabel = right.concept_label || humanizeConceptId(right.concept_id);
          return leftLabel.localeCompare(rightLabel);
        }
        return Number(left.avg_score || 0) - Number(right.avg_score || 0);
      });
    });
    return map;
  }, [nodes]);

  const positions = useMemo(() => {
    const map = new Map();
    STATUS_ORDER.forEach((status, columnIndex) => {
      const bucket = grouped.get(status) || [];
      bucket.forEach((node, rowIndex) => {
        map.set(node.concept_id, {
          x: GRAPH_LAYOUT.paddingX + columnIndex * (GRAPH_LAYOUT.cardWidth + GRAPH_LAYOUT.columnGap),
          y: GRAPH_LAYOUT.paddingY + rowIndex * (GRAPH_LAYOUT.cardHeight + GRAPH_LAYOUT.rowGap),
        });
      });
    });
    return map;
  }, [grouped]);

  const graphWidth =
    GRAPH_LAYOUT.paddingX * 2 + STATUS_ORDER.length * GRAPH_LAYOUT.cardWidth + (STATUS_ORDER.length - 1) * GRAPH_LAYOUT.columnGap;
  const graphHeight =
    GRAPH_LAYOUT.paddingY * 2 +
    Math.max(1, ...STATUS_ORDER.map((status) => (grouped.get(status) || []).length)) * GRAPH_LAYOUT.cardHeight +
    Math.max(0, Math.max(...STATUS_ORDER.map((status) => (grouped.get(status) || []).length)) - 1) * GRAPH_LAYOUT.rowGap;

  const activeConceptId = selectedConceptId || localSelectedConceptId;
  const selectedNode =
    nodes.find((node) => node.concept_id === activeConceptId) ||
    nodes.find((node) => node.concept_label === graphSummary?.graph_signal?.focus_concept_label) ||
    nodes[0] ||
    null;

  if (nodes.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-8 text-center text-sm font-semibold text-slate-400">
        No mapped concept graph is available for this class yet.
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap gap-2">
        {STATUS_ORDER.map((status) => (
          <div
            key={status}
            className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em] ${STATUS_STYLES[status].pill}`}
          >
            {STATUS_LABELS[status]}
            <span className="rounded-full bg-white/80 px-2 py-0.5 text-[10px] text-slate-700">
              {(grouped.get(status) || []).length}
            </span>
          </div>
        ))}
      </div>

      <div className="overflow-x-auto rounded-3xl border border-slate-200 bg-slate-950/95 p-4 shadow-inner">
        <div className="relative mx-auto" style={{ width: graphWidth, minHeight: graphHeight }}>
          <svg className="absolute inset-0 h-full w-full" width={graphWidth} height={graphHeight}>
            {edges.map((edge) => {
              const source = positions.get(edge.source_concept_id);
              const target = positions.get(edge.target_concept_id);
              if (!source || !target) return null;
              const startX = source.x + GRAPH_LAYOUT.cardWidth;
              const startY = source.y + GRAPH_LAYOUT.cardHeight / 2;
              const endX = target.x;
              const endY = target.y + GRAPH_LAYOUT.cardHeight / 2;
              const midX = startX + (endX - startX) / 2;
              const color = edge.status === 'blocked' ? '#f59e0b' : '#8b5cf6';
              return (
                <path
                  key={`${edge.source_concept_id}-${edge.target_concept_id}`}
                  d={`M ${startX} ${startY} C ${midX} ${startY}, ${midX} ${endY}, ${endX} ${endY}`}
                  fill="none"
                  stroke={color}
                  strokeWidth="3"
                  strokeLinecap="round"
                  strokeDasharray={edge.status === 'blocked' ? '7 7' : '0'}
                  opacity="0.8"
                />
              );
            })}
          </svg>

          {STATUS_ORDER.map((status, columnIndex) => (
            <div
              key={status}
              className={`absolute rounded-3xl border px-4 py-3 ${STATUS_STYLES[status].column}`}
              style={{
                left: GRAPH_LAYOUT.paddingX + columnIndex * (GRAPH_LAYOUT.cardWidth + GRAPH_LAYOUT.columnGap) - 12,
                top: 0,
                width: GRAPH_LAYOUT.cardWidth + 24,
              }}
            >
              <div className="flex items-center justify-between text-[10px] font-black uppercase tracking-[0.18em] text-slate-700">
                <span>{STATUS_LABELS[status]}</span>
                <span>{(grouped.get(status) || []).length}</span>
              </div>
            </div>
          ))}

          {nodes.map((node) => {
            const position = positions.get(node.concept_id);
            if (!position) return null;
            const isSelected = selectedNode?.concept_id === node.concept_id;
            const styles = STATUS_STYLES[node.status] || STATUS_STYLES.unassessed;
            return (
              <button
                key={node.concept_id}
                type="button"
                onClick={() => {
                  setLocalSelectedConceptId(node.concept_id);
                  onSelectNode?.(node);
                }}
                className={`absolute rounded-2xl border p-4 text-left transition ${
                  styles.card
                } ${isSelected ? 'ring-2 ring-white/90 scale-[1.02]' : 'hover:-translate-y-0.5 hover:shadow-xl'}`}
                style={{
                  left: position.x,
                  top: position.y + 28,
                  width: GRAPH_LAYOUT.cardWidth,
                  minHeight: GRAPH_LAYOUT.cardHeight,
                }}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.16em] ${styles.pill}`}>
                      {node.status === 'blocked' ? <Lock className="h-3 w-3" /> : <GitBranch className="h-3 w-3" />}
                      {STATUS_LABELS[node.status]}
                    </div>
                    <h3 className="mt-3 text-sm font-black text-slate-900">{node.concept_label || humanizeConceptId(node.concept_id)}</h3>
                    <p className="mt-1 text-[11px] font-semibold text-slate-500">{node.topic_title || 'Mapped concept node'}</p>
                  </div>
                  <span className="rounded-full bg-slate-900 px-2 py-1 text-[11px] font-black text-white">
                    {percent(node.avg_score)}
                  </span>
                </div>
                <p className="mt-3 line-clamp-2 text-[11px] leading-5 text-slate-600">{node.recommended_action}</p>
              </button>
            );
          })}
        </div>
      </div>

      {selectedNode ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-3xl">
              <div className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em] text-slate-600">
                <Sparkles className="h-3.5 w-3.5" />
                Selected graph node
              </div>
              <h3 className="mt-3 text-xl font-black text-slate-900">{selectedNode.concept_label}</h3>
              <p className="mt-1 text-sm font-medium text-slate-500">{selectedNode.topic_title || 'Mapped concept node'}</p>
              <p className="mt-4 text-sm leading-7 text-slate-600">{selectedNode.recommended_action}</p>
            </div>
            <div className="grid min-w-[260px] grid-cols-2 gap-3">
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Class mastery</p>
                <p className="mt-2 text-2xl font-black text-slate-900">{percent(selectedNode.avg_score)}</p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Students tracked</p>
                <p className="mt-2 text-2xl font-black text-slate-900">{selectedNode.student_count}</p>
              </div>
            </div>
          </div>

          <div className="mt-5 grid gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Prerequisites</p>
              {selectedNode.prerequisite_labels?.length ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  {selectedNode.prerequisite_labels.map((label) => (
                    <span key={label} className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate-700 shadow-sm">
                      {label}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="mt-3 text-sm text-slate-500">This node is foundational in the current scope.</p>
              )}
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Blocking prerequisites</p>
              {selectedNode.blocking_prerequisite_labels?.length ? (
                <div className="mt-3 space-y-2">
                  {selectedNode.blocking_prerequisite_labels.map((label) => (
                    <div key={label} className="flex items-center gap-2 text-sm font-semibold text-amber-700">
                      <ArrowRight className="h-4 w-4" />
                      {label}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="mt-3 text-sm text-slate-500">No blocking prerequisite is currently holding this node back.</p>
              )}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
};

export default TeacherClassGraph;
