import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function FolderView() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const currentPath = searchParams.get('path') || '';

  const [folderData, setFolderData] = useState(null);
  const [breadcrumbs, setBreadcrumbs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState(null);
  const [stats, setStats] = useState(null);

  useEffect(() => {
    fetchFolderData();
    fetchBreadcrumbs();
    fetchStats();
  }, [currentPath]);

  const fetchFolderData = async () => {
    try {
      setLoading(true);
      const response = await fetch(
        `${API_URL}/api/folders/browse?path=${encodeURIComponent(currentPath)}`
      );
      const data = await response.json();
      setFolderData(data);
    } catch (err) {
      console.error('Failed to fetch folder data:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchBreadcrumbs = async () => {
    try {
      const response = await fetch(
        `${API_URL}/api/folders/breadcrumbs?path=${encodeURIComponent(currentPath)}`
      );
      const data = await response.json();
      setBreadcrumbs(data.breadcrumbs || []);
    } catch (err) {
      console.error('Failed to fetch breadcrumbs:', err);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await fetch(
        `${API_URL}/api/folders/stats?path=${encodeURIComponent(currentPath)}`
      );
      const data = await response.json();
      setStats(data);
    } catch (err) {
      console.error('Failed to fetch stats:', err);
    }
  };

  const handleNavigateToFolder = (path) => {
    setSearchParams({ path });
    setSearchResults(null);
    setSearchQuery('');
  };

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!searchQuery.trim()) {
      setSearchResults(null);
      return;
    }

    try {
      const response = await fetch(
        `${API_URL}/api/folders/search?path=${encodeURIComponent(currentPath)}&q=${encodeURIComponent(searchQuery)}`
      );
      const data = await response.json();
      setSearchResults(data);
    } catch (err) {
      console.error('Search failed:', err);
    }
  };

  const handleViewExtraction = (extractionId) => {
    navigate(`/extractions/${extractionId}`);
  };

  const getStatusBadge = (status) => {
    const styles = {
      pending: 'bg-gray-100 text-gray-800',
      processing: 'bg-blue-100 text-blue-800',
      completed: 'bg-green-100 text-green-800',
      verified: 'bg-green-100 text-green-800',
      error: 'bg-red-100 text-red-800'
    };

    return (
      <span className={`px-2 py-1 text-xs font-medium rounded-full ${styles[status] || styles.pending}`}>
        {status.toUpperCase()}
      </span>
    );
  };

  const getConfidenceBadge = (confidence) => {
    if (!confidence) return null;

    const percentage = Math.round(confidence * 100);
    let color;

    if (percentage >= 80) color = 'bg-green-500';
    else if (percentage >= 60) color = 'bg-yellow-500';
    else color = 'bg-red-500';

    return (
      <div className="flex items-center gap-1">
        <div className={`w-2 h-2 rounded-full ${color}`}></div>
        <span className="text-xs text-gray-600">{percentage}%</span>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Loading...</div>
      </div>
    );
  }

  const displayData = searchResults || folderData;

  return (
    <div className="max-w-7xl mx-auto p-6">
      {/* Header with Search */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold mb-2">Documents</h1>
        <p className="text-gray-600">Browse and search your documents by folder</p>
      </div>

      {/* Search Bar */}
      <div className="bg-white rounded-lg border p-4 mb-6">
        <form onSubmit={handleSearch} className="flex items-center gap-3">
          <div className="flex-1">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={currentPath ? `Search in ${currentPath}...` : "Search all documents..."}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
          <button
            type="submit"
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium"
          >
            🔍 Search
          </button>
          {searchResults && (
            <button
              type="button"
              onClick={() => {
                setSearchResults(null);
                setSearchQuery('');
              }}
              className="px-4 py-2 text-gray-600 hover:text-gray-800"
            >
              Clear
            </button>
          )}
        </form>
      </div>

      {/* Search Results Info */}
      {searchResults && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
          <p className="text-blue-800">
            Found <span className="font-bold">{searchResults.count}</span> results for "{searchQuery}"
            {currentPath && ` in ${currentPath}`}
          </p>
        </div>
      )}

      {/* Stats Cards */}
      {!searchResults && stats && (
        <div className="grid grid-cols-4 gap-4 mb-6">
          <StatCard label="Total Extractions" value={stats.total_extractions} />
          <StatCard label="Unique Files" value={stats.unique_files} />
          <StatCard
            label="Completed"
            value={stats.by_status?.completed || 0}
            color="green"
          />
          <StatCard
            label="Processing"
            value={stats.by_status?.processing || 0}
            color="blue"
          />
        </div>
      )}

      {/* Breadcrumbs */}
      {!searchResults && (
        <div className="flex items-center gap-2 text-sm mb-4">
          {breadcrumbs.map((crumb, index) => (
            <div key={index} className="flex items-center gap-2">
              {index > 0 && <span className="text-gray-400">/</span>}
              <button
                onClick={() => handleNavigateToFolder(crumb.path)}
                className={`hover:text-blue-600 ${
                  index === breadcrumbs.length - 1
                    ? 'font-semibold text-gray-900'
                    : 'text-gray-600'
                }`}
              >
                {crumb.name === 'Home' ? '🏠 Home' : crumb.name}
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Folders */}
      {!searchResults && displayData?.folders && displayData.folders.length > 0 && (
        <div className="mb-6">
          <h2 className="text-lg font-semibold mb-3">Folders</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {displayData.folders.map((folder) => (
              <button
                key={folder.path}
                onClick={() => handleNavigateToFolder(folder.path)}
                className="flex items-center gap-3 p-4 bg-white border border-gray-200 rounded-lg hover:border-blue-400 hover:shadow-sm transition-all text-left"
              >
                <div className="text-3xl">📁</div>
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-gray-900 truncate">{folder.name}</div>
                  <div className="text-xs text-gray-500">{folder.count} items</div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Files */}
      <div className="bg-white rounded-lg border overflow-hidden">
        <div className="px-6 py-4 border-b bg-gray-50">
          <h2 className="text-lg font-semibold">
            {searchResults ? 'Search Results' : 'Files'}
          </h2>
        </div>

        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Filename</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Template</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Confidence</th>
              {searchResults && (
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Path</th>
              )}
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {(!displayData?.files || displayData.files.length === 0) && !searchResults?.results?.length ? (
              <tr>
                <td colSpan={searchResults ? "6" : "5"} className="px-6 py-12 text-center text-gray-500">
                  {searchResults ? 'No results found' : 'No files in this folder'}
                </td>
              </tr>
            ) : (
              (searchResults?.results || displayData?.files || []).map((file) => (
                <tr key={file.id || file.extraction_id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 text-sm">
                    <div className="flex items-center gap-2">
                      <span className="text-xl">📄</span>
                      <span className="font-medium text-gray-900">{file.filename}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-700">
                    {file.template}
                  </td>
                  <td className="px-6 py-4 text-sm">
                    {getStatusBadge(file.status)}
                  </td>
                  <td className="px-6 py-4 text-sm">
                    {getConfidenceBadge(file.confidence)}
                  </td>
                  {searchResults && (
                    <td className="px-6 py-4 text-sm text-gray-600">
                      <div className="max-w-xs truncate" title={file.path}>
                        {file.path}
                      </div>
                    </td>
                  )}
                  <td className="px-6 py-4 text-sm">
                    <button
                      onClick={() => handleViewExtraction(file.extraction_id)}
                      className="text-blue-600 hover:text-blue-800 font-medium"
                    >
                      View
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Template Breakdown */}
      {!searchResults && stats?.by_template && Object.keys(stats.by_template).length > 0 && (
        <div className="mt-6 bg-white rounded-lg border p-6">
          <h3 className="text-lg font-semibold mb-4">Documents by Template</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {Object.entries(stats.by_template).map(([template, count]) => (
              <div key={template} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <span className="text-sm text-gray-700">{template}</span>
                <span className="text-lg font-bold text-gray-900">{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, color = 'blue' }) {
  const colors = {
    blue: 'border-blue-200 bg-blue-50',
    green: 'border-green-200 bg-green-50',
    yellow: 'border-yellow-200 bg-yellow-50',
    gray: 'border-gray-200 bg-gray-50'
  };

  return (
    <div className={`p-4 rounded-lg border ${colors[color]}`}>
      <div className="text-2xl font-bold text-gray-900">{value}</div>
      <div className="text-sm text-gray-600">{label}</div>
    </div>
  );
}
