import { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import { getConfidenceColor, formatConfidencePercent, truncateFieldValue } from '../../utils/confidenceHelpers';

/**
 * Live progress modal for document processing
 *
 * Features:
 * - Real-time status updates via polling
 * - Per-document progress indicators
 * - Error handling with retry options
 * - Auto-close on completion
 */
export default function ProcessingModal({
  isOpen,
  documents = [],
  onClose,
  onComplete,
  pollInterval = 2000
}) {
  const [statuses, setStatuses] = useState({});
  const [isPolling, setIsPolling] = useState(false);
  const [expandedDocs, setExpandedDocs] = useState({}); // Track which docs are expanded

  useEffect(() => {
    if (!isOpen || documents.length === 0) {
      setIsPolling(false);
      return;
    }

    // Initialize statuses
    const initialStatuses = {};
    documents.forEach(doc => {
      initialStatuses[doc.id] = {
        filename: doc.filename,
        status: doc.status || 'processing',
        progress: 0
      };
    });
    setStatuses(initialStatuses);
    setIsPolling(true);
  }, [isOpen, documents]);

  useEffect(() => {
    if (!isPolling) return;

    const pollStatuses = async () => {
      try {
        // Poll document statuses from backend
        const response = await fetch('/api/documents?' + new URLSearchParams({
          ids: documents.map(d => d.id).join(',')
        }));

        if (!response.ok) {
          throw new Error('Failed to fetch document statuses');
        }

        const data = await response.json();
        const updatedStatuses = { ...statuses };
        let allComplete = true;

        data.documents.forEach(doc => {
          updatedStatuses[doc.id] = {
            filename: doc.filename,
            status: doc.status,
            progress: getProgress(doc.status),
            extracted_fields: doc.extracted_fields || [], // NEW: Include extracted fields
            has_low_confidence_fields: doc.has_low_confidence_fields || false
          };

          if (!['completed', 'error'].includes(doc.status)) {
            allComplete = false;
          }
        });

        setStatuses(updatedStatuses);

        // Stop polling if all complete
        if (allComplete) {
          setIsPolling(false);
          // Auto-close after 2 seconds
          setTimeout(() => {
            onComplete?.();
          }, 2000);
        }
      } catch (error) {
        // Silently handle polling errors - user will see stale status
        // Could show a "Refresh" button in the UI instead
      }
    };

    const interval = setInterval(pollStatuses, pollInterval);
    pollStatuses(); // Initial poll

    return () => clearInterval(interval);
  }, [isPolling, documents, statuses, pollInterval, onComplete]);

  const getProgress = (status) => {
    const progressMap = {
      uploaded: 10,
      analyzing: 30,
      template_matched: 50,
      processing: 75,
      completed: 100,
      error: 100
    };
    return progressMap[status] || 0;
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'completed':
        return '✓';
      case 'error':
        return '⚠';
      default:
        return '⏳';
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'completed':
        return 'text-green-600';
      case 'error':
        return 'text-red-600';
      default:
        return 'text-blue-600';
    }
  };

  const toggleDocExpanded = (docId) => {
    setExpandedDocs(prev => ({
      ...prev,
      [docId]: !prev[docId]
    }));
  };

  const completedCount = Object.values(statuses).filter(
    s => s.status === 'completed'
  ).length;
  const errorCount = Object.values(statuses).filter(
    s => s.status === 'error'
  ).length;
  const totalCount = documents.length;

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
        <div className="mb-4">
          <h2 className="text-xl font-semibold text-gray-900">
            Processing Documents
          </h2>
          <p className="text-sm text-gray-600 mt-1">
            {completedCount} of {totalCount} completed
            {errorCount > 0 && ` • ${errorCount} failed`}
          </p>
        </div>

        {/* Overall Progress Bar */}
        <div className="mb-6">
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-blue-600 h-2 rounded-full transition-all duration-500"
              style={{
                width: `${(completedCount / totalCount) * 100}%`
              }}
            />
          </div>
        </div>

        {/* Document List with Extraction Preview */}
        <div className="flex-1 overflow-y-auto space-y-3 mb-6">
          {Object.entries(statuses).map(([docId, docStatus]) => {
            const isExpanded = expandedDocs[docId];
            const fields = docStatus.extracted_fields || [];
            const hasFields = fields.length > 0;
            const displayFields = isExpanded ? fields : fields.slice(0, 3);

            return (
              <div
                key={docId}
                className="bg-gray-50 rounded-lg overflow-hidden"
              >
                {/* Header with filename and status */}
                <div className="flex items-center gap-3 p-3">
                  <div className={`text-2xl ${getStatusColor(docStatus.status)}`}>
                    {getStatusIcon(docStatus.status)}
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium text-gray-900 truncate">
                        {docStatus.filename}
                      </p>
                      {docStatus.has_low_confidence_fields && (
                        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-yellow-100 text-yellow-800" title="Contains low confidence fields">
                          ⚠
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      <div className="flex-1 bg-gray-200 rounded-full h-1.5">
                        <div
                          className={`h-1.5 rounded-full transition-all duration-300 ${
                            docStatus.status === 'error'
                              ? 'bg-red-500'
                              : docStatus.status === 'completed'
                              ? 'bg-green-500'
                              : 'bg-blue-500'
                          }`}
                          style={{ width: `${docStatus.progress}%` }}
                        />
                      </div>
                      <span className="text-xs text-gray-500 w-20 text-right">
                        {docStatus.status === 'completed' && 'Complete'}
                        {docStatus.status === 'error' && 'Failed'}
                        {!['completed', 'error'].includes(docStatus.status) && 'Processing...'}
                      </span>
                    </div>
                  </div>

                  {/* Expand/Collapse button (only if has fields) */}
                  {hasFields && (
                    <button
                      onClick={() => toggleDocExpanded(docId)}
                      className="text-gray-400 hover:text-gray-600 transition-colors p-1"
                      title={isExpanded ? 'Collapse fields' : 'Expand fields'}
                    >
                      <svg
                        className={`w-5 h-5 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    </button>
                  )}
                </div>

                {/* Extraction Preview */}
                {hasFields && (
                  <div className="px-3 pb-3 space-y-1.5">
                    {displayFields.map((field, idx) => {
                      const confidence = field.confidence_score;
                      const color = getConfidenceColor(confidence);
                      const confidencePercent = formatConfidencePercent(confidence);
                      const displayValue = truncateFieldValue(field.field_value, 40);

                      return (
                        <div
                          key={field.id || idx}
                          className="flex items-center gap-2 text-xs bg-white rounded px-2 py-1.5 border border-gray-200"
                        >
                          <span className="font-medium text-gray-700 min-w-[100px] truncate">
                            {field.field_name}:
                          </span>
                          <span className="flex-1 text-gray-900 truncate" title={field.field_value}>
                            {displayValue}
                          </span>
                          <span
                            className={`px-1.5 py-0.5 rounded text-xs font-medium bg-${color}-100 text-${color}-800 whitespace-nowrap`}
                          >
                            {confidencePercent}
                          </span>
                        </div>
                      );
                    })}

                    {/* Show more indicator */}
                    {!isExpanded && fields.length > 3 && (
                      <button
                        onClick={() => toggleDocExpanded(docId)}
                        className="w-full text-xs text-blue-600 hover:text-blue-700 py-1 text-center"
                      >
                        + {fields.length - 3} more field{fields.length - 3 !== 1 ? 's' : ''}
                      </button>
                    )}
                  </div>
                )}

                {/* Field count summary when no fields yet */}
                {!hasFields && docStatus.status === 'processing' && (
                  <div className="px-3 pb-3">
                    <p className="text-xs text-gray-500 italic">
                      Extracting fields...
                    </p>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 pt-4 border-t border-gray-200">
          {completedCount === totalCount ? (
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
            >
              View Documents
            </button>
          ) : (
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
            >
              Close
            </button>
          )}
        </div>

        {/* Processing indicator */}
        {isPolling && (
          <div className="mt-3 text-center">
            <div className="inline-flex items-center gap-2 text-xs text-gray-500">
              <div className="animate-spin h-3 w-3 border-2 border-blue-500 border-t-transparent rounded-full" />
              Refreshing status...
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

ProcessingModal.propTypes = {
  isOpen: PropTypes.bool.isRequired,
  documents: PropTypes.arrayOf(PropTypes.shape({
    id: PropTypes.number.isRequired,
    filename: PropTypes.string.isRequired,
    status: PropTypes.string
  })),
  onClose: PropTypes.func.isRequired,
  onComplete: PropTypes.func,
  pollInterval: PropTypes.number
};
