/**
 * Authentication Utilities
 *
 * Handles token storage, dev mode detection, and auth state management.
 */

// Token storage keys
const TOKEN_KEY = 'paperbase_token';
const USER_KEY = 'paperbase_user';
const DEV_MODE_KEY = 'paperbase_dev_mode';

/**
 * Check if dev bypass is allowed
 *
 * Dev bypass is allowed if:
 * 1. Running in development mode (NOT production build)
 * 2. Environment variable VITE_ALLOW_DEV_BYPASS is not explicitly 'false'
 * 3. URL has ?dev=true parameter, OR
 * 4. localStorage has dev_mode flag set
 */
export const isDevBypassAllowed = () => {
  // Never allow in production builds
  if (import.meta.env.PROD) {
    return false;
  }

  // Check if explicitly disabled in env
  if (import.meta.env.VITE_ALLOW_DEV_BYPASS === 'false') {
    return false;
  }

  // Check URL parameter
  const params = new URLSearchParams(window.location.search);
  if (params.get('dev') === 'true') {
    return true;
  }

  // Check localStorage
  if (localStorage.getItem(DEV_MODE_KEY) === 'true') {
    return true;
  }

  // Default: allow in dev, block in prod
  return import.meta.env.DEV;
};

/**
 * Get stored auth token
 */
export const getToken = () => {
  return localStorage.getItem(TOKEN_KEY);
};

/**
 * Store auth token
 */
export const setToken = (token) => {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
};

/**
 * Get stored user data
 */
export const getUser = () => {
  const userJson = localStorage.getItem(USER_KEY);
  if (!userJson) return null;

  try {
    return JSON.parse(userJson);
  } catch (e) {
    console.error('Failed to parse stored user data:', e);
    return null;
  }
};

/**
 * Store user data
 */
export const setUser = (user) => {
  if (user) {
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  } else {
    localStorage.removeItem(USER_KEY);
  }
};

/**
 * Check if currently in dev mode
 */
export const isDevMode = () => {
  return localStorage.getItem(DEV_MODE_KEY) === 'true';
};

/**
 * Enable dev mode
 */
export const enableDevMode = () => {
  localStorage.setItem(DEV_MODE_KEY, 'true');
};

/**
 * Disable dev mode
 */
export const disableDevMode = () => {
  localStorage.removeItem(DEV_MODE_KEY);
};

/**
 * Clear all auth data
 */
export const clearAuth = () => {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  localStorage.removeItem(DEV_MODE_KEY);
};

/**
 * Check if user is authenticated
 */
export const isAuthenticated = () => {
  return !!(getToken() && getUser());
};

/**
 * Create a mock admin user for dev bypass
 */
export const createDevAdminUser = () => {
  return {
    id: 1,
    email: 'default@paperbase.local',
    name: 'Dev Admin',
    is_admin: true,
    is_active: true,
    auth_provider: 'dev-bypass'
  };
};

/**
 * Test credentials for development
 */
export const DEV_CREDENTIALS = {
  email: 'default@paperbase.local',
  password: 'admin'
};
