import React, { useState } from 'react';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { renderMarkdown, Task } from '../utils';

interface TaskItemProps {
  task: Task;
  onToggle: (id: number) => void;
  onEdit: (id: number, task?: string, comments?: string, color?: string) => void;
  onDelete: (id: number) => void;
  onAddChild: (parentId: number, task: string) => void;
  onReorder: (updates: { id: number; position: number; parent_id: number | null }[]) => void;
  onSetCurrent: (id: number) => void;
  onFocusTask: (id: number) => void;
  commentsExpanded?: 'all' | 'none' | 'default';
  includeCompletedInExpand?: boolean;
}

function SortableTaskItem({ task, onToggle, onEdit, onDelete, onAddChild, onReorder, onSetCurrent, onFocusTask, commentsExpanded = 'default', includeCompletedInExpand = true }: TaskItemProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editText, setEditText] = useState(task.task);
  const [showAddChild, setShowAddChild] = useState(false);
  const [childText, setChildText] = useState('');
  const [localChildren, setLocalChildren] = useState(task.children);
  const [showComments, setShowComments] = useState(() => {
    if (commentsExpanded === 'all') return !!task.comments;
    if (commentsExpanded === 'none') return false;
    return !!task.comments && !task.done;
  });
  const [commentsText, setCommentsText] = useState(task.comments || '');
  const [isEditingComments, setIsEditingComments] = useState(false);
  // const [showColorPicker, setShowColorPicker] = useState(false);
  // const [tempColor, setTempColor] = useState(task.color || '#ffffff');
  const [childrenFolded, setChildrenFolded] = useState(false);
  const [isHovering, setIsHovering] = useState(false);
  const textareaRef = React.useRef<HTMLTextAreaElement>(null);
  const [isMobile, setIsMobile] = React.useState(() => {
    if (typeof window !== 'undefined') {
      return window.innerWidth <= 768;
    }
    return false;
  });

  // Update mobile detection on resize
  React.useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth <= 768);
    };
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: task.id });

  // Calculate height based on text content
  const calculateHeight = (text: string) => {
    const lines = text.split('\n').length;
    const baseHeight = 80;
    const lineHeight = 20;
    return Math.max(baseHeight, lines * lineHeight);
  };

  const [commentHeight, setCommentHeight] = useState(calculateHeight(commentsText));

  React.useEffect(() => {
    setLocalChildren(task.children);
  }, [task.children]);

  React.useEffect(() => {
    setCommentsText(task.comments || '');
    setCommentHeight(calculateHeight(task.comments || ''));
  }, [task.comments]);

  React.useEffect(() => {
    if (commentsExpanded === 'none') {
      // Collapse All: always collapse all comments
      setShowComments(false);
    } else if (commentsExpanded === 'all') {
      // Expand All: expand allowed comments
      if (task.done && !includeCompletedInExpand) {
        // Completed item with checkbox unchecked: collapse
        setShowComments(false);
      } else if (task.comments) {
        // Otherwise expand if has comments
        setShowComments(true);
      }
    }
  }, [commentsExpanded, task.comments, task.done, includeCompletedInExpand]);

  React.useEffect(() => {
    if (isEditingComments && textareaRef.current) {
      setCommentHeight(calculateHeight(commentsText));
    }
  }, [commentsText, isEditingComments]);

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  const handleDoubleClick = () => {
    setIsEditing(true);
  };

  const handleEditSubmit = () => {
    if (editText.trim() !== task.task) {
      onEdit(task.id, editText.trim());
    }
    setIsEditing(false);
  };

  const handleEditKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleEditSubmit();
    } else if (e.key === 'Escape') {
      setEditText(task.task);
      setIsEditing(false);
    }
  };

  const handleCommentsSubmit = () => {
    if (commentsText !== task.comments) {
      onEdit(task.id, undefined, commentsText);
    }
    setIsEditingComments(false);
  };

  const handleCommentsKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && e.ctrlKey) {
      handleCommentsSubmit();
    } else if (e.key === 'Escape') {
      setCommentsText(task.comments || '');
      setIsEditingComments(false);
    }
  };

  const handleChildKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleAddChild();
    } else if (e.key === 'Escape') {
      setShowAddChild(false);
      setChildText('');
    }
  };

  const handleAddChild = () => {
    if (childText.trim()) {
      onAddChild(task.id, childText.trim());
      setShowAddChild(false);
      setChildText('');
    }
  };

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;

    if (over && active.id !== over.id) {
      const oldIndex = localChildren.findIndex((child) => child.id === active.id);
      const newIndex = localChildren.findIndex((child) => child.id === over.id);

      const newChildren = arrayMove(localChildren, oldIndex, newIndex);
      setLocalChildren(newChildren);

      const updates = newChildren.map((child, index) => ({
        id: child.id,
        position: index,
        parent_id: task.id,
      }));
      onReorder(updates);
    }
  };

  return (
      <div 
        ref={setNodeRef} 
        data-task-id={task.id} 
        className={`task-item ${task.done ? 'done' : ''} ${isDragging ? 'dragging' : ''}`} 
        style={{ 
          ...style, 
          flexDirection: 'column', 
          alignItems: 'stretch', 
          backgroundColor: task.done ? 'var(--bg-done)' : (task.is_current ? 'var(--bg-current)' : 'var(--bg-secondary)'),
          border: '2px solid ' + (task.is_current ? 'var(--border-current)' : (task.done ? 'var(--border-done)' : 'var(--border-primary)')),
          borderRadius: '8px',
          padding: '12px',
          marginBottom: '8px',
          boxShadow: '0 1px 3px var(--shadow)'
        }}
        onMouseEnter={() => !isMobile && setIsHovering(true)}
        onMouseLeave={() => !isMobile && setIsHovering(false)}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: isMobile ? 'wrap' : 'nowrap' }}>
          <span 
            className="drag-handle" 
            {...attributes} 
            {...listeners}
            role="button"
            aria-label="Drag to reorder task"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                // Focus management for keyboard drag
              }
            }}
          >
            ⋮⋮
          </span>
          {localChildren.length > 0 ? (
            <button
              onClick={() => setChildrenFolded(!childrenFolded)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  setChildrenFolded(!childrenFolded);
                }
              }}
              aria-label={childrenFolded ? "Expand children" : "Collapse children"}
              aria-expanded={!childrenFolded}
              style={{
                cursor: 'pointer',
                fontSize: '10px',
                color: 'var(--text-muted)',
                userSelect: 'none',
                width: '12px',
                minWidth: '12px',
                minHeight: '24px',
                textAlign: 'center',
                background: 'transparent',
                border: 'none',
                padding: 0,
                touchAction: 'manipulation'
              }}
              title={childrenFolded ? "Expand children" : "Collapse children"}
            >
              {childrenFolded ? '▶' : '▼'}
            </button>
          ) : (
            <span style={{ width: '12px', display: 'inline-block' }} aria-hidden="true"></span>
          )}
          <label htmlFor={`task-checkbox-${task.id}`} className="sr-only">Toggle task completion</label>
          <input
            id={`task-checkbox-${task.id}`}
            type="checkbox"
            className="checkbox"
            checked={task.done}
            onChange={() => onToggle(task.id)}
            aria-label={`Mark task "${task.task}" as ${task.done ? 'incomplete' : 'complete'}`}
          />
          <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 'normal', alignSelf: 'flex-start', marginTop: '2px' }}>#{task.id}</span>
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
            {isEditing ? (
              <input
                type="text"
                className="task-input"
                name="task-edit"
                value={editText}
                onChange={(e) => setEditText(e.target.value)}
                onBlur={handleEditSubmit}
                onKeyDown={handleEditKeyDown}
                autoComplete="off"
                aria-label="Edit task"
                autoFocus={!isMobile}
              />
            ) : (
              <>
                <span 
                  className="task-text" 
                  onDoubleClick={handleDoubleClick} 
                  style={{ 
                    fontWeight: '600', 
                    fontSize: '14px',
                    wordBreak: 'break-word',
                    overflowWrap: 'break-word',
                    minWidth: 0
                  }}
                >
                  {task.is_current && <span style={{ fontSize: '12px', marginRight: '6px' }} aria-label="Current task">▶️</span>}
                  {task.task || '(Untitled task)'}
                </span>
                {!isDragging && commentsText && (
                  <button
                    onClick={() => setShowComments(!showComments)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        setShowComments(!showComments);
                      }
                    }}
                    aria-label={showComments ? "Hide comments" : "Show comments"}
                    aria-expanded={showComments}
                    style={{ 
                      cursor: 'pointer',
                      fontSize: '12px',
                      color: 'var(--text-muted)',
                      marginTop: '4px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                      userSelect: 'none',
                      background: 'transparent',
                      border: 'none',
                      padding: 0,
                      textAlign: 'left',
                      touchAction: 'manipulation'
                    }}
                    title={showComments ? "Hide comments" : "Show comments"}
                  >
                    <span style={{ fontSize: '10px' }} aria-hidden="true">{showComments ? '▼' : '▶'}</span>
                    <span style={{ opacity: 0.9 }} aria-hidden="true">💬</span>
                    <span>{showComments ? 'Hide comments' : 'Show comments'}</span>
                  </button>
                )}
              </>
            )}
          </div>
          {!isDragging && !isMobile && isHovering && (
            <div className="task-actions" role="toolbar" aria-label="Task actions">
              <button 
                className="btn btn-set-current" 
                onClick={() => onSetCurrent(task.id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onSetCurrent(task.id);
                  }
                }}
                aria-label={`Set "${task.task}" as current task`}
                title="Set as current task"
              >
                ▶️
              </button>
              <button 
                className="btn btn-focus" 
                onClick={() => onFocusTask(task.id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onFocusTask(task.id);
                  }
                }}
                aria-label={`Focus on task "${task.task}"`}
                title="Focus on this task"
              >
                🎯
              </button>
              <button 
                className="btn btn-add" 
                onClick={() => setShowAddChild(!showAddChild)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    setShowAddChild(!showAddChild);
                  }
                }}
                aria-label={`Add subtask to "${task.task}"`}
                aria-expanded={showAddChild}
                title="Add subtask"
              >
                ➕
              </button>
              {/* <button className="btn btn-color" onClick={() => setShowColorPicker(!showColorPicker)} title="Change color">
                🎨
              </button> */}
              <button 
                className="btn btn-delete" 
                onClick={() => onDelete(task.id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onDelete(task.id);
                  }
                }}
                aria-label={`Delete task "${task.task}"`}
                title="Delete"
              >
                🗑️
              </button>
            </div>
          )}
        </div>
          {!isDragging && isMobile && (
            <div className="task-actions task-actions-mobile" role="toolbar" aria-label="Task actions" style={{ marginTop: '8px', paddingTop: '12px', borderTop: '1px solid var(--border-primary)' }}>
              <button 
                className="btn btn-set-current" 
                onClick={() => onSetCurrent(task.id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onSetCurrent(task.id);
                  }
                }}
                aria-label={`Set "${task.task}" as current task`}
                title="Set as current task"
              >
                ▶️
              </button>
              <button 
                className="btn btn-focus" 
                onClick={() => onFocusTask(task.id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onFocusTask(task.id);
                  }
                }}
                aria-label={`Focus on task "${task.task}"`}
                title="Focus on this task"
              >
                🎯
              </button>
              <button 
                className="btn btn-add" 
                onClick={() => setShowAddChild(!showAddChild)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    setShowAddChild(!showAddChild);
                  }
                }}
                aria-label={`Add subtask to "${task.task}"`}
                aria-expanded={showAddChild}
                title="Add subtask"
              >
                ➕
              </button>
              <button 
                className="btn btn-delete" 
                onClick={() => onDelete(task.id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onDelete(task.id);
                  }
                }}
                aria-label={`Delete task "${task.task}"`}
                title="Delete"
              >
                🗑️
              </button>
            </div>
          )}

          {/* Color picker temporarily disabled */}
        {/* 
        {!isDragging && showColorPicker && (
          <div className="color-picker">
            <input
              type="color"
              value={tempColor}
              onChange={(e) => setTempColor(e.target.value)}
            />
            <button className="btn" onClick={() => {
              onEdit(task.id, undefined, undefined, tempColor);
              setShowColorPicker(false);
            }}>
              ✓
            </button>
            <button className="btn" onClick={() => {
              setTempColor(task.color || '#ffffff');
              setShowColorPicker(false);
            }}>
              ✕
            </button>
          </div>
        )} 
        */}

        {!isDragging && showComments && (
          <div className="comments-section" style={{ marginTop: '8px', paddingTop: '8px', borderTop: '1px solid var(--border-primary)' }}>
            {isEditingComments ? (
              <textarea
                ref={textareaRef}
                className="task-input"
                name="task-comments"
                value={commentsText}
                onChange={(e) => setCommentsText(e.target.value)}
                onBlur={handleCommentsSubmit}
                onKeyDown={handleCommentsKeyDown}
                placeholder="Add comments. (Ctrl+Enter to save, Esc to cancel). Supports markdown: **bold**, *italic*, [links](url), lists, code, etc."
                aria-label="Task comments"
                style={{ 
                  width: '100%', 
                  minHeight: `${commentHeight}px`,
                  resize: 'vertical', 
                  fontFamily: 'inherit',
                  fontSize: '16px',
                  padding: '8px',
                  background: 'var(--bg-tertiary)',
                  color: 'var(--text-primary)',
                  borderRadius: '4px',
                  border: '2px solid #007bff',
                  lineHeight: '1.6',
                  boxSizing: 'border-box',
                  overflow: 'hidden',
                  touchAction: 'manipulation'
                }}
                autoFocus={!isMobile}
              />
            ) : (
              <div
                onDoubleClick={() => setIsEditingComments(true)}
                className="markdown-content"
                style={{
                  padding: '8px',
                  background: 'var(--bg-tertiary)',
                  borderRadius: '4px',
                  cursor: 'auto',
                  minHeight: `${commentHeight}px`,
                  fontSize: '13px',
                  color: 'var(--text-secondary)',
                  boxSizing: 'border-box',
                  wordBreak: 'break-word',
                  overflowWrap: 'break-word'
                }}
              >
                {commentsText ? (
                  <div dangerouslySetInnerHTML={renderMarkdown(commentsText)} />
                ) : (
                  <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>Double-click to add comments...</span>
                )}
              </div>
            )}
          </div>
        )}

        {showAddChild && (
          <div style={{ marginTop: '12px', paddingTop: '12px', borderTop: '1px solid var(--border-secondary)' }}>
            <div style={{ display: 'flex', gap: '10px' }}>
              <label htmlFor={`subtask-input-${task.id}`} className="sr-only">Add subtask</label>
              <input
                id={`subtask-input-${task.id}`}
                type="text"
                className="task-input"
                name="subtask"
                placeholder="Add subtask."
                value={childText}
                onChange={(e) => setChildText(e.target.value)}
                onKeyDown={handleChildKeyDown}
                autoComplete="off"
                aria-label="Subtask input"
                autoFocus={!isMobile}
              />
              <button 
                className="btn btn-add" 
                onClick={handleAddChild}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    handleAddChild();
                  }
                }}
                aria-label="Add subtask"
                title="Add"
              >
                ✓
              </button>
              <button 
                className="btn" 
                onClick={() => {
                  setShowAddChild(false);
                  setChildText('');
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    setShowAddChild(false);
                    setChildText('');
                  }
                }}
                aria-label="Cancel adding subtask"
                title="Cancel"
              >
                ✕
              </button>
            </div>
          </div>
        )}

        {localChildren.length > 0 && !childrenFolded && (
          <div style={{ 
            marginTop: '12px',
            paddingTop: '12px',
            borderTop: '1px solid var(--border-secondary)',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px'
          }}>
            <DndContext
              sensors={sensors}
              collisionDetection={closestCenter}
              onDragEnd={handleDragEnd}
            >
              <SortableContext
                items={localChildren.map((c) => c.id)}
                strategy={verticalListSortingStrategy}
              >
                {localChildren.map((child) => (
                  <SortableTaskItem
                    key={child.id}
                    task={child}
                    onToggle={onToggle}
                    onEdit={onEdit}
                    onDelete={onDelete}
                    onAddChild={onAddChild}
                    onReorder={onReorder}
                    onSetCurrent={onSetCurrent}
                    onFocusTask={onFocusTask}
                    commentsExpanded={commentsExpanded}
                    includeCompletedInExpand={includeCompletedInExpand}
                  />
                ))}
              </SortableContext>
            </DndContext>
          </div>
        )}
      </div>
    );
  }

