import { useState } from 'react';
import PropTypes from 'prop-types';

/**
 * TableEditor - Interactive table editor with inline editing
 *
 * Allows users to edit table data with inline cell editing.
 * Supports add/remove rows, edit cells, view column headers.
 *
 * Design: Spreadsheet-like interface
 * Pattern: Similar to Excel/Google Sheets inline editing
 *
 * Note: Column editing intentionally not supported in MVP (too complex)
 */
export default function TableEditor({
  value = {},
  onChange,
  maxColumns = 10,
  allowAddRows = true,
  disabled = false
}) {
  const { headers = [], rows = [] } = value;
  const [editingCell, setEditingCell] = useState(null); // { row: number, col: number }

  // Initialize empty table if needed
  const hasData = headers.length > 0 && rows.length > 0;

  const handleCellChange = (rowIndex, colIndex, newValue) => {
    const updatedRows = [...rows];
    if (Array.isArray(updatedRows[rowIndex])) {
      // Array-based row
      updatedRows[rowIndex][colIndex] = newValue;
    } else {
      // Object-based row
      const header = headers[colIndex];
      updatedRows[rowIndex] = { ...updatedRows[rowIndex], [header]: newValue };
    }

    onChange({ headers, rows: updatedRows });
  };

  const handleAddRow = () => {
    const newRow = Array.isArray(rows[0])
      ? new Array(headers.length).fill('')
      : Object.fromEntries(headers.map(h => [h, '']));

    onChange({ headers, rows: [...rows, newRow] });
  };

  const handleRemoveRow = (rowIndex) => {
    onChange({ headers, rows: rows.filter((_, i) => i !== rowIndex) });
  };

  const getCellValue = (row, colIndex) => {
    if (Array.isArray(row)) {
      return row[colIndex] || '';
    } else {
      return row[headers[colIndex]] || '';
    }
  };

  if (!hasData) {
    return (
      <div className="text-center py-8 text-gray-400 text-sm border border-gray-200 rounded-lg bg-gray-50">
        No table data available
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="overflow-x-auto border border-gray-200 rounded-lg bg-white">
        <table className="min-w-full divide-y divide-gray-200">
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
              {!disabled && <th className="px-3 py-2 w-16"></th>}
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-100">
            {rows.map((row, rowIndex) => (
              <tr key={rowIndex} className="hover:bg-gray-50 transition-colors group">
                {headers.map((header, colIndex) => {
                  const isEditing = editingCell?.row === rowIndex && editingCell?.col === colIndex;
                  const cellValue = getCellValue(row, colIndex);

                  return (
                    <td
                      key={colIndex}
                      className="px-3 py-2 text-sm text-gray-900"
                      onClick={() => !disabled && setEditingCell({ row: rowIndex, col: colIndex })}
                    >
                      {isEditing && !disabled ? (
                        <input
                          type="text"
                          value={cellValue}
                          onChange={(e) => handleCellChange(rowIndex, colIndex, e.target.value)}
                          onBlur={() => setEditingCell(null)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') setEditingCell(null);
                            if (e.key === 'Escape') setEditingCell(null);
                          }}
                          autoFocus
                          className="w-full px-2 py-1 border border-blue-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                      ) : (
                        <div className="cursor-text hover:bg-gray-100 px-2 py-1 rounded min-h-[28px]">
                          {cellValue || <span className="text-gray-400 text-xs italic">empty</span>}
                        </div>
                      )}
                    </td>
                  );
                })}

                {/* Row Actions */}
                {!disabled && (
                  <td className="px-3 py-2 text-right">
                    <button
                      onClick={() => handleRemoveRow(rowIndex)}
                      className="opacity-0 group-hover:opacity-100 text-red-500 hover:text-red-700 transition-all"
                      title="Remove row"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Add Row Button */}
      {allowAddRows && !disabled && (
        <button
          onClick={handleAddRow}
          className="w-full py-2 text-sm font-medium text-gray-600 border-2 border-dashed border-gray-300 rounded-lg hover:border-blue-400 hover:text-blue-600 transition-colors"
        >
          + Add Row
        </button>
      )}

      {/* Helper Text */}
      {!disabled && (
        <div className="text-xs text-gray-500">
          Click any cell to edit • Press <kbd className="px-1 py-0.5 bg-gray-100 border border-gray-300 rounded text-[10px] font-mono">Enter</kbd> or <kbd className="px-1 py-0.5 bg-gray-100 border border-gray-300 rounded text-[10px] font-mono">Esc</kbd> to finish
        </div>
      )}

      {/* Table Info */}
      <div className="text-xs text-gray-500">
        {headers.length} columns × {rows.length} rows
      </div>
    </div>
  );
}

TableEditor.propTypes = {
  value: PropTypes.shape({
    headers: PropTypes.arrayOf(PropTypes.string),
    rows: PropTypes.arrayOf(
      PropTypes.oneOfType([
        PropTypes.arrayOf(PropTypes.any),
        PropTypes.object
      ])
    )
  }),
  onChange: PropTypes.func.isRequired,
  maxColumns: PropTypes.number,
  allowAddRows: PropTypes.bool,
  disabled: PropTypes.bool
};
