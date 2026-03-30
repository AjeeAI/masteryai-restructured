import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useUser } from '../context/UserContext';
import { Target, Clock, Brain, CheckCircle, AlertCircle, ArrowRight, ArrowLeft, BarChart2 } from 'lucide-react';

// --- Import your custom components ---
import Breadcrumbs from "../components/BreadCrumbs";
import ScoreSummary from "../components/ScoreSummary";
import ConceptCard from "../components/ConceptCard";
import AITutorInsights from "../components/AITutorInsights";
import PathProgress from "../components/PathProgress";
import FooterActions from "../components/FooterActions";
import { API_URL } from '../config/runtime';
import { saveGraphIntervention } from '../services/graphIntervention';
import { resolveStudentId } from '../utils/sessionIdentity';

const isLikelyUuid = (value) => /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(String(value || '').trim());

const humanizeConceptId = (conceptId, fallback = 'Concept') => {
  const value = String(conceptId || '').trim();
  if (!value) return fallback;
  const cleaned = value.startsWith('topic:') ? value.replace(/^topic:/i, '') : value;
  if (isLikelyUuid(cleaned)) return fallback;
  const token = value.split(':').pop()?.trim() || value;
  return token
    .replace(/-(\d+)$/, '')
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase()) || fallback;
};

const prewarmTopics = async ({ apiUrl, token, studentId, subject, sssLevel, term, topicIds }) => {
  const normalizedIds = Array.from(new Set((topicIds || []).filter(Boolean)));
  if (!normalizedIds.length) return;
  try {
    await fetch(`${apiUrl}/learning/lesson/prewarm`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        student_id: studentId,
        subject,
        sss_level: sssLevel,
        term,
        topic_ids: normalizedIds,
      }),
    });
  } catch (error) {
    console.warn('Quiz remediation prewarm skipped:', error);
  }
};

const resolveOptionText = (question, answerLetter) => {
  const normalized = String(answerLetter || '').trim();
  if (!normalized) return '';
  if (normalized === 'SKIPPED') return 'Skipped this question';

  const optionIndex = normalized.charCodeAt(0) - 65;
  const option = Array.isArray(question?.options) ? question.options[optionIndex] : null;
  if (typeof option === 'string') return option;
  if (option && typeof option === 'object') {
    return option.text || option.value || normalized;
  }
  return normalized;
};

