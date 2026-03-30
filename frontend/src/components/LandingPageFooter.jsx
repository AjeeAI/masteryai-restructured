import { Twitter, Linkedin, BrainCircuit } from 'lucide-react';
import { Link } from 'react-router-dom';

const LandingPageFooter = () => {
  return (
    <footer className="bg-white border-t border-slate-200 pt-16 pb-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-12 mb-12">
          <div className="col-span-1 md:col-span-2">
            <Link to="/" className="flex items-center gap-2 mb-4">
              <div className="bg-blue-600 p-1.5 rounded-md">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                </svg>
              </div>
              <span className="text-lg font-bold text-slate-900">MasteryAI</span>
            </Link>
            <p className="text-slate-500 max-w-sm">
              Empowering students with intelligent, personalized learning solutions for a brighter academic future.
            </p>
          </div>
          
          <div>
            <h4 className="font-semibold text-slate-900 mb-4">Company</h4>
            <ul className="space-y-3">
              <li><Link to="/" className="text-slate-500 hover:text-blue-600 text-sm transition-colors">Home</Link></li>
              <li><Link to="/about" className="text-slate-500 hover:text-blue-600 text-sm transition-colors">About</Link></li>
              {/* Pointed to the newly created Contact route */}
              <li><Link to="/contact" className="text-slate-500 hover:text-blue-600 text-sm transition-colors">Contact</Link></li>
              <li><Link to="#" className="text-slate-500 hover:text-blue-600 text-sm transition-colors">Pricing</Link></li>
            </ul>
          </div>
          
          <div>
            <h4 className="font-semibold text-slate-900 mb-4">Legal</h4>
            <ul className="space-y-3">
              <li><Link to="#" className="text-slate-500 hover:text-blue-600 text-sm transition-colors">Privacy Policy</Link></li>
              <li><Link to="#" className="text-slate-500 hover:text-blue-600 text-sm transition-colors">Terms of Service</Link></li>
              <li><Link to="#" className="text-slate-500 hover:text-blue-600 text-sm transition-colors">Cookie Policy</Link></li>
            </ul>
          </div>
        </div>
        
        <div className="flex flex-col md:flex-row justify-between items-center pt-8 border-t border-slate-100">
          <p className="text-slate-400 text-sm mb-4 md:mb-0">
            © 2026 MasteryAI Inc. All rights reserved.
          </p>
          <div className="flex gap-4">
            {/* Added target="_blank" and rel="noopener noreferrer" for secure external linking */}
            <a 
              href="https://twitter.com" 
              target="_blank" 
              rel="noopener noreferrer" 
              className="text-slate-400 hover:text-blue-600 transition-colors"
            >
              <Twitter className="h-5 w-5" />
            </a>
            <a 
              href="https://linkedin.com" 
              target="_blank" 
              rel="noopener noreferrer" 
              className="text-slate-400 hover:text-blue-600 transition-colors"
            >
              <Linkedin className="h-5 w-5" />
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default LandingPageFooter;