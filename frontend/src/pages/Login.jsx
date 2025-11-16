import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { isDevBypassAllowed, DEV_CREDENTIALS } from '../utils/auth';

const Login = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [showDevTools, setShowDevTools] = useState(false);

  const { login, devBypass, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  // Check if dev bypass is allowed
  useEffect(() => {
    setShowDevTools(isDevBypassAllowed());
  }, []);

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      const from = location.state?.from?.pathname || '/';
      navigate(from, { replace: true });
    }
  }, [isAuthenticated, navigate, location]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const result = await login(email, password);

      if (result.success) {
        const from = location.state?.from?.pathname || '/';
        navigate(from, { replace: true });
      } else {
        setError(result.error);
      }
    } catch (err) {
      setError('An unexpected error occurred. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleDevBypass = () => {
    devBypass();
    const from = location.state?.from?.pathname || '/';
    navigate(from, { replace: true });
  };

  const handleQuickFill = () => {
    setEmail(DEV_CREDENTIALS.email);
    setPassword(DEV_CREDENTIALS.password);
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="max-w-md w-full mx-4">
        {/* Main Login Card */}
        <div className="bg-white rounded-lg shadow-xl p-8">
          {/* Header */}
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold text-gray-900 mb-2">Paperbase</h1>
            <p className="text-gray-600">Sign in to your account</p>
          </div>

          {/* Error Message */}
          {error && (
            <div className="mb-6 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
              {error}
            </div>
          )}

          {/* Login Form */}
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-2">
                Email
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="you@example.com"
                disabled={loading}
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-2">
                Password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="••••••••"
                disabled={loading}
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium"
            >
              {loading ? 'Signing in...' : 'Sign In'}
            </button>
          </form>
        </div>

        {/* Development Tools */}
        {showDevTools && (
          <div className="mt-6 bg-yellow-50 border-2 border-yellow-200 rounded-lg p-6">
            <div className="flex items-start space-x-3 mb-4">
              <span className="text-2xl">🔧</span>
              <div className="flex-1">
                <h3 className="font-semibold text-yellow-900 mb-1">Development Tools</h3>
                <p className="text-sm text-yellow-700">
                  Quick access for testing. Only visible in development builds.
                </p>
              </div>
            </div>

            <div className="space-y-3">
              {/* Quick Fill Button */}
              <button
                type="button"
                onClick={handleQuickFill}
                className="w-full bg-yellow-100 text-yellow-900 py-2 px-4 rounded-md hover:bg-yellow-200 transition-colors text-sm font-medium border border-yellow-300"
              >
                📋 Fill Test Credentials
              </button>

              {/* Dev Bypass Button */}
              <button
                type="button"
                onClick={handleDevBypass}
                className="w-full bg-yellow-600 text-white py-2 px-4 rounded-md hover:bg-yellow-700 transition-colors font-medium"
              >
                ⚡ Skip Login (Admin Access)
              </button>

              {/* Test Credentials Display */}
              <div className="mt-4 p-3 bg-yellow-100 rounded border border-yellow-300">
                <div className="text-xs font-mono text-yellow-900">
                  <div className="mb-1">
                    <span className="font-semibold">Email:</span> {DEV_CREDENTIALS.email}
                  </div>
                  <div>
                    <span className="font-semibold">Password:</span> {DEV_CREDENTIALS.password}
                  </div>
                </div>
              </div>

              <p className="text-xs text-yellow-700 mt-2">
                <strong>Skip Login:</strong> Bypasses authentication and grants admin access. No backend validation.
                <br />
                <strong>Fill Credentials:</strong> Uses real test user with backend validation.
              </p>
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="mt-6 text-center text-sm text-gray-600">
          <p>Paperbase - Intelligent Document Processing</p>
        </div>
      </div>
    </div>
  );
};

export default Login;
