/**
 * MCP State Hook - Elegant Integration
 *
 * Single source of truth for MCP (Model Context Protocol) status across the app.
 *
 * Usage:
 *   const { enabled, status, isActive } = useMCP();
 *
 *   if (isActive) {
 *     // Show MCP features
 *   }
 */

import { useState, useEffect } from 'react';

export function useMCP() {
  const [enabled, setEnabled] = useState(false);
  const [status, setStatus] = useState('disconnected');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    checkMCPStatus();

    // Check status every 30 seconds
    const interval = setInterval(checkMCPStatus, 30000);

    return () => clearInterval(interval);
  }, []);

  const checkMCPStatus = async () => {
    try {
      const response = await fetch('/api/mcp/status');

      if (response.ok) {
        const data = await response.json();
        setEnabled(data.enabled || false);
        setStatus(data.status || 'disconnected');
      } else {
        setStatus('disconnected');
      }
    } catch (error) {
      console.error('Error checking MCP status:', error);
      setStatus('error');
    } finally {
      setLoading(false);
    }
  };

  const toggleMCP = async (newEnabled) => {
    try {
      const response = await fetch('/api/mcp/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: newEnabled })
      });

      if (response.ok) {
        const data = await response.json();
        setEnabled(data.enabled);
        setStatus(data.status);
        return true;
      }

      return false;
    } catch (error) {
      console.error('Error toggling MCP:', error);
      return false;
    }
  };

  return {
    enabled,              // Is MCP enabled in settings?
    status,               // 'connected' | 'disconnected' | 'error'
    isActive: enabled && status === 'connected',  // Ready to use?
    loading,              // Initial status check
    toggleMCP,            // Function to enable/disable
    refresh: checkMCPStatus  // Manual refresh
  };
}

/**
 * Get a human-readable status message
 */
export function getMCPStatusMessage(status) {
  const messages = {
    'connected': '🟢 Claude is connected and ready',
    'disconnected': '🔴 Claude is not connected',
    'error': '🟡 Connection error - check logs',
    'loading': '⏳ Checking status...'
  };

  return messages[status] || messages.disconnected;
}

/**
 * Get status color class (Tailwind)
 */
export function getMCPStatusColor(status) {
  const colors = {
    'connected': 'text-green-600',
    'disconnected': 'text-gray-400',
    'error': 'text-yellow-600',
    'loading': 'text-gray-400'
  };

  return colors[status] || colors.disconnected;
}
