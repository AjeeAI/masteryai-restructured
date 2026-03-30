import React, { useState } from 'react';

const PracticeSidebar = ({ practiceData }) => {
  const [selectedOption, setSelectedOption] = useState('b'); // Mocking 'B' as selected

  return (
    <>
      {/* Quick Practice Card */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-sm font-bold text-indigo-700 uppercase tracking-wider">Quick Practice</h3>
          <div className="flex gap-1">
            <span className="w-2 h-2 rounded-full bg-indigo-600"></span>
            <span className="w-2 h-2 rounded-full bg-slate-200"></span>
            <span className="w-2 h-2 rounded-full bg-slate-200"></span>
          </div>
        </div>
        
        <p className="text-slate-800 font-medium mb-5 text-sm">
          {practiceData.question}
        </p>

        <div className="space-y-3 mb-6">
          {practiceData.options.map((opt) => (
            <button 
              key={opt.id}
              onClick={() => setSelectedOption(opt.id)}
              className={`w-full text-left p-3 rounded-lg border text-sm flex gap-3 transition-colors ${
                selectedOption === opt.id 
                  ? 'border-indigo-500 bg-indigo-50' 
                  : 'border-slate-200 hover:border-indigo-300'
              }`}
            >
              <span className={`flex-shrink-0 w-6 h-6 rounded flex items-center justify-center text-xs font-bold ${
                selectedOption === opt.id ? 'bg-white text-indigo-600 border border-indigo-200' : 'bg-slate-100 text-slate-500'
              }`}>
                {opt.id.toUpperCase()}
              </span>
              <span className="text-slate-700 leading-tight">{opt.text}</span>
            </button>
          ))}
        </div>

        <button className="w-full bg-indigo-600 text-white font-bold py-3 rounded-lg hover:bg-indigo-700 transition">
          Check Answer
        </button>
      </div>

      {/* Mastery Path Card */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
        <h4 className="flex items-center gap-2 font-bold text-slate-800 mb-3 text-sm">
          <span className="text-indigo-500">✓</span> Mastery Path
        </h4>
        <div className="w-full bg-slate-100 rounded-full h-2 mb-2">
          <div className="bg-indigo-500 h-2 rounded-full" style={{ width: `${practiceData.projectedMastery}%` }}></div>
        </div>
        <p className="text-xs text-slate-500">
          Correctly answering this will boost your mastery to {practiceData.projectedMastery}%.
        </p>
      </div>
    </>
  );
};

export default PracticeSidebar;