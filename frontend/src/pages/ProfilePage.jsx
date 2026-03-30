import React, { useEffect, useMemo, useState } from 'react';
import ProfileBanner from '../components/ProfileBanner';
import SettingsSidebar from '../components/SettingsSidebar';
import AccountSettingsView from '../components/AccountSettingsView';
import LearningPreferencesView from '../components/LearningPreferencesView';
import { API_URL } from '../config/runtime';
import { useUser } from '../context/UserContext';
import { useAuth } from '../context/AuthContext';
import { updateUserProfile } from '../services/api';
import { resolveStudentId } from '../utils/sessionIdentity';

const masteryTone = {
  demonstrated: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  needs_review: 'border-amber-200 bg-amber-50 text-amber-800',
  unassessed: 'border-slate-200 bg-slate-50 text-slate-600',
};

const isLikelyUuid = (value) => /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(String(value || '').trim());

const humanizeConceptId = (conceptId, fallback = 'Concept') => {
  const value = String(conceptId || '').trim();
  if (!value) return fallback;
  const cleaned = value.startsWith('topic:') ? value.replace(/^topic:/i, '') : value;
  if (isLikelyUuid(cleaned)) return fallback;
  const token = value.split(':').pop()?.trim() || value;
  return token
    .replace(/-(\d+)$/, '')
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase()) || fallback;
};

