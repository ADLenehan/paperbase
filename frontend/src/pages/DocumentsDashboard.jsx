import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import FieldEditor from '../components/FieldEditor';
import apiClient from '../api/client';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function DocumentsDashboard() {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [showTemplateModal, setShowTemplateModal] = useState(false);
  const [selectedDocument, setSelectedDocument] = useState(null);
  const [templates, setTemplates] = useState([]);
  const [templateMap, setTemplateMap] = useState({});
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [showFieldEditor, setShowFieldEditor] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    fetchDocuments();
    fetchTemplates();

    // Auto-refresh every 5 seconds to show newly uploaded documents
    const interval = setInterval(fetchDocuments, 5000);
    return () => clearInterval(interval);
  }, []);

  const fetchTemplates = async () => {
    try {
      const response = await apiClient.get('/api/templates');
      const templateList = response.data.templates || [];
      setTemplates(templateList);

      // Create template ID -> template object lookup map
      const map = {};
      templateList.forEach(t => {
        map[t.id] = t;
      });
      setTemplateMap(map);
    } catch (err) {
      console.error('Failed to fetch templates:', err);
    }
  };

  const fetchDocuments = async () => {
    try {
      console.log('Fetching documents from:', `${API_URL}/api/documents`);

      // Fetch both legacy documents and new extractions
      const [docsResponse, extractionsResponse] = await Promise.all([
        fetch(`${API_URL}/api/documents`).catch((err) => {
          console.error('Docs fetch error:', err);
          return { ok: false };
        }),
        fetch(`${API_URL}/api/extractions/stats`).catch((err) => {
          console.log('Extractions fetch failed (expected if not using new system):', err);
          return { ok: false };
        })
      ]);

      let allDocuments = [];

      // Add legacy documents if available
      if (docsResponse.ok) {
        const docsData = await docsResponse.json();
        console.log('Fetched documents:', docsData);
        allDocuments = docsData.documents || [];
        console.log('Total documents:', allDocuments.length);
      } else {
        console.error('Documents response not OK:', docsResponse.status, docsResponse.statusText);
      }

      // If we have extractions, we can show a link to the new folder view
      if (extractionsResponse.ok) {
        const extractionsData = await extractionsResponse.json();
        // Store extraction stats for display
        if (extractionsData.extractions?.total_extractions > 0) {
          // Show a banner or link to new folder view
          console.log('New extractions available:', extractionsData.extractions);
        }
      }

      setDocuments(allDocuments);
      console.log('Documents state updated with:', allDocuments.length, 'documents');
    } catch (err) {
      console.error('Failed to fetch documents:', err);
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status, confidence = null, lowestField = null) => {
    const statusConfig = {
      uploaded: { bg: 'bg-yellow-100', text: 'text-yellow-700', dot: 'bg-yellow-500', label: 'Uploaded' },
      analyzing: { bg: 'bg-sky-100', text: 'text-sky-700', dot: 'bg-sky-400', label: 'Analyzing' },
      template_matched: { bg: 'bg-sky-100', text: 'text-sky-700', dot: 'bg-sky-500', label: 'Matched' },
      template_needed: { bg: 'bg-yellow-100', text: 'text-yellow-700', dot: 'bg-yellow-500', label: 'Uploaded' },
      ready_to_process: { bg: 'bg-coral-100', text: 'text-coral-700', dot: 'bg-coral-500', label: 'Ready' },
      processing: { bg: 'bg-sky-100', text: 'text-sky-700', dot: 'bg-sky-400', label: 'Processing' },
      completed: { bg: 'bg-periwinkle-100', text: 'text-periwinkle-700', dot: 'bg-periwinkle-600', label: 'Completed' },
      verified: { bg: 'bg-periwinkle-100', text: 'text-periwinkle-700', dot: 'bg-periwinkle-600', label: 'Verified' },
      error: { bg: 'bg-coral-100', text: 'text-coral-700', dot: 'bg-coral-600', label: 'Error' }
    };

    const config = statusConfig[status] || statusConfig.uploaded;
    // Show confidence for template_matched, template_needed, and any status with confidence > 0
    const showConfidence = (status === 'template_matched' || status === 'template_needed') && confidence !== null && confidence !== undefined;

    // Determine which confidence to display and its color
    let displayConfidence = null;
    let confidenceDotColor = null;
    let tooltipText = null;

    if (lowestField && lowestField.confidence !== null && lowestField.confidence !== 0) {
      // Use lowest field confidence for completed/verified documents
      displayConfidence = lowestField.confidence;
      tooltipText = `Lowest field confidence: ${lowestField.field_name.replace(/_/g, ' ')}`;
      // Color based on lowest field confidence
      if (displayConfidence >= 0.6) {
        confidenceDotColor = 'bg-mint-500'; // Green
      } else if (displayConfidence >= 0.4) {
        confidenceDotColor = 'bg-yellow-500'; // Yellow
      } else {
        confidenceDotColor = 'bg-coral-500'; // Red
      }
    } else if (showConfidence) {
      // Use template matching confidence for matched/needed documents
      displayConfidence = confidence;
      tooltipText = 'Template match confidence';
      confidenceDotColor = config.dot;
    }

    return (
      <div className="flex items-center gap-2">
        <span className={`px-2.5 py-1 text-xs font-medium rounded-full ${config.bg} ${config.text}`}>
          {config.label}
        </span>
        {displayConfidence !== null && (
          <>
            <span className={`w-1.5 h-1.5 rounded-full ${confidenceDotColor}`} title={tooltipText}></span>
            <span className="text-xs text-gray-500 font-medium" title={tooltipText}>
              {(displayConfidence * 100).toFixed(0)}%
            </span>
          </>
        )}
      </div>
    );
  };

  const getConfidenceIndicator = (confidence, showPercentage = false) => {
    // Don't show confidence for 0 (no match) or null/undefined
    if (!confidence || confidence === 0) return null;

    const percentage = confidence * 100;
    let color;

    if (percentage >= 75) {
      color = 'bg-green-500';
    } else if (percentage >= 60) {
      color = 'bg-yellow-500';
    } else {
      color = 'bg-gray-400';
    }

    return (
      <div className="flex items-center gap-1.5">
        <div className={`w-2.5 h-2.5 rounded-full ${color}`} title={`${percentage.toFixed(0)}% confidence`}></div>
        {showPercentage && (
          <span className="text-xs text-gray-600">{percentage.toFixed(0)}%</span>
        )}
      </div>
    );
  };

  const handleAssignTemplate = async (doc) => {
    setSelectedDocument(doc);

    // Load suggested template fields if available
    if (doc.suggested_template_id) {
      try {
        const response = await apiClient.get(`/api/templates/${doc.suggested_template_id}`);
        setSelectedTemplate(response.data);
      } catch (err) {
        console.error('Failed to load template:', err);
      }
    }

    // Open directly to field editor (skip template selection screen)
    setShowFieldEditor(true);
    setShowTemplateModal(true);
  };

  const handleSelectTemplate = async (templateId) => {
    try {
      const response = await apiClient.get(`/api/templates/${templateId}`);
      setSelectedTemplate(response.data);
    } catch (err) {
      console.error('Failed to load template:', err);
    }
  };

  const handleSaveFields = async (fieldData) => {
    try {
      // Step 1: Assign template to document with custom fields
      const assignResponse = await fetch(`${API_URL}/api/documents/${selectedDocument.id}/assign-template`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          template_id: selectedTemplate.id,
          custom_fields: fieldData.fields,
          template_name: fieldData.name
        })
      });

      if (!assignResponse.ok) {
        const errorData = await assignResponse.json();
        throw new Error(errorData.detail || 'Unknown error occurred');
      }

      // Step 2: Automatically trigger extraction
      const processResponse = await fetch(`${API_URL}/api/documents/process`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          document_ids: [selectedDocument.id]
        })
      });

      if (!processResponse.ok) {
        const errorData = await processResponse.json();
        throw new Error(errorData.detail || 'Failed to start extraction');
      }

      // Close modals and refresh
      setShowFieldEditor(false);
      setShowTemplateModal(false);
      fetchDocuments();
    } catch (err) {
      console.error('Failed to assign template:', err);
      alert(`Failed to assign template: ${err.message}`);
    }
  };

  const handleCloseModal = () => {
    setShowTemplateModal(false);
    setShowFieldEditor(false);
    setSelectedDocument(null);
    setSelectedTemplate(null);
  };

  const getFilteredDocuments = () => {
    if (filter === 'all') return documents;
    return documents.filter(doc => doc.status === filter);
  };

  const statusCounts = documents.reduce((acc, doc) => {
    acc[doc.status] = (acc[doc.status] || 0) + 1;
    return acc;
  }, {});

  const filteredDocs = getFilteredDocuments();

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Loading...</div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto p-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold mb-2">Documents</h1>
        <p className="text-gray-600">View and manage all uploaded documents</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-5 gap-4 mb-6">
        <StatCard label="Total" value={documents.length} active={filter === 'all'} onClick={() => setFilter('all')} />
        <StatCard label="Analyzing" value={statusCounts.analyzing || 0} active={filter === 'analyzing'} onClick={() => setFilter('analyzing')} />
        <StatCard label="Matched" value={statusCounts.template_matched || 0} active={filter === 'template_matched'} onClick={() => setFilter('template_matched')} />
        <StatCard label="Processing" value={statusCounts.processing || 0} active={filter === 'processing'} onClick={() => setFilter('processing')} />
        <StatCard label="Completed" value={(statusCounts.completed || 0) + (statusCounts.verified || 0)} active={filter === 'completed'} onClick={() => setFilter('completed')} />
      </div>

      {/* Filter Bar */}
      <div className="bg-white rounded-lg border p-4 mb-6">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-gray-700">Filter:</span>
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="px-3 py-1 border border-gray-300 rounded-lg text-sm"
          >
            <option value="all">All Documents</option>
            <option value="uploaded">Uploaded</option>
            <option value="analyzing">Analyzing</option>
            <option value="template_matched">Template Matched</option>
            <option value="template_needed">Needs Template</option>
            <option value="ready_to_process">Ready to Process</option>
            <option value="processing">Processing</option>
            <option value="completed">Completed</option>
            <option value="verified">Verified</option>
            <option value="error">Error</option>
          </select>
        </div>
      </div>

      {/* Document Table */}
      <div className="bg-white rounded-lg border overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Filename</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Template</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Uploaded</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {filteredDocs.length === 0 ? (
              <tr>
                <td colSpan="5" className="px-6 py-12 text-center text-gray-500">
                  No documents found
                </td>
              </tr>
            ) : (
              filteredDocs.map(doc => (
                <tr key={doc.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 text-sm font-medium text-gray-900">
                    {doc.filename}
                  </td>
                  <td className="px-6 py-4 text-sm">
                    {getStatusBadge(doc.status, doc.template_confidence, doc.lowest_confidence_field)}
                  </td>
                  <td className="px-6 py-4 text-sm">
                    {doc.schema?.name ? (
                      <span className="font-medium text-gray-900">{doc.schema.name}</span>
                    ) : doc.suggested_template_id ? (
                      <span className="font-medium text-gray-900">
                        {templateMap[doc.suggested_template_id]?.name || `Template #${doc.suggested_template_id}`}
                      </span>
                    ) : (
                      <span className="text-gray-400">Not assigned</span>
                    )}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500">
                    {new Date(doc.uploaded_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4 text-sm">
                    <DocumentActions
                      doc={doc}
                      navigate={navigate}
                      onAssignTemplate={handleAssignTemplate}
                    />
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Field Editor Modal */}
      {showTemplateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              {/* Header with template selector */}
              <div className="flex justify-between items-start mb-6">
                <div className="flex-1">
                  <h2 className="text-2xl font-bold text-gray-900 mb-1">Edit Template Fields</h2>
                  <p className="text-sm text-gray-600 mb-3">
                    For: <span className="font-medium text-gray-900">{selectedDocument?.filename}</span>
                  </p>

                  {/* Template Switcher */}
                  <div className="flex items-center gap-3">
                    <label className="text-sm font-medium text-gray-700">Template:</label>
                    <select
                      value={selectedTemplate?.id || ''}
                      onChange={(e) => handleSelectTemplate(parseInt(e.target.value))}
                      className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    >
                      <option value="">Select a template...</option>
                      {templates.map((template) => (
                        <option key={template.id} value={template.id}>
                          {template.icon} {template.name} ({template.field_count} fields)
                        </option>
                      ))}
                    </select>

                    {selectedDocument?.template_confidence && (
                      <span className="text-xs px-2 py-1 bg-blue-50 text-blue-700 rounded-full">
                        {(selectedDocument.template_confidence * 100).toFixed(0)}% match
                      </span>
                    )}
                  </div>
                </div>

                <button onClick={handleCloseModal} className="text-gray-400 hover:text-gray-600">
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              {/* Field Editor */}
              {selectedTemplate ? (
                <FieldEditor
                  initialFields={selectedTemplate.fields || []}
                  templateName={selectedTemplate.name || ''}
                  isNewTemplate={false}
                  onSave={handleSaveFields}
                  onCancel={handleCloseModal}
                />
              ) : (
                <div className="text-center py-12 text-gray-500">
                  Please select a template to continue
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`p-4 rounded-lg border transition-all ${
        active
          ? 'border-blue-500 bg-blue-50 shadow-sm'
          : 'border-gray-200 bg-white hover:border-gray-300'
      }`}
    >
      <div className="text-2xl font-bold text-gray-900">{value}</div>
      <div className="text-sm text-gray-600">{label}</div>
    </button>
  );
}

function DocumentActions({ doc, navigate, onAssignTemplate }) {
  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  const handleExtractData = async () => {
    try {
      const response = await fetch(`${API_URL}/api/documents/process`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          document_ids: [doc.id]
        })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to start extraction');
      }

      alert('Extraction started - the document will be processed in the background. This page will refresh automatically to show progress.');

      // Wait a moment for status to update, then reload
      setTimeout(() => {
        window.location.reload();
      }, 1500);
    } catch (err) {
      console.error('Failed to start extraction:', err);
      alert(`Failed to start extraction: ${err.message}`);
    }
  };

  const handleRetry = async () => {
    try {
      const response = await fetch(`${API_URL}/api/documents/process`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          document_ids: [doc.id]
        })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to retry processing');
      }

      alert('Processing started');
      window.location.reload();
    } catch (err) {
      console.error('Failed to retry processing:', err);
      alert(`Failed to retry processing: ${err.message}`);
    }
  };

  const handleView = () => {
    navigate(`/documents/${doc.id}`);
  };

  const handleVerify = () => {
    navigate(`/verify/${doc.id}`);
  };

  const handleAssignTemplate = () => {
    onAssignTemplate(doc);
  };

  // Smart actions based on status
  switch (doc.status) {
    case 'uploaded':
      return (
        <span className="text-sm text-gray-400 italic">Waiting...</span>
      );

    case 'analyzing':
      return (
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <div className="animate-spin h-3.5 w-3.5 border-2 border-sky-400 border-t-transparent rounded-full"></div>
          <span className="italic">Analyzing...</span>
        </div>
      );

    case 'template_matched':
      return (
        <button
          onClick={doc.schema_id ? handleExtractData : handleAssignTemplate}
          className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg border transition-colors whitespace-nowrap ${
            doc.schema_id
              ? 'border-coral-300 text-coral-700 hover:bg-coral-50'
              : 'border-periwinkle-300 text-periwinkle-700 hover:bg-periwinkle-50'
          }`}
        >
          {doc.schema_id ? (
            <>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              Extract
            </>
          ) : (
            <>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
              </svg>
              Review
            </>
          )}
        </button>
      );

    case 'template_needed':
      return (
        <button
          onClick={handleAssignTemplate}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg border border-orange-300 text-orange-700 hover:bg-orange-50 transition-colors whitespace-nowrap"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
          </svg>
          Select
        </button>
      );

    case 'ready_to_process':
      return (
        <button
          onClick={handleExtractData}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg border border-coral-300 text-coral-700 hover:bg-coral-50 transition-colors whitespace-nowrap"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          Extract
        </button>
      );

    case 'processing':
      return (
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <div className="animate-spin h-3.5 w-3.5 border-2 border-sky-400 border-t-transparent rounded-full"></div>
          <span className="italic">Extracting...</span>
        </div>
      );

    case 'completed':
      // Show Audit button if document has low-confidence fields
      if (doc.has_low_confidence_fields) {
        return (
          <button
            onClick={() => navigate(`/audit/document/${doc.id}`)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg border border-orange-300 text-orange-700 hover:bg-orange-50 transition-colors whitespace-nowrap"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
            </svg>
            Audit
          </button>
        );
      }
      // Otherwise show Verify button
      return (
        <button
          onClick={handleVerify}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg border border-coral-300 text-coral-700 hover:bg-coral-50 transition-colors whitespace-nowrap"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          Verify
        </button>
      );

    case 'verified':
      return (
        <button
          onClick={handleView}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg border border-periwinkle-300 text-periwinkle-700 hover:bg-periwinkle-50 transition-colors whitespace-nowrap"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
          </svg>
          View
        </button>
      );

    case 'error':
      return (
        <button
          onClick={handleRetry}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg border border-orange-300 text-orange-700 hover:bg-orange-50 transition-colors whitespace-nowrap"
          title={doc.error_message}
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Retry
        </button>
      );

    default:
      return (
        <button
          onClick={handleView}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg border border-periwinkle-300 text-periwinkle-700 hover:bg-periwinkle-50 transition-colors whitespace-nowrap"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
          </svg>
          View
        </button>
      );
  }
}
