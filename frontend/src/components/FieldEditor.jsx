import { useState } from 'react';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';

function SortableField({ field, onUpdate, onRemove, depth = 0 }) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: field.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const [expanded, setExpanded] = useState(false);

  const addNestedField = () => {
    const newField = {
      id: `field-${Date.now()}`,
      name: `item_${(field.items?.length || field.properties?.length || 0) + 1}`,
      type: 'text',
      required: false,
      description: '',
    };

    if (field.type === 'array') {
      onUpdate(field.id, {
        ...field,
        items: [...(field.items || []), newField]
      });
    } else if (field.type === 'object') {
      onUpdate(field.id, {
        ...field,
        properties: [...(field.properties || []), newField]
      });
    }
    setExpanded(true);
  };

  const updateNestedField = (nestedId, updatedField) => {
    if (field.type === 'array') {
      const updatedItems = (field.items || []).map(item =>
        item.id === nestedId ? updatedField : item
      );
      onUpdate(field.id, { ...field, items: updatedItems });
    } else if (field.type === 'object') {
      const updatedProps = (field.properties || []).map(prop =>
        prop.id === nestedId ? updatedField : prop
      );
      onUpdate(field.id, { ...field, properties: updatedProps });
    }
  };

  const removeNestedField = (nestedId) => {
    if (field.type === 'array') {
      onUpdate(field.id, {
        ...field,
        items: (field.items || []).filter(item => item.id !== nestedId)
      });
    } else if (field.type === 'object') {
      onUpdate(field.id, {
        ...field,
        properties: (field.properties || []).filter(prop => prop.id !== nestedId)
      });
    }
  };

  const isNested = field.type === 'array' || field.type === 'object';
  const nestedFields = field.type === 'array' ? (field.items || []) : (field.properties || []);
  const hasNestedFields = nestedFields.length > 0;

  return (
    <div
      className={`${depth > 0 ? 'ml-8' : ''}`}
    >
      {/* Main Field Row */}
      <div
        ref={setNodeRef}
        style={style}
        {...attributes}
        className={`
          flex items-center gap-2 px-3 py-2.5 rounded-lg border
          ${isDragging ? 'border-periwinkle-400 shadow-lg bg-periwinkle-50' : 'border-gray-200 bg-white hover:border-gray-300'}
          transition-all
        `}
      >
        {/* Expand/Collapse for nested types */}
        {isNested && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              setExpanded(!expanded);
            }}
            className="flex-shrink-0 w-5 h-5 flex items-center justify-center text-gray-500 hover:text-gray-700 transition-colors"
          >
            {expanded ? '▼' : '▶'}
          </button>
        )}

        {/* Drag Handle Indicator */}
        <div
          {...listeners}
          className="flex-shrink-0 text-gray-400 cursor-grab active:cursor-grabbing"
          title="Drag to reorder"
        >
          <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
            <path d="M7 3a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3zm6 0a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3zM7 8.5a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3zm6 0a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3zM7 14a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3zm6 0a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3z" />
          </svg>
        </div>

        {/* Field Name */}
        <input
          type="text"
          value={field.name}
          onChange={(e) => onUpdate(field.id, { ...field, name: e.target.value })}
          onClick={(e) => e.stopPropagation()}
          className="flex-shrink-0 w-40 h-10 px-3 text-sm font-mono border border-gray-200 rounded focus:outline-none focus:ring-1 focus:ring-periwinkle-500 focus:border-transparent bg-white"
          placeholder="field_name"
        />

        {/* Type Dropdown */}
        <select
          value={field.type}
          onChange={(e) => onUpdate(field.id, { ...field, type: e.target.value })}
          onClick={(e) => e.stopPropagation()}
          className="flex-shrink-0 h-10 px-3 text-xs border border-gray-200 rounded focus:outline-none focus:ring-1 focus:ring-periwinkle-500 bg-white uppercase font-medium text-gray-700"
        >
          <option value="text">STR</option>
          <option value="number">NUM</option>
          <option value="date">DATE</option>
          <option value="boolean">BOOL</option>
          <option value="array">ARR</option>
          <option value="object">OBJ</option>
          <option value="table">TBL</option>
          <option value="array_of_objects">ARR_OBJ</option>
        </select>

        {/* Description */}
        <input
          type="text"
          value={field.description || ''}
          onChange={(e) => onUpdate(field.id, { ...field, description: e.target.value })}
          onClick={(e) => e.stopPropagation()}
          className="flex-1 h-10 px-3 text-sm border border-gray-200 rounded focus:outline-none focus:ring-1 focus:ring-periwinkle-500 focus:border-transparent bg-white"
          placeholder="Description..."
        />

        {/* Required Checkbox */}
        <label className="flex items-center gap-1 flex-shrink-0 cursor-pointer" onClick={(e) => e.stopPropagation()}>
          <input
            type="checkbox"
            checked={field.required || false}
            onChange={(e) => onUpdate(field.id, { ...field, required: e.target.checked })}
            className="rounded border-gray-300 text-periwinkle-500 focus:ring-periwinkle-500"
          />
          <span className="text-xs text-gray-600">Required</span>
        </label>

        {/* Remove Button */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            onRemove(field.id);
          }}
          className="flex-shrink-0 w-5 h-5 text-gray-400 hover:text-red-600 transition-colors"
          title="Remove field"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Nested Fields (Array items or Object properties) */}
      {isNested && expanded && (
        <div className="mt-2 ml-6 space-y-2">
          {hasNestedFields && (
            <DndContext
              sensors={sensors}
              collisionDetection={closestCenter}
              onDragEnd={(event) => {
                const { active, over } = event;
                if (active.id !== over.id) {
                  const oldIndex = nestedFields.findIndex((item) => item.id === active.id);
                  const newIndex = nestedFields.findIndex((item) => item.id === over.id);
                  const reordered = arrayMove(nestedFields, oldIndex, newIndex);

                  if (field.type === 'array') {
                    onUpdate(field.id, { ...field, items: reordered });
                  } else {
                    onUpdate(field.id, { ...field, properties: reordered });
                  }
                }
              }}
            >
              <SortableContext
                items={nestedFields.map(f => f.id)}
                strategy={verticalListSortingStrategy}
              >
                {nestedFields.map((nestedField) => (
                  <SortableField
                    key={nestedField.id}
                    field={nestedField}
                    onUpdate={updateNestedField}
                    onRemove={removeNestedField}
                    depth={depth + 1}
                  />
                ))}
              </SortableContext>
            </DndContext>
          )}

          {/* Add Nested Field Button */}
          <button
            onClick={addNestedField}
            className="w-full py-2 text-xs border border-dashed border-gray-300 rounded text-gray-500 hover:border-periwinkle-400 hover:text-periwinkle-600 transition-colors"
          >
            + Add {field.type === 'array' ? 'Item' : 'Property'}
          </button>
        </div>
      )}
    </div>
  );
}

