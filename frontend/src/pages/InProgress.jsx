import React from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertCircle } from 'lucide-react';

export default function InProgress() {
  const navigate = useNavigate();

  return (
    <main className="flex min-h-[calc(100vh-64px)] items-center justify-center bg-slate-50 px-6">
      <div className="max-w-xl rounded-[2rem] border border-slate-200 bg-white p-8 shadow-sm">
        <div className="mb-4 flex items-center gap-3 text-indigo-600">
          <AlertCircle className="h-6 w-6" />
          <h1 className="text-xl font-black text-slate-900">Legacy analysis route</h1>
        </div>
        <p className="text-sm leading-7 text-slate-600">
          Diagnostic and quiz analysis now happens directly inside the live lesson and quiz flows. This legacy waiting screen is no longer part of the active product path.
        </p>
        <button
          type="button"
          onClick={() => navigate('/dashboard')}
          className="mt-6 rounded-2xl bg-indigo-600 px-4 py-3 text-sm font-bold text-white hover:bg-indigo-700"
        >
          Back to dashboard
        </button>
      </div>
    </main>
  );
}
