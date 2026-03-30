import React from 'react';

const AIExplanationArea = ({ explanationData }) => {
  // Safety guard in case data hasn't loaded yet
  if (!explanationData) return null;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-100 overflow-hidden">
      {/* Header */}
      <div className="bg-indigo-600 px-6 py-4 flex justify-between items-center">
        <h2 className="text-white font-bold text-xl flex items-center gap-2">
          <span>✨</span> Explain My Mistake
        </h2>
        <span className="bg-indigo-500/50 text-indigo-100 text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wider">
          AI Generated
        </span>
      </div>

      <div className="p-6 space-y-8">
        
        {/* The Explanation (Mapped from API: 'explanation') */}
        <section>
          <h3 className="flex items-center gap-2 text-indigo-700 font-bold mb-3">
            <span>🧠</span> The Core Misconception
          </h3>
          <div className="text-slate-700 leading-relaxed bg-indigo-50/50 p-5 rounded-xl border border-indigo-50">
            {/* Using whitespace-pre-wrap so if the AI returns paragraphs or bullet 
              points in the string, they render correctly on screen.
            */}
            <span className="whitespace-pre-wrap">
              {explanationData.explanationText || explanationData.misconception}
            </span>
          </div>
        </section>

        {/* Improvement Tip (Mapped from API: 'improvement_tip') */}
        {explanationData.improvementTip && (
          <section>
            <h3 className="flex items-center gap-2 text-emerald-700 font-bold mb-4">
              <span>💡</span> How to get it right next time
            </h3>
            <div className="bg-emerald-50 rounded-xl p-5 border border-emerald-100">
              <p className="text-sm text-emerald-800 leading-relaxed">
                {explanationData.improvementTip}
              </p>
            </div>
          </section>
        )}

        {/* NOTE: The Analogy and Breakdown sections were removed because the backend 
          currently doesn't generate that specific data. If you update the Python 
          backend to return complex JSON instead of just strings, you can easily 
          add them back!
        */}

      </div>
    </div>
  );
};

export default AIExplanationArea;