export default function FieldEditor({ templateId, templateName, initialFields, onSave, onCancel, isSaving = false }) {
  const [fields, setFields] = useState(
    initialFields.map((field, idx) => ({
      ...field,
      id: field.id || `field-${idx}`,
    }))
  );
  const [nlPrompt, setNlPrompt] = useState('');
  const [isProcessingPrompt, setIsProcessingPrompt] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  const [saveAsNewTemplate, setSaveAsNewTemplate] = useState(false);
  const [newTemplateName, setNewTemplateName] = useState(templateName);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleDragEnd = (event) => {
    const { active, over } = event;

    if (active.id !== over.id) {
      setFields((items) => {
        const oldIndex = items.findIndex((item) => item.id === active.id);
        const newIndex = items.findIndex((item) => item.id === over.id);
        const newFields = arrayMove(items, oldIndex, newIndex);
        setHasChanges(true);
        return newFields;
      });
    }
  };

  const updateField = (fieldId, updatedField) => {
    setFields(fields.map(f => f.id === fieldId ? updatedField : f));
    setHasChanges(true);
  };

  const removeField = (fieldId) => {
    setFields(fields.filter(f => f.id !== fieldId));
    setHasChanges(true);
  };

  const addField = () => {
    const newField = {
      id: `field-${Date.now()}`,
      name: `field_${fields.length + 1}`,
      type: 'text',
      required: false,
      description: '',
      extraction_hints: [],
      confidence_threshold: 0.75,
    };
    setFields([...fields, newField]);
    setHasChanges(true);
  };

  const handleNaturalLanguagePrompt = async () => {
    if (!nlPrompt.trim()) return;

    setIsProcessingPrompt(true);
    try {
      const response = await fetch(`${API_URL}/api/onboarding/modify-schema-prompt`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: nlPrompt,
          current_fields: fields.map(({ id, ...field }) => field), // Remove temporary id
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to process prompt');
      }

      // Update fields with new schema from Claude
      const updatedFields = data.fields.map((field, idx) => ({
        ...field,
        id: `field-${Date.now()}-${idx}`,
      }));

      setFields(updatedFields);
      setHasChanges(true);
      setNlPrompt('');
    } catch (error) {
      console.error('Error processing prompt:', error);
      alert('Failed to process prompt: ' + error.message);
    } finally {
      setIsProcessingPrompt(false);
    }
  };

  const handleSave = () => {
    console.log('=== FieldEditor handleSave START ===');
    console.log('onSave function:', onSave);
    console.log('onSave type:', typeof onSave);
    console.log('Fields:', fields);
    console.log('saveAsNewTemplate:', saveAsNewTemplate);
    console.log('hasChanges:', hasChanges);

    const cleanedFields = fields.map(({ id, ...field }) => field);
    console.log('Cleaned fields:', cleanedFields);

    const saveData = {
      fields: cleanedFields,
      name: saveAsNewTemplate ? newTemplateName : templateName,
      isNewTemplate: saveAsNewTemplate || hasChanges,
    };
    console.log('About to call onSave with:', saveData);

    try {
      onSave(saveData);
      console.log('onSave call completed (no error thrown)');
    } catch (err) {
      console.error('ERROR calling onSave:', err);
    }

    console.log('=== FieldEditor handleSave END ===');
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h3 className="text-lg font-semibold text-gray-900">Edit Template Fields</h3>
        <p className="text-sm text-gray-600 mt-1">
          Drag any row to reorder. Click to edit inline. Arrays and objects can be nested.
        </p>
      </div>

      {/* Natural Language Prompt */}
      <div className="bg-gradient-to-r from-periwinkle-50 to-sky-50 rounded-lg p-4 border border-periwinkle-200">
        <label className="block text-sm font-medium text-gray-900 mb-2">
          ✨ Modify with AI
        </label>
        <div className="flex gap-2">
          <input
            type="text"
            value={nlPrompt}
            onChange={(e) => setNlPrompt(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleNaturalLanguagePrompt()}
            placeholder='e.g., "Add a field for customer email" or "Remove all optional fields"'
            className="flex-1 px-4 py-2 border border-periwinkle-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-periwinkle-500"
            disabled={isProcessingPrompt}
          />
          <button
            onClick={handleNaturalLanguagePrompt}
            disabled={!nlPrompt.trim() || isProcessingPrompt}
            className="px-4 py-2 bg-periwinkle-500 text-white rounded-lg hover:bg-periwinkle-600 disabled:bg-gray-300 disabled:cursor-not-allowed font-medium"
          >
            {isProcessingPrompt ? 'Processing...' : 'Apply'}
          </button>
        </div>
      </div>

      {/* Field List with Drag and Drop */}
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
      >
        <SortableContext
          items={fields.map(f => f.id)}
          strategy={verticalListSortingStrategy}
        >
          <div className="space-y-2">
            {fields.map((field) => (
              <SortableField
                key={field.id}
                field={field}
                onUpdate={updateField}
                onRemove={removeField}
              />
            ))}
          </div>
        </SortableContext>
      </DndContext>

      {/* Add Field Button */}
      <button
        onClick={addField}
        className="w-full py-3 border-2 border-dashed border-gray-300 rounded-lg text-gray-600 hover:border-periwinkle-400 hover:text-periwinkle-600 font-medium transition-colors"
      >
        + Add Field
      </button>

      {/* Save Options */}
      {hasChanges && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <div className="text-yellow-600 mt-0.5">
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="flex-1">
              <h4 className="font-medium text-gray-900">You've made changes</h4>
              <p className="text-sm text-gray-600 mt-1">
                Save as a new template to preserve the original, or overwrite the existing one.
              </p>

              <div className="mt-3 space-y-2">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    checked={saveAsNewTemplate}
                    onChange={() => setSaveAsNewTemplate(true)}
                    className="text-periwinkle-500 focus:ring-periwinkle-500"
                  />
                  <span className="text-sm font-medium text-gray-900">Save as new template</span>
                </label>
                {saveAsNewTemplate && (
                  <input
                    type="text"
                    value={newTemplateName}
                    onChange={(e) => setNewTemplateName(e.target.value)}
                    placeholder="New template name"
                    className="ml-6 px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-periwinkle-500"
                  />
                )}

                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    checked={!saveAsNewTemplate}
                    onChange={() => setSaveAsNewTemplate(false)}
                    className="text-periwinkle-500 focus:ring-periwinkle-500"
                  />
                  <span className="text-sm font-medium text-gray-900">Update existing template</span>
                </label>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex gap-3 pt-4 border-t border-gray-200">
        <button
          onClick={onCancel}
          disabled={isSaving}
          className="flex-1 px-4 py-3 border border-gray-300 rounded-lg hover:bg-gray-50 font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Cancel
        </button>
        <button
          onClick={handleSave}
          disabled={isSaving}
          className="flex-1 px-4 py-3 bg-periwinkle-500 text-white rounded-lg hover:bg-periwinkle-600 font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
        >
          {isSaving ? (
            <>
              <svg className="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              <span>Creating template...</span>
            </>
          ) : (
            hasChanges ? (saveAsNewTemplate ? 'Save as New Template' : 'Update Template') : 'Save'
          )}
        </button>
      </div>
    </div>
  );
}
