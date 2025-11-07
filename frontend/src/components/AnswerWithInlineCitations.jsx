import { prepareAnswerWithCitations } from '../utils/answerCitations';
import CitationBadge from './CitationBadge';

/**
 * AnswerWithInlineCitations - Renders answer text with inline confidence badges
 *
 * Parses answer text containing [[FIELD:name:id]] markers and replaces them
 * with confidence badges that show confidence scores and link to PDF highlights.
 *
 * Props:
 * - answerText: Answer string with [[FIELD:name:id]] markers
 * - auditItems: Array of audit items with confidence/bbox data
 * - onCitationClick: Optional callback when citation is clicked
 */
export default function AnswerWithInlineCitations({
  answerText,
  auditItems = [],
  onCitationClick
}) {
  // Parse answer text into segments (text + citations)
  const segments = prepareAnswerWithCitations(answerText, auditItems);

  return (
    <div className="prose prose-sm max-w-none">
      <p className="text-gray-900 leading-relaxed">
        {segments.map((segment, idx) => {
          if (segment.type === 'text') {
            // Render plain text
            return <span key={idx}>{segment.content}</span>;
          } else if (segment.type === 'citation') {
            // Render citation badge
            const data = segment.data || {};

            return (
              <CitationBadge
                key={idx}
                fieldId={data.field_id}
                documentId={data.document_id}
                fieldName={data.field_name}
                fieldValue={data.field_value}
                confidence={data.confidence}
                auditUrl={data.audit_url}
                filename={data.filename}
                variant="inline"
                onClick={(e) => {
                  if (onCitationClick) {
                    e.preventDefault();
                    onCitationClick(data, idx);
                  }
                }}
              />
            );
          }
          return null;
        })}
      </p>
    </div>
  );
}
