import { useState } from 'react';
import PropTypes from 'prop-types';

/**
 * ArrayOfObjectsDisplay - Read-only display for structured arrays
 *
 * Displays arrays of objects (e.g., line items, product specs).
 * Shows compact cards with option to expand.
 *
 * Design: Card-based layout for better readability
 * Pattern: Similar to product lists, order summaries
 */
export default function ArrayOfObjectsDisplay({ items = [], maxItems = 3, onViewAll, className = '' }) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (items.length === 0) {
    return (
      <span className="text-xs text-gray-400 italic">Empty list</span>
    );
  }

  const visibleItems = maxItems > 0 && !isExpanded ? items.slice(0, maxItems) : items;
  const hiddenCount = items.length - visibleItems.length;

  const handleToggleExpand = () => {
    if (onViewAll) {
      onViewAll();
    } else {
      setIsExpanded(!isExpanded);
    }
  };

  // Get all unique keys from all items
  const allKeys = [...new Set(items.flatMap(item => Object.keys(item)))];

  return (
    <div className={`space-y-2 ${className}`}>
      <div className="space-y-2">
        {visibleItems.map((item, index) => (
          <div
            key={index}
            className="bg-white border border-gray-200 rounded-lg p-3 hover:border-gray-300 transition-colors"
          >
            <div className="flex items-start justify-between mb-2">
              <span className="text-xs font-medium text-gray-500">Item {index + 1}</span>
            </div>

            <div className="space-y-1.5">
              {Object.entries(item).map(([key, value]) => (
                <div key={key} className="flex items-start gap-2">
                  <span className="text-xs text-gray-500 min-w-[80px] capitalize">
                    {key.replace(/_/g, ' ')}:
                  </span>
                  <span className="text-xs text-gray-900 font-medium flex-1">
                    {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Expand/Collapse Button */}
      {items.length > maxItems && (
        <div className="flex justify-center">
          <button
            onClick={handleToggleExpand}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-600 bg-gray-50 border border-gray-200 rounded hover:bg-gray-100 transition-colors"
          >
            {isExpanded ? (
              <>
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                </svg>
                Show less
              </>
            ) : (
              <>
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
                View all {items.length} items
              </>
            )}
          </button>
        </div>
      )}

      {/* List Info */}
      <div className="text-xs text-gray-500">
        {items.length} {items.length === 1 ? 'item' : 'items'} × {allKeys.length} {allKeys.length === 1 ? 'field' : 'fields'}
      </div>
    </div>
  );
}

ArrayOfObjectsDisplay.propTypes = {
  items: PropTypes.arrayOf(PropTypes.object),
  maxItems: PropTypes.number,
  onViewAll: PropTypes.func,
  className: PropTypes.string
};
