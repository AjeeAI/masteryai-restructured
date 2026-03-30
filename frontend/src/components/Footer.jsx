import { BookOpen } from 'lucide-react';

export default function Footer() {
  // Store the current year in a variable
  const currentYear = new Date().getFullYear();

  return (
    <footer className="mt-12 py-8 border-t border-gray-200 flex flex-col md:flex-row items-center justify-between text-sm text-gray-500">
      <div className="flex items-center gap-2 font-bold text-indigo-600 mb-4 md:mb-0">
        <BookOpen className="w-5 h-5" />
        MasteryAI
      </div>
      
        <div className="flex gap-6 mb-4 md:mb-0">
            <a href="#" className="hover:text-gray-900 font-medium">Help Center</a>
            <a href="#" className="hover:text-gray-900 font-medium">Privacy Policy</a>
            <a href="#" className="hover:text-gray-900 font-medium">Accessibility</a>
            <a href="#" className="hover:text-gray-900 font-medium">Feedback</a>
        </div>
      
      <div className="text-xs">
        {/* Inject the dynamic year using curly braces */}
        © {currentYear} MasteryAI. Built with passion for students.
      </div>
    </footer>
  );
}