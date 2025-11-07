import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import FieldEditor from '../components/FieldEditor';
import ProcessingModal from '../components/modals/ProcessingModal';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function BulkUpload() {
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [analysis, setAnalysis] = useState(null);
  const [error, setError] = useState(null);
  const [progress, setProgress] = useState({ stage: '', current: 0, total: 0, message: '' });
  const [availableTemplates, setAvailableTemplates] = useState([]);
  const [documentGroups, setDocumentGroups] = useState([]);
  const [processing, setProcessing] = useState(false);
  const navigate = useNavigate();

  // NEW: Modal states for modern UX (replaces window.prompt/alert)
  const [showProcessingModal, setShowProcessingModal] = useState(false);
  const [currentGroupIndex, setCurrentGroupIndex] = useState(null);
  const [processingDocuments, setProcessingDocuments] = useState([]);
  const [previewFields, setPreviewFields] = useState(null);
  const [showFieldPreview, setShowFieldPreview] = useState(false);
  const [pendingTemplateName, setPendingTemplateName] = useState('');
  const [processingGroupIndex, setProcessingGroupIndex] = useState(null); // Track which group is being processed via "Use This Template"

  // NEW: Track extracting state per group
  const [extractingGroups, setExtractingGroups] = useState(new Set()); // Set of group indices that are extracting
  const [completedGroups, setCompletedGroups] = useState(new Set()); // Set of group indices that finished extraction

  useEffect(() => {
    fetchTemplates();
  }, []);

  // NEW: Poll document status for extracting groups
  useEffect(() => {
    if (extractingGroups.size === 0) return;

    const pollInterval = setInterval(async () => {
      // Check status of all extracting groups
      for (const groupIdx of extractingGroups) {
        const group = documentGroups[groupIdx];
        if (!group) continue;

        try {
          // Fetch status of all documents in this group
          const statusPromises = group.document_ids.map(docId =>
            fetch(`${API_URL}/api/documents/${docId}`).then(r => r.json())
          );
          const docStatuses = await Promise.all(statusPromises);

          // Check if all documents are completed or have errors
          const allDone = docStatuses.every(doc =>
            doc.status === 'completed' || doc.status === 'verified' || doc.status === 'error'
          );

          if (allDone) {
            // Move group from extracting to completed
            setExtractingGroups(prev => {
              const newSet = new Set(prev);
              newSet.delete(groupIdx);
              return newSet;
            });
            setCompletedGroups(prev => new Set(prev).add(groupIdx));

            console.log(`Group ${groupIdx} extraction complete!`);
          }
        } catch (err) {
          console.error(`Failed to poll status for group ${groupIdx}:`, err);
        }
      }
    }, 3000); // Poll every 3 seconds

    return () => clearInterval(pollInterval);
  }, [extractingGroups, documentGroups]);

  // NEW: Auto-navigate when all groups are processed and completed
  useEffect(() => {
    if (!documentGroups.length) return;

    const allProcessed = documentGroups.every(g => g.auto_processed);
    const allCompleted = documentGroups.every((g, idx) => completedGroups.has(idx));

    if (allProcessed && allCompleted) {
      console.log('All groups processed and completed! Navigating to documents...');
      setTimeout(() => navigate('/documents'), 1500);
    }
  }, [documentGroups, completedGroups, navigate]);

  const fetchTemplates = async () => {
    try {
      const response = await fetch(`${API_URL}/api/onboarding/schemas`);
      const data = await response.json();
      setAvailableTemplates(data.schemas || []);
    } catch (err) {
      console.error('Failed to fetch templates:', err);
    }
  };

  const handleFileSelect = (e) => {
    console.log('📁 handleFileSelect called');
    const selectedFiles = Array.from(e.target.files);
    console.log('Selected files:', selectedFiles);
    setFiles(selectedFiles);
  };

  const handleDrop = (e) => {
    console.log('📁 handleDrop called');
    e.preventDefault();
    const droppedFiles = Array.from(e.dataTransfer.files);
    console.log('Dropped files:', droppedFiles);
    setFiles(droppedFiles);
  };

  const handleUploadAndAnalyze = async () => {
    console.log('📤 handleUploadAndAnalyze called');
    console.log('Files:', files);
    console.log('Files length:', files.length);

    if (files.length === 0) {
      console.log('❌ No files selected, returning early');
      return;
    }

    console.log('✅ Starting upload process...');
    setUploading(true);
    setError(null);
    setProgress({ stage: 'uploading', current: 0, total: files.length, message: 'Uploading files...' });

    const formData = new FormData();
    files.forEach(file => {
      formData.append('files', file);
    });

    try {
      setProgress({ stage: 'uploading', current: files.length, total: files.length, message: `Uploaded ${files.length} file${files.length !== 1 ? 's' : ''}` });

      // Show parsing stage
      setProgress({ stage: 'parsing', current: 0, total: files.length, message: 'Parsing documents with Reducto...' });

      const response = await fetch(`${API_URL}/api/bulk/upload-and-analyze`, {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Upload failed');
      }

      // Show grouping stage
      setProgress({ stage: 'grouping', current: files.length, total: files.length, message: 'Grouping similar documents...' });

      // Show matching stage
      setProgress({ stage: 'matching', current: data.groups?.length || 0, total: data.groups?.length || 0, message: 'Matching templates...' });

      // Transform groups into editable format with template selection
      const groups = data.groups.map(group => {
        // Get actual template name if matched
        let displayName = group.suggested_name;
        if (group.template_match.template_id) {
          const matchedTemplate = availableTemplates.find(t => t.id === group.template_match.template_id);
          if (matchedTemplate) {
            displayName = matchedTemplate.name;
          }
        }

        return {
          ...group,
          selectedTemplateId: group.template_match.template_id,
          isNewTemplate: false,
          templateName: displayName,
          showFieldPreview: false
        };
      });

      setDocumentGroups(groups);
      setAnalysis(data);

      // Analytics available in data.analytics if needed for debugging
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
      setProgress({ stage: '', current: 0, total: 0, message: '' });
    }
  };

  const updateGroupTemplate = (groupIndex, templateId) => {
    const updatedGroups = [...documentGroups];
    updatedGroups[groupIndex].selectedTemplateId = templateId;
    updatedGroups[groupIndex].isNewTemplate = templateId === 'new';
    setDocumentGroups(updatedGroups);
  };

  const updateGroupTemplateName = (groupIndex, name) => {
    const updatedGroups = [...documentGroups];
    updatedGroups[groupIndex].templateName = name;
    setDocumentGroups(updatedGroups);
  };

  const toggleFieldPreview = (groupIndex) => {
    const updatedGroups = [...documentGroups];
    updatedGroups[groupIndex].showFieldPreview = !updatedGroups[groupIndex].showFieldPreview;
    setDocumentGroups(updatedGroups);
  };

  const handleProcessAll = async () => {
    setProcessing(true);
    setError(null);

    const errors = [];
    const successes = [];
    const updatedGroups = [...documentGroups];

    try {
      // Process each group based on selection (only unprocessed groups)
      for (const [index, group] of documentGroups.entries()) {
        // Skip already processed groups
        if (group.auto_processed) {
          continue;
        }

        try {
          if (group.isNewTemplate) {
            // Create new template
            const response = await fetch(`${API_URL}/api/bulk/create-new-template`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                document_ids: group.document_ids,
                template_name: group.templateName
              }),
            });

            if (!response.ok) {
              const errorData = await response.json().catch(() => ({}));
              throw new Error(errorData.detail || `HTTP ${response.status}`);
            }

            // Mark as processed
            updatedGroups[index] = { ...updatedGroups[index], auto_processed: true };
            successes.push({ group: group.templateName, index });
          } else if (group.selectedTemplateId) {
            // Use existing template
            const response = await fetch(`${API_URL}/api/bulk/confirm-template`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                document_ids: group.document_ids,
                template_id: group.selectedTemplateId
              }),
            });

            if (!response.ok) {
              const errorData = await response.json().catch(() => ({}));
              throw new Error(errorData.detail || `HTTP ${response.status}`);
            }

            // Mark as processed
            updatedGroups[index] = { ...updatedGroups[index], auto_processed: true };
            successes.push({ group: group.suggested_name, index });
          }
        } catch (err) {
          errors.push({
            group: group.templateName || group.suggested_name,
            index,
            error: err.message
          });
        }
      }

      // Update state
      setDocumentGroups(updatedGroups);

      // Show results
      if (errors.length > 0 && successes.length > 0) {
        // Partial failure
        setError(`Processed ${successes.length}/${documentGroups.length} groups successfully. Failed: ${errors.map(e => `"${e.group}" (${e.error})`).join(', ')}`);
        // Still navigate to see successful ones
        setTimeout(() => navigate('/documents'), 2000);
      } else if (errors.length > 0) {
        // Complete failure
        setError(`Failed to process all groups: ${errors.map(e => `"${e.group}" (${e.error})`).join(', ')}`);
      } else {
        // Complete success - navigate immediately
        setTimeout(() => navigate('/documents'), 1000);
      }
    } finally {
      setProcessing(false);
    }
  };

  const handleConfirmTemplate = async (documentIds, templateId) => {
    try {
      const response = await fetch(`${API_URL}/api/bulk/confirm-template`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ document_ids: documentIds, template_id: templateId }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Template confirmation failed');
      }

      // Navigate to bulk confirmation
      navigate(`/confirm?schema_id=${data.schema_id}`);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleCreateNewTemplate = async (documentIds, templateName) => {
    try {
      const response = await fetch(`${API_URL}/api/bulk/create-new-template`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ document_ids: documentIds, template_name: templateName }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Template creation failed');
      }

      // Potential matches available in data.potential_matches if needed
      // User will see matched documents in the documents dashboard

      // Navigate to schema editing
      navigate(`/schema/${data.schema_id}`);
    } catch (err) {
      setError(err.message);
    }
  };


  const handleFinalizeTemplate = async (fieldData) => {
    console.log('🚀🚀🚀 handleFinalizeTemplate CALLED 🚀🚀🚀');
    console.log('currentGroupIndex:', currentGroupIndex);
    console.log('fieldData:', fieldData);
    console.log('documentGroups:', documentGroups);

    if (currentGroupIndex === null) {
      console.error('❌ currentGroupIndex is NULL - EARLY RETURN!');
      setError('Internal error: No group selected. Please try again.');
      return;
    }

    console.log('✅ currentGroupIndex is valid, proceeding...');
    const group = documentGroups[currentGroupIndex];
    console.log('group:', group);

    if (!group) {
      console.error('❌ Group not found at index', currentGroupIndex);
      setError('Internal error: Group not found. Please try again.');
      return;
    }

    try {
      setProcessing(true);
      setError(null);

      // Extract fields array from FieldEditor's return object
      // FieldEditor returns: { fields: [...], name: "...", isNewTemplate: bool }
      const finalFields = Array.isArray(fieldData) ? fieldData : fieldData.fields;

      const requestBody = {
        document_ids: group.document_ids,
        template_name: pendingTemplateName,
        fields: finalFields
      };

      console.log('=== CREATE TEMPLATE REQUEST ===');
      console.log('API URL:', `${API_URL}/api/bulk/create-new-template`);
      console.log('Document IDs:', group.document_ids);
      console.log('Template Name:', pendingTemplateName);
      console.log('Fields Count:', finalFields?.length);
      console.log('First field:', finalFields?.[0]);
      console.log('Request body:', requestBody);
      console.log('Stringified body:', JSON.stringify(requestBody));

      // Create template with user-confirmed fields
      console.log('Making fetch request...');
      const response = await fetch(`${API_URL}/api/bulk/create-new-template`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody),
      });
      console.log('Fetch completed, response status:', response.status);

      if (!response.ok) {
        const data = await response.json().catch(() => ({ detail: `HTTP ${response.status}` }));
        console.error('Template creation failed:', data);

        // Handle specific errors
        let errorMessage = data.detail || data.message || 'Template creation failed';

        // Check for duplicate name error
        if (response.status === 500 && (errorMessage.includes('UNIQUE') || errorMessage.includes('unique'))) {
          errorMessage = `A template named "${pendingTemplateName}" already exists. Please try a different name.`;
        }

        throw new Error(errorMessage);
      }

      const data = await response.json();
      console.log('Template created successfully:', data);

      // Mark this group as processed (extraction started on backend)
      const updatedGroups = [...documentGroups];
      updatedGroups[currentGroupIndex] = {
        ...updatedGroups[currentGroupIndex],
        auto_processed: true,
        selectedTemplateId: data.schema_id,
        templateName: pendingTemplateName
      };
      setDocumentGroups(updatedGroups);

      // Mark group as extracting (will be polled for completion)
      setExtractingGroups(prev => new Set(prev).add(currentGroupIndex));

      // Close preview and reset state
      setShowFieldPreview(false);
      setPreviewFields(null);
      setPendingTemplateName('');
      setCurrentGroupIndex(null);
      setProcessing(false);

      // Refresh templates list
      fetchTemplates();

      // Check if all groups are processed
      const remainingGroups = updatedGroups.filter(g => !g.auto_processed);
      console.log(`Template created! Remaining groups: ${remainingGroups.length}/${updatedGroups.length}`);

      if (remainingGroups.length === 0) {
        // All groups processed! Wait for extractions to complete before navigating
        console.log('All groups processing started! Waiting for extractions to complete...');
      }
    } catch (err) {
      console.error('Error in handleFinalizeTemplate:', err);
      setError(err.message || 'Failed to create template. Check console for details.');
      setProcessing(false);
    }
  };

  const handleCancelFieldPreview = () => {
    setShowFieldPreview(false);
    setPreviewFields(null);
    setPendingTemplateName('');
    setCurrentGroupIndex(null);
  };

  return (
    <div className="max-w-6xl mx-auto p-6">
      <h1 className="text-3xl font-bold mb-6 text-gray-900">Bulk Document Upload</h1>

      {/* Upload Section */}
      {!analysis && (
        <div className="space-y-6">
          <div
            onDrop={handleDrop}
            onDragOver={(e) => e.preventDefault()}
            className="border-2 border-dashed border-gray-300 rounded-lg p-12 text-center hover:border-periwinkle-400 transition-colors"
          >
            <input
              type="file"
              multiple
              accept=".pdf,.png,.jpg,.jpeg,.doc,.docx"
              onChange={handleFileSelect}
              className="hidden"
              id="file-input"
            />
            <label htmlFor="file-input" className="cursor-pointer">
              <div className="text-gray-600">
                <svg className="mx-auto h-12 w-12 mb-4 text-periwinkle-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
                <p className="text-lg font-medium text-gray-900">Drop files here or click to browse</p>
                <p className="text-sm text-gray-500 mt-2">Upload multiple documents at once</p>
              </div>
            </label>
          </div>

          {files.length > 0 && (
            <div className="bg-white rounded-lg border border-gray-200 p-4 shadow-sm">
              <h3 className="font-semibold mb-3 text-gray-900">{files.length} files selected</h3>
              <ul className="space-y-1 text-sm max-h-40 overflow-y-auto">
                {files.map((file, idx) => (
                  <li key={idx} className="text-gray-600">{file.name}</li>
                ))}
              </ul>
            </div>
          )}

          {error && (
            <div className="bg-primary-50 border border-primary-200 text-primary-700 px-4 py-3 rounded-lg">
              {error}
            </div>
          )}

          {uploading && (
            <ProgressDisplay progress={progress} />
          )}

          <button
            onClick={handleUploadAndAnalyze}
            disabled={files.length === 0 || uploading}
            className="w-full bg-periwinkle-500 text-white py-3 rounded-lg font-medium hover:bg-periwinkle-600 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors focus:outline-none focus:ring-2 focus:ring-periwinkle-500 focus:ring-offset-2"
          >
            {uploading ? 'Processing...' : 'Upload & Analyze'}
          </button>
        </div>
      )}

      {/* Analysis Results - Table View */}
      {analysis && documentGroups.length > 0 && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-bold text-gray-900">Review & Process Documents</h2>
              <p className="text-gray-600 mt-1">
                {(() => {
                  const processedCount = documentGroups.filter(g => g.auto_processed).length;
                  const totalGroups = documentGroups.length;
                  const remainingGroups = totalGroups - processedCount;

                  if (processedCount > 0) {
                    return `${processedCount} of ${totalGroups} groups processed. ${remainingGroups > 0 ? `${remainingGroups} remaining.` : 'All done!'}`;
                  }
                  return `${analysis.total_documents} documents grouped into ${totalGroups} template${totalGroups !== 1 ? 's' : ''}. Review and assign templates below.`;
                })()}
              </p>
            </div>
            <button
              onClick={handleProcessAll}
              disabled={
                processing ||
                // Only disable if NO groups are ready to process
                !documentGroups.some(g =>
                  !g.auto_processed && (g.selectedTemplateId || g.isNewTemplate)
                )
              }
              className="px-6 py-3 bg-periwinkle-500 text-white rounded-lg font-medium hover:bg-periwinkle-600 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
            >
              {processing ? 'Processing...' : (() => {
                const processableGroups = documentGroups.filter(g =>
                  !g.auto_processed && (g.selectedTemplateId || g.isNewTemplate)
                );
                return processableGroups.length > 0
                  ? `Process ${processableGroups.length} Group${processableGroups.length !== 1 ? 's' : ''}`
                  : 'No Groups Ready';
              })()}
            </button>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
              {error}
            </div>
          )}

          {/* Table */}
          <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="text-left px-6 py-3 text-sm font-semibold text-gray-900">Documents</th>
                  <th className="text-left px-6 py-3 text-sm font-semibold text-gray-900">Template</th>
                  <th className="text-left px-6 py-3 text-sm font-semibold text-gray-900">Match</th>
                  <th className="text-left px-6 py-3 text-sm font-semibold text-gray-900">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {(() => {
                  const remainingGroups = documentGroups.filter(group => !group.auto_processed);

                  if (remainingGroups.length === 0) {
                    // All groups processed!
                    return (
                      <tr>
                        <td colSpan="4" className="px-6 py-12 text-center">
                          <div className="flex flex-col items-center justify-center space-y-3">
                            <div className="text-xl font-semibold text-gray-900">All Groups Processed!</div>
                            <div className="text-sm text-gray-600">
                              Extraction started for all {analysis.total_documents} documents. Redirecting to documents page...
                            </div>
                            <div className="mt-4">
                              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-periwinkle-500"></div>
                            </div>
                          </div>
                        </td>
                      </tr>
                    );
                  }

                  return remainingGroups.map((group, idx) => {
                    // Find original index for callbacks
                    const originalIndex = documentGroups.findIndex(g => g === group);
                    return (
                      <DocumentGroupRow
                        key={originalIndex}
                        group={group}
                        groupIndex={originalIndex}
                        availableTemplates={availableTemplates}
                        isExtracting={extractingGroups.has(originalIndex)}
                        isCompleted={completedGroups.has(originalIndex)}
                        onTemplateChange={updateGroupTemplate}
                        onTemplateNameChange={updateGroupTemplateName}
                        onTogglePreview={toggleFieldPreview}
                        onCreateNewTemplate={async (groupIdx) => {
                          console.log('Create New Template clicked for group', groupIdx);
                          setCurrentGroupIndex(groupIdx);

                          const group = documentGroups[groupIdx];

                          try {
                            // Generate AI-suggested fields
                            setProcessing(true);
                            setError(null);

                            const response = await fetch(`${API_URL}/api/bulk/generate-schema`, {
                              method: 'POST',
                              headers: { 'Content-Type': 'application/json' },
                              body: JSON.stringify({
                                document_ids: group.document_ids,
                                template_name: group.suggested_name || 'New Template'
                              }),
                            });

                            const data = await response.json();

                            if (!response.ok) {
                              throw new Error(data.detail || 'Schema generation failed');
                            }

                            // Show field preview with suggested template name
                            setPendingTemplateName(group.suggested_name || 'New Template');
                            setPreviewFields(data.suggested_fields || []);
                            setShowFieldPreview(true);
                            setProcessing(false);
                          } catch (err) {
                            setError(err.message);
                            setProcessing(false);
                          }
                        }}
                        onUseTemplate={async (groupIdx) => {
                          // Handle "Use This Template" button click
                          setProcessingGroupIndex(groupIdx);
                          try {
                            const g = documentGroups[groupIdx];
                            const response = await fetch(`${API_URL}/api/bulk/confirm-template`, {
                              method: 'POST',
                              headers: { 'Content-Type': 'application/json' },
                              body: JSON.stringify({
                                document_ids: g.document_ids,
                                template_id: g.template_match.template_id
                              }),
                            });

                            if (!response.ok) {
                              const errorData = await response.json().catch(() => ({}));
                              throw new Error(errorData.detail || `HTTP ${response.status}`);
                            }

                            // Mark as processed
                            const updatedGroups = [...documentGroups];
                            updatedGroups[groupIdx] = { ...updatedGroups[groupIdx], auto_processed: true };
                            setDocumentGroups(updatedGroups);

                            // Mark group as extracting (will be polled for completion)
                            setExtractingGroups(prev => new Set(prev).add(groupIdx));

                            // Check if all done
                            const remainingGroups = updatedGroups.filter(g => !g.auto_processed);
                            if (remainingGroups.length === 0) {
                              console.log('All groups processing started! Waiting for extractions to complete...');
                            }
                          } catch (err) {
                            setError(`Failed to process group: ${err.message}`);
                          } finally {
                            setProcessingGroupIndex(null);
                          }
                        }}
                        processingGroupIndex={processingGroupIndex}
                        setError={setError}
                        isProcessing={processing && currentGroupIndex === originalIndex}
                      />
                    );
                  });
                })()}
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between text-sm text-gray-600 bg-gray-50 px-6 py-4 rounded-lg">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-mint-500 rounded-full"></div>
                <span>Good match (≥70% - can use template)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-yellow-500 rounded-full"></div>
                <span>Uncertain (50-70% - review carefully)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-red-500 rounded-full"></div>
                <span>Poor match ({'<'}50% - create new template)</span>
              </div>
            </div>
            <div>
              Need help? <a href="#" className="text-periwinkle-600 hover:underline">View guide</a>
            </div>
          </div>
        </div>
      )}


      {/* NEW: Processing Modal (live progress feedback) */}
      <ProcessingModal
        isOpen={showProcessingModal}
        documents={processingDocuments}
        onClose={() => setShowProcessingModal(false)}
        onComplete={() => {
          setShowProcessingModal(false);
          navigate('/documents');
        }}
      />

      {/* NEW: Field Preview Modal - Review AI-suggested fields before creating template */}
      {showFieldPreview && previewFields && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
            {/* Header */}
            <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <h2 className="text-xl font-semibold text-gray-900 mb-3">
                    Review Template Fields
                  </h2>
                  {/* Editable template name */}
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-gray-700">Template Name</label>
                    <input
                      type="text"
                      value={pendingTemplateName}
                      onChange={(e) => {
                        setPendingTemplateName(e.target.value);
                        // Clear error when user starts editing (especially for duplicate name errors)
                        if (error) setError(null);
                      }}
                      disabled={processing}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-periwinkle-500 focus:border-periwinkle-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
                      placeholder="Enter template name"
                    />
                    <p className="text-xs text-gray-500">
                      Review AI-suggested fields below and edit as needed before saving.
                    </p>
                  </div>
                </div>
                {/* Close button */}
                <button
                  onClick={handleCancelFieldPreview}
                  disabled={processing}
                  className="ml-4 text-gray-400 hover:text-gray-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  aria-label="Close modal"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
              {error && (
                <div className="mt-3 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm flex items-start justify-between">
                  <span className="flex-1">{error}</span>
                  <button
                    onClick={() => setError(null)}
                    className="ml-2 text-red-500 hover:text-red-700 font-bold"
                  >
                    ×
                  </button>
                </div>
              )}
            </div>

            {/* Field Editor */}
            <div className="flex-1 overflow-y-auto p-6">
              <FieldEditor
                templateId={null}
                templateName={pendingTemplateName}
                initialFields={previewFields}
                onSave={handleFinalizeTemplate}
                onCancel={handleCancelFieldPreview}
                isNewTemplate={true}
                isSaving={processing}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ProgressDisplay({ progress }) {
  const getStageIcon = (stage) => {
    const icons = {
      uploading: '📤',
      parsing: '📄',
      grouping: '📊',
      matching: '🔍'
    };
    return icons[stage] || '⏳';
  };

  const getStageLabel = (stage) => {
    const labels = {
      uploading: 'Uploading',
      parsing: 'Parsing documents',
      grouping: 'Grouping similar documents',
      matching: 'Matching templates'
    };
    return labels[stage] || 'Processing';
  };

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6 shadow-sm">
      <div className="flex items-center gap-3 mb-4">
        <div className="text-3xl animate-pulse">{getStageIcon(progress.stage)}</div>
        <div className="flex-1">
          <div className="font-semibold text-gray-900">{getStageLabel(progress.stage)}</div>
          <div className="text-sm text-gray-600 mt-1">{progress.message}</div>
        </div>
      </div>

      {/* Progress bar */}
      {progress.total > 0 && (
        <div className="space-y-2">
          <div className="flex justify-between text-sm text-gray-600">
            <span>{progress.current} of {progress.total}</span>
            <span>{Math.round((progress.current / progress.total) * 100)}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-periwinkle-500 h-2 rounded-full transition-all duration-300"
              style={{ width: `${(progress.current / progress.total) * 100}%` }}
            />
          </div>
        </div>
      )}

      {/* Stage indicators */}
      <div className="flex gap-2 mt-4">
        {['uploading', 'parsing', 'grouping', 'matching'].map((stage, idx) => (
          <div
            key={stage}
            className={`flex-1 h-1 rounded-full transition-all ${
              progress.stage === stage
                ? 'bg-periwinkle-500'
                : idx < ['uploading', 'parsing', 'grouping', 'matching'].indexOf(progress.stage)
                ? 'bg-mint-500'
                : 'bg-gray-200'
            }`}
          />
        ))}
      </div>
    </div>
  );
}

