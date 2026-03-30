import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { useUser } from '../context/UserContext';
import { updateUserProfile } from '../services/api';
const AccountSettingsView = ({ user }) => {
  const { token } = useAuth();
  const { updateLocalUser } = useUser();

  // --- Form & Upload States ---
  const [formData, setFormData] = useState({
    fullName: user.name || user.fullName || '',
    email: user.email || '',
    gradeLevel: user.gradeLevel || 'sss 2',
  });

  const [isSaving, setIsSaving] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  useEffect(() => {
    setFormData({
      fullName: user.name || user.fullName || '',
      email: user.email || '',
      gradeLevel: user.gradeLevel || 'sss 2',
    });
  }, [user]);

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
    setSuccessMsg('');
    setErrorMsg('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSaving(true);
    setErrorMsg('');
    setSuccessMsg('');

    const nameParts = formData.fullName.trim().split(' ');
    const firstName = nameParts[0] || '';
    const lastName = nameParts.slice(1).join(' ') || '';

    const payload = {
      first_name: firstName,
      last_name: lastName,
      // grade_level: formData.gradeLevel // Uncomment if your backend accepts this here!
    };

    try {
      const updatedData = await updateUserProfile(token, payload);
      updateLocalUser(updatedData);
      setSuccessMsg("Profile updated successfully!");
    } catch (err) {
      console.error(err);
      setErrorMsg(err.message);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      
      {/* --- Account Information Form --- */}
      <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-200">
        <h2 className="text-xl font-bold text-slate-800">Account Information</h2>
        <p className="text-sm text-slate-500 mb-6">Update your personal details and account preferences.</p>

        {/* Feedback Banners */}
        {errorMsg && (
          <div className="mb-6 p-3 bg-rose-50 border border-rose-200 text-rose-600 rounded-lg text-sm font-medium">
            {errorMsg}
          </div>
        )}
        {successMsg && (
          <div className="mb-6 p-3 bg-emerald-50 border border-emerald-200 text-emerald-700 rounded-lg text-sm font-medium">
            {successMsg}
          </div>
        )}

        <form className="space-y-5" onSubmit={handleSubmit}>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-2">
              <label className="text-sm font-semibold text-slate-700">Full Name</label>
              <input 
                type="text" 
                name="fullName"
                value={formData.fullName}
                onChange={handleChange}
                className="w-full border border-slate-300 rounded-lg px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-shadow"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-semibold text-slate-700">Email Address</label>
              <input 
                type="email" 
                name="email"
                value={formData.email}
                onChange={handleChange}
                className="w-full border border-slate-300 rounded-lg px-4 py-2.5 bg-slate-50 text-slate-500 cursor-not-allowed"
                disabled 
              />
            </div>
          </div>

          <div className="space-y-2 w-full md:w-1/2 md:pr-3">
            <label className="text-sm font-semibold text-slate-700">Grade Level</label>
            <select 
              name="gradeLevel"
              value={formData.gradeLevel}
              onChange={handleChange}
              className="w-full border border-slate-300 rounded-lg px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
            >
              <option value="sss 1">sss 1</option>
              <option value="sss 2">sss 2</option>
              <option value="sss 3">sss 3</option>
            </select>
          </div>

          <div className="pt-4 flex justify-end">
            <button 
              type="submit" 
              disabled={isSaving}
              className={`font-semibold py-2.5 px-6 rounded-lg transition-all flex items-center gap-2 ${
                isSaving
                  ? 'bg-indigo-400 cursor-not-allowed text-white' 
                  : 'bg-indigo-600 hover:bg-indigo-700 text-white shadow-md hover:shadow-lg'
              }`}
            >
              {isSaving ? "Saving..." : "Save Changes"}
            </button>
          </div>
        </form>
      </div>

      {/* ... Keep your existing School Information and Security sections below ... */}

    </div>
  );
};

export default AccountSettingsView;
