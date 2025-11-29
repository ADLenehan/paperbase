import { Link } from 'react-router-dom'
import { useState, useEffect } from 'react'

// High-quality stock images from Unsplash
const images = {
  hero: 'https://images.unsplash.com/photo-1497366216548-37526070297c?auto=format&fit=crop&w=2000&q=80',
  heroOverlay: 'https://images.unsplash.com/photo-1553877522-43269d4ea984?auto=format&fit=crop&w=2000&q=80',
  documents: 'https://images.unsplash.com/photo-1568667256549-094345857637?auto=format&fit=crop&w=800&q=80',
  analysis: 'https://images.unsplash.com/photo-1551288049-bebda4e38f71?auto=format&fit=crop&w=800&q=80',
  teamwork: 'https://images.unsplash.com/photo-1522071820081-009f0129c71c?auto=format&fit=crop&w=800&q=80',
  office: 'https://images.unsplash.com/photo-1497215728101-856f4ea42174?auto=format&fit=crop&w=800&q=80',
  laptop: 'https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=800&q=80',
  filing: 'https://images.unsplash.com/photo-1586281380349-632531db7ed4?auto=format&fit=crop&w=800&q=80',
  invoices: 'https://images.unsplash.com/photo-1554224155-6726b3ff858f?auto=format&fit=crop&w=600&q=80',
  contracts: 'https://images.unsplash.com/photo-1450101499163-c8848c66ca85?auto=format&fit=crop&w=600&q=80',
  forms: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=600&q=80',
  testimonial1: 'https://images.unsplash.com/photo-1494790108755-2616b612b786?auto=format&fit=crop&w=200&q=80',
  testimonial2: 'https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?auto=format&fit=crop&w=200&q=80',
  testimonial3: 'https://images.unsplash.com/photo-1438761681033-6461ffad8d80?auto=format&fit=crop&w=200&q=80',
  ctaBg: 'https://images.unsplash.com/photo-1557804506-669a67965ba0?auto=format&fit=crop&w=2000&q=80',
}

// Animated counter component
function AnimatedCounter({ end, duration = 2000, suffix = '' }) {
  const [count, setCount] = useState(0)

  useEffect(() => {
    let startTime
    const animate = (timestamp) => {
      if (!startTime) startTime = timestamp
      const progress = Math.min((timestamp - startTime) / duration, 1)
      setCount(Math.floor(progress * end))
      if (progress < 1) requestAnimationFrame(animate)
    }
    requestAnimationFrame(animate)
  }, [end, duration])

  return <span>{count}{suffix}</span>
}

// Feature data with images
const features = [
  {
    image: images.documents,
    title: 'AI-Powered Extraction',
    description: 'Upload any document and let AI automatically identify and extract structured data with 95% accuracy. No coding required.',
    stats: '95% accuracy',
    color: 'from-coral-500 to-orange-500',
  },
  {
    image: images.analysis,
    title: 'Smart Templates',
    description: 'AI learns your document types and creates reusable templates. Process hundreds of similar documents in seconds.',
    stats: '10x faster',
    color: 'from-sky-500 to-periwinkle-500',
  },
  {
    image: images.teamwork,
    title: 'Team Collaboration',
    description: 'Share documents, assign reviews, and manage permissions. Built for teams of any size with enterprise-grade security.',
    stats: 'Unlimited users',
    color: 'from-mint-500 to-sky-500',
  },
]

// How it works steps with mockup images
const steps = [
  {
    number: '01',
    title: 'Upload Your Documents',
    description: 'Drag and drop PDFs, images, or scanned documents. We support invoices, contracts, forms, receipts, and 100+ document types.',
    image: images.filing,
  },
  {
    number: '02',
    title: 'AI Analyzes & Matches',
    description: 'Our AI analyzes your documents, groups similar ones together, and automatically suggests the best extraction template.',
    image: images.laptop,
  },
  {
    number: '03',
    title: 'Review & Verify',
    description: 'Check extracted data in a clean table view. Edit any fields that need correction with side-by-side PDF viewing.',
    image: images.office,
  },
  {
    number: '04',
    title: 'Search & Export',
    description: 'Query your documents with natural language. Export to CSV, JSON, or integrate via our powerful API.',
    image: images.analysis,
  },
]

// Testimonials
const testimonials = [
  {
    quote: "Paperbase cut our document processing time by 80%. What used to take our team days now happens in hours.",
    author: "Sarah Chen",
    role: "Operations Director",
    company: "TechFlow Inc.",
    image: images.testimonial1,
  },
  {
    quote: "The accuracy is incredible. We've processed over 50,000 invoices with minimal corrections needed.",
    author: "Michael Rodriguez",
    role: "CFO",
    company: "Global Logistics",
    image: images.testimonial2,
  },
  {
    quote: "Finally, a document solution that actually works. The natural language search is a game-changer.",
    author: "Emily Watson",
    role: "Legal Ops Manager",
    company: "Sterling Law",
    image: images.testimonial3,
  },
]

