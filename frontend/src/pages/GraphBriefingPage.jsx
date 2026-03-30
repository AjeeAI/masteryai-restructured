import React, { useEffect, useState } from 'react';
import { ArrowLeft, Clipboard, Download, Loader2, Printer } from 'lucide-react';
import { Link, useSearchParams } from 'react-router-dom';

import { useAuth } from '../context/AuthContext';
import { useUser } from '../context/UserContext';
import { API_URL } from '../config/runtime';
import { resolveStudentId } from '../utils/sessionIdentity';

const formatDateTime = (value) => {
  if (!value) return 'Not available';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Not available';
  return date.toLocaleString();
};

export default function GraphBriefingPage() {
  const [searchParams] = useSearchParams();
  const subject = searchParams.get('subject') || null;
  const { token } = useAuth();
  const { userData, studentData } = useUser();
  const apiUrl = API_URL;
  const studentId = resolveStudentId(studentData, userData);

  const [briefing, setBriefing] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [copyState, setCopyState] = useState('idle');

  useEffect(() => {
    const fetchBriefing = async () => {
      if (!token || !studentId) {
        setIsLoading(false);
        setError('Graph briefing requires an authenticated student session.');
        return;
      }
      try {
        setIsLoading(true);
        setError('');
        const query = new URLSearchParams({ student_id: String(studentId) });
        if (subject) {
          query.set('subject', subject);
        }
        const response = await fetch(`${apiUrl}/learning/dashboard/briefing/export?${query.toString()}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!response.ok) {
          const detail = await response.json().catch(() => null);
          throw new Error(detail?.detail || 'Failed to load graph briefing.');
        }
        const data = await response.json();
        setBriefing(data || null);
      } catch (err) {
        setBriefing(null);
        setError(err.message || 'Graph briefing is unavailable right now.');
      } finally {
        setIsLoading(false);
      }
    };

    fetchBriefing();
  }, [apiUrl, studentId, subject, token]);

  const handleCopy = async () => {
    if (!briefing?.markdown) return;
    try {
      await navigator.clipboard.writeText(briefing.markdown);
      setCopyState('success');
      window.setTimeout(() => setCopyState('idle'), 1800);
    } catch {
      setCopyState('error');
      window.setTimeout(() => setCopyState('idle'), 1800);
    }
  };

  const handleDownload = () => {
    if (!briefing?.markdown) return;
    const blob = new Blob([briefing.markdown], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = briefing.file_name || 'learning-path-briefing.md';
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <main className="min-h-screen bg-slate-50 p-4 print:bg-white print:p-0 sm:p-6">
      <div className="mx-auto max-w-5xl space-y-5">
        <div className="flex flex-col gap-4 rounded-[24px] border border-slate-200 bg-white p-5 shadow-sm print:hidden">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="text-xl font-black text-slate-900 sm:text-2xl">Learning path briefing</h1>
              <p className="mt-1 text-sm text-slate-500">
                Print-friendly graph-backed summary of what to learn next, what is blocking you, and what recent evidence changed.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Link
                to={subject ? `/graph-path?subject=${encodeURIComponent(subject)}` : '/graph-path'}
                className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-black uppercase tracking-[0.16em] text-slate-700 transition hover:bg-slate-100"
              >
                <ArrowLeft className="h-4 w-4" />
                Back
              </Link>
              <button
                type="button"
                onClick={handleCopy}
                disabled={!briefing?.markdown}
                className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-black uppercase tracking-[0.16em] text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Clipboard className="h-4 w-4" />
                {copyState === 'success' ? 'Copied' : copyState === 'error' ? 'Copy failed' : 'Copy'}
              </button>
              <button
                type="button"
                onClick={handleDownload}
                disabled={!briefing?.markdown}
                className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-black uppercase tracking-[0.16em] text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Download className="h-4 w-4" />
                Download
              </button>
              <button
                type="button"
                onClick={() => window.print()}
                disabled={!briefing?.markdown}
                className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2 text-xs font-black uppercase tracking-[0.16em] text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Printer className="h-4 w-4" />
                Print
              </button>
            </div>
          </div>
        </div>

        {isLoading ? (
          <div className="flex min-h-[280px] flex-col items-center justify-center rounded-[24px] border border-slate-200 bg-white text-slate-400 shadow-sm">
            <Loader2 className="mb-3 h-10 w-10 animate-spin text-indigo-500" />
            <p className="text-sm font-semibold">Preparing graph briefing...</p>
          </div>
        ) : error ? (
          <div className="rounded-[24px] border border-rose-200 bg-rose-50 p-5 text-sm font-semibold text-rose-700">
            {error}
          </div>
        ) : !briefing ? (
          <div className="rounded-[24px] border border-slate-200 bg-white p-5 text-sm font-semibold text-slate-500 shadow-sm">
            No graph briefing is available yet.
          </div>
        ) : (
          <div className="space-y-6">
            <section className="rounded-[24px] border border-slate-200 bg-white p-5 shadow-sm print:shadow-none sm:p-7">
              <p className="text-[11px] font-black uppercase tracking-[0.2em] text-indigo-500">Student graph briefing</p>
              <h2 className="mt-3 text-2xl font-black text-slate-900 sm:text-3xl">{briefing.title}</h2>
              <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-600">{briefing.subtitle}</p>
              <div className="mt-6 grid gap-4 md:grid-cols-3">
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Subject</p>
                  <p className="mt-2 text-lg font-black capitalize text-slate-900">{briefing.subject}</p>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Scope</p>
                  <p className="mt-2 text-lg font-black text-slate-900">
                    {briefing.sss_level} Term {briefing.term}
                  </p>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">Generated</p>
                  <p className="mt-2 text-sm font-bold text-slate-900">{formatDateTime(briefing.generated_at)}</p>
                </div>
              </div>
            </section>

            <section className="grid gap-5 lg:grid-cols-2">
              {(briefing.sections || []).map((section) => (
                <div key={section.title} className="rounded-[24px] border border-slate-200 bg-white p-5 shadow-sm print:break-inside-avoid print:shadow-none">
                  <h3 className="text-sm font-black uppercase tracking-[0.18em] text-slate-500">{section.title}</h3>
                  <div className="mt-4 space-y-3">
                    {(section.items || []).length ? (
                      section.items.map((item, index) => (
                        <div key={`${section.title}-${index}`} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-700">
                          {item}
                        </div>
                      ))
                    ) : (
                      <p className="text-sm text-slate-400">No items in this section yet.</p>
                    )}
                  </div>
                </div>
              ))}
            </section>

            <section className="rounded-[24px] border border-slate-200 bg-slate-950 p-5 shadow-sm print:hidden">
              <p className="text-[11px] font-black uppercase tracking-[0.18em] text-slate-500">Markdown source</p>
              <pre className="mt-4 overflow-x-auto whitespace-pre-wrap text-xs leading-6 text-slate-200">
                {briefing.markdown}
              </pre>
            </section>
          </div>
        )}
      </div>
    </main>
  );
}
