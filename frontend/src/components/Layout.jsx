import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import MCPIndicator from './MCPIndicator'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function Layout() {
  const location = useLocation()
  const navigate = useNavigate()
  const [auditQueueCount, setAuditQueueCount] = useState(0)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [showResults, setShowResults] = useState(false)
  const [searching, setSearching] = useState(false)

  const navItems = [
    { path: '/', label: 'Upload' },
    { path: '/documents', label: 'Documents' },
    { path: '/audit', label: 'Audit', badge: auditQueueCount },
    { path: '/query', label: 'Ask AI' },
    { path: '/export', label: 'Export' },
    { path: '/analytics', label: 'Analytics' },
    { path: '/settings', label: 'Settings' },
  ]

  // Fetch audit queue count
  useEffect(() => {
    const fetchAuditCount = async () => {
      try {
        const response = await fetch(`${API_URL}/api/audit/queue?count_only=true`)
        if (response.ok) {
          const data = await response.json()
          setAuditQueueCount(data.count || 0)
        }
      } catch (error) {
        console.error('Failed to fetch audit queue count:', error)
      }
    }

    fetchAuditCount()
    // Refresh count every 30 seconds
    const interval = setInterval(fetchAuditCount, 30000)
    return () => clearInterval(interval)
  }, [])

  // Handle keyword search
  const handleSearch = async (e) => {
    e.preventDefault()
    if (!searchQuery.trim()) return

    setSearching(true)
    try {
      const response = await fetch(
        `${API_URL}/api/folders/search?q=${encodeURIComponent(searchQuery)}`
      )
      if (response.ok) {
        const data = await response.json()
        setSearchResults(data.results || [])
        setShowResults(true)
      }
    } catch (error) {
      console.error('Search failed:', error)
    } finally {
      setSearching(false)
    }
  }

  // Close search results when clicking outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (!e.target.closest('.search-container')) {
        setShowResults(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Navigate to document
  const handleResultClick = (result) => {
    setShowResults(false)
    setSearchQuery('')
    navigate(`/audit/document/${result.id}`)
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center flex-1">
              <div className="flex-shrink-0 flex items-center">
                <h1 className="text-xl font-bold text-gray-900">Paperbase</h1>
              </div>
              <div className="hidden sm:ml-6 sm:flex sm:space-x-8">
                {navItems.map((item) => (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={`inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium ${
                      location.pathname === item.path
                        ? 'border-blue-500 text-gray-900'
                        : 'border-transparent text-gray-500 hover:border-blue-300 hover:text-gray-700'
                    }`}
                  >
                    {item.label}
                    {item.badge > 0 && (
                      <span className="ml-2 bg-red-500 text-white text-xs font-semibold px-2 py-0.5 rounded-full">
                        {item.badge}
                      </span>
                    )}
                  </Link>
                ))}
              </div>
            </div>

            {/* Search Bar */}
            <div className="flex items-center gap-4 search-container relative">
              {/* MCP Indicator */}
              <MCPIndicator />

              <form onSubmit={handleSearch} className="relative">
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search documents..."
                  className="w-64 px-4 py-2 pr-10 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                />
                <button
                  type="submit"
                  disabled={searching}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                >
                  {searching ? (
                    <div className="animate-spin h-5 w-5 border-2 border-gray-300 border-t-blue-600 rounded-full"></div>
                  ) : (
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                    </svg>
                  )}
                </button>
              </form>

              {/* Search Results Dropdown */}
              {showResults && (
                <div className="absolute top-full right-0 mt-2 w-96 bg-white rounded-lg shadow-lg border border-gray-200 max-h-96 overflow-y-auto z-50">
                  {searchResults.length === 0 ? (
                    <div className="p-4 text-center text-gray-500">
                      No documents found for "{searchQuery}"
                    </div>
                  ) : (
                    <div className="py-2">
                      <div className="px-4 py-2 text-xs text-gray-500 font-medium border-b border-gray-100">
                        {searchResults.length} result{searchResults.length !== 1 ? 's' : ''}
                      </div>
                      {searchResults.map((result) => (
                        <button
                          key={result.id}
                          onClick={() => handleResultClick(result)}
                          className="w-full px-4 py-3 hover:bg-gray-50 text-left border-b border-gray-100 last:border-b-0"
                        >
                          <div className="flex items-start justify-between">
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-medium text-gray-900 truncate">
                                {result.filename}
                              </p>
                              {result.template_name && (
                                <p className="text-xs text-gray-500 mt-1">
                                  Template: {result.template_name}
                                </p>
                              )}
                            </div>
                            <svg className="w-4 h-4 text-gray-400 ml-2 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                            </svg>
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <Outlet />
      </main>
    </div>
  )
}

export default Layout
