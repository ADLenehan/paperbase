import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import apiClient from '../api/client'

function Verify() {
  const { documentId } = useParams()
  const navigate = useNavigate()
  const [queue, setQueue] = useState([])
  const [currentItem, setCurrentItem] = useState(null)
  const [currentIndex, setCurrentIndex] = useState(0)
  const [loading, setLoading] = useState(true)
  const [verifying, setVerifying] = useState(false)
  const [customValue, setCustomValue] = useState('')
  const [document, setDocument] = useState(null)

  useEffect(() => {
    if (documentId) {
      fetchDocument()
    } else {
      fetchQueue()
    }
  }, [documentId])

  useEffect(() => {
    if (queue.length > 0 && currentIndex < queue.length) {
      setCurrentItem(queue[currentIndex])
      setCustomValue('')
    }
  }, [queue, currentIndex])

  const fetchDocument = async () => {
    setLoading(true)
    try {
      const response = await apiClient.get(`/api/documents/${documentId}`)
      setDocument(response.data)
      // Convert document extractions to verification queue format
      if (response.data.extracted_fields) {
        const items = Object.entries(response.data.extracted_fields).map(([field, value]) => ({
          id: `${documentId}_${field}`,
          document_id: documentId,
          document_filename: response.data.filename,
          field_name: field,
          extracted_value: value,
          confidence: response.data.confidence_scores?.[field] || 1.0
        }))
        setQueue(items)
      }
    } catch (error) {
      console.error('Error fetching document:', error)
    } finally {
      setLoading(false)
    }
  }

  const fetchQueue = async () => {
    setLoading(true)
    try {
      const response = await apiClient.get('/api/verification/queue')
      setQueue(response.data.queue || [])
    } catch (error) {
      console.error('Error fetching queue:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleVerify = async (action, value = null) => {
    if (!currentItem) return

    setVerifying(true)
    try {
      await apiClient.post('/api/verification/verify', {
        field_id: currentItem.id,
        action,
        corrected_value: value || customValue
      })

      // Move to next item
      setCurrentIndex(prev => prev + 1)
    } catch (error) {
      console.error('Verification error:', error)
    } finally {
      setVerifying(false)
    }
  }

  const handleSkip = () => {
    setCurrentIndex(prev => prev + 1)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <p className="mt-2 text-sm text-gray-600">Loading verification queue...</p>
        </div>
      </div>
    )
  }

  if (queue.length === 0) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-8">
        <div className="text-center py-12 bg-white rounded-lg shadow-sm border border-gray-200">
          <svg className="mx-auto h-12 w-12 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <h2 className="mt-4 text-2xl font-semibold text-gray-900">All Caught Up!</h2>
          <p className="mt-2 text-gray-600">No low-confidence extractions need review</p>
        </div>
      </div>
    )
  }

  if (currentIndex >= queue.length) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-8">
        <div className="text-center py-12 bg-white rounded-lg shadow-sm border border-gray-200">
          <svg className="mx-auto h-12 w-12 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <h2 className="mt-4 text-2xl font-semibold text-gray-900">Session Complete!</h2>
          <p className="mt-2 text-gray-600">You've reviewed {queue.length} items</p>
          <div className="mt-4 flex gap-3 justify-center">
            <button
              onClick={() => navigate('/documents')}
              className="bg-blue-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-blue-700"
            >
              Back to Documents
            </button>
            {!documentId && (
              <button
                onClick={() => window.location.reload()}
                className="bg-gray-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-gray-700"
              >
                Start New Session
              </button>
            )}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      {/* Progress Header */}
      <div className="mb-6">
        <div className="flex justify-between items-center mb-2">
          <div className="flex items-center gap-3">
            {documentId && (
              <button
                onClick={() => navigate('/documents')}
                className="text-gray-600 hover:text-gray-900"
              >
                ← Back
              </button>
            )}
            <h1 className="text-2xl font-bold text-gray-900">
              {documentId ? 'Document Verification' : 'HITL Verification'}
            </h1>
          </div>
          <span className="text-sm text-gray-600">
            {currentIndex + 1} of {queue.length}
          </span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div
            className="bg-blue-600 h-2 rounded-full transition-all duration-300"
            style={{ width: `${((currentIndex) / queue.length) * 100}%` }}
          />
        </div>
      </div>

      {currentItem && (
        <div className="grid grid-cols-2 gap-6">
          {/* Left Panel - Document Context */}
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Document Context</h3>

            <div className="space-y-3 mb-6">
              <div>
                <span className="text-sm text-gray-500">Document:</span>
                <p className="font-medium text-gray-900">{currentItem.document_filename}</p>
              </div>

              <div>
                <span className="text-sm text-gray-500">Field:</span>
                <p className="font-medium text-gray-900 capitalize">
                  {currentItem.field_name.replace(/_/g, ' ')}
                </p>
              </div>

              <div>
                <span className="text-sm text-gray-500">Extracted Value:</span>
                <p className="font-medium text-gray-900">{currentItem.extracted_value || '(empty)'}</p>
              </div>

              <div>
                <span className="text-sm text-gray-500">Confidence:</span>
                <div className="flex items-center gap-2">
                  <div className="flex-1 bg-gray-200 rounded-full h-2">
                    <div
                      className="bg-yellow-500 h-2 rounded-full"
                      style={{ width: `${currentItem.confidence * 100}%` }}
                    />
                  </div>
                  <span className="text-sm font-medium text-gray-900">
                    {(currentItem.confidence * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            </div>

            {/* Document Preview Placeholder */}
            <div className="border-2 border-dashed border-gray-300 rounded-lg p-12 text-center">
              <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <p className="mt-2 text-sm text-gray-500">PDF preview coming soon</p>
            </div>
          </div>

          {/* Right Panel - Verification Actions */}
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Verification</h3>

            <p className="text-sm text-gray-600 mb-6">
              Is the extracted value correct? Choose an action below.
            </p>

            <div className="space-y-3">
              {/* Confirm */}
              <button
                onClick={() => handleVerify('confirm')}
                disabled={verifying}
                className="w-full bg-green-600 text-white py-3 px-4 rounded-lg font-medium hover:bg-green-700 transition-colors disabled:opacity-50"
              >
                ✓ Correct (Confirm)
              </button>

              {/* Custom Value */}
              <div className="space-y-2">
                <input
                  type="text"
                  value={customValue}
                  onChange={(e) => setCustomValue(e.target.value)}
                  placeholder="Enter correct value..."
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                <button
                  onClick={() => handleVerify('correct')}
                  disabled={verifying || !customValue}
                  className="w-full bg-blue-600 text-white py-3 px-4 rounded-lg font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
                >
                  Submit Correction
                </button>
              </div>

              {/* Not Found */}
              <button
                onClick={() => handleVerify('not_found')}
                disabled={verifying}
                className="w-full bg-yellow-600 text-white py-3 px-4 rounded-lg font-medium hover:bg-yellow-700 transition-colors disabled:opacity-50"
              >
                Not Found in Document
              </button>

              {/* Skip */}
              <button
                onClick={handleSkip}
                disabled={verifying}
                className="w-full bg-gray-200 text-gray-700 py-3 px-4 rounded-lg font-medium hover:bg-gray-300 transition-colors disabled:opacity-50"
              >
                Skip for Now
              </button>
            </div>

            {/* Keyboard Shortcuts */}
            <div className="mt-8 pt-6 border-t border-gray-200">
              <h4 className="text-sm font-medium text-gray-900 mb-2">Keyboard Shortcuts</h4>
              <div className="text-xs text-gray-600 space-y-1">
                <p><kbd className="px-2 py-1 bg-gray-100 rounded">1</kbd> Confirm</p>
                <p><kbd className="px-2 py-1 bg-gray-100 rounded">2</kbd> Not Found</p>
                <p><kbd className="px-2 py-1 bg-gray-100 rounded">S</kbd> Skip</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default Verify
