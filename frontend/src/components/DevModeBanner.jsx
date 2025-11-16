import React from 'react';
import { useAuth } from '../contexts/AuthContext';

/**
 * DevModeBanner - Visual indicator when dev bypass is active
 *
 * Shows a prominent banner at the top of the page when running in dev mode,
 * with an option to exit dev mode and return to normal login.
 */
const DevModeBanner = () => {
  const { devMode, user, exitDevMode } = useAuth();

  if (!devMode) {
    return null;
  }

  return (
    <div className="bg-yellow-500 text-yellow-900 px-4 py-2 flex items-center justify-between shadow-md">
      <div className="flex items-center space-x-3">
        <span className="text-xl">⚠️</span>
        <div>
          <div className="font-semibold">Development Mode Active</div>
          <div className="text-sm">
            Authentication bypassed. Logged in as: <span className="font-mono">{user?.email}</span>
          </div>
        </div>
      </div>
      <button
        onClick={exitDevMode}
        className="px-4 py-2 bg-yellow-900 text-yellow-100 rounded hover:bg-yellow-800 transition-colors text-sm font-medium"
      >
        Exit Dev Mode
      </button>
    </div>
  );
};

export default DevModeBanner;
