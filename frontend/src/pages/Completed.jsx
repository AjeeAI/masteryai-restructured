import React from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertCircle, ArrowRight } from 'lucide-react';

export default function CompletedPage() {
  const navigate = useNavigate();

  return (
    <main className="flex min-h-[calc(100vh-64px)] items-center justify-center bg-slate-50 px-6">
      <div className="max-w-xl rounded-[2rem] border border-slate-200 bg-white p-8 shadow-sm">
        <div className="mb-4 flex items-center gap-3 text-indigo-600">
          <AlertCircle className="h-6 w-6" />
          <h1 className="text-xl font-black text-slate-900">Legacy completion route</h1>
        </div>
        <p className="text-sm leading-7 text-slate-600">
          This older completion screen is no longer used in the live quiz flow. Quiz results now render directly with graph-backed remediation and recommended next lessons.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => navigate('/dashboard')}
            className="rounded-2xl border border-slate-200 px-4 py-3 text-sm font-bold text-slate-700 hover:bg-slate-50"
          >
            Back to dashboard
          </button>
          <button
            type="button"
            onClick={() => navigate(-1)}
            className="inline-flex items-center gap-2 rounded-2xl bg-indigo-600 px-4 py-3 text-sm font-bold text-white hover:bg-indigo-700"
          >
            Return
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>
      </div>
    </main>
  );
}
