import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import PDFExcerpt from './PDFExcerpt';
import ArrayEditor from './ArrayEditor';
import TableEditor from './TableEditor';
import ArrayOfObjectsEditor from './ArrayOfObjectsEditor';
import ComplexFieldDisplay from './ComplexFieldDisplay';
import { getConfidenceColor, formatConfidencePercent } from '../utils/confidenceHelpers';
import { useConfidenceThresholds } from '../hooks/useConfidenceThresholds';

/**
 * InlineAuditModal - Modal for verifying fields without leaving the current page
 *
 * Allows users to verify low-confidence field extractions inline, preserving context.
 * Shows PDF excerpt with highlighted bbox and field editor with verification actions.
 *
 * Props:
 * - isOpen: Boolean to control modal visibility
 * - onClose: Callback when modal is closed
 * - field: Field object { field_id, document_id, filename, field_name, field_value, confidence, source_page, source_bbox }
 * - onVerify: Callback when verification is submitted (fieldId, action, correctedValue, notes)
 * - onNext: Callback to load next field (returns next field object or null)
 * - queuePosition: Optional string like "5 of 12" to show progress
 * - regenerateAnswer: Boolean to control if answer should be regenerated after verification
 */
export default function InlineAuditModal({
  isOpen,
  onClose,
  field,
  onVerify,
  onNext,
  queuePosition,
  regenerateAnswer = false
}) {
  const [action, setAction] = useState(null); // null | 'correct' | 'incorrect' | 'not_found'
  const [correctedValue, setCorrectedValue] = useState('');
  const [notes, setNotes] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showPDF, setShowPDF] = useState(true);

  // Fetch dynamic confidence thresholds
  const thresholds = useConfidenceThresholds();

  // Reset state when field changes
  useEffect(() => {
    if (field) {
      setAction(null);
      // Handle both simple (field_value) and complex (field_value_json) types
      const initialValue = field.field_type && ['array', 'table', 'array_of_objects'].includes(field.field_type)
        ? field.field_value_json
        : field.field_value;
      setCorrectedValue(initialValue || (field.field_type === 'array' ? [] : field.field_type === 'table' ? [] : ''));
      setNotes('');
    }
  }, [field]);

  // Keyboard shortcuts
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e) => {
      // Escape to close
      if (e.key === 'Escape') {
        handleClose();
        return;
      }

      // Ignore if typing in input
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
        return;
      }

      // 1 = Correct
      if (e.key === '1') {
        e.preventDefault();
        handleVerify('correct');
      }
      // 2 = Fix value
      else if (e.key === '2') {
        e.preventDefault();
        setAction('incorrect');
      }
      // 3 = Not found
      else if (e.key === '3') {
        e.preventDefault();
        handleVerify('not_found');
      }
      // S = Skip
      else if (e.key === 's' || e.key === 'S') {
        e.preventDefault();
        handleSkip();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, action, correctedValue]);

  if (!isOpen || !field) return null;

  const handleClose = () => {
    setAction(null);
    setCorrectedValue('');
    setNotes('');
    onClose?.();
  };

  const handleVerify = async (verificationAction) => {
    setIsSubmitting(true);

    try {
      const valueToSubmit = verificationAction === 'incorrect' ? correctedValue : field.field_value;

      await onVerify?.(field.field_id, verificationAction, valueToSubmit, notes);

      // Check if there's a next field
      if (onNext) {
        const nextField = await onNext();
        if (!nextField) {
          // No more fields, close modal
          handleClose();
        }
        // Otherwise, modal will update with new field via props
      } else {
        // No next handler, just close
        handleClose();
      }
    } catch (error) {
      console.error('Verification error:', error);
      alert('Failed to verify field. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSkip = () => {
    if (onNext) {
      onNext();
    } else {
      handleClose();
    }
  };

  const handleSubmitFix = () => {
    // Validate based on field type
    if (field.field_type && ['array', 'table', 'array_of_objects'].includes(field.field_type)) {
      // For complex types, check if value is valid (array/object)
      if (!correctedValue || (Array.isArray(correctedValue) && correctedValue.length === 0)) {
        alert('Please enter a corrected value');
        return;
      }
    } else {
      // For simple types, check if string is non-empty
      if (!correctedValue || !String(correctedValue).trim()) {
        alert('Please enter a corrected value');
        return;
      }
    }
    handleVerify('incorrect');
  };

  // Build PDF URL
  const pdfUrl = field.document_id ? `/api/files/${field.document_id}/preview` : null;

  // Confidence color
  const confidenceColor = getConfidenceColor(field.confidence);
  const colorClasses = {
    green: 'bg-mint-100 text-mint-800 border-mint-300',
    yellow: 'bg-yellow-100 text-yellow-800 border-yellow-300',
    red: 'bg-coral-100 text-coral-800 border-coral-300'
  };

  const modalContent = (
    <div className="fixed inset-0 z-50 overflow-y-auto" aria-labelledby="modal-title" role="dialog" aria-modal="true">
      {/* Background overlay */}
      <div className="flex items-center justify-center min-h-screen px-4 pt-4 pb-20 text-center sm:block sm:p-0">
        <div
          className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity"
          aria-hidden="true"
          onClick={handleClose}
        ></div>

        {/* Modal panel */}
        <div className="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-6xl sm:w-full">
          {/* Header */}
          <div className="bg-gray-50 px-6 py-4 border-b border-gray-200">
            <div className="flex items-center justify-between">
              <div className="flex-1">
                <h3 className="text-lg leading-6 font-medium text-gray-900" id="modal-title">
                  Review Extraction
                </h3>
                {queuePosition && (
                  <p className="mt-1 text-sm text-gray-500">
                    Progress: {queuePosition}
                  </p>
                )}
              </div>
              <button
                onClick={handleClose}
                className="ml-4 text-gray-400 hover:text-gray-500 focus:outline-none"
              >
                <span className="sr-only">Close</span>
                <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>

          {/* Body - Split view */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 p-6" style={{ maxHeight: 'calc(100vh - 250px)' }}>
            {/* Left: PDF Viewer */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-medium text-gray-700">Document Preview</h4>
                <button
                  onClick={() => setShowPDF(!showPDF)}
                  className="text-xs text-blue-600 hover:text-blue-700"
                >
                  {showPDF ? 'Hide' : 'Show'} PDF
                </button>
              </div>

              {showPDF && pdfUrl && (
                <PDFExcerpt
                  fileUrl={pdfUrl}
                  page={field.source_page || 1}
                  bbox={field.source_bbox}
                  fieldLabel={field.field_name}
                  className="h-full"
                />
              )}

              {!showPDF && (
                <div className="bg-gray-100 rounded-lg border-2 border-dashed border-gray-300 p-8 flex items-center justify-center h-96">
                  <div className="text-center text-gray-500">
                    <svg className="mx-auto h-12 w-12 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    <p className="text-sm">PDF preview hidden</p>
                  </div>
                </div>
              )}

              <div className="text-xs text-gray-500 bg-gray-50 p-2 rounded">
                <p><strong>File:</strong> {field.filename}</p>
                {field.source_page && <p><strong>Page:</strong> {field.source_page}</p>}
              </div>
            </div>

            {/* Right: Field Editor */}
            <div className="space-y-4 overflow-y-auto">
              {/* Field Info */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Field Name
                </label>
                <div className="px-3 py-2 bg-gray-50 border border-gray-300 rounded-md text-sm text-gray-900 font-mono">
                  {field.field_name}
                </div>
              </div>

              {/* Extracted Value */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Extracted Value
                  {field.field_type && field.field_type !== 'text' && (
                    <span className="ml-2 text-xs text-gray-500">({field.field_type})</span>
                  )}
                </label>
                <div className="relative">
                  <div className="px-3 py-2 bg-white border border-gray-300 rounded-md text-sm text-gray-900">
                    {field.field_type && ['array', 'table', 'array_of_objects'].includes(field.field_type) ? (
                      <ComplexFieldDisplay field={field} />
                    ) : (
                      field.field_value || <span className="text-gray-400 italic">No value extracted</span>
                    )}
                  </div>
                  <div className="absolute top-2 right-2">
                    <span className={`inline-flex items-center px-2 py-1 text-xs font-medium rounded border ${colorClasses[confidenceColor]}`}>
                      {formatConfidencePercent(field.confidence)}
                    </span>
                  </div>
                </div>
              </div>

              {/* Confidence Warning - Uses dynamic threshold */}
              {field.confidence < thresholds.high && (
                <div className="bg-yellow-50 border-l-4 border-yellow-400 p-3 rounded-r">
                  <div className="flex">
                    <div className="flex-shrink-0">
                      <svg className="h-5 w-5 text-yellow-400" viewBox="0 0 20 20" fill="currentColor">
                        <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                      </svg>
                    </div>
                    <div className="ml-3">
                      <p className="text-sm text-yellow-700">
                        {field.confidence < thresholds.medium
                          ? 'Low confidence extraction. Please verify the value is correct.'
                          : 'Medium confidence extraction. Review recommended.'
                        }
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Action Selection */}
              {action === null && (
                <div className="space-y-2">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Is this extraction correct?
                  </label>

                  <button
                    onClick={() => handleVerify('correct')}
                    disabled={isSubmitting}
                    className="w-full flex items-center justify-center px-4 py-3 border border-transparent text-sm font-medium rounded-md text-white bg-mint-600 hover:bg-mint-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-mint-500 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <svg className="w-5 h-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    Yes, Correct (1)
                  </button>

                  <button
                    onClick={() => setAction('incorrect')}
                    disabled={isSubmitting}
                    className="w-full flex items-center justify-center px-4 py-3 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-periwinkle-500"
                  >
                    <svg className="w-5 h-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                    </svg>
                    No, Fix Value (2)
                  </button>

                  <button
                    onClick={() => handleVerify('not_found')}
                    disabled={isSubmitting}
                    className="w-full flex items-center justify-center px-4 py-3 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-periwinkle-500"
                  >
                    <svg className="w-5 h-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                    Not Found in Document (3)
                  </button>

                  <button
                    onClick={handleSkip}
                    disabled={isSubmitting}
                    className="w-full flex items-center justify-center px-4 py-3 border border-gray-300 text-sm font-medium rounded-md text-gray-500 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500"
                  >
                    Skip for Now (S)
                  </button>
                </div>
              )}

              {/* Fix Value Form */}
              {action === 'incorrect' && (
                <div className="space-y-3 bg-periwinkle-50 p-4 rounded-lg border border-periwinkle-200">
                  <label className="block text-sm font-medium text-gray-700">
                    Corrected Value
                  </label>
                  {/* Conditional Editor Based on Field Type */}
                  {field.field_type === 'array' && (
                    <ArrayEditor
                      value={correctedValue}
                      onChange={(val) => setCorrectedValue(val)}
                      className="w-full"
                    />
                  )}
                  {field.field_type === 'table' && (
                    <TableEditor
                      value={correctedValue}
                      onChange={(val) => setCorrectedValue(val)}
                      className="w-full"
                    />
                  )}
                  {field.field_type === 'array_of_objects' && (
                    <ArrayOfObjectsEditor
                      value={correctedValue}
                      onChange={(val) => setCorrectedValue(val)}
                      className="w-full"
                    />
                  )}
                  {(!field.field_type || ['text', 'date', 'number', 'boolean'].includes(field.field_type)) && (
                    <input
                      type="text"
                      value={correctedValue || ''}
                      onChange={(e) => setCorrectedValue(e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                      placeholder="Enter the correct value"
                      autoFocus
                    />
                  )}

                  <label className="block text-sm font-medium text-gray-700">
                    Notes (Optional)
                  </label>
                  <textarea
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                    rows="2"
                    placeholder="Add any notes about this correction..."
                  />

                  <div className="flex gap-2">
                    <button
                      onClick={handleSubmitFix}
                      disabled={isSubmitting || !correctedValue.trim()}
                      className="flex-1 px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-periwinkle-600 hover:bg-periwinkle-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-periwinkle-500 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {isSubmitting ? 'Submitting...' : 'Submit Correction'}
                    </button>
                    <button
                      onClick={() => setAction(null)}
                      disabled={isSubmitting}
                      className="px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}

              {/* Keyboard Shortcuts Help */}
              <div className="bg-gray-50 p-3 rounded-lg border border-gray-200">
                <p className="text-xs font-medium text-gray-700 mb-2">Keyboard Shortcuts:</p>
                <div className="grid grid-cols-2 gap-2 text-xs text-gray-600">
                  <div><kbd className="px-1 py-0.5 bg-white border border-gray-300 rounded">1</kbd> Correct</div>
                  <div><kbd className="px-1 py-0.5 bg-white border border-gray-300 rounded">2</kbd> Fix Value</div>
                  <div><kbd className="px-1 py-0.5 bg-white border border-gray-300 rounded">3</kbd> Not Found</div>
                  <div><kbd className="px-1 py-0.5 bg-white border border-gray-300 rounded">S</kbd> Skip</div>
                  <div><kbd className="px-1 py-0.5 bg-white border border-gray-300 rounded">Esc</kbd> Close</div>
                </div>
              </div>
            </div>
          </div>

          {/* Footer */}
          {regenerateAnswer && (
            <div className="bg-gray-50 px-6 py-3 border-t border-gray-200">
              <p className="text-xs text-gray-600">
                <svg className="inline w-4 h-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Answer will be updated with verified data
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );

  return createPortal(modalContent, document.body);
}
