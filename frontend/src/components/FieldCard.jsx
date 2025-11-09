import { useState } from 'react';
import ComplexFieldDisplay from './ComplexFieldDisplay';
import ArrayEditor from './ArrayEditor';
import TableEditor from './TableEditor';
import ArrayOfObjectsEditor from './ArrayOfObjectsEditor';
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
 *
 * NEW: Inline editing support
 * - editable: Enable inline editing (click value to edit)
 * - onSave: Called when user saves edited value
 */
export default function FieldCard({
  field,
  onViewCitation,
  onEdit,
  onVerify,
  compact = false,
  editable = false,
  onSave
}) {
  const [expanded, setExpanded] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(field.value || '');
  const [editValueJson, setEditValueJson] = useState(field.field_value_json);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState(null);

  const confidenceColor = getConfidenceColor(field.confidence);
  const hasCitation = field.source_bbox && field.source_page !== null && field.source_page !== undefined;

  // Complex types: array, table, array_of_objects
  const isComplexType = ['array', 'table', 'array_of_objects'].includes(field.field_type);

  // Save handler
  const handleSave = async () => {
    if (!onSave) return;

    // Check if value changed
    const newValue = isComplexType ? editValueJson : editValue;
    const oldValue = isComplexType ? field.field_value_json : field.value;

    if (JSON.stringify(newValue) === JSON.stringify(oldValue)) {
      setIsEditing(false);
      return;
    }

    setIsSaving(true);
    setError(null);

    try {
      // For complex types, pass JSON, for simple types pass string
      const valueToSave = isComplexType ? JSON.stringify(editValueJson) : editValue;
      await onSave(field.id, valueToSave);
      setIsEditing(false);
    } catch (err) {
      console.error('Failed to save field:', err);
      setError('Failed to save. Please try again.');
    } finally {
      setIsSaving(false);
    }
  };

  // Cancel handler
  const handleCancel = () => {
    setEditValue(field.value || '');
    setEditValueJson(field.field_value_json);
    setError(null);
    setIsEditing(false);
  };

  // Start editing
  const handleStartEdit = () => {
    setEditValue(field.value || '');
    setEditValueJson(field.field_value_json);
    setIsEditing(true);
  };

  // Handle keyboard shortcuts
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !isComplexType) {
      e.preventDefault();
      handleSave();
    } else if (e.key === 'Escape') {
      handleCancel();
    }
  };

  const confidenceColorClasses = {
    green: 'bg-mint-100 text-mint-800 border-mint-300',
    yellow: 'bg-yellow-100 text-yellow-800 border-yellow-300',
    red: 'bg-primary-100 text-primary-800 border-primary-300'
  };

  const renderValue = () => {
    // Edit mode
    if (isEditing) {
      return (
        <div className="mt-2 space-y-3">
          {/* Error message */}
          {error && (
            <div className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-2 py-1">
              {error}
            </div>
          )}

          {/* Input based on field type */}
          {field.field_type === 'text' && (
            <input
              type="text"
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              onKeyDown={handleKeyDown}
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-periwinkle-500 focus:border-transparent"
              placeholder="Enter value..."
              autoFocus
            />
          )}

          {field.field_type === 'date' && (
            <input
              type="date"
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              onKeyDown={handleKeyDown}
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-periwinkle-500 focus:border-transparent"
              autoFocus
            />
          )}

          {field.field_type === 'number' && (
            <input
              type="number"
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              onKeyDown={handleKeyDown}
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-periwinkle-500 focus:border-transparent"
              placeholder="Enter number..."
              autoFocus
            />
          )}

          {field.field_type === 'boolean' && (
            <select
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              onKeyDown={handleKeyDown}
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-periwinkle-500 focus:border-transparent"
              autoFocus
            >
              <option value="">Select...</option>
              <option value="true">True</option>
              <option value="false">False</option>
            </select>
          )}

          {field.field_type === 'array' && (
            <ArrayEditor
              value={editValueJson || []}
              onChange={setEditValueJson}
            />
          )}

          {field.field_type === 'table' && (
            <TableEditor
              value={editValueJson || { headers: [], rows: [] }}
              onChange={setEditValueJson}
            />
          )}

          {field.field_type === 'array_of_objects' && (
            <ArrayOfObjectsEditor
              value={editValueJson || []}
              onChange={setEditValueJson}
            />
          )}

          {/* Default textarea for other types */}
          {!['text', 'date', 'number', 'boolean', 'array', 'table', 'array_of_objects'].includes(field.field_type) && (
            <textarea
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              onKeyDown={handleKeyDown}
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-periwinkle-500 focus:border-transparent"
              rows={3}
              placeholder="Enter value..."
              autoFocus
            />
          )}

          {/* Action buttons */}
          <div className="flex items-center gap-2">
            <button
              onClick={handleCancel}
              disabled={isSaving}
              className="px-3 py-1.5 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={isSaving}
              className="px-3 py-1.5 text-sm font-medium text-white bg-periwinkle-600 rounded-lg hover:bg-periwinkle-700 transition-colors disabled:opacity-50 flex items-center gap-1"
            >
              {isSaving ? (
                <>
                  <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Saving...
                </>
              ) : (
                'Save'
              )}
            </button>
          </div>
        </div>
      );
    }

    // Display mode
    if (!field.value && !field.field_value_json) {
      return (
        <div
          className={`mt-2 ${editable ? 'cursor-pointer hover:bg-gray-50 rounded p-2 -m-2' : ''}`}
          onClick={editable ? handleStartEdit : undefined}
        >
          <span className="text-gray-400 italic">No value</span>
          {editable && <span className="ml-2 text-xs text-gray-400">(click to edit)</span>}
        </div>
      );
    }

    // Complex types
    if (isComplexType && field.field_value_json) {
      return (
        <div className={`mt-2 group ${editable ? 'cursor-pointer hover:bg-gray-50 rounded p-2 -m-2' : ''}`}>
          <div onClick={editable ? handleStartEdit : undefined}>
            <ComplexFieldDisplay
              fieldType={field.field_type}
              value={field.field_value_json}
              compact={!expanded}
            />
            {!compact && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setExpanded(!expanded);
                }}
                className="mt-2 text-xs text-periwinkle-600 hover:text-periwinkle-700 font-medium"
              >
                {expanded ? 'Show less' : 'Show more'}
              </button>
            )}
            {editable && (
              <span className="ml-2 text-xs text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity">
                (click to edit)
              </span>
            )}
          </div>
        </div>
      );
    }

    // Simple types
    return (
      <div
        className={`mt-2 text-sm text-gray-900 break-words ${editable ? 'cursor-pointer hover:bg-gray-50 rounded p-2 -m-2 group' : ''}`}
        onClick={editable ? handleStartEdit : undefined}
      >
        {field.value || 'N/A'}
        {editable && (
          <span className="ml-2 text-xs text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity">
            (click to edit)
          </span>
        )}
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
            <span className="inline-flex items-center px-2 py-1 text-xs font-medium rounded bg-periwinkle-100 text-periwinkle-700">
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
