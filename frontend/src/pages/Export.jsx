import { useState, useEffect } from 'react';
import apiClient from '../api/client';
import ExportModal from '../components/ExportModal';

/**
 * Export Page - Browse templates and export data
 */
export default function Export() {
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [showExportModal, setShowExportModal] = useState(false);
  const [categoryFilter, setCategoryFilter] = useState('all');

  useEffect(() => {
    fetchTemplates();
  }, []);

  const fetchTemplates = async () => {
    try {
      const response = await apiClient.get('/api/export/templates');
      setTemplates(response.data.templates || []);
    } catch (err) {
      console.error('Failed to fetch templates:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleExport = (template) => {
    setSelectedTemplate(template);
    setShowExportModal(true);
  };

  const categories = [...new Set(templates.map(t => t.category))];
  const filteredTemplates = categoryFilter === 'all'
    ? templates
    : templates.filter(t => t.category === categoryFilter);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading templates...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Export Data</h1>
        <p className="text-gray-600">
          Export extracted document data in CSV, Excel, or JSON format
        </p>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="text-2xl font-bold text-gray-900">
            {templates.length}
          </div>
          <div className="text-sm text-gray-600">Templates Available</div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="text-2xl font-bold text-gray-900">
            {templates.reduce((sum, t) => sum + (t.document_count || 0), 0)}
          </div>
          <div className="text-sm text-gray-600">Total Documents</div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="text-2xl font-bold text-gray-900">
            {categories.length}
          </div>
          <div className="text-sm text-gray-600">Categories</div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="text-2xl font-bold text-blue-600">3</div>
          <div className="text-sm text-gray-600">Export Formats</div>
        </div>
      </div>

      {/* Category Filter */}
      <div className="mb-6">
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setCategoryFilter('all')}
            className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
              categoryFilter === 'all'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            All Templates
          </button>
          {categories.map(category => (
            <button
              key={category}
              onClick={() => setCategoryFilter(category)}
              className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
                categoryFilter === category
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              {category.charAt(0).toUpperCase() + category.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Templates Grid */}
      {filteredTemplates.length === 0 ? (
        <div className="text-center py-12 bg-white rounded-lg border border-gray-200">
          <div className="text-6xl mb-4">📄</div>
          <h3 className="text-lg font-semibold text-gray-900 mb-2">No Templates Found</h3>
          <p className="text-gray-600 mb-6">
            {categoryFilter === 'all'
              ? 'No templates have been created yet.'
              : `No templates in the "${categoryFilter}" category.`}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredTemplates.map(template => (
            <div
              key={template.id}
              className="bg-white rounded-lg border border-gray-200 p-6 hover:shadow-lg transition-shadow"
            >
              {/* Template Header */}
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="text-3xl">{template.icon || '📄'}</div>
                  <div>
                    <h3 className="font-semibold text-gray-900">{template.name}</h3>
                    <span className="inline-block px-2 py-1 text-xs font-medium bg-gray-100 text-gray-700 rounded-full mt-1">
                      {template.category}
                    </span>
                  </div>
                </div>
              </div>

              {/* Description */}
              {template.description && (
                <p className="text-sm text-gray-600 mb-4 line-clamp-2">
                  {template.description}
                </p>
              )}

              {/* Stats */}
              <div className="grid grid-cols-2 gap-4 mb-4 pb-4 border-b border-gray-200">
                <div>
                  <div className="text-2xl font-bold text-gray-900">
                    {template.document_count || 0}
                  </div>
                  <div className="text-xs text-gray-600">Documents</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-gray-900">
                    {template.field_count || 0}
                  </div>
                  <div className="text-xs text-gray-600">Fields</div>
                </div>
              </div>

              {/* Export Button */}
              {(template.document_count || 0) > 0 ? (
                <button
                  onClick={() => handleExport(template)}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  Export Data
                </button>
              ) : (
                <div className="w-full text-center py-2 text-sm text-gray-400 bg-gray-50 rounded-md">
                  No documents to export
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Export Formats Info */}
      <div className="mt-12 bg-blue-50 border border-blue-200 rounded-lg p-6">
        <h2 className="text-lg font-semibold text-blue-900 mb-4">Available Export Formats</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="flex items-start gap-3">
            <div className="text-2xl">📊</div>
            <div>
              <h3 className="font-medium text-blue-900">Excel (.xlsx)</h3>
              <p className="text-sm text-blue-700">
                Formatted spreadsheet with auto-sized columns and bold headers. Best for analysis in Excel or Google Sheets.
              </p>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <div className="text-2xl">📄</div>
            <div>
              <h3 className="font-medium text-blue-900">CSV (.csv)</h3>
              <p className="text-sm text-blue-700">
                Plain text format compatible with all spreadsheet tools. Smaller file size, no formatting.
              </p>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <div className="text-2xl">🔧</div>
            <div>
              <h3 className="font-medium text-blue-900">JSON (.json)</h3>
              <p className="text-sm text-blue-700">
                Structured data format ideal for APIs, data pipelines, and programmatic access.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Export Modal */}
      {selectedTemplate && (
        <ExportModal
          isOpen={showExportModal}
          onClose={() => {
            setShowExportModal(false);
            setSelectedTemplate(null);
          }}
          templateId={selectedTemplate.id}
        />
      )}
    </div>
  );
}
