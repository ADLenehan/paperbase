import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import SampleUpload from '../components/Onboarding/SampleUpload'
import TemplateLibrary from '../components/Onboarding/TemplateLibrary'
import SchemaPreviewInline from '../components/Onboarding/SchemaPreviewInline'

function Onboarding() {
  const [step, setStep] = useState(1) // 1: Choose path, 2: Upload OR Template, 3: Review
  const [schema, setSchema] = useState(null)
  const [error, setError] = useState(null)
  const [onboardingPath, setOnboardingPath] = useState(null) // 'template' or 'samples'
  const [isFromTemplate, setIsFromTemplate] = useState(false)
  const navigate = useNavigate()

  const handleChoosePath = (path) => {
    setOnboardingPath(path)
    setStep(2)
  }

  const handleUploadComplete = (result) => {
    console.log('Upload complete:', result)
    const schemaWithId = {
      ...result.schema,
      id: result.schema_id
    }
    setSchema(schemaWithId)
    setIsFromTemplate(false)
    setStep(3)
    setError(null)
  }

  const handleTemplateSelected = (template) => {
    console.log('Template selected:', template)
    const schemaFromTemplate = {
      id: template.id,
      name: template.name,
      fields: template.fields
    }
    setSchema(schemaFromTemplate)
    setIsFromTemplate(true)
    setStep(3)
  }

  const handleSkipTemplate = () => {
    // Go to sample upload
    setOnboardingPath('samples')
  }

  const handleError = (errorMessage) => {
    setError(errorMessage)
    setTimeout(() => setError(null), 5000)
  }

  const handleConfirm = async (confirmedSchema) => {
    console.log('Schema confirmed:', confirmedSchema)
    navigate('/documents')
  }

  const handleSchemaUpdate = (updatedSchema) => {
    setSchema(updatedSchema)
  }

  const handleBackToStart = () => {
    setStep(1)
    setOnboardingPath(null)
    setSchema(null)
    setIsFromTemplate(false)
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* Progress Steps */}
      <div className="mb-8">
        <nav aria-label="Progress">
          <ol className="flex items-center">
            <li className="relative pr-8 sm:pr-20 flex-1">
              <div className="absolute inset-0 flex items-center" aria-hidden="true">
                <div className={`h-0.5 w-full ${step >= 2 ? 'bg-blue-600' : 'bg-gray-200'}`} />
              </div>
              <div className={`relative flex h-8 w-8 items-center justify-center rounded-full ${
                step >= 1 ? 'bg-blue-600' : 'bg-gray-200'
              }`}>
                <span className="text-white font-medium">1</span>
              </div>
              <span className="absolute top-10 left-0 text-sm font-medium text-gray-900 whitespace-nowrap">
                Choose Approach
              </span>
            </li>

            <li className="relative pr-8 sm:pr-20 flex-1">
              <div className="absolute inset-0 flex items-center" aria-hidden="true">
                <div className={`h-0.5 w-full ${step >= 3 ? 'bg-blue-600' : 'bg-gray-200'}`} />
              </div>
              <div className={`relative flex h-8 w-8 items-center justify-center rounded-full ${
                step >= 2 ? 'bg-blue-600' : 'bg-gray-200'
              }`}>
                <span className="text-white font-medium">2</span>
              </div>
              <span className="absolute top-10 left-0 text-sm font-medium text-gray-900 whitespace-nowrap">
                {onboardingPath === 'template' ? 'Select Template' : 'Upload Samples'}
              </span>
            </li>

            <li className="relative flex-1">
              <div className={`relative flex h-8 w-8 items-center justify-center rounded-full ${
                step >= 3 ? 'bg-blue-600' : 'bg-gray-200'
              }`}>
                <span className="text-white font-medium">3</span>
              </div>
              <span className="absolute top-10 left-0 text-sm font-medium text-gray-900 whitespace-nowrap">
                Review & Customize
              </span>
            </li>
          </ol>
        </nav>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="ml-3">
              <p className="text-sm text-red-800">{error}</p>
            </div>
          </div>
        </div>
      )}

      {/* Main Content */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8">
        {/* Step 1: Choose Path */}
        {step === 1 && (
          <div>
            <h1 className="text-3xl font-bold text-gray-900 mb-2">
              Welcome to Paperbase
            </h1>
            <p className="text-gray-600 mb-8">
              Choose how you'd like to get started with document extraction
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Template Option */}
              <button
                onClick={() => handleChoosePath('template')}
                className="text-left p-6 border-2 border-gray-200 rounded-lg hover:border-blue-500 hover:shadow-md transition-all group"
              >
                <div className="flex items-start gap-4">
                  <div className="p-3 bg-purple-100 rounded-lg group-hover:bg-purple-200 transition-colors">
                    <svg className="w-8 h-8 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z" />
                    </svg>
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900 mb-2 group-hover:text-blue-600 transition-colors">
                      Start with a Template
                    </h3>
                    <p className="text-sm text-gray-600 mb-3">
                      Choose from pre-built schemas for common document types like invoices, contracts, and receipts
                    </p>
                    <div className="flex items-center gap-2 text-sm text-purple-600 font-medium">
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                      </svg>
                      Browse templates
                    </div>
                  </div>
                </div>
                <div className="mt-4 pt-4 border-t border-gray-200">
                  <div className="flex items-center gap-2 text-xs text-gray-500">
                    <svg className="w-4 h-4 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                    </svg>
                    Fastest setup • Best practices included
                  </div>
                </div>
              </button>

              {/* Upload Samples Option */}
              <button
                onClick={() => handleChoosePath('samples')}
                className="text-left p-6 border-2 border-gray-200 rounded-lg hover:border-blue-500 hover:shadow-md transition-all group"
              >
                <div className="flex items-start gap-4">
                  <div className="p-3 bg-blue-100 rounded-lg group-hover:bg-blue-200 transition-colors">
                    <svg className="w-8 h-8 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900 mb-2 group-hover:text-blue-600 transition-colors">
                      Generate from Samples
                    </h3>
                    <p className="text-sm text-gray-600 mb-3">
                      Upload 3-5 sample documents and let AI automatically generate a custom extraction schema
                    </p>
                    <div className="flex items-center gap-2 text-sm text-blue-600 font-medium">
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                      </svg>
                      Upload documents
                    </div>
                  </div>
                </div>
                <div className="mt-4 pt-4 border-t border-gray-200">
                  <div className="flex items-center gap-2 text-xs text-gray-500">
                    <svg className="w-4 h-4 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                    </svg>
                    Custom to your docs • AI-powered
                  </div>
                </div>
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Template Library or Sample Upload */}
        {step === 2 && onboardingPath === 'template' && (
          <TemplateLibrary
            onSelectTemplate={handleTemplateSelected}
            onSkip={handleSkipTemplate}
          />
        )}

        {step === 2 && onboardingPath === 'samples' && (
          <div>
            <div className="flex items-center justify-between mb-6">
              <div>
                <h1 className="text-3xl font-bold text-gray-900 mb-2">
                  Upload Sample Documents
                </h1>
                <p className="text-gray-600">
                  Upload 3-5 sample documents to generate a custom extraction schema powered by AI
                </p>
              </div>
              <button
                onClick={handleBackToStart}
                className="text-sm text-gray-600 hover:text-gray-900 flex items-center gap-1"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                </svg>
                Back
              </button>
            </div>

            <SampleUpload
              onUploadComplete={handleUploadComplete}
              onError={handleError}
            />
          </div>
        )}

        {/* Step 3: Review with Inline Editing */}
        {step === 3 && schema && (
          <div>
            <div className="flex items-center justify-between mb-6">
              <h1 className="text-2xl font-bold text-gray-900">
                Review & Customize
              </h1>
              <button
                onClick={handleBackToStart}
                className="text-sm text-gray-600 hover:text-gray-900 flex items-center gap-1"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                </svg>
                Start Over
              </button>
            </div>

            <SchemaPreviewInline
              schema={schema}
              onConfirm={handleConfirm}
              onSchemaUpdate={handleSchemaUpdate}
              isFromTemplate={isFromTemplate}
            />
          </div>
        )}
      </div>

      {/* Help Section */}
      <div className="mt-8 text-center text-sm text-gray-500">
        <p>
          Need help? Check out our{' '}
          <a href="#" className="text-blue-600 hover:text-blue-800">
            documentation
          </a>{' '}
          or{' '}
          <a href="#" className="text-blue-600 hover:text-blue-800">
            watch a tutorial
          </a>
        </p>
      </div>
    </div>
  )
}

export default Onboarding