function DocumentGroupRow({ group, groupIndex, availableTemplates, isExtracting, isCompleted, onTemplateChange, onTemplateNameChange, onTogglePreview, onCreateNewTemplate, onUseTemplate, processingGroupIndex, setError, isProcessing = false }) {
  const navigate = useNavigate();
  const confidence = group.template_match.confidence;
  // Updated color thresholds: 70%+ = green, 50-70% = yellow, <50% = red
  const confidenceColor = confidence >= 0.70 ? 'bg-mint-500' : confidence >= 0.50 ? 'bg-yellow-500' : 'bg-red-500';
  const matchSource = group.template_match.match_source || 'unknown';
  const [templateFields, setTemplateFields] = useState(null);
  const [loadingFields, setLoadingFields] = useState(false);
  const [showFieldEditor, setShowFieldEditor] = useState(false);

  // Smart default action based on confidence and match
  const getDefaultAction = (confidence, hasTemplate) => {
    if (!hasTemplate) return 'create';
    if (confidence >= 0.75) return 'use';
    if (confidence >= 0.5) return 'review';
    return 'change';
  };

  // Match source display
  const sourceIcon = matchSource === 'elasticsearch' ? '⚡' : matchSource === 'claude' ? '🧠' : '❓';
  const sourceLabel = matchSource === 'elasticsearch' ? 'Fast Match' : matchSource === 'claude' ? 'AI Match' : 'No Match';
  const sourceBgColor = matchSource === 'elasticsearch' ? 'bg-mint-50 text-mint-700' : matchSource === 'claude' ? 'bg-periwinkle-50 text-periwinkle-700' : 'bg-gray-50 text-gray-600';

  const loadTemplateFields = async (templateId) => {
    if (!templateId || templateId === 'new') return;

    setLoadingFields(true);
    try {
      const response = await fetch(`${API_URL}/api/onboarding/schemas/${templateId}`);
      const data = await response.json();
      setTemplateFields(data.fields || []);
    } catch (error) {
      console.error('Error loading template fields:', error);
    } finally {
      setLoadingFields(false);
    }
  };

  const handleTemplateChange = (templateId) => {
    onTemplateChange(groupIndex, templateId);
    if (templateId && templateId !== 'new') {
      loadTemplateFields(templateId);
    } else {
      setTemplateFields(null);
    }
  };

  const handleTogglePreview = () => {
    const newState = !group.showFieldPreview;
    onTogglePreview(groupIndex);

    // Load fields when opening preview
    if (newState && group.selectedTemplateId && !templateFields) {
      loadTemplateFields(group.selectedTemplateId);
    }
  };

  const handleOpenFieldEditor = () => {
    if (!group.selectedTemplateId && !group.isNewTemplate) {
      // Better UX: Show inline error message instead of alert
      setError('Please select a template first');
      return;
    }

    if (group.selectedTemplateId && !templateFields) {
      loadTemplateFields(group.selectedTemplateId);
    }
    setShowFieldEditor(true);
  };

  const handleSaveFields = async (fieldData) => {
    // This will be handled by creating a new template or updating existing
    // For now, just close the editor
    setShowFieldEditor(false);

    // Update the group with new template info
    if (fieldData.isNewTemplate) {
      onTemplateNameChange(groupIndex, fieldData.name);
      onTemplateChange(groupIndex, 'new');
    }

    // Store the modified fields temporarily
    setTemplateFields(fieldData.fields);
  };

  return (
    <>
      <tr className="hover:bg-gray-50">
        {/* Documents */}
        <td className="px-6 py-4">
          <div className="text-sm font-medium text-gray-900 mb-1">{group.filenames.length} file{group.filenames.length !== 1 ? 's' : ''}</div>
          <div className="text-xs text-gray-500 max-w-xs truncate">
            {group.filenames.slice(0, 2).join(', ')}
            {group.filenames.length > 2 && ` +${group.filenames.length - 2} more`}
          </div>
        </td>

        {/* Template Display */}
        <td className="px-6 py-4">
          <div className="flex items-start gap-2">
            <div>
              <div className="text-sm font-medium text-gray-900">
                {group.templateName || 'No template selected'}
              </div>
              {confidence < 0.70 && group.template_match.template_id && (
                <div className="text-xs text-red-600 font-medium mt-1">
                  Low confidence - recommend creating new template
                </div>
              )}
              {group.template_match.reasoning && (
                <div className="text-xs text-gray-500 mt-1 max-w-xs">
                  {group.template_match.reasoning.slice(0, 80)}...
                </div>
              )}
            </div>
          </div>
        </td>

        {/* Match Confidence */}
        <td className="px-6 py-4">
          {confidence < 0.70 ? (
            <span className="px-4 py-2 rounded-lg border-2 border-red-500 text-red-500 text-sm font-medium inline-flex items-center justify-center w-fit">
              {Math.round(confidence * 100)}%
            </span>
          ) : (
            <span className={`text-xs px-2 py-1 rounded ${sourceBgColor} inline-flex items-center gap-1 w-fit`}>
              <span>{sourceIcon}</span>
              <span>{sourceLabel}</span>
            </span>
          )}
        </td>

        {/* Actions - Simple Per-Group Buttons */}
        <td className="px-6 py-4">
          <div className="flex flex-col gap-2">
            {/* Show "View in Documents" link if extraction is complete */}
            {isCompleted ? (
              <button
                onClick={() => navigate('/documents')}
                className="px-4 py-2 bg-periwinkle-500 text-white rounded-lg text-sm font-medium hover:bg-periwinkle-600 transition-colors inline-flex items-center justify-center gap-2"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>View in Documents</span>
              </button>
            ) : isExtracting ? (
              /* Show "Extracting..." while extraction is in progress */
              <div className="px-4 py-2 bg-sky-100 text-sky-700 rounded-lg text-sm font-medium inline-flex items-center justify-center gap-2">
                <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <span>Extracting...</span>
              </div>
            ) : (
              <>
                {/* Show "Use This Template" if ES found a match with confidence >= 0.70 */}
                {group.template_match.template_id && confidence >= 0.70 ? (
                  <button
                    onClick={() => onUseTemplate(groupIndex)}
                    disabled={processingGroupIndex === groupIndex}
                    className="px-4 py-2 bg-mint-500 text-white rounded-lg text-sm font-medium hover:bg-mint-600 transition-colors inline-flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {processingGroupIndex === groupIndex ? (
                      <>
                        <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        <span>Processing...</span>
                      </>
                    ) : (
                      <span>Use This Template</span>
                    )}
                  </button>
                ) : null}

                {/* Always show "Create New Template" button */}
                <button
                  onClick={() => {
                    console.log('Button clicked for group', groupIndex);
                    onCreateNewTemplate(groupIndex);
                  }}
                  disabled={isProcessing}
                  className="px-4 py-2 bg-periwinkle-500 text-white rounded-lg text-sm font-medium hover:bg-periwinkle-600 transition-colors inline-flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isProcessing ? (
                    <>
                      <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      <span>Generating...</span>
                    </>
                  ) : (
                    <>
                      <span>✨</span>
                      <span>Create New Template</span>
                    </>
                  )}
                </button>
              </>
            )}
          </div>
        </td>
      </tr>

      {/* Expandable Field Preview */}
      {group.showFieldPreview && !showFieldEditor && (
        <tr>
          <td colSpan="4" className="px-6 py-4 bg-gray-50 border-t border-gray-200">
            {loadingFields ? (
              <div className="text-center py-4 text-gray-500">Loading fields...</div>
            ) : templateFields && templateFields.length > 0 ? (
              <div className="max-w-4xl">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="text-sm font-semibold text-gray-900">Template Fields</h4>
                  <button
                    onClick={handleOpenFieldEditor}
                    className="text-sm text-periwinkle-600 hover:text-periwinkle-700 font-medium"
                  >
                    ✏️ Edit Fields
                  </button>
                </div>
                <div className="grid grid-cols-3 gap-3">
                  {templateFields.map((field, idx) => (
                    <div key={idx} className="bg-white px-3 py-2 rounded border border-gray-200">
                      <div className="font-mono text-xs text-gray-900 font-medium">{field.name}</div>
                      <div className="text-xs text-gray-500 mt-1">
                        {field.type} • {field.required ? 'required' : 'optional'}
                      </div>
                      {field.description && (
                        <div className="text-xs text-gray-400 mt-1 line-clamp-1">{field.description}</div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="text-sm text-gray-500 italic">
                {group.isNewTemplate
                  ? 'Fields will be generated when template is created. Click "Edit" to customize.'
                  : 'No fields available. Select a template or create a new one.'}
              </div>
            )}
          </td>
        </tr>
      )}

      {/* Field Editor Modal */}
      {showFieldEditor && (
        <tr>
          <td colSpan="4" className="px-6 py-6 bg-white border-t border-b-2 border-periwinkle-200">
            <FieldEditor
              templateId={group.selectedTemplateId}
              templateName={group.templateName}
              initialFields={templateFields || group.common_fields?.map((name, idx) => ({
                name,
                type: 'text',
                required: false,
                description: '',
                extraction_hints: [],
                confidence_threshold: 0.75
              })) || []}
              onSave={handleSaveFields}
              onCancel={() => setShowFieldEditor(false)}
            />
          </td>
        </tr>
      )}
    </>
  );
}
