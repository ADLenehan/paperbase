import { useState, useEffect, useCallback } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import DocumentViewer from '../components/DocumentViewer';
import AuditTableView from '../components/AuditTableView';
import ComplexFieldDisplay from '../components/ComplexFieldDisplay';
import ArrayEditor from '../components/ArrayEditor';
import TableEditor from '../components/TableEditor';
import ArrayOfObjectsEditor from '../components/ArrayOfObjectsEditor';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function Audit() {
  const { documentId } = useParams();
  const [searchParams] = useSearchParams();
  const templateId = searchParams.get('template_id');
  const mode = searchParams.get('mode'); // NEW: 'table' or null (single field mode)

  const [queue, setQueue] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [currentItem, setCurrentItem] = useState(null);
  const [loading, setLoading] = useState(true);
  const [verifying, setVerifying] = useState(false);
  const [correctionValue, setCorrectionValue] = useState('');
  const [showCorrectionInput, setShowCorrectionInput] = useState(false);
  const [isEditingComplexField, setIsEditingComplexField] = useState(false);

  // NEW: Table mode state
  const [viewMode, setViewMode] = useState(mode === 'table' ? 'table' : 'single');
  const [tableDocuments, setTableDocuments] = useState([]);
  const [tableSchema, setTableSchema] = useState(null);

  // PDF viewer state
  const [currentPage, setCurrentPage] = useState(1);
  const [zoom, setZoom] = useState(1.0);

  // Session stats
  const [sessionStats, setSessionStats] = useState({
    reviewed: 0,
    correct: 0,
    corrected: 0,
    notFound: 0
  });

  useEffect(() => {
    if (viewMode === 'table' && templateId) {
      fetchTableData(templateId);
    } else {
      fetchQueue();
    }
  }, [documentId, templateId, viewMode]);

  useEffect(() => {
    if (queue.length > 0 && currentIndex < queue.length) {
      const item = queue[currentIndex];
      setCurrentItem(item);
      setCorrectionValue('');
      setShowCorrectionInput(false);

      // Jump to the page where the field is located
      if (item.source_page) {
        setCurrentPage(item.source_page);
      }
    } else {
      setCurrentItem(null);
    }
  }, [queue, currentIndex]);

  const fetchQueue = async () => {
    setLoading(true);
    try {
      let url;
      if (documentId) {
        // Document-specific audit
        url = `${API_URL}/api/audit/document/${documentId}`;
      } else {
        // General audit queue
        const params = new URLSearchParams();
        if (templateId) params.append('template_id', templateId);
        params.append('max_confidence', '0.6'); // Only low confidence
        url = `${API_URL}/api/audit/queue?${params}`;
      }

      const response = await fetch(url);
      if (!response.ok) throw new Error('Failed to fetch audit queue');

      const data = await response.json();
      setQueue(data.items || []);
    } catch (error) {
      console.error('Error fetching audit queue:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async (action, value = null) => {
    if (!currentItem) return;

    setVerifying(true);
    try {
      const response = await fetch(`${API_URL}/api/audit/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          field_id: currentItem.field_id,
          action,
          corrected_value: value || correctionValue
        })
      });

      if (!response.ok) throw new Error('Verification failed');

      const result = await response.json();

      // Update session stats
      setSessionStats(prev => ({
        reviewed: prev.reviewed + 1,
        correct: prev.correct + (action === 'correct' ? 1 : 0),
        corrected: prev.corrected + (action === 'incorrect' ? 1 : 0),
        notFound: prev.notFound + (action === 'not_found' ? 1 : 0)
      }));

      // Move to next item
      if (result.next_item) {
        // Add next item to queue and advance
        setQueue(prev => [...prev.slice(0, currentIndex + 1), result.next_item, ...prev.slice(currentIndex + 1)]);
        setCurrentIndex(prev => prev + 1);
      } else {
        // No more items, advance in current queue
        setCurrentIndex(prev => prev + 1);
      }
    } catch (error) {
      console.error('Verification error:', error);
      alert('Failed to verify field. Please try again.');
    } finally {
      setVerifying(false);
    }
  };

  const handleCorrect = () => {
    handleVerify('correct');
  };

  const handleIncorrect = () => {
    if (!correctionValue.trim()) {
      setShowCorrectionInput(true);
      return;
    }
    handleVerify('incorrect', correctionValue);
  };

  const handleNotFound = () => {
    handleVerify('not_found');
  };

  const handleSkip = () => {
    setCurrentIndex(prev => prev + 1);
  };

  // NEW: Table mode functions
  const fetchTableData = async (schemaId) => {
    setLoading(true);
    try {
      // Fetch schema
      const schemaRes = await fetch(`${API_URL}/api/onboarding/schemas/${schemaId}`);
      if (!schemaRes.ok) throw new Error('Schema not found');
      const schema = await schemaRes.json();
      setTableSchema(schema);

      // Fetch documents with this schema
      const docsRes = await fetch(`${API_URL}/api/documents?schema_id=${schemaId}`);
      if (!docsRes.ok) throw new Error('Documents not found');
      const docsData = await docsRes.json();
      setTableDocuments(docsData.documents || []);
    } catch (error) {
      console.error('Error fetching table data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleBulkVerify = async (verifications) => {
    setVerifying(true);
    try {
      const response = await fetch(`${API_URL}/api/audit/bulk-verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ verifications })
      });

      if (!response.ok) throw new Error('Bulk verification failed');

      const result = await response.json();

      // Refresh table data
      if (tableSchema) {
        await fetchTableData(tableSchema.id);
      }

      alert(`Successfully verified ${result.results.successful} of ${result.results.total} fields`);
    } catch (error) {
      console.error('Bulk verification error:', error);
      alert('Failed to verify fields. Please try again.');
    } finally {
      setVerifying(false);
    }
  };


  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mb-2"></div>
          <p className="text-sm text-gray-600">Loading audit queue...</p>
        </div>
      </div>
    );
  }

  if (queue.length === 0) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-8">
        <div className="text-center py-12 bg-white rounded-lg shadow-sm border border-gray-200">
          <svg className="mx-auto h-12 w-12 text-green-500 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <h2 className="text-2xl font-semibold text-gray-900 mb-2">All Caught Up!</h2>
          <p className="text-gray-600">No low-confidence extractions need review</p>
        </div>
      </div>
    );
  }

  if (currentIndex >= queue.length) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-8">
        <div className="text-center py-12 bg-white rounded-lg shadow-sm border border-gray-200">
          <svg className="mx-auto h-12 w-12 text-green-500 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <h2 className="text-2xl font-semibold text-gray-900 mb-2">Session Complete!</h2>
          <p className="text-gray-600 mb-4">You've reviewed {sessionStats.reviewed} fields</p>

          {/* Session Stats */}
          <div className="grid grid-cols-3 gap-4 max-w-md mx-auto mt-6">
            <div className="bg-green-50 rounded-lg p-4">
              <div className="text-2xl font-bold text-green-700">{sessionStats.correct}</div>
              <div className="text-sm text-green-600">Correct</div>
            </div>
            <div className="bg-blue-50 rounded-lg p-4">
              <div className="text-2xl font-bold text-blue-700">{sessionStats.corrected}</div>
              <div className="text-sm text-blue-600">Corrected</div>
            </div>
            <div className="bg-yellow-50 rounded-lg p-4">
              <div className="text-2xl font-bold text-yellow-700">{sessionStats.notFound}</div>
              <div className="text-sm text-yellow-600">Not Found</div>
            </div>
          </div>

          <button
            onClick={() => window.location.reload()}
            className="mt-6 bg-periwinkle-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-periwinkle-700 transition-colors"
          >
            Start New Session
          </button>
        </div>
      </div>
    );
  }

  if (!currentItem) return null;

  // Prepare PDF highlights
  const highlights = currentItem.source_bbox ? [{
    bbox: currentItem.source_bbox,
    color: currentItem.confidence < 0.4 ? 'red' : currentItem.confidence < 0.6 ? 'yellow' : 'green',
    label: currentItem.field_name,
    page: currentItem.source_page
  }] : [];

  const fileUrl = `${API_URL}/api/files/${currentItem.document_id}/preview`;

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between mb-2">
          <h1 className="text-2xl font-bold text-gray-900">
            {viewMode === 'table' ? 'Bulk Review' : 'Audit Queue'}
          </h1>
          <div className="flex items-center gap-4">
            {/* NEW: Mode Toggle */}
            {templateId && (
              <button
                onClick={() => setViewMode(viewMode === 'table' ? 'single' : 'table')}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {viewMode === 'table' ? '👁️ Single Field Mode' : '📊 Table Mode'}
              </button>
            )}
            {viewMode === 'single' && (
              <span className="text-sm text-gray-600">
                {currentIndex + 1} of {queue.length}
              </span>
            )}
          </div>
        </div>

        {/* Progress Bar - Single Mode Only */}
        {viewMode === 'single' && (
          <>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-periwinkle-600 h-2 rounded-full transition-all duration-300"
                style={{ width: `${((currentIndex) / queue.length) * 100}%` }}
              />
            </div>

            {/* Session Stats */}
            <div className="flex items-center gap-4 mt-3 text-xs text-gray-600">
              <span>✓ {sessionStats.correct} correct</span>
              <span>✏️ {sessionStats.corrected} corrected</span>
              <span>⊘ {sessionStats.notFound} not found</span>
            </div>
          </>
        )}
      </div>

      {/* Main Content - Conditional Rendering */}
      {viewMode === 'table' ? (
        /* NEW: Table Mode */
        <div className="flex-1 overflow-auto p-6">
          {loading ? (
            <div className="flex items-center justify-center h-64">
              <div className="text-gray-500">Loading...</div>
            </div>
          ) : (
            <AuditTableView
              documents={tableDocuments}
              schema={tableSchema}
              onVerify={handleBulkVerify}
              isVerifying={verifying}
              showActions={true}
              onCancel={() => setViewMode('single')}
            />
          )}
        </div>
      ) : (
        /* Original: Single Field Mode */
        <div className="flex-1 flex overflow-hidden">
        {/* Left: Document Viewer */}
        <div className="flex-1 p-6">
          <DocumentViewer
            fileUrl={fileUrl}
            filename={currentItem.filename}
            page={currentPage}
            highlights={highlights}
            onPageChange={setCurrentPage}
            zoom={zoom}
            onZoomChange={setZoom}
          />
        </div>

        {/* Right: Field Review */}
        <div className="w-96 bg-white border-l border-gray-200 p-6 overflow-y-auto">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Field Review</h3>

          {/* Document Info */}
          <div className="mb-6 space-y-2">
            <div>
              <span className="text-xs text-gray-500">Document:</span>
              <p className="font-medium text-gray-900 text-sm">{currentItem.filename}</p>
            </div>

            {currentItem.template_name && (
              <div>
                <span className="text-xs text-gray-500">Template:</span>
                <p className="font-medium text-gray-900 text-sm">{currentItem.template_name}</p>
              </div>
            )}

            <div>
              <span className="text-xs text-gray-500">Field:</span>
              <p className="font-medium text-gray-900 text-sm capitalize">
                {currentItem.field_name.replace(/_/g, ' ')}
              </p>
            </div>
          </div>

          {/* Extracted Value */}
          <div className="mb-6">
            <label className="text-xs text-gray-500 mb-1 block">Extracted Value:</label>
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-3">
              {currentItem.field_type && ['array', 'table', 'array_of_objects'].includes(currentItem.field_type) ? (
                <div>
                  {isEditingComplexField ? (
                    <div className="space-y-3">
                      {currentItem.field_type === 'array' && (
                        <ArrayEditor
                          value={currentItem.field_value_json || []}
                          onChange={(newValue) => setCorrectionValue(JSON.stringify(newValue))}
                        />
                      )}
                      {currentItem.field_type === 'table' && (
                        <TableEditor
                          value={currentItem.field_value_json || { headers: [], rows: [] }}
                          onChange={(newValue) => setCorrectionValue(JSON.stringify(newValue))}
                        />
                      )}
                      {currentItem.field_type === 'array_of_objects' && (
                        <ArrayOfObjectsEditor
                          value={currentItem.field_value_json || []}
                          onChange={(newValue) => setCorrectionValue(JSON.stringify(newValue))}
                        />
                      )}
                      <div className="flex gap-2">
                        <button
                          onClick={() => setIsEditingComplexField(false)}
                          className="px-3 py-1.5 text-sm border border-gray-300 rounded hover:bg-gray-50 transition-colors"
                        >
                          Cancel
                        </button>
                        <button
                          onClick={() => {
                            setShowCorrectionInput(true);
                            setIsEditingComplexField(false);
                          }}
                          className="px-3 py-1.5 text-sm bg-periwinkle-600 text-white rounded hover:bg-periwinkle-700 transition-colors"
                        >
                          Apply Changes
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <ComplexFieldDisplay
                        field={currentItem}
                        mode="expanded"
                      />
                      <button
                        onClick={() => setIsEditingComplexField(true)}
                        className="text-xs text-blue-600 hover:text-blue-700 hover:underline"
                      >
                        Edit
                      </button>
                    </div>
                  )}
                </div>
              ) : (
                <p className="font-mono text-sm text-gray-900">
                  {currentItem.field_value || '(not extracted)'}
                </p>
              )}
            </div>
          </div>

          {/* Confidence */}
          <div className="mb-6">
            <label className="text-xs text-gray-500 mb-1 block">Confidence:</label>
            {currentItem.confidence === 0 || currentItem.confidence === null ? (
              <div className="text-sm text-gray-500 italic">
                Field not extracted
              </div>
            ) : (
              <div className="flex items-center gap-3">
                <div className="flex-1 bg-gray-200 rounded-full h-2">
                  <div
                    className={`h-2 rounded-full ${
                      currentItem.confidence < 0.4
                        ? 'bg-coral-500'
                        : currentItem.confidence < 0.6
                        ? 'bg-yellow-500'
                        : 'bg-mint-500'
                    }`}
                    style={{ width: `${currentItem.confidence * 100}%` }}
                  />
                </div>
                <span className="text-sm font-medium text-gray-900">
                  {Math.round(currentItem.confidence * 100)}%
                </span>
              </div>
            )}
          </div>

          {/* Bbox Status */}
          {!currentItem.source_bbox && (
            <div className="mb-6 bg-yellow-50 border border-yellow-200 rounded-lg p-3">
              <div className="flex items-start gap-2">
                <svg className="w-4 h-4 text-yellow-600 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <div className="text-xs text-yellow-700">
                  No location data available. You'll need to review the full document.
                </div>
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="space-y-3">
            {/* Correct */}
            <button
              onClick={handleCorrect}
              disabled={verifying}
              className="w-full bg-periwinkle-600 text-white py-3 px-4 rounded-lg font-medium hover:bg-periwinkle-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              ✓ Correct
            </button>

            {/* Correction Input */}
            {showCorrectionInput ? (
              <div className="space-y-2">
                <input
                  type="text"
                  value={correctionValue}
                  onChange={(e) => setCorrectionValue(e.target.value)}
                  onKeyPress={(e) => {
                    if (e.key === 'Enter' && correctionValue.trim()) {
                      handleIncorrect();
                    }
                  }}
                  placeholder="Enter correct value..."
                  autoFocus
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-periwinkle-500 focus:border-transparent"
                />
                <button
                  onClick={handleIncorrect}
                  disabled={verifying || !correctionValue.trim()}
                  className="w-full bg-periwinkle-600 text-white py-3 px-4 rounded-lg font-medium hover:bg-periwinkle-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Submit Correction
                </button>
              </div>
            ) : (
              <button
                onClick={() => setShowCorrectionInput(true)}
                disabled={verifying}
                className="w-full border-2 border-periwinkle-500 text-periwinkle-700 bg-white py-3 px-4 rounded-lg font-medium hover:bg-periwinkle-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                ✗ Fix Value
              </button>
            )}

            {/* Not Found */}
            <button
              onClick={handleNotFound}
              disabled={verifying}
              className="w-full bg-coral-600 text-white py-3 px-4 rounded-lg font-medium hover:bg-coral-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              ⊘ Not Found
            </button>

            {/* Skip */}
            <button
              onClick={handleSkip}
              disabled={verifying}
              className="w-full bg-gray-200 text-gray-700 py-3 px-4 rounded-lg font-medium hover:bg-gray-300 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Skip
            </button>
          </div>
        </div>
        </div>
      )}
    </div>
  );
}
