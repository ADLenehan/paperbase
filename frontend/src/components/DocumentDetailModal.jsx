import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import InlineAuditModal from './InlineAuditModal';
import ComplexFieldDisplay from './ComplexFieldDisplay';
import { getConfidenceColor, formatConfidencePercent, truncateFieldValue } from '../utils/confidenceHelpers';
import { useConfidenceThresholds } from '../hooks/useConfidenceThresholds';
import apiClient from '../api/client';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/**
 * DocumentDetailModal - Modal showing document details with extracted fields
 *
 * Features:
 * - Overview tab: Document metadata and stats
 * - Extractions tab: All extracted fields with confidence scores
 * - Click any field to verify inline (opens InlineAuditModal)
 * - Quick access to full audit view
 */
export default function DocumentDetailModal({ isOpen, onClose, documentId }) {
  const [activeTab, setActiveTab] = useState('overview'); // 'overview' | 'extractions'
  const [document, setDocument] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Inline audit state
  const [showAuditModal, setShowAuditModal] = useState(false);
  const [currentField, setCurrentField] = useState(null);
  const [auditQueue, setAuditQueue] = useState([]);
  const [auditIndex, setAuditIndex] = useState(0);

  const navigate = useNavigate();
  const thresholds = useConfidenceThresholds();

  // Fetch document details when modal opens
  useEffect(() => {
    if (isOpen && documentId) {
      fetchDocument();
    }
  }, [isOpen, documentId]);

  const fetchDocument = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_URL}/api/documents/${documentId}`);
      if (!response.ok) throw new Error('Failed to fetch document');

      const data = await response.json();
      setDocument(data);
    } catch (err) {
      console.error('Error fetching document:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setActiveTab('overview');
    setDocument(null);
    setShowAuditModal(false);
    setCurrentField(null);
    onClose?.();
  };

  const handleFieldClick = (field) => {
    // Build audit queue starting from this field
    const lowConfidenceFields = document.fields
      .filter(f => f.confidence < thresholds.audit)
      .sort((a, b) => a.confidence - b.confidence);

    const startIndex = lowConfidenceFields.findIndex(f => f.id === field.id);

    if (startIndex >= 0) {
      setAuditQueue(lowConfidenceFields);
      setAuditIndex(startIndex);
      setCurrentField(buildAuditField(lowConfidenceFields[startIndex]));
      setShowAuditModal(true);
    } else {
      // Field not in audit queue, show it standalone
      setAuditQueue([field]);
      setAuditIndex(0);
      setCurrentField(buildAuditField(field));
      setShowAuditModal(true);
    }
  };

  const buildAuditField = (field) => {
    return {
      field_id: field.id,
      document_id: documentId,
      filename: document.filename,
      field_name: field.name,
      field_value: field.value,
      field_type: field.field_type || 'text',
      field_value_json: field.field_value_json,
      confidence: field.confidence,
      source_page: field.source_page,
      source_bbox: field.source_bbox
    };
  };

  const handleVerify = async (fieldId, action, correctedValue, notes) => {
    try {
      await apiClient.post('/api/audit/verify', {
        field_id: fieldId,
        action,
        corrected_value: correctedValue,
        notes
      });

      // Refresh document data
      await fetchDocument();
    } catch (err) {
      console.error('Verification error:', err);
      throw err;
    }
  };

  const handleNextField = async () => {
    const nextIndex = auditIndex + 1;
    if (nextIndex < auditQueue.length) {
      setAuditIndex(nextIndex);
      setCurrentField(buildAuditField(auditQueue[nextIndex]));
      return auditQueue[nextIndex];
    }
    return null;
  };

  const handleReviewAll = () => {
    const lowConfidenceFields = document.fields
      .filter(f => f.confidence < thresholds.audit)
      .sort((a, b) => a.confidence - b.confidence);

    if (lowConfidenceFields.length > 0) {
      setAuditQueue(lowConfidenceFields);
      setAuditIndex(0);
      setCurrentField(buildAuditField(lowConfidenceFields[0]));
      setShowAuditModal(true);
    }
  };

  const handleOpenFullAudit = () => {
    handleClose();
    navigate(`/audit/document/${documentId}`);
  };

  if (!isOpen) return null;

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
        <div className="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-5xl sm:w-full">
          {/* Header */}
          <div className="bg-gray-50 px-6 py-4 border-b border-gray-200">
            <div className="flex items-center justify-between">
              <div className="flex-1">
                <h3 className="text-lg leading-6 font-medium text-gray-900" id="modal-title">
                  Document Details
                </h3>
                {document && (
                  <p className="mt-1 text-sm text-gray-500">
                    {document.filename}
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

            {/* Tabs */}
            <div className="mt-4 flex space-x-4 border-b border-gray-200">
              <button
                onClick={() => setActiveTab('overview')}
                className={`pb-2 px-1 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'overview'
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Overview
              </button>
              <button
                onClick={() => setActiveTab('extractions')}
                className={`pb-2 px-1 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'extractions'
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Extractions
                {document && document.fields && (
                  <span className="ml-2 text-xs text-gray-400">
                    ({document.fields.length})
                  </span>
                )}
              </button>
            </div>
          </div>

          {/* Body */}
          <div className="p-6" style={{ maxHeight: 'calc(100vh - 250px)', overflowY: 'auto' }}>
            {loading && (
              <div className="flex items-center justify-center py-12">
                <div className="text-center">
                  <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mb-2"></div>
                  <p className="text-sm text-gray-600">Loading document...</p>
                </div>
              </div>
            )}

            {error && (
              <div className="bg-red-50 border-l-4 border-red-400 p-4 rounded-r">
                <div className="flex">
                  <div className="flex-shrink-0">
                    <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                    </svg>
                  </div>
                  <div className="ml-3">
                    <p className="text-sm text-red-700">{error}</p>
                  </div>
                </div>
              </div>
            )}

            {!loading && !error && document && (
              <>
                {activeTab === 'overview' && (
                  <OverviewTab
                    document={document}
                    thresholds={thresholds}
                    onReviewAll={handleReviewAll}
                    onOpenFullAudit={handleOpenFullAudit}
                  />
                )}

                {activeTab === 'extractions' && (
                  <ExtractionsTab
                    document={document}
                    thresholds={thresholds}
                    onFieldClick={handleFieldClick}
                  />
                )}
              </>
            )}
          </div>

          {/* Footer */}
          <div className="bg-gray-50 px-6 py-4 border-t border-gray-200">
            <div className="flex items-center justify-between">
              <button
                onClick={handleClose}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
              >
                Close
              </button>
              <button
                onClick={handleOpenFullAudit}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
              >
                Open Full Audit View
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Inline Audit Modal */}
      {showAuditModal && currentField && (
        <InlineAuditModal
          isOpen={showAuditModal}
          onClose={() => setShowAuditModal(false)}
          field={currentField}
          onVerify={handleVerify}
          onNext={handleNextField}
          queuePosition={auditQueue.length > 1 ? `${auditIndex + 1} of ${auditQueue.length}` : null}
          regenerateAnswer={false}
        />
      )}
    </div>
  );

  return createPortal(modalContent, document.body);
}

function OverviewTab({ document, thresholds, onReviewAll, onOpenFullAudit }) {
  const lowConfidenceCount = document.fields?.filter(f => f.confidence < thresholds.audit).length || 0;
  const verifiedCount = document.fields?.filter(f => f.verified).length || 0;
  const totalFields = document.fields?.length || 0;
  const verificationPercent = totalFields > 0 ? Math.round((verifiedCount / totalFields) * 100) : 0;

  const statusConfig = {
    completed: { color: 'green', icon: '✓', label: 'Completed' },
    verified: { color: 'green', icon: '✓', label: 'Verified' },
    processing: { color: 'blue', icon: '⟳', label: 'Processing' },
    error: { color: 'red', icon: '✗', label: 'Error' }
  };

  const status = statusConfig[document.status] || { color: 'gray', icon: '•', label: document.status };

  return (
    <div className="space-y-6">
      {/* Document Metadata */}
      <div>
        <h4 className="text-sm font-medium text-gray-900 mb-3">Document Information</h4>
        <dl className="grid grid-cols-2 gap-4">
          <div>
            <dt className="text-xs text-gray-500">Filename</dt>
            <dd className="mt-1 text-sm text-gray-900 font-medium">{document.filename}</dd>
          </div>
          <div>
            <dt className="text-xs text-gray-500">Status</dt>
            <dd className="mt-1">
              <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-${status.color}-100 text-${status.color}-800`}>
                {status.icon} {status.label}
              </span>
            </dd>
          </div>
          <div>
            <dt className="text-xs text-gray-500">Uploaded</dt>
            <dd className="mt-1 text-sm text-gray-900">
              {new Date(document.uploaded_at).toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
              })}
            </dd>
          </div>
          {document.processed_at && (
            <div>
              <dt className="text-xs text-gray-500">Processed</dt>
              <dd className="mt-1 text-sm text-gray-900">
                {new Date(document.processed_at).toLocaleDateString('en-US', {
                  year: 'numeric',
                  month: 'short',
                  day: 'numeric',
                  hour: '2-digit',
                  minute: '2-digit'
                })}
              </dd>
            </div>
          )}
        </dl>
      </div>

      {/* Extraction Stats */}
      <div>
        <h4 className="text-sm font-medium text-gray-900 mb-3">Extraction Stats</h4>
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-blue-50 rounded-lg p-4">
            <div className="text-2xl font-bold text-blue-700">{totalFields}</div>
            <div className="text-sm text-blue-600">Total Fields</div>
          </div>
          <div className={`rounded-lg p-4 ${lowConfidenceCount > 0 ? 'bg-yellow-50' : 'bg-green-50'}`}>
            <div className={`text-2xl font-bold ${lowConfidenceCount > 0 ? 'text-yellow-700' : 'text-green-700'}`}>
              {lowConfidenceCount}
            </div>
            <div className={`text-sm ${lowConfidenceCount > 0 ? 'text-yellow-600' : 'text-green-600'}`}>
              Need Review
            </div>
          </div>
          <div className="bg-green-50 rounded-lg p-4">
            <div className="text-2xl font-bold text-green-700">{verificationPercent}%</div>
            <div className="text-sm text-green-600">Verified</div>
          </div>
        </div>
      </div>

      {/* Audit Queue Alert */}
      {lowConfidenceCount > 0 && (
        <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4 rounded-r">
          <div className="flex items-start">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-yellow-400" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="ml-3 flex-1">
              <h3 className="text-sm font-medium text-yellow-800">
                {lowConfidenceCount} {lowConfidenceCount === 1 ? 'field needs' : 'fields need'} review
              </h3>
              <p className="mt-1 text-sm text-yellow-700">
                Some extracted fields have low confidence scores and should be verified.
              </p>
              <div className="mt-3 flex gap-2">
                <button
                  onClick={onReviewAll}
                  className="px-3 py-1.5 text-sm font-medium text-yellow-800 bg-yellow-100 rounded-md hover:bg-yellow-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-yellow-500"
                >
                  Review All
                </button>
                <button
                  onClick={onOpenFullAudit}
                  className="px-3 py-1.5 text-sm font-medium text-yellow-800 bg-white border border-yellow-300 rounded-md hover:bg-yellow-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-yellow-500"
                >
                  Open Full Audit View
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Success Message */}
      {lowConfidenceCount === 0 && totalFields > 0 && (
        <div className="bg-green-50 border-l-4 border-green-400 p-4 rounded-r">
          <div className="flex">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-green-400" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="ml-3">
              <p className="text-sm text-green-700">
                All extractions have high confidence. No review needed!
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ExtractionsTab({ document, thresholds, onFieldClick }) {
  const [filter, setFilter] = useState('all'); // 'all' | 'high' | 'medium' | 'low'

  const filteredFields = document.fields?.filter(field => {
    if (filter === 'all') return true;
    if (filter === 'high') return field.confidence >= thresholds.high;
    if (filter === 'medium') return field.confidence >= thresholds.medium && field.confidence < thresholds.high;
    if (filter === 'low') return field.confidence < thresholds.medium;
    return true;
  }) || [];

  const highCount = document.fields?.filter(f => f.confidence >= thresholds.high).length || 0;
  const mediumCount = document.fields?.filter(f => f.confidence >= thresholds.medium && f.confidence < thresholds.high).length || 0;
  const lowCount = document.fields?.filter(f => f.confidence < thresholds.medium).length || 0;

  return (
    <div className="space-y-4">
      {/* Filter Tabs */}
      <div className="flex items-center justify-between border-b border-gray-200">
        <div className="flex space-x-4">
          <button
            onClick={() => setFilter('all')}
            className={`pb-2 px-1 text-sm font-medium border-b-2 transition-colors ${
              filter === 'all'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            All ({document.fields?.length || 0})
          </button>
          <button
            onClick={() => setFilter('high')}
            className={`pb-2 px-1 text-sm font-medium border-b-2 transition-colors ${
              filter === 'high'
                ? 'border-green-600 text-green-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            High ({highCount})
          </button>
          <button
            onClick={() => setFilter('medium')}
            className={`pb-2 px-1 text-sm font-medium border-b-2 transition-colors ${
              filter === 'medium'
                ? 'border-yellow-600 text-yellow-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            Medium ({mediumCount})
          </button>
          <button
            onClick={() => setFilter('low')}
            className={`pb-2 px-1 text-sm font-medium border-b-2 transition-colors ${
              filter === 'low'
                ? 'border-red-600 text-red-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            Low ({lowCount})
          </button>
        </div>
      </div>

      {/* Fields Table */}
      <div className="overflow-hidden border border-gray-200 rounded-lg">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Field Name
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Value
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Confidence
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Status
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {filteredFields.length === 0 ? (
              <tr>
                <td colSpan="4" className="px-4 py-8 text-center text-sm text-gray-500">
                  No fields found
                </td>
              </tr>
            ) : (
              filteredFields.map((field) => {
                const confidenceColor = getConfidenceColor(field.confidence);
                const colorClasses = {
                  green: 'bg-green-100 text-green-800 border-green-300',
                  yellow: 'bg-yellow-100 text-yellow-800 border-yellow-300',
                  red: 'bg-red-100 text-red-800 border-red-300'
                };

                return (
                  <tr
                    key={field.id}
                    onClick={() => onFieldClick(field)}
                    className="hover:bg-gray-50 cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">
                      {field.name}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-700">
                      {field.field_type && ['array', 'table', 'array_of_objects'].includes(field.field_type) ? (
                        <span className="text-xs text-gray-500 italic">
                          Complex type: {field.field_type}
                        </span>
                      ) : (
                        truncateFieldValue(field.value, 60)
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm">
                      <div className="flex items-center gap-2">
                        <span className={`inline-flex items-center px-2 py-1 text-xs font-medium rounded border ${colorClasses[confidenceColor]}`}>
                          {formatConfidencePercent(field.confidence)}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm">
                      {field.verified ? (
                        <span className="inline-flex items-center px-2 py-1 text-xs font-medium rounded bg-green-100 text-green-800">
                          ✓ Verified
                        </span>
                      ) : field.needs_verification ? (
                        <span className="inline-flex items-center px-2 py-1 text-xs font-medium rounded bg-yellow-100 text-yellow-800">
                          ⚠ Needs Review
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2 py-1 text-xs font-medium rounded bg-gray-100 text-gray-600">
                          • Not Reviewed
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {filteredFields.length > 0 && (
        <p className="text-xs text-gray-500 text-center">
          Click any field to review and verify
        </p>
      )}
    </div>
  );
}
