import { useState } from 'react'
import apiClient from '../../api/client'

function SchemaBuilder({ schema, onSave, onCancel }) {
  const [fields, setFields] = useState(schema?.fields || [])
  const [schemaName, setSchemaName] = useState(schema?.name || 'Untitled Schema')
  const [draggedIndex, setDraggedIndex] = useState(null)
  const [showPromptInput, setShowPromptInput] = useState(false)
  const [promptText, setPromptText] = useState('')
  const [isProcessingPrompt, setIsProcessingPrompt] = useState(false)
  const [promptError, setPromptError] = useState(null)
  const [isSaving, setIsSaving] = useState(false)

  const fieldTypes = [
    { value: 'text', label: 'Text', icon: '📝' },
    { value: 'number', label: 'Number', icon: '🔢' },
    { value: 'date', label: 'Date', icon: '📅' },
    { value: 'boolean', label: 'Boolean', icon: '☑️' },
    { value: 'array', label: 'Array', icon: '📋' },
    { value: 'object', label: 'Object', icon: '{}' }
  ]

  const addField = (parentPath = null) => {
    const newField = {
      name: '',
      type: 'text',
      description: '',
      required: false,
      confidence_threshold: 0.8,
      extraction_hints: []
    }

    if (parentPath === null) {
      setFields([...fields, newField])
    } else {
      // Add to nested array
      const updatedFields = [...fields]
      const pathParts = parentPath.split('.')
      let target = updatedFields

      for (let i = 0; i < pathParts.length - 1; i++) {
        target = target[parseInt(pathParts[i])]
      }

      const fieldIndex = parseInt(pathParts[pathParts.length - 1])
      if (!target[fieldIndex].array_items) {
        target[fieldIndex].array_items = []
      }
      target[fieldIndex].array_items.push(newField)
      setFields(updatedFields)
    }
  }

  const updateField = (index, key, value, parentPath = null) => {
    const updatedFields = [...fields]

    if (parentPath === null) {
      updatedFields[index][key] = value

      // If changing to array type, initialize array_items
      if (key === 'type' && value === 'array' && !updatedFields[index].array_items) {
        updatedFields[index].array_items = []
      }
      // If changing to object type, initialize object_fields
      if (key === 'type' && value === 'object' && !updatedFields[index].object_fields) {
        updatedFields[index].object_fields = []
      }
    } else {
      const pathParts = parentPath.split('.')
      let target = updatedFields

      for (const part of pathParts) {
        target = target[parseInt(part)]
      }

      target.array_items[index][key] = value
    }

    setFields(updatedFields)
  }

  const removeField = (index, parentPath = null) => {
    if (parentPath === null) {
      setFields(fields.filter((_, i) => i !== index))
    } else {
      const updatedFields = [...fields]
      const pathParts = parentPath.split('.')
      let target = updatedFields

      for (const part of pathParts) {
        target = target[parseInt(part)]
      }

      target.array_items = target.array_items.filter((_, i) => i !== index)
      setFields(updatedFields)
    }
  }

  const handleDragStart = (e, index) => {
    setDraggedIndex(index)
    e.dataTransfer.effectAllowed = 'move'
  }

  const handleDragOver = (e, index) => {
    e.preventDefault()
    if (draggedIndex === null || draggedIndex === index) return

    const updatedFields = [...fields]
    const draggedField = updatedFields[draggedIndex]
    updatedFields.splice(draggedIndex, 1)
    updatedFields.splice(index, 0, draggedField)

    setFields(updatedFields)
    setDraggedIndex(index)
  }

  const handleDragEnd = () => {
    setDraggedIndex(null)
  }

  const handlePromptSubmit = async () => {
    if (!promptText.trim()) return

    setIsProcessingPrompt(true)
    setPromptError(null)

    try {
      const response = await apiClient.post(`/api/onboarding/schemas/${schema.id}/modify-with-prompt`, {
        prompt: promptText,
        current_fields: fields
      })

      if (response.data.fields) {
        setFields(response.data.fields)
        setPromptText('')
        setShowPromptInput(false)
      }
    } catch (error) {
      setPromptError(error.response?.data?.detail || 'Failed to process prompt')
    } finally {
      setIsProcessingPrompt(false)
    }
  }

  const handleSave = async () => {
    setIsSaving(true)
    try {
      if (schema.id) {
        // Update existing schema
        await apiClient.put(`/api/onboarding/schemas/${schema.id}`, {
          name: schemaName,
          fields: fields
        })
      }

      const updatedSchema = {
        ...schema,
        name: schemaName,
        fields: fields
      }
      onSave(updatedSchema)
    } catch (error) {
      alert('Failed to save schema: ' + (error.response?.data?.detail || error.message))
    } finally {
      setIsSaving(false)
    }
  }

  const handleImport = () => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = 'application/json'
    input.onchange = (e) => {
      const file = e.target.files[0]
      const reader = new FileReader()
      reader.onload = (event) => {
        try {
          const imported = JSON.parse(event.target.result)
          if (imported.fields) {
            setFields(imported.fields)
            if (imported.name) setSchemaName(imported.name)
          }
        } catch (error) {
          alert('Invalid schema file')
        }
      }
      reader.readAsText(file)
    }
    input.click()
  }

  const handleExport = () => {
    const schemaData = {
      name: schemaName,
      fields: fields
    }
    const blob = new Blob([JSON.stringify(schemaData, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${schemaName.replace(/\s+/g, '_').toLowerCase()}_schema.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleCopy = async () => {
    const schemaData = {
      name: schemaName,
      fields: fields
    }
    try {
      await navigator.clipboard.writeText(JSON.stringify(schemaData, null, 2))
      // Show success feedback
      const btn = event.target.closest('button')
      const originalText = btn.innerHTML
      btn.innerHTML = '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg><span class="ml-2">Copied!</span>'
      setTimeout(() => {
        btn.innerHTML = originalText
      }, 2000)
    } catch {
      alert('Failed to copy schema')
    }
  }

  const renderField = (field, index, parentPath = null) => {
    const isArray = field.type === 'array'
    const isObject = field.type === 'object'

    return (
      <div key={`${parentPath || ''}.${index}`} className="mb-3">
        <div
          draggable={parentPath === null}
          onDragStart={(e) => parentPath === null && handleDragStart(e, index)}
          onDragOver={(e) => parentPath === null && handleDragOver(e, index)}
          onDragEnd={handleDragEnd}
          className={`bg-white border rounded-lg p-4 transition-all ${
            draggedIndex === index ? 'opacity-50 border-blue-400' : 'border-gray-200 hover:border-gray-300'
          } ${parentPath === null ? 'cursor-move' : ''}`}
        >
          <div className="grid grid-cols-12 gap-3 items-start">
            {/* Drag Handle */}
            {parentPath === null && (
              <div className="col-span-1 flex items-center justify-center pt-2">
                <svg className="w-4 h-4 text-gray-400" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M7 2a2 2 0 1 0 .001 4.001A2 2 0 0 0 7 2zm0 6a2 2 0 1 0 .001 4.001A2 2 0 0 0 7 8zm0 6a2 2 0 1 0 .001 4.001A2 2 0 0 0 7 14zm6-8a2 2 0 1 0-.001-4.001A2 2 0 0 0 13 6zm0 2a2 2 0 1 0 .001 4.001A2 2 0 0 0 13 8zm0 6a2 2 0 1 0 .001 4.001A2 2 0 0 0 13 14z" />
                </svg>
              </div>
            )}

            {/* Field Name */}
            <div className={parentPath === null ? "col-span-3" : "col-span-4"}>
              <label className="block text-xs font-medium text-gray-700 mb-1">Name</label>
              <input
                type="text"
                value={field.name}
                onChange={(e) => updateField(index, 'name', e.target.value, parentPath)}
                placeholder="field_name"
                className="w-full h-11 px-3 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>

            {/* Field Type */}
            <div className="col-span-2">
              <label className="block text-xs font-medium text-gray-700 mb-1">Type</label>
              <select
                value={field.type}
                onChange={(e) => updateField(index, 'type', e.target.value, parentPath)}
                className="w-full h-11 px-3 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                {fieldTypes.map((type) => (
                  <option key={type.value} value={type.value}>
                    {type.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Description */}
            <div className="col-span-4">
              <label className="block text-xs font-medium text-gray-700 mb-1">Description</label>
              <input
                type="text"
                value={field.description}
                onChange={(e) => updateField(index, 'description', e.target.value, parentPath)}
                placeholder="Field description"
                className="w-full h-11 px-3 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>

            {/* Required Checkbox */}
            <div className="col-span-1 flex items-center justify-center pt-6">
              <input
                type="checkbox"
                checked={field.required || false}
                onChange={(e) => updateField(index, 'required', e.target.checked, parentPath)}
                className="h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                title="Required"
              />
            </div>

            {/* Remove Button */}
            <div className="col-span-1 flex items-center justify-center pt-6">
              <button
                onClick={() => removeField(index, parentPath)}
                className="text-red-600 hover:text-red-800 transition-colors"
                title="Remove field"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            </div>
          </div>

          {/* Additional Settings Row */}
          <div className="grid grid-cols-12 gap-3 mt-3">
            <div className={parentPath === null ? "col-span-4 col-start-2" : "col-span-5"}>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Confidence Threshold
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={field.confidence_threshold || 0.8}
                  onChange={(e) => updateField(index, 'confidence_threshold', parseFloat(e.target.value), parentPath)}
                  className="flex-1"
                />
                <span className="text-sm text-gray-600 w-12 font-medium">
                  {((field.confidence_threshold || 0.8) * 100).toFixed(0)}%
                </span>
              </div>
            </div>

            <div className="col-span-7">
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Extraction Hints (comma-separated)
              </label>
              <input
                type="text"
                value={field.extraction_hints?.join(', ') || ''}
                onChange={(e) => {
                  const hints = e.target.value.split(',').map(h => h.trim()).filter(h => h)
                  updateField(index, 'extraction_hints', hints, parentPath)
                }}
                placeholder="total, amount due, balance"
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
          </div>
        </div>

        {/* Nested Array Items */}
        {isArray && (
          <div className="ml-8 mt-3 border-l-2 border-blue-200 pl-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-gray-700">↳ Array Items</span>
            </div>

            {field.array_items?.map((item, itemIndex) =>
              renderField(item, itemIndex, `${index}`)
            )}

            <button
              onClick={() => addField(`${index}`)}
              className="mt-2 flex items-center gap-2 text-sm text-blue-600 hover:text-blue-800 transition-colors"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Add Array Item Field
            </button>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          <label className="block text-sm font-medium text-gray-700 mb-2">Schema Name</label>
          <input
            type="text"
            value={schemaName}
            onChange={(e) => setSchemaName(e.target.value)}
            className="w-full max-w-md px-4 py-2 border border-gray-300 rounded-lg text-lg font-semibold focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
          <p className="mt-1 text-sm text-gray-500">
            {fields.length} {fields.length === 1 ? 'field' : 'fields'} defined
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex gap-2">
          <button
            onClick={handleImport}
            className="px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors flex items-center gap-2"
            title="Import schema from JSON"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
            </svg>
            Import
          </button>
          <button
            onClick={handleExport}
            className="px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
            title="Export schema as JSON"
          >
            Export
          </button>
          <button
            onClick={handleCopy}
            className="px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors flex items-center gap-2"
            title="Copy schema to clipboard"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
            Copy
          </button>
        </div>
      </div>

      {/* AI Prompt Editor */}
      <div className="bg-gradient-to-r from-purple-50 to-blue-50 border border-purple-200 rounded-lg p-4">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            <h3 className="text-sm font-semibold text-gray-900">AI Schema Editor</h3>
          </div>
          <button
            onClick={() => setShowPromptInput(!showPromptInput)}
            className="text-sm text-purple-600 hover:text-purple-800 font-medium transition-colors"
          >
            {showPromptInput ? 'Hide' : 'Show'}
          </button>
        </div>

        {showPromptInput && (
          <div className="mt-3 space-y-3">
            <textarea
              value={promptText}
              onChange={(e) => setPromptText(e.target.value)}
              placeholder="Describe the changes you want to make... (e.g., 'Add a field for customer email address' or 'Change invoice_date to a date type')"
              className="w-full px-3 py-2 border border-purple-300 rounded-lg text-sm focus:ring-2 focus:ring-purple-500 focus:border-purple-500 resize-none"
              rows={3}
              disabled={isProcessingPrompt}
            />

            {promptError && (
              <div className="bg-red-50 border border-red-200 rounded-md p-3 text-sm text-red-700">
                {promptError}
              </div>
            )}

            <div className="flex gap-2">
              <button
                onClick={handlePromptSubmit}
                disabled={!promptText.trim() || isProcessingPrompt}
                className="flex-1 bg-purple-600 text-white py-2 px-4 rounded-lg font-medium hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
              >
                {isProcessingPrompt ? (
                  <>
                    <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Processing...
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                    Apply Changes
                  </>
                )}
              </button>
              <button
                onClick={() => {
                  setPromptText('')
                  setPromptError(null)
                }}
                className="px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
              >
                Clear
              </button>
            </div>
          </div>
        )}

        {!showPromptInput && (
          <p className="text-sm text-gray-600">
            Use AI to modify your schema with natural language
          </p>
        )}
      </div>

      {/* Fields Table */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-900">Schema Fields</h3>
          <span className="text-xs text-gray-500">Define the fields to extract from documents</span>
        </div>

        <div className="grid grid-cols-12 gap-3 px-4 py-2 bg-gray-50 rounded-lg text-xs font-medium text-gray-700 border border-gray-200">
          <div className="col-span-1"></div>
          <div className="col-span-3">Name</div>
          <div className="col-span-2">Type</div>
          <div className="col-span-4">Description</div>
          <div className="col-span-1 text-center">Req.</div>
          <div className="col-span-1"></div>
        </div>

        {fields.length === 0 ? (
          <div className="text-center py-16 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
            <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <p className="mt-4 text-gray-500 font-medium">No fields defined yet</p>
            <p className="mt-1 text-sm text-gray-400">Add your first field or use AI prompt to generate fields</p>
            <button
              onClick={() => addField()}
              className="mt-6 inline-flex items-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium transition-colors shadow-sm"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Add First Field
            </button>
          </div>
        ) : (
          <>
            {fields.map((field, index) => renderField(field, index))}

            <button
              onClick={() => addField()}
              className="w-full py-3 border-2 border-dashed border-gray-300 rounded-lg text-sm text-gray-600 hover:border-blue-500 hover:text-blue-600 hover:bg-blue-50 flex items-center justify-center gap-2 transition-all"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Add Field
            </button>
          </>
        )}
      </div>

      {/* Action Buttons */}
      <div className="flex gap-3 pt-6 border-t-2 border-gray-200">
        <button
          onClick={onCancel}
          disabled={isSaving}
          className="flex-1 bg-white border-2 border-gray-300 text-gray-700 py-3 px-4 rounded-lg font-medium hover:bg-gray-50 disabled:opacity-50 transition-colors"
        >
          Cancel
        </button>
        <button
          onClick={handleSave}
          disabled={isSaving || fields.length === 0}
          className="flex-1 bg-blue-600 text-white py-3 px-4 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2 shadow-sm"
        >
          {isSaving ? (
            <>
              <svg className="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              Saving...
            </>
          ) : (
            <>
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              Save Schema
            </>
          )}
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
            <h3 className="text-sm font-medium text-blue-800">Schema Builder Tips</h3>
            <div className="mt-2 text-sm text-blue-700">
              <ul className="list-disc list-inside space-y-1">
                <li>Drag fields with the handle to reorder them</li>
                <li>Use <strong>array</strong> type for lists of items (e.g., line items in invoices)</li>
                <li>Lower confidence thresholds will trigger human review during processing</li>
                <li>Add extraction hints to help Reducto locate fields (e.g., "total", "due date")</li>
                <li>Try the AI editor to modify fields with natural language prompts</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default SchemaBuilder
