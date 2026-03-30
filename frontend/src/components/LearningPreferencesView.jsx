import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { useUser } from '../context/UserContext';
import { updateStudentPreferences } from '../services/api';
import { resolveUserId } from '../utils/sessionIdentity';

const LearningPreferencesView = () => {
  const { token } = useAuth();
  // studentData holds academic info; userData holds basic account info
  const { studentData, userData, updateLocalStudent } = useUser();

  // 1. Initialize state from global context
  const savedPrefs = studentData?.preferences || {};
  
  const [depth, setDepth] = useState(
    savedPrefs.explanation_depth === 'simple'
      ? 'quick'
      : savedPrefs.explanation_depth === 'detailed'
        ? 'deep'
        : 'standard',
  );
  const [styles, setStyles] = useState({
    visual: Boolean(savedPrefs.examples_first),
    interactive: savedPrefs.pace === 'fast',
    auditory: false,
  });

  const [isSaving, setIsSaving] = useState(false);
  const [statusMsg, setStatusMsg] = useState({ type: '', text: '' });

  // 2. Sync local state if global context data updates (e.g., after initial fetch)
  useEffect(() => {
    if (studentData?.preferences) {
      const prefs = studentData.preferences;
      setDepth(
        prefs.explanation_depth === 'simple'
          ? 'quick'
          : prefs.explanation_depth === 'detailed'
            ? 'deep'
            : 'standard',
      );
      setStyles({
        visual: Boolean(prefs.examples_first),
        interactive: prefs.pace === 'fast',
        auditory: false,
      });
    }
  }, [studentData]);

  const handleToggle = (key) => {
    setStyles((prev) => ({ ...prev, [key]: !prev[key] }));
    setStatusMsg({ type: '', text: '' }); 
  };

  const handleSave = async () => {
    setIsSaving(true);
    setStatusMsg({ type: '', text: '' });

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000);

    // Identify the correct User ID from context
    const targetUserId = resolveUserId(studentData, userData);

    const payload = {
      explanation_depth: depth === 'quick' ? 'simple' : depth === 'deep' ? 'detailed' : 'standard',
      examples_first: Boolean(styles.visual),
      pace: styles.interactive ? 'fast' : 'normal',
    };

    try {
      await updateStudentPreferences(token, targetUserId, payload);

      // 4. Update global state instantly so Navbar/Dashboard are in sync
      updateLocalStudent({
        preferences: {
          ...(studentData?.preferences || {}),
          student_id: targetUserId,
          explanation_depth: payload.explanation_depth,
          examples_first: payload.examples_first,
          pace: payload.pace,
          updated_at: new Date().toISOString(),
        },
      });
      setStatusMsg({ type: 'success', text: 'Learning preferences updated successfully!' });

    } catch (err) {
      console.error("Preference Save Error:", err);
      setStatusMsg({ 
        type: 'error', 
        text: err.name === 'AbortError' ? 'Server timeout. Please try again.' : err.message 
      });
    } finally {
      clearTimeout(timeoutId);
      setIsSaving(false);
    }
  };

  // Helper data for the Curriculum Widget
  const currentLevel = studentData?.sss_level || "Not Set";
  const currentTerm = studentData?.current_term || 1;
  const enrolledSubjects = studentData?.subjects || [];

  return (
    <div className="space-y-6">
      
      {/* Main Preferences Card */}
      <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-200">
        <div className="mb-6">
          <h2 className="text-xl font-bold text-slate-800">AI Tutor Personalization</h2>
          <p className="text-sm text-slate-500 mt-1">Configure how your Adaptive AI assistant delivers lessons and feedback.</p>
        </div>

        {/* Feedback Banners */}
        {statusMsg.text && (
          <div className={`mb-8 p-3 rounded-lg text-sm font-medium border ${
            statusMsg.type === 'success' ? 'bg-emerald-50 border-emerald-200 text-emerald-700' : 'bg-rose-50 border-rose-200 text-rose-600'
          }`}>
            {statusMsg.text}
          </div>
        )}

        {/* Section 1: Explanation Depth */}
        <div className="mb-10">
          <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-4">Explanation Depth</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <DepthCard 
              id="quick" 
              title="Quick Summaries" 
              desc="Focused on key concepts and immediate takeaways." 
              icon="⚡" 
              currentDepth={depth} 
              setDepth={(id) => { setDepth(id); setStatusMsg({ type: '', text: '' }); }} 
            />
            <DepthCard 
              id="standard" 
              title="Standard Depth" 
              desc="Default balanced approach for curriculum mastery." 
              icon="⚖️" 
              currentDepth={depth} 
              setDepth={(id) => { setDepth(id); setStatusMsg({ type: '', text: '' }); }} 
            />
            <DepthCard 
              id="deep" 
              title="Deep Dive" 
              desc="Detailed explanations with cross-subject connections." 
              icon="🔬" 
              currentDepth={depth} 
              setDepth={(id) => { setDepth(id); setStatusMsg({ type: '', text: '' }); }} 
            />
          </div>
        </div>

        {/* Section 2: Preferred Learning Style */}
        <div className="mb-10">
          <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-4">Preferred Learning Style</h3>
          <div className="space-y-4">
            <ToggleRow 
              title="Visual & Diagrams" 
              desc="Prioritize charts, maps, and visual storytelling." 
              icon="👁️" 
              isOn={styles.visual} 
              onToggle={() => handleToggle('visual')} 
            />
            <hr className="border-slate-100" />
            <ToggleRow 
              title="Interactive Practice" 
              desc="More frequent 'learning by doing' checkpoints." 
              icon="✨" 
              isOn={styles.interactive} 
              onToggle={() => handleToggle('interactive')} 
            />
            <hr className="border-slate-100" />
            <ToggleRow 
              title="Auditory Narrations" 
              desc="Enable AI voice-overs for complex text modules." 
              icon="🎧" 
              isOn={styles.auditory} 
              onToggle={() => handleToggle('auditory')} 
            />
          </div>
        </div>

        {/* Section 3: Mastery Goals */}
        <div className="mb-10">
          <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-4">Mastery Goals</h3>
          <div className="bg-indigo-50/50 border border-indigo-100 rounded-xl p-5 flex items-start gap-4">
            <div className="text-indigo-600 text-xl mt-0.5">⏱️</div>
            <div>
              <h4 className="font-bold text-slate-800 text-sm">Adaptive Pacing</h4>
              <p className="text-sm text-slate-600 mt-1 leading-relaxed">
                Your AI Tutor is currently set to <span className="font-semibold text-indigo-700">Curriculum Pace</span>. It will automatically suggest prerequisite concepts if your mastery score falls below 75%.
              </p>
              <button className="text-indigo-600 font-semibold text-sm mt-3 hover:text-indigo-800 transition-colors">
                Adjust Pacing Strategy →
              </button>
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex justify-end items-center gap-4 pt-4 border-t border-slate-100">
          <button 
            type="button"
            onClick={() => { setDepth('standard'); setStyles({ visual: true, interactive: true, auditory: false }); }}
            className="text-sm font-semibold text-slate-500 hover:text-slate-800 transition-colors"
          >
            Reset Defaults
          </button>
          <button 
            onClick={handleSave}
            disabled={isSaving}
            className={`font-semibold py-2.5 px-6 rounded-lg transition-colors shadow-sm ${
              isSaving ? 'bg-indigo-400 text-white cursor-not-allowed' : 'bg-indigo-600 hover:bg-indigo-700 text-white'
            }`}
          >
            {isSaving ? 'Saving...' : 'Save Preferences'}
          </button>
        </div>
      </div>

      {/* Curriculum Focus Widget */}
      <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center text-amber-600 text-lg">
            🎓
          </div>
          <div>
            <h3 className="font-bold text-slate-800">Current Curriculum Focus</h3>
            <p className="text-xs text-slate-500">Academic Year 2023/24</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {enrolledSubjects.length > 0 ? (
            enrolledSubjects.map((sub, idx) => (
              <div key={idx} className="flex justify-between items-center p-4 rounded-xl border border-slate-100 bg-slate-50">
                <div className="flex items-center gap-3">
                  <span className={`w-2.5 h-2.5 rounded-full ${idx % 2 === 0 ? 'bg-emerald-500' : 'bg-indigo-500'}`}></span>
                  <span className="font-bold text-slate-700 text-sm capitalize">{sub}</span>
                </div>
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  {currentLevel} • Term {currentTerm}
                </span>
              </div>
            ))
          ) : (
             <p className="text-sm text-slate-500 col-span-2">No subjects selected yet. Update them in your class setup.</p>
          )}
        </div>
      </div>

    </div>
  );
};

