import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function ChatSearch() {
  const navigate = useNavigate();

  // Chat state
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  // Folder state
  const [currentPath, setCurrentPath] = useState('');
  const [folderData, setFolderData] = useState(null);
  const [breadcrumbs, setBreadcrumbs] = useState([]);
  const [stats, setStats] = useState(null);
  const [loadingFolder, setLoadingFolder] = useState(true);

  useEffect(() => {
    fetchFolderData();
    fetchBreadcrumbs();
    fetchStats();
  }, [currentPath]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const fetchFolderData = async () => {
    try {
      setLoadingFolder(true);
      const response = await fetch(
        `${API_URL}/api/folders/browse?path=${encodeURIComponent(currentPath)}`
      );
      const data = await response.json();
      setFolderData(data);
    } catch (err) {
      console.error('Failed to fetch folder data:', err);
    } finally {
      setLoadingFolder(false);
    }
  };

  const fetchBreadcrumbs = async () => {
    try {
      const response = await fetch(
        `${API_URL}/api/folders/breadcrumbs?path=${encodeURIComponent(currentPath)}`
      );
      const data = await response.json();
      setBreadcrumbs(data.breadcrumbs || []);
    } catch (err) {
      console.error('Failed to fetch breadcrumbs:', err);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await fetch(
        `${API_URL}/api/folders/stats?path=${encodeURIComponent(currentPath)}`
      );
      const data = await response.json();
      setStats(data);
    } catch (err) {
      console.error('Failed to fetch stats:', err);
    }
  };

  const handleNavigateToFolder = (path) => {
    setCurrentPath(path);
    // Add system message about context change
    if (messages.length > 0) {
      setMessages(prev => [...prev, {
        role: 'system',
        content: path
          ? `Now searching in: ${path}`
          : 'Now searching all documents'
      }]);
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

      const response = await fetch(`${API_URL}/api/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: input,
          conversation_history: history,
          folder_path: currentPath || null  // Scope to current folder
        })
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Search failed');
      }

      // Add assistant response
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.answer,
        explanation: data.explanation,
        results: data.results,
        total: data.total,
        folder_context: currentPath
      }]);

    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `Error: ${err.message}`,
        error: true
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleViewExtraction = (extractionId) => {
    navigate(`/extractions/${extractionId}`);
  };

  const exampleQueries = currentPath
    ? [
        `Show me all ${currentPath.split('/')[0]} from last week`,
        `Which files have low confidence scores?`,
        `Find documents over $1000`
      ]
    : [
        "Show me all invoices over $1,000",
        "Find documents with low confidence scores",
        "What contracts were signed last month?"
      ];

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Left Sidebar - Folder Navigation */}
      <div className="w-80 bg-white border-r flex flex-col overflow-hidden">
        {/* Sidebar Header */}
        <div className="px-4 py-3 border-b bg-gray-50">
          <h2 className="font-semibold text-gray-900">Document Folders</h2>
          <p className="text-xs text-gray-600 mt-1">
            {stats?.total_extractions || 0} total documents
          </p>
        </div>

        {/* Breadcrumbs */}
        <div className="px-4 py-2 border-b bg-white">
          <div className="flex items-center gap-1 text-xs flex-wrap">
            {breadcrumbs.map((crumb, index) => (
              <div key={index} className="flex items-center gap-1">
                {index > 0 && <span className="text-gray-400">/</span>}
                <button
                  onClick={() => handleNavigateToFolder(crumb.path)}
                  className={`hover:text-blue-600 ${
                    index === breadcrumbs.length - 1
                      ? 'font-semibold text-gray-900'
                      : 'text-gray-600'
                  }`}
                >
                  {crumb.name === 'Home' ? '🏠' : crumb.name}
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Stats */}
        {stats && (
          <div className="px-4 py-3 border-b bg-blue-50">
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <div className="text-gray-600">Files</div>
                <div className="font-bold text-gray-900">{stats.unique_files || 0}</div>
              </div>
              <div>
                <div className="text-gray-600">Completed</div>
                <div className="font-bold text-green-600">{stats.by_status?.completed || 0}</div>
              </div>
            </div>
          </div>
        )}

        {/* Folders */}
        <div className="flex-1 overflow-y-auto">
          {loadingFolder ? (
            <div className="p-4 text-center text-gray-500 text-sm">Loading...</div>
          ) : (
            <>
              {/* Folders */}
              {folderData?.folders && folderData.folders.length > 0 && (
                <div className="p-2">
                  <div className="px-2 py-1 text-xs font-semibold text-gray-600 uppercase">
                    Folders
                  </div>
                  {folderData.folders.map((folder) => (
                    <button
                      key={folder.path}
                      onClick={() => handleNavigateToFolder(folder.path)}
                      className="w-full flex items-center gap-2 px-3 py-2 hover:bg-gray-100 rounded-lg text-left transition-colors"
                    >
                      <span className="text-xl">📁</span>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-gray-900 truncate">
                          {folder.name}
                        </div>
                        <div className="text-xs text-gray-500">{folder.count} items</div>
                      </div>
                    </button>
                  ))}
                </div>
              )}

              {/* Files */}
              {folderData?.files && folderData.files.length > 0 && (
                <div className="p-2 border-t">
                  <div className="px-2 py-1 text-xs font-semibold text-gray-600 uppercase">
                    Files ({folderData.files.length})
                  </div>
                  {folderData.files.slice(0, 20).map((file) => (
                    <button
                      key={file.extraction_id}
                      onClick={() => handleViewExtraction(file.extraction_id)}
                      className="w-full flex items-center gap-2 px-3 py-2 hover:bg-gray-100 rounded-lg text-left transition-colors group"
                    >
                      <span className="text-lg">📄</span>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-gray-900 truncate group-hover:text-blue-600">
                          {file.filename}
                        </div>
                        <div className="flex items-center gap-2 text-xs text-gray-500">
                          <span>{file.template}</span>
                          {file.status === 'completed' && <span className="text-green-600">✓</span>}
                          {file.status === 'processing' && <span className="text-blue-600">⋯</span>}
                        </div>
                      </div>
                    </button>
                  ))}
                  {folderData.files.length > 20 && (
                    <div className="px-3 py-2 text-xs text-gray-500 text-center">
                      +{folderData.files.length - 20} more files
                    </div>
                  )}
                </div>
              )}

              {(!folderData?.folders?.length && !folderData?.files?.length) && (
                <div className="p-4 text-center text-gray-500 text-sm">
                  No items in this folder
                </div>
              )}
            </>
          )}
        </div>

        {/* Context Indicator */}
        {currentPath && (
          <div className="px-4 py-3 border-t bg-blue-50">
            <div className="text-xs text-blue-800">
              <div className="font-semibold mb-1">Search Context:</div>
              <div className="flex items-center gap-2">
                <span>📍</span>
                <span className="truncate">{currentPath}</span>
              </div>
              <button
                onClick={() => handleNavigateToFolder('')}
                className="mt-2 text-xs text-blue-600 hover:text-blue-800 font-medium"
              >
                ← Search all documents
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="bg-white border-b px-6 py-4">
          <h1 className="text-2xl font-bold">AI Document Search</h1>
          <p className="text-sm text-gray-600 mt-1">
            {currentPath
              ? `Ask questions about documents in ${currentPath}`
              : 'Ask questions about your documents in natural language'
            }
          </p>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {messages.length === 0 ? (
            <div className="max-w-3xl mx-auto mt-12">
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
                  {currentPath
                    ? `Searching in ${currentPath}`
                    : 'Use natural language to search and analyze your documents'
                  }
                </p>
              </div>
            </div>
          ) : (
            <div className="max-w-3xl mx-auto space-y-4">
              {messages.map((message, idx) => (
                <Message key={idx} message={message} onViewExtraction={handleViewExtraction} />
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input */}
        <div className="border-t bg-white px-6 py-4">
          <form onSubmit={handleSubmit} className="max-w-3xl mx-auto">
            {/* Example questions - show when no messages */}
            {messages.length === 0 && (
              <div className="mb-3 flex flex-wrap gap-2 justify-center">
                {exampleQueries.map((query, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => setInput(query)}
                    className="px-3 py-1.5 text-sm text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-full transition-colors"
                  >
                    {query}
                  </button>
                ))}
              </div>
            )}

            <div className="flex gap-3">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={currentPath
                  ? `Ask about documents in ${currentPath}...`
                  : "Ask a question about your documents..."
                }
                className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                disabled={loading}
              />
              <button
                type="submit"
                disabled={loading || !input.trim()}
                className="px-6 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
              >
                {loading ? 'Searching...' : 'Search'}
              </button>
            </div>
            {currentPath && (
              <div className="mt-2 text-xs text-gray-600 text-center">
                Searching in: <span className="font-semibold">{currentPath}</span>
              </div>
            )}
          </form>
        </div>
      </div>
    </div>
  );
}

function Message({ message, onViewExtraction }) {
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
          <p>{message.content}</p>
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
          <p className="mb-2">{message.content}</p>

          {message.explanation && (
            <p className="text-sm text-gray-600 italic mb-3">
              {message.explanation}
            </p>
          )}

          {message.folder_context && (
            <p className="text-xs text-blue-600 mb-2">
              📍 Searched in: {message.folder_context}
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
