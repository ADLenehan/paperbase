/**
 * Utility functions for handling confidence scores and audit metadata
 */

/**
 * Get color class for confidence level (Tailwind CSS)
 * @param {number} confidence - Confidence score (0.0-1.0)
 * @returns {string} Color class prefix
 */
export const getConfidenceColor = (confidence) => {
  if (confidence >= 0.8) return 'green';
  if (confidence >= 0.6) return 'yellow';
  return 'red';
};

/**
 * Get badge text for confidence level
 * @param {number} confidence - Confidence score (0.0-1.0)
 * @returns {string} Badge text with icon
 */
export const getConfidenceBadgeText = (confidence) => {
  if (confidence >= 0.8) return '✓ High';
  if (confidence >= 0.6) return '⚠ Medium';
  return '⚠ Low';
};

/**
 * Format confidence as percentage
 * @param {number} confidence - Confidence score (0.0-1.0)
 * @returns {string} Formatted percentage (e.g., "85%")
 */
export const formatConfidencePercent = (confidence) => {
  return `${Math.round(confidence * 100)}%`;
};

/**
 * Group audit items by document ID
 * @param {Array} auditItems - Array of audit items
 * @returns {Object} Grouped audit items by document_id
 */
export const groupAuditItemsByDocument = (auditItems) => {
  if (!auditItems || !Array.isArray(auditItems)) return {};

  return auditItems.reduce((acc, item) => {
    const docId = item.document_id;
    if (!acc[docId]) {
      acc[docId] = {
        filename: item.filename,
        document_id: docId,
        fields: []
      };
    }
    acc[docId].fields.push(item);
    return acc;
  }, {});
};

/**
 * Calculate average confidence for a group of fields
 * @param {Array} fields - Array of field objects with confidence scores
 * @returns {number} Average confidence (0.0-1.0)
 */
export const calculateAverageConfidence = (fields) => {
  if (!fields || fields.length === 0) return 1.0;

  const total = fields.reduce((sum, field) => sum + (field.confidence || 0), 0);
  return total / fields.length;
};

/**
 * Determine if audit is recommended based on confidence summary
 * @param {Object} confidenceSummary - Confidence summary object
 * @returns {boolean} True if audit is recommended
 */
export const isAuditRecommended = (confidenceSummary) => {
  if (!confidenceSummary) return false;
  return confidenceSummary.audit_recommended === true ||
         confidenceSummary.low_confidence_count > 0;
};

/**
 * Get confidence level label
 * @param {string} level - Confidence level ('high', 'medium', 'low')
 * @returns {Object} Label config with color and icon
 */
export const getConfidenceLevelConfig = (level) => {
  const configs = {
    high: {
      color: 'green',
      icon: '✓',
      label: 'High Confidence',
      description: 'Data is reliable and verified'
    },
    medium: {
      color: 'yellow',
      icon: '⚠',
      label: 'Medium Confidence',
      description: 'Review recommended for important decisions'
    },
    low: {
      color: 'red',
      icon: '⚠',
      label: 'Low Confidence',
      description: 'Manual review strongly recommended'
    },
    unknown: {
      color: 'gray',
      icon: '?',
      label: 'Unknown',
      description: 'Confidence data not available'
    }
  };

  return configs[level] || configs.unknown;
};

/**
 * Truncate long field values for display
 * @param {string} value - Field value
 * @param {number} maxLength - Maximum length
 * @returns {string} Truncated value
 */
export const truncateFieldValue = (value, maxLength = 50) => {
  if (!value) return '';
  const str = String(value);
  if (str.length <= maxLength) return str;
  return str.substring(0, maxLength) + '...';
};
