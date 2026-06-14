import React, { useState, useEffect, useRef } from 'react';
import { X, Send, Target, Maximize2, Minimize2, Sparkles, Mic, MicOff, Volume2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeRaw from 'rehype-raw';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';

import { API_URL as RUNTIME_API_URL, AI_CORE_URL as RUNTIME_AI_CORE_URL } from '../../config/runtime';

const API_URL = RUNTIME_API_URL;
const AI_CORE_URL = RUNTIME_AI_CORE_URL;
const createMessageId = () => typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : `msg-${Date.now()}`;

// --- QUICK ACTIONS DEFINITION ---
const QUICK_ACTIONS = [
  { label: "Teach Me", prompt: "Teach me the core concepts of this lesson." },
  { label: "Quiz Me", prompt: "Quiz me on this lesson." },
  { label: "Quick Recap", prompt: "Give me a quick recap of this topic." },
  { label: "Exam Practice", prompt: "Give me a WAEC-style practice question." },
  { label: "Why does this matter?", prompt: "Explain why learning this topic is important." }
];

// --- INTERACTIVE WIDGET COMPONENT ---
const InteractiveQuizWidget = ({ widgetData, onAnswerSubmit, disabled }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!widgetData || widgetData.type !== 'multiple_choice') return null;

  const WidgetContent = ({ isExpandedView }) => (
    <div className={`w-full bg-white ${isExpandedView ? 'h-full flex flex-col justify-center max-w-4xl mx-auto p-6 md:p-12' : 'mt-3 border border-indigo-100 rounded-xl overflow-hidden shadow-sm'}`}>
      <div className={`${isExpandedView ? 'mb-8 md:mb-12' : 'bg-indigo-50 px-4 py-3 border-b border-indigo-100 relative'}`}>
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2 text-indigo-700 font-black text-[10px] uppercase tracking-widest">
            <Target size={12}/> Quick Check
          </div>
          {!isExpandedView && (
            <button
              onClick={() => setIsExpanded(true)}
              className="text-indigo-400 hover:text-indigo-700 transition-colors bg-transparent border-none p-1"
              title="Expand question"
            >
              <Maximize2 size={14} />
            </button>
          )}
        </div>
        <p className={`${isExpandedView ? 'text-2xl md:text-4xl leading-tight' : 'text-sm'} font-semibold text-slate-800`}>
          {widgetData.question}
        </p>
      </div>
      <div className={`${isExpandedView ? 'space-y-4' : 'p-2 space-y-1.5'}`}>
        {widgetData.options.map((option, idx) => (
          <button
            key={idx}
            disabled={disabled}
            onClick={() => {
              onAnswerSubmit(option);
              if (isExpandedView) setIsExpanded(false);
            }}
            className={`w-full text-left transition-all duration-200 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed
              ${isExpandedView
                ? 'px-6 py-5 text-lg md:text-xl border-2 border-slate-200 hover:border-indigo-600 hover:bg-indigo-50 hover:text-indigo-700 shadow-sm hover:shadow-md font-medium'
                : 'px-4 py-2.5 text-sm text-slate-700 hover:bg-indigo-50 hover:text-indigo-700 border border-transparent hover:border-indigo-200'
              }`}
          >
            {option}
          </button>
        ))}
      </div>
    </div>
  );

  return (
    <>
      <WidgetContent isExpandedView={false} />
      {isExpanded && (
        <div className="fixed inset-0 z-[9999] bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 sm:p-8 animate-in fade-in duration-200">
          <div className="bg-white w-full h-full md:h-auto md:min-h-[60vh] md:max-h-[90vh] rounded-2xl md:rounded-3xl shadow-2xl overflow-y-auto relative flex flex-col">
            <button
              onClick={() => setIsExpanded(false)}
              className="absolute top-4 right-4 md:top-8 md:right-8 p-3 bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-full transition-colors z-10"
            >
              <Minimize2 size={24} />
            </button>
            <div className="flex-1 overflow-y-auto flex flex-col justify-center">
              <WidgetContent isExpandedView={true} />
            </div>
          </div>
        </div>
      )}
    </>
  );
};

