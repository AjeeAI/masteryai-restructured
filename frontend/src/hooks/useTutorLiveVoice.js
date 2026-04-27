import { useState, useRef, useCallback } from 'react';

export const useTutorLiveVoice = (sessionId, token, subject, modelTier = 'flash') => {
  const [isVoiceActive, setIsVoiceActive] = useState(false);
  const [isTutorSpeaking, setIsTutorSpeaking] = useState(false);
  
  const socketRef = useRef(null);
  const audioContextRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const streamRef = useRef(null);

  // Initialize the Audio Context for playback
  const initAudioContext = () => {
    if (!audioContextRef.current) {
      audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)({
        sampleRate: 24000, // Gemini 3 typically uses 24kHz
      });
    }
    if (audioContextRef.current.state === 'suspended') {
      audioContextRef.current.resume();
    }
  };

  const startVoiceSession = useCallback(async (onTextUpdate) => {
    initAudioContext();
    
    // 1. Setup WebSocket URL (Bridging to your new FastAPI endpoint)
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host; 
    const wsUrl = `${protocol}//${host}/api/v1/tutor/live-voice/${sessionId}?subject=${subject}&model_tier=${modelTier}`;

    socketRef.current = new WebSocket(wsUrl);
    socketRef.current.binaryType = 'arraybuffer';

    socketRef.current.onmessage = async (event) => {
      if (typeof event.data === 'string') {
        const data = JSON.parse(event.data);
        if (data.text) onTextUpdate(data.text);
      } else {
        // Handle binary audio chunk from Gemini
        playAudioChunk(event.data);
      }
    };

    // 2. Setup Microphone Stream
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    streamRef.current = stream;
    
    // We use audio/webm as it is the most stable across Brave/Chrome for raw chunks
    mediaRecorderRef.current = new MediaRecorder(stream, { mimeType: 'audio/webm' });

    mediaRecorderRef.current.ondataavailable = (event) => {
      if (event.data.size > 0 && socketRef.current?.readyState === WebSocket.OPEN) {
        socketRef.current.send(event.data);
      }
    };

    // Send audio chunks every 100ms for ultra-low latency
    mediaRecorderRef.current.start(100);
    setIsVoiceActive(true);
  }, [sessionId, subject, modelTier]);

  const playAudioChunk = async (arrayBuffer) => {
    setIsTutorSpeaking(true);
    const audioBuffer = await audioContextRef.current.decodeAudioData(arrayBuffer);
    const source = audioContextRef.current.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(audioContextRef.current.destination);
    source.onended = () => setIsTutorSpeaking(false);
    source.start();
  };

  const stopVoiceSession = () => {
    mediaRecorderRef.current?.stop();
    streamRef.current?.getTracks().forEach(track => track.stop());
    socketRef.current?.close();
    setIsVoiceActive(false);
  };

  return { isVoiceActive, isTutorSpeaking, startVoiceSession, stopVoiceSession };
};