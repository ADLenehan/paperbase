import PropTypes from 'prop-types';

/**
 * ArrayDisplay - Read-only chip-based array display
 *
 * Displays simple arrays as styled chips/badges.
 * Used for fields like colors, tags, categories, etc.
 *
 * Design: Simple, compact, scannable
 * Pattern: Similar to Gmail labels, Slack mentions, GitHub topics
 */
export default function ArrayDisplay({ items = [], maxItems = 5, onViewAll }) {
  const visibleItems = maxItems > 0 ? items.slice(0, maxItems) : items;
  const hiddenCount = items.length - visibleItems.length;

  if (items.length === 0) {
    return (
      <span className="text-xs text-gray-400 italic">Empty array</span>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {visibleItems.map((item, index) => (
        <span
          key={index}
          className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200"
          title={String(item)}
        >
          {String(item)}
        </span>
      ))}

      {hiddenCount > 0 && (
        <button
          onClick={onViewAll}
          className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600 border border-gray-200 hover:bg-gray-200 transition-colors"
          title={`View all ${items.length} items`}
        >
          +{hiddenCount} more
        </button>
      )}
    </div>
  );
}

ArrayDisplay.propTypes = {
  items: PropTypes.arrayOf(
    PropTypes.oneOfType([PropTypes.string, PropTypes.number, PropTypes.bool])
  ),
  maxItems: PropTypes.number,
  onViewAll: PropTypes.func
};
