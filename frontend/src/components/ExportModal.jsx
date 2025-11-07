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

  // NEW: Multi-template and complex data support
  const [expandComplexFields, setExpandComplexFields] = useState(true);
  const [templateAnalysis, setTemplateAnalysis] = useState(null);
  const [analyzingTemplates, setAnalyzingTemplates] = useState(false);

  useEffect(() => {
    if (isOpen && templateId) {
      fetchTemplate();
      fetchSummary();
    } else if (isOpen && documentIds && documentIds.length > 0) {
      // Analyze templates for selected documents
      analyzeDocumentTemplates();
    }
  }, [isOpen, templateId, dateFrom, dateTo, documentIds]);

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

  const analyzeDocumentTemplates = async () => {
    if (!documentIds || documentIds.length === 0) return;

    setAnalyzingTemplates(true);
    try {
      // First, fetch the documents to get their template IDs
      const docsResponse = await apiClient.get('/api/documents', {
        params: { size: 1000 } // Get enough documents to cover selection
      });
      const allDocs = docsResponse.data.documents || [];
      const selectedDocs = allDocs.filter(doc => documentIds.includes(doc.id));

      // Extract unique template IDs from selected documents
      // Prioritize schema_id (confirmed template) over suggested_template_id
      const templateIds = [...new Set(
        selectedDocs
          .map(doc => doc.schema_id || doc.suggested_template_id)
          .filter(id => id != null)
      )];

      if (templateIds.length === 0) {
        // No templates assigned yet - show warning
        setTemplateAnalysis({
          strategy: "no_templates",
          document_count: documentIds.length,
          warning: "Selected documents do not have templates assigned yet. Please assign templates before exporting."
        });
        return;
      }

      // Analyze template compatibility
      const analysisResponse = await apiClient.post('/api/export/analyze-templates', {
        template_ids: templateIds
      });

      setTemplateAnalysis({
        ...analysisResponse.data,
        template_count: templateIds.length,
        document_count: documentIds.length,
        documents_without_templates: selectedDocs.filter(doc => !doc.schema_id && !doc.suggested_template_id).length
      });

      // Auto-select recommended format
      if (analysisResponse.data.recommended_format) {
        setFormat(analysisResponse.data.recommended_format);
      }
    } catch (err) {
      console.error('Failed to analyze templates:', err);
      setTemplateAnalysis({
        strategy: "error",
        error: err.response?.data?.detail || err.message,
        document_count: documentIds.length
      });
    } finally {
      setAnalyzingTemplates(false);
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
        if (format === 'excel' && !expandComplexFields) url += '&expand_complex_fields=false';
      } else if (templateId) {
        // Export by template
        url = `/api/export/template/${templateId}/${format}?${params}`;
        if (format === 'excel' && !expandComplexFields) url += '&expand_complex_fields=false';
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

          {/* Template Analysis (Multi-Template Export) */}
          {analyzingTemplates && (
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 mb-6">
              <div className="flex items-center gap-2 text-gray-600">
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Analyzing templates...
              </div>
            </div>
          )}

          {templateAnalysis && templateAnalysis.strategy === "no_templates" && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
              <div className="flex items-start gap-2">
                <svg className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <div className="flex-1">
                  <p className="text-sm font-semibold text-red-900 mb-1">
                    No Templates Assigned
                  </p>
                  <p className="text-xs text-red-800">
                    {templateAnalysis.warning}
                  </p>
                </div>
              </div>
            </div>
          )}

          {templateAnalysis && templateAnalysis.strategy === "error" && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
              <div className="flex items-start gap-2">
                <svg className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
                <div className="flex-1">
                  <p className="text-sm font-semibold text-red-900 mb-1">
                    Analysis Error
                  </p>
                  <p className="text-xs text-red-800">
                    {templateAnalysis.error}
                  </p>
                </div>
              </div>
            </div>
          )}

          {templateAnalysis && templateAnalysis.strategy !== "no_templates" && templateAnalysis.strategy !== "error" && (
            <div className={`border rounded-lg p-4 mb-6 ${
              templateAnalysis.has_complex_fields
                ? 'bg-amber-50 border-amber-200'
                : 'bg-green-50 border-green-200'
            }`}>
              <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                {templateAnalysis.template_count > 1 ? (
                  <>
                    <span className="text-amber-900">📋 Multi-Template Export</span>
                  </>
                ) : (
                  <>
                    <span className="text-green-900">📄 Single Template Export</span>
                  </>
                )}
              </h3>

              <div className="grid grid-cols-2 gap-4 text-sm mb-3">
                <div>
                  <span className={templateAnalysis.has_complex_fields ? 'text-amber-700' : 'text-green-700'}>
                    Documents:
                  </span>
                  <span className="ml-2 font-semibold">{templateAnalysis.document_count}</span>
                </div>
                <div>
                  <span className={templateAnalysis.has_complex_fields ? 'text-amber-700' : 'text-green-700'}>
                    Templates:
                  </span>
                  <span className="ml-2 font-semibold">{templateAnalysis.template_count}</span>
                </div>
              </div>

              {/* Complex Fields Warning */}
              {templateAnalysis.has_complex_fields && (
                <div className="bg-amber-100 border border-amber-300 rounded p-3 mb-3">
                  <div className="flex items-start gap-2">
                    <svg className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                    <div className="flex-1">
                      <p className="text-sm font-semibold text-amber-900 mb-1">
                        Complex Data Detected
                      </p>
                      <p className="text-xs text-amber-800">
                        These documents contain{' '}
                        <span className="font-semibold">
                          {templateAnalysis.complex_field_types.join(', ')}
                        </span>
                        {' '}fields.
                        {format === 'excel' ? (
                          <span> Excel will create separate sheets for table and array_of_objects fields.</span>
                        ) : format === 'csv' ? (
                          <span className="font-semibold"> CSV will serialize complex fields as JSON strings (not recommended).</span>
                        ) : (
                          <span> JSON preserves the full structure.</span>
                        )}
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Multi-Template Strategy */}
              {templateAnalysis.template_count > 1 && (
                <div className="text-sm">
                  <p className="text-amber-800 mb-1">
                    <span className="font-semibold">Strategy:</span>{' '}
                    {templateAnalysis.strategy === 'merged' ? (
                      <span>Merged (Field overlap: {(templateAnalysis.field_overlap * 100).toFixed(0)}%)</span>
                    ) : (
                      <span>Separated by template (Low field overlap: {(templateAnalysis.field_overlap * 100).toFixed(0)}%)</span>
                    )}
                  </p>
                  {templateAnalysis.strategy === 'separated' && format === 'excel' && (
                    <p className="text-xs text-amber-700 mt-1">
                      💡 Excel format will create separate sheets for each template
                    </p>
                  )}
                </div>
              )}
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

              {/* Complex Fields Toggle (Excel only) */}
              {format === 'excel' && templateAnalysis?.has_complex_fields && (
                <label className="flex items-start">
                  <input
                    type="checkbox"
                    checked={expandComplexFields}
                    onChange={(e) => setExpandComplexFields(e.target.checked)}
                    className="rounded border-gray-300 text-blue-600 focus:ring-blue-500 mt-0.5"
                  />
                  <div className="ml-2 flex-1">
                    <span className="text-sm text-gray-700 font-medium">
                      Expand complex fields to separate sheets
                    </span>
                    <p className="text-xs text-gray-500 mt-0.5">
                      Create dedicated sheets for tables and arrays with document ID cross-references
                    </p>
                  </div>
                </label>
              )}
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
              disabled={loading || templateAnalysis?.strategy === "no_templates" || templateAnalysis?.strategy === "error"}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
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
