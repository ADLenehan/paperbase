import { useState, useEffect, useRef } from 'react'
import apiClient from '../api/client'

function NaturalLanguageQuery() {
  const [messages, setMessages] = useState([])
  const [inputValue, setInputValue] = useState('')
  const [loading, setLoading] = useState(false)
  const [suggestions, setSuggestions] = useState([])
  const messagesEndRef = useRef(null)

  useEffect(() => {
    fetchSuggestions()
    // Add welcome message
    setMessages([{
      type: 'assistant',
      content: 'Hi! Ask me anything about your documents. Try questions like "Show me all invoices over $1,000" or "What\'s the total spending by vendor this year?"',
      timestamp: new Date()
    }])
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  const fetchSuggestions = async () => {
    try {
      const response = await apiClient.get('/api/query/suggestions')
      setSuggestions(response.data.suggestions || [])
    } catch (error) {
      console.error('Error fetching suggestions:', error)
    }
  }

  const handleSubmit = async (e, suggestedQuery = null) => {
    if (e) e.preventDefault()

    const query = suggestedQuery || inputValue
    if (!query.trim()) return

    // Add user message
    const userMessage = {
      type: 'user',
      content: query,
      timestamp: new Date()
    }
    setMessages(prev => [...prev, userMessage])
    setInputValue('')
    setLoading(true)

    try {
      // Build conversation history
      const conversationHistory = messages
        .filter(m => m.type === 'user' || m.type === 'assistant')
        .slice(-4) // Last 2 exchanges
        .map(m => ({
          query: m.type === 'user' ? m.content : '',
          answer: m.type === 'assistant' ? m.content : ''
        }))
        .filter(h => h.query || h.answer)

      const response = await apiClient.post('/api/query/natural-language', {
        query,
        conversation_history: conversationHistory
      })

      const data = response.data

      // Check if clarification is needed
      if (data.clarifying_question) {
        setMessages(prev => [...prev, {
          type: 'assistant',
          content: data.clarifying_question,
          timestamp: new Date(),
          isClarification: true
        }])
        setLoading(false)
        return
      }

      // Add assistant response
      const assistantMessage = {
        type: 'assistant',
        content: data.summary,
        timestamp: new Date(),
        results: data.results || [],
        totalCount: data.total_count || 0,
        queryExplanation: data.query_explanation || '',
        suggestedActions: data.suggested_actions || [],
        aggregations: data.aggregations
      }
      setMessages(prev => [...prev, assistantMessage])

    } catch (error) {
      console.error('Query error:', error)
      setMessages(prev => [...prev, {
        type: 'error',
        content: error.response?.data?.detail || 'Sorry, I encountered an error processing your query. Please try again.',
        timestamp: new Date()
      }])
    } finally {
      setLoading(false)
    }
  }

  const handleSuggestionClick = (query) => {
    setInputValue(query)
    handleSubmit(null, query)
  }

  const formatAggregations = (aggregations) => {
    if (!aggregations) return null

    if (aggregations.type === 'sum') {
      return (
        <div className="mt-3 p-4 bg-blue-50 rounded-lg border border-blue-200">
          <div className="text-sm font-semibold text-blue-900 mb-1">Total</div>
          <div className="text-2xl font-bold text-blue-700">
            ${aggregations.total?.toLocaleString() || 0}
          </div>
          <div className="text-xs text-blue-600 mt-1">
            {aggregations.field}
          </div>
        </div>
      )
    }

    if (aggregations.type === 'avg') {
      return (
        <div className="mt-3 p-4 bg-green-50 rounded-lg border border-green-200">
          <div className="text-sm font-semibold text-green-900 mb-1">Average</div>
          <div className="text-2xl font-bold text-green-700">
            ${aggregations.average?.toLocaleString() || 0}
          </div>
          <div className="text-xs text-green-600 mt-1">
            across {aggregations.count} documents
          </div>
        </div>
      )
    }

    if (aggregations.type === 'group_by' && aggregations.groups) {
      const sortedGroups = Object.entries(aggregations.groups)
        .sort((a, b) => b[1].total - a[1].total)
        .slice(0, 5)

      return (
        <div className="mt-3 space-y-2">
          <div className="text-sm font-semibold text-gray-700 mb-2">Breakdown by {aggregations.field}</div>
          {sortedGroups.map(([key, value]) => (
            <div key={key} className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
              <span className="font-medium text-gray-900">{key}</span>
              <div className="text-right">
                <div className="font-bold text-gray-900">
                  ${value.total?.toLocaleString() || 0}
                </div>
                <div className="text-xs text-gray-500">
                  {value.count} document{value.count !== 1 ? 's' : ''}
                </div>
              </div>
            </div>
          ))}
        </div>
      )
    }

    if (aggregations.type === 'count') {
      return (
        <div className="mt-3 p-4 bg-purple-50 rounded-lg border border-purple-200">
          <div className="text-sm font-semibold text-purple-900 mb-1">Count</div>
          <div className="text-2xl font-bold text-purple-700">
            {aggregations.count}
          </div>
          <div className="text-xs text-purple-600 mt-1">documents</div>
        </div>
      )
    }

    return null
  }

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="bg-white border-b border-gray-200 px-6 py-4">
          <h1 className="text-2xl font-bold text-gray-900">Natural Language Search</h1>
          <p className="text-sm text-gray-600 mt-1">
            Ask questions about your documents in plain English
          </p>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {messages.map((message, index) => (
            <div
              key={index}
              className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-3xl ${
                  message.type === 'user'
                    ? 'bg-blue-600 text-white rounded-2xl rounded-tr-sm'
                    : message.type === 'error'
                    ? 'bg-red-50 text-red-900 rounded-2xl rounded-tl-sm border border-red-200'
                    : 'bg-white text-gray-900 rounded-2xl rounded-tl-sm shadow-sm border border-gray-200'
                } px-4 py-3`}
              >
                {/* Message Content */}
                <div className="text-sm leading-relaxed whitespace-pre-wrap">
                  {message.content}
                </div>

                {/* Query Explanation */}
                {message.queryExplanation && (
                  <div className="mt-2 pt-2 border-t border-gray-200 text-xs text-gray-500">
                    <span className="font-semibold">What I searched for:</span> {message.queryExplanation}
                  </div>
                )}

                {/* Aggregations */}
                {message.aggregations && formatAggregations(message.aggregations)}

                {/* Results Preview */}
                {message.results && message.results.length > 0 && (
                  <div className="mt-3 space-y-2">
                    <div className="text-xs font-semibold text-gray-500 mb-2">
                      Showing {Math.min(message.results.length, 5)} of {message.totalCount} results
                    </div>
                    {message.results.slice(0, 5).map((result, idx) => (
                      <div
                        key={idx}
                        className="p-3 bg-gray-50 rounded-lg border border-gray-200 hover:border-blue-300 transition-colors"
                      >
                        <div className="flex justify-between items-start mb-2">
                          <span className="text-sm font-semibold text-gray-900">
                            {result.filename || 'Unknown File'}
                          </span>
                          {result.score > 0 && (
                            <span className="text-xs text-gray-500">
                              {(result.score * 10).toFixed(1)}% match
                            </span>
                          )}
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-xs">
                          {Object.entries(result.data || {})
                            .filter(([key]) => !['filename', 'full_text', 'confidence_scores', 'document_id'].includes(key))
                            .slice(0, 4)
                            .map(([key, value]) => (
                              <div key={key}>
                                <span className="text-gray-500 capitalize">
                                  {key.replace(/_/g, ' ')}:
                                </span>
                                <span className="ml-1 text-gray-900 font-medium">
                                  {value?.toString() || 'N/A'}
                                </span>
                              </div>
                            ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Suggested Actions */}
                {message.suggestedActions && message.suggestedActions.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-gray-200">
                    <div className="text-xs font-semibold text-gray-600 mb-2">
                      💡 Suggested actions:
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {message.suggestedActions.map((action, idx) => (
                        <button
                          key={idx}
                          className="text-xs px-3 py-1 bg-blue-50 text-blue-700 rounded-full hover:bg-blue-100 transition-colors"
                          onClick={() => handleSuggestionClick(action)}
                        >
                          {action}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Timestamp */}
                <div className="text-xs text-gray-400 mt-2">
                  {message.timestamp?.toLocaleTimeString()}
                </div>
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex justify-start">
              <div className="bg-white rounded-2xl rounded-tl-sm shadow-sm border border-gray-200 px-4 py-3">
                <div className="flex space-x-2">
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="bg-white border-t border-gray-200 px-6 py-4">
          <form onSubmit={handleSubmit} className="flex gap-3">
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="Ask about your documents... (e.g., 'Show me invoices over $5,000 from last month')"
              className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !inputValue.trim()}
              className="bg-blue-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Thinking...' : 'Ask'}
            </button>
          </form>
        </div>
      </div>

      {/* Sidebar with Suggestions */}
      <div className="w-80 bg-white border-l border-gray-200 overflow-y-auto">
        <div className="p-6">
          <h2 className="text-lg font-bold text-gray-900 mb-4">💡 Example Questions</h2>

          {suggestions.map((category, idx) => (
            <div key={idx} className="mb-6">
              <h3 className="text-sm font-semibold text-gray-700 mb-2">
                {category.category}
              </h3>
              <div className="space-y-2">
                {category.queries?.map((query, qIdx) => (
                  <button
                    key={qIdx}
                    onClick={() => handleSuggestionClick(query)}
                    className="w-full text-left text-sm px-3 py-2 bg-gray-50 hover:bg-blue-50 hover:text-blue-700 text-gray-700 rounded-lg transition-colors"
                  >
                    {query}
                  </button>
                ))}
              </div>
            </div>
          ))}

          <div className="mt-8 p-4 bg-blue-50 rounded-lg border border-blue-200">
            <h3 className="text-sm font-semibold text-blue-900 mb-2">
              🎯 Tips for Better Results
            </h3>
            <ul className="text-xs text-blue-800 space-y-1">
              <li>• Be specific with amounts and dates</li>
              <li>• Use relative dates like "last month", "Q4"</li>
              <li>• Ask for totals, averages, or counts</li>
              <li>• Compare time periods</li>
              <li>• Look for patterns and anomalies</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}

export default NaturalLanguageQuery