const QuizPage = () => {
  const { topicId } = useParams();
  const { token } = useAuth();
  const { studentData, userData } = useUser();
  const activeId = resolveStudentId(studentData, userData);

  const currentSubject = localStorage.getItem('active_subject') || studentData?.subjects?.[0] || 'math';
  const currentLevel = studentData?.sss_level || 'SSS3';
  const currentTerm = studentData?.current_term || 1;

  const apiUrl = API_URL;

  // --- LIFECYCLE STATES ---
  const [phase, setPhase] = useState('setup'); // 'setup' | 'generating' | 'active' | 'submitting' | 'results'
  const [error, setError] = useState("");

  // Setup Config
  const [difficulty, setDifficulty] = useState('medium');
  const [purpose] = useState('practice');

  // Active Quiz Data
  const [quizData, setQuizData] = useState(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selectedOption, setSelectedOption] = useState(null); // Now tracks 'A', 'B', 'C', 'D'
  const [answers, setAnswers] = useState({});
  const [startTime, setStartTime] = useState(null);

  const [formattedResults, setFormattedResults] = useState(null);

  // ======================================================================
  // 1. GENERATE QUIZ
  // ======================================================================
  const handleGenerateQuiz = async () => {
    if (!topicId) {
      setError("Missing Topic ID! Please go back to the lesson and click 'Take Mastery Quiz' again.");
      return;
    }

    setPhase('generating');
    setError("");

    try {
      const response = await fetch(`${apiUrl}/learning/quizzes/generate`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          student_id: activeId,
          subject: currentSubject,
          sss_level: currentLevel,
          term: currentTerm,
          topic_id: topicId, 
          purpose: purpose,
          difficulty: difficulty,
          num_questions: 5 
        })
      });

      if (!response.ok) throw new Error("Failed to generate quiz. Please try again.");

      const data = await response.json();
      setQuizData(data); // Injects the JSON structure you provided
      setStartTime(Date.now());
      setPhase('active');
    } catch (err) {
      setError(err.message);
      setPhase('setup');
    }
  };

  // ======================================================================
  // 2. SUBMIT QUIZ & MAP RESULTS
  // ======================================================================
 // ======================================================================
  // 2. SUBMIT QUIZ & MAP RESULTS
  // ======================================================================
  const submitQuizAnswers = async (finalAnswers) => {
    setPhase('submitting');
    setError("");

    const timeTakenSeconds = Math.floor((Date.now() - startTime) / 1000);
    
    // finalAnswers is now safely mapped as { "question_uuid": "A" }
    const formattedAnswers = Object.entries(finalAnswers).map(([qId, ans]) => ({
      question_id: qId,
      answer: ans 
    }));

    try {
      const submitRes = await fetch(`${apiUrl}/learning/quizzes/${quizData.quiz_id}/submit`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ student_id: activeId, answers: formattedAnswers, time_taken_seconds: timeTakenSeconds })
      });

      if (!submitRes.ok) throw new Error("Failed to submit quiz.");
      const submitData = await submitRes.json();
      const attemptId = submitData.attempt_id;

      const resultsRes = await fetch(`${apiUrl}/learning/quizzes/${quizData.quiz_id}/results?student_id=${activeId}&attempt_id=${attemptId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (!resultsRes.ok) throw new Error("Submitted successfully, but failed to load results.");
      const resultsJson = await resultsRes.json();

      // ==========================================================
      // ðŸ‘‡ THE FIX: Smart math for Score and Accuracy ðŸ‘‡
      // ==========================================================
      const totalQs = quizData.questions.length;
      const rawScore = resultsJson.score || 0;
      
      // If backend returns 60, keep 60. If it returns 0.6, make it 60.
      const finalScorePercentage = rawScore > 1 ? rawScore : Math.round(rawScore * 100); 
      
      // Calculate correct points (e.g., 60% of 5 questions = 3 correct answers)
      const correctAnswersCount = Math.round((finalScorePercentage / 100) * totalQs);

      const minutes = Math.floor(timeTakenSeconds / 60);
      const seconds = timeTakenSeconds % 60;
      // ==========================================================
      
      const humanizeConceptId = (conceptId, fallback = 'Concept') => {
        const value = String(conceptId || '').trim();
        if (!value) return fallback;
        const cleaned = value.startsWith('topic:') ? value.replace(/^topic:/i, '') : value;
        if (isLikelyUuid(cleaned)) return fallback;
        const token = value.split(':').pop()?.trim() || value;
        return token
          .replace(/-(\d+)$/, '')
          .replace(/[_-]+/g, ' ')
          .replace(/\s+/g, ' ')
          .trim()
          .replace(/\b\w/g, (char) => char.toUpperCase()) || fallback;
      };

      const normalizeConceptLabel = (label, conceptId, fallback = 'Concept') => {
        const cleaned = String(label || '').trim();
        if (!cleaned || cleaned.includes(':') || isLikelyUuid(cleaned)) {
          return humanizeConceptId(conceptId, fallback);
        }
        return cleaned;
      };

      const wrongConcepts = (resultsJson.concept_breakdown || [])
        .filter(c => !c.is_correct)
        .map(c => normalizeConceptLabel(c.concept_label, c.concept_id));
      const firstCorrectConcept = (resultsJson.concept_breakdown || []).find((concept) => concept?.is_correct);
      const firstCorrectLabel = firstCorrectConcept
        ? normalizeConceptLabel(firstCorrectConcept.concept_label, firstCorrectConcept.concept_id)
        : null;
      const weakestConceptLabel = (() => {
        const rawLabel = resultsJson.graph_remediation?.weakest_concept_label || null;
        const rawId = resultsJson.graph_remediation?.weakest_concept_id || null;
        if (rawLabel || rawId) {
          return normalizeConceptLabel(rawLabel, rawId);
        }
        return wrongConcepts[0] || null;
      })();
      const nextConceptLabel = resultsJson.graph_remediation?.recommended_next_concept_label || null;

      const firstWrongQuestion = quizData.questions.find((question) => {
        const submitted = finalAnswers[question.id];
        return Boolean(submitted) && submitted !== question.correct_answer;
      });
      const explainState = firstWrongQuestion
        ? {
            question: firstWrongQuestion.text,
            studentAnswer: resolveOptionText(firstWrongQuestion, finalAnswers[firstWrongQuestion.id]),
            correctAnswer: resolveOptionText(firstWrongQuestion, firstWrongQuestion.correct_answer),
            topicId,
          }
        : null;

      const recommendedTopicId = resultsJson.recommended_revision_topic_id
        || resultsJson.graph_remediation?.recommended_next_topic_id
        || null;
      const rawRecommendedTitle = resultsJson.recommended_revision_topic_title
        || resultsJson.graph_remediation?.recommended_next_topic_title
        || null;
      const recommendedTopicTitle = (rawRecommendedTitle && !isLikelyUuid(rawRecommendedTitle))
        ? String(rawRecommendedTitle).trim()
        : null;
      const recommendationReason = resultsJson.graph_remediation?.recommendation_reason
        || resultsJson.recommendation_story?.supporting_reason
        || null;
      const recentEvidence = (resultsJson.recommendation_story?.evidence_summary || firstCorrectLabel || weakestConceptLabel)
        ? {
            summary: resultsJson.recommendation_story?.evidence_summary
              || `Latest quiz attempt scored ${finalScorePercentage}% and changed your concept focus for this course.`,
            strongest_gain_concept_label: firstCorrectLabel,
            strongest_drop_concept_label: weakestConceptLabel,
          }
        : null;
      const nextStep = (recommendedTopicId || recommendedTopicTitle || nextConceptLabel || recommendationReason || weakestConceptLabel)
        ? {
            recommended_topic_id: recommendedTopicId,
            recommended_topic_title: recommendedTopicTitle,
            recommended_concept_label: nextConceptLabel,
            prereq_gaps: resultsJson.graph_remediation?.blocking_prerequisite_label
              ? [{ label: resultsJson.graph_remediation.blocking_prerequisite_label }]
              : [],
            prereq_gap_labels: resultsJson.graph_remediation?.blocking_prerequisite_label
              ? [resultsJson.graph_remediation.blocking_prerequisite_label]
              : [],
            reason: recommendationReason,
          }
        : null;
      const recommendationStory = resultsJson.recommendation_story || (nextStep
        ? {
            status: weakestConceptLabel ? 'hold_current' : 'advance',
            headline: recommendedTopicTitle
              ? `Move into ${recommendedTopicTitle}`
              : weakestConceptLabel
                ? `Repair ${weakestConceptLabel}`
                : 'Use the latest quiz evidence to guide your next move.',
            supporting_reason: recommendationReason,
            evidence_summary: recentEvidence?.summary || null,
            next_concept_label: nextConceptLabel,
            action_label: recommendedTopicId ? 'Open Recommended Lesson' : 'Review this concept',
          }
        : null);

      if (nextStep || recentEvidence || recommendationStory) {
        saveGraphIntervention({
          studentId: activeId,
          subject: currentSubject,
          sssLevel: currentLevel,
          term: currentTerm,
          payload: {
            source: 'quiz',
            analytics: {
              source_label: 'Quiz result',
              outcome: finalScorePercentage >= 70 ? 'Advance from strength' : 'Repair weak concept',
              focus_concept: nextConceptLabel || weakestConceptLabel || firstCorrectConcept?.concept_label || null,
              blocking_prerequisite: resultsJson.graph_remediation?.blocking_prerequisite_label || null,
            },
            next_step: nextStep,
            recent_evidence: recentEvidence,
            recommendation_story: recommendationStory,
          },
        });
      }

      await prewarmTopics({
        apiUrl,
        token,
        studentId: activeId,
        subject: currentSubject,
        sssLevel: currentLevel,
        term: currentTerm,
        topicIds: recommendedTopicId ? [recommendedTopicId] : [],
      });

      const mappedApiData = {
        paths: { classLevel: currentLevel, topic: currentSubject },
        summary: {
            studentName: userData?.first_name || "Student",
            score: correctAnswersCount, // Fixed: Will show "3" instead of "300"
            total: totalQs,
            message: finalScorePercentage >= 70 ? "Great job! You've shown strong mastery of these concepts." : "Good effort! Review the insights to improve your mastery.",
            timeTaken: `${minutes}m ${seconds}s`,
            accuracy: finalScorePercentage, // Fixed: Will show "60" instead of "6000"
            xpEarned: submitData.xp_awarded || Math.round(finalScorePercentage * 2.5)
        },
        concepts: (resultsJson.concept_breakdown || []).map((c, i) => ({
            id: i + 1,
            title: normalizeConceptLabel(c.concept_label, c.concept_id, `Concept ${i+1}`),
            mastery: c.weight_change > 0 ? 100 : Math.max(0, 50 + (c.weight_change * 10)),
            description: c.is_correct ? "Perfect! You understand this core concept." : "Needs review. Pay attention to the rules here."
        })),
        aiInsights: {
            greeting: `Hi ${userData?.first_name || 'there'}! Here is my analysis:`,
            strugglePoints: wrongConcepts.length > 0 ? wrongConcepts : ["None! Perfect execution."],
            keyInsight: resultsJson.insights?.[0] || "Keep up the consistent practice to solidify these topics!",
            prerequisite: resultsJson.graph_remediation?.blocking_prerequisite_label
              || resultsJson.insights?.[1]
              || "Review the foundational rules before moving forward."
        },
        nextTopicId: recommendedTopicId,
        nextTopic: recommendedTopicTitle
          || (recommendedTopicId ? "Recommended lesson" : null)
          || recommendationStory?.headline
          || "Stay on this lesson",
        remediation: {
          weakestConcept: weakestConceptLabel,
          blockingPrerequisite: resultsJson.graph_remediation?.blocking_prerequisite_label || null,
          recommendationReason: recommendationReason,
          nextConcept: nextConceptLabel,
        },
        recommendationStory,
        explainState,
      };

      setFormattedResults(mappedApiData);
      setPhase('results');
      
    } catch (err) {
      setError(err.message);
      setPhase('active');
    }
  };

  // ======================================================================
  // ACTIVE QUIZ HANDLERS
  // ======================================================================
  // ðŸ‘‡ Now takes the Letter (A, B, C, D) instead of the long string
  const handleSelectOption = (optionLetter) => setSelectedOption(optionLetter);

  const handleNextOrSubmit = () => {
    const currentQuestion = quizData.questions[currentIndex];
    const updatedAnswers = { ...answers, [currentQuestion.id]: selectedOption };
    setAnswers(updatedAnswers);

    const isLastQuestion = currentIndex === quizData.questions.length - 1;

    if (isLastQuestion) submitQuizAnswers(updatedAnswers);
    else {
      setCurrentIndex(currentIndex + 1);
      // Load previously selected answer if they navigate back (future proofing)
      setSelectedOption(updatedAnswers[quizData.questions[currentIndex + 1].id] || null);
    }
  };

  const handleSkip = () => {
    const currentQuestion = quizData.questions[currentIndex];
    const updatedAnswers = { ...answers, [currentQuestion.id]: "SKIPPED" };
    setAnswers(updatedAnswers);

    const isLastQuestion = currentIndex === quizData.questions.length - 1;

    if (isLastQuestion) submitQuizAnswers(updatedAnswers);
    else {
      setCurrentIndex(currentIndex + 1);
      setSelectedOption(updatedAnswers[quizData.questions[currentIndex + 1].id] || null);
    }
  };

  // ======================================================================
  // RENDER: SETUP PHASE
  // ======================================================================
  if (phase === 'setup' || phase === 'generating') {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-6 font-sans">
        <div className="max-w-md w-full bg-white rounded-3xl p-8 shadow-xl border border-slate-100">
          <div className="w-16 h-16 bg-indigo-50 text-[#6b46c1] rounded-2xl flex items-center justify-center mb-6 mx-auto">
            <Target size={32} />
          </div>
          <h1 className="text-2xl font-black text-center text-slate-900 mb-2">Configure Your Quiz</h1>
          <p className="text-center text-slate-500 text-sm mb-8">Set your parameters to generate a targeted mastery assessment.</p>

          {error && <div className="bg-rose-50 text-rose-600 p-3 rounded-lg text-sm mb-6 text-center font-bold">{error}</div>}

          <div className="space-y-6">
            <div>
              <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-3 block">Difficulty</label>
              <div className="grid grid-cols-3 gap-3">
                {['easy', 'medium', 'hard'].map(lvl => (
                  <button key={lvl} onClick={() => setDifficulty(lvl)} disabled={phase === 'generating'} className={`py-3 rounded-xl text-xs font-bold capitalize border-2 transition-all ${difficulty === lvl ? 'border-[#6b46c1] bg-indigo-50/50 text-[#6b46c1]' : 'border-slate-100 text-slate-400 hover:border-slate-200'}`}>
                    {lvl}
                  </button>
                ))}
              </div>
            </div>

            <button onClick={handleGenerateQuiz} disabled={phase === 'generating'} className="w-full py-4 bg-[#6b46c1] text-white rounded-xl font-bold hover:bg-[#5b3da6] transition-all shadow-lg shadow-indigo-200 flex justify-center items-center gap-2 mt-4 disabled:opacity-70">
              {phase === 'generating' ? 'Compiling AI Quiz...' : 'Generate Quiz'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ======================================================================
  // RENDER: ACTIVE / SUBMITTING PHASE
  // ======================================================================
  if (phase === 'active' || phase === 'submitting') {
    const currentQuestion = quizData.questions[currentIndex];
    const isLastQuestion = currentIndex === quizData.questions.length - 1;
    const progressPercentage = ((currentIndex) / quizData.questions.length) * 100;

    return (
      <div className="min-h-screen bg-slate-50 flex flex-col font-sans relative pb-12">
        <header className="flex justify-between items-center px-8 py-6 w-full max-w-7xl mx-auto">
          <div className="flex items-center gap-2 text-[#6b46c1] font-bold text-xl tracking-tight">
            <div className="bg-[#6b46c1] p-1.5 rounded-lg text-white">
              <Brain className="w-5 h-5" />
            </div>
            MasteryAI
          </div>

          <div className="w-64 hidden sm:block">
            <div className="flex justify-between text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-2">
              <span>Question {currentIndex + 1} of {quizData.questions.length}</span>
              <span>{Math.round(progressPercentage)}% Complete</span>
            </div>
            <div className="h-1.5 w-full bg-slate-200 rounded-full overflow-hidden">
              <div className="h-full bg-[#6b46c1] transition-all duration-500 ease-out" style={{ width: `${progressPercentage}%` }}></div>
            </div>
          </div>
        </header>

        <main className="flex-grow flex flex-col items-center justify-center px-4 mt-8">
          <div className="bg-indigo-50 text-[#6b46c1] px-4 py-1.5 rounded-full text-[10px] font-black uppercase tracking-widest mb-6 border border-indigo-100/50">
            {currentSubject} - {currentQuestion.concept_label || humanizeConceptId(currentQuestion.concept_id, 'Concept')}
          </div>

          <h1 className="text-2xl md:text-3xl font-black text-slate-800 mb-8 text-center max-w-2xl leading-relaxed">
            {currentQuestion.text}
          </h1>

          <div className="bg-white rounded-3xl p-6 md:p-10 shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-slate-100 w-full max-w-3xl">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-10">
              {currentQuestion.options.map((option, i) => {
                // Determine 'A', 'B', 'C', 'D'
                const optionLetter = String.fromCharCode(65 + i); 
                // Safely grab the text from your JSON structure
                const optText = typeof option === 'string' ? option : option.text || option.value;
                // ðŸ‘‡ Now comparing the selected 'A'/'B' against this specific tile's letter
                const isSelected = selectedOption === optionLetter;
                
                return (
                  <div key={i} onClick={() => handleSelectOption(optionLetter)} className={`border-2 rounded-2xl p-5 flex items-center gap-4 cursor-pointer transition-all duration-200 ${isSelected ? 'border-[#6b46c1] bg-indigo-50/30' : 'border-slate-100 hover:border-slate-200 hover:bg-slate-50'}`}>
                    <div className={`w-5 h-5 rounded-full flex-shrink-0 flex items-center justify-center transition-colors ${isSelected ? 'border-[6px] border-[#6b46c1] bg-white' : 'border-2 border-slate-300 bg-white'}`}></div>
                    <div className="flex flex-col">
                      <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-0.5">Option {optionLetter}</span>
                      <span className={`text-sm font-bold ${isSelected ? 'text-[#6b46c1]' : 'text-slate-700'}`}>{optText}</span>
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="flex flex-col-reverse sm:flex-row justify-between items-center gap-6 pt-2">
              <button onClick={handleSkip} disabled={phase === 'submitting'} className="text-xs font-bold text-slate-400 hover:text-slate-600 transition-colors flex items-center gap-2 group">
                <ArrowLeft className="w-4 h-4 text-slate-300 group-hover:text-slate-500" /> I haven't learned this yet (Skip)
              </button>

              <button onClick={handleNextOrSubmit} disabled={!selectedOption || phase === 'submitting'} className={`py-3.5 px-8 rounded-xl font-bold text-sm transition-all flex items-center justify-center gap-2 w-full sm:w-auto ${selectedOption ? 'bg-[#6b46c1] hover:bg-[#5b3da6] text-white shadow-lg shadow-indigo-500/25 transform hover:-translate-y-0.5' : 'bg-slate-100 text-slate-400 cursor-not-allowed'}`}>
                {phase === 'submitting' ? 'Scoring...' : (isLastQuestion ? 'Submit Answer' : 'Next Question')}
                {(selectedOption || isLastQuestion) && phase !== 'submitting' && <ArrowRight className="w-4 h-4" />}
              </button>
            </div>
          </div>
        </main>
      </div>
    );
  }

  // ======================================================================
  // RENDER: RESULTS PHASE (YOUR CUSTOM UI)
  // ======================================================================
  if (phase === 'results' && formattedResults) {
    return (
      <div className="min-h-screen bg-slate-50 font-sans">
        <div className="max-w-7xl mx-auto px-6 py-8">
            <Breadcrumbs classLevel={formattedResults.paths.classLevel} topic={formattedResults.paths.topic} />

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-6">
                {/* Left Column - Main Results */}
                <div className="lg:col-span-2 flex flex-col">
                    <ScoreSummary data={formattedResults.summary} />

                    <div className="mb-4 flex items-center gap-2 mt-8">
                        <BarChart2 className="w-6 h-6 text-emerald-500" />
                        <h2 className="text-xl font-bold text-gray-900">Concept Mastery Breakdown</h2>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        {formattedResults.concepts.map(concept => (
                            <ConceptCard 
                              key={concept.id}
                              title={concept.title}
                              mastery={concept.mastery}
                              description={concept.description}
                            />
                        ))}
                    </div>
                </div>

                {/* Right Column - Sidebar */}
                <div className="lg:col-span-1 flex flex-col">
                    <AITutorInsights insights={formattedResults.aiInsights} />
                    <div className="mt-6">
                       <PathProgress
                         nextTopic={formattedResults.nextTopic}
                         nextTopicId={formattedResults.nextTopicId}
                         nextConcept={formattedResults.remediation?.nextConcept}
                         reason={formattedResults.remediation?.recommendationReason}
                         blockingPrerequisite={formattedResults.remediation?.blockingPrerequisite}
                         story={formattedResults.recommendationStory}
                         actionLabel={formattedResults.recommendationStory?.action_label}
                       />
                    </div>
                    {formattedResults.remediation?.weakestConcept && (
                      <div className="mt-6 rounded-2xl border border-rose-200 bg-rose-50 p-5">
                        <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-rose-500">Weakest concept</div>
                        <div className="mt-2 text-sm font-bold text-rose-900">{formattedResults.remediation.weakestConcept}</div>
                        {formattedResults.remediation.nextConcept && (
                          <p className="mt-2 text-xs leading-6 text-rose-800">
                            Best next focus: {formattedResults.remediation.nextConcept}
                          </p>
                        )}
                      </div>
                    )}
                </div>
            </div>

            <div className="mt-8">
              <FooterActions
                recommendedTopicId={formattedResults.nextTopicId}
                recommendedTopicTitle={formattedResults.nextTopic}
                explainState={formattedResults.explainState}
                actionLabel={formattedResults.recommendationStory?.action_label}
              />
            </div>
        </div>
      </div>
    );
  }

  return null;
};

export default QuizPage;

