import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import apiClient from '../api/client';

/**
 * ExportModal - Reusable component for exporting document data
 *
 * Can be used for:
 * - Exporting all documents for a template
 * - Exporting specific selected documents
 * - Exporting with filters (date range, confidence, etc.)
 */
export default function ExportModal({ isOpen, onClose, templateId = null, documentIds = null }) {
  const [format, setFormat] = useState('excel');
  const [includeMetadata, setIncludeMetadata] = useState(true);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [confidenceMin, setConfidenceMin] = useState(0);
  const [verifiedOnly, setVerifiedOnly] = useState(false);
  const [loading, setLoading] = useState(false);
  const [summary, setSummary] = useState(null);
  const [template, setTemplate] = useState(null);

  useEffect(() => {
    if (isOpen && templateId) {
      fetchTemplate();
      fetchSummary();
    }
  }, [isOpen, templateId, dateFrom, dateTo]);

  const fetchTemplate = async () => {
    try {
      const response = await apiClient.get(`/api/templates/${templateId}`);
      setTemplate(response.data);
    } catch (err) {
      console.error('Failed to fetch template:', err);
    }
  };

  const fetchSummary = async () => {
    try {
      const params = new URLSearchParams();
      if (templateId) params.append('template_id', templateId);
      if (dateFrom) params.append('date_from', dateFrom);
      if (dateTo) params.append('date_to', dateTo);

      const response = await apiClient.get(`/api/export/summary?${params}`);
      setSummary(response.data);
    } catch (err) {
      console.error('Failed to fetch export summary:', err);
    }
  };

  const handleExport = async () => {
    setLoading(true);
    try {
      let url = '';
      const params = new URLSearchParams();

      // Add common parameters
      if (dateFrom) params.append('date_from', dateFrom);
      if (dateTo) params.append('date_to', dateTo);
      if (confidenceMin > 0) params.append('confidence_min', confidenceMin);
      if (verifiedOnly) params.append('verified_only', 'true');
      if (!includeMetadata) params.append('include_metadata', 'false');

      // Determine export type and build URL
      if (documentIds && documentIds.length > 0) {
        // Export specific documents
        url = `/api/export/documents?document_ids=${documentIds.join(',')}&format=${format}`;
        if (!includeMetadata) url += '&include_metadata=false';
      } else if (templateId) {
        // Export by template
        url = `/api/export/template/${templateId}/${format}?${params}`;
      } else {
        throw new Error('Either templateId or documentIds must be provided');
      }

      // Download the file
      const response = await apiClient.get(url, {
        responseType: 'blob',
      });

      // Extract filename from Content-Disposition header
      const contentDisposition = response.headers['content-disposition'];
      let filename = `export_${new Date().toISOString().split('T')[0]}.${format === 'excel' ? 'xlsx' : format}`;

      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename="?(.+)"?/i);
        if (filenameMatch) {
          filename = filenameMatch[1];
        }
      }

      // Create download link
      const blob = new Blob([response.data]);
      const downloadUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(downloadUrl);

      // Close modal after successful export
      onClose();
    } catch (err) {
      console.error('Export failed:', err);
      alert('Export failed: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex min-h-screen items-center justify-center p-4">
        {/* Backdrop */}
        <div
          className="fixed inset-0 bg-black bg-opacity-50 transition-opacity"
          onClick={onClose}
        />

        {/* Modal */}
        <div className="relative bg-white rounded-lg shadow-xl max-w-2xl w-full p-6">
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-2xl font-semibold text-gray-900">Export Data</h2>
              {template && (
                <p className="text-sm text-gray-600 mt-1">
                  {template.icon} {template.name}
                </p>
              )}
              {documentIds && documentIds.length > 0 && (
                <p className="text-sm text-gray-600 mt-1">
                  {documentIds.length} document{documentIds.length !== 1 ? 's' : ''} selected
                </p>
              )}
            </div>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600"
            >
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Export Summary */}
          {summary && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
              <h3 className="text-sm font-semibold text-blue-900 mb-2">Export Preview</h3>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-blue-700">Documents:</span>
                  <span className="ml-2 font-semibold">{summary.total_documents}</span>
                </div>
                <div>
                  <span className="text-blue-700">Fields:</span>
                  <span className="ml-2 font-semibold">{summary.total_fields}</span>
                </div>
                <div>
                  <span className="text-blue-700">Verified:</span>
                  <span className="ml-2 font-semibold">
                    {summary.verified_fields} ({(summary.verification_rate * 100).toFixed(0)}%)
                  </span>
                </div>
                <div>
                  <span className="text-blue-700">Avg Confidence:</span>
                  <span className="ml-2 font-semibold">
                    {(summary.average_confidence * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Format Selection */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Export Format
            </label>
            <div className="grid grid-cols-3 gap-3">
              <button
                onClick={() => setFormat('excel')}
                className={`p-4 border-2 rounded-lg text-center transition-colors ${
                  format === 'excel'
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <div className="text-2xl mb-1">📊</div>
                <div className="font-medium text-sm">Excel</div>
                <div className="text-xs text-gray-500">Formatted .xlsx</div>
              </button>
              <button
                onClick={() => setFormat('csv')}
                className={`p-4 border-2 rounded-lg text-center transition-colors ${
                  format === 'csv'
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <div className="text-2xl mb-1">📄</div>
                <div className="font-medium text-sm">CSV</div>
                <div className="text-xs text-gray-500">Plain text</div>
              </button>
              <button
                onClick={() => setFormat('json')}
                className={`p-4 border-2 rounded-lg text-center transition-colors ${
                  format === 'json'
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <div className="text-2xl mb-1">🔧</div>
                <div className="font-medium text-sm">JSON</div>
                <div className="text-xs text-gray-500">For APIs</div>
              </button>
            </div>
          </div>

          {/* Filters */}
          <div className="space-y-4 mb-6">
            <h3 className="text-sm font-semibold text-gray-900">Filters (Optional)</h3>

            {/* Date Range */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-gray-700 mb-1">From Date</label>
                <input
                  type="date"
                  value={dateFrom}
                  onChange={(e) => setDateFrom(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-700 mb-1">To Date</label>
                <input
                  type="date"
                  value={dateTo}
                  onChange={(e) => setDateTo(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>
            </div>

            {/* Confidence Filter */}
            <div>
              <label className="block text-sm text-gray-700 mb-1">
                Minimum Confidence: {(confidenceMin * 100).toFixed(0)}%
              </label>
              <input
                type="range"
                min="0"
                max="1"
                step="0.1"
                value={confidenceMin}
                onChange={(e) => setConfidenceMin(parseFloat(e.target.value))}
                className="w-full"
              />
              <div className="flex justify-between text-xs text-gray-500 mt-1">
                <span>0%</span>
                <span>50%</span>
                <span>100%</span>
              </div>
            </div>

            {/* Checkboxes */}
            <div className="space-y-2">
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={verifiedOnly}
                  onChange={(e) => setVerifiedOnly(e.target.checked)}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <span className="ml-2 text-sm text-gray-700">
                  Only verified fields
                </span>
              </label>
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={includeMetadata}
                  onChange={(e) => setIncludeMetadata(e.target.checked)}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <span className="ml-2 text-sm text-gray-700">
                  Include confidence scores and verification status
                </span>
              </label>
            </div>
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-3">
            <button
              onClick={onClose}
              disabled={loading}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              onClick={handleExport}
              disabled={loading}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
            >
              {loading ? (
                <>
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Exporting...
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  Export
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

ExportModal.propTypes = {
  isOpen: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  templateId: PropTypes.number,
  documentIds: PropTypes.arrayOf(PropTypes.number),
};
