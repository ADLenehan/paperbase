import { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';

export default function BulkConfirmation() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const schemaId = searchParams.get('schema_id');

  const [documents, setDocuments] = useState([]);
  const [schema, setSchema] = useState(null);
  const [loading, setLoading] = useState(true);
  const [editedValues, setEditedValues] = useState({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchData();
  }, [schemaId]);

  const fetchData = async () => {
    if (!schemaId) {
      setLoading(false);
      return;
    }

    try {
      // Fetch schema
      const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';
      const schemaRes = await fetch(`${API_URL}/api/onboarding/schemas/${schemaId}`);
      if (!schemaRes.ok) {
        throw new Error('Schema not found');
      }
      const schemaData = await schemaRes.json();
      setSchema(schemaData);

      // Fetch documents with extractions
      const docsRes = await fetch(`${API_URL}/api/documents?schema_id=${schemaId}`);
      if (!docsRes.ok) {
        throw new Error('Documents not found');
      }
      const docsData = await docsRes.json();
      setDocuments(docsData.documents || []);
    } catch (err) {
      console.error('Failed to fetch data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleCellEdit = (docId, fieldName, value) => {
    setEditedValues(prev => ({
      ...prev,
      [`${docId}_${fieldName}`]: value
    }));
  };

  const getFieldValue = (doc, fieldName) => {
    const key = `${doc.id}_${fieldName}`;
    if (editedValues[key] !== undefined) {
      return editedValues[key];
    }

    const field = doc.extracted_fields?.find(f => f.field_name === fieldName);
    return field?.field_value || '';
  };

  const getFieldConfidence = (doc, fieldName) => {
    const field = doc.extracted_fields?.find(f => f.field_name === fieldName);
    return field?.confidence_score;
  };

  const getConfidenceColor = (confidence) => {
    if (!confidence) return 'bg-gray-50';
    if (confidence >= 0.8) return 'bg-mint-50';
    if (confidence >= 0.6) return 'bg-yellow-50';
    return 'bg-coral-50';
  };

  const handleConfirmAll = async () => {
    setSaving(true);
    try {
      const verifications = [];

      // Build verification data
      documents.forEach(doc => {
        schema.fields.forEach(field => {
          const key = `${doc.id}_${field.name}`;
          const originalField = doc.extracted_fields?.find(f => f.field_name === field.name);
          const currentValue = editedValues[key] !== undefined ? editedValues[key] : originalField?.field_value;

          if (originalField) {
            verifications.push({
              document_id: doc.id,
              field_id: originalField.id,
              field_name: field.name,
              original_value: originalField.field_value,
              verified_value: currentValue,
              action: editedValues[key] !== undefined ? 'corrected' : 'confirmed'
            });
          }
        });
      });

      // Submit bulk verification
      const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';
      const response = await fetch(`${API_URL}/api/bulk/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ verifications })
      });

      if (!response.ok) {
        throw new Error('Bulk verification failed');
      }

      // Navigate to documents view
      navigate('/documents');
    } catch (err) {
      console.error('Failed to save verifications:', err);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Loading...</div>
      </div>
    );
  }

  if (!schema || documents.length === 0) {
    return (
      <div className="max-w-6xl mx-auto p-6">
        <div className="text-center text-gray-500">No documents found</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-semibold text-gray-900 mb-1">Review Extractions</h1>
          <p className="text-sm text-gray-500">
            Review and confirm extracted data from {documents.length} documents
          </p>
        </div>

        {/* Table */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden mb-4">
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider bg-gray-50 sticky left-0 z-10">
                    Document
                  </th>
                  {schema.fields.map(field => (
                    <th
                      key={field.name}
                      className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider bg-gray-50 min-w-[200px]"
                    >
                      {field.name.replace(/_/g, ' ')}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {documents.map(doc => (
                  <tr key={doc.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-6 py-4 text-sm font-medium text-gray-900 bg-white sticky left-0 z-10 border-r border-gray-100">
                      <div className="max-w-[200px] truncate" title={doc.filename}>
                        {doc.filename}
                      </div>
                    </td>
                    {schema.fields.map(field => {
                      const confidence = getFieldConfidence(doc, field.name);
                      const value = getFieldValue(doc, field.name);
                      const bgColor = getConfidenceColor(confidence);

                      return (
                        <td
                          key={`${doc.id}_${field.name}`}
                          className={`px-6 py-4 text-sm ${bgColor} transition-colors`}
                        >
                          <div className="flex items-center gap-3">
                            <input
                              type="text"
                              value={value}
                              onChange={(e) => handleCellEdit(doc.id, field.name, e.target.value)}
                              className="flex-1 px-3 py-1.5 bg-white border border-gray-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-periwinkle-500 focus:border-transparent"
                              placeholder="Enter value..."
                            />
                            {confidence !== undefined && (
                              <span className={`text-xs font-medium px-2 py-1 rounded ${
                                confidence >= 0.8
                                  ? 'bg-mint-100 text-mint-700'
                                  : confidence >= 0.6
                                  ? 'bg-yellow-100 text-yellow-700'
                                  : 'bg-coral-100 text-coral-700'
                              }`}>
                                {Math.round(confidence * 100)}%
                              </span>
                            )}
                          </div>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Legend */}
        <div className="flex items-center gap-6 text-sm text-gray-600 mb-6">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-mint-50 border border-mint-200 rounded"></div>
            <span>High Confidence (≥80%)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-yellow-50 border border-yellow-200 rounded"></div>
            <span>Medium Confidence (60-80%)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-coral-50 border border-coral-200 rounded"></div>
            <span>Low Confidence (&lt;60%)</span>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-3 mb-6">
          <button
            onClick={handleConfirmAll}
            disabled={saving}
            className="flex-1 bg-periwinkle-500 text-white py-3 px-6 rounded-lg font-medium hover:bg-periwinkle-600 focus:outline-none focus:ring-2 focus:ring-periwinkle-500 focus:ring-offset-2 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
          >
            {saving ? 'Saving...' : 'Confirm All & Continue'}
          </button>
          <button
            onClick={() => navigate('/documents')}
            className="px-8 bg-white border border-gray-300 py-3 rounded-lg font-medium hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 transition-colors"
          >
            Cancel
          </button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
            <div className="text-3xl font-bold text-gray-900">
              {documents.reduce((sum, doc) => {
                return sum + (doc.extracted_fields?.filter(f => f.confidence_score >= 0.8).length || 0);
              }, 0)}
            </div>
            <div className="text-sm text-gray-600 mt-1">High Confidence Fields</div>
          </div>
          <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
            <div className="text-3xl font-bold text-gray-900">
              {documents.reduce((sum, doc) => {
                return sum + (doc.extracted_fields?.filter(f => f.confidence_score >= 0.6 && f.confidence_score < 0.8).length || 0);
              }, 0)}
            </div>
            <div className="text-sm text-gray-600 mt-1">Medium Confidence Fields</div>
          </div>
          <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
            <div className="text-3xl font-bold text-gray-900">
              {documents.reduce((sum, doc) => {
                return sum + (doc.extracted_fields?.filter(f => f.confidence_score < 0.6).length || 0);
              }, 0)}
            </div>
            <div className="text-sm text-gray-600 mt-1">Low Confidence Fields</div>
          </div>
        </div>
      </div>
    </div>
  );
}