// Stats
const stats = [
  { value: 95, suffix: '%', label: 'Extraction Accuracy' },
  { value: 70, suffix: '%', label: 'Cost Reduction' },
  { value: 5, suffix: 's', label: 'Per Document' },
  { value: 100, suffix: '+', label: 'Document Types' },
]

// Use cases
const useCases = [
  {
    title: 'Invoices & Receipts',
    description: 'Extract vendor info, line items, totals, and payment terms automatically with confidence scoring.',
    image: images.invoices,
    items: ['Invoice numbers & dates', 'Line item extraction', 'Tax calculations', 'Payment due dates'],
  },
  {
    title: 'Contracts & Agreements',
    description: 'Pull out key clauses, dates, parties, and obligations from legal documents instantly.',
    image: images.contracts,
    items: ['Party names', 'Effective dates', 'Key terms & clauses', 'Renewal provisions'],
  },
  {
    title: 'Forms & Applications',
    description: 'Digitize paper forms and structured documents with field-level confidence indicators.',
    image: images.forms,
    items: ['Applicant information', 'Checkbox detection', 'Signature fields', 'Custom form fields'],
  },
]

function LandingPage() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [activeTab, setActiveTab] = useState(0)

  return (
    <div className="min-h-screen bg-white">
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 bg-white/95 backdrop-blur-md z-50 border-b border-slate-100">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16 items-center">
            <div className="flex items-center">
              <Link to="/" className="flex items-center gap-3">
                <div className="w-10 h-10 bg-gradient-to-br from-coral-500 via-orange-400 to-yellow-400 rounded-xl flex items-center justify-center shadow-lg shadow-coral-500/25">
                  <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                </div>
                <span className="text-2xl font-bold bg-gradient-to-r from-slate-900 to-slate-700 bg-clip-text text-transparent">Paperbase</span>
              </Link>
            </div>

            {/* Desktop Navigation */}
            <div className="hidden md:flex items-center gap-8">
              <a href="#features" className="text-slate-600 hover:text-slate-900 text-sm font-medium transition-colors">
                Features
              </a>
              <a href="#how-it-works" className="text-slate-600 hover:text-slate-900 text-sm font-medium transition-colors">
                How It Works
              </a>
              <a href="#use-cases" className="text-slate-600 hover:text-slate-900 text-sm font-medium transition-colors">
                Use Cases
              </a>
              <a href="#pricing" className="text-slate-600 hover:text-slate-900 text-sm font-medium transition-colors">
                Pricing
              </a>
              <Link
                to="/upload"
                className="bg-gradient-to-r from-coral-500 to-orange-500 hover:from-coral-600 hover:to-orange-600 text-white px-5 py-2.5 rounded-xl text-sm font-semibold transition-all shadow-lg shadow-coral-500/25 hover:shadow-coral-500/40"
              >
                Get Started Free
              </Link>
            </div>

            {/* Mobile menu button */}
            <button
              className="md:hidden p-2 text-slate-600"
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
          <div className="md:hidden bg-white border-t border-slate-100 py-4 shadow-xl">
            <div className="flex flex-col gap-4 px-4">
              <a href="#features" className="text-slate-600 hover:text-slate-900 text-sm font-medium" onClick={() => setMobileMenuOpen(false)}>
                Features
              </a>
              <a href="#how-it-works" className="text-slate-600 hover:text-slate-900 text-sm font-medium" onClick={() => setMobileMenuOpen(false)}>
                How It Works
              </a>
              <a href="#use-cases" className="text-slate-600 hover:text-slate-900 text-sm font-medium" onClick={() => setMobileMenuOpen(false)}>
                Use Cases
              </a>
              <a href="#pricing" className="text-slate-600 hover:text-slate-900 text-sm font-medium" onClick={() => setMobileMenuOpen(false)}>
                Pricing
              </a>
              <Link
                to="/upload"
                className="bg-gradient-to-r from-coral-500 to-orange-500 text-white px-4 py-2.5 rounded-xl text-sm font-semibold text-center"
                onClick={() => setMobileMenuOpen(false)}
              >
                Get Started Free
              </Link>
            </div>
          </div>
        )}
      </nav>

      {/* Hero Section with Background Image */}
      <section className="relative min-h-screen flex items-center pt-16">
        {/* Background Image with Overlay */}
        <div className="absolute inset-0 z-0">
          <img
            src={images.hero}
            alt=""
            className="w-full h-full object-cover"
          />
          <div className="absolute inset-0 bg-gradient-to-r from-slate-900/95 via-slate-900/80 to-slate-900/60"></div>
          <div className="absolute inset-0 bg-gradient-to-t from-slate-900/50 to-transparent"></div>
        </div>

        <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20 lg:py-32">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            {/* Left Column - Text Content */}
            <div>
              <div className="inline-flex items-center gap-2 bg-white/10 backdrop-blur-sm text-white px-4 py-2 rounded-full text-sm font-medium mb-8 border border-white/20">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-mint-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-mint-400"></span>
                </span>
                AI-Powered Document Intelligence
              </div>

              <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-white tracking-tight mb-6 leading-tight">
                Transform documents into{' '}
                <span className="bg-gradient-to-r from-coral-400 via-orange-400 to-yellow-400 bg-clip-text text-transparent">
                  actionable data
                </span>
              </h1>

              <p className="text-xl text-slate-300 mb-10 leading-relaxed max-w-xl">
                Upload PDFs, invoices, contracts, or any document. Our AI extracts the data you need,
                creates searchable databases, and learns from your corrections.
              </p>

              <div className="flex flex-col sm:flex-row gap-4">
                <Link
                  to="/upload"
                  className="bg-gradient-to-r from-coral-500 to-orange-500 hover:from-coral-600 hover:to-orange-600 text-white px-8 py-4 rounded-xl text-lg font-semibold transition-all shadow-xl shadow-coral-500/30 hover:shadow-coral-500/50 flex items-center justify-center gap-2 group"
                >
                  Start Extracting Free
                  <svg className="w-5 h-5 group-hover:translate-x-1 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                  </svg>
                </Link>
                <a
                  href="#how-it-works"
                  className="bg-white/10 hover:bg-white/20 backdrop-blur-sm text-white px-8 py-4 rounded-xl text-lg font-semibold transition-all flex items-center justify-center gap-2 border border-white/20"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  Watch Demo
                </a>
              </div>

              {/* Trust indicators */}
              <div className="mt-12 flex items-center gap-8">
                <div className="text-slate-400 text-sm">Trusted by teams at:</div>
                <div className="flex items-center gap-6 opacity-60">
                  <span className="text-white font-semibold">Stripe</span>
                  <span className="text-white font-semibold">Notion</span>
                  <span className="text-white font-semibold">Linear</span>
                </div>
              </div>
            </div>

            {/* Right Column - App Preview */}
            <div className="hidden lg:block">
              <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-2 shadow-2xl border border-white/20">
                <div className="bg-slate-900 rounded-xl overflow-hidden">
                  {/* Browser chrome */}
                  <div className="flex items-center gap-2 px-4 py-3 bg-slate-800 border-b border-slate-700">
                    <div className="flex gap-2">
                      <div className="w-3 h-3 rounded-full bg-red-500"></div>
                      <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
                      <div className="w-3 h-3 rounded-full bg-green-500"></div>
                    </div>
                    <div className="flex-1 text-center">
                      <span className="text-slate-400 text-sm">app.paperbase.io</span>
                    </div>
                  </div>
                  {/* App Preview */}
                  <div className="p-6 bg-gradient-to-br from-slate-50 to-slate-100">
                    <div className="grid grid-cols-5 gap-4">
                      {/* Sidebar */}
                      <div className="col-span-1 bg-white rounded-lg shadow-sm p-3 space-y-2">
                        <div className="h-3 bg-coral-200 rounded w-full"></div>
                        <div className="h-3 bg-slate-200 rounded w-4/5"></div>
                        <div className="h-3 bg-slate-200 rounded w-3/5"></div>
                        <div className="h-3 bg-slate-200 rounded w-4/5"></div>
                        <div className="h-px bg-slate-200 my-3"></div>
                        <div className="h-3 bg-slate-200 rounded w-full"></div>
                        <div className="h-3 bg-slate-200 rounded w-2/3"></div>
                      </div>
                      {/* Main content */}
                      <div className="col-span-4 space-y-4">
                        {/* Header */}
                        <div className="bg-white rounded-lg shadow-sm p-4 flex justify-between items-center">
                          <div className="flex items-center gap-3">
                            <div className="w-10 h-10 bg-coral-100 rounded-lg flex items-center justify-center">
                              <svg className="w-5 h-5 text-coral-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                              </svg>
                            </div>
                            <div>
                              <div className="font-semibold text-slate-900 text-sm">Invoice_2024_001.pdf</div>
                              <div className="text-xs text-slate-500">Processing complete</div>
                            </div>
                          </div>
                          <span className="bg-mint-100 text-mint-700 text-xs px-3 py-1 rounded-full font-medium">95% confidence</span>
                        </div>
                        {/* Extracted fields */}
                        <div className="bg-white rounded-lg shadow-sm p-4">
                          <div className="text-xs font-medium text-slate-500 mb-3">EXTRACTED DATA</div>
                          <div className="grid grid-cols-2 gap-3">
                            {[
                              { label: 'Invoice #', value: 'INV-2024-0847' },
                              { label: 'Amount', value: '$4,250.00' },
                              { label: 'Vendor', value: 'Acme Corp' },
                              { label: 'Due Date', value: 'Dec 15' },
                            ].map((field, i) => (
                              <div key={i} className="bg-slate-50 rounded p-2">
                                <div className="text-xs text-slate-500">{field.label}</div>
                                <div className="text-sm font-medium text-slate-900">{field.value}</div>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Scroll indicator */}
        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 z-10">
          <div className="w-6 h-10 rounded-full border-2 border-white/30 flex items-start justify-center p-2">
            <div className="w-1 h-2 bg-white/60 rounded-full animate-bounce"></div>
          </div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="py-20 bg-gradient-to-b from-slate-900 to-slate-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
            {stats.map((stat, i) => (
              <div key={i} className="text-center">
                <div className="text-5xl font-bold bg-gradient-to-r from-coral-400 via-orange-400 to-yellow-400 bg-clip-text text-transparent mb-2">
                  <AnimatedCounter end={stat.value} suffix={stat.suffix} />
                </div>
                <div className="text-slate-400 font-medium">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features Section with Images */}
      <section id="features" className="py-24 bg-slate-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <div className="inline-flex items-center gap-2 bg-coral-100 text-coral-700 px-4 py-2 rounded-full text-sm font-medium mb-6">
              Powerful Features
            </div>
            <h2 className="text-4xl lg:text-5xl font-bold text-slate-900 mb-6">
              Everything you need for{' '}
              <span className="bg-gradient-to-r from-coral-500 to-orange-500 bg-clip-text text-transparent">
                document intelligence
              </span>
            </h2>
            <p className="text-xl text-slate-600 max-w-2xl mx-auto">
              From extraction to search, Paperbase handles the entire document workflow without writing a single line of code.
            </p>
          </div>

          <div className="space-y-24">
            {features.map((feature, i) => (
              <div
                key={i}
                className={`grid lg:grid-cols-2 gap-12 items-center ${i % 2 === 1 ? 'lg:flex-row-reverse' : ''}`}
              >
                <div className={i % 2 === 1 ? 'lg:order-2' : ''}>
                  <div className={`inline-flex items-center gap-2 bg-gradient-to-r ${feature.color} text-white px-4 py-2 rounded-full text-sm font-medium mb-6`}>
                    {feature.stats}
                  </div>
                  <h3 className="text-3xl font-bold text-slate-900 mb-4">{feature.title}</h3>
                  <p className="text-lg text-slate-600 leading-relaxed mb-6">{feature.description}</p>
                  <Link
                    to="/upload"
                    className="inline-flex items-center gap-2 text-coral-600 hover:text-coral-700 font-semibold group"
                  >
                    Learn more
                    <svg className="w-4 h-4 group-hover:translate-x-1 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                    </svg>
                  </Link>
                </div>
                <div className={i % 2 === 1 ? 'lg:order-1' : ''}>
                  <div className="relative">
                    <div className="absolute inset-0 bg-gradient-to-r from-coral-500 to-orange-500 rounded-2xl transform rotate-3 scale-105 opacity-10"></div>
                    <img
                      src={feature.image}
                      alt={feature.title}
                      className="relative rounded-2xl shadow-2xl w-full h-80 object-cover"
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section id="how-it-works" className="py-24 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <div className="inline-flex items-center gap-2 bg-sky-100 text-sky-700 px-4 py-2 rounded-full text-sm font-medium mb-6">
              Simple Workflow
            </div>
            <h2 className="text-4xl lg:text-5xl font-bold text-slate-900 mb-6">
              Four steps to{' '}
              <span className="bg-gradient-to-r from-sky-500 to-periwinkle-500 bg-clip-text text-transparent">
                document automation
              </span>
            </h2>
            <p className="text-xl text-slate-600 max-w-2xl mx-auto">
              From document upload to actionable data in minutes. No technical expertise required.
            </p>
          </div>

          {/* Tab Navigation */}
          <div className="flex flex-wrap justify-center gap-4 mb-12">
            {steps.map((step, i) => (
              <button
                key={i}
                onClick={() => setActiveTab(i)}
                className={`px-6 py-3 rounded-xl font-medium transition-all ${
                  activeTab === i
                    ? 'bg-gradient-to-r from-coral-500 to-orange-500 text-white shadow-lg shadow-coral-500/25'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                <span className="mr-2">{step.number}</span>
                {step.title}
              </button>
            ))}
          </div>

          {/* Active Step Content */}
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <div className="space-y-6">
              <div className="text-6xl font-bold bg-gradient-to-r from-coral-500 to-orange-500 bg-clip-text text-transparent">
                {steps[activeTab].number}
              </div>
              <h3 className="text-3xl font-bold text-slate-900">{steps[activeTab].title}</h3>
              <p className="text-lg text-slate-600 leading-relaxed">{steps[activeTab].description}</p>
              <Link
                to="/upload"
                className="inline-flex items-center gap-2 bg-gradient-to-r from-coral-500 to-orange-500 text-white px-6 py-3 rounded-xl font-semibold shadow-lg shadow-coral-500/25 hover:shadow-coral-500/40 transition-all group"
              >
                Try It Now
                <svg className="w-4 h-4 group-hover:translate-x-1 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                </svg>
              </Link>
            </div>
            <div className="relative">
              <div className="absolute inset-0 bg-gradient-to-r from-sky-500 to-periwinkle-500 rounded-2xl transform -rotate-3 scale-105 opacity-10"></div>
              <img
                src={steps[activeTab].image}
                alt={steps[activeTab].title}
                className="relative rounded-2xl shadow-2xl w-full h-96 object-cover"
              />
            </div>
          </div>
        </div>
      </section>

      {/* App Mockup Section - Interactive Demo */}
      <section className="py-24 bg-gradient-to-b from-slate-900 to-slate-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <div className="inline-flex items-center gap-2 bg-white/10 text-white px-4 py-2 rounded-full text-sm font-medium mb-6">
              Live Preview
            </div>
            <h2 className="text-4xl lg:text-5xl font-bold text-white mb-6">
              See Paperbase in action
            </h2>
            <p className="text-xl text-slate-400 max-w-2xl mx-auto">
              Experience the intuitive interface that makes document processing effortless.
            </p>
          </div>

          {/* Large App Mockup */}
          <div className="bg-white/5 backdrop-blur-lg rounded-3xl p-3 shadow-2xl border border-white/10">
            <div className="bg-slate-900 rounded-2xl overflow-hidden">
              {/* Browser chrome */}
              <div className="flex items-center gap-4 px-6 py-4 bg-slate-800 border-b border-slate-700">
                <div className="flex gap-2">
                  <div className="w-3 h-3 rounded-full bg-red-500"></div>
                  <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
                  <div className="w-3 h-3 rounded-full bg-green-500"></div>
                </div>
                <div className="flex-1 flex items-center justify-center">
                  <div className="bg-slate-700 rounded-lg px-4 py-1.5 flex items-center gap-2">
                    <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                    </svg>
                    <span className="text-slate-400 text-sm">app.paperbase.io/documents</span>
                  </div>
                </div>
              </div>

              {/* App Content */}
              <div className="p-8 bg-gradient-to-br from-slate-50 to-slate-100">
                <div className="grid grid-cols-12 gap-6">
                  {/* Sidebar */}
                  <div className="col-span-2 space-y-4">
                    <div className="bg-white rounded-xl shadow-sm p-4">
                      <div className="flex items-center gap-3 mb-4">
                        <div className="w-8 h-8 bg-gradient-to-br from-coral-500 to-orange-500 rounded-lg"></div>
                        <span className="font-bold text-slate-900">Paperbase</span>
                      </div>
                      <nav className="space-y-1">
                        {['Dashboard', 'Documents', 'Templates', 'Search', 'Settings'].map((item, i) => (
                          <div
                            key={i}
                            className={`px-3 py-2 rounded-lg text-sm font-medium ${
                              i === 1 ? 'bg-coral-50 text-coral-600' : 'text-slate-600 hover:bg-slate-50'
                            }`}
                          >
                            {item}
                          </div>
                        ))}
                      </nav>
                    </div>
                  </div>

                  {/* Main Content */}
                  <div className="col-span-10 space-y-6">
                    {/* Header */}
                    <div className="flex justify-between items-center">
                      <div>
                        <h2 className="text-2xl font-bold text-slate-900">Documents</h2>
                        <p className="text-slate-500">12 documents processed today</p>
                      </div>
                      <button className="bg-gradient-to-r from-coral-500 to-orange-500 text-white px-4 py-2 rounded-lg font-medium flex items-center gap-2">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                        </svg>
                        Upload
                      </button>
                    </div>

                    {/* Documents Table */}
                    <div className="bg-white rounded-xl shadow-sm overflow-hidden">
                      <table className="w-full">
                        <thead className="bg-slate-50 border-b border-slate-200">
                          <tr>
                            <th className="text-left py-3 px-4 text-xs font-semibold text-slate-500 uppercase">Document</th>
                            <th className="text-left py-3 px-4 text-xs font-semibold text-slate-500 uppercase">Template</th>
                            <th className="text-left py-3 px-4 text-xs font-semibold text-slate-500 uppercase">Confidence</th>
                            <th className="text-left py-3 px-4 text-xs font-semibold text-slate-500 uppercase">Status</th>
                            <th className="text-left py-3 px-4 text-xs font-semibold text-slate-500 uppercase">Date</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {[
                            { name: 'Invoice_2024_001.pdf', template: 'Invoice', confidence: 95, status: 'complete', date: 'Just now' },
                            { name: 'Contract_ABC.pdf', template: 'Contract', confidence: 92, status: 'complete', date: '2 min ago' },
                            { name: 'Receipt_Nov.pdf', template: 'Receipt', confidence: 88, status: 'review', date: '5 min ago' },
                            { name: 'Application_Form.pdf', template: 'Application', confidence: 97, status: 'complete', date: '10 min ago' },
                          ].map((doc, i) => (
                            <tr key={i} className="hover:bg-slate-50">
                              <td className="py-3 px-4">
                                <div className="flex items-center gap-3">
                                  <div className="w-8 h-8 bg-red-100 rounded flex items-center justify-center">
                                    <svg className="w-4 h-4 text-red-600" fill="currentColor" viewBox="0 0 20 20">
                                      <path fillRule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" clipRule="evenodd" />
                                    </svg>
                                  </div>
                                  <span className="font-medium text-slate-900">{doc.name}</span>
                                </div>
                              </td>
                              <td className="py-3 px-4">
                                <span className="text-slate-600">{doc.template}</span>
                              </td>
                              <td className="py-3 px-4">
                                <div className="flex items-center gap-2">
                                  <div className="w-16 h-2 bg-slate-200 rounded-full overflow-hidden">
                                    <div
                                      className={`h-full rounded-full ${
                                        doc.confidence >= 90 ? 'bg-mint-500' : doc.confidence >= 80 ? 'bg-yellow-500' : 'bg-red-500'
                                      }`}
                                      style={{ width: `${doc.confidence}%` }}
                                    ></div>
                                  </div>
                                  <span className="text-sm text-slate-600">{doc.confidence}%</span>
                                </div>
                              </td>
                              <td className="py-3 px-4">
                                <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${
                                  doc.status === 'complete' ? 'bg-mint-100 text-mint-700' : 'bg-yellow-100 text-yellow-700'
                                }`}>
                                  {doc.status === 'complete' ? (
                                    <>
                                      <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                                      </svg>
                                      Complete
                                    </>
                                  ) : (
                                    <>
                                      <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                                        <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                                      </svg>
                                      Review
                                    </>
                                  )}
                                </span>
                              </td>
                              <td className="py-3 px-4 text-sm text-slate-500">{doc.date}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Use Cases Section */}
      <section id="use-cases" className="py-24 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <div className="inline-flex items-center gap-2 bg-mint-100 text-mint-700 px-4 py-2 rounded-full text-sm font-medium mb-6">
              Use Cases
            </div>
            <h2 className="text-4xl lg:text-5xl font-bold text-slate-900 mb-6">
              Built for{' '}
              <span className="bg-gradient-to-r from-mint-500 to-sky-500 bg-clip-text text-transparent">
                every document type
              </span>
            </h2>
            <p className="text-xl text-slate-600 max-w-2xl mx-auto">
              From simple invoices to complex contracts, Paperbase handles it all with precision.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {useCases.map((useCase, i) => (
              <div key={i} className="group bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden hover:shadow-xl transition-all">
                <div className="relative h-48 overflow-hidden">
                  <img
                    src={useCase.image}
                    alt={useCase.title}
                    className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-500"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-slate-900/60 to-transparent"></div>
                  <h3 className="absolute bottom-4 left-4 text-xl font-bold text-white">{useCase.title}</h3>
                </div>
                <div className="p-6">
                  <p className="text-slate-600 mb-4">{useCase.description}</p>
                  <ul className="space-y-2">
                    {useCase.items.map((item, j) => (
                      <li key={j} className="flex items-center gap-2 text-sm text-slate-600">
                        <svg className="w-4 h-4 text-mint-500 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                        </svg>
                        {item}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Testimonials Section */}
      <section className="py-24 bg-slate-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <div className="inline-flex items-center gap-2 bg-periwinkle-100 text-periwinkle-700 px-4 py-2 rounded-full text-sm font-medium mb-6">
              Testimonials
            </div>
            <h2 className="text-4xl lg:text-5xl font-bold text-slate-900 mb-6">
              Loved by teams{' '}
              <span className="bg-gradient-to-r from-periwinkle-500 to-sky-500 bg-clip-text text-transparent">
                everywhere
              </span>
            </h2>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {testimonials.map((testimonial, i) => (
              <div key={i} className="bg-white rounded-2xl p-8 shadow-sm border border-slate-200">
                <div className="flex gap-1 mb-6">
                  {[...Array(5)].map((_, j) => (
                    <svg key={j} className="w-5 h-5 text-yellow-400" fill="currentColor" viewBox="0 0 20 20">
                      <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                    </svg>
                  ))}
                </div>
                <p className="text-slate-600 mb-6 leading-relaxed">"{testimonial.quote}"</p>
                <div className="flex items-center gap-4">
                  <img
                    src={testimonial.image}
                    alt={testimonial.author}
                    className="w-12 h-12 rounded-full object-cover"
                  />
                  <div>
                    <div className="font-semibold text-slate-900">{testimonial.author}</div>
                    <div className="text-sm text-slate-500">{testimonial.role}, {testimonial.company}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section id="pricing" className="py-24 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <div className="inline-flex items-center gap-2 bg-coral-100 text-coral-700 px-4 py-2 rounded-full text-sm font-medium mb-6">
              Pricing
            </div>
            <h2 className="text-4xl lg:text-5xl font-bold text-slate-900 mb-6">
              Simple, transparent{' '}
              <span className="bg-gradient-to-r from-coral-500 to-orange-500 bg-clip-text text-transparent">
                pricing
              </span>
            </h2>
            <p className="text-xl text-slate-600 max-w-2xl mx-auto">
              Start free, upgrade when you need more. No hidden fees, no surprises.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
            {[
              {
                name: 'Starter',
                price: 'Free',
                description: 'Perfect for trying out Paperbase',
                features: ['50 documents/month', '3 templates', 'Basic search', 'Community support'],
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
                className={`relative rounded-2xl p-8 ${
                  plan.highlighted
                    ? 'bg-gradient-to-br from-slate-900 to-slate-800 text-white shadow-2xl scale-105'
                    : 'bg-white border border-slate-200 shadow-sm'
                }`}
              >
                {plan.highlighted && (
                  <div className="absolute -top-4 left-1/2 -translate-x-1/2">
                    <span className="bg-gradient-to-r from-coral-500 to-orange-500 text-white text-xs font-semibold px-4 py-1 rounded-full">
                      Most Popular
                    </span>
                  </div>
                )}
                <h3 className={`text-xl font-bold ${plan.highlighted ? 'text-white' : 'text-slate-900'}`}>
                  {plan.name}
                </h3>
                <div className="mt-4 flex items-baseline">
                  <span className={`text-5xl font-bold ${plan.highlighted ? 'text-white' : 'text-slate-900'}`}>
                    {plan.price}
                  </span>
                  {plan.period && (
                    <span className={`ml-2 ${plan.highlighted ? 'text-slate-400' : 'text-slate-500'}`}>
                      {plan.period}
                    </span>
                  )}
                </div>
                <p className={`mt-2 ${plan.highlighted ? 'text-slate-400' : 'text-slate-600'}`}>
                  {plan.description}
                </p>
                <ul className="mt-8 space-y-4">
                  {plan.features.map((feature, j) => (
                    <li key={j} className="flex items-center gap-3">
                      <svg
                        className={`w-5 h-5 flex-shrink-0 ${plan.highlighted ? 'text-mint-400' : 'text-mint-500'}`}
                        fill="currentColor"
                        viewBox="0 0 20 20"
                      >
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                      </svg>
                      <span className={plan.highlighted ? 'text-slate-300' : 'text-slate-600'}>{feature}</span>
                    </li>
                  ))}
                </ul>
                <Link
                  to="/upload"
                  className={`mt-8 block w-full py-4 rounded-xl text-center font-semibold transition-all ${
                    plan.highlighted
                      ? 'bg-gradient-to-r from-coral-500 to-orange-500 text-white shadow-lg shadow-coral-500/25 hover:shadow-coral-500/40'
                      : 'bg-slate-900 text-white hover:bg-slate-800'
                  }`}
                >
                  {plan.cta}
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Final CTA Section with Background Image */}
      <section className="relative py-32">
        <div className="absolute inset-0 z-0">
          <img
            src={images.ctaBg}
            alt=""
            className="w-full h-full object-cover"
          />
          <div className="absolute inset-0 bg-gradient-to-r from-coral-600/90 to-orange-500/90"></div>
        </div>

        <div className="relative z-10 max-w-4xl mx-auto text-center px-4 sm:px-6 lg:px-8">
          <h2 className="text-4xl lg:text-5xl font-bold text-white mb-6">
            Ready to transform your document workflow?
          </h2>
          <p className="text-xl text-white/90 mb-10 max-w-2xl mx-auto">
            Join thousands of teams using Paperbase to extract, search, and manage their documents with AI.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              to="/upload"
              className="bg-white text-coral-600 hover:bg-slate-50 px-8 py-4 rounded-xl text-lg font-semibold transition-all shadow-xl flex items-center justify-center gap-2 group"
            >
              Get Started for Free
              <svg className="w-5 h-5 group-hover:translate-x-1 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
            </Link>
            <a
              href="#features"
              className="bg-white/10 backdrop-blur-sm hover:bg-white/20 text-white px-8 py-4 rounded-xl text-lg font-semibold transition-all border border-white/30"
            >
              Learn More
            </a>
          </div>
          <p className="text-white/70 mt-6">No credit card required</p>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-slate-900 text-slate-400 py-16 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="grid md:grid-cols-5 gap-8">
            <div className="col-span-2">
              <div className="flex items-center gap-3 mb-6">
                <div className="w-10 h-10 bg-gradient-to-br from-coral-500 via-orange-400 to-yellow-400 rounded-xl flex items-center justify-center">
                  <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                </div>
                <span className="text-2xl font-bold text-white">Paperbase</span>
              </div>
              <p className="text-slate-400 max-w-xs mb-6">
                AI-powered document intelligence platform. Transform any document into structured, searchable data.
              </p>
              <div className="flex gap-4">
                <a href="#" className="w-10 h-10 bg-slate-800 rounded-lg flex items-center justify-center hover:bg-slate-700 transition-colors">
                  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M8.29 20.251c7.547 0 11.675-6.253 11.675-11.675 0-.178 0-.355-.012-.53A8.348 8.348 0 0022 5.92a8.19 8.19 0 01-2.357.646 4.118 4.118 0 001.804-2.27 8.224 8.224 0 01-2.605.996 4.107 4.107 0 00-6.993 3.743 11.65 11.65 0 01-8.457-4.287 4.106 4.106 0 001.27 5.477A4.072 4.072 0 012.8 9.713v.052a4.105 4.105 0 003.292 4.022 4.095 4.095 0 01-1.853.07 4.108 4.108 0 003.834 2.85A8.233 8.233 0 012 18.407a11.616 11.616 0 006.29 1.84" />
                  </svg>
                </a>
                <a href="#" className="w-10 h-10 bg-slate-800 rounded-lg flex items-center justify-center hover:bg-slate-700 transition-colors">
                  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                    <path fillRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" clipRule="evenodd" />
                  </svg>
                </a>
                <a href="#" className="w-10 h-10 bg-slate-800 rounded-lg flex items-center justify-center hover:bg-slate-700 transition-colors">
                  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                    <path fillRule="evenodd" d="M19 0h-14c-2.761 0-5 2.239-5 5v14c0 2.761 2.239 5 5 5h14c2.762 0 5-2.239 5-5v-14c0-2.761-2.238-5-5-5zm-11 19h-3v-11h3v11zm-1.5-12.268c-.966 0-1.75-.79-1.75-1.764s.784-1.764 1.75-1.764 1.75.79 1.75 1.764-.783 1.764-1.75 1.764zm13.5 12.268h-3v-5.604c0-3.368-4-3.113-4 0v5.604h-3v-11h3v1.765c1.396-2.586 7-2.777 7 2.476v6.759z" clipRule="evenodd" />
                  </svg>
                </a>
              </div>
            </div>

            <div>
              <h4 className="text-white font-semibold mb-4">Product</h4>
              <ul className="space-y-3 text-sm">
                <li><a href="#features" className="hover:text-white transition-colors">Features</a></li>
                <li><a href="#pricing" className="hover:text-white transition-colors">Pricing</a></li>
                <li><a href="#" className="hover:text-white transition-colors">API Docs</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Integrations</a></li>
              </ul>
            </div>

            <div>
              <h4 className="text-white font-semibold mb-4">Company</h4>
              <ul className="space-y-3 text-sm">
                <li><a href="#" className="hover:text-white transition-colors">About Us</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Blog</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Careers</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Contact</a></li>
              </ul>
            </div>

            <div>
              <h4 className="text-white font-semibold mb-4">Legal</h4>
              <ul className="space-y-3 text-sm">
                <li><a href="#" className="hover:text-white transition-colors">Privacy Policy</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Terms of Service</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Security</a></li>
                <li><a href="#" className="hover:text-white transition-colors">GDPR</a></li>
              </ul>
            </div>
          </div>

          <div className="border-t border-slate-800 mt-12 pt-8 flex flex-col md:flex-row justify-between items-center gap-4">
            <p className="text-sm">&copy; 2024 Paperbase. All rights reserved.</p>
            <div className="flex items-center gap-6 text-sm">
              <a href="#" className="hover:text-white transition-colors">Status</a>
              <a href="#" className="hover:text-white transition-colors">Changelog</a>
              <a href="#" className="hover:text-white transition-colors">Support</a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}

export default LandingPage
