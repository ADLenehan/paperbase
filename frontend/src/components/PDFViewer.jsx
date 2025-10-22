import { useState, useEffect } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

// Configure PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjs.version}/pdf.worker.min.js`;

/**
 * PDFViewer component for rendering PDFs with bounding box highlights
 *
 * @param {string} fileUrl - URL to the PDF file
 * @param {number} page - Page number to display (1-indexed)
 * @param {Array} highlights - Array of bbox highlights: [{bbox: [x,y,w,h], color: 'red', label: 'field_name'}]
 * @param {function} onPageChange - Callback when page changes
 * @param {number} zoom - Zoom level (default 1.0)
 * @param {function} onZoomChange - Callback when zoom changes
 */
export default function PDFViewer({
  fileUrl,
  page = 1,
  highlights = [],
  onPageChange,
  zoom = 1.0,
  onZoomChange
}) {
  const [numPages, setNumPages] = useState(null);
  const [pageWidth, setPageWidth] = useState(600);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  function onDocumentLoadSuccess({ numPages }) {
    setNumPages(numPages);
    setLoading(false);
  }

  function onDocumentLoadError(error) {
    console.error('Error loading PDF:', error);
    setError('Failed to load PDF');
    setLoading(false);
  }

  const handlePrevPage = () => {
    if (page > 1) {
      onPageChange?.(page - 1);
    }
  };

  const handleNextPage = () => {
    if (page < numPages) {
      onPageChange?.(page + 1);
    }
  };

  const handleZoomIn = () => {
    const newZoom = Math.min(zoom + 0.2, 2.0);
    onZoomChange?.(newZoom);
  };

  const handleZoomOut = () => {
    const newZoom = Math.max(zoom - 0.2, 0.5);
    onZoomChange?.(newZoom);
  };

  const handleZoomReset = () => {
    onZoomChange?.(1.0);
  };

  if (error) {
    return (
      <div className="flex items-center justify-center h-full bg-gray-100 rounded-lg border-2 border-dashed border-gray-300">
        <div className="text-center p-8">
          <svg className="mx-auto h-12 w-12 text-red-400 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <p className="text-gray-600 font-medium">{error}</p>
          <p className="text-sm text-gray-500 mt-2">Please check the file URL and try again</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-gray-100 rounded-lg border border-gray-300 overflow-hidden">
      {/* PDF Controls */}
      <div className="flex items-center justify-between bg-white border-b border-gray-200 px-4 py-2">
        {/* Page Navigation */}
        <div className="flex items-center gap-2">
          <button
            onClick={handlePrevPage}
            disabled={page <= 1}
            className="p-1.5 rounded hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            title="Previous page"
          >
            <svg className="w-5 h-5 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>

          <span className="text-sm text-gray-700 min-w-[80px] text-center">
            {loading ? 'Loading...' : `Page ${page} of ${numPages || '?'}`}
          </span>

          <button
            onClick={handleNextPage}
            disabled={!numPages || page >= numPages}
            className="p-1.5 rounded hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            title="Next page"
          >
            <svg className="w-5 h-5 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>

        {/* Zoom Controls */}
        <div className="flex items-center gap-2">
          <button
            onClick={handleZoomOut}
            disabled={zoom <= 0.5}
            className="p-1.5 rounded hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            title="Zoom out"
          >
            <svg className="w-5 h-5 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM13 10H7" />
            </svg>
          </button>

          <button
            onClick={handleZoomReset}
            className="text-sm text-gray-700 min-w-[60px] hover:bg-gray-100 px-2 py-1 rounded transition-colors"
            title="Reset zoom"
          >
            {Math.round(zoom * 100)}%
          </button>

          <button
            onClick={handleZoomIn}
            disabled={zoom >= 2.0}
            className="p-1.5 rounded hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            title="Zoom in"
          >
            <svg className="w-5 h-5 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7" />
            </svg>
          </button>
        </div>
      </div>

      {/* PDF Document */}
      <div className="flex-1 overflow-auto p-4">
        <div className="relative inline-block">
          <Document
            file={fileUrl}
            onLoadSuccess={onDocumentLoadSuccess}
            onLoadError={onDocumentLoadError}
            loading={
              <div className="flex items-center justify-center h-96">
                <div className="text-center">
                  <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mb-2"></div>
                  <p className="text-sm text-gray-600">Loading PDF...</p>
                </div>
              </div>
            }
          >
            <Page
              pageNumber={page}
              width={pageWidth * zoom}
              renderTextLayer={true}
              renderAnnotationLayer={true}
            />
          </Document>

          {/* Bounding Box Overlays */}
          {highlights.length > 0 && (
            <BBoxOverlays
              highlights={highlights}
              pageWidth={pageWidth * zoom}
              currentPage={page}
            />
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * BBoxOverlays component - renders bounding boxes over PDF
 */
function BBoxOverlays({ highlights, pageWidth, currentPage }) {
  return (
    <div className="absolute top-0 left-0 pointer-events-none">
      {highlights
        .filter(h => !h.page || h.page === currentPage)
        .map((highlight, index) => {
          if (!highlight.bbox || highlight.bbox.length < 4) return null;

          const [x, y, width, height] = highlight.bbox;

          // Color mapping based on confidence or explicit color
          const colorMap = {
            red: 'border-red-500 bg-red-500',
            yellow: 'border-yellow-500 bg-yellow-500',
            green: 'border-green-500 bg-green-500',
            blue: 'border-blue-500 bg-blue-500'
          };

          const colorClass = colorMap[highlight.color] || 'border-red-500 bg-red-500';

          return (
            <div
              key={index}
              className={`absolute border-2 ${colorClass} bg-opacity-10 pointer-events-auto cursor-pointer transition-opacity hover:bg-opacity-20`}
              style={{
                left: `${x}px`,
                top: `${y}px`,
                width: `${width}px`,
                height: `${height}px`
              }}
              title={highlight.label || 'Extraction'}
            >
              {highlight.label && (
                <div className="absolute -top-6 left-0 bg-gray-900 text-white text-xs px-2 py-1 rounded whitespace-nowrap">
                  {highlight.label}
                </div>
              )}
            </div>
          );
        })}
    </div>
  );
}
