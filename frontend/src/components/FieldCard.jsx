import { useState } from 'react';
import ComplexFieldDisplay from './ComplexFieldDisplay';
import { getConfidenceColor, formatConfidencePercent } from '../utils/confidenceHelpers';

/**
 * FieldCard - Display a single extracted field with metadata
 *
 * Shows:
 * - Field name and type
 * - Extracted value (with complex type support)
 * - Confidence badge (color-coded)
 * - Citation link (if bbox available)
 * - Verification status
 * - Quick edit button
 */
export default function FieldCard({ field, onViewCitation, onEdit, onVerify, compact = false }) {
  const [expanded, setExpanded] = useState(false);

  const confidenceColor = getConfidenceColor(field.confidence);
  const hasCitation = field.source_bbox && field.source_page !== null && field.source_page !== undefined;

  // Complex types: array, table, array_of_objects
  const isComplexType = ['array', 'table', 'array_of_objects'].includes(field.field_type);

  const confidenceColorClasses = {
    green: 'bg-mint-100 text-mint-800 border-mint-300',
    yellow: 'bg-yellow-100 text-yellow-800 border-yellow-300',
    red: 'bg-primary-100 text-primary-800 border-primary-300'
  };

  const renderValue = () => {
    if (!field.value && !field.field_value_json) {
      return <span className="text-gray-400 italic">No value</span>;
    }

    // Complex types
    if (isComplexType && field.field_value_json) {
      return (
        <div className="mt-2">
          <ComplexFieldDisplay
            fieldType={field.field_type}
            value={field.field_value_json}
            compact={!expanded}
          />
          {!compact && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="mt-2 text-xs text-periwinkle-600 hover:text-periwinkle-700 font-medium"
            >
              {expanded ? 'Show less' : 'Show more'}
            </button>
          )}
        </div>
      );
    }

    // Simple types
    return (
      <div className="mt-2 text-sm text-gray-900 break-words">
        {field.value || 'N/A'}
      </div>
    );
  };

  return (
    <div className={`bg-white border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow ${compact ? 'p-3' : ''}`}>
      {/* Header: Field name + confidence */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex-1 min-w-0">
          <h4 className={`font-medium text-gray-900 ${compact ? 'text-sm' : 'text-base'} truncate`}>
            {field.name}
          </h4>
          <div className="flex items-center gap-2 mt-1">
            <span className={`text-xs px-1.5 py-0.5 rounded bg-gray-100 text-gray-600 font-mono`}>
              {field.field_type || 'text'}
            </span>
            {field.required && (
              <span className="text-xs text-gray-500">• Required</span>
            )}
          </div>
        </div>

        {/* Confidence badge */}
        <span className={`inline-flex items-center px-2 py-1 text-xs font-semibold rounded border ${confidenceColorClasses[confidenceColor]} whitespace-nowrap`}>
          {formatConfidencePercent(field.confidence)}
        </span>
      </div>

      {/* Value */}
      {renderValue()}

      {/* Actions row */}
      <div className="flex items-center gap-2 mt-3 pt-3 border-t border-gray-100">
        {/* Citation button */}
        {hasCitation ? (
          <button
            onClick={() => onViewCitation?.(field)}
            className="flex items-center gap-1 text-xs text-periwinkle-600 hover:text-periwinkle-700 font-medium"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            View Citation →
          </button>
        ) : (
          <span className="text-xs text-gray-400 italic">No citation</span>
        )}

        {/* Verification status */}
        <div className="ml-auto flex items-center gap-2">
          {field.verified ? (
            <span className="inline-flex items-center px-2 py-1 text-xs font-medium rounded bg-mint-100 text-mint-700">
              ✓ Verified
            </span>
          ) : field.confidence < 0.6 ? (
            <span className="inline-flex items-center px-2 py-1 text-xs font-medium rounded bg-yellow-100 text-yellow-700">
              ⚠ Needs Review
            </span>
          ) : null}

          {/* Quick actions */}
          {onVerify && !field.verified && (
            <button
              onClick={() => onVerify?.(field)}
              className="text-xs text-gray-600 hover:text-gray-800 font-medium"
            >
              Verify
            </button>
          )}
          {onEdit && (
            <button
              onClick={() => onEdit?.(field)}
              className="text-xs text-gray-600 hover:text-gray-800 font-medium"
            >
              Edit
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
