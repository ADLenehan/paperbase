import { useState, useEffect } from 'react';
import { MCPStatusCard } from '../components/MCPIndicator';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function Settings() {
  const [settings, setSettings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activeCategory, setActiveCategory] = useState('all');
  const [categories, setCategories] = useState([]);
  const [orgName, setOrgName] = useState('');
  const [userEmail, setUserEmail] = useState('');
  const [message, setMessage] = useState(null);

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/settings/`);
      if (!response.ok) throw new Error('Failed to fetch settings');

      const data = await response.json();
      setSettings(data.settings);
      setOrgName(data.org_name);
      setUserEmail(data.user_email);

      // Extract unique categories
      const uniqueCategories = [...new Set(data.settings.map(s => s.category).filter(Boolean))];
      setCategories(['all', ...uniqueCategories.sort()]);
    } catch (error) {
      console.error('Error fetching settings:', error);
      setMessage({ type: 'error', text: 'Failed to load settings' });
    } finally {
      setLoading(false);
    }
  };

  const handleSettingChange = (key, newValue) => {
    setSettings(prev => prev.map(s =>
      s.key === key ? { ...s, value: newValue } : s
    ));
  };

  const handleSave = async (settingKey) => {
    setSaving(true);
    const setting = settings.find(s => s.key === settingKey);

    try {
      const response = await fetch(`${API_URL}/api/settings/${settingKey}?level=organization`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          key: setting.key,
          value: setting.value,
          value_type: setting.value_type,
          description: setting.description
        })
      });

      if (!response.ok) throw new Error('Failed to save setting');

      setMessage({ type: 'success', text: `${setting.key} saved successfully` });
      setTimeout(() => setMessage(null), 3000);
    } catch (error) {
      console.error('Error saving setting:', error);
      setMessage({ type: 'error', text: 'Failed to save setting' });
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async (settingKey) => {
    if (!confirm('Reset this setting to the default value?')) return;

    setSaving(true);
    try {
      const response = await fetch(`${API_URL}/api/settings/${settingKey}?level=organization`, {
        method: 'DELETE'
      });

      if (!response.ok) throw new Error('Failed to reset setting');

      // Refresh settings to show new default
      await fetchSettings();
      setMessage({ type: 'success', text: 'Setting reset to default' });
      setTimeout(() => setMessage(null), 3000);
    } catch (error) {
      console.error('Error resetting setting:', error);
      setMessage({ type: 'error', text: 'Failed to reset setting' });
    } finally {
      setSaving(false);
    }
  };

  const renderSettingInput = (setting) => {
    switch (setting.value_type) {
      case 'float':
      case 'int':
        const min = setting.min !== undefined ? setting.min : 0;
        const max = setting.max !== undefined ? setting.max : 100;
        const step = setting.value_type === 'float' ? 0.01 : 1;

        // Check if this is a threshold setting (0-1 range) that should display as percentage
        const isThreshold = setting.key.includes('threshold') || setting.key.includes('confidence');
        const isPercentage = isThreshold && max <= 1;

        // Display value (convert to percentage if needed)
        const displayValue = isPercentage ? Math.round(setting.value * 100) : setting.value;
        const displayMin = isPercentage ? Math.round(min * 100) : min;
        const displayMax = isPercentage ? Math.round(max * 100) : max;
        const displayStep = isPercentage ? 1 : step;

        // Convert display value back to actual value (0-1) for storage
        const handleChange = (displayVal) => {
          const actualValue = isPercentage ? displayVal / 100 : displayVal;
          handleSettingChange(setting.key, actualValue);
        };

        return (
          <div className="space-y-2">
            <div className="flex items-center gap-4">
              <input
                type="range"
                min={displayMin}
                max={displayMax}
                step={displayStep}
                value={displayValue}
                onChange={(e) => handleChange(parseFloat(e.target.value))}
                className="flex-1 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-periwinkle-600"
                style={{
                  background: `linear-gradient(to right, #6366f1 0%, #6366f1 ${((displayValue - displayMin) / (displayMax - displayMin)) * 100}%, #e5e7eb ${((displayValue - displayMin) / (displayMax - displayMin)) * 100}%, #e5e7eb 100%)`
                }}
              />
              <input
                type="number"
                min={displayMin}
                max={displayMax}
                step={displayStep}
                value={displayValue}
                onChange={(e) => handleChange(parseFloat(e.target.value))}
                className="w-20 px-3 py-2 border border-gray-300 rounded-lg text-center focus:ring-2 focus:ring-periwinkle-500 focus:border-transparent"
              />
            </div>
            <div className="flex justify-between text-xs text-gray-500">
              <span>{displayMin}{isPercentage ? '%' : ''}</span>
              <span>{displayMax}{isPercentage ? '%' : ''}</span>
            </div>
          </div>
        );

      case 'bool':
        return (
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={setting.value}
              onChange={(e) => handleSettingChange(setting.key, e.target.checked)}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
            <span className="ml-3 text-sm text-gray-700">
              {setting.value ? 'Enabled' : 'Disabled'}
            </span>
          </label>
        );

      case 'string':
        return (
          <input
            type="text"
            value={setting.value}
            onChange={(e) => handleSettingChange(setting.key, e.target.value)}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        );

      default:
        return (
          <textarea
            value={JSON.stringify(setting.value, null, 2)}
            onChange={(e) => {
              try {
                handleSettingChange(setting.key, JSON.parse(e.target.value));
              } catch (err) {
                // Invalid JSON, ignore
              }
            }}
            rows={4}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg font-mono text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        );
    }
  };

  const getSourceBadge = (source) => {
    const badges = {
      user: { color: 'bg-purple-100 text-purple-700', label: 'User Override' },
      organization: { color: 'bg-blue-100 text-blue-700', label: 'Organization' },
      system: { color: 'bg-green-100 text-green-700', label: 'System' },
      default: { color: 'bg-gray-100 text-gray-700', label: 'Default' }
    };

    const badge = badges[source] || badges.default;
    return (
      <span className={`text-xs px-2 py-1 rounded-full ${badge.color}`}>
        {badge.label}
      </span>
    );
  };

  const filteredSettings = activeCategory === 'all'
    ? settings
    : settings.filter(s => s.category === activeCategory);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mb-2"></div>
          <p className="text-sm text-gray-600">Loading settings...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Settings</h1>
        <p className="text-gray-600">
          Configure system behavior and thresholds for {orgName}
        </p>
        <p className="text-sm text-gray-500 mt-1">Logged in as: {userEmail}</p>
      </div>

      {/* Message */}
      {message && (
        <div className={`mb-6 p-4 rounded-lg ${
          message.type === 'success' ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'
        }`}>
          {message.text}
        </div>
      )}

      {/* Category Tabs */}
      <div className="mb-6 border-b border-gray-200">
        <div className="flex gap-4 overflow-x-auto">
          {categories.map(category => (
            <button
              key={category}
              onClick={() => setActiveCategory(category)}
              className={`px-4 py-2 font-medium text-sm whitespace-nowrap border-b-2 transition-colors ${
                activeCategory === category
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-600 hover:text-gray-900'
              }`}
            >
              {category === 'all' ? 'All Settings' : category.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')}
            </button>
          ))}
        </div>
      </div>

      {/* MCP Status - Shows Claude connection status */}
      <div className="mb-6">
        <MCPStatusCard />
      </div>

      {/* Settings List */}
      <div className="space-y-6">
        {filteredSettings.map(setting => (
          <div key={setting.key} className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <div className="flex items-start justify-between mb-4">
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-2">
                  <h3 className="text-lg font-semibold text-gray-900">
                    {setting.key.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')}
                  </h3>
                  {getSourceBadge(setting.source)}
                </div>
                {setting.description && (
                  <p className="text-sm text-gray-600">{setting.description}</p>
                )}
              </div>
            </div>

            <div className="mb-4">
              {renderSettingInput(setting)}
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => handleSave(setting.key)}
                disabled={saving}
                className="bg-blue-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {saving ? 'Saving...' : 'Save'}
              </button>

              {setting.source !== 'default' && (
                <button
                  onClick={() => handleReset(setting.key)}
                  disabled={saving}
                  className="bg-gray-200 text-gray-700 px-4 py-2 rounded-lg font-medium hover:bg-gray-300 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Reset to Default
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      {filteredSettings.length === 0 && (
        <div className="text-center py-12 bg-white rounded-lg shadow-sm border border-gray-200">
          <p className="text-gray-600">No settings in this category</p>
        </div>
      )}

      {/* Info Box */}
      <div className="mt-8 bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h4 className="font-semibold text-blue-900 mb-2">About Settings Hierarchy</h4>
        <div className="text-sm text-blue-800 space-y-1">
          <p><strong>User Override:</strong> Applies only to your user account</p>
          <p><strong>Organization:</strong> Applies to all users in your organization</p>
          <p><strong>System:</strong> System-wide default setting</p>
          <p><strong>Default:</strong> Hardcoded application default</p>
        </div>
        <p className="text-sm text-blue-700 mt-3">
          Settings at higher levels override those at lower levels. Reset a setting to use the fallback value.
        </p>
      </div>
    </div>
  );
}
