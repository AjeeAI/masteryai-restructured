import React, { useState, useEffect } from 'react';
import { useUser } from '../context/UserContext';
import { useAuth } from '../context/AuthContext';
import { Flame, Star, CheckCircle2, Clock } from 'lucide-react';
import StatCard from './StatCard';
import { API_URL } from '../config/runtime';

const DashboardStats = () => {
  const { studentData } = useUser();
  const { token } = useAuth();
  
  // State to hold the fetched stats
  const [liveStats, setLiveStats] = useState({
    streak: 0,
    masteryPoints: 0,
    conceptsMastered: 0,
    totalConcepts: 0,
    studyTimeMinutes: 0
  });

  useEffect(() => {
    const fetchMyStats = async () => {
      if (!token) return;
      
      try {
        // Hitting your dedicated, native stats endpoint
        const response = await fetch(`${API_URL}/students/stats`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (response.ok) {
          const myData = await response.json();
          
          setLiveStats({
            // These keys exactly match your StudentStatsOut Pydantic model
            streak: myData.streak || 0, 
            masteryPoints: myData.mastery_points || 0,
            conceptsMastered: studentData?.concepts_mastered || 0, // Fallback if not in API
            totalConcepts: studentData?.total_concepts || 0,
            studyTimeMinutes: myData.study_time_seconds ? Math.floor(myData.study_time_seconds / 60) : 0
          });
        }
      } catch (err) {
        console.error("Failed to fetch live stats for dashboard", err);
      }
    };

    fetchMyStats();
  }, [token, studentData]);

  const formatStudyTime = (totalMinutes) => {
    if (!totalMinutes) return "0h 0m";
    const hours = Math.floor(totalMinutes / 60);
    const minutes = totalMinutes % 60;
    return hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`;
  };

  return (
    <div className="mb-6 grid grid-cols-2 gap-3 md:gap-4 xl:grid-cols-4">
      <StatCard 
        icon={Flame} 
        iconBg="bg-orange-50" 
        iconColor="text-orange-500" 
        title="Study Streak" 
        value={`${liveStats.streak} Days`} 
        subtext={liveStats.streak > 0 ? "Keep it up!" : "Start today!"} 
        subtextColor={liveStats.streak > 0 ? "text-orange-500" : "text-gray-400"} 
      />
      
      <StatCard 
        icon={Star} 
        iconBg="bg-yellow-50" 
        iconColor="text-yellow-500" 
        title="Mastery Points" 
        value={liveStats.masteryPoints.toLocaleString()} 
        subtext="Total earned" 
        subtextColor="text-gray-400" 
      />
      
      <StatCard 
        icon={CheckCircle2} 
        iconBg="bg-green-50" 
        iconColor="text-green-500" 
        title="Concepts" 
        value={`${liveStats.conceptsMastered} / ${liveStats.totalConcepts}`} 
        subtext="Mastered"
        subtextColor="text-gray-400"
      />
      
      <StatCard 
        icon={Clock} 
        iconBg="bg-blue-50" 
        iconColor="text-blue-500" 
        title="Study Time" 
        value={formatStudyTime(liveStats.studyTimeMinutes)} 
        subtext="All time" 
        subtextColor="text-gray-400" 
      />
    </div>
  );
};

export default DashboardStats;