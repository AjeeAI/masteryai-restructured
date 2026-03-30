const STORAGE_KEY = 'presentation_walkthrough_v1';
const EVENT_NAME = 'presentation-walkthrough-updated';

const readState = () => {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
};

const writeState = (state) => {
  if (typeof window === 'undefined') return;
  if (!state) {
    window.localStorage.removeItem(STORAGE_KEY);
  } else {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }
  window.dispatchEvent(new CustomEvent(EVENT_NAME, { detail: state }));
};

export const createPresentationWalkthroughSteps = ({ subject, recommendedTopicId, teacherClassId }) => {
  const encodedSubject = subject ? encodeURIComponent(subject) : '';
  const steps = [
    {
      id: 'dashboard',
      title: 'Student dashboard',
      description: 'Start with the live graph recommendation and intervention summary.',
      path: '/dashboard',
    },
  ];

  if (recommendedTopicId) {
    steps.push({
      id: 'lesson',
      title: 'Recommended lesson',
      description: 'Show the graph-first lesson cockpit and tutor actions.',
      path: `/lesson/${recommendedTopicId}`,
    });
  }

  steps.push(
    {
      id: 'graph-path',
      title: 'Graph explorer',
      description: 'Show ready nodes, blockers, and graph evidence.',
      path: encodedSubject ? `/graph-path?subject=${encodedSubject}` : '/graph-path',
    },
    {
      id: 'graph-briefing',
      title: 'Student briefing',
      description: 'Open the printable graph-backed student summary.',
      path: encodedSubject ? `/graph-briefing?subject=${encodedSubject}` : '/graph-briefing',
    },
  );

  if (teacherClassId) {
    steps.push({
      id: 'teacher-presentation',
      title: 'Teacher presentation',
      description: 'Switch to the class graph, queue, and outcome story.',
      path: `/teacher/presentation/${teacherClassId}`,
    });
  }

  return steps;
};

export const startPresentationWalkthrough = ({ subject, recommendedTopicId, teacherClassId }) => {
  const steps = createPresentationWalkthroughSteps({ subject, recommendedTopicId, teacherClassId });
  const state = {
    active: true,
    currentStepIndex: 0,
    steps,
    startedAt: new Date().toISOString(),
  };
  writeState(state);
  return state;
};

export const readPresentationWalkthrough = () => readState();

export const stopPresentationWalkthrough = () => {
  writeState(null);
};

export const advancePresentationWalkthrough = () => {
  const current = readState();
  if (!current?.active || !Array.isArray(current.steps) || !current.steps.length) {
    return null;
  }
  const nextIndex = Math.min(current.currentStepIndex + 1, current.steps.length - 1);
  const nextState = {
    ...current,
    currentStepIndex: nextIndex,
  };
  writeState(nextState);
  return nextState;
};

export const syncPresentationWalkthroughStep = (path) => {
  const current = readState();
  if (!current?.active || !Array.isArray(current.steps)) {
    return null;
  }
  const nextIndex = current.steps.findIndex((step) => step.path === path);
  if (nextIndex < 0 || nextIndex === current.currentStepIndex) {
    return current;
  }
  const nextState = {
    ...current,
    currentStepIndex: nextIndex,
  };
  writeState(nextState);
  return nextState;
};

export const subscribePresentationWalkthrough = (callback) => {
  if (typeof window === 'undefined') return () => {};
  const handler = (event) => callback(event.detail ?? readState());
  window.addEventListener(EVENT_NAME, handler);
  return () => window.removeEventListener(EVENT_NAME, handler);
};
