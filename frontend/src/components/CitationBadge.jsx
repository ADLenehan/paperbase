import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getConfidenceColor, formatConfidencePercent, truncateFieldValue } from '../utils/confidenceHelpers';

/**
 * CitationBadge - Reusable confidence indicator with audit link
 *
 * A small, clickable badge that shows confidence level and links to audit interface.
 * Can be used inline in text or as standalone element.
 *
 * Props:
 * - fieldId: Field ID for audit tracking
 * - documentId: Document ID
 * - fieldName: Name of the field
 * - fieldValue: Extracted value
 * - confidence: Confidence score (0.0-1.0)
 * - auditUrl: URL to audit page
 * - filename: Document filename (for tooltip)
 * - variant: 'inline' | 'standalone' (default: 'inline')
 * - onClick: Optional custom click handler
 */
export default function CitationBadge({
  fieldId,
  documentId,
  fieldName,
  fieldValue,
  confidence,
  auditUrl,
  filename,
  variant = 'inline',
  onClick
}) {
  const navigate = useNavigate();
  const [showTooltip, setShowTooltip] = useState(false);

  const color = getConfidenceColor(confidence);
  const percentage = formatConfidencePercent(confidence);

  // Color classes for different confidence levels
  const colorClasses = {
    green: {
      bg: 'bg-green-100 hover:bg-green-200',
      text: 'text-green-800',
      border: 'border-green-300'
    },
    yellow: {
      bg: 'bg-yellow-100 hover:bg-yellow-200',
      text: 'text-yellow-800',
      border: 'border-yellow-300'
    },
    red: {
      bg: 'bg-red-100 hover:bg-red-200',
      text: 'text-red-800',
      border: 'border-red-300'
    }
  };

  const classes = colorClasses[color] || colorClasses.yellow;

  const handleClick = (e) => {
    e.stopPropagation();

    if (onClick) {
      onClick(e);
      return;
    }

    // Navigate to audit URL
    if (auditUrl) {
      // Extract path from audit URL (remove domain if present)
      const urlPath = auditUrl.includes('http')
        ? new URL(auditUrl).pathname + new URL(auditUrl).search
        : auditUrl;
      navigate(urlPath);
    }
  };

  // Inline variant - compact badge for embedding in text
  if (variant === 'inline') {
    return (
      <span className="relative inline-flex">
        <button
          onClick={handleClick}
          onMouseEnter={() => setShowTooltip(true)}
          onMouseLeave={() => setShowTooltip(false)}
          className={`inline-flex items-center px-1.5 py-0.5 text-xs font-medium rounded border ${classes.bg} ${classes.text} ${classes.border} transition-colors cursor-pointer`}
          title={`${fieldName}: ${percentage} confidence - Click to review`}
        >
          {confidence < 0.8 && <span className="mr-0.5">⚠</span>}
          {percentage}
        </button>

        {/* Tooltip */}
        {showTooltip && (
          <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-3 py-2 bg-gray-900 text-white text-xs rounded shadow-lg whitespace-nowrap z-50">
            <div className="font-semibold">{fieldName}</div>
            <div className="text-gray-300 mt-1">{truncateFieldValue(fieldValue, 40)}</div>
            <div className="text-gray-400 text-xs mt-1">{filename}</div>
            <div className="mt-1 text-blue-300">Click to review →</div>
            {/* Arrow */}
            <div className="absolute top-full left-1/2 transform -translate-x-1/2 w-2 h-2 bg-gray-900 rotate-45"></div>
          </div>
        )}
      </span>
    );
  }

  // Standalone variant - full display with field details
  return (
    <button
      onClick={handleClick}
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
      className={`flex items-center justify-between gap-2 px-3 py-2 text-sm rounded-lg border ${classes.bg} ${classes.text} ${classes.border} transition-colors hover:shadow-md cursor-pointer w-full text-left`}
    >
      <div className="flex-1 min-w-0">
        <div className="font-medium flex items-center gap-2">
          {confidence < 0.8 && <span>⚠</span>}
          <span className="truncate">{fieldName}</span>
        </div>
        <div className="text-xs opacity-75 truncate mt-0.5">
          {truncateFieldValue(fieldValue, 60)}
        </div>
      </div>

      <div className="flex items-center gap-2 flex-shrink-0">
        <span className={`px-2 py-1 text-xs font-bold rounded ${classes.bg} ${classes.border}`}>
          {percentage}
        </span>
        <span className="text-xs">→</span>
      </div>

      {/* Tooltip for standalone too */}
      {showTooltip && (
        <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-3 py-2 bg-gray-900 text-white text-xs rounded shadow-lg whitespace-nowrap z-50">
          <div className="text-gray-400">Click to review in audit interface</div>
          <div className="absolute top-full left-1/2 transform -translate-x-1/2 w-2 h-2 bg-gray-900 rotate-45"></div>
        </div>
      )}
    </button>
  );
}
