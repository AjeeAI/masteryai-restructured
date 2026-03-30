const normalizeEnv = (value) => String(value || '').replace(/['"]/g, '').trim();

const browserHostname =
  typeof window !== 'undefined' ? String(window.location.hostname || '').toLowerCase() : '';

const isLocalBrowser =
  browserHostname === 'localhost' ||
  browserHostname === '127.0.0.1' ||
  browserHostname === '0.0.0.0';

export const API_URL =
  normalizeEnv(import.meta.env.VITE_API_URL) ||
  (isLocalBrowser
    ? 'http://127.0.0.1:8001/api/v1'
    : 'https://mastery-backend-7xe8.onrender.com/api/v1');

export const AI_CORE_URL =
  normalizeEnv(import.meta.env.VITE_AI_CORE_URL) ||
  (isLocalBrowser ? 'http://127.0.0.1:10001' : 'https://mastery-ai-core.onrender.com');

export const GOOGLE_CLIENT_ID = normalizeEnv(import.meta.env.VITE_GOOGLE_CLIENT_ID);
export const GOOGLE_AUTH_ENABLED = GOOGLE_CLIENT_ID.length > 0;
