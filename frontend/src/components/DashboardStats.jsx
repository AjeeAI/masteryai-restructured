import React from 'react';
import { useUser } from '../context/UserContext';
import { useAuth } from '../context/AuthContext';
import { useQuery } from '@tanstack/react-query';
import { Flame, Star, CheckCircle2, Clock, Loader2 } from 'lucide-react';
import StatCard from './StatCard';
import { API_URL } from '../config/runtime';

const DashboardStats = () => {
  const { studentData } = useUser();
  const { token } = useAuth();

  // 🔥 Upgraded to TanStack Query!
  const { data: liveStats, isLoading } = useQuery({
    queryKey: ['studentStats'],
    queryFn: async () => {
      const response = await fetch(`${API_URL}/students/stats`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (!response.ok) throw new Error("Failed to fetch live stats");
      return response.json();
    },
    // Only run the query if we have a token
    enabled: !!token,
    // The select transformer cleanly maps your backend Pydantic model to your frontend variables
    select: (myData) => ({
      streak: myData.streak || 0, 
      masteryPoints: myData.mastery_points || 0,
      conceptsMastered: studentData?.concepts_mastered || 0,
      totalConcepts: studentData?.total_concepts || 0,
      studyTimeMinutes: myData.study_time_seconds ? Math.floor(myData.study_time_seconds / 60) : 0
    })
  });

  const formatStudyTime = (totalMinutes) => {
    if (!totalMinutes) return "0h 0m";
    const hours = Math.floor(totalMinutes / 60);
    const minutes = totalMinutes % 60;
    return hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`;
  };

  // Safe fallback while TanStack is fetching
  const stats = liveStats || { streak: 0, masteryPoints: 0, conceptsMastered: 0, totalConcepts: 0, studyTimeMinutes: 0 };

  return (
    <div className="mb-6 grid grid-cols-2 gap-3 md:gap-4 xl:grid-cols-4 relative">
      
      {/* Optional: A subtle loading state if TanStack is fetching in the background */}
      {isLoading && (
        <div className="absolute -top-4 right-0 flex items-center gap-2 text-xs text-slate-400">
          <Loader2 className="w-3 h-3 animate-spin" /> Syncing stats
        </div>
      )}

      <StatCard 
        icon={Flame} 
        iconBg="bg-orange-50" 
        iconColor="text-orange-500" 
        title="Study Streak" 
        value={`${stats.streak} Days`} 
        subtext={stats.streak > 0 ? "Keep it up!" : "Start today!"} 
        subtextColor={stats.streak > 0 ? "text-orange-500" : "text-gray-400"} 
      />
      
      <StatCard 
        icon={Star} 
        iconBg="bg-yellow-50" 
        iconColor="text-yellow-500" 
        title="Mastery Points" 
        value={stats.masteryPoints.toLocaleString()} 
        subtext="Total earned" 
        subtextColor="text-gray-400" 
      />
      
      <StatCard 
        icon={CheckCircle2} 
        iconBg="bg-green-50" 
        iconColor="text-green-500" 
        title="Concepts" 
        value={`${stats.conceptsMastered} / ${stats.totalConcepts}`} 
        subtext="Mastered"
        subtextColor="text-gray-400"
      />
      
      <StatCard 
        icon={Clock} 
        iconBg="bg-blue-50" 
        iconColor="text-blue-500" 
        title="Study Time" 
        value={formatStudyTime(stats.studyTimeMinutes)} 
        subtext="All time" 
        subtextColor="text-gray-400" 
      />
    </div>
  );
};

export default DashboardStats;