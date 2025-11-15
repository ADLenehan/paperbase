import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import FieldCard from '../components/FieldCard';
import PDFViewer from '../components/PDFViewer';
import InlineAuditModal from '../components/InlineAuditModal';
import ExportModal from '../components/ExportModal';
import { useConfidenceThresholds } from '../hooks/useConfidenceThresholds';
import apiClient from '../api/client';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/**
 * DocumentDetail - Full-page document detail view with vertical layout
 *
 * Layout:
 * - Top section (60%): PDF/Image viewer with bbox highlighting
 * - Bottom section (40%): List of all extracted fields with metadata
 *
 * Features:
 * - Click field card → highlight in PDF
 * - Click "View Citation" → jump to that page/bbox
 * - Inline editing with optimistic UI updates
 * - Quick verify without leaving page
 * - Export, Edit, Audit actions in header
 */
export default function DocumentDetail() {
  const { documentId } = useParams();
  const navigate = useNavigate();
  const thresholds = useConfidenceThresholds();

  const [document, setDocument] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // PDF viewer state
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedFieldId, setSelectedFieldId] = useState(null);
  const [zoom, setZoom] = useState(1.0);

  // Field filtering
  const [confidenceFilter, setConfidenceFilter] = useState('all'); // 'all' | 'high' | 'medium' | 'low' | 'needs-review'
  const [viewMode, setViewMode] = useState('cards'); // 'cards' | 'table'

  // Audit modal state
  const [showAuditModal, setShowAuditModal] = useState(false);
  const [currentField, setCurrentField] = useState(null);
  const [auditQueue, setAuditQueue] = useState([]);
  const [auditIndex, setAuditIndex] = useState(0);

  // Export modal
  const [showExportModal, setShowExportModal] = useState(false);

  // Mark as verified
  const [markingVerified, setMarkingVerified] = useState(false);

  // Refs for scrolling
  const fieldsContainerRef = useRef(null);
  const pdfViewerRef = useRef(null);

  useEffect(() => {
    if (documentId) {
      fetchDocument();
    }
  }, [documentId]);

  const fetchDocument = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_URL}/api/documents/${documentId}`);
      if (!response.ok) {
        throw new Error(`Failed to fetch document: ${response.statusText}`);
      }

      const data = await response.json();
      console.log('Document loaded:', data);
      console.log('Document file_path:', data.file_path);
      console.log('PDF URL will be:', `${API_URL}/api/files/${documentId}/preview`);
      setDocument(data);
    } catch (err) {
      console.error('Error fetching document:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleViewCitation = (field) => {
    // Navigate PDF to the page and highlight bbox
    setSelectedFieldId(field.id);
    if (field.source_page !== null && field.source_page !== undefined) {
      setCurrentPage(field.source_page);
    }
  };

  const handleFieldClick = (field) => {
    // Select field and navigate to its location
    setSelectedFieldId(field.id);
    if (field.source_page !== null && field.source_page !== undefined) {
      setCurrentPage(field.source_page);
    }
  };

  const handleVerifyField = (field) => {
    // Open audit modal for this field
    // Filter by BOTH confidence AND verified status (exclude already-verified fields)
    const lowConfidenceFields = document.fields
      .filter(f => f.confidence < thresholds.audit && !f.verified)
      .sort((a, b) => a.confidence - b.confidence);

    const startIndex = lowConfidenceFields.findIndex(f => f.id === field.id);

    if (startIndex >= 0) {
      setAuditQueue(lowConfidenceFields);
      setAuditIndex(startIndex);
      setCurrentField(buildAuditField(lowConfidenceFields[startIndex]));
    } else {
      // Field not in audit queue, show it standalone
      setAuditQueue([field]);
      setAuditIndex(0);
      setCurrentField(buildAuditField(field));
    }

    setShowAuditModal(true);
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

  // NEW: Inline field save handler with optimistic UI updates
  const handleFieldSave = async (fieldId, newValue) => {
    try {
      // Find the field to determine the correct action
      const field = document.fields.find(f => f.id === fieldId);

      if (!field) {
        throw new Error('Field not found');
      }

      // Determine action based on original value
      let action;
      const originalValue = field.value;

      if (!originalValue || originalValue === '' || originalValue === null) {
        // User is filling in a missing value
        action = 'not_found';
      } else if (originalValue !== newValue) {
        // User is correcting an incorrect extraction
        action = 'incorrect';
      } else {
        // No change, skip save
        return;
      }

      // OPTIMISTIC UPDATE: Update UI immediately for perceived speed
      // Also mark as verified since the backend will do this
      setDocument(prev => ({
        ...prev,
        fields: prev.fields.map(f =>
          f.id === fieldId ? { ...f, value: newValue, verified: true } : f
        )
      }));

      try {
        // Use audit verification API with intelligent action detection
        await apiClient.post('/api/audit/verify', {
          field_id: fieldId,
          action: action,
          corrected_value: newValue,
          notes: `Inline edit from document view (${action})`
        });

        // Refresh document data to get server updates (confidence, verified flag, etc.)
        await fetchDocument();

        // Optional: Show success feedback
        // You could add a toast notification here if you have a toast library
      } catch (error) {
        // Revert optimistic update on error
        await fetchDocument();
        throw error;
      }
    } catch (error) {
      console.error('Failed to save field:', error);
      // Re-throw so FieldCard can show error
      throw error;
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

  const handleOpenAudit = () => {
    navigate(`/audit/document/${documentId}`);
  };

  // NEW: Mark document as verified
  const handleMarkVerified = async () => {
    // Check if any fields need verification
    const needsReview = document.fields.filter(f =>
      f.confidence < thresholds.audit && !f.verified
    );

    if (needsReview.length > 0) {
      const confirmed = window.confirm(
        `This document has ${needsReview.length} field(s) that need review. ` +
        `Mark as verified anyway?`
      );
      if (!confirmed) return;
    }

    setMarkingVerified(true);
    try {
      await apiClient.post(`/api/documents/${documentId}/verify`, {
        force: needsReview.length > 0
      });

      await fetchDocument();
      // Optional: Show success message
      alert('Document marked as verified!');
    } catch (error) {
      console.error('Failed to verify document:', error);
      alert('Failed to verify document. Please try again.');
    } finally {
      setMarkingVerified(false);
    }
  };

  const getFilteredFields = () => {
    if (!document?.fields) return [];

    let filtered = document.fields;

    switch (confidenceFilter) {
      case 'high':
        filtered = filtered.filter(f => f.confidence >= thresholds.high);
        break;
      case 'medium':
        filtered = filtered.filter(f => f.confidence >= thresholds.medium && f.confidence < thresholds.high);
        break;
      case 'low':
        filtered = filtered.filter(f => f.confidence < thresholds.medium);
        break;
      case 'needs-review':
        filtered = filtered.filter(f => f.confidence < thresholds.audit && !f.verified);
        break;
      default:
        break;
    }

    return filtered;
  };

  const filteredFields = getFilteredFields();

  const highCount = document?.fields?.filter(f => f.confidence >= thresholds.high).length || 0;
  const mediumCount = document?.fields?.filter(f => f.confidence >= thresholds.medium && f.confidence < thresholds.high).length || 0;
  const lowCount = document?.fields?.filter(f => f.confidence < thresholds.medium).length || 0;
  const needsReviewCount = document?.fields?.filter(f => f.confidence < thresholds.audit && !f.verified).length || 0;

  // Prepare PDF highlights for all fields with bboxes
  const allHighlights = filteredFields
    .filter(f => f.source_bbox && f.source_page === currentPage)
    .map(f => {
      const isSelected = f.id === selectedFieldId;
      const needsReview = f.confidence < thresholds.audit && !f.verified;

      // Color based on confidence or selection
      let color;
      if (isSelected) {
        color = 'blue';
      } else if (needsReview) {
        color = 'yellow';
      } else if (f.confidence >= thresholds.high) {
        color = 'green';
      } else if (f.confidence >= thresholds.medium) {
        color = 'yellow';
      } else {
        color = 'red';
      }

      return {
        bbox: f.source_bbox,
        color,
        label: f.name.replace(/_/g, ' '),
        page: f.source_page,
        opacity: isSelected ? 1.0 : 0.3
      };
    });

  const statusConfig = {
    completed: { color: 'mint', icon: '✓', label: 'Completed' },
    verified: { color: 'mint', icon: '✓', label: 'Verified' },
    processing: { color: 'sky', icon: '⟳', label: 'Processing' },
    error: { color: 'primary', icon: '✗', label: 'Error' }
  };

  const status = statusConfig[document?.status] || { color: 'gray', icon: '•', label: document?.status || 'Unknown' };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-periwinkle-600 mb-4"></div>
          <p className="text-gray-600">Loading document...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-2xl mx-auto mt-12 p-6">
        <div className="bg-primary-50 border-l-4 border-primary-400 p-4 rounded-r">
          <div className="flex">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-primary-400" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-primary-800">Error loading document</h3>
              <p className="mt-2 text-sm text-primary-700">{error}</p>
              <button
                onClick={() => navigate('/documents')}
                className="mt-3 text-sm font-medium text-primary-700 hover:text-primary-800 underline"
              >
                ← Back to documents
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!document) {
    return (
      <div className="max-w-2xl mx-auto mt-12 p-6">
        <p className="text-gray-600">Document not found</p>
        <button
          onClick={() => navigate('/documents')}
          className="mt-3 text-sm font-medium text-periwinkle-600 hover:text-periwinkle-700 underline"
        >
          ← Back to documents
        </button>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4 flex-1 min-w-0">
            <button
              onClick={() => navigate('/documents')}
              className="text-gray-400 hover:text-gray-600 transition-colors"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <div className="flex-1 min-w-0">
              <h1 className="text-xl font-semibold text-gray-900 truncate">
                {document.filename}
              </h1>
              <div className="flex items-center gap-3 mt-1 text-sm text-gray-500">
                {document.template_name && (
                  <Link to={`/schema/${document.template_id}`} className="text-periwinkle-600 hover:text-periwinkle-700 font-medium">
                    {document.template_name}
                  </Link>
                )}
                <span className={`inline-flex items-center px-2 py-1 text-xs font-medium rounded bg-${status.color}-100 text-${status.color}-700`}>
                  {status.icon} {status.label}
                </span>
                <span>
                  Uploaded {new Date(document.uploaded_at).toLocaleDateString('en-US', {
                    month: 'short',
                    day: 'numeric',
                    year: 'numeric'
                  })}
                </span>
              </div>
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-2 ml-4">
            {/* Mark as Verified button */}
            <button
              onClick={handleMarkVerified}
              disabled={markingVerified || document.status === 'verified'}
              className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors flex items-center gap-2 ${
                needsReviewCount > 0
                  ? 'bg-yellow-100 text-yellow-700 border border-yellow-300 hover:bg-yellow-200'
                  : document.status === 'verified'
                  ? 'bg-periwinkle-100 text-periwinkle-700 border border-periwinkle-300 cursor-not-allowed'
                  : 'bg-periwinkle-500 text-white hover:bg-periwinkle-600'
              } ${markingVerified ? 'opacity-50 cursor-wait' : ''}`}
            >
              {markingVerified ? (
                <>
                  <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Verifying...
                </>
              ) : document.status === 'verified' ? (
                <>✓ Verified</>
              ) : needsReviewCount > 0 ? (
                <>⚠ Mark Verified ({needsReviewCount} need review)</>
              ) : (
                <>✓ Mark as Verified</>
              )}
            </button>

            <button
              onClick={() => setShowExportModal(true)}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
            >
              Export
            </button>
            <button
              onClick={handleOpenAudit}
              className="px-4 py-2 text-sm font-medium text-white bg-periwinkle-500 rounded-lg hover:bg-periwinkle-600 transition-colors"
            >
              Open Audit{needsReviewCount > 0 && ` (${needsReviewCount})`}
            </button>
          </div>
        </div>
      </div>

      {/* Main content: Horizontal layout (PDF left, fields right) */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: PDF/Image viewer with bbox highlighting */}
        <div className="flex-1 p-6 bg-gray-100">
          <div className="h-full overflow-hidden">
            {document.file_path ? (
              // Check if file is an image or PDF
              document.filename && /\.(png|jpg|jpeg|gif|webp)$/i.test(document.filename) ? (
                // Image viewer
                <div className="h-full overflow-auto flex items-center justify-center bg-white rounded-lg shadow">
                  <img
                    src={`${API_URL}/api/files/${documentId}/preview`}
                    alt={document.filename}
                    className="max-w-full max-h-full object-contain"
                  />
                </div>
              ) : (
                // PDF viewer with bbox highlighting - show ALL bboxes for current page
                <PDFViewer
                  ref={pdfViewerRef}
                  fileUrl={`${API_URL}/api/files/${documentId}/preview`}
                  page={currentPage}
                  highlights={allHighlights}
                  onPageChange={setCurrentPage}
                  zoom={zoom}
                  onZoomChange={setZoom}
                />
              )
            ) : (
              <div className="flex items-center justify-center h-full text-gray-500">
                <div className="text-center">
                  <svg className="w-16 h-16 mx-auto mb-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  <p className="text-sm">No file available</p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right: Fields list */}
        <div className="w-96 flex flex-col bg-white border-l border-gray-200 overflow-hidden">
          {/* Fields header + filters */}
          <div className="px-6 py-4 border-b border-gray-200 flex-shrink-0">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">
                Extracted Fields ({document.fields?.length || 0})
              </h2>
            </div>

            {/* Filter tabs */}
            <div className="flex gap-2 overflow-x-auto pb-2">
              <button
                onClick={() => setConfidenceFilter('all')}
                className={`px-3 py-1.5 text-sm font-medium rounded-lg whitespace-nowrap transition-colors ${
                  confidenceFilter === 'all'
                    ? 'bg-periwinkle-100 text-periwinkle-700'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                All ({document.fields?.length || 0})
              </button>
              <button
                onClick={() => setConfidenceFilter('needs-review')}
                className={`px-3 py-1.5 text-sm font-medium rounded-lg whitespace-nowrap transition-colors ${
                  confidenceFilter === 'needs-review'
                    ? 'bg-yellow-100 text-yellow-700'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                Needs Review ({needsReviewCount})
              </button>
              <button
                onClick={() => setConfidenceFilter('high')}
                className={`px-3 py-1.5 text-sm font-medium rounded-lg whitespace-nowrap transition-colors ${
                  confidenceFilter === 'high'
                    ? 'bg-mint-100 text-mint-700'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                High ({highCount})
              </button>
              <button
                onClick={() => setConfidenceFilter('medium')}
                className={`px-3 py-1.5 text-sm font-medium rounded-lg whitespace-nowrap transition-colors ${
                  confidenceFilter === 'medium'
                    ? 'bg-yellow-100 text-yellow-700'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                Medium ({mediumCount})
              </button>
              <button
                onClick={() => setConfidenceFilter('low')}
                className={`px-3 py-1.5 text-sm font-medium rounded-lg whitespace-nowrap transition-colors ${
                  confidenceFilter === 'low'
                    ? 'bg-primary-100 text-primary-700'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                Low ({lowCount})
              </button>
            </div>
          </div>

          {/* Fields list - scrollable */}
          <div ref={fieldsContainerRef} className="flex-1 overflow-y-auto p-6 space-y-3">
            {filteredFields.length === 0 ? (
              <div className="text-center py-12 text-gray-500">
                <p>No fields found</p>
              </div>
            ) : (
              filteredFields.map((field) => (
                <div
                  key={field.id}
                  onClick={() => handleFieldClick(field)}
                  className={`cursor-pointer transition-all ${
                    selectedFieldId === field.id
                      ? 'ring-2 ring-periwinkle-500 ring-offset-2 rounded-lg'
                      : ''
                  }`}
                >
                  <FieldCard
                    field={field}
                    editable={true}
                    onSave={handleFieldSave}
                    onViewCitation={handleViewCitation}
                    onVerify={handleVerifyField}
                  />
                </div>
              ))
            )}
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

      {/* Export Modal */}
      {showExportModal && (
        <ExportModal
          isOpen={showExportModal}
          onClose={() => setShowExportModal(false)}
          selectedDocumentIds={[documentId]}
          templateId={document.template_id}
        />
      )}
    </div>
  );
}
