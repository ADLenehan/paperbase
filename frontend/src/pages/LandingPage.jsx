import { Link } from 'react-router-dom'
import { useState } from 'react'

// Feature data
const features = [
  {
    icon: (
      <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    ),
    title: 'AI-Powered Extraction',
    description: 'Upload any document and let AI automatically identify and extract structured data. No coding required.',
    color: 'coral',
  },
  {
    icon: (
      <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z" />
      </svg>
    ),
    title: 'Smart Templates',
    description: 'AI learns your document types and creates reusable templates. Process hundreds of similar documents instantly.',
    color: 'sky',
  },
  {
    icon: (
      <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
      </svg>
    ),
    title: 'Bulk Processing',
    description: 'Upload 10, 100, or 1000 documents at once. Our system groups and processes them automatically.',
    color: 'orange',
  },
  {
    icon: (
      <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>
    ),
    title: 'Natural Language Search',
    description: 'Ask questions in plain English. Find any document or data point across your entire library.',
    color: 'periwinkle',
  },
  {
    icon: (
      <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    title: 'Confidence Scoring',
    description: 'Every extraction includes a confidence score. Review low-confidence fields with our built-in audit interface.',
    color: 'mint',
  },
  {
    icon: (
      <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
      </svg>
    ),
    title: 'Secure & Private',
    description: 'Your documents stay secure. Role-based access control, API keys, and audit trails built in.',
    color: 'yellow',
  },
]

// How it works steps
const steps = [
  {
    number: '01',
    title: 'Upload Documents',
    description: 'Drag and drop your PDFs, images, or scanned documents. We support invoices, contracts, forms, and more.',
    image: '/images/step-upload.png',
  },
  {
    number: '02',
    title: 'AI Matches Templates',
    description: 'Our AI analyzes your documents, groups similar ones together, and suggests the best extraction template.',
    image: '/images/step-match.png',
  },
  {
    number: '03',
    title: 'Review & Confirm',
    description: 'Check extracted data in a clean table view. Edit any fields that need correction with side-by-side PDF viewing.',
    image: '/images/step-review.png',
  },
  {
    number: '04',
    title: 'Search & Export',
    description: 'Query your documents with natural language. Export to CSV, JSON, or integrate via API.',
    image: '/images/step-export.png',
  },
]

// Stats
const stats = [
  { value: '95%', label: 'Extraction Accuracy' },
  { value: '70%', label: 'Cost Reduction' },
  { value: '<5s', label: 'Per Document' },
  { value: '100+', label: 'Document Types' },
]

// Color mapping for feature cards
const colorClasses = {
  coral: {
    bg: 'bg-coral-50',
    iconBg: 'bg-coral-100',
    iconText: 'text-coral-600',
    border: 'border-coral-200',
  },
  sky: {
    bg: 'bg-sky-50',
    iconBg: 'bg-sky-100',
    iconText: 'text-sky-600',
    border: 'border-sky-200',
  },
  orange: {
    bg: 'bg-orange-50',
    iconBg: 'bg-orange-100',
    iconText: 'text-orange-600',
    border: 'border-orange-200',
  },
  periwinkle: {
    bg: 'bg-periwinkle-50',
    iconBg: 'bg-periwinkle-100',
    iconText: 'text-periwinkle-600',
    border: 'border-periwinkle-200',
  },
  mint: {
    bg: 'bg-mint-50',
    iconBg: 'bg-mint-100',
    iconText: 'text-mint-600',
    border: 'border-mint-200',
  },
  yellow: {
    bg: 'bg-yellow-50',
    iconBg: 'bg-yellow-100',
    iconText: 'text-yellow-600',
    border: 'border-yellow-200',
  },
}

function LandingPage() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  return (
    <div className="min-h-screen bg-white">
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 bg-white/80 backdrop-blur-md z-50 border-b border-gray-100">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16 items-center">
            <div className="flex items-center">
              <Link to="/" className="flex items-center gap-2">
                <div className="w-8 h-8 bg-gradient-to-br from-coral-500 to-orange-400 rounded-lg flex items-center justify-center">
                  <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                </div>
                <span className="text-xl font-bold text-gray-900">Paperbase</span>
              </Link>
            </div>

            {/* Desktop Navigation */}
            <div className="hidden md:flex items-center gap-8">
              <a href="#features" className="text-gray-600 hover:text-gray-900 text-sm font-medium transition-colors">
                Features
              </a>
              <a href="#how-it-works" className="text-gray-600 hover:text-gray-900 text-sm font-medium transition-colors">
                How It Works
              </a>
              <a href="#pricing" className="text-gray-600 hover:text-gray-900 text-sm font-medium transition-colors">
                Pricing
              </a>
              <Link
                to="/upload"
                className="bg-coral-500 hover:bg-coral-600 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
              >
                Get Started
              </Link>
            </div>

            {/* Mobile menu button */}
            <button
              className="md:hidden p-2 text-gray-600"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                {mobileMenuOpen ? (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                ) : (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                )}
              </svg>
            </button>
          </div>
        </div>

        {/* Mobile menu */}
        {mobileMenuOpen && (
          <div className="md:hidden bg-white border-t border-gray-100 py-4">
            <div className="flex flex-col gap-4 px-4">
              <a href="#features" className="text-gray-600 hover:text-gray-900 text-sm font-medium" onClick={() => setMobileMenuOpen(false)}>
                Features
              </a>
              <a href="#how-it-works" className="text-gray-600 hover:text-gray-900 text-sm font-medium" onClick={() => setMobileMenuOpen(false)}>
                How It Works
              </a>
              <a href="#pricing" className="text-gray-600 hover:text-gray-900 text-sm font-medium" onClick={() => setMobileMenuOpen(false)}>
                Pricing
              </a>
              <Link
                to="/upload"
                className="bg-coral-500 hover:bg-coral-600 text-white px-4 py-2 rounded-lg text-sm font-medium text-center"
                onClick={() => setMobileMenuOpen(false)}
              >
                Get Started
              </Link>
            </div>
          </div>
        )}
      </nav>

      {/* Hero Section */}
      <section className="pt-32 pb-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="text-center max-w-4xl mx-auto">
            <div className="inline-flex items-center gap-2 bg-coral-50 text-coral-700 px-4 py-2 rounded-full text-sm font-medium mb-8">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-coral-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-coral-500"></span>
              </span>
              No-code document extraction platform
            </div>

            <h1 className="text-5xl sm:text-6xl lg:text-7xl font-bold text-gray-900 tracking-tight mb-6">
              Turn documents into{' '}
              <span className="bg-gradient-to-r from-coral-500 via-orange-400 to-yellow-400 bg-clip-text text-transparent">
                structured data
              </span>
            </h1>

            <p className="text-xl text-gray-600 mb-10 max-w-2xl mx-auto leading-relaxed">
              Upload PDFs, invoices, contracts, or any document. Our AI extracts the data you need,
              creates searchable databases, and learns from your corrections.
            </p>

            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Link
                to="/upload"
                className="bg-coral-500 hover:bg-coral-600 text-white px-8 py-4 rounded-xl text-lg font-semibold transition-all hover:shadow-lg hover:shadow-coral-500/25 flex items-center justify-center gap-2"
              >
                Start Extracting
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                </svg>
              </Link>
              <a
                href="#how-it-works"
                className="bg-gray-100 hover:bg-gray-200 text-gray-900 px-8 py-4 rounded-xl text-lg font-semibold transition-colors flex items-center justify-center gap-2"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                See How It Works
              </a>
            </div>
          </div>

          {/* Hero Image / Demo Preview */}
          <div className="mt-20 relative">
            <div className="absolute inset-0 bg-gradient-to-t from-white via-transparent to-transparent z-10 pointer-events-none h-32 bottom-0 top-auto"></div>
            <div className="bg-gradient-to-br from-gray-900 to-gray-800 rounded-2xl shadow-2xl overflow-hidden border border-gray-700">
              <div className="flex items-center gap-2 px-4 py-3 bg-gray-800 border-b border-gray-700">
                <div className="flex gap-2">
                  <div className="w-3 h-3 rounded-full bg-red-500"></div>
                  <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
                  <div className="w-3 h-3 rounded-full bg-green-500"></div>
                </div>
                <div className="flex-1 text-center">
                  <span className="text-gray-400 text-sm">paperbase.app</span>
                </div>
              </div>
              <div className="p-8 bg-gray-50">
                {/* Mock UI Preview */}
                <div className="grid grid-cols-3 gap-6">
                  {/* Left Panel - Document List */}
                  <div className="col-span-1 bg-white rounded-lg shadow-sm border border-gray-200 p-4">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="font-semibold text-gray-900 text-sm">Documents</h3>
                      <span className="bg-coral-100 text-coral-600 text-xs px-2 py-1 rounded-full">12 new</span>
                    </div>
                    <div className="space-y-2">
                      {['Invoice_2024_001.pdf', 'Contract_ABC.pdf', 'Receipt_Nov.pdf'].map((doc, i) => (
                        <div key={i} className={`p-3 rounded-lg ${i === 0 ? 'bg-coral-50 border border-coral-200' : 'bg-gray-50'} text-sm`}>
                          <div className="font-medium text-gray-900 truncate">{doc}</div>
                          <div className="text-xs text-gray-500 mt-1">Processing complete</div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Center Panel - Extraction Preview */}
                  <div className="col-span-2 bg-white rounded-lg shadow-sm border border-gray-200 p-4">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="font-semibold text-gray-900 text-sm">Extracted Data</h3>
                      <div className="flex gap-2">
                        <span className="bg-mint-100 text-mint-600 text-xs px-2 py-1 rounded-full flex items-center gap-1">
                          <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                          </svg>
                          95% confidence
                        </span>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      {[
                        { label: 'Invoice Number', value: 'INV-2024-0847' },
                        { label: 'Date', value: 'Nov 15, 2024' },
                        { label: 'Vendor', value: 'Acme Corporation' },
                        { label: 'Total Amount', value: '$4,250.00' },
                        { label: 'Due Date', value: 'Dec 15, 2024' },
                        { label: 'Payment Terms', value: 'Net 30' },
                      ].map((field, i) => (
                        <div key={i} className="bg-gray-50 rounded-lg p-3">
                          <div className="text-xs text-gray-500 mb-1">{field.label}</div>
                          <div className="text-sm font-medium text-gray-900">{field.value}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="py-16 bg-gray-50 border-y border-gray-100">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
            {stats.map((stat, i) => (
              <div key={i} className="text-center">
                <div className="text-4xl font-bold bg-gradient-to-r from-coral-500 to-orange-400 bg-clip-text text-transparent">
                  {stat.value}
                </div>
                <div className="text-gray-600 mt-2">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-24 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold text-gray-900 mb-4">
              Everything you need for document processing
            </h2>
            <p className="text-xl text-gray-600 max-w-2xl mx-auto">
              From extraction to search, Paperbase handles the entire document workflow without writing a single line of code.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((feature, i) => {
              const colors = colorClasses[feature.color]
              return (
                <div
                  key={i}
                  className={`p-6 rounded-2xl border ${colors.border} ${colors.bg} transition-all hover:shadow-lg hover:-translate-y-1`}
                >
                  <div className={`w-14 h-14 rounded-xl ${colors.iconBg} ${colors.iconText} flex items-center justify-center mb-4`}>
                    {feature.icon}
                  </div>
                  <h3 className="text-lg font-semibold text-gray-900 mb-2">{feature.title}</h3>
                  <p className="text-gray-600">{feature.description}</p>
                </div>
              )
            })}
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section id="how-it-works" className="py-24 bg-gray-50 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold text-gray-900 mb-4">
              How it works
            </h2>
            <p className="text-xl text-gray-600 max-w-2xl mx-auto">
              Four simple steps from document upload to actionable data. No technical expertise required.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
            {steps.map((step, i) => (
              <div key={i} className="relative">
                {/* Connector line */}
                {i < steps.length - 1 && (
                  <div className="hidden lg:block absolute top-12 left-full w-full h-0.5 bg-gradient-to-r from-coral-300 to-transparent -translate-x-8 z-0"></div>
                )}

                <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 relative z-10">
                  <div className="text-5xl font-bold text-gray-100 absolute top-4 right-4">
                    {step.number}
                  </div>
                  <div className="w-12 h-12 bg-coral-100 rounded-xl flex items-center justify-center text-coral-600 font-bold text-lg mb-4">
                    {step.number}
                  </div>
                  <h3 className="text-lg font-semibold text-gray-900 mb-2">{step.title}</h3>
                  <p className="text-gray-600 text-sm">{step.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Use Cases Section */}
      <section className="py-24 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold text-gray-900 mb-4">
              Built for every document type
            </h2>
            <p className="text-xl text-gray-600 max-w-2xl mx-auto">
              From simple invoices to complex contracts, Paperbase handles it all.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            {[
              {
                title: 'Invoices & Receipts',
                description: 'Extract vendor info, line items, totals, and payment terms automatically.',
                icon: '📄',
                items: ['Invoice numbers', 'Line items', 'Tax calculations', 'Payment due dates'],
              },
              {
                title: 'Contracts & Agreements',
                description: 'Pull out key clauses, dates, parties, and obligations from legal documents.',
                icon: '📋',
                items: ['Party names', 'Effective dates', 'Key terms', 'Renewal clauses'],
              },
              {
                title: 'Forms & Applications',
                description: 'Digitize paper forms and structured documents with high accuracy.',
                icon: '📝',
                items: ['Applicant info', 'Checkbox fields', 'Signatures', 'Custom fields'],
              },
            ].map((useCase, i) => (
              <div key={i} className="bg-white rounded-2xl p-8 shadow-sm border border-gray-100 hover:shadow-lg transition-shadow">
                <div className="text-4xl mb-4">{useCase.icon}</div>
                <h3 className="text-xl font-semibold text-gray-900 mb-2">{useCase.title}</h3>
                <p className="text-gray-600 mb-4">{useCase.description}</p>
                <ul className="space-y-2">
                  {useCase.items.map((item, j) => (
                    <li key={j} className="flex items-center gap-2 text-sm text-gray-600">
                      <svg className="w-4 h-4 text-mint-500" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                      </svg>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section id="pricing" className="py-24 bg-gray-50 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold text-gray-900 mb-4">
              Simple, transparent pricing
            </h2>
            <p className="text-xl text-gray-600 max-w-2xl mx-auto">
              Start free, upgrade when you need more. No hidden fees.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
            {[
              {
                name: 'Starter',
                price: 'Free',
                description: 'Perfect for trying out Paperbase',
                features: ['50 documents/month', '3 templates', 'Basic search', 'Email support'],
                cta: 'Get Started',
                highlighted: false,
              },
              {
                name: 'Pro',
                price: '$49',
                period: '/month',
                description: 'For growing teams and businesses',
                features: ['1,000 documents/month', 'Unlimited templates', 'Natural language search', 'API access', 'Priority support'],
                cta: 'Start Free Trial',
                highlighted: true,
              },
              {
                name: 'Enterprise',
                price: 'Custom',
                description: 'For large-scale document processing',
                features: ['Unlimited documents', 'Custom integrations', 'SSO & SAML', 'Dedicated support', 'On-premise option'],
                cta: 'Contact Sales',
                highlighted: false,
              },
            ].map((plan, i) => (
              <div
                key={i}
                className={`rounded-2xl p-8 ${
                  plan.highlighted
                    ? 'bg-gradient-to-br from-coral-500 to-orange-500 text-white shadow-xl shadow-coral-500/25 scale-105'
                    : 'bg-white border border-gray-200'
                }`}
              >
                <h3 className={`text-lg font-semibold ${plan.highlighted ? 'text-white' : 'text-gray-900'}`}>
                  {plan.name}
                </h3>
                <div className="mt-4 flex items-baseline">
                  <span className={`text-4xl font-bold ${plan.highlighted ? 'text-white' : 'text-gray-900'}`}>
                    {plan.price}
                  </span>
                  {plan.period && (
                    <span className={`ml-1 ${plan.highlighted ? 'text-white/80' : 'text-gray-500'}`}>
                      {plan.period}
                    </span>
                  )}
                </div>
                <p className={`mt-2 text-sm ${plan.highlighted ? 'text-white/80' : 'text-gray-600'}`}>
                  {plan.description}
                </p>
                <ul className="mt-6 space-y-3">
                  {plan.features.map((feature, j) => (
                    <li key={j} className="flex items-center gap-2 text-sm">
                      <svg
                        className={`w-4 h-4 ${plan.highlighted ? 'text-white' : 'text-mint-500'}`}
                        fill="currentColor"
                        viewBox="0 0 20 20"
                      >
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                      </svg>
                      <span className={plan.highlighted ? 'text-white' : 'text-gray-600'}>{feature}</span>
                    </li>
                  ))}
                </ul>
                <Link
                  to="/upload"
                  className={`mt-8 block w-full py-3 rounded-xl text-center font-semibold transition-colors ${
                    plan.highlighted
                      ? 'bg-white text-coral-600 hover:bg-gray-100'
                      : 'bg-coral-500 text-white hover:bg-coral-600'
                  }`}
                >
                  {plan.cta}
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Final CTA Section */}
      <section className="py-24 px-4 sm:px-6 lg:px-8">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-4xl font-bold text-gray-900 mb-6">
            Ready to transform your document workflow?
          </h2>
          <p className="text-xl text-gray-600 mb-10">
            Join thousands of teams using Paperbase to extract, search, and manage their documents.
          </p>
          <Link
            to="/upload"
            className="inline-flex items-center gap-2 bg-coral-500 hover:bg-coral-600 text-white px-8 py-4 rounded-xl text-lg font-semibold transition-all hover:shadow-lg hover:shadow-coral-500/25"
          >
            Get Started for Free
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
            </svg>
          </Link>
          <p className="text-sm text-gray-500 mt-4">No credit card required</p>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-gray-900 text-gray-400 py-16 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="grid md:grid-cols-4 gap-8">
            <div className="col-span-1">
              <div className="flex items-center gap-2 mb-4">
                <div className="w-8 h-8 bg-gradient-to-br from-coral-500 to-orange-400 rounded-lg flex items-center justify-center">
                  <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                </div>
                <span className="text-xl font-bold text-white">Paperbase</span>
              </div>
              <p className="text-sm">
                No-code document extraction platform powered by AI.
              </p>
            </div>

            <div>
              <h4 className="text-white font-semibold mb-4">Product</h4>
              <ul className="space-y-2 text-sm">
                <li><a href="#features" className="hover:text-white transition-colors">Features</a></li>
                <li><a href="#pricing" className="hover:text-white transition-colors">Pricing</a></li>
                <li><a href="#" className="hover:text-white transition-colors">API Docs</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Changelog</a></li>
              </ul>
            </div>

            <div>
              <h4 className="text-white font-semibold mb-4">Company</h4>
              <ul className="space-y-2 text-sm">
                <li><a href="#" className="hover:text-white transition-colors">About</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Blog</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Careers</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Contact</a></li>
              </ul>
            </div>

            <div>
              <h4 className="text-white font-semibold mb-4">Legal</h4>
              <ul className="space-y-2 text-sm">
                <li><a href="#" className="hover:text-white transition-colors">Privacy Policy</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Terms of Service</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Security</a></li>
              </ul>
            </div>
          </div>

          <div className="border-t border-gray-800 mt-12 pt-8 flex flex-col md:flex-row justify-between items-center gap-4">
            <p className="text-sm">&copy; 2024 Paperbase. All rights reserved.</p>
            <div className="flex gap-4">
              <a href="#" className="hover:text-white transition-colors">
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M8.29 20.251c7.547 0 11.675-6.253 11.675-11.675 0-.178 0-.355-.012-.53A8.348 8.348 0 0022 5.92a8.19 8.19 0 01-2.357.646 4.118 4.118 0 001.804-2.27 8.224 8.224 0 01-2.605.996 4.107 4.107 0 00-6.993 3.743 11.65 11.65 0 01-8.457-4.287 4.106 4.106 0 001.27 5.477A4.072 4.072 0 012.8 9.713v.052a4.105 4.105 0 003.292 4.022 4.095 4.095 0 01-1.853.07 4.108 4.108 0 003.834 2.85A8.233 8.233 0 012 18.407a11.616 11.616 0 006.29 1.84" />
                </svg>
              </a>
              <a href="#" className="hover:text-white transition-colors">
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                  <path fillRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" clipRule="evenodd" />
                </svg>
              </a>
              <a href="#" className="hover:text-white transition-colors">
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                  <path fillRule="evenodd" d="M19 0h-14c-2.761 0-5 2.239-5 5v14c0 2.761 2.239 5 5 5h14c2.762 0 5-2.239 5-5v-14c0-2.761-2.238-5-5-5zm-11 19h-3v-11h3v11zm-1.5-12.268c-.966 0-1.75-.79-1.75-1.764s.784-1.764 1.75-1.764 1.75.79 1.75 1.764-.783 1.764-1.75 1.764zm13.5 12.268h-3v-5.604c0-3.368-4-3.113-4 0v5.604h-3v-11h3v1.765c1.396-2.586 7-2.777 7 2.476v6.759z" clipRule="evenodd" />
                </svg>
              </a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}

export default LandingPage
