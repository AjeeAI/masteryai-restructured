import React, { useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { AlertCircle, Loader2 } from 'lucide-react';

export default function ModuleQuizPage() {
  const navigate = useNavigate();
  const { topicId } = useParams();

  useEffect(() => {
    if (!topicId) return;
    navigate(`/quiz/${topicId}`, { replace: true });
  }, [navigate, topicId]);

  if (topicId) {
    return (
      <div className="flex min-h-[calc(100vh-64px)] items-center justify-center bg-slate-50 px-6">
        <div className="rounded-3xl border border-slate-200 bg-white px-8 py-10 text-center shadow-sm">
          <Loader2 className="mx-auto mb-4 h-8 w-8 animate-spin text-indigo-600" />
          <p className="text-sm font-semibold text-slate-700">Redirecting to the live quiz flow...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-[calc(100vh-64px)] items-center justify-center bg-slate-50 px-6">
      <div className="max-w-lg rounded-3xl border border-amber-200 bg-white p-8 shadow-sm">
        <div className="mb-4 flex items-center gap-3 text-amber-600">
          <AlertCircle className="h-6 w-6" />
          <h1 className="text-lg font-black">Module quiz route requires a topic</h1>
        </div>
        <p className="text-sm leading-7 text-slate-600">
          This route now forwards into the main graph-backed quiz experience. Open a lesson first, then start the quiz from that lesson.
        </p>
        <button
          type="button"
          onClick={() => navigate('/dashboard')}
          className="mt-6 rounded-2xl bg-indigo-600 px-4 py-3 text-sm font-bold text-white hover:bg-indigo-700"
        >
          Back to dashboard
        </button>
      </div>
    </div>
  );
}
