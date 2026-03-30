import { ChevronRight } from 'lucide-react';

export default function Breadcrumbs({ classLevel, topic }) {
  return (
    <div className="flex items-center gap-2 text-sm text-gray-500 mb-6 font-medium">
        <span>{classLevel}</span>
        <ChevronRight className="w-4 h-4" />
        <span>{topic} Mastery</span>
        <ChevronRight className="w-4 h-4" />
        <span className='text-indigo-600 font-bold'>Quiz Result</span>
    </div>
  );
}