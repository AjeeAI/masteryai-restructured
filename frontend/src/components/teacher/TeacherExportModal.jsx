import React, { useState } from 'react';
import { Clipboard, Download, FileText, Share2, X } from 'lucide-react';

const formatDateTime = (value) => {
  if (!value) return 'Not available';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Not available';
  return date.toLocaleString();
};

const TeacherExportModal = ({ isOpen, onClose, exportData, isLoading, error }) => {
  const [copyState, setCopyState] = useState('idle');

  const previewSections = Array.isArray(exportData?.sections) ? exportData.sections : [];

  if (!isOpen) return null;

  const handleCopy = async () => {
    if (!exportData?.markdown) return;
    try {
      await navigator.clipboard.writeText(exportData.markdown);
      setCopyState('success');
      window.setTimeout(() => setCopyState('idle'), 1800);
    } catch {
      setCopyState('error');
      window.setTimeout(() => setCopyState('idle'), 1800);
    }
  };

  const handleDownload = () => {
    if (!exportData?.markdown) return;
    const blob = new Blob([exportData.markdown], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = exportData.file_name || 'teacher-export.md';
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-slate-950/45 px-4 backdrop-blur-sm">
      <div className="flex max-h-[90vh] w-full max-w-4xl flex-col overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-2xl">
        <div className="flex items-start justify-between border-b border-slate-200 px-6 py-5">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em] text-slate-600">
              <Share2 className="h-3.5 w-3.5" />
              Teacher export
            </div>
            <h2 className="mt-3 text-2xl font-black text-slate-900">
              {exportData?.title || 'Preparing export'}
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              {exportData?.subtitle || 'Pulling the latest graph-backed evidence for sharing.'}
            </p>
            {exportData?.generated_at ? (
              <p className="mt-2 text-xs font-semibold text-slate-400">
                Generated {formatDateTime(exportData.generated_at)}
              </p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl border border-slate-200 p-2 text-slate-500 transition hover:bg-slate-100 hover:text-slate-700"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="grid flex-1 gap-0 overflow-hidden lg:grid-cols-[1.05fr_0.95fr]">
          <div className="overflow-y-auto border-r border-slate-200 bg-slate-50 px-6 py-6">
            {isLoading ? (
              <div className="rounded-2xl border border-dashed border-slate-200 bg-white p-8 text-center text-sm font-semibold text-slate-400">
                Preparing export...
              </div>
            ) : error ? (
              <div className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-sm font-semibold text-rose-700">
                {error}
              </div>
            ) : (
              <div className="space-y-4">
                {previewSections.map((section) => (
                  <div key={section.title} className="rounded-2xl border border-slate-200 bg-white p-4">
                    <h3 className="text-sm font-black uppercase tracking-[0.18em] text-slate-500">{section.title}</h3>
                    <div className="mt-3 space-y-2">
                      {(section.items || []).length ? (
                        section.items.map((item, index) => (
                          <p key={`${section.title}-${index}`} className="text-sm leading-6 text-slate-700">
                            {item}
                          </p>
                        ))
                      ) : (
                        <p className="text-sm text-slate-400">No export-ready items in this section.</p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="flex min-h-0 flex-col px-6 py-6">
            <div className="mb-4 flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={handleCopy}
                disabled={isLoading || !exportData?.markdown}
                className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2 text-xs font-black uppercase tracking-[0.16em] text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Clipboard className="h-4 w-4" />
                {copyState === 'success' ? 'Copied' : copyState === 'error' ? 'Copy failed' : 'Copy markdown'}
              </button>
              <button
                type="button"
                onClick={handleDownload}
                disabled={isLoading || !exportData?.markdown}
                className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-black uppercase tracking-[0.16em] text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Download className="h-4 w-4" />
                Download .md
              </button>
            </div>

            <div className="min-h-0 flex-1 overflow-hidden rounded-2xl border border-slate-200 bg-slate-950">
              <div className="flex items-center gap-2 border-b border-slate-800 px-4 py-3 text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">
                <FileText className="h-3.5 w-3.5" />
                Markdown preview
              </div>
              <pre className="h-full overflow-y-auto whitespace-pre-wrap px-4 py-4 text-xs leading-6 text-slate-200">
                {exportData?.markdown || 'No export body available yet.'}
              </pre>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TeacherExportModal;
