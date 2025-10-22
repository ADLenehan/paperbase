import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';

export default function SchemaEditor() {
  const { schemaId } = useParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [schema, setSchema] = useState(null);
  const [error, setError] = useState(null);
  const [documentCount, setDocumentCount] = useState(0);
  const [showSaveModal, setShowSaveModal] = useState(false);
  const [saveOption, setSaveOption] = useState('update');
  const [newTemplateName, setNewTemplateName] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchSchema();
    fetchDocumentCount();
  }, [schemaId]);

  const fetchSchema = async () => {
    try {
      const response = await fetch(`${API_URL}/api/onboarding/schemas/${schemaId}`);
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to load schema');
      }

      setSchema(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchDocumentCount = async () => {
    try {
      const response = await fetch(`${API_URL}/api/onboarding/schemas/${schemaId}/document-count`);
      const data = await response.json();

      if (response.ok) {
        setDocumentCount(data.document_count);
      }
    } catch (err) {
      console.error('Failed to fetch document count:', err);
    }
  };

  const handleSave = () => {
    // Show modal if there are documents using this template
    if (documentCount > 0) {
      setShowSaveModal(true);
    } else {
      // No documents, just update directly
      performSave('update', false);
    }
  };

  const performSave = async (option, triggerReExtraction) => {
    setSaving(true);
    setError(null);

    try {
      if (option === 'new') {
        // Create new schema with the modified fields
        const response = await fetch(`${API_URL}/api/onboarding/schemas`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: newTemplateName || `${schema.name} (Copy)`,
            fields: schema.fields
          }),
        });

        if (!response.ok) {
          throw new Error('Failed to create new template');
        }

        const data = await response.json();
        navigate(`/confirm?schema_id=${data.schema_id}`);
      } else {
        // Update existing schema
        const response = await fetch(`${API_URL}/api/onboarding/schemas/${schemaId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(schema),
        });

        if (!response.ok) {
          throw new Error('Failed to save schema');
        }

        // Trigger re-extraction if requested
        if (triggerReExtraction) {
          const reExtractResponse = await fetch(`${API_URL}/api/onboarding/schemas/${schemaId}/re-extract`, {
            method: 'POST',
          });

          if (!reExtractResponse.ok) {
            throw new Error('Schema updated but re-extraction failed');
          }

          const reExtractData = await reExtractResponse.json();
          alert(`Re-extracting ${reExtractData.processed_count} documents. Check the Documents Dashboard for progress.`);
        }

        navigate(`/documents`);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
      setShowSaveModal(false);
    }
  };

  const addField = () => {
    const newField = {
      name: `field_${schema.fields.length + 1}`,
      type: 'text',
      required: false,
      extraction_hints: [],
      confidence_threshold: 0.75,
      description: ''
    };
    setSchema({
      ...schema,
      fields: [...schema.fields, newField]
    });
  };

  const updateField = (index, key, value) => {
    const updatedFields = [...schema.fields];
    updatedFields[index] = {
      ...updatedFields[index],
      [key]: value
    };
    setSchema({
      ...schema,
      fields: updatedFields
    });
  };

  const removeField = (index) => {
    const updatedFields = schema.fields.filter((_, i) => i !== index);
    setSchema({
      ...schema,
      fields: updatedFields
    });
  };

  if (loading) {
    return (
      <div className="max-w-6xl mx-auto p-6">
        <div className="text-center py-12">
          <div className="text-gray-600">Loading schema...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-6xl mx-auto p-6">
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {error}
        </div>
      </div>
    );
  }

  if (!schema) {
    return null;
  }

  return (
    <div className="max-w-6xl mx-auto p-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Edit Schema</h1>
        <p className="text-gray-600 mt-2">Customize the fields for "{schema.name}"</p>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Schema Name
          </label>
          <input
            type="text"
            value={schema.name}
            onChange={(e) => setSchema({ ...schema, name: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-periwinkle-500"
          />
        </div>

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold text-gray-900">Fields</h2>
            <button
              onClick={addField}
              className="px-4 py-2 bg-periwinkle-500 text-white rounded-lg hover:bg-periwinkle-600 font-medium transition-colors"
            >
              + Add Field
            </button>
          </div>

          {schema.fields.map((field, index) => (
            <div key={index} className="border border-gray-200 rounded-lg p-4 bg-gray-50">
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Field Name
                  </label>
                  <input
                    type="text"
                    value={field.name}
                    onChange={(e) => updateField(index, 'name', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-periwinkle-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Type
                  </label>
                  <select
                    value={field.type}
                    onChange={(e) => updateField(index, 'type', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-periwinkle-500"
                  >
                    <option value="text">Text</option>
                    <option value="number">Number</option>
                    <option value="date">Date</option>
                    <option value="boolean">Boolean</option>
                    <option value="array">Array</option>
                  </select>
                </div>
              </div>

              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Description
                </label>
                <input
                  type="text"
                  value={field.description || ''}
                  onChange={(e) => updateField(index, 'description', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-periwinkle-500"
                  placeholder="Brief description of this field"
                />
              </div>

              <div className="flex items-center justify-between">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={field.required || false}
                    onChange={(e) => updateField(index, 'required', e.target.checked)}
                    className="rounded border-gray-300 text-periwinkle-500 focus:ring-periwinkle-500"
                  />
                  <span className="text-sm text-gray-700">Required field</span>
                </label>

                <button
                  onClick={() => removeField(index)}
                  className="text-red-600 hover:text-red-700 text-sm font-medium"
                >
                  Remove
                </button>
              </div>
            </div>
          ))}

          {schema.fields.length === 0 && (
            <div className="text-center py-8 text-gray-500">
              No fields yet. Click "Add Field" to get started.
            </div>
          )}
        </div>
      </div>

      <div className="flex gap-3">
        <button
          onClick={() => navigate(-1)}
          className="flex-1 border border-gray-300 py-3 px-4 rounded-lg hover:bg-gray-50 font-medium transition-colors"
        >
          Cancel
        </button>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex-1 bg-periwinkle-500 text-white py-3 px-4 rounded-lg hover:bg-periwinkle-600 font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {saving ? 'Saving...' : 'Save & Continue'}
        </button>
      </div>

      {/* Save Options Modal */}
      {showSaveModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <div className="mb-6">
              <div className="flex items-center gap-3 mb-2">
                <div className="w-10 h-10 bg-yellow-100 rounded-full flex items-center justify-center">
                  <span className="text-yellow-600 text-xl">⚠</span>
                </div>
                <h2 className="text-xl font-bold text-gray-900">You've made changes</h2>
              </div>
              <p className="text-gray-600">
                Save as a new template to preserve the original, or overwrite the existing one.
              </p>
              {documentCount > 0 && (
                <div className="mt-3 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                  <p className="text-sm text-blue-800">
                    <strong>{documentCount}</strong> document{documentCount !== 1 ? 's' : ''} currently use{documentCount === 1 ? 's' : ''} this template
                  </p>
                </div>
              )}
            </div>

            <div className="space-y-3 mb-6">
              <label className="flex items-start gap-3 p-4 border-2 rounded-lg cursor-pointer hover:bg-gray-50 transition-colors"
                     style={{ borderColor: saveOption === 'new' ? '#6366f1' : '#e5e7eb' }}>
                <input
                  type="radio"
                  name="saveOption"
                  value="new"
                  checked={saveOption === 'new'}
                  onChange={(e) => setSaveOption(e.target.value)}
                  className="mt-1"
                />
                <div className="flex-1">
                  <div className="font-semibold text-gray-900 mb-1">Save as new template</div>
                  <div className="text-sm text-gray-600">
                    Create a new template with these changes. Existing documents remain unchanged.
                  </div>
                  {saveOption === 'new' && (
                    <input
                      type="text"
                      placeholder="New template name"
                      value={newTemplateName}
                      onChange={(e) => setNewTemplateName(e.target.value)}
                      className="mt-3 w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-periwinkle-500"
                    />
                  )}
                </div>
              </label>

              <label className="flex items-start gap-3 p-4 border-2 rounded-lg cursor-pointer hover:bg-gray-50 transition-colors"
                     style={{ borderColor: saveOption === 'update' ? '#6366f1' : '#e5e7eb' }}>
                <input
                  type="radio"
                  name="saveOption"
                  value="update"
                  checked={saveOption === 'update'}
                  onChange={(e) => setSaveOption(e.target.value)}
                  className="mt-1"
                />
                <div className="flex-1">
                  <div className="font-semibold text-gray-900 mb-1">Update existing template</div>
                  <div className="text-sm text-gray-600">
                    Update this template and optionally re-extract all documents using it.
                  </div>
                  {saveOption === 'update' && documentCount > 0 && (
                    <label className="flex items-center gap-2 mt-3">
                      <input
                        type="checkbox"
                        checked={saveOption === 'update-reextract'}
                        onChange={(e) => setSaveOption(e.target.checked ? 'update-reextract' : 'update')}
                        className="rounded border-gray-300 text-periwinkle-500 focus:ring-periwinkle-500"
                      />
                      <span className="text-sm text-gray-700">
                        Re-extract all {documentCount} document{documentCount !== 1 ? 's' : ''}
                      </span>
                    </label>
                  )}
                </div>
              </label>
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => setShowSaveModal(false)}
                disabled={saving}
                className="flex-1 border border-gray-300 py-2 px-4 rounded-lg hover:bg-gray-50 font-medium transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={() => performSave(
                  saveOption === 'new' ? 'new' : 'update',
                  saveOption === 'update-reextract'
                )}
                disabled={saving || (saveOption === 'new' && !newTemplateName)}
                className="flex-1 bg-periwinkle-500 text-white py-2 px-4 rounded-lg hover:bg-periwinkle-600 font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {saving ? 'Saving...' : 'Continue'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
