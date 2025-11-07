import { useState, useEffect } from 'react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Cache thresholds globally to avoid multiple API calls
let cachedThresholds = null;
let cacheTimestamp = null;
const CACHE_DURATION = 5 * 60 * 1000; // 5 minutes

/**
 * Hook to fetch and cache confidence thresholds from settings API
 *
 * Returns:
 * {
 *   high: number (default 0.8),
 *   medium: number (default 0.6),
 *   review: number (default 0.6),
 *   loading: boolean,
 *   error: Error|null
 * }
 */
export function useConfidenceThresholds() {
  const [thresholds, setThresholds] = useState({
    high: 0.8,
    medium: 0.6,
    review: 0.6,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchThresholds = async () => {
      // Check cache first
      const now = Date.now();
      if (cachedThresholds && cacheTimestamp && (now - cacheTimestamp < CACHE_DURATION)) {
        setThresholds(cachedThresholds);
        return;
      }

      setLoading(true);
      setError(null);

      try {
        const response = await fetch(`${API_URL}/api/settings/category/confidence`);

        if (!response.ok) {
          throw new Error(`Failed to fetch thresholds: ${response.status}`);
        }

        const data = await response.json();

        // Extract threshold values from settings response
        const newThresholds = {
          high: data.confidence_threshold_high?.value ?? 0.8,
          medium: data.confidence_threshold_medium?.value ?? 0.6,
          review: data.audit_confidence_threshold?.value ?? data.review_threshold?.value ?? 0.6,
        };

        // Update cache
        cachedThresholds = newThresholds;
        cacheTimestamp = now;

        setThresholds(newThresholds);
      } catch (err) {
        console.error('Failed to fetch confidence thresholds, using defaults:', err);
        setError(err);
        // Keep default values on error
      } finally {
        setLoading(false);
      }
    };

    fetchThresholds();
  }, []);

  return { ...thresholds, loading, error };
}

/**
 * Helper to get confidence color based on dynamic thresholds
 * @param {number} confidence - Confidence score (0.0-1.0)
 * @param {Object} thresholds - { high, medium } thresholds
 * @returns {string} Color class prefix
 */
export function getConfidenceColorDynamic(confidence, thresholds = { high: 0.8, medium: 0.6 }) {
  if (confidence >= thresholds.high) return 'green';
  if (confidence >= thresholds.medium) return 'yellow';
  return 'red';
}

/**
 * Helper to get confidence badge text based on dynamic thresholds
 * @param {number} confidence - Confidence score (0.0-1.0)
 * @param {Object} thresholds - { high, medium } thresholds
 * @returns {string} Badge text with icon
 */
export function getConfidenceBadgeTextDynamic(confidence, thresholds = { high: 0.8, medium: 0.6 }) {
  if (confidence >= thresholds.high) return '✓ High';
  if (confidence >= thresholds.medium) return '⚠ Medium';
  return '⚠ Low';
}

/**
 * Clear the threshold cache (useful for testing or when settings change)
 */
export function clearThresholdCache() {
  cachedThresholds = null;
  cacheTimestamp = null;
}
