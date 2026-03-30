import React from 'react';

const ContextSidebar = ({ questionData, insightData }) => {
  return (
    <>
      {/* Original Question Card */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
        <div className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-2">
          <span>↺</span> ORIGINAL QUESTION
        </div>
        <h3 className="text-lg font-semibold text-slate-800 mb-5 leading-snug">
          {questionData.text}
        </h3>
        
        <div className="space-y-4">
          <div className="bg-red-50 border border-red-100 rounded-lg p-3">
            <p className="text-xs font-bold text-red-500 mb-1 flex items-center gap-1">✕ YOUR ANSWER</p>
            <p className="text-sm text-slate-700">{questionData.userAnswer}</p>
          </div>
          
          <div className="bg-emerald-50 border border-emerald-100 rounded-lg p-3">
            <p className="text-xs font-bold text-emerald-600 mb-1 flex items-center gap-1">✓ CORRECT ANSWER</p>
            <p className="text-sm text-slate-700">{questionData.correctAnswer}</p>
          </div>
        </div>
      </div>

      {/* Topic Insight Card */}
      <div className="bg-indigo-50 rounded-xl border border-indigo-100 p-5">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-indigo-500">📊</span>
          <h4 className="font-semibold text-indigo-900">Topic Insight</h4>
        </div>
        <p className="text-sm text-indigo-800 leading-relaxed">
          This question falls under <strong>{insightData.topic}</strong>. You have a {insightData.masteryRate}% mastery rate in this sub-topic.
        </p>
      </div>
    </>
  );
};

export default ContextSidebar;