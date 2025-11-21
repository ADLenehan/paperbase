import React, { createContext, useContext, useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '../api/client';
import {
  getToken,
  setToken as storeToken,
  getUser as getStoredUser,
  setUser as storeUser,
  clearAuth,
  isDevMode as checkDevMode,
  enableDevMode,
  disableDevMode,
  createDevAdminUser
} from '../utils/auth';

const AuthContext = createContext(null);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setTokenState] = useState(null);
  const [loading, setLoading] = useState(true);
  const [devMode, setDevMode] = useState(false);
  const navigate = useNavigate();

  // Initialize auth state from localStorage
  useEffect(() => {
    const initAuth = () => {
      const storedToken = getToken();
      const storedUser = getStoredUser();
      const isDevModeActive = checkDevMode();

      if (storedToken && storedUser) {
        setTokenState(storedToken);
        setUser(storedUser);
        setDevMode(isDevModeActive);
      }

      setLoading(false);
    };

    initAuth();
  }, []);

  /**
   * Login with email and password
   */
  const login = async (email, password) => {
    try {
      const response = await apiClient.post('/api/auth/login', {
        email,
        password
      });

      const { access_token, user: userData } = response.data;

      // Store token and user
      storeToken(access_token);
      storeUser(userData);

      setTokenState(access_token);
      setUser(userData);
      setDevMode(false);
      disableDevMode();

      return { success: true };
    } catch (error) {
      console.error('Login failed:', error);
      return {
        success: false,
        error: error.response?.data?.detail || 'Login failed. Please check your credentials.'
      };
    }
  };

  /**
   * Sign up with email, password, and name
   */
  const signup = async ({ email, password, name }) => {
    try {
      const response = await apiClient.post('/api/users/', {
        email,
        password,
        name,
        is_active: true
      });

      // After successful signup, log the user in
      return await login(email, password);
    } catch (error) {
      console.error('Signup failed:', error);
      return {
        success: false,
        error: error.response?.data?.detail || 'Signup failed. Please try again.'
      };
    }
  };

  /**
   * Logout
   */
  const logout = () => {
    clearAuth();
    setTokenState(null);
    setUser(null);
    setDevMode(false);
    navigate('/login');
  };

  /**
   * Dev bypass - skip authentication entirely
   */
  const devBypass = () => {
    const adminUser = createDevAdminUser();

    // Store dev user and enable dev mode
    storeUser(adminUser);
    storeToken('dev-bypass-token');
    enableDevMode();

    setUser(adminUser);
    setTokenState('dev-bypass-token');
    setDevMode(true);

    return { success: true };
  };

  /**
   * Exit dev mode and return to login
   */
  const exitDevMode = () => {
    logout();
  };

  /**
   * Refresh user data
   */
  const refreshUser = async () => {
    if (!token || devMode) {
      return;
    }

    try {
      const response = await apiClient.get('/api/auth/me');
      const userData = response.data;

      storeUser(userData);
      setUser(userData);
    } catch (error) {
      console.error('Failed to refresh user:', error);
      // If token is invalid, logout
      if (error.response?.status === 401) {
        logout();
      }
    }
  };

  const value = {
    user,
    token,
    loading,
    devMode,
    isAuthenticated: !!(user && token),
    login,
    signup,
    logout,
    devBypass,
    exitDevMode,
    refreshUser
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

export default AuthContext;
