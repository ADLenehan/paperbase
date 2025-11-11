import { useState, useEffect } from 'react';
import { X } from 'lucide-react';

/**
 * AddFieldModal - Two-step flow for adding fields to templates
 *
 * Step 1: User describes what they want to extract
 * Step 2: Review Claude's suggestion and confirm
 */
export default function AddFieldModal({ schemaId, onClose, onFieldAdded }) {
  const [step, setStep] = useState(1);
  const [description, setDescription] = useState('');
  const [loading, setLoading] = useState(false);
  const [suggestion, setSuggestion] = useState(null);
  const [extractFromExisting, setExtractFromExisting] = useState(true);
  const [error, setError] = useState(null);

  // Reset state when modal closes
  const handleClose = () => {
    setStep(1);
    setDescription('');
    setSuggestion(null);
    setError(null);
    onClose();
  };

  const handleAnalyze = async () => {
    if (!description.trim()) {
      setError('Please describe what field you want to extract');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`/api/onboarding/schemas/${schemaId}/fields/suggest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ description: description.trim() })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to analyze documents');
      }

      const data = await response.json();
      setSuggestion(data);
      setStep(2);
    } catch (err) {
      console.error('Analysis error:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleAddField = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`/api/onboarding/schemas/${schemaId}/fields/add`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          field: suggestion.field,
          extract_from_existing: extractFromExisting
        })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to add field');
      }

      const data = await response.json();

      // Show success message
      if (data.extraction_job_id) {
        alert(`Field added! Extracting from ${suggestion.total_documents} documents. Check progress in a moment.`);
      } else {
        alert('Field added successfully! It will be used for new uploads.');
      }

      onFieldAdded();
      handleClose();
    } catch (err) {
      console.error('Add field error:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b">
          <h2 className="text-xl font-semibold">
            {step === 1 ? 'Add New Field' : 'Review Suggested Field'}
          </h2>
          <button
            onClick={handleClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
            disabled={loading}
          >
            <X size={24} />
          </button>
        </div>

        {error && (
          <div className="mx-6 mt-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-800">
            {error}
          </div>
        )}

        {/* Step 1: Describe Field */}
        {step === 1 && (
          <div className="p-6">
            <p className="text-gray-700 mb-4">
              What field do you want to extract?
            </p>

            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="I want to extract payment terms like 'Net 30' or 'Due on Receipt'"
              rows={4}
              className="w-full border border-gray-300 rounded-lg p-3 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              disabled={loading}
            />

            <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <p className="text-sm text-blue-900 font-medium mb-2">Examples:</p>
              <ul className="text-sm text-blue-800 space-y-1 list-disc ml-5">
                <li>Purchase order numbers</li>
                <li>List of product codes mentioned</li>
                <li>Payment due date</li>
                <li>Line items with description, quantity, and price</li>
              </ul>
            </div>

            <p className="text-sm text-gray-600 mt-4">
              💡 Tip: Be specific! Claude will analyze your existing documents to understand exactly what you mean.
            </p>

            <div className="flex gap-3 mt-6">
              <button
                onClick={handleClose}
                className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                disabled={loading}
              >
                Cancel
              </button>
              <button
                onClick={handleAnalyze}
                disabled={loading || !description.trim()}
                className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
              >
                {loading ? 'Analyzing Documents...' : 'Analyze Documents →'}
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Review Suggestion */}
        {step === 2 && suggestion && (
          <div className="p-6">
            <p className="text-gray-700 mb-4">
              Based on your {suggestion.total_documents} documents, Claude suggests:
            </p>

            {/* Field Details */}
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 mb-6">
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div>
                  <label className="text-sm font-medium text-gray-600">Field Name:</label>
                  <div className="font-mono text-gray-900">{suggestion.field.name}</div>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-600">Type:</label>
                  <div className="text-gray-900 capitalize">{suggestion.field.type}</div>
                </div>
              </div>

              <div className="mb-4">
                <label className="text-sm font-medium text-gray-600">Description:</label>
                <div className="text-gray-900">{suggestion.field.description}</div>
              </div>

              <div>
                <label className="text-sm font-medium text-gray-600">Extraction Hints:</label>
                <div className="flex flex-wrap gap-2 mt-1">
                  {suggestion.field.extraction_hints.map((hint, i) => (
                    <span key={i} className="px-2 py-1 bg-blue-100 text-blue-800 rounded text-sm">
                      {hint}
                    </span>
                  ))}
                </div>
              </div>

              <div className="mt-4">
                <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${
                  suggestion.field.confidence_threshold >= 0.8
                    ? 'bg-green-100 text-green-800'
                    : suggestion.field.confidence_threshold >= 0.6
                    ? 'bg-yellow-100 text-yellow-800'
                    : 'bg-red-100 text-red-800'
                }`}>
                  Confidence: {(suggestion.field.confidence_threshold * 100).toFixed(0)}%
                </span>
              </div>
            </div>

            {/* Sample Extractions */}
            <div className="mb-6">
              <h3 className="font-medium text-gray-900 mb-2">Preview from Sample Documents:</h3>
              <div className="border border-gray-200 rounded-lg overflow-hidden">
                <table className="w-full">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-2 text-left text-sm font-medium text-gray-600">Document</th>
                      <th className="px-4 py-2 text-left text-sm font-medium text-gray-600">Extracted Value</th>
                      <th className="px-4 py-2 text-left text-sm font-medium text-gray-600">Confidence</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {suggestion.sample_extractions.map((ex, i) => (
                      <tr key={i} className="hover:bg-gray-50">
                        <td className="px-4 py-2 text-sm text-gray-900">{ex.filename}</td>
                        <td className="px-4 py-2 text-sm font-mono text-gray-900">
                          {ex.value || <span className="text-gray-400 italic">(not found)</span>}
                        </td>
                        <td className="px-4 py-2 text-sm">
                          {ex.confidence ? (
                            <span className={`px-2 py-1 rounded text-xs font-medium ${
                              ex.confidence >= 0.8
                                ? 'bg-green-100 text-green-800'
                                : ex.confidence >= 0.6
                                ? 'bg-yellow-100 text-yellow-800'
                                : 'bg-red-100 text-red-800'
                            }`}>
                              {(ex.confidence * 100).toFixed(0)}%
                            </span>
                          ) : (
                            <span className="text-gray-400">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <p className="text-sm text-gray-600 mt-2">
                Found in ~{Math.round(suggestion.estimated_success_rate * 100)}% of sample documents
              </p>
            </div>

            {/* Extraction Decision */}
            <div className="border-t pt-4 mb-6">
              <h3 className="font-medium text-gray-900 mb-3">
                Extract from all {suggestion.total_documents} existing documents?
              </h3>

              <label className="flex items-start gap-3 p-4 border-2 rounded-lg cursor-pointer hover:bg-gray-50 mb-2 ${extractFromExisting ? 'border-blue-500 bg-blue-50' : 'border-gray-200'}">
                <input
                  type="radio"
                  checked={extractFromExisting}
                  onChange={() => setExtractFromExisting(true)}
                  className="mt-1"
                  disabled={loading}
                />
                <div className="flex-1">
                  <div className="font-medium text-gray-900">
                    Yes, extract now (${suggestion.estimated_cost.toFixed(2)}, ~{Math.round(suggestion.estimated_time_seconds / 60)} minutes)
                    <span className="ml-2 px-2 py-1 bg-blue-600 text-white rounded text-xs">
                      Recommended
                    </span>
                  </div>
                  <div className="text-sm text-gray-600 mt-1">
                    Found in ~{Math.round(suggestion.estimated_success_rate * 100)}% of documents based on samples
                  </div>
                </div>
              </label>

              <label className={`flex items-start gap-3 p-4 border-2 rounded-lg cursor-pointer hover:bg-gray-50 ${!extractFromExisting ? 'border-blue-500 bg-blue-50' : 'border-gray-200'}`}>
                <input
                  type="radio"
                  checked={!extractFromExisting}
                  onChange={() => setExtractFromExisting(false)}
                  className="mt-1"
                  disabled={loading}
                />
                <div className="flex-1">
                  <div className="font-medium text-gray-900">No, only use for new uploads (FREE, instant)</div>
                  <div className="text-sm text-gray-600 mt-1">
                    Existing documents will have this field empty
                  </div>
                </div>
              </label>
            </div>

            {/* Actions */}
            <div className="flex gap-3">
              <button
                onClick={() => setStep(1)}
                className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                disabled={loading}
              >
                ← Back
              </button>
              <button
                onClick={handleAddField}
                disabled={loading}
                className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
              >
                {loading ? 'Adding Field...' : 'Add Field & Extract'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
