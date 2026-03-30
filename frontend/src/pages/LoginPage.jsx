import React, { useState } from 'react';
import { GoogleOAuthProvider, GoogleLogin } from '@react-oauth/google';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { API_URL, GOOGLE_AUTH_ENABLED, GOOGLE_CLIENT_ID } from '../config/runtime';
import loginImg from "/src/assets/login_img.png";

const LoginPage = () => {
  const navigate = useNavigate();
  const [error, setError] = useState('');
  const [formErrors, setFormErrors] = useState({});
  const [isLoading, setIsLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const { login } = useAuth();
  const [formData, setFormData] = useState({ email: '', password: '' });
  const apiUrl = API_URL;

  const handleGoogleSuccess = async (credentialResponse) => {
    setIsLoading(true);
    setError('');

    try {
      const response = await fetch(`${apiUrl}/auth/google`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ token: credentialResponse.credential }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new Error(errorData?.detail || 'Google login failed on the server.');
      }

      const data = await response.json();
      if (data.user_id) {
        localStorage.setItem('mastery_student_id', data.user_id);
      }

      login(data.access_token);
      navigate('/dashboard');
    } catch (err) {
      console.error('Google Auth API Error:', err);
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const validateForm = () => {
    const newErrors = {};
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    if (!formData.email.trim()) {
      newErrors.email = 'Email address is required.';
    } else if (!emailRegex.test(formData.email)) {
      newErrors.email = 'Please enter a valid email address.';
    }

    if (!formData.password) {
      newErrors.password = 'Password is required.';
    } else if (formData.password.length < 8) {
      newErrors.password = 'Password must be at least 8 characters long.';
    }

    setFormErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleInputChange = (field, value) => {
    setFormData({ ...formData, [field]: value });
    if (formErrors[field]) {
      setFormErrors({ ...formErrors, [field]: null });
    }
  };

  const handleManualSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!validateForm()) return;

    setIsLoading(true);

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 15000);

    try {
      const response = await fetch(`${apiUrl}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: formData.email,
          password: formData.password,
        }),
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        const errData = await response.json().catch(() => null);
        throw new Error(errData?.detail || 'Login failed. Please check your credentials.');
      }

      const data = await response.json();
      if (data.user_id) {
        localStorage.setItem('mastery_student_id', data.user_id);
      }

      login(data.access_token);
      navigate('/dashboard');
    } catch (err) {
      console.error('Login Error:', err);
      if (err.name === 'AbortError') {
        setError('Your learning data is still syncing. Please refresh in a moment.');
      } else {
        setError(err.message);
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex">
      <div className="hidden lg:flex lg:w-1/2 bg-[#6b46c1] relative flex-col items-center justify-center p-12 overflow-hidden">
        <div className="absolute top-10 left-10 text-white/10">
          <svg className="w-24 h-24" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/></svg>
        </div>
        <div className="absolute bottom-10 left-1/2 -translate-x-1/2 text-white/5 font-black text-9xl tracking-widest pointer-events-none select-none">
          ATOM
        </div>

        <div className="relative w-full max-w-lg z-10">
          <div className="bg-[#e2e8f0] rounded-3xl aspect-[4/3] w-full shadow-2xl overflow-hidden relative">
            <img src={loginImg} alt="Student studying" className="object-cover w-full h-full opacity-90 mix-blend-multiply" />
          </div>

          <div className="absolute -top-6 -right-6 bg-white px-6 py-4 rounded-2xl shadow-xl flex items-center gap-4 animate-bounce-slow">
            <div className="bg-[#4f46e5] p-2 rounded-full text-white">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"></path></svg>
            </div>
            <div>
              <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Mastery Score</p>
              <p className="text-2xl font-black text-[#4f46e5]">84%</p>
            </div>
          </div>
        </div>
      </div>

      <div className="w-full lg:w-1/2 flex flex-col justify-center items-center p-8 sm:p-12 bg-white relative">
        <div className="w-full max-w-md space-y-8">
          <div>
            <h1 className="text-4xl font-black text-slate-900 tracking-tight">Welcome Back</h1>
            <p className="text-slate-500 mt-3 text-sm leading-relaxed">Log in to continue your mastery journey on MasteryAI.</p>
          </div>

          {error && (
            <div className="bg-rose-50 text-rose-600 p-4 rounded-xl text-sm font-medium border border-rose-100 flex items-start gap-3">
              <svg className="w-5 h-5 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleManualSubmit} className="space-y-5" noValidate>
            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-700 uppercase tracking-wider">Email Address</label>
              <div className="relative">
                <span className={`absolute left-4 top-1/2 -translate-y-1/2 ${formErrors.email ? 'text-rose-500' : 'text-slate-400'}`}>
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path></svg>
                </span>
                <input
                  type="email"
                  placeholder="student@masteryai.edu"
                  value={formData.email}
                  onChange={(e) => handleInputChange('email', e.target.value)}
                  className={`w-full pl-12 pr-4 py-3.5 bg-white border rounded-xl text-sm focus:outline-none focus:ring-2 transition-all ${formErrors.email ? 'border-rose-500 focus:ring-rose-500/20 text-rose-900 placeholder:text-rose-300' : 'border-slate-200 focus:ring-[#6b46c1]'}`}
                />
              </div>
              {formErrors.email && <p className="text-[11px] text-rose-500 font-medium pl-1">{formErrors.email}</p>}
            </div>

            <div className="space-y-1.5">
              <div className="flex justify-between items-center">
                <label className="text-xs font-bold text-slate-700 uppercase tracking-wider">Password</label>
                <a href="#" className="text-xs font-bold text-[#6b46c1] hover:text-[#4f46e5] transition-colors">Forgot Password?</a>
              </div>
              <div className="relative">
                <span className={`absolute left-4 top-1/2 -translate-y-1/2 ${formErrors.password ? 'text-rose-500' : 'text-slate-400'}`}>
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"></path></svg>
                </span>
                <input
                  type={showPassword ? 'text' : 'password'}
                  placeholder="********"
                  value={formData.password}
                  onChange={(e) => handleInputChange('password', e.target.value)}
                  className={`w-full pl-12 pr-12 py-3.5 bg-white border rounded-xl text-sm focus:outline-none focus:ring-2 transition-all tracking-widest ${formErrors.password ? 'border-rose-500 focus:ring-rose-500/20 text-rose-900 placeholder:text-rose-300' : 'border-slate-200 focus:ring-[#6b46c1] placeholder:tracking-normal'}`}
                />
                <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 focus:outline-none">
                  {showPassword ? <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21"></path></svg> : <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path></svg>}
                </button>
              </div>
              {formErrors.password && <p className="text-[11px] text-rose-500 font-medium pl-1">{formErrors.password}</p>}
            </div>

            <button type="submit" disabled={isLoading} className={`w-full text-white font-bold py-3.5 rounded-xl transition-all shadow-lg flex justify-center items-center gap-2 mt-2 ${isLoading ? 'bg-slate-400 cursor-not-allowed shadow-none' : 'bg-[#6b46c1] hover:bg-[#5b3da6] shadow-indigo-500/30'}`}>
              {isLoading ? 'Signing In...' : 'Sign In'}
              {!isLoading && <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14 5l7 7m0 0l-7 7m7-7H3"></path></svg>}
            </button>
          </form>

          <div className="relative flex items-center py-2">
            <div className="flex-grow border-t border-slate-200"></div>
            <span className="flex-shrink-0 mx-4 text-slate-400 text-xs font-bold uppercase tracking-widest">Or Use</span>
            <div className="flex-grow border-t border-slate-200"></div>
          </div>

          {GOOGLE_AUTH_ENABLED ? (
            <div className="flex justify-center w-full">
              <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
                <GoogleLogin
                  onSuccess={handleGoogleSuccess}
                  onError={() => setError('Google Login Failed.')}
                  theme="outline"
                  size="large"
                  text="continue_with"
                  shape="rectangular"
                />
              </GoogleOAuthProvider>
            </div>
          ) : (
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-center text-sm text-slate-500">
              Google sign-in is disabled locally until <code>VITE_GOOGLE_CLIENT_ID</code> is set.
            </div>
          )}

          <p className="text-center text-sm text-slate-500 font-medium">New to MasteryAI? <Link to="/register" className="text-[#6b46c1] font-bold hover:underline">Create an account</Link></p>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
