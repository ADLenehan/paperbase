import { Link } from 'react-router-dom';
import { useState, useEffect } from 'react';

const Landing = () => {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 20);
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <div className="relative min-h-screen bg-white overflow-hidden font-display">
      <div className="relative">
        {/* Navigation */}
        <nav className="fixed top-0 left-0 right-0 z-50 bg-white border-b border-border" style={{ fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif' }}>
          <div className="container-max section-padding">
            <div className="flex items-center justify-between h-16 md:h-20">
              {/* Logo */}
              <Link to="/" className="flex items-center">
                <span className="text-2xl font-display" style={{ fontWeight: 500 }}>PaperBase</span>
              </Link>

              {/* Center Nav Links */}
              <div className="hidden md:flex items-center space-x-8">
                <a href="#features" className="text-sm uppercase tracking-wide font-medium text-muted-foreground hover:text-foreground transition-colors">
                  Features
                </a>
                <a href="#how-it-works" className="text-sm uppercase tracking-wide font-medium text-muted-foreground hover:text-foreground transition-colors">
                  How It Works
                </a>
              </div>

              {/* Right Side - Login + Button */}
              <div className="hidden md:flex items-center space-x-4">
                <Link to="/login" className="text-sm uppercase tracking-wide font-medium text-muted-foreground hover:text-foreground transition-colors">
                  Login
                </Link>
                <button
                  onClick={() => window.location.href = '/login'}
                  className="inline-flex items-center justify-center font-medium transition-all duration-200 rounded-full focus:outline-none focus:ring-2 focus:ring-offset-2 ring-offset-background shadow-sm hover:shadow-md bg-coral-500 text-white hover:bg-coral-600 focus:ring-coral-500 px-4 py-2 text-sm"
                >
                  Try 10 Docs Free
                </button>
              </div>

              {/* Mobile menu button */}
              <button className="md:hidden p-2 text-muted-foreground hover:text-foreground">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              </button>
            </div>
          </div>
        </nav>

        {/* Hero Section */}
        <section className="py-20 md:py-28 bg-white">
          <div className="container-max section-padding">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center max-w-7xl mx-auto">
              {/* Left: Text Content */}
              <div>
                <h1 className="font-display text-display-md md:text-display-lg mb-6">
                  Extract Data from Documents with 100% Accuracy
                </h1>
                <p className="text-xl md:text-2xl text-muted-foreground mb-8" style={{ fontWeight: 300, fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif' }}>
                  AI-powered extraction meets human validation. Process 100 documents in minutes with perfect accuracy.
                </p>
                <div className="flex flex-col sm:flex-row gap-4 mb-8">
                  <Link
                    to="/login"
                    className="inline-flex items-center justify-center font-medium transition-all duration-200 rounded-full focus:outline-none focus:ring-2 focus:ring-offset-2 ring-offset-background shadow-sm hover:shadow-md px-8 py-3.5 text-lg relative bg-gradient-to-r from-coral-500 to-orange-400 text-white hover:from-coral-600 hover:to-orange-500 shadow-lg hover:shadow-xl"
                  >
                    <span className="absolute -z-10 inset-0 rounded-full shadow-[0_0_0_10px_rgba(233,117,99,0.18)] pointer-events-none" aria-hidden="true"></span>
                    <svg className="mr-2 h-5 w-5 md:h-6 md:w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                    </svg>
                    Start Free Trial
                  </Link>
                </div>
                {/* Trust signals with colored badges */}
                <div className="flex flex-wrap gap-3">
                  <span className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-coral-50 border border-coral-200">
                    <svg className="w-4 h-4 text-coral-600" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                    </svg>
                    <span className="text-sm font-medium text-coral-700">Try 10 Documents Free</span>
                  </span>
                  <span className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-coral-50 border border-coral-200">
                    <svg className="w-4 h-4 text-coral-600" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                    </svg>
                    <span className="text-sm font-medium text-coral-700">100% Accuracy Guaranteed</span>
                  </span>
                </div>
              </div>

              {/* Right: Hero Image */}
              <div>
                <div className="rounded-2xl overflow-hidden">
                  <img
                    src="/images/Gemini_Generated_Image_c5sqfkc5sqfkc5sq.png"
                    alt="Document processing workflow"
                    className="w-full h-auto"
                  />
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Problem Gallery */}
        <section className="py-20 md:py-28 bg-white">
          <div className="container-max section-padding">
            <div className="max-w-6xl mx-auto">
              <h2 className="text-center mb-4">The Data Extraction Challenge</h2>
              <p className="text-center text-muted-foreground mb-12 text-lg md:text-xl" style={{ fontWeight: 300, fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif' }}>
                Traditional approaches to extracting structured data from documents fall short
              </p>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-12 max-w-6xl mx-auto">
                {/* Problem 1: Pure AI */}
                <div className="relative">
                  <h3 className="font-display text-3xl md:text-4xl mb-6" style={{ fontWeight: 300 }}>Pure AI Not Precise Enough for Most Industries</h3>
                  <div className="aspect-[4/3] rounded-xl overflow-hidden mb-6">
                    <img
                      src="/images/Gemini_Generated_Image_4eb3a34eb3a34eb3.png"
                      alt="Filing cabinet chaos"
                      className="w-full h-full object-cover"
                    />
                  </div>
                  <p className="text-muted-foreground text-lg mb-4" style={{ fontWeight: 300, fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif' }}>
                    OCR and AI tools achieve 85-95% accuracy - insufficient for regulated industries requiring 100% precision
                  </p>
                  <span className="inline-block px-4 py-2 rounded-full bg-coral-50 border border-coral-200 text-coral-700 text-sm font-medium">
                    85-95% accuracy isn't enough
                  </span>
                </div>

                {/* Problem 2: Manual Entry */}
                <div className="relative">
                  <h3 className="font-display text-3xl md:text-4xl mb-6" style={{ fontWeight: 300 }}>Manual Entry is Costly and Error-Prone</h3>
                  <div className="aspect-[4/3] rounded-xl overflow-hidden mb-6">
                    <img
                      src="/images/Gemini_Generated_Image_eeth86eeth86eeth.png"
                      alt="Woman drowning in papers"
                      className="w-full h-full object-cover"
                    />
                  </div>
                  <p className="text-muted-foreground text-lg mb-4" style={{ fontWeight: 300, fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif' }}>
                    Human data entry is slow, expensive, and still makes mistakes. Teams spend 20+ hours/week on repetitive typing.
                  </p>
                  <span className="inline-block px-4 py-2 rounded-full bg-coral-50 border border-coral-200 text-coral-700 text-sm font-medium">
                    20+ hrs/week wasted
                  </span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* How It Works - Merged with See It In Action */}
        <section id="how-it-works" className="py-20 md:py-28 bg-white">
          <div className="container-max section-padding">
            <div className="max-w-6xl mx-auto">
              <h2 className="text-center mb-4">How It Works</h2>
              <p className="text-center text-muted-foreground mb-12 text-lg md:text-xl" style={{ fontWeight: 300, fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif' }}>
                AI handles the speed, you ensure the accuracy
              </p>

              {/* 4-Step Process */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-20">
                {/* Step 1 */}
                <div className="relative rounded-xl bg-white overflow-hidden border-2 border-border hover:border-coral-500 transition-colors shadow-sm p-6">
                  <div className="mb-4">
                    <div className="w-16 h-16 bg-coral-100 rounded-full flex items-center justify-center mb-4">
                      <svg className="w-8 h-8 text-coral-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                      </svg>
                    </div>
                  </div>
                  <h3 className="font-semibold text-lg mb-3">Upload & Match</h3>
                  <p className="text-muted-foreground text-sm">
                    Upload PDFs in bulk. Claude AI automatically matches documents to extraction templates.
                  </p>
                </div>

                {/* Step 2 */}
                <div className="relative rounded-xl bg-white overflow-hidden border-2 border-border hover:border-sky-400 transition-colors shadow-sm p-6">
                  <div className="mb-4">
                    <div className="w-16 h-16 bg-sky-100 rounded-full flex items-center justify-center mb-4">
                      <svg className="w-8 h-8 text-sky-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                    </div>
                  </div>
                  <h3 className="font-semibold text-lg mb-3">AI Extract</h3>
                  <p className="text-muted-foreground text-sm">
                    Reducto AI parses documents and extracts all fields with confidence scores for each value.
                  </p>
                </div>

                {/* Step 3 */}
                <div className="relative rounded-xl bg-white overflow-hidden border-2 border-border hover:border-yellow-400 transition-colors shadow-sm p-6">
                  <div className="mb-4">
                    <div className="w-16 h-16 bg-yellow-100 rounded-full flex items-center justify-center mb-4">
                      <svg className="w-8 h-8 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                    </div>
                  </div>
                  <h3 className="font-semibold text-lg mb-3">Human Audit</h3>
                  <p className="text-muted-foreground text-sm">
                    Low-confidence fields flagged for review. Verify in &lt;10s with inline PDF viewer. 100% accuracy.
                  </p>
                </div>

                {/* Step 4 */}
                <div className="relative rounded-xl bg-white overflow-hidden border-2 border-border hover:border-coral-500 transition-colors shadow-sm p-6">
                  <div className="mb-4">
                    <div className="w-16 h-16 bg-coral-100 rounded-full flex items-center justify-center mb-4">
                      <svg className="w-8 h-8 text-coral-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                      </svg>
                    </div>
                  </div>
                  <h3 className="font-semibold text-lg mb-3">Search & Export</h3>
                  <p className="text-muted-foreground text-sm">
                    Ask questions in plain English. Elasticsearch powers instant search across all extracted data.
                  </p>
                </div>
              </div>

              {/* Demo Image */}
              <div className="mt-16 mb-20 max-w-4xl mx-auto">
                <div className="rounded-2xl overflow-hidden">
                  <img
                    src="/images/Gemini_Generated_Image_p68et1p68et1p68e.png"
                    alt="Workflow automation demo"
                    className="w-full h-auto"
                  />
                </div>
              </div>

              {/* Capabilities with Product Screenshots */}
              <div className="space-y-16">
                {/* Capability 1: Bulk Upload */}
                <div className="grid lg:grid-cols-2 gap-8 items-center">
                  <div>
                    <div className="inline-block px-3 py-1 rounded-full bg-coral-50 border border-coral-200 text-coral-700 text-xs font-medium mb-4">
                      Template Matching
                    </div>
                    <h3 className="text-2xl font-semibold mb-4">Upload 100 Documents, AI Matches Templates</h3>
                    <p className="text-muted-foreground text-lg mb-6">
                      Drop in invoices, contracts, receipts - Claude AI analyzes content and automatically selects the right extraction template for each document type. No manual configuration required.
                    </p>
                    <ul className="space-y-3">
                      <li className="flex items-start gap-3">
                        <span className="text-coral-500 text-xl font-bold">✓</span>
                        <span className="text-muted-foreground">Batch upload: process 100+ documents at once</span>
                      </li>
                      <li className="flex items-start gap-3">
                        <span className="text-coral-500 text-xl font-bold">✓</span>
                        <span className="text-muted-foreground">Auto-grouping: similar documents grouped together</span>
                      </li>
                      <li className="flex items-start gap-3">
                        <span className="text-coral-500 text-xl font-bold">✓</span>
                        <span className="text-muted-foreground">Smart matching: Claude suggests best template per group</span>
                      </li>
                    </ul>
                  </div>
                  <div className="rounded-xl overflow-hidden bg-gray-100 aspect-[4/3] flex items-center justify-center border-2 border-dashed border-gray-300">
                    <span className="text-gray-400 text-lg font-medium">Product Screenshot: Bulk Upload UI</span>
                  </div>
                </div>

                {/* Capability 2: Inline Audit */}
                <div className="grid lg:grid-cols-2 gap-8 items-center">
                  <div className="rounded-xl overflow-hidden bg-gray-100 aspect-[4/3] flex items-center justify-center border-2 border-dashed border-gray-300 lg:order-1">
                    <span className="text-gray-400 text-lg font-medium">Product Screenshot: Inline Audit Modal</span>
                  </div>
                  <div className="lg:order-2">
                    <div className="inline-block px-3 py-1 rounded-full bg-yellow-50 border border-yellow-200 text-yellow-700 text-xs font-medium mb-4">
                      Human-in-the-Loop
                    </div>
                    <h3 className="text-2xl font-semibold mb-4">Verify Low-Confidence Fields in Seconds</h3>
                    <p className="text-muted-foreground text-lg mb-6">
                      AI flags uncertain extractions for quick human review. Click a field, see the PDF source highlighted, verify in &lt;10 seconds. This is how you achieve 100% accuracy without manual data entry.
                    </p>
                    <ul className="space-y-3">
                      <li className="flex items-start gap-3">
                        <span className="text-coral-500 text-xl font-bold">✓</span>
                        <span className="text-muted-foreground">Inline PDF viewer: see exact source of extracted data</span>
                      </li>
                      <li className="flex items-start gap-3">
                        <span className="text-coral-500 text-xl font-bold">✓</span>
                        <span className="text-muted-foreground">Confidence scores: AI tells you which fields need review</span>
                      </li>
                      <li className="flex items-start gap-3">
                        <span className="text-coral-500 text-xl font-bold">✓</span>
                        <span className="text-muted-foreground">10-second validation: 3x faster than previous workflow</span>
                      </li>
                    </ul>
                  </div>
                </div>

                {/* Capability 3: Natural Language Search */}
                <div className="grid lg:grid-cols-2 gap-8 items-center">
                  <div>
                    <div className="inline-block px-3 py-1 rounded-full bg-sky-50 border border-sky-200 text-sky-700 text-xs font-medium mb-4">
                      Powered by Elasticsearch
                    </div>
                    <h3 className="text-2xl font-semibold mb-4">Ask Questions, Get Instant Answers</h3>
                    <p className="text-muted-foreground text-lg mb-6">
                      Forget complex queries. Ask "Show me invoices over $1000 from last quarter" and get instant results. Claude translates your question into Elasticsearch queries, searching across all extracted data.
                    </p>
                    <ul className="space-y-3">
                      <li className="flex items-start gap-3">
                        <span className="text-coral-500 text-xl font-bold">✓</span>
                        <span className="text-muted-foreground">Natural language: ask questions in plain English</span>
                      </li>
                      <li className="flex items-start gap-3">
                        <span className="text-coral-500 text-xl font-bold">✓</span>
                        <span className="text-muted-foreground">Instant search: Elasticsearch powers sub-200ms queries</span>
                      </li>
                      <li className="flex items-start gap-3">
                        <span className="text-coral-500 text-xl font-bold">✓</span>
                        <span className="text-muted-foreground">Complex filters: search across multiple fields and dates</span>
                      </li>
                    </ul>
                  </div>
                  <div className="rounded-xl overflow-hidden bg-gray-100 aspect-[4/3] flex items-center justify-center border-2 border-dashed border-gray-300">
                    <span className="text-gray-400 text-lg font-medium">Product Screenshot: Natural Language Search</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Final CTA */}
        <section className="py-28 md:py-36 bg-white">
          <div className="container-max section-padding">
            <div className="max-w-4xl mx-auto text-center">
              <h2 className="font-display text-3xl md:text-4xl mb-8 text-center">
                Try 10 Documents Free
              </h2>
              <p className="text-lg md:text-xl text-muted-foreground mb-8" style={{ fontWeight: 300, fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif' }}>
                See how PaperBase extracts data with 100% accuracy. Upload, extract, validate - free trial, no credit card required.
              </p>
              <div className="flex justify-center mb-12">
                <Link
                  to="/login"
                  className="inline-flex items-center justify-center font-medium transition-all duration-200 rounded-full focus:outline-none focus:ring-2 focus:ring-offset-2 ring-offset-background shadow-sm hover:shadow-md px-8 py-3.5 text-lg relative bg-gradient-to-r from-sky-500 to-sky-400 text-white hover:from-sky-600 hover:to-sky-500 shadow-lg hover:shadow-xl h-16"
                >
                  <span className="absolute -z-10 inset-0 rounded-full shadow-[0_0_0_10px_rgba(56,189,248,0.18)] pointer-events-none" aria-hidden="true"></span>
                  <svg className="mr-2 h-5 w-5 md:h-6 md:w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                  </svg>
                  Start Free Trial
                </Link>
              </div>
              <p className="text-base text-muted-foreground mt-6 px-4">
                ✅ Try 10 documents free • ✅ No credit card required
              </p>
            </div>
          </div>
        </section>

        {/* Hero Image Section - Before Footer */}
        <section className="py-0 bg-white">
          <div className="container-max section-padding">
            <div className="max-w-7xl mx-auto">
              <div className="lg:w-1/2 mx-auto">
                <img
                  src="/images/Gemini_Generated_Image_do3nuddo3nuddo3n.png"
                  alt="Document processing chaos"
                  className="w-full h-auto rounded-2xl"
                />
              </div>
            </div>
          </div>
        </section>

        {/* Footer */}
        <footer className="border-t border-border bg-white">
          <div className="container-max section-padding py-16 md:py-20">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-8 mb-12">
              <div className="col-span-2 md:col-span-1">
                <Link to="/" className="inline-flex">
                  <span className="text-2xl font-display" style={{ fontWeight: 600 }}>PaperBase</span>
                </Link>
                <p className="mt-4 text-sm text-muted-foreground">
                  AI for Document Processing
                </p>
              </div>

              <div>
                <h3 className="font-semibold text-sm mb-3">Product</h3>
                <ul className="space-y-2">
                  <li><a className="text-sm text-muted-foreground hover:text-foreground transition-colors" href="#features">Features</a></li>
                  <li><a className="text-sm text-muted-foreground hover:text-foreground transition-colors" href="#how-it-works">How It Works</a></li>
                </ul>
              </div>

              <div>
                <h3 className="font-semibold text-sm mb-3">Company</h3>
                <ul className="space-y-2">
                  <li><Link className="text-sm text-muted-foreground hover:text-foreground transition-colors" to="/login">Login</Link></li>
                </ul>
              </div>

              <div>
                <h3 className="font-semibold text-sm mb-3">Legal</h3>
                <ul className="space-y-2">
                  <li><a className="text-sm text-muted-foreground hover:text-foreground transition-colors" href="#">Privacy</a></li>
                  <li><a className="text-sm text-muted-foreground hover:text-foreground transition-colors" href="#">Terms</a></li>
                </ul>
              </div>
            </div>

            <div className="pt-8 border-t border-border">
              <div className="flex flex-col md:flex-row justify-between items-center space-y-4 md:space-y-0">
                <p className="text-sm text-muted-foreground">
                  © 2024 PaperBase. Built with Claude Code.
                </p>
              </div>
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
};

export default Landing;
