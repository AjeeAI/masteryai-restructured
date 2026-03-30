export const resolveStudentId = (studentData, userData) => {
  if (studentData?.student_id) return studentData.student_id;
  if (studentData?.user_id) return studentData.user_id;
  if (userData?.student_id) return userData.student_id;
  if (userData?.user_id) return userData.user_id;
  if (userData?.id) return userData.id;
  if (typeof window !== 'undefined') {
    return window.localStorage.getItem('mastery_student_id');
  }
  return null;
};

export const resolveUserId = (studentData, userData) => {
  if (userData?.user_id) return userData.user_id;
  if (userData?.id) return userData.id;
  if (studentData?.user_id) return studentData.user_id;
  if (studentData?.student_id) return studentData.student_id;
  if (typeof window !== 'undefined') {
    return window.localStorage.getItem('mastery_student_id');
  }
  return null;
};
