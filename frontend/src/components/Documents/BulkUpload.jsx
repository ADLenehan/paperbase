import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import apiClient from '../../api/client'

function BulkUpload({ schemaId, onUploadComplete, onError }) {
  const [files, setFiles] = useState([])
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState({})

  const onDrop = useCallback((acceptedFiles) => {
    // Validate file types
    const invalidFiles = acceptedFiles.filter(file => !file.type.includes('pdf'))
    if (invalidFiles.length > 0) {
      onError?.('Only PDF files are supported')
      return
    }

    setFiles(prev => [...prev, ...acceptedFiles])
  }, [onError])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf']
    },
    multiple: true
  })

  const removeFile = (index) => {
    setFiles(files.filter((_, i) => i !== index))
  }

  const handleUpload = async () => {
    if (files.length === 0) {
      onError?.('Please select files to upload')
      return
    }

    setUploading(true)
    const results = []
    const progress = {}

    for (let i = 0; i < files.length; i++) {
      const file = files[i]
      progress[file.name] = 'uploading'
      setUploadProgress({...progress})

      try {
        // Step 1: Upload file
        const formData = new FormData()
        formData.append('file', file)
        if (schemaId) {
          formData.append('schema_id', schemaId)
        }

        const uploadResponse = await apiClient.post('/api/documents/upload', formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        })

        const documentId = uploadResponse.data.document_id

        // Step 2: Process document
        progress[file.name] = 'processing'
        setUploadProgress({...progress})

        await apiClient.post('/api/documents/process', {
          document_ids: [documentId],
          schema_id: schemaId
        })

        progress[file.name] = 'completed'
        setUploadProgress({...progress})

        results.push({
          file: file.name,
          documentId,
          status: 'success'
        })
      } catch (error) {
        progress[file.name] = 'failed'
        setUploadProgress({...progress})
        results.push({
          file: file.name,
          status: 'error',
          error: error.message
        })
      }
    }

    setUploading(false)
    onUploadComplete?.(results)
  }

  const getProgressColor = (status) => {
    switch (status) {
      case 'completed':
        return 'bg-green-600'
      case 'failed':
        return 'bg-red-600'
      case 'processing':
      case 'uploading':
        return 'bg-blue-600'
      default:
        return 'bg-gray-200'
    }
  }

  const getStatusText = (status) => {
    switch (status) {
      case 'uploading':
        return 'Uploading...'
      case 'processing':
        return 'Processing...'
      case 'completed':
        return 'Complete'
      case 'failed':
        return 'Failed'
      default:
        return 'Pending'
    }
  }

  return (
    <div className="space-y-6">
      <div
        {...getRootProps()}
        className={`
          border-2 border-dashed rounded-lg p-8 text-center cursor-pointer
          transition-colors
          ${isDragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400'}
          ${uploading ? 'opacity-50 pointer-events-none' : ''}
        `}
      >
        <input {...getInputProps()} />
        <svg
          className="mx-auto h-12 w-12 text-gray-400"
          stroke="currentColor"
          fill="none"
          viewBox="0 0 48 48"
        >
          <path
            d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02"
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        <p className="mt-2 text-sm text-gray-600">
          {isDragActive ? (
            'Drop the files here...'
          ) : (
            <>
              <span className="font-medium text-blue-600">Click to upload</span> or drag and drop
            </>
          )}
        </p>
        <p className="mt-1 text-xs text-gray-500">
          PDF files • Upload as many as you need
        </p>
      </div>

      {files.length > 0 && (
        <div className="space-y-2">
          <div className="flex justify-between items-center">
            <h3 className="text-sm font-medium text-gray-900">
              Queue ({files.length} {files.length === 1 ? 'document' : 'documents'})
            </h3>
            {!uploading && (
              <button
                onClick={() => setFiles([])}
                className="text-sm text-gray-600 hover:text-gray-800"
              >
                Clear all
              </button>
            )}
          </div>

          <ul className="divide-y divide-gray-200 border border-gray-200 rounded-md max-h-96 overflow-y-auto">
            {files.map((file, index) => {
              const status = uploadProgress[file.name] || 'pending'

              return (
                <li key={index} className="py-3 px-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center min-w-0 flex-1">
                      <svg
                        className="h-5 w-5 text-gray-400 flex-shrink-0"
                        fill="currentColor"
                        viewBox="0 0 20 20"
                      >
                        <path
                          fillRule="evenodd"
                          d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z"
                          clipRule="evenodd"
                        />
                      </svg>
                      <div className="ml-2 flex-1 min-w-0">
                        <p className="text-sm text-gray-900 truncate">
                          {file.name}
                        </p>
                        <p className="text-xs text-gray-500">
                          {(file.size / 1024).toFixed(0)} KB • {getStatusText(status)}
                        </p>
                      </div>
                    </div>
                    {!uploading && status !== 'completed' && (
                      <button
                        onClick={() => removeFile(index)}
                        className="ml-4 text-sm text-red-600 hover:text-red-800"
                      >
                        Remove
                      </button>
                    )}
                    {status === 'completed' && (
                      <svg className="h-5 w-5 text-green-600" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                      </svg>
                    )}
                    {status === 'failed' && (
                      <svg className="h-5 w-5 text-red-600" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                      </svg>
                    )}
                  </div>
                  {(status === 'uploading' || status === 'processing') && (
                    <div className="mt-2">
                      <div className="w-full bg-gray-200 rounded-full h-1">
                        <div className={`${getProgressColor(status)} h-1 rounded-full animate-pulse`} style={{ width: '100%' }} />
                      </div>
                    </div>
                  )}
                </li>
              )
            })}
          </ul>
        </div>
      )}

      {files.length > 0 && !uploading && (
        <button
          onClick={handleUpload}
          className="w-full bg-blue-600 text-white py-3 px-4 rounded-lg font-medium hover:bg-blue-700 transition-colors"
        >
          Upload & Process {files.length} {files.length === 1 ? 'Document' : 'Documents'}
        </button>
      )}

      {uploading && (
        <div className="text-center text-sm text-gray-600">
          <p>Processing documents... Please don't close this window.</p>
        </div>
      )}
    </div>
  )
}

export default BulkUpload
