import React from 'react';
import { Outlet } from 'react-router-dom';
import LandingPageHeader from '../components/LandingPageHeader'; // Adjust path as needed
import LandingPageFooter from '../components/LandingPageFooter'; // Adjust path as needed

const LandingLayout = () => {
  return (
    <div className="min-h-screen flex flex-col font-sans text-slate-900 bg-white">
      <LandingPageHeader />
      
      {/* pt-20 ensures content starts below the fixed 80px (h-20) header */}
      <main className="flex-grow pt-20"> 
        <Outlet />
      </main>
      
      <LandingPageFooter />
    </div>
  );
};

export default LandingLayout;