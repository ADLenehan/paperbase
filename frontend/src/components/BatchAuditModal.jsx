import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import ArrayEditor from './ArrayEditor';
import TableEditor from './TableEditor';
import ArrayOfObjectsEditor from './ArrayOfObjectsEditor';
import ComplexFieldDisplay from './ComplexFieldDisplay';
import {
  getConfidenceColor,
  formatConfidencePercent,
  groupAuditItemsByDocument
} from '../utils/confidenceHelpers';

/**
 * BatchAuditModal - Bulk verification interface for multiple fields
 *
 * Allows users to review and verify multiple low-confidence fields at once
 * in a table view, with inline editing and bulk actions.
 *
 * Props:
 * - isOpen: Whether modal is visible
 * - onClose: Callback when modal is closed
 * - fields: Array of audit items to review
 * - onBatchVerify: Callback when fields are verified (fieldId -> {action, correctedValue, notes})
 * - regenerateAnswer: Whether to regenerate answer after verification
 */
export default function BatchAuditModal({
  isOpen,
  onClose,
  fields = [],
  onBatchVerify,
  regenerateAnswer = false
}) {
  // Track verification state for each field
  const [verifications, setVerifications] = useState({});

  // Track which fields are being edited
  const [editingField, setEditingField] = useState(null);

  // Track edited values
  const [editedValues, setEditedValues] = useState({});

  // Track notes for each field
  const [fieldNotes, setFieldNotes] = useState({});

  // Processing state
  const [isProcessing, setIsProcessing] = useState(false);

  // Statistics
  const [stats, setStats] = useState({
    total: 0,
    verified: 0,
    pending: 0
  });

  // Initialize verification state when fields change
  useEffect(() => {
    if (fields && fields.length > 0) {
      const initialVerifications = {};
      const initialValues = {};
      const initialNotes = {};

      fields.forEach(field => {
        initialVerifications[field.field_id] = null; // null = pending, 'correct', 'incorrect', 'not_found'
        // Handle both simple (field_value) and complex (field_value_json) types
        const initialValue = field.field_type && ['array', 'table', 'array_of_objects'].includes(field.field_type)
          ? field.field_value_json
          : field.field_value;
        initialValues[field.field_id] = initialValue;
        initialNotes[field.field_id] = '';
      });

      setVerifications(initialVerifications);
      setEditedValues(initialValues);
      setFieldNotes(initialNotes);
      updateStats(initialVerifications);
    }
  }, [fields]);

  // Update statistics
  const updateStats = (currentVerifications) => {
    const total = Object.keys(currentVerifications).length;
    const verified = Object.values(currentVerifications).filter(v => v !== null).length;
    const pending = total - verified;

    setStats({ total, verified, pending });
  };

  // Handle verification action for a field
  const handleVerify = (fieldId, action) => {
    const newVerifications = {
      ...verifications,
      [fieldId]: action
    };

    setVerifications(newVerifications);
    updateStats(newVerifications);

    // If marking as incorrect, enable editing
    if (action === 'incorrect') {
      setEditingField(fieldId);
    } else {
      setEditingField(null);
    }
  };

  // Handle value edit
  const handleValueChange = (fieldId, newValue) => {
    setEditedValues({
      ...editedValues,
      [fieldId]: newValue
    });
  };

  // Handle notes change
  const handleNotesChange = (fieldId, notes) => {
    setFieldNotes({
      ...fieldNotes,
      [fieldId]: notes
    });
  };

  // Handle submit all verifications
  const handleSubmitAll = async () => {
    setIsProcessing(true);

    try {
      // Build verifications map
      const verificationsMap = {};

      Object.entries(verifications).forEach(([fieldId, action]) => {
        if (action !== null) {
          verificationsMap[fieldId] = {
            action,
            corrected_value: action === 'incorrect' ? editedValues[fieldId] : null,
            notes: fieldNotes[fieldId] || null
          };
        }
      });

      // Call parent callback
      if (onBatchVerify) {
        await onBatchVerify(verificationsMap);
      }

      // Close modal
      handleClose();
    } catch (error) {
      console.error('Batch verification failed:', error);
      alert('Failed to verify fields. Please try again.');
    } finally {
      setIsProcessing(false);
    }
  };

  // Handle close
  const handleClose = () => {
    if (!isProcessing) {
      onClose();
    }
  };

  // Keyboard shortcuts
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e) => {
      // Esc to close
      if (e.key === 'Escape' && !isProcessing) {
        handleClose();
      }

      // Ctrl+Enter to submit
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && stats.verified > 0) {
        handleSubmitAll();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, isProcessing, stats.verified]);

  // Don't render if not open
  if (!isOpen) return null;

  // Group fields by document for better organization
  const groupedFields = groupAuditItemsByDocument(fields);

  return createPortal(
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black bg-opacity-50 transition-opacity"
        onClick={handleClose}
      />

      {/* Modal */}
      <div className="flex min-h-full items-center justify-center p-4">
        <div
          className="relative bg-white rounded-lg shadow-xl max-w-6xl w-full max-h-[90vh] flex flex-col"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold text-gray-900">
                Batch Review - {stats.total} Fields
              </h2>
              <p className="text-sm text-gray-600 mt-1">
                Review and verify multiple fields at once
              </p>
            </div>

            {/* Stats */}
            <div className="flex items-center gap-4">
              <div className="text-sm">
                <span className="font-medium text-green-600">{stats.verified}</span>
                <span className="text-gray-500"> verified</span>
              </div>
              <div className="text-sm">
                <span className="font-medium text-gray-600">{stats.pending}</span>
                <span className="text-gray-500"> pending</span>
              </div>
              <button
                onClick={handleClose}
                disabled={isProcessing}
                className="text-gray-400 hover:text-gray-600 disabled:opacity-50"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>

          {/* Content - Table View */}
          <div className="flex-1 overflow-y-auto px-6 py-4">
            {Object.entries(groupedFields).map(([docId, { filename, fields: docFields }]) => (
              <div key={docId} className="mb-6">
                {/* Document Header */}
                <div className="flex items-center gap-2 mb-3 pb-2 border-b border-gray-200">
                  <span className="text-lg">📄</span>
                  <h3 className="font-medium text-gray-900">{filename}</h3>
                  <span className="text-sm text-gray-500">
                    ({docFields.length} field{docFields.length !== 1 ? 's' : ''})
                  </span>
                </div>

                {/* Fields Table */}
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Field
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Extracted Value
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Confidence
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Actions
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Notes
                        </th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {docFields.map((field) => {
                        const fieldId = field.field_id;
                        const verification = verifications[fieldId];
                        const isEditing = editingField === fieldId;
                        const confidenceColor = getConfidenceColor(field.confidence);

                        return (
                          <tr
                            key={fieldId}
                            className={`
                              ${verification === 'correct' ? 'bg-green-50' : ''}
                              ${verification === 'incorrect' ? 'bg-yellow-50' : ''}
                              ${verification === 'not_found' ? 'bg-red-50' : ''}
                            `}
                          >
                            {/* Field Name */}
                            <td className="px-4 py-3 text-sm font-medium text-gray-900">
                              {field.field_name}
                              {verification && (
                                <div className="text-xs mt-1">
                                  {verification === 'correct' && <span className="text-green-600">✓ Correct</span>}
                                  {verification === 'incorrect' && <span className="text-yellow-600">✏ Fixed</span>}
                                  {verification === 'not_found' && <span className="text-red-600">✗ Not Found</span>}
                                </div>
                              )}
                            </td>

                            {/* Value (editable if incorrect) */}
                            <td className="px-4 py-3 text-sm text-gray-700">
                              {isEditing || verification === 'incorrect' ? (
                                <>
                                  {field.field_type === 'array' && (
                                    <ArrayEditor
                                      value={editedValues[fieldId]}
                                      onChange={(val) => handleValueChange(fieldId, val)}
                                      className="w-full"
                                    />
                                  )}
                                  {field.field_type === 'table' && (
                                    <TableEditor
                                      value={editedValues[fieldId]}
                                      onChange={(val) => handleValueChange(fieldId, val)}
                                      className="w-full"
                                    />
                                  )}
                                  {field.field_type === 'array_of_objects' && (
                                    <ArrayOfObjectsEditor
                                      value={editedValues[fieldId]}
                                      onChange={(val) => handleValueChange(fieldId, val)}
                                      className="w-full"
                                    />
                                  )}
                                  {(!field.field_type || ['text', 'date', 'number', 'boolean'].includes(field.field_type)) && (
                                    <input
                                      type="text"
                                      value={editedValues[fieldId] || ''}
                                      onChange={(e) => handleValueChange(fieldId, e.target.value)}
                                      className="w-full px-2 py-1 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                      placeholder="Enter corrected value"
                                    />
                                  )}
                                </>
                              ) : (
                                <>
                                  {field.field_type && ['array', 'table', 'array_of_objects'].includes(field.field_type) ? (
                                    <ComplexFieldDisplay field={field} />
                                  ) : (
                                    <span>{field.field_value || <em className="text-gray-400">No value</em>}</span>
                                  )}
                                </>
                              )}
                            </td>

                            {/* Confidence */}
                            <td className="px-4 py-3 text-sm">
                              {(() => {
                                const colorClasses = {
                                  green: 'bg-green-100 text-green-800 border-green-300',
                                  yellow: 'bg-yellow-100 text-yellow-800 border-yellow-300',
                                  red: 'bg-red-100 text-red-800 border-red-300'
                                };
                                const confidenceColorClass = colorClasses[confidenceColor] || colorClasses.yellow;

                                return (
                                  <span className={`inline-flex px-2 py-1 rounded-full text-xs font-medium border ${confidenceColorClass}`}>
                                    {formatConfidencePercent(field.confidence)}
                                  </span>
                                );
                              })()}
                            </td>

                            {/* Action Buttons */}
                            <td className="px-4 py-3 text-sm">
                              <div className="flex gap-1">
                                <button
                                  onClick={() => handleVerify(fieldId, 'correct')}
                                  className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                                    verification === 'correct'
                                      ? 'bg-green-600 text-white'
                                      : 'bg-gray-100 text-gray-700 hover:bg-green-100'
                                  }`}
                                  title="Mark as correct (1)"
                                >
                                  ✓ Correct
                                </button>
                                <button
                                  onClick={() => handleVerify(fieldId, 'incorrect')}
                                  className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                                    verification === 'incorrect'
                                      ? 'bg-yellow-600 text-white'
                                      : 'bg-gray-100 text-gray-700 hover:bg-yellow-100'
                                  }`}
                                  title="Fix value (2)"
                                >
                                  ✏ Fix
                                </button>
                                <button
                                  onClick={() => handleVerify(fieldId, 'not_found')}
                                  className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                                    verification === 'not_found'
                                      ? 'bg-red-600 text-white'
                                      : 'bg-gray-100 text-gray-700 hover:bg-red-100'
                                  }`}
                                  title="Not found (3)"
                                >
                                  ✗ Not Found
                                </button>
                              </div>
                            </td>

                            {/* Notes */}
                            <td className="px-4 py-3 text-sm">
                              <input
                                type="text"
                                value={fieldNotes[fieldId] || ''}
                                onChange={(e) => handleNotesChange(fieldId, e.target.value)}
                                className="w-full px-2 py-1 border border-gray-300 rounded text-xs focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                placeholder="Optional notes..."
                              />
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </div>

          {/* Footer - Actions */}
          <div className="px-6 py-4 border-t border-gray-200 bg-gray-50">
            <div className="flex items-center justify-between">
              <div className="text-sm text-gray-600">
                <span className="font-medium">{stats.verified}</span> of <span className="font-medium">{stats.total}</span> fields reviewed
                {regenerateAnswer && stats.verified > 0 && (
                  <span className="ml-3 text-blue-600">
                    Answer will be regenerated after verification
                  </span>
                )}
              </div>

              <div className="flex gap-3">
                <button
                  onClick={handleClose}
                  disabled={isProcessing}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 transition-colors"
                >
                  Cancel
                </button>

                <button
                  onClick={handleSubmitAll}
                  disabled={isProcessing || stats.verified === 0}
                  className="px-6 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
                >
                  {isProcessing ? (
                    <>
                      <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      Processing...
                    </>
                  ) : (
                    <>
                      Submit {stats.verified > 0 ? `(${stats.verified})` : ''}
                      <span className="text-xs opacity-75">Ctrl+Enter</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Keyboard hints */}
            <div className="mt-3 text-xs text-gray-500 flex gap-4">
              <span>💡 Tips:</span>
              <span>Use action buttons to verify each field</span>
              <span>•</span>
              <span>Edit values inline when marked as "Fix"</span>
              <span>•</span>
              <span>Press Ctrl+Enter to submit all</span>
            </div>
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
}
