import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useUser } from '../context/UserContext';
import CourseSidebar from '../components/CourseSidebar';
import { Menu, X, MessageSquare, Send, ChevronRight, BookOpen, Target } from 'lucide-react';

// Markdown & Math Rendering
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeRaw from 'rehype-raw';
import rehypeKatex from 'rehype-katex';

// CRITICAL: KaTeX Styles for Math Formulas
import 'katex/dist/katex.min.css';

import { API_URL as RUNTIME_API_URL } from '../config/runtime';
import { resolveStudentId } from '../utils/sessionIdentity';

const API_URL = RUNTIME_API_URL;
const safeArray = (value) => (Array.isArray(value) ? value : []);
const createMessageId = () => typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : `msg-${Date.now()}`;

const LessonPage = () => {
  const navigate = useNavigate();
  const { topicId } = useParams(); 
  const { token } = useAuth();
  const { studentData, userData } = useUser();
  const activeId = resolveStudentId(studentData, userData);

  const currentSubject = localStorage.getItem('active_subject') || studentData?.subjects?.[0] || 'math';
  const currentLevel = studentData?.sss_level || 'SSS1';
  const currentTerm = studentData?.current_term || 1;

  // --- UI STATE ---
  const [isSidebarOpen, setIsSidebarOpen] = useState(window.innerWidth > 1024);
  const [isChatOpen, setIsChatOpen] = useState(window.innerWidth > 1280); 

  // --- CORE DATA STATES ---
  const [bootstrap, setBootstrap] = useState(null);
  const [sidebarTopics, setSidebarTopics] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  // --- AI CHAT & ASSESSMENT STATES ---
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [pendingAssessment, setPendingAssessment] = useState(null);
  const [assessmentAnswer, setAssessmentAnswer] = useState('');
  
  const scrollRef = useRef(null);
  const streamingMessageRef = useRef(null);

  const lessonData = bootstrap?.lesson || null;

  // Fix for Markdown Tables & Common Math spacing issues
  const formatContent = (text) => {
    if (!text) return "";
    return text
      .replace(/\|\s*\|/g, '|\n|') // Fix broken tables
      .replace(/\\degree/g, '^\circ'); // Common fix for degree symbols if coming from LaTeX
  };

  // Auto-scroll chat
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isTyping, isChatOpen, pendingAssessment]);

  // Initial Cockpit Load
  useEffect(() => {
    if (!activeId || !token || !topicId) return;
    let cancelled = false;

    const initializeCockpit = async () => {
      setIsLoading(true);
      setError("");
      try {
        const response = await fetch(`${API_URL}/learning/lesson/cockpit`, {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({
            student_id: activeId,
            subject: currentSubject,
            sss_level: currentLevel,
            term: currentTerm,
            topic_id: topicId,
          })
        });

        if (!response.ok) throw new Error('Failed to load lesson cockpit.');
        const cockpitJson = await response.json();
        
        if (cancelled) return;

        const bootstrapJson = cockpitJson.tutor_bootstrap || {};
        setBootstrap(bootstrapJson);
        setSessionId(bootstrapJson.session_id);
        setPendingAssessment(bootstrapJson.pending_assessment || null);
        setSidebarTopics(safeArray(cockpitJson.topics));

        setMessages([{
          id: createMessageId(),
          role: 'assistant',
          content: bootstrapJson.greeting || 'Your lesson is ready. Let me know if you need any help!'
        }]);

      } catch (err) {
        if (!cancelled) setError(err.message || "Failed to load lesson.");
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };

    initializeCockpit();
    return () => { cancelled = true; };
  }, [topicId, activeId, token, currentSubject, currentLevel, currentTerm]);

  // --- STREAMING CHAT LOGIC ---
  const startStreamingMessage = () => {
    const id = createMessageId();
    streamingMessageRef.current = id;
    setMessages(prev => [...prev, { id, role: 'assistant', content: '', streaming: true }]);
    return id;
  };

  const updateStreamingMessage = (delta) => {
    const id = streamingMessageRef.current;
    if (!id || !delta) return;
    setMessages(prev => prev.map(item => item.id === id ? { ...item, content: `${item.content || ''}${delta}` } : item));
  };

  const finalizeStreamingMessage = (payload) => {
    const id = streamingMessageRef.current;
    if (!id) return;
    setMessages(prev => prev.map(item => item.id === id ? { 
      ...item, 
      content: payload.content || item.content,
      citations: payload.citations || [],
      prerequisite_warning: payload.prerequisite_warning || null,
      streaming: false 
    } : item));
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
          
          if (event === 'delta') updateStreamingMessage(data.content || '');
          if (event === 'message') finalizeStreamingMessage(data);
        }
      }
    } catch (err) {
      const id = streamingMessageRef.current;
      setMessages(prev => prev.map(item => item.id === id ? { ...item, content: "Error connecting to tutor.", streaming: false } : item));
    }
  };

  const handleSendMessage = async (e) => {
    if (e) e.preventDefault();
    if (!chatInput.trim() || !sessionId || isTyping) return;
    const studentMsg = chatInput.trim();
    setMessages(prev => [...prev, { id: createMessageId(), role: 'student', content: studentMsg }]);
    setChatInput("");
    setIsTyping(true);
    startStreamingMessage();
    await consumeStream({
      student_id: activeId,
      session_id: sessionId,
      subject: currentSubject,
      sss_level: currentLevel,
      term: currentTerm,
      topic_id: topicId,
      message: studentMsg
    });
    setIsTyping(false);
  };

  const submitAssessment = async () => {
    if (!pendingAssessment || !assessmentAnswer.trim() || isTyping) return;
    setIsTyping(true);
    try {
      const response = await fetch(`${API_URL}/tutor/assessment/submit`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          student_id: activeId,
          session_id: sessionId,
          assessment_id: pendingAssessment.assessment_id,
          subject: currentSubject,
          sss_level: currentLevel,
          term: currentTerm,
          topic_id: topicId,
          answer: assessmentAnswer.trim(),
        }),
      });
      const out = await response.json();
      setMessages(prev => [...prev, {
        id: createMessageId(),
        role: 'assistant',
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

  // --- CORE RENDERER (Updated with Math Support) ---
const renderContentBlock = (block, index) => {
    const type = block.type?.toLowerCase() || 'text';
    const markdownPlugins = [remarkGfm, remarkMath];
    const htmlPlugins = [rehypeRaw, rehypeKatex];

    // Shared prose classes for consistent high-quality typography
    const baseProse = "prose prose-slate max-w-none transition-all duration-200";
    const dynamicProse = "prose-headings:mt-8 prose-headings:mb-4 prose-headings:font-black prose-headings:text-slate-800 " +
                         "prose-p:leading-relaxed prose-p:mb-6 prose-p:text-slate-600 " +
                         "prose-li:my-2 prose-strong:text-indigo-700 " +
                         "prose-img:rounded-3xl prose-img:shadow-lg";

    switch (type) {
      case 'video':
        return (
          <div key={index} className="aspect-video bg-slate-900 rounded-2xl md:rounded-3xl mb-12 shadow-2xl overflow-hidden ring-1 ring-slate-200">
            {block.url ? <iframe src={block.url} className="w-full h-full" allowFullScreen title="Lesson Video"></iframe> : null}
          </div>
        );

      case 'example':
        const example = typeof block.value === 'object' ? block.value : { content: block.value };
        return (
          <div key={index} className="bg-indigo-50/50 border-l-4 border-indigo-600 p-6 md:p-8 rounded-r-3xl mb-10 shadow-sm">
            <div className="flex items-center gap-2 mb-4">
               <span className="px-2 py-1 bg-indigo-600 text-[10px] font-black text-white uppercase tracking-tighter rounded">Example</span>
            </div>
            <div className={`${baseProse} prose-indigo prose-sm md:prose-base ${dynamicProse}`}>
              <ReactMarkdown remarkPlugins={markdownPlugins} rehypePlugins={htmlPlugins}>
                {formatContent(example.prompt || example.content || "")}
              </ReactMarkdown>
            </div>
            {example.solution && (
              <div className="mt-6 p-5 bg-white rounded-2xl border border-indigo-100 shadow-sm">
                <span className="text-[10px] font-bold text-indigo-400 uppercase tracking-widest block mb-2">Detailed Solution</span>
                <div className={`${baseProse} prose-indigo prose-sm ${dynamicProse}`}>
                  <ReactMarkdown remarkPlugins={markdownPlugins} rehypePlugins={htmlPlugins}>
                    {formatContent(example.solution)}
                  </ReactMarkdown>
                </div>
              </div>
            )}
          </div>
        );

      case 'exercise':
        const exercise = typeof block.value === 'object' ? block.value : { question: block.value };
        return (
          <div key={index} className="bg-emerald-50/50 border-l-4 border-emerald-600 p-6 md:p-8 rounded-r-3xl mb-10 shadow-sm">
            <div className="flex items-center gap-2 mb-4">
               <span className="px-2 py-1 bg-emerald-600 text-[10px] font-black text-white uppercase tracking-tighter rounded">Practice</span>
            </div>
            <div className={`${baseProse} prose-emerald prose-sm md:prose-base ${dynamicProse}`}>
              <ReactMarkdown remarkPlugins={markdownPlugins} rehypePlugins={htmlPlugins}>
                {formatContent(exercise.question || exercise.content || "")}
              </ReactMarkdown>
            </div>
          </div>
        );

      default:
        const textContent = typeof block.value === 'object' ? (block.value.note || block.value.content || "") : block.value;
        return (
          <div key={index} className={`${baseProse} lg:prose-lg mb-12 dark:prose-invert ${dynamicProse}`}>
            <ReactMarkdown remarkPlugins={markdownPlugins} rehypePlugins={htmlPlugins}>
              {formatContent(textContent)}
            </ReactMarkdown>
          </div>
        );
    }
  };

  return (
    <div className="flex bg-slate-50 h-[calc(100vh-64px)] overflow-hidden relative">
      
      {/* SIDEBAR */}
      <div className={`bg-white border-r border-slate-200 transition-all duration-300 flex-shrink-0 z-50 fixed inset-y-0 left-0 lg:relative ${isSidebarOpen ? 'w-72 translate-x-0' : 'w-0 -translate-x-full lg:translate-x-0 overflow-hidden'}`}>
        <CourseSidebar activeStep={topicId} subject={currentSubject} level={currentLevel} topics={sidebarTopics} />
      </div>

      {/* MAIN CONTENT AREA */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <div className="h-14 border-b border-slate-200 bg-white flex items-center justify-between px-4 flex-shrink-0">
          <button onClick={() => setIsSidebarOpen(!isSidebarOpen)} className="p-2 hover:bg-slate-100 rounded-lg text-slate-500 transition-colors flex items-center gap-2">
            <Menu size={20} />
            <span className="hidden sm:inline text-xs font-bold uppercase tracking-wider">Syllabus</span>
          </button>
          {!isChatOpen && (
            <button onClick={() => setIsChatOpen(true)} className="p-2 hover:bg-indigo-50 rounded-lg text-indigo-600 transition-colors flex items-center gap-2">
              <span className="hidden sm:inline text-xs font-bold uppercase tracking-wider">AI Tutor</span>
              <MessageSquare size={20} />
            </button>
          )}
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-8 md:px-12 scroll-smooth">
          <div className="max-w-3xl mx-auto">
            {isLoading ? (
               <div className="animate-pulse space-y-8 mt-10">
                 <div className="h-8 bg-slate-200 rounded w-1/2"></div>
                 <div className="h-4 bg-slate-200 rounded w-full"></div>
                 <div className="h-4 bg-slate-200 rounded w-5/6"></div>
                 <div className="aspect-video bg-slate-200 rounded-3xl w-full"></div>
               </div>
            ) : lessonData ? (
              <>
                <h1 className="text-3xl md:text-4xl font-black text-slate-900 mb-6 tracking-tight">{lessonData.title}</h1>
                <div className="space-y-2">
                  {lessonData.content_blocks?.map((block, index) => renderContentBlock(block, index))}
                </div>
                <div className="flex flex-col sm:flex-row justify-between items-center gap-4 pt-12 border-t border-slate-200 pb-20 mt-16">
                  <button onClick={() => navigate(`/course/${currentSubject}`)} className="text-sm text-slate-500 font-bold hover:text-slate-800">← Back to Syllabus</button>
                  <button onClick={() => navigate(`/quiz/${topicId}`)} className="bg-indigo-600 text-white px-8 py-3 rounded-xl font-bold hover:bg-indigo-700 shadow-lg shadow-indigo-100">Take Mastery Quiz →</button>
                </div>
              </>
            ) : <p className="text-center mt-20 text-slate-400">Select a topic to begin.</p>}
          </div>
        </div>
      </div>

      {/* AI CHAT PANEL */}
      <div className={`bg-white border-l border-slate-200 transition-all duration-300 flex-shrink-0 flex flex-col fixed inset-y-0 right-0 z-50 lg:relative ${isChatOpen ? 'w-full sm:w-[400px] translate-x-0' : 'w-0 translate-x-full lg:hidden'}`}>
        <div className="p-4 border-b border-slate-100 flex items-center justify-between bg-indigo-50/30">
          <h3 className="text-sm font-bold text-slate-900">AI Tutor</h3>
          <button onClick={() => setIsChatOpen(false)} className="text-slate-400 hover:text-slate-600 p-2"><X size={20} /></button>
        </div>

        <div ref={scrollRef} className="flex-1 p-4 overflow-y-auto space-y-4 bg-white">
          {messages.map((msg, i) => (
            <div key={msg.id || i} className={`p-4 rounded-2xl max-w-[90%] text-sm ${msg.role === 'student' ? 'bg-indigo-600 text-white ml-auto rounded-tr-sm' : 'bg-slate-50 border border-slate-100 text-slate-700 mr-auto rounded-tl-sm shadow-sm'}`}>
              {msg.role === 'assistant' ? (
                <div className="prose prose-sm prose-slate max-w-none">
                  <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeRaw, rehypeKatex]}>
                    {formatContent(msg.content)}
                  </ReactMarkdown>
                </div>
              ) : msg.content}
            </div>
          ))}
          {isTyping && <div className="text-xs text-slate-400 animate-pulse ml-2">Tutor is thinking...</div>}
          
          {pendingAssessment && (
            <div className="bg-emerald-50 border border-emerald-100 p-5 rounded-2xl mt-4">
              <div className="flex items-center gap-2 mb-3 text-emerald-600 font-bold text-[10px] uppercase tracking-widest"><Target size={14}/> Checkpoint</div>
              <p className="text-sm font-semibold text-emerald-900 mb-4">{pendingAssessment.question}</p>
              <textarea className="w-full text-sm p-3 rounded-xl border border-emerald-200 focus:ring-2 focus:ring-emerald-500 outline-none mb-3" rows={3} placeholder="Your answer..." value={assessmentAnswer} onChange={(e) => setAssessmentAnswer(e.target.value)} disabled={isTyping} />
              <button onClick={submitAssessment} disabled={isTyping || !assessmentAnswer.trim()} className="w-full bg-emerald-600 text-white font-bold py-3 rounded-xl hover:bg-emerald-700 disabled:opacity-50 transition-all">Submit Answer</button>
            </div>
          )}
        </div>

        <div className="p-4 border-t border-slate-100 bg-white pb-8">
          <form onSubmit={handleSendMessage} className="relative">
            <input type="text" value={chatInput} onChange={(e) => setChatInput(e.target.value)} disabled={isTyping || !sessionId} placeholder="Ask me anything..." className="w-full pl-4 pr-12 py-3.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-indigo-600 outline-none" />
            <button type="submit" disabled={!chatInput.trim() || isTyping} className="absolute right-2 top-1/2 -translate-y-1/2 w-8 h-8 bg-indigo-600 text-white rounded-lg flex items-center justify-center disabled:bg-slate-300"><Send size={14} /></button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default LessonPage;