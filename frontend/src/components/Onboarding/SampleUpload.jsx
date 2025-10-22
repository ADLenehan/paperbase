import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import apiClient from '../../api/client'

function SampleUpload({ onUploadComplete, onError }) {
  const [files, setFiles] = useState([])
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)

  const onDrop = useCallback((acceptedFiles) => {
    // Validate file count
    if (acceptedFiles.length < 1) {
      onError?.('Please upload at least 1 sample document')
      return
    }
    if (acceptedFiles.length > 5) {
      onError?.('Maximum 5 sample documents allowed')
      return
    }

    // Validate file types
    const invalidFiles = acceptedFiles.filter(file => !file.type.includes('pdf'))
    if (invalidFiles.length > 0) {
      onError?.('Only PDF files are supported')
      return
    }

    setFiles(acceptedFiles)
  }, [onError])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf']
    },
    multiple: true
  })

  const handleUpload = async () => {
    if (files.length === 0) {
      onError?.('Please select files to upload')
      return
    }

    setUploading(true)
    setProgress(0)

    try {
      const formData = new FormData()
      files.forEach(file => {
        formData.append('files', file)
      })

      const response = await apiClient.post('/api/onboarding/analyze-samples', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })

      setProgress(100)
      onUploadComplete?.(response.data)
    } catch (error) {
      onError?.(error.response?.data?.detail || error.message || 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const removeFile = (index) => {
    setFiles(files.filter((_, i) => i !== index))
  }

  return (
    <div className="space-y-6">
      <div
        {...getRootProps()}
        className={`
          border-2 border-dashed rounded-lg p-12 text-center cursor-pointer
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
          aria-hidden="true"
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
          PDF files only • 1-5 sample documents
        </p>
      </div>

      {files.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-gray-900">
            Selected Files ({files.length})
          </h3>
          <ul className="divide-y divide-gray-200 border border-gray-200 rounded-md">
            {files.map((file, index) => (
              <li key={index} className="flex items-center justify-between py-3 px-4">
                <div className="flex items-center min-w-0">
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
                  <span className="ml-2 text-sm text-gray-900 truncate">
                    {file.name}
                  </span>
                  <span className="ml-2 text-xs text-gray-500">
                    ({(file.size / 1024).toFixed(0)} KB)
                  </span>
                </div>
                {!uploading && (
                  <button
                    onClick={() => removeFile(index)}
                    className="ml-4 text-sm text-red-600 hover:text-red-800"
                  >
                    Remove
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {uploading && (
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-gray-600">Analyzing documents...</span>
            <span className="text-gray-900 font-medium">{progress}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-blue-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
          <p className="text-xs text-gray-500">
            This may take 2-3 minutes. Please don't close this window.
          </p>
        </div>
      )}

      {files.length >= 1 && !uploading && (
        <button
          onClick={handleUpload}
          className="w-full bg-blue-600 text-white py-3 px-4 rounded-lg font-medium hover:bg-blue-700 transition-colors"
        >
          Analyze Documents & Generate Schema
        </button>
      )}
    </div>
  )
}

export default SampleUpload