interface ListViewProps {
  tasks: Task[];
  onToggle: (id: number) => void;
  onEdit: (id: number, task?: string, comments?: string, color?: string) => void;
  onDelete: (id: number) => void;
  onAddChild: (parentId: number, task: string) => void;
  onReorder: (updates: { id: number; position: number; parent_id: number | null }[]) => void;
  onSetCurrent: (id: number) => void;
  onFocusTask: (id: number) => void;
  findCurrentTask: (tasks: Task[]) => Task | null;
  scrollToCurrentTask: () => void;
  focusedTaskId: number | null;
  handleUnfocus: () => void;
  findTaskById: (tasks: Task[], id: number) => Task | null;
}

export function ListView({ 
  tasks, 
  onToggle, 
  onEdit, 
  onDelete, 
  onAddChild, 
  onReorder, 
  onSetCurrent,
  onFocusTask,
  findCurrentTask,
  scrollToCurrentTask,
  focusedTaskId,
  handleUnfocus,
  findTaskById
}: ListViewProps) {
  const [hideCompleted, setHideCompleted] = useState(false);
  const [commentsExpanded, setCommentsExpanded] = useState<'all' | 'none' | 'default'>('default');
  const [includeCompletedInExpand, setIncludeCompletedInExpand] = useState(true);
  
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;

    if (over && active.id !== over.id) {
      const oldIndex = tasks.findIndex((task) => task.id === active.id);
      const newIndex = tasks.findIndex((task) => task.id === over.id);

      const newTasks = arrayMove(tasks, oldIndex, newIndex);

      const updates = newTasks.map((task, index) => ({
        id: task.id,
        position: index,
        parent_id: null,
      }));
      onReorder(updates);
    }
  };

  const currentTask = findCurrentTask(tasks);
  const filteredTasks = hideCompleted ? tasks.filter(task => !task.done) : tasks;

  return (
    <>
      {/* Control Buttons */}
      <div style={{
        position: 'sticky',
        top: focusedTaskId !== null ? '50px' : '0',
        display: 'flex',
        gap: '8px',
        marginBottom: '16px',
        padding: '8px',
        background: 'var(--bg-tertiary)',
        borderRadius: '8px',
        alignItems: 'center',
        flexWrap: 'wrap',
        zIndex: 99,
        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)'
      }}>
        <span style={{ fontSize: '13px', fontWeight: '600', color: 'var(--text-secondary)', marginRight: '8px' }}>
          Comments:
        </span>
        <button
          onClick={() => setCommentsExpanded('none')}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              setCommentsExpanded('none');
            }
          }}
          aria-label="Collapse all comments"
          style={{
            padding: '6px 12px',
            fontSize: '12px',
            border: '1px solid var(--border-primary)',
            borderRadius: '4px',
            background: 'var(--bg-secondary)',
            color: 'var(--text-primary)',
            cursor: 'pointer',
            fontWeight: '500',
            minHeight: '24px',
            minWidth: '24px'
          }}
          title="Collapse all comments"
        >
          Collapse All
        </button>
        <button
          onClick={() => setCommentsExpanded('all')}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              setCommentsExpanded('all');
            }
          }}
          aria-label="Expand all comments"
          style={{
            padding: '6px 12px',
            fontSize: '12px',
            border: '1px solid var(--border-primary)',
            borderRadius: '4px',
            background: 'var(--bg-secondary)',
            color: 'var(--text-primary)',
            cursor: 'pointer',
            fontWeight: '500',
            minHeight: '24px',
            minWidth: '24px'
          }}
          title="Expand all comments"
        >
          Expand All
        </button>
        <div style={{ width: '1px', height: '24px', background: 'var(--border-primary)', margin: '0 8px' }}></div>
        <label style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          fontSize: '13px',
          color: 'var(--text-secondary)',
          cursor: 'pointer',
          userSelect: 'none'
        }}>
          <input
            type="checkbox"
            checked={includeCompletedInExpand}
            onChange={(e) => setIncludeCompletedInExpand(e.target.checked)}
            aria-label="Include completed tasks when expanding comments"
            style={{ cursor: 'pointer', minWidth: '24px', minHeight: '24px' }}
          />
          Expand completed comments
        </label>
      </div>

      {focusedTaskId !== null && (
        <div style={{
          position: 'sticky',
          top: 0,
          background: 'var(--bg-current)',
          border: '1px solid var(--border-current)',
          borderRadius: '8px',
          padding: '8px',
          marginBottom: '16px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          zIndex: 100,
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '14px' }}>🎯</span>
            <span style={{ fontSize: '13px', fontWeight: '600', color: 'var(--text-primary)' }}>Focus Mode</span>
            <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
              Viewing: {findTaskById(tasks, focusedTaskId)?.task}
            </span>
          </div>
          <button 
            onClick={handleUnfocus}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                handleUnfocus();
              }
            }}
            aria-label="Exit focus mode"
            style={{
              padding: '6px 12px',
              fontSize: '12px',
              background: 'var(--bg-secondary)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-primary)',
              borderRadius: '4px',
              cursor: 'pointer',
              fontWeight: '500',
              minHeight: '24px',
              minWidth: '24px'
            }}
          >
            ✕ Exit Focus
          </button>
        </div>
      )}

      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
      >
        <SortableContext
          items={filteredTasks.map((t) => t.id)}
          strategy={verticalListSortingStrategy}
        >
          <div className="task-list">
            {filteredTasks.map((task) => (
              <SortableTaskItem
                key={task.id}
                task={task}
                onToggle={onToggle}
                onEdit={onEdit}
                onDelete={onDelete}
                onAddChild={onAddChild}
                onReorder={onReorder}
                onSetCurrent={onSetCurrent}
                onFocusTask={onFocusTask}
                commentsExpanded={commentsExpanded}
                includeCompletedInExpand={includeCompletedInExpand}
              />
            ))}
          </div>
        </SortableContext>
      </DndContext>

      {currentTask && (
        <button
          onClick={scrollToCurrentTask}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              scrollToCurrentTask();
            }
          }}
          aria-label="Go to current task"
          style={{
            position: 'fixed',
            bottom: '20px',
            right: '20px',
            background: '#007bff',
            color: 'white',
            border: 'none',
            borderRadius: '50%',
            width: '60px',
            height: '60px',
            minWidth: '60px',
            minHeight: '60px',
            fontSize: '24px',
            cursor: 'pointer',
            boxShadow: '0 4px 8px var(--shadow)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            userSelect: 'none',
            touchAction: 'manipulation'
          }}
          title="Go to current task"
        >
          ▶️
        </button>
      )}
    </>
  );
}
