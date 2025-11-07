import { useState } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

// Configure PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjs.version}/pdf.worker.min.js`;

/**
 * Validate and sanitize bounding box coordinates
 * @param {Array} bbox - Raw bbox [x, y, width, height]
 * @returns {Array|null} Validated bbox or null if invalid
 */
function validateBbox(bbox) {
  if (!bbox || !Array.isArray(bbox) || bbox.length !== 4) {
    return null;
  }

  // Ensure all values are numbers and non-negative
  const validated = bbox.map(val => {
    const num = parseFloat(val);
    return isNaN(num) || num < 0 ? 0 : num;
  });

  // Ensure non-zero width and height
  if (validated[2] <= 0 || validated[3] <= 0) {
    console.warn('Invalid bbox: width or height is zero or negative', bbox);
    return null;
  }

  // Basic sanity check: coordinates shouldn't be excessively large
  if (validated.some(val => val > 10000)) {
    console.warn('Invalid bbox: coordinates too large', bbox);
    return null;
  }

  return validated;
}

/**
 * PDFExcerpt - Lightweight PDF viewer for modal displays
 *
 * Displays a single page with optional bbox highlight.
 * Optimized for small, focused views in modals.
 *
 * @param {string} fileUrl - URL to the PDF file
 * @param {number} page - Page number to display (1-indexed)
 * @param {Array} bbox - Optional bounding box [x, y, width, height]
 * @param {string} fieldLabel - Label for the highlighted field
 * @param {number} zoom - Zoom level (default 1.0)
 * @param {boolean} showControls - Show zoom controls (default true)
 * @param {string} className - Additional CSS classes
 */
export default function PDFExcerpt({
  fileUrl,
  page = 1,
  bbox,
  fieldLabel,
  zoom = 1.0,
  showControls = true,
  className = ''
}) {
  const [currentZoom, setCurrentZoom] = useState(zoom);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [pageWidth, setPageWidth] = useState(500);

  function onDocumentLoadSuccess() {
    setLoading(false);
  }

  function onDocumentLoadError(err) {
    console.error('PDF load error:', err);
    setError('Failed to load PDF');
    setLoading(false);
  }

  const handleZoomIn = () => {
    setCurrentZoom(prev => Math.min(prev + 0.2, 2.0));
  };

  const handleZoomOut = () => {
    setCurrentZoom(prev => Math.max(prev - 0.2, 0.5));
  };

  const handleZoomReset = () => {
    setCurrentZoom(1.0);
  };

  // Determine bbox color based on confidence (passed via fieldLabel or default to yellow)
  const bboxColor = bbox ? 'border-yellow-500 bg-yellow-500' : '';

  if (error) {
    return (
      <div className={`flex items-center justify-center bg-gray-100 rounded-lg border-2 border-dashed border-gray-300 p-8 ${className}`}>
        <div className="text-center">
          <svg className="mx-auto h-10 w-10 text-red-400 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <p className="text-sm text-gray-600 font-medium">{error}</p>
          <p className="text-xs text-gray-500 mt-1">Cannot display PDF preview</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`flex flex-col bg-gray-100 rounded-lg border border-gray-300 overflow-hidden ${className}`}>
      {/* Controls Bar */}
      {showControls && (
        <div className="flex items-center justify-between bg-white border-b border-gray-200 px-3 py-2">
          <div className="text-xs text-gray-600">
            Page {page}
          </div>

          {/* Zoom Controls */}
          <div className="flex items-center gap-1">
            <button
              onClick={handleZoomOut}
              disabled={currentZoom <= 0.5}
              className="p-1 rounded hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              title="Zoom out"
            >
              <svg className="w-4 h-4 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM13 10H7" />
              </svg>
            </button>

            <button
              onClick={handleZoomReset}
              className="text-xs text-gray-700 min-w-[50px] hover:bg-gray-100 px-2 py-0.5 rounded transition-colors"
              title="Reset zoom"
            >
              {Math.round(currentZoom * 100)}%
            </button>

            <button
              onClick={handleZoomIn}
              disabled={currentZoom >= 2.0}
              className="p-1 rounded hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              title="Zoom in"
            >
              <svg className="w-4 h-4 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7" />
              </svg>
            </button>
          </div>
        </div>
      )}

      {/* PDF Display */}
      <div className="flex-1 overflow-auto p-3 bg-gray-50">
        <div className="relative inline-block">
          <Document
            file={fileUrl}
            onLoadSuccess={onDocumentLoadSuccess}
            onLoadError={onDocumentLoadError}
            loading={
              <div className="flex items-center justify-center h-64">
                <div className="text-center">
                  <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mb-2"></div>
                  <p className="text-xs text-gray-600">Loading PDF...</p>
                </div>
              </div>
            }
          >
            <Page
              pageNumber={page}
              width={pageWidth * currentZoom}
              renderTextLayer={true}
              renderAnnotationLayer={false}
            />
          </Document>

          {/* Bounding Box Overlay */}
          {(() => {
            const validBbox = validateBbox(bbox);
            return validBbox && (
              <div className="absolute top-0 left-0 pointer-events-none">
                <div
                  className={`absolute border-2 ${bboxColor} bg-opacity-20 animate-pulse`}
                  style={{
                    left: `${validBbox[0] * currentZoom}px`,
                    top: `${validBbox[1] * currentZoom}px`,
                    width: `${validBbox[2] * currentZoom}px`,
                    height: `${validBbox[3] * currentZoom}px`
                  }}
                >
                  {fieldLabel && (
                    <div className="absolute -top-6 left-0 bg-gray-900 text-white text-xs px-2 py-1 rounded whitespace-nowrap">
                      {fieldLabel}
                    </div>
                  )}
                </div>
              </div>
            );
          })()}
        </div>
      </div>

      {/* Loading Overlay */}
      {loading && (
        <div className="absolute inset-0 bg-white bg-opacity-75 flex items-center justify-center">
          <div className="text-center">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mb-2"></div>
            <p className="text-sm text-gray-600">Loading page...</p>
          </div>
        </div>
      )}
    </div>
  );
}
