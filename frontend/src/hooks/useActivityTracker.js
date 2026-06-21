import { useEffect, useRef } from 'react';
import { API_URL } from '../config/runtime';

export const useActivityTracker = (studentId, token, eventType, refId, subject, term) => {
  const startTimeRef = useRef(Date.now());

  useEffect(() => {
    return () => {
      const endTime = Date.now();
      const durationSeconds = Math.floor((endTime - startTimeRef.current) / 1000);

      if (durationSeconds > 5 && studentId && token) {
        fetch(`${API_URL}/learning/activity/log`, {
          method: 'POST',
          headers: { 
            'Authorization': `Bearer ${token}`, 
            'Content-Type': 'application/json' 
          },
          keepalive: true, 
          body: JSON.stringify({
            student_id: studentId,
            subject: subject || 'civic',
            term: term || 1,
            event_type: eventType, // 'tutor_session', 'quiz_submitted', etc.
            ref_id: refId,
            duration_seconds: durationSeconds
          })
        }).catch(err => console.error("Failed to log activity:", err));
      }
    };
  }, [studentId, token, eventType, refId, subject, term]);
};