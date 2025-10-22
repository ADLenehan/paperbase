import { useState } from 'react';
import PropTypes from 'prop-types';
import ExportModal from './ExportModal';

/**
 * ExportButton - Simple button that opens ExportModal
 *
 * Usage:
 * <ExportButton templateId={5} />
 * <ExportButton documentIds={[1,2,3]} />
 */
export default function ExportButton({ templateId = null, documentIds = null, variant = 'primary', label = 'Export' }) {
  const [showModal, setShowModal] = useState(false);

  const variantStyles = {
    primary: 'bg-blue-600 hover:bg-blue-700 text-white',
    secondary: 'bg-white hover:bg-gray-50 text-gray-700 border border-gray-300',
    ghost: 'bg-transparent hover:bg-gray-100 text-gray-700',
  };

  return (
    <>
      <button
        onClick={() => setShowModal(true)}
        className={`inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${variantStyles[variant]}`}
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
        </svg>
        {label}
      </button>

      <ExportModal
        isOpen={showModal}
        onClose={() => setShowModal(false)}
        templateId={templateId}
        documentIds={documentIds}
      />
    </>
  );
}

ExportButton.propTypes = {
  templateId: PropTypes.number,
  documentIds: PropTypes.arrayOf(PropTypes.number),
  variant: PropTypes.oneOf(['primary', 'secondary', 'ghost']),
  label: PropTypes.string,
};
