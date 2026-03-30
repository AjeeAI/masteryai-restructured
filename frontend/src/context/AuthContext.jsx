import React, { createContext, useContext, useState } from 'react';

// Create the context
const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  // Initialize state from localStorage using the new name: 'mastery-ai_token'
  const [token, setToken] = useState(() => localStorage.getItem('mastery-ai_token'));

  // Function to handle login
  const login = (newToken) => {
    localStorage.setItem('mastery-ai_token', newToken);
    setToken(newToken);
  };

  // Function to handle logout
  const logout = () => {
    localStorage.removeItem('mastery-ai_token');
    setToken(null);
  };

  return (
    <AuthContext.Provider value={{ token, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

// Custom hook to make it easy to grab auth data anywhere
export const useAuth = () => useContext(AuthContext);