import React, { useRef, useState } from 'react';

const ProfileBanner = ({ user, onImageUpload }) => {
  const fileInputRef = useRef(null);
  const [previewUrl, setPreviewUrl] = useState(null);

  const handleImageClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (event) => {
    const file = event.target.files[0];
    if (file) {
      const localUrl = URL.createObjectURL(file);
      setPreviewUrl(localUrl);

      if (onImageUpload) {
        onImageUpload(file);
      }
    }
  };

  // 👇 HELPER FUNCTION: Extracts initials from the user's name
  const getInitials = (name) => {
    if (!name) return "U"; // Fallback to 'U' for User if name is entirely missing
    const nameParts = name.trim().split(" ");
    if (nameParts.length >= 2) {
      // First letter of first name + First letter of last name
      return `${nameParts[0][0]}${nameParts[nameParts.length - 1][0]}`.toUpperCase();
    }
    // Just first letter if they only have one name
    return nameParts[0][0].toUpperCase();
  };

  // Determine what to show
  const displayImage = previewUrl || user.avatarUrl || user.avatar_url; // Safely check backend snake_case too
  
  // Construct the name exactly like the Navbar does!
  const userName = user.first_name 
    ? `${user.first_name} ${user.last_name || ''}`.trim() 
    : user.name || user.fullName || "Student";

  return (
    <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200 flex flex-col md:flex-row items-center md:items-start justify-between gap-6">
      
      <div className="flex flex-col md:flex-row items-center md:items-start gap-6">
        
        {/* Avatar Area */}
        <div className="relative group cursor-pointer" onClick={handleImageClick}>
          <input 
            type="file" 
            ref={fileInputRef} 
            onChange={handleFileChange} 
            accept="image/png, image/jpeg, image/jpg" 
            className="hidden" 
          />
          
          <div className="w-24 h-24 bg-indigo-50 rounded-2xl overflow-hidden border-4 border-white shadow-md transition-transform group-hover:scale-105 flex items-center justify-center">
            {/* 👇 THE MAGIC: Conditionally render the image OR the initials! */}
            {displayImage ? (
              <img 
                src={displayImage} 
                alt={`${userName}'s Avatar`} 
                className="w-full h-full object-cover" 
              />
            ) : (
              <span className="text-3xl font-black text-indigo-600 tracking-widest">
                {getInitials(userName)}
              </span>
            )}
          </div>

          <button className="absolute -bottom-2 -right-2 bg-indigo-600 text-white p-2 rounded-full shadow-lg hover:bg-indigo-700 transition transform group-hover:scale-110">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"></path><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z"></path></svg>
          </button>
        </div>

        <div className="text-center md:text-left">
          <h1 className="text-2xl font-bold text-slate-800">{userName}</h1>
          <div className="flex flex-wrap items-center justify-center md:justify-start gap-3 mt-2">
            <span className="bg-indigo-50 text-indigo-700 text-xs font-bold px-3 py-1 rounded-full">
              {user.gradeLevel} • {user.league}
            </span>
            <span className="flex items-center gap-1 text-amber-600 text-sm font-semibold bg-amber-50 px-3 py-1 rounded-full">
              🪙 {user.masteryPoints} Mastery Points
            </span>
          </div>
          <p className="text-slate-500 text-sm mt-3 flex items-center justify-center md:justify-start gap-2">
            ✉️ {user.email}
          </p>
        </div>
      </div>

      <button className="bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-2 px-6 rounded-lg transition-colors flex items-center gap-2">
        <span>🔗</span> Share Profile
      </button>

    </div>
  );
};

export default ProfileBanner;