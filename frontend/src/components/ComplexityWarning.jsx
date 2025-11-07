import PropTypes from 'prop-types';

/**
 * ComplexityWarning - Alert banner for high complexity scores
 *
 * Displays complexity assessment results from Claude during bulk upload.
 * Helps users understand when templates need manual review.
 *
 * Design: Contextual warnings based on complexity tier
 * Pattern: Similar to GitHub PR complexity warnings, IDE code warnings
 */
export default function ComplexityWarning({
  complexityScore = 0,
  complexityTier = 'auto',
  confidence = 1.0,
  warnings = [],
  onProceed,
  onReview,
  className = ''
}) {
  // Don't show warning for low complexity (auto tier)
  if (complexityTier === 'auto' && complexityScore <= 50) {
    return null;
  }

  const tierConfig = {
    auto: {
      color: 'green',
      icon: '✓',
      title: 'Simple Document',
      description: 'Claude can handle this automatically with high confidence.'
    },
    assisted: {
      color: 'yellow',
      icon: '⚠️',
      title: 'Medium Complexity Detected',
      description: 'Claude suggests a schema, but manual review is recommended.'
    },
    manual: {
      color: 'red',
      icon: '⚠️',
      title: 'High Complexity Detected',
      description: 'This document requires manual schema definition.'
    }
  };

  const config = tierConfig[complexityTier] || tierConfig.assisted;

  const colorClasses = {
    green: {
      container: 'bg-green-50 border-green-200',
      icon: 'text-green-600',
      title: 'text-green-900',
      text: 'text-green-700',
      button: 'bg-green-600 hover:bg-green-700 text-white'
    },
    yellow: {
      container: 'bg-yellow-50 border-yellow-200',
      icon: 'text-yellow-600',
      title: 'text-yellow-900',
      text: 'text-yellow-700',
      button: 'bg-yellow-600 hover:bg-yellow-700 text-white'
    },
    red: {
      container: 'bg-red-50 border-red-200',
      icon: 'text-red-600',
      title: 'text-red-900',
      text: 'text-red-700',
      button: 'bg-red-600 hover:bg-red-700 text-white'
    }
  };

  const colors = colorClasses[config.color];

  return (
    <div className={`rounded-lg border p-4 ${colors.container} ${className}`}>
      <div className="flex items-start gap-3">
        {/* Icon */}
        <div className={`flex-shrink-0 text-xl ${colors.icon}`}>
          {config.icon}
        </div>

        <div className="flex-1">
          {/* Title */}
          <h4 className={`font-semibold mb-1 ${colors.title}`}>
            {config.title}
            {complexityScore > 0 && (
              <span className="ml-2 text-sm font-normal">
                (Score: {complexityScore})
              </span>
            )}
          </h4>

          {/* Description */}
          <p className={`text-sm mb-2 ${colors.text}`}>
            {config.description}
          </p>

          {/* Confidence Badge */}
          {confidence < 0.8 && (
            <div className="mb-3">
              <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${colors.container} border ${colors.text}`}>
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Low Confidence: {Math.round(confidence * 100)}%
              </span>
            </div>
          )}

          {/* Warnings List */}
          {warnings.length > 0 && (
            <div className={`mb-3 space-y-1 text-sm ${colors.text}`}>
              <div className="font-medium">Issues detected:</div>
              <ul className="list-disc list-inside space-y-0.5 ml-2">
                {warnings.map((warning, index) => (
                  <li key={index}>{warning}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Recommendations */}
          <div className={`text-sm ${colors.text}`}>
            <div className="font-medium mb-1">Recommendation:</div>
            {complexityTier === 'manual' ? (
              <p>Define the extraction schema manually for best results.</p>
            ) : complexityTier === 'assisted' ? (
              <p>Review the suggested schema carefully before proceeding.</p>
            ) : (
              <p>You can proceed with confidence.</p>
            )}
          </div>
        </div>
      </div>

      {/* Action Buttons */}
      {(onProceed || onReview) && (
        <div className="mt-4 flex items-center gap-3">
          {onReview && (
            <button
              onClick={onReview}
              className={`px-4 py-2 rounded font-medium text-sm transition-colors ${colors.button}`}
            >
              {complexityTier === 'manual' ? 'Define Schema' : 'Review Template'}
            </button>
          )}
          {onProceed && complexityTier !== 'manual' && (
            <button
              onClick={onProceed}
              className="px-4 py-2 rounded font-medium text-sm bg-white border border-gray-300 text-gray-700 hover:bg-gray-50 transition-colors"
            >
              Proceed Anyway
            </button>
          )}
        </div>
      )}
    </div>
  );
}

ComplexityWarning.propTypes = {
  complexityScore: PropTypes.number,
  complexityTier: PropTypes.oneOf(['auto', 'assisted', 'manual']),
  confidence: PropTypes.number,
  warnings: PropTypes.arrayOf(PropTypes.string),
  onProceed: PropTypes.func,
  onReview: PropTypes.func,
  className: PropTypes.string
};
