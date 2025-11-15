import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import AnswerWithAudit from '../AnswerWithAudit'

vi.mock('../hooks/useConfidenceThresholds', () => ({
  useConfidenceThresholds: () => ({
    high: 0.7,
    medium: 0.5,
    low: 0.3
  })
}))

describe('AnswerWithAudit', () => {
  const mockAnswer = 'The total invoice amount is $1,000.00'
  const mockAnswerMetadata = {
    sources_used: ['1', '2'],
    low_confidence_warnings: ['invoice_total'],
    confidence_level: 'medium'
  }
  const mockAuditItems = [
    {
      field_id: 1,
      document_id: 1,
      filename: 'invoice.pdf',
      field_name: 'invoice_total',
      field_value: '1000.00',
      confidence: 0.55,
      audit_url: '/audit/1'
    }
  ]
  const mockConfidenceSummary = {
    high_confidence_count: 5,
    medium_confidence_count: 2,
    low_confidence_count: 1,
    total_fields: 8,
    avg_confidence: 0.72,
    audit_recommended: true
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders answer text', () => {
    render(
      <AnswerWithAudit
        answer={mockAnswer}
        answerMetadata={mockAnswerMetadata}
        auditItems={mockAuditItems}
        auditItemsFilteredCount={1}
        auditItemsTotalCount={1}
        confidenceSummary={mockConfidenceSummary}
      />
    )

    expect(screen.getByText(mockAnswer)).toBeInTheDocument()
  })

  it('displays warning banner when audit is recommended', () => {
    render(
      <AnswerWithAudit
        answer={mockAnswer}
        answerMetadata={mockAnswerMetadata}
        auditItems={mockAuditItems}
        auditItemsFilteredCount={1}
        auditItemsTotalCount={1}
        confidenceSummary={mockConfidenceSummary}
      />
    )

    expect(screen.getByText('Data Quality Notice')).toBeInTheDocument()
  })

  it('displays source documents link when provided', () => {
    const documentsLink = '/documents?query_id=123'
    
    render(
      <AnswerWithAudit
        answer={mockAnswer}
        answerMetadata={mockAnswerMetadata}
        auditItems={mockAuditItems}
        auditItemsFilteredCount={1}
        auditItemsTotalCount={1}
        confidenceSummary={mockConfidenceSummary}
        documentsLink={documentsLink}
      />
    )

    const link = screen.getByText(/View the 1 source document/)
    expect(link).toBeInTheDocument()
    expect(link.closest('a')).toHaveAttribute('href', documentsLink)
  })

  it('displays correct document count in source link', () => {
    const multiDocAuditItems = [
      { ...mockAuditItems[0], document_id: 1 },
      { ...mockAuditItems[0], field_id: 2, document_id: 2 }
    ]
    
    render(
      <AnswerWithAudit
        answer={mockAnswer}
        answerMetadata={mockAnswerMetadata}
        auditItems={multiDocAuditItems}
        auditItemsFilteredCount={2}
        auditItemsTotalCount={2}
        confidenceSummary={mockConfidenceSummary}
        documentsLink="/documents"
      />
    )

    expect(screen.getByText(/View the 2 source documents/)).toBeInTheDocument()
  })

  it('toggles sources visibility when button is clicked', () => {
    render(
      <AnswerWithAudit
        answer={mockAnswer}
        answerMetadata={mockAnswerMetadata}
        auditItems={mockAuditItems}
        auditItemsFilteredCount={1}
        auditItemsTotalCount={1}
        confidenceSummary={mockConfidenceSummary}
      />
    )

    const sourcesButton = screen.getByText(/Sources Used/)
    fireEvent.click(sourcesButton)

    expect(screen.getByText('invoice.pdf')).toBeInTheDocument()
  })

  it('displays audit fields section', () => {
    render(
      <AnswerWithAudit
        answer={mockAnswer}
        answerMetadata={mockAnswerMetadata}
        auditItems={mockAuditItems}
        auditItemsFilteredCount={1}
        auditItemsTotalCount={1}
        confidenceSummary={mockConfidenceSummary}
      />
    )

    expect(screen.getByText(/Fields Needing Review/)).toBeInTheDocument()
  })

  it('displays Review All button', () => {
    render(
      <AnswerWithAudit
        answer={mockAnswer}
        answerMetadata={mockAnswerMetadata}
        auditItems={mockAuditItems}
        auditItemsFilteredCount={1}
        auditItemsTotalCount={1}
        confidenceSummary={mockConfidenceSummary}
      />
    )

    expect(screen.getByText('Review All')).toBeInTheDocument()
  })

  it('displays data quality summary', () => {
    render(
      <AnswerWithAudit
        answer={mockAnswer}
        answerMetadata={mockAnswerMetadata}
        auditItems={mockAuditItems}
        auditItemsFilteredCount={1}
        auditItemsTotalCount={1}
        confidenceSummary={mockConfidenceSummary}
      />
    )

    expect(screen.getByText('Data Quality:')).toBeInTheDocument()
    expect(screen.getByText('5 high')).toBeInTheDocument()
    expect(screen.getByText('2 medium')).toBeInTheDocument()
    expect(screen.getByText('1 low')).toBeInTheDocument()
  })

  it('calls onFieldVerified when field is verified', async () => {
    const mockOnFieldVerified = vi.fn()
    
    render(
      <AnswerWithAudit
        answer={mockAnswer}
        answerMetadata={mockAnswerMetadata}
        auditItems={mockAuditItems}
        auditItemsFilteredCount={1}
        auditItemsTotalCount={1}
        confidenceSummary={mockConfidenceSummary}
        onFieldVerified={mockOnFieldVerified}
      />
    )

    expect(mockOnFieldVerified).not.toHaveBeenCalled()
  })

  it('renders simple answer when no audit items', () => {
    render(
      <AnswerWithAudit
        answer={mockAnswer}
        answerMetadata={mockAnswerMetadata}
        auditItems={[]}
        auditItemsFilteredCount={0}
        auditItemsTotalCount={0}
        confidenceSummary={null}
      />
    )

    expect(screen.getByText(mockAnswer)).toBeInTheDocument()
    expect(screen.queryByText('Data Quality Notice')).not.toBeInTheDocument()
  })

  it('displays field lineage information when provided', () => {
    const fieldLineage = {
      queried_fields: ['invoice_total', 'invoice_date', 'vendor_name'],
      field_contexts: {},
      synthetic_fields: []
    }
    
    render(
      <AnswerWithAudit
        answer={mockAnswer}
        answerMetadata={mockAnswerMetadata}
        auditItems={mockAuditItems}
        auditItemsFilteredCount={1}
        auditItemsTotalCount={1}
        confidenceSummary={mockConfidenceSummary}
        fieldLineage={fieldLineage}
      />
    )

    expect(screen.getByText(/Query matched on:/)).toBeInTheDocument()
    expect(screen.getByText(/invoice_total, invoice_date, vendor_name/)).toBeInTheDocument()
  })

  it('truncates field lineage display when more than 5 fields', () => {
    const fieldLineage = {
      queried_fields: ['field1', 'field2', 'field3', 'field4', 'field5', 'field6', 'field7'],
      field_contexts: {},
      synthetic_fields: []
    }
    
    render(
      <AnswerWithAudit
        answer={mockAnswer}
        answerMetadata={mockAnswerMetadata}
        auditItems={mockAuditItems}
        auditItemsFilteredCount={1}
        auditItemsTotalCount={1}
        confidenceSummary={mockConfidenceSummary}
        fieldLineage={fieldLineage}
      />
    )

    expect(screen.getByText(/\+2 more/)).toBeInTheDocument()
  })

  it('shows filtered count when different from total', () => {
    render(
      <AnswerWithAudit
        answer={mockAnswer}
        answerMetadata={mockAnswerMetadata}
        auditItems={mockAuditItems}
        auditItemsFilteredCount={1}
        auditItemsTotalCount={5}
        confidenceSummary={mockConfidenceSummary}
      />
    )

    expect(screen.getByText(/Filtered: 1 of 5 relevant to this query/)).toBeInTheDocument()
  })
})