// --- MAIN AI TUTOR PANEL COMPONENT ---
const AITutorPanel = ({
    activeId,
    token,
    sessionId,
    currentSubject,
    currentLevel,
    currentTerm,
    topicId,
    initialGreeting,
    initialPendingAssessment,
    isMaximized,
    onToggleMaximize,
    onClose
}) => {

  const [messages, setMessages] = useState([
      { id: createMessageId(), role: 'assistant', content: initialGreeting || 'Your lesson is ready. Let me know if you need any help!' }
  ]);
  const [chatInput, setChatInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [pendingAssessment, setPendingAssessment] = useState(initialPendingAssessment);
  const [assessmentAnswer, setAssessmentAnswer] = useState('');

  // --- NEW: AUDIO RECORDING & SPEECH STATES ---
  const [isRecording, setIsRecording] = useState(false);
  const [isTutorSpeaking, setIsTutorSpeaking] = useState(false);
  
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const scrollRef = useRef(null);
  const streamingMessageRef = useRef(null);

  const formatContent = (text) => {
    if (!text) return "";
    return text.replace(/\|\s*\|/g, '|\n|').replace(/\\degree/g, '^\circ');
  };

  useEffect(() => {
    setMessages([
      { 
        id: createMessageId(), 
        role: 'assistant', 
        content: initialGreeting || 'Your lesson is ready. Let me know if you need any help!' 
      }
    ]);
    setPendingAssessment(initialPendingAssessment);
    setChatInput("");
    setAssessmentAnswer("");
    
    // Stop any ongoing speech when the topic changes
    window.speechSynthesis.cancel();
    setIsTutorSpeaking(false);
  }, [topicId, initialGreeting, initialPendingAssessment]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, isTyping, pendingAssessment, isRecording, isTutorSpeaking]);

  const startStreamingMessage = () => {
    const id = createMessageId();
    streamingMessageRef.current = id;
    setMessages(prev => [...prev, { id, role: 'assistant', content: '', streaming: true }]);
    return id;
  };

  const updateStreamingMessage = (text) => {
    const id = streamingMessageRef.current;
    if (!id) return;
    setMessages(prev => prev.map(item => item.id === id ? { ...item, content: text, streaming: false } : item));
    streamingMessageRef.current = null;
  };

  const consumeStream = async (payload) => {
    try {
      const response = await fetch(`${API_URL}/tutor/chat/stream`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error('Stream failed');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split('\n\n');
        buffer = events.pop() || '';

        for (const block of events) {
          const lines = block.split('\n');
          const dataLine = lines.find(l => l.startsWith('data:'))?.replace('data:', '').trim() || '{}';
          const event = lines.find(l => l.startsWith('event:'))?.replace('event:', '').trim();
          const data = JSON.parse(dataLine);

          if (event === 'delta') {
            const id = streamingMessageRef.current;
            setMessages(prev => prev.map(item => item.id === id ? { ...item, content: `${item.content || ''}${data.content || ''}` } : item));
          }
          if (event === 'message') {
            const id = streamingMessageRef.current;
            setMessages(prev => prev.map(item => item.id === id ? {
              ...item,
              content: data.assistant_message || data.content || item.content,
              interactive_widget: data.interactive_widget || null,
              streaming: false
            } : item));
            streamingMessageRef.current = null;
          }
        }
      }
    } catch (err) {
      const id = streamingMessageRef.current;
      setMessages(prev => prev.map(item => item.id === id ? { ...item, content: "Error connecting to tutor.", streaming: false } : item));
    }
  };

  const triggerChatRequest = async (studentMsg) => {
    if (!studentMsg.trim() || !sessionId || isTyping) return;
    
    // Interrupt any active tutor speech context
    window.speechSynthesis.cancel();
    setIsTutorSpeaking(false);

    setMessages(prev => [...prev, { id: createMessageId(), role: 'student', content: studentMsg }]);
    setChatInput("");
    setIsTyping(true);
    startStreamingMessage();
    await consumeStream({
      student_id: activeId, session_id: sessionId, subject: currentSubject,
      sss_level: currentLevel, term: currentTerm, topic_id: topicId, message: studentMsg
    });
    setIsTyping(false);
  };

  const handleSendMessage = (e) => {
    if (e) e.preventDefault();
    triggerChatRequest(chatInput);
  };

  // --- NEW: TURN-BASED VOICE PROCESSING PIPELINE ---
  const startAudioRecording = async () => {
    try {
      window.speechSynthesis.cancel();
      setIsTutorSpeaking(false);
      
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunksRef.current = [];
      
      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        await sendAudioTurnToBackend(audioBlob);
        
        // Clear audio track allocations
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorderRef.current = recorder;
      recorder.start();
      setIsRecording(true);
    } catch (err) {
      console.error("Microphone initialization error:", err);
    }
  };

  const stopAudioRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  const toggleVoiceMode = () => {
    if (isRecording) {
      stopAudioRecording();
    } else {
      startAudioRecording();
    }
  };

  const sendAudioTurnToBackend = async (audioBlob) => {
    setIsTyping(true);
    
    // Add visual structural turn for the student audio payload
    const tempId = createMessageId();
    setMessages(prev => [...prev, { id: tempId, role: 'student', content: "🎙️ *Transcribing voice...*" }]);
    
    const formData = new FormData();
    formData.append("audio_file", audioBlob, "turn.webm");
    
    // 🔥 ADD ALL MISSING CONTEXT VARIABLES HERE 🔥
    formData.append("student_id", activeId);
    formData.append("session_id", sessionId);
    formData.append("subject", currentSubject);
    formData.append("sss_level", currentLevel);
    formData.append("term", currentTerm);
    formData.append("topic_id", topicId);

    startStreamingMessage();

    try {
      const response = await fetch(`${AI_CORE_URL}/tutor/voice-turn`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData
      });

      const data = await response.json();
      
      if (data.text) {
        // Update the placeholder to show what the student actually said
        if (data.transcription) {
             setMessages(prev => prev.map(msg => 
                 msg.id === tempId ? { ...msg, content: `🎙️ "${data.transcription}"` } : msg
             ));
        }

        updateStreamingMessage(data.text);
        triggerNativeTTS(data.text);
      } else if (data.error) {
        updateStreamingMessage(`⚠️ Error processing voice turn: ${data.error}`);
      }
    } catch (err) {
      console.error("Voice dispatch exception:", err);
      updateStreamingMessage("❌ Failed to reach the voice engine endpoint.");
    } finally {
      setIsTyping(false);
    }
  };

  const triggerNativeTTS = (textToSpeak) => {
    if (!textToSpeak) return;
    
    // Clean markdown characters out of speech output strings
    const cleanText = textToSpeak.replace(/[*#_`~\-]/g, '');
    
    const utterance = new SpeechSynthesisUtterance(cleanText);
    
    utterance.onstart = () => setIsTutorSpeaking(true);
    utterance.onend = () => setIsTutorSpeaking(false);
    utterance.onerror = () => setIsTutorSpeaking(false);
    
    window.speechSynthesis.speak(utterance);
  };

  const handleWidgetSubmit = async (selectedOption) => {
    if (isTyping) return;
    window.speechSynthesis.cancel();
    setIsTutorSpeaking(false);

    setMessages(prev => [...prev, { id: createMessageId(), role: 'student', content: `I select: ${selectedOption}` }]);
    setIsTyping(true);
    startStreamingMessage();
    await consumeStream({
      student_id: activeId, session_id: sessionId, subject: currentSubject,
      sss_level: currentLevel, term: currentTerm, topic_id: topicId,
      message: `I select: ${selectedOption}. Was I correct? Explain why.`
    });
    setIsTyping(false);
  };

  const submitAssessment = async () => {
    if (!pendingAssessment || !assessmentAnswer.trim() || isTyping) return;
    window.speechSynthesis.cancel();
    setIsTutorSpeaking(false);
    setIsTyping(true);
    try {
      const response = await fetch(`${API_URL}/tutor/assessment/submit`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          student_id: activeId, session_id: sessionId, assessment_id: pendingAssessment.assessment_id,
          subject: currentSubject, sss_level: currentLevel, term: currentTerm,
          topic_id: topicId, answer: assessmentAnswer.trim(),
        }),
      });
      const out = await response.json();
      setMessages(prev => [...prev, {
        id: createMessageId(), role: 'assistant',
        content: `**Checkpoint Result:** ${out.is_correct ? 'Great job!' : 'Not quite.'}\n\n${out.feedback}`
      }]);
      setPendingAssessment(null);
      setAssessmentAnswer('');
    } catch (err) {
      setMessages(prev => [...prev, { role: 'assistant', content: "Failed to submit checkpoint." }]);
    } finally {
      setIsTyping(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-white w-full">
        {/* HEADER */}
        <div className="p-4 border-b border-slate-100 flex items-center justify-between bg-indigo-50/30">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-bold text-slate-900">AI Tutor</h3>
            {isRecording && (
              <span className="flex items-center gap-1.5 text-[10px] bg-red-100 text-red-600 px-2 py-0.5 rounded-full font-black animate-pulse">
                <div className="w-1.5 h-1.5 bg-red-600 rounded-full"></div> LISTENING
              </span>
            )}
            {isTutorSpeaking && (
              <span className="flex items-center gap-1.5 text-[10px] bg-emerald-100 text-emerald-600 px-2 py-0.5 rounded-full font-black">
                <Volume2 size={10} className="animate-bounce" /> SPEAKING
              </span>
            )}
          </div>
          <div className="flex items-center gap-1">
            <button onClick={onToggleMaximize} className="text-slate-400 hover:text-slate-600 p-2 transition-colors" title="Toggle Fullscreen">
              {isMaximized ? <Minimize2 size={18} /> : <Maximize2 size={18} />}
            </button>
            <button onClick={onClose} className="text-slate-400 hover:text-slate-600 p-2 transition-colors" title="Close">
              <X size={20} />
            </button>
          </div>
        </div>

        {/* CHAT FEED */}
        <div ref={scrollRef} className="flex-1 p-4 overflow-y-auto space-y-4 bg-white pb-6">
          {messages.map((msg, i) => (
            <div key={msg.id || i} className={`flex flex-col max-w-[90%] ${msg.role === 'student' ? 'ml-auto' : 'mr-auto'}`}>
                <div className={`p-4 rounded-2xl text-sm ${msg.role === 'student' ? 'bg-indigo-600 text-white rounded-tr-sm' : 'bg-slate-50 border border-slate-100 text-slate-700 rounded-tl-sm shadow-sm'}`}>
                  {msg.role === 'assistant' ? (
                    <div className="prose prose-sm prose-slate max-w-none">
                      <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeRaw, rehypeKatex]}>
                        {formatContent(msg.content)}
                      </ReactMarkdown>
                    </div>
                  ) : msg.content}
                </div>

                {msg.role === 'assistant' && msg.interactive_widget && (
                  <InteractiveQuizWidget
                    widgetData={msg.interactive_widget}
                    onAnswerSubmit={handleWidgetSubmit}
                    disabled={isTyping}
                  />
                )}
            </div>
          ))}

          {/* TURN-BASED AUDIO METRICS CONSOLE */}
          {(isRecording || isTutorSpeaking) && (
             <div className="flex items-center gap-3 p-4 bg-indigo-50/50 border border-indigo-100 rounded-2xl mx-auto w-fit">
                <Volume2 size={16} className={isTutorSpeaking ? "text-indigo-600 animate-bounce" : "text-red-500 animate-pulse"} />
                <span className="text-xs font-bold text-indigo-700 uppercase tracking-widest">
                  {isTutorSpeaking ? "Tutor is speaking..." : "Recording your voice... Click Mic again to send"}
                </span>
             </div>
          )}

          {isTyping && !isRecording && <div className="text-xs text-slate-400 animate-pulse ml-2">Tutor is thinking...</div>}

          {/* PENDING ASSESSMENT */}
          {pendingAssessment && (
            <div className="bg-emerald-50 border border-emerald-100 p-5 rounded-2xl mt-4">
              <div className="flex items-center gap-2 mb-3 text-emerald-600 font-bold text-[10px] uppercase tracking-widest"><Target size={14}/> Checkpoint</div>
              <p className="text-sm font-semibold text-emerald-900 mb-4">{pendingAssessment.question}</p>
              <textarea className="w-full text-sm p-3 rounded-xl border border-emerald-200 focus:ring-2 focus:ring-emerald-500 outline-none mb-3" rows={3} placeholder="Your answer..." value={assessmentAnswer} onChange={(e) => setAssessmentAnswer(e.target.value)} disabled={isTyping} />
              <button onClick={submitAssessment} disabled={isTyping || !assessmentAnswer.trim()} className="w-full bg-emerald-600 text-white font-bold py-3 rounded-xl hover:bg-emerald-700 disabled:opacity-50 transition-all">Submit Answer</button>
            </div>
          )}
        </div>

        {/* INPUT AREA WITH QUICK ACTIONS */}
        <div className="border-t border-slate-100 bg-white">
          <div className="px-4 py-3 bg-slate-50/50 overflow-x-auto whitespace-nowrap scrollbar-hide flex gap-2">
             <div className="flex items-center gap-2 text-xs font-bold text-slate-400 uppercase tracking-widest mr-2">
                <Sparkles size={12} /> Actions
             </div>
             {QUICK_ACTIONS.map((action, idx) => (
                <button
                  key={idx}
                  disabled={isTyping || isRecording}
                  onClick={() => triggerChatRequest(action.prompt)}
                  className="inline-block px-3 py-1.5 bg-white border border-slate-200 text-slate-600 text-xs font-medium rounded-full hover:bg-indigo-50 hover:text-indigo-700 hover:border-indigo-200 transition-colors disabled:opacity-50 flex-shrink-0 shadow-sm"
                >
                  {action.label}
                </button>
             ))}
          </div>

          <div className="p-4 flex gap-2 max-w-4xl mx-auto pt-2">
            <form onSubmit={handleSendMessage} className="relative flex-1">
              <input 
                type="text" 
                value={chatInput} 
                onChange={(e) => setChatInput(e.target.value)} 
                disabled={isTyping || !sessionId || isRecording} 
                placeholder={isRecording ? "Recording session active..." : "Ask me anything..."} 
                className="w-full pl-4 pr-12 py-3.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-indigo-600 outline-none disabled:opacity-60" 
              />
              <button 
                type="submit" 
                disabled={!chatInput.trim() || isTyping || isRecording} 
                className="absolute right-2 top-1/2 -translate-y-1/2 w-8 h-8 bg-indigo-600 text-white rounded-lg flex items-center justify-center disabled:bg-slate-300 transition-colors hover:bg-indigo-700"
              >
                <Send size={14} />
              </button>
            </form>

            {/* VOICE TOGGLE BUTTON */}
            <button
                type="button"
                onClick={toggleVoiceMode}
                disabled={!sessionId || (isTyping && !isRecording)}
                className={`w-12 h-12 rounded-xl flex items-center justify-center transition-all shadow-sm ${
                    isRecording 
                    ? 'bg-red-500 text-white shadow-red-200 ring-4 ring-red-50' 
                    : 'bg-slate-100 text-slate-500 hover:bg-indigo-50 hover:text-indigo-600'
                }`}
            >
                {isRecording ? <MicOff size={20} /> : <Mic size={20} />}
            </button>
          </div>
        </div>
      </div>
  );
};

export default AITutorPanel;