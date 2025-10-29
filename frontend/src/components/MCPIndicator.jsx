/**
 * MCP Indicator Component
 *
 * Small badge showing MCP (Claude) connection status.
 * Displays in navbar/header to show when AI features are active.
 *
 * Usage:
 *   <MCPIndicator />
 */

import React from 'react';
import { useMCP, getMCPStatusMessage, getMCPStatusColor } from '../hooks/useMCP';

export function MCPIndicator({ showLabel = true, size = 'sm' }) {
  const { isActive, status, loading } = useMCP();

  if (loading) {
    return null; // Don't show until we know status
  }

  // Don't show if not active
  if (!isActive) {
    return null;
  }

  const sizeClasses = {
    xs: 'w-1.5 h-1.5',
    sm: 'w-2 h-2',
    md: 'w-3 h-3',
    lg: 'w-4 h-4'
  };

  const textSizeClasses = {
    xs: 'text-xs',
    sm: 'text-xs',
    md: 'text-sm',
    lg: 'text-base'
  };

  return (
    <div className="flex items-center space-x-1.5">
      {/* Status dot */}
      <div className={`${sizeClasses[size]} bg-green-500 rounded-full animate-pulse`}></div>

      {/* Label */}
      {showLabel && (
        <span className={`${textSizeClasses[size]} ${getMCPStatusColor(status)} font-medium`}>
          Claude
        </span>
      )}
    </div>
  );
}

/**
 * Detailed MCP Status Card
 * Shows full status with description and actions
 */
export function MCPStatusCard() {
  const { enabled, status, isActive, toggleMCP, refresh } = useMCP();

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-lg font-semibold">AI Assistant (Claude)</h3>
        {isActive && (
          <span className="inline-flex items-center px-2 py-1 text-xs font-medium rounded-full bg-green-100 text-green-800">
            <span className="w-2 h-2 bg-green-500 rounded-full mr-1.5"></span>
            Active
          </span>
        )}
      </div>

      <p className="text-sm text-gray-600 mb-4">
        {getMCPStatusMessage(status)}
      </p>

      {isActive && (
        <div className="bg-blue-50 border-l-4 border-blue-500 p-3 mb-4">
          <p className="text-sm text-blue-800">
            <strong>Claude Mode Active</strong> - Your searches and queries are enhanced by AI.
          </p>
        </div>
      )}

      <div className="flex space-x-2">
        <button
          onClick={() => toggleMCP(!enabled)}
          className={`px-4 py-2 text-sm rounded ${
            enabled
              ? 'bg-gray-200 hover:bg-gray-300 text-gray-700'
              : 'bg-blue-600 hover:bg-blue-700 text-white'
          }`}
        >
          {enabled ? 'Disable' : 'Enable'}
        </button>

        <button
          onClick={refresh}
          className="px-4 py-2 text-sm border border-gray-300 rounded hover:bg-gray-50"
        >
          Refresh Status
        </button>
      </div>

      {enabled && !isActive && (
        <p className="text-xs text-gray-500 mt-3">
          MCP is enabled but Claude is not connected. Make sure Claude Desktop is running.
        </p>
      )}
    </div>
  );
}

/**
 * Inline MCP Banner
 * Shows at top of pages when MCP is active
 */
export function MCPBanner({ onClose }) {
  const { isActive } = useMCP();

  if (!isActive) {
    return null;
  }

  return (
    <div className="bg-gradient-to-r from-blue-50 to-purple-50 border-l-4 border-blue-500 p-3 mb-4 rounded-r">
      <div className="flex items-start justify-between">
        <div className="flex items-start space-x-3">
          <div className="flex-shrink-0 mt-0.5">
            <span className="text-2xl">🤖</span>
          </div>
          <div>
            <h4 className="text-sm font-semibold text-gray-900 mb-1">
              Claude Mode Active
            </h4>
            <p className="text-xs text-gray-700">
              Your queries are powered by AI for smarter results and insights.
              <a href="/settings" className="ml-2 underline hover:text-blue-700">
                Configure
              </a>
            </p>
          </div>
        </div>

        {onClose && (
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
            aria-label="Close banner"
          >
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                clipRule="evenodd"
              />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}

export default MCPIndicator;
