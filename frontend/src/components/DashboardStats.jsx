import React from 'react';
import { useUser } from '../context/UserContext';
import { Flame, Star, CheckCircle2, Clock } from 'lucide-react'; // Assuming you use lucide-react
import StatCard from './StatCard';

const DashboardStats = () => {
  // 1. Grab the live data from your global context
  const { studentData } = useUser();

  // 2. Helper function to turn raw minutes from the backend into "Xh Ym"
  const formatStudyTime = (totalMinutes) => {
    if (!totalMinutes) return "0h 0m";
    const hours = Math.floor(totalMinutes / 60);
    const minutes = totalMinutes % 60;
    return hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`;
  };

  // 3. Extract your data with safe fallbacks (in case the user is brand new)
  const streak = studentData?.streak_days || 0;
  const masteryPoints = studentData?.mastery_score || 0;
  const conceptsMastered = studentData?.concepts_mastered || 0;
  const totalConcepts = studentData?.total_concepts || 0;
  const studyTime = studentData?.study_time_minutes || 0;

  return (
    <div className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
      <StatCard 
        icon={Flame} 
        iconBg="bg-orange-50" 
        iconColor="text-orange-500" 
        title="Study Streak" 
        value={`${streak} Days`} 
        subtext={streak > 0 ? "Keep it up!" : "Start your streak today!"} 
        subtextColor={streak > 0 ? "text-orange-500" : "text-gray-400"} 
      />
      
      <StatCard 
        icon={Star} 
        iconBg="bg-yellow-50" 
        iconColor="text-yellow-500" 
        title="Mastery Points" 
        // .toLocaleString() adds the nice commas (e.g. 3,450)
        value={masteryPoints.toLocaleString()} 
        subtext="Total earned" 
        subtextColor="text-gray-400" 
      />
      
      <StatCard 
        icon={CheckCircle2} 
        iconBg="bg-green-50" 
        iconColor="text-green-500" 
        title="Concepts Mastered" 
        value={`${conceptsMastered} / ${totalConcepts}`} 
      />
      
      <StatCard 
        icon={Clock} 
        iconBg="bg-blue-50" 
        iconColor="text-blue-500" 
        title="Study Time" 
        value={formatStudyTime(studyTime)} 
        subtext="All time" 
        subtextColor="text-gray-400" 
      />
    </div>
  );
};

export default DashboardStats;
