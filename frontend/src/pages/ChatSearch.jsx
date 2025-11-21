import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { MCPBanner } from '../components/MCPIndicator';
import AnswerWithAudit from '../components/AnswerWithAudit';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function ChatSearch() {
  const navigate = useNavigate();

  // Chat state
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  // Template filter state
  const [templates, setTemplates] = useState([]);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [loadingTemplates, setLoadingTemplates] = useState(true);

  useEffect(() => {
    fetchTemplates();
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const fetchTemplates = async () => {
    try {
      setLoadingTemplates(true);
      const response = await fetch(`${API_URL}/api/templates`);
      const data = await response.json();
      setTemplates(data.templates || []);
    } catch (err) {
      console.error('Failed to fetch templates:', err);
      setTemplates([]);
    } finally {
      setLoadingTemplates(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMessage = { role: 'user', content: input };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      // Build conversation history
      const history = messages
        .filter(m => m.role !== 'system')
        .map(m => ({
          query: m.role === 'user' ? m.content : '',
          answer: m.role === 'assistant' ? m.content : ''
        }))
        .filter(h => h.query || h.answer);

      // Create AbortController for timeout
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 second timeout

      const response = await fetch(`${API_URL}/api/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: input,
          conversation_history: history,
          template_id: selectedTemplate || null  // Filter by template if selected
        }),
        signal: controller.signal
      });

      clearTimeout(timeoutId);

      let data;
      try {
        data = await response.json();
      } catch (parseError) {
        console.error('Failed to parse response:', parseError);
        throw new Error('Server returned invalid response. Is Elasticsearch running?');
      }

      if (!response.ok) {
        throw new Error(data.detail || data.message || 'Search failed');
      }

      // Add assistant response with audit metadata
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.answer,
        explanation: data.explanation,
        results: data.results,
        total: data.total,
        // Audit metadata fields
        answer_metadata: data.answer_metadata,
        audit_items: data.audit_items,
        audit_items_filtered_count: data.audit_items_filtered_count,
        audit_items_total_count: data.audit_items_total_count,
        confidence_summary: data.confidence_summary,
        // Field lineage tracking
        field_lineage: data.field_lineage,
        // NEW: Query history tracking
        query_id: data.query_id,
        documents_link: data.documents_link
      }]);

    } catch (err) {
      console.error('Search error:', err);
      let errorMessage = err.message;
      let troubleshooting = [];

      if (err.name === 'AbortError') {
        errorMessage = 'Search request timed out after 30 seconds.';
        troubleshooting = [
          'Elasticsearch may be starting up (takes ~30 seconds)',
          'Check if Docker has enough memory (4GB+ recommended)',
          'Try your query again in a moment'
        ];
      } else if (err.message.includes('Failed to fetch')) {
        errorMessage = 'Could not connect to the server.';
        troubleshooting = [
          'Check if the backend is running on port 8000',
          'Verify Docker Compose services are up',
          'Run: docker-compose ps to check status'
        ];
      } else if (err.message.includes('Connection error') || err.message.includes('9200')) {
        errorMessage = 'Elasticsearch is not available.';
        troubleshooting = [
          'Start Elasticsearch: docker-compose up -d elasticsearch',
          'Wait 20-30 seconds for Elasticsearch to initialize',
          'Check status: curl http://localhost:9200/_cluster/health'
        ];
      }

      const troubleshootingText = troubleshooting.length > 0
        ? '\n\n💡 **Troubleshooting:**\n' + troubleshooting.map(t => `- ${t}`).join('\n')
        : '';

      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `❌ **${errorMessage}**${troubleshootingText}`,
        error: true
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleViewExtraction = (extractionId) => {
    navigate(`/extractions/${extractionId}`);
  };

  // Helper function to safely extract document IDs from various formats
  const extractDocumentIds = (message) => {
    // Try multiple sources in order of preference
    const sources = message.answer_metadata?.sources_used || [];

    if (!Array.isArray(sources) || sources.length === 0) {
      // Fallback: extract from results
      return (message.results || [])
        .map(r => r.document_id)
        .filter(id => id != null);
    }

    // Handle different formats of sources_used
    return sources.map(source => {
      // If it's already a number, return it
      if (typeof source === 'number') return source;

      // If it's an object with document_id
      if (typeof source === 'object' && source.document_id) return source.document_id;

      // If it's an object with id
      if (typeof source === 'object' && source.id) return source.id;

      // If it's a string that might be a number
      if (typeof source === 'string') {
        const parsed = parseInt(source, 10);
        return isNaN(parsed) ? null : parsed;
      }

      return null;
    }).filter(id => id != null);
  };

  // Handler for field verification from inline modal
  const handleFieldVerified = async (messageIndex, fieldId, action, correctedValue, notes) => {
    try {
      const message = messages[messageIndex];

      // Safely extract document IDs from various formats
      const documentIds = extractDocumentIds(message);

      // Call verify-and-regenerate endpoint
      const response = await fetch(`${API_URL}/api/audit/verify-and-regenerate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          field_id: fieldId,
          action: action,
          corrected_value: correctedValue,
          notes: notes,
          original_query: messages[messageIndex - 1]?.content || '',  // Get user's query
          document_ids: documentIds
        })
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Verification failed');
      }

      // Update message with new answer if regenerated
      if (data.updated_answer) {
        setMessages(prev => {
          const updated = [...prev];
          updated[messageIndex] = {
            ...updated[messageIndex],
            content: data.updated_answer,
            answer_metadata: data.answer_metadata,
            // Mark that this was updated
            updated_from_verification: true,
            last_updated: new Date().toISOString()
          };
          return updated;
        });
      }

      return data;
    } catch (err) {
      console.error('Field verification failed:', err);
      alert(`Failed to verify field: ${err.message}`);
      throw err;
    }
  };

  // Handler for batch field verification from batch modal
  const handleBatchFieldsVerified = async (messageIndex, verificationsMap) => {
    try {
      const message = messages[messageIndex];

      // Safely extract document IDs from various formats
      const documentIds = extractDocumentIds(message);

      // Convert verificationsMap to array format
      const verifications = Object.entries(verificationsMap).map(([fieldId, verification]) => ({
        field_id: parseInt(fieldId),
        action: verification.action,
        corrected_value: verification.corrected_value,
        notes: verification.notes
      }));

      // Call bulk-verify-and-regenerate endpoint
      const response = await fetch(`${API_URL}/api/audit/bulk-verify-and-regenerate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          verifications: verifications,
          original_query: messages[messageIndex - 1]?.content || '',  // Get user's query
          document_ids: documentIds
        })
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Batch verification failed');
      }

      // Update message with new answer if regenerated
      if (data.updated_answer) {
        setMessages(prev => {
          const updated = [...prev];
          updated[messageIndex] = {
            ...updated[messageIndex],
            content: data.updated_answer,
            answer_metadata: data.answer_metadata,
            // Mark that this was updated
            updated_from_verification: true,
            last_updated: new Date().toISOString(),
            verified_count: data.verified_count
          };
          return updated;
        });
      }

      return data;
    } catch (err) {
      console.error('Batch verification failed:', err);
      alert(`Failed to verify fields: ${err.message}`);
      throw err;
    }
  };

  // Handler to regenerate answer after verification
  const handleAnswerRegenerate = async (messageIndex) => {
    // This is called after verification to refresh the answer
    // The actual regeneration happens in handleFieldVerified
    console.log('Answer regeneration triggered for message', messageIndex);
  };

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col max-w-5xl mx-auto w-full">
        {/* Header */}
        <div className="bg-white border-b px-6 py-4">
          <h1 className="text-2xl font-bold text-gray-900">AI Document Search</h1>
          <p className="text-sm text-gray-600 mt-1">
            Ask questions about your documents in natural language
          </p>
        </div>

        {/* MCP Banner - Shows when Claude is connected */}
        <div className="px-6 pt-4">
          <MCPBanner />
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {messages.length === 0 ? (
            <div className="max-w-3xl mx-auto mt-20">
              <div className="text-center">
                <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-100 rounded-full mb-4">
                  <svg className="w-8 h-8 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                  </svg>
                </div>
                <h2 className="text-xl font-semibold text-gray-900 mb-2">
                  Ask questions about your documents
                </h2>
                <p className="text-gray-600">
                  Use natural language to search and analyze your documents
                </p>
              </div>
            </div>
          ) : (
            <div className="max-w-3xl mx-auto space-y-4">
              {messages.map((message, idx) => {
                // Show audit badge if low confidence data is present
                const showAuditBadge = message.role === 'assistant' &&
                  message.confidence_summary?.audit_recommended;

                return (
                  <div key={idx} className="relative">
                    {showAuditBadge && (
                      <div className="absolute -left-12 top-4">
                        <span className="inline-flex items-center px-2 py-1 text-xs font-medium text-yellow-800 bg-yellow-100 rounded-full border border-yellow-300" title="Contains low-confidence data">
                          ⚠
                        </span>
                      </div>
                    )}
                    <Message
                      message={message}
                      messageIndex={idx}
                      onViewExtraction={handleViewExtraction}
                      onFieldVerified={handleFieldVerified}
                      onBatchFieldsVerified={handleBatchFieldsVerified}
                      onAnswerRegenerate={handleAnswerRegenerate}
                    />
                  </div>
                );
              })}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input */}
        <div className="sticky bottom-0 border-t bg-white px-6 py-4 shadow-lg">
          <form onSubmit={handleSubmit} className="max-w-3xl mx-auto">
            {/* Template Filter */}
            {!loadingTemplates && templates.length > 0 && (
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Filter by Template (optional)
                </label>
                <select
                  value={selectedTemplate || ''}
                  onChange={(e) => setSelectedTemplate(e.target.value || null)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white"
                >
                  <option value="">All Templates</option>
                  {templates.map((template) => (
                    <option key={template.id} value={template.id}>
                      {template.name}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div className="flex gap-3">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask a question about your documents..."
                className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                disabled={loading}
              />
              <button
                type="submit"
                disabled={loading || !input.trim()}
                className="px-6 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
              >
                {loading ? 'Searching...' : 'Search'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

function Message({ message, messageIndex, onViewExtraction, onFieldVerified, onBatchFieldsVerified, onAnswerRegenerate }) {
  // System message (context changes)
  if (message.role === 'system') {
    return (
      <div className="flex justify-center">
        <div className="px-4 py-2 bg-gray-100 text-gray-600 rounded-full text-sm">
          {message.content}
        </div>
      </div>
    );
  }

  // User message
  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-2xl bg-blue-600 text-white rounded-lg px-4 py-3">
          <p className="text-white">{message.content}</p>
        </div>
      </div>
    );
  }

  // Assistant message
  return (
    <div className="flex justify-start">
      <div className="max-w-2xl">
        <div className={`rounded-lg px-4 py-3 ${
          message.error ? 'bg-red-50 text-red-900' : 'bg-white border border-gray-200'
        }`}>
          {/* Show update indicator if answer was regenerated */}
          {message.updated_from_verification && (
            <div className="mb-3 px-3 py-2 bg-blue-50 border border-blue-200 rounded-lg flex items-center gap-2 text-sm text-blue-800">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              <span>Answer updated based on your verification</span>
            </div>
          )}

          {/* Use AnswerWithAudit component for enhanced display */}
          <AnswerWithAudit
            answer={message.content}
            answerMetadata={message.answer_metadata}
            auditItems={message.audit_items}
            auditItemsFilteredCount={message.audit_items_filtered_count}
            auditItemsTotalCount={message.audit_items_total_count}
            confidenceSummary={message.confidence_summary}
            fieldLineage={message.field_lineage}
            queryId={message.query_id}
            documentsLink={message.documents_link}
            onFieldVerified={(fieldId, action, correctedValue, notes) =>
              onFieldVerified(messageIndex, fieldId, action, correctedValue, notes)
            }
            onBatchVerified={(verificationsMap) =>
              onBatchFieldsVerified(messageIndex, verificationsMap)
            }
            onAnswerRegenerate={() => onAnswerRegenerate(messageIndex)}
          />

          {message.explanation && (
            <p className="text-sm text-gray-600 italic mb-3 mt-3">
              {message.explanation}
            </p>
          )}

          {message.results && message.results.length > 0 && (
            <div className="mt-3 pt-3 border-t border-gray-200">
              <p className="text-sm font-medium text-gray-700 mb-2">
                {message.total} document{message.total !== 1 ? 's' : ''} found
              </p>
              <div className="space-y-2">
                {message.results.slice(0, 5).map((doc, idx) => (
                  <div key={idx} className="p-3 bg-gray-50 rounded border border-gray-200 hover:border-blue-300 hover:bg-blue-50 transition-colors cursor-pointer"
                       onClick={() => onViewExtraction && doc.extraction_id && onViewExtraction(doc.extraction_id)}>
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1">
                        <p className="font-medium text-gray-900 text-sm flex items-center gap-2">
                          📄 {doc.filename || 'Untitled'}
                        </p>
                        <div className="mt-1 space-y-1">
                          {Object.entries(doc)
                            .filter(([key]) => !['filename', 'document_id', 'extraction_id', '_score'].includes(key))
                            .slice(0, 3)
                            .map(([key, value]) => (
                              <p key={key} className="text-xs text-gray-600">
                                <span className="font-medium">{key.replace(/_/g, ' ')}:</span> {String(value)}
                              </p>
                            ))}
                        </div>
                      </div>
                      {doc.extraction_id && (
                        <button
                          className="text-xs text-blue-600 hover:text-blue-800 font-medium"
                          onClick={(e) => {
                            e.stopPropagation();
                            onViewExtraction(doc.extraction_id);
                          }}
                        >
                          View →
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
              {message.results.length > 5 && (
                <p className="text-sm text-gray-500 mt-2">
                  ...and {message.results.length - 5} more
                </p>
              )}
            </div>
          )}

          {message.results && message.results.length === 0 && (
            <p className="text-sm text-gray-500 mt-2">No documents found</p>
          )}
        </div>
      </div>
    </div>
  );
}
