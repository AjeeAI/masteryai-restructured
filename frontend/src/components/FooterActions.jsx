import { useNavigate } from 'react-router-dom'; // <-- 1. Import the hook
import { ArrowRight, Compass, HelpCircle } from 'lucide-react';

export default function FooterActions({
  recommendedTopicId = null,
  recommendedTopicTitle = null,
  explainState = null,
  actionLabel = null,
}) {
  const navigate = useNavigate(); // <-- 2. Initialize it
  const hasExplainContext = Boolean(
    explainState?.question && explainState?.studentAnswer && explainState?.correctAnswer,
  );

  return (
    <div className="flex flex-col md:flex-row justify-between items-center gap-4 py-6 border-t border-gray-200 mt-8">
        <div className="flex gap-4 w-full md:w-auto">
            
            {/* <-- 3. Wire up Return to Dashboard --> */}
            <button 
              onClick={() => {
                if (recommendedTopicId) {
                  navigate(`/lesson/${recommendedTopicId}`);
                  return;
                }
                navigate('/dashboard');
              }}
              className="flex-1 md:flex-none flex items-center justify-center gap-2 bg-blue-500 hover:bg-blue-600 text-white px-6 py-3 rounded-xl font-bold transition-colors cursor-pointer"
            >
                {recommendedTopicId ? <ArrowRight className="w-5 h-5" /> : <Compass className="w-5 h-5" />}
                {recommendedTopicId ? (actionLabel || `Open ${recommendedTopicTitle || 'Recommended Lesson'}`) : 'Return to Learning Map'}
            </button>

            {/* <-- 4. Wire up Explain My Mistakes --> */}
            {hasExplainContext && (
              <button 
                onClick={() => navigate('/mastery-path', { state: explainState })}
                className="flex-1 md:flex-none flex items-center justify-center gap-2 bg-[#1c2438] hover:bg-[#2a3447] text-white px-6 py-3 rounded-xl font-bold transition-colors cursor-pointer"
              >
                  <HelpCircle className="w-5 h-5" />
                  Explain My Mistakes
              </button>
            )}

        </div>
    </div>
  );
}
