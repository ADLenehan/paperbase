import { useState, useRef, useEffect } from 'react';
import PropTypes from 'prop-types';

/**
 * ArrayEditor - Interactive array editor with chip-based interface
 *
 * Allows users to add/remove items from simple arrays.
 * Visual feedback with chips, inline editing.
 *
 * Design: Chip-based like Gmail labels
 * Pattern: Add via input + Enter, remove via click
 */
export default function ArrayEditor({ value = [], onChange, placeholder = 'Add item...', disabled = false }) {
  const [inputValue, setInputValue] = useState('');
  const [focusedIndex, setFocusedIndex] = useState(-1);
  const inputRef = useRef(null);

  const handleAddItem = () => {
    const trimmed = inputValue.trim();
    if (!trimmed) return;

    // Prevent duplicates
    if (value.includes(trimmed)) {
      setInputValue('');
      inputRef.current?.focus();
      return;
    }

    onChange([...value, trimmed]);
    setInputValue('');
    inputRef.current?.focus();
  };

  const handleRemoveItem = (index) => {
    onChange(value.filter((_, i) => i !== index));
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleAddItem();
    } else if (e.key === 'Backspace' && !inputValue && value.length > 0) {
      // Remove last item when backspace on empty input
      handleRemoveItem(value.length - 1);
    }
  };

  return (
    <div className={`border border-gray-200 rounded-lg p-2 bg-white ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}>
      {/* Existing Items */}
      {value.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-2">
          {value.map((item, index) => (
            <span
              key={index}
              className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200 hover:border-blue-300 transition-colors"
              onMouseEnter={() => setFocusedIndex(index)}
              onMouseLeave={() => setFocusedIndex(-1)}
            >
              <span>{String(item)}</span>
              {!disabled && (
                <button
                  onClick={() => handleRemoveItem(index)}
                  className="text-blue-500 hover:text-blue-700 hover:bg-blue-100 rounded-full p-0.5 transition-colors"
                  title="Remove item"
                  aria-label={`Remove ${item}`}
                >
                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              )}
            </span>
          ))}
        </div>
      )}

      {/* Add New Item Input */}
      {!disabled && (
        <div className="flex items-center gap-2">
          <input
            ref={inputRef}
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            className="flex-1 px-2 py-1 text-sm border-0 focus:outline-none focus:ring-0"
            disabled={disabled}
          />
          <button
            onClick={handleAddItem}
            disabled={!inputValue.trim()}
            className="px-3 py-1 text-xs font-medium text-blue-600 hover:text-blue-700 hover:bg-blue-50 rounded transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            title="Add item (or press Enter)"
          >
            + Add
          </button>
        </div>
      )}

      {/* Helper Text */}
      {!disabled && (
        <div className="mt-2 text-xs text-gray-500">
          Press <kbd className="px-1 py-0.5 bg-gray-100 border border-gray-300 rounded text-[10px] font-mono">Enter</kbd> to add
          {value.length > 0 && (
            <> • Click × to remove</>
          )}
        </div>
      )}
    </div>
  );
}

ArrayEditor.propTypes = {
  value: PropTypes.arrayOf(
    PropTypes.oneOfType([PropTypes.string, PropTypes.number])
  ),
  onChange: PropTypes.func.isRequired,
  placeholder: PropTypes.string,
  disabled: PropTypes.bool
};