/* --- Internal Sub-Components --- */

const DepthCard = ({ id, title, desc, icon, currentDepth, setDepth }) => {
  const isSelected = currentDepth === id;
  return (
    <button 
      onClick={() => setDepth(id)}
      className={`text-left p-5 rounded-xl border-2 transition-all relative ${
        isSelected ? 'border-indigo-600 bg-indigo-50/30' : 'border-slate-200 hover:border-indigo-300 bg-white'
      }`}
    >
      {isSelected && (
        <div className="absolute top-3 right-3 text-indigo-600">
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd"></path></svg>
        </div>
      )}
      <div className="text-2xl mb-3">{icon}</div>
      <h4 className={`font-bold text-sm mb-1 ${isSelected ? 'text-indigo-900' : 'text-slate-800'}`}>{title}</h4>
      <p className="text-xs text-slate-500 leading-relaxed">{desc}</p>
    </button>
  );
};

const ToggleRow = ({ title, desc, icon, isOn, onToggle }) => {
  return (
    <div className="flex items-center justify-between py-2">
      <div className="flex items-start gap-4">
        <div className="w-10 h-10 rounded-full bg-slate-50 flex items-center justify-center text-lg border border-slate-100">
          {icon}
        </div>
        <div>
          <h4 className="font-bold text-slate-800 text-sm">{title}</h4>
          <p className="text-xs text-slate-500 mt-0.5">{desc}</p>
        </div>
      </div>
      <button 
        onClick={onToggle}
        className={`w-12 h-6 rounded-full relative transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 ${
          isOn ? 'bg-indigo-600' : 'bg-slate-300'
        }`}
      >
        <span className={`absolute top-1 left-1 bg-white w-4 h-4 rounded-full transition-transform ${
          isOn ? 'translate-x-6' : 'translate-x-0'
        }`} />
      </button>
    </div>
  );
};

export default LearningPreferencesView;
