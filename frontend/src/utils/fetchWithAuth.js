/**
 * Authenticated Fetch Wrapper
 *
 * Wraps the native fetch() API to automatically include auth tokens.
 * Use this for requests that need FormData or other features not easily done with axios.
 *
 * Usage:
 *   import { fetchWithAuth } from '../utils/fetchWithAuth'
 *
 *   const response = await fetchWithAuth('/api/bulk/upload', {
 *     method: 'POST',
 *     body: formData
 *   })
 */

import { getToken } from './auth';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/**
 * Fetch with automatic auth token injection
 *
 * @param {string} url - URL to fetch (relative or absolute)
 * @param {RequestInit} options - Fetch options
 * @returns {Promise<Response>}
 */
export async function fetchWithAuth(url, options = {}) {
  // Ensure URL is absolute
  const absoluteUrl = url.startsWith('http') ? url : `${API_URL}${url}`;

  // Get auth token
  const token = getToken();

  // Merge headers with auth token
  const headers = {
    ...(options.headers || {}),
  };

  // Add Authorization header if token exists
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  // Make the request
  const response = await fetch(absoluteUrl, {
    ...options,
    headers,
  });

  return response;
}

/**
 * Authenticated fetch with JSON parsing
 *
 * @param {string} url - URL to fetch
 * @param {RequestInit} options - Fetch options
 * @returns {Promise<any>} - Parsed JSON response
 */
export async function fetchJSON(url, options = {}) {
  const response = await fetchWithAuth(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `HTTP ${response.status}: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Upload files with auth
 *
 * @param {string} url - URL to upload to
 * @param {FormData} formData - Form data with files
 * @param {RequestInit} options - Additional fetch options
 * @returns {Promise<Response>}
 */
export async function uploadFiles(url, formData, options = {}) {
  return fetchWithAuth(url, {
    method: 'POST',
    body: formData,
    ...options,
    // Don't set Content-Type - let browser set it with boundary for multipart/form-data
  });
}

export default fetchWithAuth;
