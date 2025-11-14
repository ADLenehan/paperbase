import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import ChatSearch from '../ChatSearch'

global.fetch = vi.fn()

const renderWithRouter = (component) => {
  return render(<BrowserRouter>{component}</BrowserRouter>)
}

describe('ChatSearch', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    global.fetch.mockResolvedValue({
      ok: true,
      json: async () => ({ templates: [] })
    })
  })

  it('renders chat search page', async () => {
    renderWithRouter(<ChatSearch />)

    expect(screen.getByText('AI Document Search')).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/Ask a question about your documents/)).toBeInTheDocument()
  })

  it('displays welcome message when no messages', () => {
    renderWithRouter(<ChatSearch />)

    expect(screen.getByText('Ask questions about your documents')).toBeInTheDocument()
  })

  it('submits query when form is submitted', async () => {
    const mockSearchResponse = {
      answer: 'Test answer',
      results: [],
      total: 0,
      answer_metadata: {},
      audit_items: [],
      confidence_summary: {}
    }

    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ templates: [] })
    }).mockResolvedValueOnce({
      ok: true,
      json: async () => mockSearchResponse
    })

    renderWithRouter(<ChatSearch />)

    const input = screen.getByPlaceholderText(/Ask a question about your documents/)
    const submitButton = screen.getByText('Search')

    fireEvent.change(input, { target: { value: 'show me invoices' } })
    fireEvent.click(submitButton)

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/search'),
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('show me invoices')
        })
      )
    })
  })

  it('displays user message after submission', async () => {
    const mockSearchResponse = {
      answer: 'Test answer',
      results: [],
      total: 0,
      answer_metadata: {},
      audit_items: [],
      confidence_summary: {}
    }

    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ templates: [] })
    }).mockResolvedValueOnce({
      ok: true,
      json: async () => mockSearchResponse
    })

    renderWithRouter(<ChatSearch />)

    const input = screen.getByPlaceholderText(/Ask a question about your documents/)
    fireEvent.change(input, { target: { value: 'show me invoices' } })
    fireEvent.submit(input.closest('form'))

    await waitFor(() => {
      expect(screen.getByText('show me invoices')).toBeInTheDocument()
    })
  })

  it('displays assistant response after search', async () => {
    const mockSearchResponse = {
      answer: 'Found 5 invoices',
      results: [],
      total: 5,
      answer_metadata: {},
      audit_items: [],
      confidence_summary: {}
    }

    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ templates: [] })
    }).mockResolvedValueOnce({
      ok: true,
      json: async () => mockSearchResponse
    })

    renderWithRouter(<ChatSearch />)

    const input = screen.getByPlaceholderText(/Ask a question about your documents/)
    fireEvent.change(input, { target: { value: 'show me invoices' } })
    fireEvent.submit(input.closest('form'))

    await waitFor(() => {
      expect(screen.getByText('Found 5 invoices')).toBeInTheDocument()
    })
  })

  it('disables input while loading', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ templates: [] })
    }).mockImplementationOnce(() => new Promise(resolve => setTimeout(resolve, 1000)))

    renderWithRouter(<ChatSearch />)

    const input = screen.getByPlaceholderText(/Ask a question about your documents/)
    fireEvent.change(input, { target: { value: 'test query' } })
    fireEvent.submit(input.closest('form'))

    await waitFor(() => {
      expect(input).toBeDisabled()
    })
  })

  it('displays error message on search failure', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ templates: [] })
    }).mockResolvedValueOnce({
      ok: false,
      json: async () => ({ detail: 'Search failed' })
    })

    renderWithRouter(<ChatSearch />)

    const input = screen.getByPlaceholderText(/Ask a question about your documents/)
    fireEvent.change(input, { target: { value: 'test query' } })
    fireEvent.submit(input.closest('form'))

    await waitFor(() => {
      expect(screen.getByText(/Search failed/)).toBeInTheDocument()
    })
  })

  it('displays timeout error message', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ templates: [] })
    }).mockImplementationOnce(() => {
      return new Promise((_, reject) => {
        setTimeout(() => reject({ name: 'AbortError' }), 100)
      })
    })

    renderWithRouter(<ChatSearch />)

    const input = screen.getByPlaceholderText(/Ask a question about your documents/)
    fireEvent.change(input, { target: { value: 'test query' } })
    fireEvent.submit(input.closest('form'))

    await waitFor(() => {
      expect(screen.getByText(/timed out/)).toBeInTheDocument()
    }, { timeout: 3000 })
  })

  it('clears input after submission', async () => {
    const mockSearchResponse = {
      answer: 'Test answer',
      results: [],
      total: 0,
      answer_metadata: {},
      audit_items: [],
      confidence_summary: {}
    }

    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ templates: [] })
    }).mockResolvedValueOnce({
      ok: true,
      json: async () => mockSearchResponse
    })

    renderWithRouter(<ChatSearch />)

    const input = screen.getByPlaceholderText(/Ask a question about your documents/)
    fireEvent.change(input, { target: { value: 'test query' } })
    fireEvent.submit(input.closest('form'))

    await waitFor(() => {
      expect(input.value).toBe('')
    })
  })

  it('loads templates on mount', async () => {
    const mockTemplates = [
      { id: 1, name: 'Invoice' },
      { id: 2, name: 'Contract' }
    ]

    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ templates: mockTemplates })
    })

    renderWithRouter(<ChatSearch />)

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/templates')
      )
    })
  })

  it('displays template filter when templates are loaded', async () => {
    const mockTemplates = [
      { id: 1, name: 'Invoice' },
      { id: 2, name: 'Contract' }
    ]

    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ templates: mockTemplates })
    })

    renderWithRouter(<ChatSearch />)

    await waitFor(() => {
      expect(screen.getByText('Filter by Template (optional)')).toBeInTheDocument()
    })
  })

  it('includes selected template in search request', async () => {
    const mockTemplates = [
      { id: 1, name: 'Invoice' }
    ]
    const mockSearchResponse = {
      answer: 'Test answer',
      results: [],
      total: 0,
      answer_metadata: {},
      audit_items: [],
      confidence_summary: {}
    }

    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ templates: mockTemplates })
    }).mockResolvedValueOnce({
      ok: true,
      json: async () => mockSearchResponse
    })

    renderWithRouter(<ChatSearch />)

    await waitFor(() => {
      expect(screen.getByText('Filter by Template (optional)')).toBeInTheDocument()
    })

    const select = screen.getByRole('combobox')
    fireEvent.change(select, { target: { value: '1' } })

    const input = screen.getByPlaceholderText(/Ask a question about your documents/)
    fireEvent.change(input, { target: { value: 'test query' } })
    fireEvent.submit(input.closest('form'))

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/search'),
        expect.objectContaining({
          body: expect.stringContaining('"template_id":"1"')
        })
      )
    })
  })
})
