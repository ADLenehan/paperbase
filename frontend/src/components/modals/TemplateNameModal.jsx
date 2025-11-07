import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';

/**
 * Modern modal for template naming (replaces window.prompt)
 *
 * Features:
 * - AI-suggested template name pre-filled
 * - Input validation (min 3 chars, no duplicates)
 * - Keyboard shortcuts (Enter to confirm, Escape to cancel)
 * - Focus management for accessibility
 */
export default function TemplateNameModal({
  isOpen,
  onClose,
  onConfirm,
  suggestedName = '',
  existingTemplates = [],
  isProcessing = false
}) {
  const [templateName, setTemplateName] = useState(suggestedName);
  const [error, setError] = useState('');

  useEffect(() => {
    setTemplateName(suggestedName);
  }, [suggestedName]);

  useEffect(() => {
    if (isOpen) {
      // Focus input when modal opens
      const input = document.getElementById('template-name-input');
      if (input) {
        setTimeout(() => input.focus(), 100);
      }
    }
  }, [isOpen]);

  const validateName = (name) => {
    if (!name || name.trim().length < 3) {
      return 'Template name must be at least 3 characters';
    }

    const normalizedName = name.trim().toLowerCase();
    const isDuplicate = existingTemplates.some(
      template => template.name.toLowerCase() === normalizedName
    );

    if (isDuplicate) {
      return 'A template with this name already exists';
    }

    return '';
  };

  const handleSubmit = (e) => {
    e.preventDefault();

    const validationError = validateName(templateName);
    if (validationError) {
      setError(validationError);
      return;
    }

    onConfirm(templateName.trim());
    handleClose();
  };

  const handleClose = () => {
    setTemplateName('');
    setError('');
    onClose();
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') {
      handleClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
      onClick={handleClose}
    >
      <div
        className="bg-white rounded-lg shadow-xl p-6 w-full max-w-md"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={handleKeyDown}
      >
        <h2 className="text-xl font-semibold text-gray-900 mb-4">
          Create New Template
        </h2>

        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label
              htmlFor="template-name-input"
              className="block text-sm font-medium text-gray-700 mb-2"
            >
              Template Name
            </label>
            <input
              id="template-name-input"
              type="text"
              value={templateName}
              onChange={(e) => {
                setTemplateName(e.target.value);
                setError(''); // Clear error on change
              }}
              className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 ${
                error
                  ? 'border-red-300 focus:ring-red-500'
                  : 'border-gray-300 focus:ring-blue-500'
              }`}
              placeholder="e.g., Technical Specifications"
              autoComplete="off"
              disabled={isProcessing}
            />
            {error && (
              <p className="mt-2 text-sm text-red-600">
                {error}
              </p>
            )}
            <p className="mt-2 text-sm text-gray-500">
              This template will be used for similar documents in the future.
            </p>
          </div>

          <div className="flex justify-end gap-3">
            <button
              type="button"
              onClick={handleClose}
              disabled={isProcessing}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isProcessing}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {isProcessing ? (
                <>
                  <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  <span>Generating fields...</span>
                </>
              ) : (
                'Create Template'
              )}
            </button>
          </div>
        </form>

        <div className="mt-4 pt-4 border-t border-gray-200">
          <p className="text-xs text-gray-500">
            <strong>Tip:</strong> Use descriptive names like &quot;Purchase Orders&quot; or &quot;Employee Timesheets&quot; for better organization.
          </p>
        </div>
      </div>
    </div>
  );
}

TemplateNameModal.propTypes = {
  isOpen: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  onConfirm: PropTypes.func.isRequired,
  suggestedName: PropTypes.string,
  existingTemplates: PropTypes.arrayOf(PropTypes.shape({
    id: PropTypes.number,
    name: PropTypes.string
  })),
  isProcessing: PropTypes.bool
};
