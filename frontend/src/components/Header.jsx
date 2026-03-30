import React from 'react';
import { Search, Bell, BookOpen } from 'lucide-react';

export default function Header({ name, classLevel }) {
  return (
    <header className="flex items-center justify-between px-8 py-4 bg-white sticky top-0 z-50 border-b border-gray-100">
      <div className="flex items-center gap-8">
        <div className="flex items-center gap-2 text-indigo-600 font-bold text-xl">
          <BookOpen className="w-6 h-6" />
          <span>MasteryAI</span>
        </div>
        <nav className="hidden md:flex gap-6 text-sm font-medium">
          <a href="#" className="text-indigo-600">Dashboard</a>
          <a href="#" className="text-gray-500 hover:text-gray-900">Learning Path</a>
          <a href="#" className="text-gray-500 hover:text-gray-900">Mastery Path</a>
          <a href="#" className="text-gray-500 hover:text-gray-900">Practice</a>
        </nav>
      </div>

      <div className="flex items-center gap-6">
        <div className="relative hidden md:block">
          <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input 
            type="text" 
            placeholder="Search topics..." 
            className="pl-9 pr-4 py-2 bg-gray-50 border border-gray-100 rounded-full text-sm focus:outline-none focus:ring-2 focus:ring-indigo-100 w-64"
          />
        </div>
        <button className="text-gray-400 hover:text-gray-600 relative">
          <Bell className="w-5 h-5" />
          <span className="absolute top-0 right-0 w-2 h-2 bg-red-500 rounded-full"></span>
        </button>
        <div className="flex items-center gap-3 border-l border-gray-200 pl-6">
          <div className="text-right hidden sm:block">
            <div className="text-sm font-semibold text-gray-900">{name}</div>
            <div className="text-xs text-indigo-600 font-medium bg-indigo-50 px-2 py-0.5 rounded-full inline-block mt-0.5">
              {classLevel} • Student
            </div>
          </div>
          <div className="w-10 h-10 rounded-full bg-indigo-100 overflow-hidden">
            <img src="https://api.dicebear.com/7.x/avataaars/svg?seed=Alex" alt="Profile" className="w-full h-full object-cover" />
          </div>
        </div>
      </div>
    </header>
  );
}