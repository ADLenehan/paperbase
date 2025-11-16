import { useState } from 'react';
import CitationBadge from './CitationBadge';
import InlineAuditModal from './InlineAuditModal';
import BatchAuditModal from './BatchAuditModal';
import AnswerWithInlineCitations from './AnswerWithInlineCitations';
import {
  groupAuditItemsByDocument,
  calculateAverageConfidence,
  isAuditRecommended,
  getConfidenceLevelConfig,
  formatConfidencePercent
} from '../utils/confidenceHelpers';
import { useConfidenceThresholds } from '../hooks/useConfidenceThresholds';
import { extractFieldReferences } from '../utils/answerCitations';

/**
 * AnswerWithAudit - Enhanced answer display with audit metadata and citations
 *
 * Main component that wraps AI answers with confidence indicators, citations,
 * and links to the audit interface for low-confidence data.
 *
 * Props:
 * - answer: Natural language answer from Claude
 * - answerMetadata: { sources_used, low_confidence_warnings, confidence_level }
 * - auditItems: Array of { field_id, document_id, filename, field_name, field_value, confidence, audit_url } (FILTERED to query-relevant only)
 * - auditItemsFilteredCount: Number of audit items shown (query-relevant)
 * - auditItemsTotalCount: Total number of low-confidence fields in documents
 * - confidenceSummary: { high_confidence_count, medium_confidence_count, low_confidence_count, total_fields, avg_confidence, audit_recommended }
 * - fieldLineage: { queried_fields, field_contexts, synthetic_fields } (NEW)
 * - queryId: Query history identifier (NEW)
 * - documentsLink: URL to view source documents used in this answer (NEW)
 */
