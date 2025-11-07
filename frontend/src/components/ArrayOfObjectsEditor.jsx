import { useState } from 'react';
import PropTypes from 'prop-types';

/**
 * ArrayOfObjectsEditor - Interactive editor for structured arrays
 *
 * Allows users to add/remove/edit items in structured arrays (e.g., line items).
 * Each item is edited via a form-based interface.
 *
 * Design: Collapsible cards with form fields
 * Pattern: Similar to order line items, product lists
 */
export default function ArrayOfObjectsEditor({
  value = [],
  onChange,
  schema = null,
  allowAddItems = true,
  disabled = false
}) {
  const [expandedItems, setExpandedItems] = useState(new Set([0])); // First item expanded by default

  // Infer schema from first item if not provided
  const inferredSchema = schema || (value.length > 0
    ? Object.keys(value[0]).map(key => ({
        key,
        type: typeof value[0][key],
        label: key.replace(/_/g, ' ')
      }))
    : []
  );

  const toggleExpanded = (index) => {
    const newExpanded = new Set(expandedItems);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedItems(newExpanded);
  };

  const handleItemChange = (index, field, newValue) => {
    const updatedItems = [...value];
    updatedItems[index] = { ...updatedItems[index], [field]: newValue };
    onChange(updatedItems);
  };

  const handleAddItem = () => {
    const newItem = Object.fromEntries(
      inferredSchema.map(field => [field.key, ''])
    );
    onChange([...value, newItem]);
    setExpandedItems(new Set([...expandedItems, value.length]));
  };

  const handleRemoveItem = (index) => {
    onChange(value.filter((_, i) => i !== index));
    const newExpanded = new Set(expandedItems);
    newExpanded.delete(index);
    setExpandedItems(newExpanded);
  };

  if (value.length === 0 && !allowAddItems) {
    return (
      <div className="text-center py-8 text-gray-400 text-sm border border-gray-200 rounded-lg bg-gray-50">
        No items
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {value.map((item, index) => {
        const isExpanded = expandedItems.has(index);

        return (
          <div
            key={index}
            className="border border-gray-200 rounded-lg bg-white overflow-hidden"
          >
            {/* Item Header */}
            <div
              className="flex items-center justify-between p-3 bg-gray-50 cursor-pointer hover:bg-gray-100 transition-colors"
              onClick={() => toggleExpanded(index)}
            >
              <div className="flex items-center gap-2">
                <svg
                  className={`w-4 h-4 text-gray-500 transition-transform ${isExpanded ? 'rotate-90' : ''}`}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
                <span className="font-medium text-sm text-gray-900">
                  Item {index + 1}
                </span>
                {/* Show first field value as preview */}
                {!isExpanded && inferredSchema.length > 0 && (
                  <span className="text-xs text-gray-500">
                    {String(item[inferredSchema[0].key] || '').substring(0, 30)}
                    {String(item[inferredSchema[0].key] || '').length > 30 ? '...' : ''}
                  </span>
                )}
              </div>

              {!disabled && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleRemoveItem(index);
                  }}
                  className="text-red-500 hover:text-red-700 hover:bg-red-50 p-1.5 rounded transition-colors"
                  title="Remove item"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              )}
            </div>

            {/* Item Form (Expanded) */}
            {isExpanded && (
              <div className="p-4 space-y-3">
                {inferredSchema.map((field) => (
                  <div key={field.key}>
                    <label className="block text-xs font-medium text-gray-700 mb-1 capitalize">
                      {field.label || field.key}
                    </label>
                    <input
                      type={field.type === 'number' ? 'number' : 'text'}
                      value={item[field.key] || ''}
                      onChange={(e) => handleItemChange(index, field.key, e.target.value)}
                      disabled={disabled}
                      className="w-full px-3 py-2 text-sm border border-gray-200 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-50 disabled:cursor-not-allowed"
                      placeholder={`Enter ${field.label || field.key}...`}
                    />
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}

      {/* Add Item Button */}
      {allowAddItems && !disabled && (
        <button
          onClick={handleAddItem}
          className="w-full py-3 text-sm font-medium text-gray-600 border-2 border-dashed border-gray-300 rounded-lg hover:border-blue-400 hover:text-blue-600 transition-colors"
        >
          + Add Item
        </button>
      )}

      {/* Helper Text */}
      {!disabled && value.length > 0 && (
        <div className="text-xs text-gray-500">
          Click to expand/collapse items • {value.length} {value.length === 1 ? 'item' : 'items'} total
        </div>
      )}
    </div>
  );
}

ArrayOfObjectsEditor.propTypes = {
  value: PropTypes.arrayOf(PropTypes.object),
  onChange: PropTypes.func.isRequired,
  schema: PropTypes.arrayOf(
    PropTypes.shape({
      key: PropTypes.string.isRequired,
      type: PropTypes.string,
      label: PropTypes.string
    })
  ),
  allowAddItems: PropTypes.bool,
  disabled: PropTypes.bool
};
