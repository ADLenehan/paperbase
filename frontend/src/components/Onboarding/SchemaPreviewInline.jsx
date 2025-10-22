import { useState } from 'react'
import apiClient from '../../api/client'

function SchemaPreviewInline({ schema, onConfirm, onSchemaUpdate, isFromTemplate = false }) {
  const [fields, setFields] = useState(schema?.fields || [])
  const [editingFieldIndex, setEditingFieldIndex] = useState(null)
  const [promptText, setPromptText] = useState('')
  const [isProcessingPrompt, setIsProcessingPrompt] = useState(false)
  const [promptError, setPromptError] = useState(null)

  const getConfidenceColor = (threshold) => {
    if (threshold >= 0.8) return 'text-green-700 bg-green-100 border-green-200'
    if (threshold >= 0.6) return 'text-yellow-700 bg-yellow-100 border-yellow-200'
    return 'text-red-700 bg-red-100 border-red-200'
  }

  const handleFieldPromptSubmit = async (fieldIndex) => {
    if (!promptText.trim()) return

    setIsProcessingPrompt(true)
    setPromptError(null)

    try {
      const response = await apiClient.post(`/api/onboarding/schemas/${schema.id}/modify-with-prompt`, {
        prompt: `For the field "${fields[fieldIndex].name}": ${promptText}`,
        current_fields: fields
      })

      if (response.data.fields) {
        setFields(response.data.fields)
        onSchemaUpdate?.({ ...schema, fields: response.data.fields })
        setPromptText('')
        setEditingFieldIndex(null)
      }
    } catch (error) {
      setPromptError(error.response?.data?.detail || 'Failed to process prompt')
    } finally {
      setIsProcessingPrompt(false)
    }
  }

  const handleRemoveField = async (fieldIndex) => {
    const fieldName = fields[fieldIndex].name
    const updatedFields = fields.filter((_, i) => i !== fieldIndex)
    setFields(updatedFields)
    onSchemaUpdate?.({ ...schema, fields: updatedFields })
  }

  const toggleFieldEdit = (index) => {
    if (editingFieldIndex === index) {
      setEditingFieldIndex(null)
      setPromptText('')
      setPromptError(null)
    } else {
      setEditingFieldIndex(index)
      setPromptText('')
      setPromptError(null)
    }
  }

  return (
    <div className="space-y-6">
      {/* Schema Header */}
      <div className="bg-gradient-to-r from-blue-50 to-purple-50 border border-blue-200 rounded-lg p-6">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">
              {schema.name}
            </h2>
            <p className="text-gray-600">
              {isFromTemplate ? (
                <>
                  Template loaded with <strong>{fields.length} fields</strong>.
                  Review and customize below.
                </>
              ) : (
                <>
                  AI found <strong>{fields.length} fields</strong> in your documents.
                  Click any field to edit with AI.
                </>
              )}
            </p>
          </div>
          {isFromTemplate && (
            <span className="inline-flex items-center gap-2 px-3 py-1 bg-purple-100 text-purple-700 rounded-full text-sm font-medium border border-purple-200">
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z" />
              </svg>
              From Template
            </span>
          )}
        </div>
      </div>

      {/* Fields List with Inline Editing */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-gray-900">
            Extraction Fields
          </h3>
          <span className="text-sm text-gray-500">
            Click <strong>✨ AI Edit</strong> to modify any field
          </span>
        </div>

        {fields.map((field, index) => (
          <div
            key={index}
            className={`bg-white border rounded-lg transition-all ${
              editingFieldIndex === index
                ? 'border-purple-300 shadow-md'
                : 'border-gray-200 hover:border-gray-300'
            }`}
          >
            {/* Field Card */}
            <div className="p-4">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <h4 className="text-lg font-medium text-gray-900">
                      {field.name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                    </h4>
                    {field.required && (
                      <span className="text-xs bg-red-100 text-red-700 px-2 py-1 rounded border border-red-200">
                        Required
                      </span>
                    )}
                    <span className={`text-xs px-2 py-1 rounded border font-medium ${getConfidenceColor(field.confidence_threshold)}`}>
                      {(field.confidence_threshold * 100).toFixed(0)}% confidence
                    </span>
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

                    {field.extraction_hints && field.extraction_hints.length > 0 && (
                      <div className="flex items-center gap-1">
                        <span className="text-gray-500">Hints:</span>
                        <div className="flex flex-wrap gap-1">
                          {field.extraction_hints.slice(0, 3).map((hint, hintIndex) => (
                            <span
                              key={hintIndex}
                              className="text-xs bg-gray-100 text-gray-700 px-2 py-0.5 rounded"
                            >
                              "{hint}"
                            </span>
                          ))}
                          {field.extraction_hints.length > 3 && (
                            <span className="text-xs text-gray-500">
                              +{field.extraction_hints.length - 3} more
                            </span>
                          )}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Array Items Preview */}
                  {field.type === 'array' && field.array_items?.length > 0 && (
                    <div className="mt-3 pl-4 border-l-2 border-gray-200">
                      <span className="text-xs text-gray-500 font-medium">
                        Array contains {field.array_items.length} nested {field.array_items.length === 1 ? 'field' : 'fields'}
                      </span>
                    </div>
                  )}
                </div>

                {/* Action Buttons */}
                <div className="flex items-center gap-2 ml-4">
                  <button
                    onClick={() => toggleFieldEdit(index)}
                    className={`flex items-center gap-1 px-3 py-1.5 rounded-lg font-medium text-sm transition-colors ${
                      editingFieldIndex === index
                        ? 'bg-purple-100 text-purple-700 border border-purple-300'
                        : 'bg-purple-50 text-purple-600 hover:bg-purple-100 border border-purple-200'
                    }`}
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                    {editingFieldIndex === index ? 'Close' : 'AI Edit'}
                  </button>
                  <button
                    onClick={() => handleRemoveField(index)}
                    className="p-1.5 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                    title="Remove field"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              </div>
            </div>

            {/* Inline AI Prompt Input */}
            {editingFieldIndex === index && (
              <div className="border-t border-purple-200 bg-purple-50 p-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  ✨ Describe your changes for this field
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={promptText}
                    onChange={(e) => setPromptText(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && handleFieldPromptSubmit(index)}
                    placeholder='e.g., "Make this required" or "Change to date type" or "Add hint: Due Date"'
                    className="flex-1 px-3 py-2 border border-purple-300 rounded-lg text-sm focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                    disabled={isProcessingPrompt}
                  />
                  <button
                    onClick={() => handleFieldPromptSubmit(index)}
                    disabled={!promptText.trim() || isProcessingPrompt}
                    className="px-4 py-2 bg-purple-600 text-white rounded-lg font-medium hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-sm"
                  >
                    {isProcessingPrompt ? (
                      <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                    ) : (
                      'Apply'
                    )}
                  </button>
                </div>
                {promptError && (
                  <p className="mt-2 text-sm text-red-600">{promptError}</p>
                )}
                <p className="mt-2 text-xs text-gray-600">
                  Press Enter or click Apply to make changes with AI
                </p>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Action Buttons */}
      <div className="flex gap-3 pt-4 border-t-2">
        <button
          onClick={() => onConfirm?.(schema)}
          className="flex-1 bg-blue-600 text-white py-3 px-4 rounded-lg font-medium hover:bg-blue-700 transition-colors shadow-sm flex items-center justify-center gap-2"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          Looks Good - Continue
        </button>
      </div>

      {/* Help Text */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <div className="flex">
          <div className="flex-shrink-0">
            <svg className="h-5 w-5 text-blue-400" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1 a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
            </svg>
          </div>
          <div className="ml-3">
            <h3 className="text-sm font-medium text-blue-800">
              {isFromTemplate ? 'Customize Your Template' : 'Review Your Schema'}
            </h3>
            <div className="mt-2 text-sm text-blue-700">
              <p>
                {isFromTemplate ? (
                  <>
                    This schema is based on the template you selected. You can edit any field using AI prompts,
                    remove fields you don't need, or keep it as-is if it looks good.
                  </>
                ) : (
                  <>
                    This schema was automatically generated from your sample documents.
                    Click <strong>✨ AI Edit</strong> on any field to make quick changes with natural language.
                  </>
                )}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default SchemaPreviewInline
