import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import FieldEditor from '../components/FieldEditor';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';

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

  useEffect(() => {
    fetchTemplates();
  }, []);

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
    const selectedFiles = Array.from(e.target.files);
    setFiles(selectedFiles);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const droppedFiles = Array.from(e.dataTransfer.files);
    setFiles(droppedFiles);
  };

  const handleUploadAndAnalyze = async () => {
    if (files.length === 0) return;

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

      // Show analytics if available
      if (data.analytics) {
        console.log('Matching Analytics:', data.analytics);
      }
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

    try {
      // Process each group based on selection
      for (const group of documentGroups) {
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
            throw new Error(`Failed to create template for ${group.templateName}`);
          }
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
            throw new Error(`Failed to process group ${group.suggested_name}`);
          }
        }
      }

      // Navigate to documents dashboard to see processing status
      navigate('/documents');
    } catch (err) {
      setError(err.message);
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

      // Show notification if potential matches found
      if (data.potential_matches && data.potential_matches.length > 0) {
        alert(`✨ Template created! Found ${data.rematch_count} potential matches. Check the Documents dashboard to review them.`);
      }

      // Navigate to schema editing
      navigate(`/schema/${data.schema_id}`);
    } catch (err) {
      setError(err.message);
    }
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
                {analysis.total_documents} documents grouped into {documentGroups.length} template{documentGroups.length !== 1 ? 's' : ''}.
                Review and assign templates below.
              </p>
            </div>
            <button
              onClick={handleProcessAll}
              disabled={processing || documentGroups.some(g => !g.selectedTemplateId && !g.isNewTemplate)}
              className="px-6 py-3 bg-periwinkle-500 text-white rounded-lg font-medium hover:bg-periwinkle-600 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
            >
              {processing ? 'Processing...' : `Process All (${analysis.total_documents} docs)`}
            </button>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
              {error}
            </div>
          )}

          {/* Analytics Display */}
          {analysis.analytics && (
            <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
              <h4 className="font-semibold text-gray-700 mb-3 text-sm">Matching Analytics</h4>
              <div className="grid grid-cols-3 gap-4">
                <div className="bg-white rounded-lg p-3 border border-gray-200">
                  <div className="text-xs text-gray-500 mb-1">Fast Matches (ES)</div>
                  <div className="text-2xl font-bold text-mint-600">
                    ⚡ {analysis.analytics.elasticsearch_matches}
                  </div>
                </div>
                <div className="bg-white rounded-lg p-3 border border-gray-200">
                  <div className="text-xs text-gray-500 mb-1">AI Matches (Claude)</div>
                  <div className="text-2xl font-bold text-periwinkle-600">
                    🧠 {analysis.analytics.claude_fallback_matches}
                  </div>
                </div>
                <div className="bg-white rounded-lg p-3 border border-gray-200">
                  <div className="text-xs text-gray-500 mb-1">Estimated Cost</div>
                  <div className="text-2xl font-bold text-green-600">
                    💰 {analysis.analytics.cost_estimate}
                  </div>
                </div>
              </div>
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
                {documentGroups.map((group, idx) => (
                  <DocumentGroupRow
                    key={idx}
                    group={group}
                    groupIndex={idx}
                    availableTemplates={availableTemplates}
                    onTemplateChange={updateGroupTemplate}
                    onTemplateNameChange={updateGroupTemplateName}
                    onTogglePreview={toggleFieldPreview}
                  />
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between text-sm text-gray-600 bg-gray-50 px-6 py-4 rounded-lg">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-mint-500 rounded-full"></div>
                <span>High confidence ({'>'}70%)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-yellow-500 rounded-full"></div>
                <span>Medium confidence (50-70%)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-gray-400 rounded-full"></div>
                <span>Low confidence ({'<'}50%)</span>
              </div>
            </div>
            <div>
              Need help? <a href="#" className="text-periwinkle-600 hover:underline">View guide</a>
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

function DocumentGroupRow({ group, groupIndex, availableTemplates, onTemplateChange, onTemplateNameChange, onTogglePreview }) {
  const confidence = group.template_match.confidence;
  const confidenceColor = confidence >= 0.75 ? 'bg-mint-500' : confidence >= 0.6 ? 'bg-yellow-500' : 'bg-gray-400';
  const matchSource = group.template_match.match_source || 'unknown';
  const [templateFields, setTemplateFields] = useState(null);
  const [loadingFields, setLoadingFields] = useState(false);
  const [showFieldEditor, setShowFieldEditor] = useState(false);

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
      alert('Please select a template first');
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
            {group.template_match.template_id ? (
              <span className="text-yellow-500 text-sm">✨</span>
            ) : null}
            <div>
              <div className="text-sm font-medium text-gray-900">
                {group.templateName || 'No template selected'}
              </div>
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
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2">
              <div className={`w-3 h-3 rounded-full ${confidenceColor}`}></div>
              <span className="text-sm font-medium text-gray-700">
                {Math.round(confidence * 100)}%
              </span>
            </div>
            {/* Match source badge */}
            <span className={`text-xs px-2 py-1 rounded ${sourceBgColor} inline-flex items-center gap-1 w-fit`}>
              <span>{sourceIcon}</span>
              <span>{sourceLabel}</span>
            </span>
          </div>
        </td>

        {/* Actions - Single Explore Dropdown */}
        <td className="px-6 py-4">
          <select
            onChange={(e) => {
              const value = e.target.value;
              if (value === 'edit') {
                handleOpenFieldEditor();
              } else if (value === 'change') {
                // Show template selector inline
                const newTemplateId = prompt('Enter template ID or "new" for new template:');
                if (newTemplateId) {
                  handleTemplateChange(newTemplateId === 'new' ? 'new' : parseInt(newTemplateId));
                }
              }
              e.target.value = ''; // Reset dropdown
            }}
            className="px-4 py-2 text-sm border border-gray-300 rounded-lg bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-periwinkle-500 cursor-pointer"
          >
            <option value="">Explore ▼</option>
            <option value="edit">✏️ Edit Template Fields</option>
            <option value="change">🔄 Change Template</option>
          </select>
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
