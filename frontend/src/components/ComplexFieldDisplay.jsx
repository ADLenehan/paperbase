import PropTypes from 'prop-types';
import ArrayDisplay from './ArrayDisplay';
import TableDisplay from './TableDisplay';
import ArrayOfObjectsDisplay from './ArrayOfObjectsDisplay';

/**
 * ComplexFieldDisplay - Smart component that detects field type and renders appropriately
 *
 * This is the main component to use for displaying extracted fields.
 * It automatically detects the field_type and renders the appropriate display component.
 *
 * Supported types:
 * - text, date, number, boolean → Plain text
 * - array → ArrayDisplay (chips)
 * - table → TableDisplay (headers + rows)
 * - array_of_objects → ArrayOfObjectsDisplay (cards)
 *
 * Design: Simple, powerful, single entry point
 * Pattern: Polymorphic component based on data type
 */
export default function ComplexFieldDisplay({
  field,
  mode = 'compact',
  onEdit,
  className = ''
}) {
  const fieldType = field.field_type || 'text';
  const value = fieldType === 'text' || fieldType === 'date' || fieldType === 'number' || fieldType === 'boolean'
    ? field.field_value
    : field.field_value_json;

  // Handle null/undefined values
  if (value === null || value === undefined) {
    return (
      <span className={`text-xs text-gray-400 italic ${className}`}>
        (not extracted)
      </span>
    );
  }

  // Render based on field type
  switch (fieldType) {
    case 'array':
      return (
        <ArrayDisplay
          items={Array.isArray(value) ? value : []}
          maxItems={mode === 'compact' ? 5 : 0}
          onViewAll={onEdit}
          className={className}
        />
      );

    case 'table':
      return (
        <TableDisplay
          data={typeof value === 'object' ? value : {}}
          maxRows={mode === 'compact' ? 3 : 0}
          onViewAll={onEdit}
          className={className}
        />
      );

    case 'array_of_objects':
      return (
        <ArrayOfObjectsDisplay
          items={Array.isArray(value) ? value : []}
          maxItems={mode === 'compact' ? 3 : 0}
          onViewAll={onEdit}
          className={className}
        />
      );

    case 'boolean':
      return (
        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${className} ${
          value === true || value === 'true' || value === 'True' || value === '1'
            ? 'bg-green-50 text-green-700 border border-green-200'
            : 'bg-red-50 text-red-700 border border-red-200'
        }`}>
          {value === true || value === 'true' || value === 'True' || value === '1' ? 'Yes' : 'No'}
        </span>
      );

    case 'text':
    case 'date':
    case 'number':
    default:
      // Simple types: Display as plain text
      const displayValue = String(value || '');
      const isTruncated = mode === 'compact' && displayValue.length > 100;

      return (
        <span className={`text-sm text-gray-900 ${className}`}>
          {isTruncated ? displayValue.substring(0, 100) + '...' : displayValue}
        </span>
      );
  }
}

ComplexFieldDisplay.propTypes = {
  field: PropTypes.shape({
    field_name: PropTypes.string.isRequired,
    field_type: PropTypes.oneOf([
      'text',
      'date',
      'number',
      'boolean',
      'array',
      'table',
      'array_of_objects'
    ]),
    field_value: PropTypes.oneOfType([PropTypes.string, PropTypes.number, PropTypes.bool]),
    field_value_json: PropTypes.any,
    confidence_score: PropTypes.number
  }).isRequired,
  mode: PropTypes.oneOf(['compact', 'expanded']),
  onEdit: PropTypes.func,
  className: PropTypes.string
};
