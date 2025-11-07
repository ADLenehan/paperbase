import { useState } from 'react';
import PropTypes from 'prop-types';
import ComplexFieldDisplay from './ComplexFieldDisplay';
import ArrayEditor from './ArrayEditor';
import TableEditor from './TableEditor';
import ArrayOfObjectsEditor from './ArrayOfObjectsEditor';

/**
 * Reusable table view for bulk field verification
 *
 * Extracted from BulkConfirmation.jsx for use in:
 * - BulkConfirmation page (original use case)
 * - Audit page table mode (new integrated view)
 *
 * Features:
 * - Documents (rows) × Fields (columns) grid
 * - Inline editing with real-time updates (supports complex types)
 * - Confidence-based color coding
 * - Batch verification support
 * - Statistics summary
 * - Complex data type support (arrays, tables, array_of_objects)
 */
export default function AuditTableView({
  documents,
  schema,
  onVerify,
  isVerifying = false,
  showActions = true,
  onCancel
}) {
  const [editedValues, setEditedValues] = useState({});
  const [editingComplexField, setEditingComplexField] = useState(null); // { docId, fieldName, type }

  const handleCellEdit = (docId, fieldName, value) => {
    setEditedValues(prev => ({
      ...prev,
      [`${docId}_${fieldName}`]: value
    }));
  };

  const getField = (doc, fieldName) => {
    return doc.extracted_fields?.find(f => f.field_name === fieldName);
  };

  const getFieldValue = (doc, fieldName) => {
    const key = `${doc.id}_${fieldName}`;
    if (editedValues[key] !== undefined) {
      return editedValues[key];
    }

    const field = getField(doc, fieldName);
    // Return the appropriate value based on field type
    const fieldType = field?.field_type || 'text';
    if (fieldType === 'array' || fieldType === 'table' || fieldType === 'array_of_objects') {
      return field?.field_value_json;
    }
    return field?.field_value || '';
  };

  const getFieldConfidence = (doc, fieldName) => {
    const field = getField(doc, fieldName);
    return field?.confidence_score;
  };

  const getFieldId = (doc, fieldName) => {
    const field = getField(doc, fieldName);
    return field?.id;
  };

  const getFieldType = (doc, fieldName) => {
    const field = getField(doc, fieldName);
    return field?.field_type || 'text';
  };

  const isComplexType = (fieldType) => {
    return ['array', 'table', 'array_of_objects'].includes(fieldType);
  };

  const getConfidenceColor = (confidence) => {
    if (!confidence) return 'bg-gray-50';
    if (confidence >= 0.8) return 'bg-green-50';
    if (confidence >= 0.6) return 'bg-yellow-50';
    return 'bg-red-50';
  };

  const handleConfirmAll = () => {
    const verifications = [];

    // Build verification data for new bulk-verify endpoint
    documents.forEach(doc => {
      schema.fields.forEach(field => {
        const key = `${doc.id}_${field.name}`;
        const originalField = doc.extracted_fields?.find(f => f.field_name === field.name);
        const currentValue = editedValues[key] !== undefined ? editedValues[key] : originalField?.field_value;

        if (originalField) {
          // Determine action based on whether value was edited
          const wasEdited = editedValues[key] !== undefined && editedValues[key] !== originalField.field_value;

          verifications.push({
            field_id: originalField.id,
            action: wasEdited ? 'incorrect' : 'correct',
            corrected_value: wasEdited ? currentValue : null,
            notes: wasEdited ? 'Corrected in bulk table view' : null
          });
        }
      });
    });

    onVerify(verifications);
  };

  // Calculate statistics
  const stats = {
    high: 0,
    medium: 0,
    low: 0
  };

  documents.forEach(doc => {
    doc.extracted_fields?.forEach(field => {
      const conf = field.confidence_score;
      if (conf >= 0.8) stats.high++;
      else if (conf >= 0.6) stats.medium++;
      else stats.low++;
    });
  });

  if (!schema || documents.length === 0) {
    return (
      <div className="text-center py-12 text-gray-500">
        No documents to review
      </div>
    );
  }

  // Render complex field editor modal
  const renderComplexEditorModal = () => {
    if (!editingComplexField) return null;

    const { docId, fieldName, type } = editingComplexField;
    const doc = documents.find(d => d.id === docId);
    if (!doc) return null;

    const currentValue = getFieldValue(doc, fieldName);

    const handleSave = (newValue) => {
      handleCellEdit(docId, fieldName, newValue);
      setEditingComplexField(null);
    };

    const handleCancel = () => {
      setEditingComplexField(null);
    };

    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
        <div className="bg-white rounded-lg shadow-xl max-w-3xl w-full max-h-[90vh] overflow-y-auto">
          <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
            <h3 className="text-lg font-semibold text-gray-900">
              Edit {fieldName.replace(/_/g, ' ')}
            </h3>
            <button
              onClick={handleCancel}
              className="text-gray-400 hover:text-gray-600 transition-colors"
            >
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div className="p-6">
            {type === 'array' && (
              <ArrayEditor
                value={currentValue || []}
                onChange={handleSave}
              />
            )}
            {type === 'table' && (
              <TableEditor
                value={currentValue || { headers: [], rows: [] }}
                onChange={handleSave}
              />
            )}
            {type === 'array_of_objects' && (
              <ArrayOfObjectsEditor
                value={currentValue || []}
                onChange={handleSave}
              />
            )}
          </div>

          <div className="sticky bottom-0 bg-gray-50 border-t border-gray-200 px-6 py-4 flex justify-end gap-3">
            <button
              onClick={handleCancel}
              className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-100 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleCancel}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              Done
            </button>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-4">
      {/* Complex Field Editor Modal */}
      {renderComplexEditorModal()}

      {/* Table */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
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
                    <div className="flex flex-col">
                      <span>{field.name.replace(/_/g, ' ')}</span>
                      {field.description && (
                        <span className="text-xs text-gray-400 font-normal normal-case mt-0.5">
                          {field.description}
                        </span>
                      )}
                    </div>
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
                    const fieldId = getFieldId(doc, field.name);
                    const fieldType = getFieldType(doc, field.name);
                    const fieldObj = getField(doc, field.name);

                    return (
                      <td
                        key={`${doc.id}_${field.name}`}
                        className={`px-6 py-4 text-sm ${bgColor} transition-colors`}
                      >
                        <div className="flex items-center gap-3">
                          {isComplexType(fieldType) ? (
                            // Complex types: Show display component with edit button
                            <div className="flex-1 flex items-center gap-2">
                              <div className="flex-1 min-w-0">
                                <ComplexFieldDisplay
                                  field={fieldObj}
                                  mode="compact"
                                />
                              </div>
                              <button
                                onClick={() => setEditingComplexField({ docId: doc.id, fieldName: field.name, type: fieldType })}
                                className="flex-shrink-0 p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors"
                                title="Edit"
                                disabled={!fieldId}
                              >
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                                </svg>
                              </button>
                            </div>
                          ) : (
                            // Simple types: Show inline text input
                            <input
                              type="text"
                              value={value}
                              onChange={(e) => handleCellEdit(doc.id, field.name, e.target.value)}
                              className="flex-1 px-3 py-1.5 bg-white border border-gray-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                              placeholder="Enter value..."
                              disabled={!fieldId}
                            />
                          )}
                          {confidence !== undefined && (
                            <span className={`text-xs font-medium px-2 py-1 rounded whitespace-nowrap ${
                              confidence >= 0.8
                                ? 'bg-green-100 text-green-700'
                                : confidence >= 0.6
                                ? 'bg-yellow-100 text-yellow-700'
                                : 'bg-red-100 text-red-700'
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
      <div className="flex items-center gap-6 text-sm text-gray-600">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 bg-green-50 border border-green-200 rounded"></div>
          <span>High Confidence (≥80%)</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 bg-yellow-50 border border-yellow-200 rounded"></div>
          <span>Medium Confidence (60-80%)</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 bg-red-50 border border-red-200 rounded"></div>
          <span>Low Confidence (&lt;60%)</span>
        </div>
      </div>

      {/* Actions */}
      {showActions && (
        <div className="flex gap-3">
          <button
            onClick={handleConfirmAll}
            disabled={isVerifying}
            className="flex-1 bg-blue-600 text-white py-3 px-6 rounded-lg font-medium hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
          >
            {isVerifying ? 'Saving...' : 'Confirm All & Continue'}
          </button>
          {onCancel && (
            <button
              onClick={onCancel}
              disabled={isVerifying}
              className="px-8 bg-white border border-gray-300 py-3 rounded-lg font-medium hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Cancel
            </button>
          )}
        </div>
      )}

      {/* Statistics */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
          <div className="text-3xl font-bold text-green-600">
            {stats.high}
          </div>
          <div className="text-sm text-gray-600 mt-1">High Confidence Fields</div>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
          <div className="text-3xl font-bold text-yellow-600">
            {stats.medium}
          </div>
          <div className="text-sm text-gray-600 mt-1">Medium Confidence Fields</div>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
          <div className="text-3xl font-bold text-red-600">
            {stats.low}
          </div>
          <div className="text-sm text-gray-600 mt-1">Low Confidence Fields</div>
        </div>
      </div>
    </div>
  );
}

AuditTableView.propTypes = {
  documents: PropTypes.arrayOf(PropTypes.shape({
    id: PropTypes.number.isRequired,
    filename: PropTypes.string.isRequired,
    extracted_fields: PropTypes.arrayOf(PropTypes.shape({
      id: PropTypes.number.isRequired,
      field_name: PropTypes.string.isRequired,
      field_value: PropTypes.string,
      confidence_score: PropTypes.number
    }))
  })).isRequired,
  schema: PropTypes.shape({
    fields: PropTypes.arrayOf(PropTypes.shape({
      name: PropTypes.string.isRequired,
      description: PropTypes.string
    })).isRequired
  }).isRequired,
  onVerify: PropTypes.func.isRequired,
  isVerifying: PropTypes.bool,
  showActions: PropTypes.bool,
  onCancel: PropTypes.func
};