export default function AnswerWithAudit({
  answer,
  answerMetadata,
  auditItems,
  auditItemsFilteredCount,
  auditItemsTotalCount,
  confidenceSummary,
  fieldLineage,
  queryId,
  documentsLink,
  onFieldVerified, // Callback when a field is verified (optional)
  onBatchVerified, // Callback when batch of fields verified (optional)
  onAnswerRegenerate // Callback to regenerate answer (optional)
}) {
  const [showSources, setShowSources] = useState(false);
  const [showAuditFields, setShowAuditFields] = useState(true); // Show by default if there are items
  const [showAllFields, setShowAllFields] = useState(false); // Toggle to show all vs query-relevant only

  // Inline audit modal state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [currentField, setCurrentField] = useState(null);
  const [currentFieldIndex, setCurrentFieldIndex] = useState(0);
  const [verifiedFields, setVerifiedFields] = useState(new Set());

  // Batch audit modal state
  const [isBatchModalOpen, setIsBatchModalOpen] = useState(false);

  // Fetch dynamic confidence thresholds
  const thresholds = useConfidenceThresholds();

  // Handler to open inline modal for a specific field
  const handleOpenInlineAudit = (field, index) => {
    setCurrentField(field);
    setCurrentFieldIndex(index);
    setIsModalOpen(true);
  };

  // Handler to verify a field
  const handleFieldVerify = async (fieldId, action, correctedValue, notes) => {
    // Call parent callback if provided
    if (onFieldVerified) {
      await onFieldVerified(fieldId, action, correctedValue, notes);
    }

    // Mark as verified
    setVerifiedFields(prev => new Set([...prev, fieldId]));

    // Optionally regenerate answer
    if (onAnswerRegenerate) {
      await onAnswerRegenerate();
    }
  };

  // Handler to get next field in queue
  const handleGetNextField = () => {
    const unverifiedFields = auditItems.filter(item => !verifiedFields.has(item.field_id));

    if (unverifiedFields.length === 0) {
      return null; // No more fields
    }

    // Get next field
    const nextField = unverifiedFields[0];
    const nextIndex = auditItems.findIndex(item => item.field_id === nextField.field_id);

    setCurrentField(nextField);
    setCurrentFieldIndex(nextIndex);

    return nextField;
  };

  // Handler for batch verification
  const handleBatchVerify = async (verificationsMap) => {
    // Call parent batch callback if provided
    if (onBatchVerified) {
      await onBatchVerified(verificationsMap);
    } else if (onFieldVerified) {
      // Fallback: process each verification individually
      for (const [fieldId, verification] of Object.entries(verificationsMap)) {
        await onFieldVerified(
          parseInt(fieldId),
          verification.action,
          verification.corrected_value,
          verification.notes
        );
      }
    }

    // Mark all as verified
    const newVerifiedFields = new Set(verifiedFields);
    Object.keys(verificationsMap).forEach(fieldId => {
      newVerifiedFields.add(parseInt(fieldId));
    });
    setVerifiedFields(newVerifiedFields);

    // Optionally regenerate answer (if not handled by batch callback)
    if (onAnswerRegenerate && !onBatchVerified) {
      await onAnswerRegenerate();
    }
  };

  // Backward compatibility - if no audit data, show simple answer
  if (!auditItems || auditItems.length === 0) {
    return (
      <div className="prose prose-sm max-w-none">
        <p className="text-gray-900">{answer}</p>
      </div>
    );
  }

  // Calculate queue position (now safe since we checked auditItems exists)
  const queuePosition = auditItems.length > 0
    ? `${currentFieldIndex + 1} of ${auditItems.length}`
    : null;

  // Group audit items by document
  const groupedItems = groupAuditItemsByDocument(auditItems);
  const documentCount = Object.keys(groupedItems).length;

  // Get confidence level configuration
  const confidenceLevel = answerMetadata?.confidence_level || 'unknown';
  const levelConfig = getConfidenceLevelConfig(confidenceLevel);

  // Determine if we should show the warning banner
  const showWarningBanner = isAuditRecommended(confidenceSummary);

  // Check if answer has field references
  const hasFieldReferences = answer && extractFieldReferences(answer).length > 0;

  // Handler for inline citation click
  const handleInlineCitationClick = (citationData, index) => {
    // Find the field in auditItems
    const field = auditItems.find(
      item => item.field_id === citationData.field_id &&
              item.document_id === citationData.document_id
    );

    if (field) {
      const globalIndex = auditItems.findIndex(item => item.field_id === field.field_id);
      handleOpenInlineAudit(field, globalIndex);
    }
  };

  return (
    <div className="space-y-3">
      {/* Main Answer with Inline Citations */}
      {hasFieldReferences ? (
        <AnswerWithInlineCitations
          answerText={answer}
          auditItems={auditItems}
          onCitationClick={handleInlineCitationClick}
        />
      ) : (
        /* Fallback: Plain text if no field references */
        <div className="prose prose-sm max-w-none">
          <p className="text-gray-900">{answer}</p>
        </div>
      )}

      {/* Source Documents Link - NEW: Query History Integration */}
      {documentsLink && (
        <div className="border border-blue-200 rounded-lg bg-blue-50 p-3">
          <a
            href={documentsLink}
            className="flex items-center gap-2 text-sm font-medium text-blue-700 hover:text-blue-900 hover:underline transition-colors"
          >
            <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            View the {documentCount} source document{documentCount !== 1 ? 's' : ''} used in this answer
          </a>
        </div>
      )}

      {/* Confidence Banner - Show if low confidence detected */}
      {showWarningBanner && (
        <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4 rounded-r-lg">
          <div className="flex items-start">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-yellow-400" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="ml-3 flex-1">
              <h3 className="text-sm font-medium text-yellow-800">
                Data Quality Notice
              </h3>
              <div className="mt-2 text-sm text-yellow-700">
                <p>
                  This answer uses {auditItems.length} field{auditItems.length !== 1 ? 's' : ''} with low confidence scores.
                  {auditItemsTotalCount > auditItems.length && (
                    <span className="ml-1 text-gray-600">
                      (Showing {auditItems.length} of {auditItemsTotalCount} low-confidence fields in these documents)
                    </span>
                  )}
                </p>
                {fieldLineage && fieldLineage.queried_fields && fieldLineage.queried_fields.length > 0 && (
                  <p className="mt-1 text-xs text-gray-600">
                    Query matched on: {fieldLineage.queried_fields.slice(0, 5).join(', ')}
                    {fieldLineage.queried_fields.length > 5 && ` +${fieldLineage.queried_fields.length - 5} more`}
                  </p>
                )}
              </div>
              <div className="mt-3">
                <button
                  onClick={() => setShowAuditFields(!showAuditFields)}
                  className="text-sm font-medium text-yellow-800 hover:text-yellow-900 underline"
                >
                  {showAuditFields ? 'Hide' : 'Show'} fields needing review →
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Source Citations - Collapsible */}
      {answerMetadata?.sources_used && answerMetadata.sources_used.length > 0 && (
        <div className="border border-gray-200 rounded-lg bg-gray-50">
          <button
            onClick={() => setShowSources(!showSources)}
            className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-gray-100 transition-colors rounded-lg"
          >
            <div className="flex items-center gap-2">
              <span className="text-lg">📄</span>
              <span className="text-sm font-medium text-gray-900">
                Sources Used ({documentCount} document{documentCount !== 1 ? 's' : ''})
              </span>
            </div>
            <svg
              className={`w-5 h-5 text-gray-500 transition-transform ${showSources ? 'rotate-180' : ''}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          {showSources && (
            <div className="px-4 pb-3 space-y-2 border-t border-gray-200 pt-3">
              {Object.entries(groupedItems).map(([docId, { filename, fields }]) => {
                const avgConfidence = calculateAverageConfidence(fields);
                const needsReview = avgConfidence < thresholds.high;  // Use dynamic threshold

                return (
                  <div key={docId} className="text-sm">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-gray-900">
                        {filename}
                      </span>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-600">
                          avg: {formatConfidencePercent(avgConfidence)}
                        </span>
                        {needsReview && (
                          <span className="text-yellow-600 text-xs">⚠</span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Fields Needing Review - Expandable */}
      {auditItems.length > 0 && showAuditFields && (
        <div className="border border-yellow-200 rounded-lg bg-yellow-50">
          <div className="px-4 py-3 border-b border-yellow-200 bg-yellow-100 rounded-t-lg">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-lg">🔍</span>
                <span className="text-sm font-semibold text-gray-900">
                  Fields Needing Review ({auditItems.length})
                </span>
              </div>
              <div className="flex items-center gap-3">
                {auditItemsTotalCount > auditItems.length && (
                  <span className="text-xs text-gray-600 bg-white px-2 py-1 rounded">
                    Filtered: {auditItems.length} of {auditItemsTotalCount} relevant to this query
                  </span>
                )}
                <button
                  onClick={() => setIsBatchModalOpen(true)}
                  className="px-3 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-1.5"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                  </svg>
                  Review All
                </button>
              </div>
            </div>
            {fieldLineage && fieldLineage.queried_fields && fieldLineage.queried_fields.length > 0 && (
              <div className="mt-2 text-xs text-gray-600">
                <span className="font-medium">Query fields:</span> {fieldLineage.queried_fields.join(', ')}
              </div>
            )}
          </div>

          <div className="p-3 space-y-3 max-h-96 overflow-y-auto">
            {Object.entries(groupedItems).map(([docId, { filename, fields }]) => (
              <div key={docId} className="space-y-2">
                {/* Document header */}
                <div className="text-sm font-medium text-gray-900 flex items-center gap-2">
                  <span>📄</span>
                  <span>{filename}</span>
                </div>

                {/* Fields for this document */}
                <div className="space-y-1.5 pl-6">
                  {fields.map((field, idx) => {
                    const globalIndex = auditItems.findIndex(item => item.field_id === field.field_id);
                    const isVerified = verifiedFields.has(field.field_id);

                    return (
                      <div key={`${field.field_id}-${idx}`} className="relative">
                        <CitationBadge
                          fieldId={field.field_id}
                          documentId={field.document_id}
                          fieldName={field.field_name}
                          fieldValue={field.field_value}
                          confidence={field.confidence}
                          auditUrl={field.audit_url}
                          filename={filename}
                          variant="standalone"
                          onClick={(e) => {
                            e.preventDefault();
                            handleOpenInlineAudit(field, globalIndex);
                          }}
                        />
                        {isVerified && (
                          <div className="absolute top-2 right-2 bg-green-500 text-white text-xs px-2 py-0.5 rounded-full">
                            ✓ Verified
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Overall Data Quality Footer */}
      {confidenceSummary && (
        <div className="px-4 py-2 bg-gray-50 border border-gray-200 rounded-lg">
          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              <span>📊</span>
              <span className="font-medium text-gray-700">Data Quality:</span>
            </div>
            <div className="flex items-center gap-3 text-gray-600">
              {confidenceSummary.high_confidence_count > 0 && (
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 bg-green-500 rounded-full"></span>
                  {confidenceSummary.high_confidence_count} high
                </span>
              )}
              {confidenceSummary.medium_confidence_count > 0 && (
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 bg-yellow-500 rounded-full"></span>
                  {confidenceSummary.medium_confidence_count} medium
                </span>
              )}
              {confidenceSummary.low_confidence_count > 0 && (
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 bg-red-500 rounded-full"></span>
                  {confidenceSummary.low_confidence_count} low
                </span>
              )}
              {confidenceSummary.avg_confidence !== undefined && (
                <span className="ml-2 font-medium text-gray-900">
                  (avg: {formatConfidencePercent(confidenceSummary.avg_confidence)})
                </span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Inline Audit Modal */}
      <InlineAuditModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        field={currentField}
        onVerify={handleFieldVerify}
        onNext={handleGetNextField}
        queuePosition={queuePosition}
        regenerateAnswer={!!onAnswerRegenerate}
      />

      {/* Batch Audit Modal */}
      <BatchAuditModal
        isOpen={isBatchModalOpen}
        onClose={() => setIsBatchModalOpen(false)}
        fields={auditItems}
        onBatchVerify={handleBatchVerify}
        regenerateAnswer={!!onAnswerRegenerate}
      />
    </div>
  );
}
