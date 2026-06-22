import { CheckCircle, AlertCircle } from 'lucide-react';

export default function ScoreSummary({ data }) {
  // Determine if the user passed (70% or higher)
  const isPassed = data.accuracy >= 70;

  return (
    <div className="bg-gradient-to-r from-[#7F13EC] to-[#5b3da6] rounded-2xl p-6 sm:p-8 text-white shadow-lg mb-8">
      
      {/* Dynamic Status Header */}
      <div className={`flex items-center gap-2 text-xs font-bold uppercase tracking-wider mb-4 ${isPassed ? 'text-emerald-300' : 'text-amber-300'}`}>
        {isPassed ? <CheckCircle className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
        {isPassed ? 'Mastery Achieved' : 'Keep Practicing'}
      </div>
      
      {/* FIXED: Changed to flex-col on mobile, flex-row on larger screens */}
      <div className="flex flex-col sm:flex-row sm:items-start gap-4 sm:gap-6 mb-8">
        
        {/* Circular SVG Progress */}
        <div className="relative w-20 h-20 sm:w-24 sm:h-24 flex items-center justify-center shrink-0">
          <svg className="w-full h-full transform -rotate-90" viewBox="0 0 36 36">
            <path className="text-white/20" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="currentColor" strokeWidth="3" />
            <path 
              className={isPassed ? "text-emerald-400" : "text-amber-400"} 
              strokeDasharray={`${(data.score / data.total) * 100}, 100`} 
              d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" 
              fill="none" stroke="currentColor" strokeWidth="3" 
            />
          </svg>
          <div className="absolute text-center">
            <span className="text-xl sm:text-2xl font-bold">{data.score}/{data.total}</span>
            <span className="block text-[10px] font-medium text-white/80 uppercase tracking-wider">Score</span>
          </div>
        </div>
        
        {/* Dynamic Greeting - FIXED: Added flex-1 min-w-0 */}
        <div className="flex-1 min-w-0">
          {/* FIXED: Added break-words and reduced mobile font size slightly */}
          <h1 className="text-2xl sm:text-3xl font-bold mb-2 break-words">
            {isPassed ? `Excellent Work, ${data.studentName}!` : `Good Effort, ${data.studentName}!`}
          </h1>
          <p className="text-indigo-100 text-sm max-w-lg leading-relaxed">
            {data.message}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2 sm:gap-4 border-t border-white/20 pt-6">
        <div>
          <div className="text-[10px] sm:text-xs text-indigo-200 font-bold uppercase tracking-wider mb-1">Time Taken</div>
          <div className="text-lg sm:text-xl font-bold">{data.timeTaken}</div>
        </div>
        <div>
          <div className="text-[10px] sm:text-xs text-indigo-200 font-bold uppercase tracking-wider mb-1">Accuracy</div>
          <div className={`text-lg sm:text-xl font-bold ${isPassed ? 'text-emerald-300' : 'text-amber-300'}`}>
            {data.accuracy}%
          </div>
        </div>
        <div>
          <div className="text-[10px] sm:text-xs text-indigo-200 font-bold uppercase tracking-wider mb-1">XP Earned</div>
          <div className="text-lg sm:text-xl font-bold text-amber-300">+{data.xpEarned} XP</div>
        </div>
      </div>
    </div>
  );
}