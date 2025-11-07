/**
 * Answer Citations Utility
 *
 * Parses answer text with field reference markers [[FIELD:name:doc_id]]
 * and replaces them with citation components showing confidence and bbox.
 *
 * Example input:
 * "The back rise for size 2 is 7 1/2 inches [[FIELD:back_rise_size_2:123]]"
 *
 * Example output:
 * "The back rise for size 2 is 7 1/2 inches" + <CitationBadge />
 */

/**
 * Extract field references from answer text
 *
 * @param {string} answerText - Answer with [[FIELD:name:id]] markers
 * @returns {Array} Array of {fieldName, documentId, startIndex, endIndex}
 */
export function extractFieldReferences(answerText) {
  if (!answerText) return [];

  // Pattern: [[FIELD:field_name:document_id]]
  const pattern = /\[\[FIELD:([^:]+):(\d+)\]\]/g;
  const references = [];
  let match;

  while ((match = pattern.exec(answerText)) !== null) {
    references.push({
      fieldName: match[1],
      documentId: parseInt(match[2], 10),
      startIndex: match.index,
      endIndex: match.index + match[0].length,
      markerText: match[0]
    });
  }

  return references;
}

/**
 * Match field references to audit items to get confidence and bbox data
 *
 * @param {Array} fieldReferences - Output from extractFieldReferences
 * @param {Array} auditItems - Audit items from backend with confidence/bbox
 * @returns {Map} Map of markerText -> auditItem
 */
export function matchReferencesToAuditItems(fieldReferences, auditItems) {
  const matchMap = new Map();

  for (const ref of fieldReferences) {
    // Find matching audit item by field_name and document_id
    const matchingItem = auditItems.find(
      item => item.field_name === ref.fieldName && item.document_id === ref.documentId
    );

    if (matchingItem) {
      matchMap.set(ref.markerText, {
        ...matchingItem,
        reference: ref
      });
    } else {
      // No audit item found - might be high confidence field not in audit queue
      // We'll render it without confidence badge
      matchMap.set(ref.markerText, {
        field_name: ref.fieldName,
        document_id: ref.documentId,
        reference: ref,
        confidence: null // Unknown confidence
      });
    }
  }

  return matchMap;
}

/**
 * Parse answer text into segments for rendering
 *
 * @param {string} answerText - Answer with [[FIELD:name:id]] markers
 * @param {Map} citationMap - Map from matchReferencesToAuditItems
 * @returns {Array} Array of {type: 'text'|'citation', content, data}
 */
export function parseAnswerWithCitations(answerText, citationMap) {
  if (!answerText) return [{type: 'text', content: answerText}];

  const segments = [];
  const references = extractFieldReferences(answerText);

  if (references.length === 0) {
    // No citations, return plain text
    return [{type: 'text', content: answerText}];
  }

  let lastIndex = 0;

  // Sort references by position
  references.sort((a, b) => a.startIndex - b.startIndex);

  for (const ref of references) {
    // Add text before citation
    if (ref.startIndex > lastIndex) {
      segments.push({
        type: 'text',
        content: answerText.substring(lastIndex, ref.startIndex)
      });
    }

    // Add citation segment
    const citationData = citationMap.get(ref.markerText);
    segments.push({
      type: 'citation',
      content: ref.markerText,
      data: citationData || {
        field_name: ref.fieldName,
        document_id: ref.documentId,
        confidence: null
      }
    });

    lastIndex = ref.endIndex;
  }

  // Add remaining text
  if (lastIndex < answerText.length) {
    segments.push({
      type: 'text',
      content: answerText.substring(lastIndex)
    });
  }

  return segments;
}

/**
 * Complete pipeline: parse answer text and prepare for rendering
 *
 * @param {string} answerText - Answer with [[FIELD:name:id]] markers
 * @param {Array} auditItems - Audit items with confidence/bbox
 * @returns {Array} Segments ready for rendering
 */
export function prepareAnswerWithCitations(answerText, auditItems = []) {
  const references = extractFieldReferences(answerText);
  const citationMap = matchReferencesToAuditItems(references, auditItems);
  return parseAnswerWithCitations(answerText, citationMap);
}

/**
 * Strip field reference markers from text (for plain text display)
 *
 * @param {string} answerText - Answer with [[FIELD:name:id]] markers
 * @returns {string} Clean text without markers
 */
export function stripFieldReferences(answerText) {
  if (!answerText) return '';
  return answerText.replace(/\[\[FIELD:[^:]+:\d+\]\]/g, '');
}
