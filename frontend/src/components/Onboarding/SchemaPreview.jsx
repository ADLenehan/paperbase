import { useState } from 'react'

function SchemaPreview({ schema, onConfirm, onEdit }) {
  const [editingField, setEditingField] = useState(null)

  const getConfidenceColor = (threshold) => {
    if (threshold >= 0.8) return 'text-green-700 bg-green-100'
    if (threshold >= 0.6) return 'text-yellow-700 bg-yellow-100'
    return 'text-red-700 bg-red-100'
  }

  return (
    <div className="space-y-6">
      {/* Schema Header */}
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">
          {schema.name}
        </h2>
        <p className="text-gray-600">
          Found {schema.fields.length} fields in your documents
        </p>
      </div>

      {/* Fields List */}
      <div className="space-y-3">
        <h3 className="text-lg font-semibold text-gray-900">
          Extraction Fields
        </h3>

        {schema.fields.map((field, index) => (
          <div
            key={index}
            className="bg-white border border-gray-200 rounded-lg p-4 hover:border-gray-300 transition-colors"
          >
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <h4 className="text-lg font-medium text-gray-900">
                    {field.name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                  </h4>
                  {field.required && (
                    <span className="text-xs bg-red-100 text-red-700 px-2 py-1 rounded">
                      Required
                    </span>
                  )}
                </div>

                <p className="text-sm text-gray-600 mb-3">
                  {field.description}
                </p>

                <div className="flex items-center gap-4 text-sm">
                  <div className="flex items-center gap-1">
                    <span className="text-gray-500">Type:</span>
                    <span className="font-medium text-gray-900 capitalize">
                      {field.type}
                    </span>
                  </div>

                  <div className="flex items-center gap-1">
                    <span className="text-gray-500">Confidence:</span>
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${getConfidenceColor(field.confidence_threshold)}`}>
                      {(field.confidence_threshold * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>

                {field.extraction_hints && field.extraction_hints.length > 0 && (
                  <div className="mt-3">
                    <span className="text-xs text-gray-500">Extraction hints:</span>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {field.extraction_hints.map((hint, hintIndex) => (
                        <span
                          key={hintIndex}
                          className="text-xs bg-gray-100 text-gray-700 px-2 py-1 rounded"
                        >
                          "{hint}"
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <button
                onClick={() => onEdit?.(field, index)}
                className="ml-4 text-sm text-blue-600 hover:text-blue-800"
              >
                Edit
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Action Buttons */}
      <div className="flex gap-3 pt-4">
        <button
          onClick={onEdit}
          className="flex-1 bg-white border-2 border-gray-300 text-gray-700 py-3 px-4 rounded-lg font-medium hover:bg-gray-50 transition-all hover:border-blue-500 flex items-center justify-center gap-2"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
          </svg>
          Edit Schema
        </button>
        <button
          onClick={() => onConfirm?.(schema)}
          className="flex-1 bg-blue-600 text-white py-3 px-4 rounded-lg font-medium hover:bg-blue-700 transition-colors shadow-sm flex items-center justify-center gap-2"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          Confirm & Continue
        </button>
      </div>

      {/* Help Text */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <div className="flex">
          <div className="flex-shrink-0">
            <svg className="h-5 w-5 text-blue-400" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
            </svg>
          </div>
          <div className="ml-3">
            <h3 className="text-sm font-medium text-blue-800">
              Review Your Schema
            </h3>
            <div className="mt-2 text-sm text-blue-700">
              <p>
                This schema was automatically generated from your sample documents.
                You can edit field names, types, and extraction hints before confirming.
                Fields with lower confidence thresholds will be flagged for human review during processing.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default SchemaPreview
