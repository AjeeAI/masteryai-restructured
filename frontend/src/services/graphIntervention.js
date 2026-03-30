const STORAGE_KEY = 'mastery_graph_interventions_v1';
const LATEST_KEY = 'mastery_graph_intervention_latest_v1';
const EVENT_NAME = 'mastery:graph-intervention-updated';
const TTL_MS = 30 * 60 * 1000;

const hasStorage = () => typeof window !== 'undefined' && typeof window.localStorage !== 'undefined';

const normalizeScopePart = (value) => String(value || '').trim().toLowerCase();

export const buildGraphInterventionScope = ({ studentId, subject, sssLevel, term }) => {
  const parts = [studentId, subject, sssLevel, term].map(normalizeScopePart);
  if (parts.some((part) => !part)) return '';
  return parts.join(':');
};

const writeStore = (store) => {
  if (!hasStorage()) return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
};

const pruneStore = (store) => {
  const now = Date.now();
  return Object.fromEntries(
    Object.entries(store || {}).filter(([, entry]) => (
      entry
      && entry.payload
      && typeof entry.expires_at === 'number'
      && entry.expires_at > now
    )),
  );
};

const readStore = () => {
  if (!hasStorage()) return {};
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : {};
    const pruned = pruneStore(parsed);
    if (JSON.stringify(parsed) !== JSON.stringify(pruned)) {
      writeStore(pruned);
    }
    return pruned;
  } catch (error) {
    console.warn('Graph intervention cache reset:', error);
    writeStore({});
    return {};
  }
};

export const readGraphIntervention = (scopeOrParts) => {
  const scope = typeof scopeOrParts === 'string' ? scopeOrParts : buildGraphInterventionScope(scopeOrParts || {});
  if (!scope) return null;
  const store = readStore();
  return store[scope]?.payload || null;
};

export const saveGraphIntervention = ({
  studentId,
  subject,
  sssLevel,
  term,
  payload,
}) => {
  const scope = buildGraphInterventionScope({ studentId, subject, sssLevel, term });
  if (!scope || !payload || !hasStorage()) return;

  const now = Date.now();
  const store = readStore();
  const nextStore = {
    ...store,
    [scope]: {
      updated_at: now,
      expires_at: now + TTL_MS,
      payload: {
        ...payload,
        updated_at: now,
      },
    },
  };

  writeStore(nextStore);
  window.localStorage.setItem(LATEST_KEY, JSON.stringify({
    scope,
    studentId: normalizeScopePart(studentId),
    subject: normalizeScopePart(subject),
    sssLevel: String(sssLevel || '').trim(),
    term: String(term || '').trim(),
    updated_at: now,
  }));
  window.dispatchEvent(new CustomEvent(EVENT_NAME, { detail: { scope } }));
};

export const readLatestGraphIntervention = (studentId) => {
  const normalizedStudentId = normalizeScopePart(studentId);
  if (!normalizedStudentId || !hasStorage()) return null;

  const store = readStore();
  try {
    const raw = window.localStorage.getItem(LATEST_KEY);
    if (raw) {
      const latest = JSON.parse(raw);
      if (latest?.studentId === normalizedStudentId) {
        const payload = store[latest.scope]?.payload || null;
        if (payload) {
          return {
            ...latest,
            payload,
          };
        }
      }
    }
  } catch (error) {
    console.warn('Latest graph intervention pointer reset:', error);
  }

  const fallback = Object.entries(store)
    .filter(([scope]) => scope.startsWith(`${normalizedStudentId}:`))
    .sort(([, left], [, right]) => (right.updated_at || 0) - (left.updated_at || 0))[0];

  if (!fallback) return null;

  const [scope, entry] = fallback;
  const [, subject, sssLevel, term] = scope.split(':');
  return {
    scope,
    studentId: normalizedStudentId,
    subject,
    sssLevel,
    term,
    updated_at: entry.updated_at || Date.now(),
    payload: entry.payload,
  };
};

export const subscribeGraphIntervention = (scopeOrParts, callback) => {
  const scope = typeof scopeOrParts === 'string' ? scopeOrParts : buildGraphInterventionScope(scopeOrParts || {});
  if (!scope || typeof window === 'undefined' || typeof callback !== 'function') {
    return () => {};
  }

  const emit = () => callback(readGraphIntervention(scope));

  const onCustom = (event) => {
    if (event?.detail?.scope === scope) emit();
  };

  const onStorage = (event) => {
    if (event?.key === STORAGE_KEY) emit();
  };

  window.addEventListener(EVENT_NAME, onCustom);
  window.addEventListener('storage', onStorage);

  return () => {
    window.removeEventListener(EVENT_NAME, onCustom);
    window.removeEventListener('storage', onStorage);
  };
};

export const applyGraphInterventionOverlay = (basePayload, intervention) => {
  if (!intervention) return basePayload;
  return {
    ...basePayload,
    next_step: intervention.next_step || basePayload?.next_step || null,
    recent_evidence: intervention.recent_evidence || basePayload?.recent_evidence || null,
    recommendation_story: intervention.recommendation_story || basePayload?.recommendation_story || null,
    evidence_summary: intervention.evidence_summary || basePayload?.evidence_summary || null,
  };
};
