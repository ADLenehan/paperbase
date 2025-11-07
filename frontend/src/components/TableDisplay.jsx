import { useState } from 'react';
import PropTypes from 'prop-types';

/**
 * TableDisplay - Read-only table display with headers and rows
 *
 * Displays table data extracted from documents (e.g., line items, grading charts).
 * Shows preview with option to expand full table in modal.
 *
 * Design: Compact preview → Full modal view
 * Pattern: Similar to Excel/Google Sheets preview
 */
export default function TableDisplay({ data = {}, maxRows = 5, onViewAll, className = '' }) {
  const [isExpanded, setIsExpanded] = useState(false);

  const { headers = [], rows = [] } = data;

  if (!headers.length || !rows.length) {
    return (
      <span className="text-xs text-gray-400 italic">Empty table</span>
    );
  }

  const visibleRows = maxRows > 0 && !isExpanded ? rows.slice(0, maxRows) : rows;
  const hiddenRowCount = rows.length - visibleRows.length;

  const handleToggleExpand = () => {
    if (onViewAll) {
      onViewAll();
    } else {
      setIsExpanded(!isExpanded);
    }
  };

  return (
    <div className={`space-y-2 ${className}`}>
      <div className="overflow-x-auto border border-gray-200 rounded-lg bg-white">
        <table className="min-w-full divide-y divide-gray-200 text-xs">
          <thead className="bg-gray-50">
            <tr>
              {headers.map((header, index) => (
                <th
                  key={index}
                  className="px-3 py-2 text-left text-xs font-medium text-gray-700 uppercase tracking-wider"
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-100">
            {visibleRows.map((row, rowIndex) => (
              <tr key={rowIndex} className="hover:bg-gray-50 transition-colors">
                {Array.isArray(row) ? (
                  // Array-based rows: ["value1", "value2", ...]
                  row.map((cell, cellIndex) => (
                    <td key={cellIndex} className="px-3 py-2 text-sm text-gray-900 whitespace-nowrap">
                      {String(cell || '')}
                    </td>
                  ))
                ) : (
                  // Object-based rows: { column1: "value1", column2: "value2" }
                  headers.map((header, cellIndex) => (
                    <td key={cellIndex} className="px-3 py-2 text-sm text-gray-900 whitespace-nowrap">
                      {String(row[header] || '')}
                    </td>
                  ))
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Expand/Collapse Button */}
      {rows.length > maxRows && (
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
                View all {rows.length} rows
              </>
            )}
          </button>
        </div>
      )}

      {/* Table Info */}
      <div className="text-xs text-gray-500">
        {headers.length} columns × {rows.length} rows
      </div>
    </div>
  );
}

TableDisplay.propTypes = {
  data: PropTypes.shape({
    headers: PropTypes.arrayOf(PropTypes.string),
    rows: PropTypes.arrayOf(
      PropTypes.oneOfType([
        PropTypes.arrayOf(PropTypes.any),
        PropTypes.object
      ])
    )
  }),
  maxRows: PropTypes.number,
  onViewAll: PropTypes.func,
  className: PropTypes.string
};
