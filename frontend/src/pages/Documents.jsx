import { useState } from 'react'
import BulkUpload from '../components/Documents/BulkUpload'
import DocumentList from '../components/Documents/DocumentList'

function Documents() {
  const [refreshTrigger, setRefreshTrigger] = useState(0)
  const [showUpload, setShowUpload] = useState(true)
  const [error, setError] = useState(null)
  const [successMessage, setSuccessMessage] = useState(null)

  const handleUploadComplete = (results) => {
    const successCount = results.filter(r => r.status === 'success').length
    const failCount = results.filter(r => r.status === 'error').length

    setSuccessMessage(
      `${successCount} document(s) processed successfully${failCount > 0 ? `, ${failCount} failed` : ''}`
    )
    setTimeout(() => setSuccessMessage(null), 5000)

    setShowUpload(false)
    setRefreshTrigger(prev => prev + 1)
  }

  const handleError = (errorMessage) => {
    setError(errorMessage)
    setTimeout(() => setError(null), 5000)
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="mb-8">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Documents</h1>
            <p className="mt-1 text-sm text-gray-600">
              Upload and manage your processed documents
            </p>
          </div>
          <button
            onClick={() => setShowUpload(!showUpload)}
            className="bg-blue-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-blue-700 transition-colors"
          >
            {showUpload ? 'Hide Upload' : 'Upload Documents'}
          </button>
        </div>
      </div>

      {/* Messages */}
      {error && (
        <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex">
            <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
            </svg>
            <p className="ml-3 text-sm text-red-800">{error}</p>
          </div>
        </div>
      )}

      {successMessage && (
        <div className="mb-6 bg-green-50 border border-green-200 rounded-lg p-4">
          <div className="flex">
            <svg className="h-5 w-5 text-green-400" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
            <p className="ml-3 text-sm text-green-800">{successMessage}</p>
          </div>
        </div>
      )}

      {/* Upload Section */}
      {showUpload && (
        <div className="mb-8 bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Upload Documents
          </h2>
          <BulkUpload
            schemaId={1}
            onUploadComplete={handleUploadComplete}
            onError={handleError}
          />
        </div>
      )}

      {/* Document List */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          All Documents
        </h2>
        <DocumentList refreshTrigger={refreshTrigger} />
      </div>
    </div>
  )
}

export default Documents
