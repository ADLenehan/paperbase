import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import DocumentViewer from '../DocumentViewer'

vi.mock('react-pdf', () => ({
  Document: ({ children, onLoadSuccess, file }) => {
    setTimeout(() => onLoadSuccess?.({ numPages: 3 }), 0)
    return <div data-testid="pdf-document">{children}</div>
  },
  Page: ({ pageNumber, onLoadSuccess }) => {
    setTimeout(() => {
      onLoadSuccess?.({
        getViewport: () => ({ width: 600, height: 800 })
      })
    }, 0)
    return <div data-testid={`pdf-page-${pageNumber}`}>Page {pageNumber}</div>
  },
  pdfjs: {
    GlobalWorkerOptions: { workerSrc: '' },
    version: '3.0.0'
  }
}))

describe('DocumentViewer', () => {
  const mockFileUrl = '/api/files/1/preview'
  const mockFilename = 'test-document.pdf'

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders PDF document viewer', async () => {
    render(
      <DocumentViewer
        fileUrl={mockFileUrl}
        filename={mockFilename}
        page={1}
      />
    )

    await waitFor(() => {
      expect(screen.getByTestId('pdf-document')).toBeInTheDocument()
    })
  })

  it('displays page navigation controls for PDFs', async () => {
    render(
      <DocumentViewer
        fileUrl={mockFileUrl}
        filename={mockFilename}
        page={1}
      />
    )

    await waitFor(() => {
      expect(screen.getByText(/Page 1 of/)).toBeInTheDocument()
    })
  })

  it('calls onPageChange when next button is clicked', async () => {
    const mockOnPageChange = vi.fn()
    
    render(
      <DocumentViewer
        fileUrl={mockFileUrl}
        filename={mockFilename}
        page={1}
        onPageChange={mockOnPageChange}
      />
    )

    await waitFor(() => {
      expect(screen.getByText(/Page 1 of 3/)).toBeInTheDocument()
    })

    const nextButton = screen.getByTitle('Next page')
    fireEvent.click(nextButton)

    expect(mockOnPageChange).toHaveBeenCalledWith(2)
  })

  it('calls onPageChange when previous button is clicked', async () => {
    const mockOnPageChange = vi.fn()
    
    render(
      <DocumentViewer
        fileUrl={mockFileUrl}
        filename={mockFilename}
        page={2}
        onPageChange={mockOnPageChange}
      />
    )

    await waitFor(() => {
      expect(screen.getByText(/Page 2 of 3/)).toBeInTheDocument()
    })

    const prevButton = screen.getByTitle('Previous page')
    fireEvent.click(prevButton)

    expect(mockOnPageChange).toHaveBeenCalledWith(1)
  })

  it('disables previous button on first page', async () => {
    render(
      <DocumentViewer
        fileUrl={mockFileUrl}
        filename={mockFilename}
        page={1}
      />
    )

    await waitFor(() => {
      const prevButton = screen.getByTitle('Previous page')
      expect(prevButton).toBeDisabled()
    })
  })

  it('disables next button on last page', async () => {
    render(
      <DocumentViewer
        fileUrl={mockFileUrl}
        filename={mockFilename}
        page={3}
      />
    )

    await waitFor(() => {
      const nextButton = screen.getByTitle('Next page')
      expect(nextButton).toBeDisabled()
    })
  })

  it('calls onZoomChange when zoom in is clicked', async () => {
    const mockOnZoomChange = vi.fn()
    
    render(
      <DocumentViewer
        fileUrl={mockFileUrl}
        filename={mockFilename}
        page={1}
        zoom={1.0}
        onZoomChange={mockOnZoomChange}
      />
    )

    const zoomInButton = screen.getByTitle('Zoom in')
    fireEvent.click(zoomInButton)

    expect(mockOnZoomChange).toHaveBeenCalledWith(1.2)
  })

  it('calls onZoomChange when zoom out is clicked', async () => {
    const mockOnZoomChange = vi.fn()
    
    render(
      <DocumentViewer
        fileUrl={mockFileUrl}
        filename={mockFilename}
        page={1}
        zoom={1.0}
        onZoomChange={mockOnZoomChange}
      />
    )

    const zoomOutButton = screen.getByTitle('Zoom out')
    fireEvent.click(zoomOutButton)

    expect(mockOnZoomChange).toHaveBeenCalledWith(0.8)
  })

  it('calls onZoomChange when reset zoom is clicked', async () => {
    const mockOnZoomChange = vi.fn()
    
    render(
      <DocumentViewer
        fileUrl={mockFileUrl}
        filename={mockFilename}
        page={1}
        zoom={1.5}
        onZoomChange={mockOnZoomChange}
      />
    )

    const resetButton = screen.getByTitle('Reset zoom')
    fireEvent.click(resetButton)

    expect(mockOnZoomChange).toHaveBeenCalledWith(1.0)
  })

  it('displays zoom percentage', () => {
    render(
      <DocumentViewer
        fileUrl={mockFileUrl}
        filename={mockFilename}
        page={1}
        zoom={1.5}
      />
    )

    expect(screen.getByText('150%')).toBeInTheDocument()
  })

  it('renders image viewer for image files', async () => {
    render(
      <DocumentViewer
        fileUrl="/api/files/1/preview"
        filename="test-image.png"
        page={1}
      />
    )

    await waitFor(() => {
      const img = screen.getByAlt('test-image.png')
      expect(img).toBeInTheDocument()
    })
  })

  it('renders highlights as bounding boxes', async () => {
    const highlights = [
      {
        bbox: [0.1, 0.2, 0.3, 0.4],
        color: 'red',
        label: 'invoice_total',
        page: 1
      }
    ]

    render(
      <DocumentViewer
        fileUrl={mockFileUrl}
        filename={mockFilename}
        page={1}
        highlights={highlights}
      />
    )

    await waitFor(() => {
      expect(screen.getByTitle('invoice_total')).toBeInTheDocument()
    })
  })

  it('handles document load error gracefully', async () => {
    vi.mocked(require('react-pdf').Document).mockImplementationOnce(
      ({ onLoadError }) => {
        setTimeout(() => onLoadError?.(new Error('Load failed')), 0)
        return <div>Error</div>
      }
    )

    render(
      <DocumentViewer
        fileUrl={mockFileUrl}
        filename={mockFilename}
        page={1}
      />
    )

    await waitFor(() => {
      expect(screen.getByText(/Failed to load document/)).toBeInTheDocument()
    })
  })
})