const ProfilePage = () => {
  const [activeTab, setActiveTab] = useState('account');
  const [isUploading, setIsUploading] = useState(false);
  const [masteryLoading, setMasteryLoading] = useState(false);
  const [masteryError, setMasteryError] = useState('');
  const [masterySummary, setMasterySummary] = useState(null);
  const [masteryItems, setMasteryItems] = useState([]);

  const { token } = useAuth();
  const { userData, studentData, updateLocalUser } = useUser();
  const apiUrl = API_URL;
  const activeStudentId = resolveStudentId(studentData, userData);

  const CLOUDINARY_CLOUD_NAME = 'dzt3imk5w';
  const CLOUDINARY_UPLOAD_PRESET = 'masteryai_avatars';

  const handleImageUpload = async (file) => {
    setIsUploading(true);

    try {
      const uploadData = new FormData();
      uploadData.append('file', file);
      uploadData.append('upload_preset', CLOUDINARY_UPLOAD_PRESET);

      const cloudinaryRes = await fetch(
        `https://api.cloudinary.com/v1_1/${CLOUDINARY_CLOUD_NAME}/image/upload`,
        { method: 'POST', body: uploadData },
      );

      if (!cloudinaryRes.ok) throw new Error('Cloudinary upload failed');

      const cloudinaryData = await cloudinaryRes.json();
      const imageUrl = cloudinaryData.secure_url;
      await updateUserProfile(token, { avatar_url: imageUrl });
      updateLocalUser({ avatar_url: imageUrl });
    } catch (error) {
      console.error('Upload Error:', error);
      alert('Failed to update profile picture. Please try again.');
    } finally {
      setIsUploading(false);
    }
  };

  const activeUser = {
    first_name: userData?.first_name,
    last_name: userData?.last_name,
    name: `${userData?.first_name || ''} ${userData?.last_name || ''}`.trim() || 'Student',
    email: userData?.email || 'No email available',
    gradeLevel: studentData?.sss_level || 'Not set',
    league: studentData?.league_name || 'Learner',
    masteryPoints: Number(studentData?.mastery_score || 0),
    avatarUrl: userData?.avatar_url || null,
  };

  const masteryScope = useMemo(() => {
    const subject = (localStorage.getItem('active_subject') || studentData?.favorite_subject || 'math').toLowerCase();
    const term = Number(studentData?.current_term || 1);
    return { subject, term };
  }, [studentData?.current_term, studentData?.favorite_subject]);

  useEffect(() => {
    if (activeTab !== 'mastery') return;
    if (!token || !activeStudentId) return;

    let isMounted = true;
    const fetchMastery = async () => {
      setMasteryLoading(true);
      setMasteryError('');
      try {
        const params = new URLSearchParams({
          student_id: activeStudentId,
          subject: masteryScope.subject,
          term: String(masteryScope.term),
          view: 'concept',
          persist_snapshot: 'false',
        });
        const response = await fetch(`${apiUrl}/learning/mastery?${params.toString()}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!response.ok) throw new Error('Unable to load mastery overview.');
        const data = await response.json();
        if (!isMounted) return;
        setMasterySummary(data?.evidence_summary || null);
        setMasteryItems(Array.isArray(data?.mastery) ? data.mastery : []);
      } catch (error) {
        if (!isMounted) return;
        setMasteryError(error.message || 'Unable to load mastery overview.');
        setMasterySummary(null);
        setMasteryItems([]);
      } finally {
        if (isMounted) setMasteryLoading(false);
      }
    };

    fetchMastery();
    return () => {
      isMounted = false;
    };
  }, [activeStudentId, activeTab, apiUrl, masteryScope.subject, masteryScope.term, token]);

  return (
    <div className="min-h-screen bg-slate-50 pb-12">
      <main className="max-w-6xl mx-auto px-4 py-8 space-y-6">
        <ProfileBanner user={activeUser} onImageUpload={handleImageUpload} />

        {isUploading && (
          <div className="p-4 bg-indigo-50 border border-indigo-200 text-indigo-700 rounded-2xl text-sm font-bold text-center animate-pulse shadow-sm">
            Uploading and saving your new avatar...
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-12 gap-8 items-start">
          <div className="md:col-span-3">
            <SettingsSidebar activeTab={activeTab} setActiveTab={setActiveTab} />
          </div>

          <div className="md:col-span-9">
            {activeTab === 'account' && <AccountSettingsView user={activeUser} />}
            {activeTab === 'preferences' && <LearningPreferencesView />}
            {activeTab === 'mastery' && (
              <div className="p-8 bg-white rounded-xl shadow-sm border border-slate-200 space-y-6">
                <div>
                  <h2 className="text-xl font-bold text-slate-800">Mastery Overview</h2>
                  <p className="mt-2 text-sm leading-7 text-slate-600">
                    Evidence snapshot for {masteryScope.subject.toUpperCase()} term {masteryScope.term}. This pulls
                    directly from your latest mastery evidence.
                  </p>
                </div>

                {masteryLoading && (
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-6 text-sm font-semibold text-slate-500 animate-pulse">
                    Loading mastery evidence...
                  </div>
                )}

                {!masteryLoading && masteryError && (
                  <div className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-sm font-semibold text-rose-700">
                    {masteryError}
                  </div>
                )}

                {!masteryLoading && !masteryError && masterySummary && (
                  <div className="grid gap-4 md:grid-cols-3">
                    {[
                      { label: 'Demonstrated', value: masterySummary.demonstrated, tone: masteryTone.demonstrated },
                      { label: 'Needs review', value: masterySummary.needs_review, tone: masteryTone.needs_review },
                      { label: 'Unassessed', value: masterySummary.unassessed, tone: masteryTone.unassessed },
                    ].map((item) => (
                      <div key={item.label} className={`rounded-2xl border p-4 ${item.tone}`}>
                        <div className="text-[10px] font-black uppercase tracking-[0.18em]">{item.label}</div>
                        <div className="mt-2 text-2xl font-black">{item.value}</div>
                      </div>
                    ))}
                  </div>
                )}

                {!masteryLoading && !masteryError && masteryItems.length > 0 && (
                  <div className="space-y-3">
                    <div className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">
                      Top concepts right now
                    </div>
                    <div className="grid gap-3 md:grid-cols-2">
                      {masteryItems.slice(0, 6).map((item) => {
                        const state = item.mastery_state || 'unassessed';
                        const tone = masteryTone[state] || masteryTone.unassessed;
                        return (
                          <div key={item.concept_id} className={`rounded-2xl border p-4 ${tone}`}>
                            <div className="text-sm font-bold">{humanizeConceptId(item.concept_id)}</div>
                            <div className="mt-1 text-xs font-semibold">
                              {state.replace('_', ' ')} · {Math.round(Number(item.score || 0) * 100)}%
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {!masteryLoading && !masteryError && masteryItems.length === 0 && (
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-6 text-sm font-semibold text-slate-500">
                    No mastery evidence recorded yet. Complete a quiz or a tutor checkpoint to populate this panel.
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
};

export default ProfilePage;
