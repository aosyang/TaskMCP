import React, { useState } from 'react';
import { createPortal } from 'react-dom';
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
  onEdit: (id: number, task?: string, comments?: string) => void;
  onDelete: (id: number) => void;
  onAddChild: (parentId: number, task: string) => void;
  onReorder: (updates: { id: number; position: number; parent_id: number | null }[]) => void;
  onSetCurrent: (id: number) => void;
  onFocusTask: (id: number) => void;
  disableReorder?: boolean;
  focusedTaskId?: number | null;
  commentsExpanded?: 'all' | 'none' | 'default';
  includeCompletedInExpand?: boolean;
  collapsedTaskIds: Set<number>;
  onToggleCollapse: (id: number) => void;
}

function SortableTaskItem({ task, onToggle, onEdit, onDelete, onAddChild, onReorder, onSetCurrent, onFocusTask, commentsExpanded = 'default', includeCompletedInExpand = true, collapsedTaskIds, onToggleCollapse, disableReorder = false, focusedTaskId = null }: TaskItemProps) {
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
  const childrenFolded = collapsedTaskIds.has(task.id);
  const [isHovering, setIsHovering] = useState(false);
  const [isHoveringTitle, setIsHoveringTitle] = useState(false);
  const [isFocusWithin, setIsFocusWithin] = useState(false);
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
  } = useSortable({ id: task.id, disabled: disableReorder });

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

  // Helper function to generate hover transition styles
  const getHoverTransitionStyle = (isVisible: boolean): React.CSSProperties => ({
    opacity: isVisible ? 1 : 0,
    visibility: isVisible ? 'visible' : 'hidden',
    pointerEvents: isVisible ? 'auto' : 'none',
    transition: 'opacity 0.2s ease-in-out'
  });

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
    // If comment is empty after losing focus, hide the comment section
    if (!commentsText.trim()) {
      setShowComments(false);
    }
  };

  const handleCommentsKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && e.ctrlKey) {
      handleCommentsSubmit();
    } else if (e.key === 'Escape') {
      const originalComments = task.comments || '';
      setCommentsText(originalComments);
      setIsEditingComments(false);
      // If original comment is empty, hide the comment section
      if (!originalComments.trim()) {
        setShowComments(false);
      }
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

      if (disableReorder || oldIndex < 0 || newIndex < 0) return;
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
          backgroundColor: task.done ? (focusedTaskId !== null ? 'var(--bg-secondary)' : 'var(--bg-done)') : (task.is_current ? 'var(--bg-current)' : 'var(--bg-secondary)'),
          border: task.is_current ? '2px solid var(--border-current)' : '1px solid var(--border-primary)',
          borderRadius: '8px',
          padding: isMobile ? '8px' : '6px 8px',
          marginBottom: 0,
          boxShadow: task.is_current ? '0 2px 6px var(--shadow)' : 'none',
          opacity: task.done && focusedTaskId !== null ? 0.62 : 1,
          boxSizing: 'border-box',
          transform: 'none'
        }}
        onMouseEnter={() => !isMobile && setIsHovering(true)}
        onMouseLeave={() => !isMobile && setIsHovering(false)}
        onFocusCapture={() => !isMobile && setIsFocusWithin(true)}
        onBlurCapture={(e) => {
          if (!isMobile && !e.currentTarget.contains(e.relatedTarget as Node | null)) {
            setIsFocusWithin(false);
          }
        }}
      >
        <div
          style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: isMobile ? 'wrap' : 'nowrap' }}
          onMouseEnter={() => !isMobile && setIsHoveringTitle(true)}
          onMouseLeave={() => !isMobile && setIsHoveringTitle(false)}
        >
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
              onClick={() => onToggleCollapse(task.id)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  onToggleCollapse(task.id);
                }
              }}
              aria-label={childrenFolded ? "Expand children" : "Collapse children"}
              aria-expanded={!childrenFolded}
              style={{
                cursor: 'pointer',
                fontSize: 'var(--font-size-xs)',
                color: 'var(--text-muted)',
                userSelect: 'none',
                width: '14px',
                height: '14px',
                minWidth: '14px',
                minHeight: '14px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
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
          <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', fontWeight: 'normal', alignSelf: 'center', lineHeight: '1' }}>#{task.id}</span>
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
                    fontSize: 'var(--font-size-base)',
                    wordBreak: 'break-word',
                    overflowWrap: 'break-word',
                    minWidth: 0
                  }}
                >
                  {task.is_current && <span style={{ fontSize: 'var(--font-size-sm)', marginRight: '6px' }} aria-label="Current task">📌</span>}
                  {task.task || '(Untitled task)'}
                </span>
              </>
            )}
          </div>
          {!isDragging && (
            <button type="button" className="btn-comments"
              onClick={() => {
                if (commentsText) {
                  setShowComments(!showComments);
                } else {
                  setShowComments(true);
                  setIsEditingComments(true);
                }
              }}
              aria-label={commentsText ? (showComments ? "Hide comments" : "Show comments") : "Add comment"}
              aria-expanded={showComments}
              title={commentsText ? (showComments ? "Hide comments" : "Show comments") : "Add comment"}
              style={{ flexShrink: 0, padding: '2px 5px', minHeight: isMobile ? '36px' : '28px', minWidth: isMobile ? '36px' : '28px', background: 'transparent', border: 'none', color: 'var(--text-secondary)' }}>
              <span aria-hidden="true">{commentsText && showComments ? '▾ ' : ''}💬</span>
            </button>
          )}
          {!isDragging && !isMobile && (
            <div
              className="task-actions"
              role="toolbar"
              aria-label="Task actions"
              style={getHoverTransitionStyle(isHovering || isFocusWithin || task.is_current || focusedTaskId === task.id)}
            >
              <button
                className={'btn btn-set-current' + (task.is_current ? ' is-active' : '')}
                onClick={() => onSetCurrent(task.id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onSetCurrent(task.id);
                  }
                }}
                aria-label={task.is_current ? `Clear current task` : `Set "${task.task}" as current task`}
                title={task.is_current ? "Clear current task" : "Set as current task"}
                style={getHoverTransitionStyle(isHovering || isFocusWithin || task.is_current)}
              >
                📌
              </button>
              <button
                className={'btn btn-focus' + (focusedTaskId === task.id ? ' is-active' : '')}
                onClick={() => onFocusTask(task.id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onFocusTask(task.id);
                  }
                }}
                aria-label={`Focus on task "${task.task}"`}
                title="Focus on this task"
                style={getHoverTransitionStyle(isHovering || isFocusWithin || focusedTaskId === task.id)}
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
                style={getHoverTransitionStyle(isHovering || isFocusWithin)}
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
                style={getHoverTransitionStyle(isHovering || isFocusWithin)}
              >
                🗑️
              </button>
            </div>
          )}
        </div>
          {!isDragging && isMobile && (
            <div className="task-actions task-actions-mobile" role="toolbar" aria-label="Task actions" style={{ marginTop: '4px', paddingTop: '4px', borderTop: '1px solid var(--border-primary)' }}>
              <button
                className={'btn btn-set-current' + (task.is_current ? ' is-active' : '')}
                onClick={() => onSetCurrent(task.id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onSetCurrent(task.id);
                  }
                }}
                aria-label={task.is_current ? `Clear current task` : `Set "${task.task}" as current task`}
                title={task.is_current ? "Clear current task" : "Set as current task"}
              >
                📌
              </button>
              <button
                className={'btn btn-focus' + (focusedTaskId === task.id ? ' is-active' : '')}
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

        {!isDragging && showComments && (
          <div className="comments-section" style={{ marginTop: '4px', paddingTop: '4px', borderTop: '1px solid var(--border-primary)' }}>
            {showComments && (isEditingComments ? (
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
                  fontSize: 'var(--font-size-md)',
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
            ))}
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
            marginTop: '4px',
            paddingTop: '4px',
            borderTop: '1px solid var(--border-secondary)',
            display: 'flex',
            flexDirection: 'column',
            gap: '5px'
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
                    disableReorder={disableReorder}
                    onToggle={onToggle}
                    onEdit={onEdit}
                    onDelete={onDelete}
                    onAddChild={onAddChild}
                    onReorder={onReorder}
                    onSetCurrent={onSetCurrent}
                    onFocusTask={onFocusTask}
                    commentsExpanded={commentsExpanded}
                    includeCompletedInExpand={includeCompletedInExpand}
                    collapsedTaskIds={collapsedTaskIds}
                    onToggleCollapse={onToggleCollapse}
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
  onEdit: (id: number, task?: string, comments?: string) => void;
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
  collapsedTaskIds: Set<number>;
  onToggleCollapse: (id: number) => void;
  onFoldCompleted: () => void;
  hideCompleted: boolean;
  onSetHideCompleted: (value: boolean) => void;
  taskCounts: { all: number; open: number };
  currentTask: Task | null;
  hiddenTaskCount: number;
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
  findTaskById,
  collapsedTaskIds,
  onToggleCollapse,
  onFoldCompleted,
  hideCompleted,
  onSetHideCompleted,
  taskCounts,
  currentTask,
  hiddenTaskCount
}: ListViewProps) {
  const [commentsExpanded, setCommentsExpanded] = useState<'all' | 'none' | 'default'>('default');
  const [includeCompletedInExpand, setIncludeCompletedInExpand] = useState(true);
  const [showFocusControls, setShowFocusControls] = useState(false);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;

    if (!hideCompleted && focusedTaskId === null && over && active.id !== over.id) {
      const oldIndex = tasks.findIndex((task) => task.id === active.id);
      const newIndex = tasks.findIndex((task) => task.id === over.id);

      if (oldIndex < 0 || newIndex < 0) return;
      const newTasks = arrayMove(tasks, oldIndex, newIndex);

      const updates = newTasks.map((task, index) => ({
        id: task.id,
        position: index,
        parent_id: null,
      }));
      onReorder(updates);
    }
  };



  return (
    <>
      {/* Control Buttons */}
      {focusedTaskId === null ? (
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
        <div role="group" aria-label="Filter tasks" style={{ display: 'inline-flex', gap: '2px', border: '1px solid var(--border-primary)', borderRadius: '6px', padding: '2px', marginRight: '4px' }}>
          {([false, true] as const).map(open => (
            <button key={String(open)} type="button" className="btn-comments"
              aria-pressed={hideCompleted === open}
              title={open ? 'Show unfinished tasks and their ancestors. Switch to All to reorder.' : 'Show all tasks'}
              onClick={() => onSetHideCompleted(open)}
              style={{ fontWeight: hideCompleted === open ? 600 : 400, background: hideCompleted === open ? 'var(--bg-current)' : 'transparent', border: hideCompleted === open ? '1px solid var(--border-current)' : '1px solid transparent' }}>
              {open ? 'Open' : 'All'} · {open ? taskCounts.open : taskCounts.all}
            </button>
          ))}
        </div>
        <div role="group" aria-label="Tree view controls" style={{ display: 'inline-flex', alignItems: 'center', flexWrap: 'wrap', gap: '8px', padding: '4px 8px', border: '1px solid var(--border-primary)', borderRadius: '6px' }}>
          <span style={{ fontSize: 'var(--font-size-sm)', fontWeight: 600, color: 'var(--text-secondary)' }}>Tree view</span>
          <button onClick={onFoldCompleted} className="btn-comments" aria-label="Fold completed branches" title="Collapse every completed branch. Unfinished branches keep their current open/closed state.">Fold Completed</button>
        </div>
        <div role="group" aria-label="Comment controls" style={{ display: 'inline-flex', alignItems: 'center', flexWrap: 'wrap', gap: '8px', padding: '4px 8px', border: '1px solid var(--border-primary)', borderRadius: '6px' }}>
          <span style={{ fontSize: 'var(--font-size-sm)', fontWeight: 600, color: 'var(--text-secondary)' }}>Comments</span>
        <button
          onClick={() => setCommentsExpanded('none')}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              setCommentsExpanded('none');
            }
          }}
          className="btn-comments"
          aria-label="Collapse all comments"
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
          className="btn-comments"
          aria-label="Expand all comments"
          title="Expand all comments"
        >
          Expand All
        </button>
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
      </div>

      ) : showFocusControls ? (
        <div style={{ marginBottom: '6px' }}>
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
        <div role="group" aria-label="Filter tasks" style={{ display: 'inline-flex', gap: '2px', border: '1px solid var(--border-primary)', borderRadius: '6px', padding: '2px', marginRight: '4px' }}>
          {([false, true] as const).map(open => (
            <button key={String(open)} type="button" className="btn-comments"
              aria-pressed={hideCompleted === open}
              title={open ? 'Show unfinished tasks and their ancestors. Switch to All to reorder.' : 'Show all tasks'}
              onClick={() => onSetHideCompleted(open)}
              style={{ fontWeight: hideCompleted === open ? 600 : 400, background: hideCompleted === open ? 'var(--bg-current)' : 'transparent', border: hideCompleted === open ? '1px solid var(--border-current)' : '1px solid transparent' }}>
              {open ? 'Open' : 'All'} · {open ? taskCounts.open : taskCounts.all}
            </button>
          ))}
        </div>
        <div role="group" aria-label="Tree view controls" style={{ display: 'inline-flex', alignItems: 'center', flexWrap: 'wrap', gap: '8px', padding: '4px 8px', border: '1px solid var(--border-primary)', borderRadius: '6px' }}>
          <span style={{ fontSize: 'var(--font-size-sm)', fontWeight: 600, color: 'var(--text-secondary)' }}>Tree view</span>
          <button onClick={onFoldCompleted} className="btn-comments" aria-label="Fold completed branches" title="Collapse every completed branch. Unfinished branches keep their current open/closed state.">Fold Completed</button>
        </div>
        <div role="group" aria-label="Comment controls" style={{ display: 'inline-flex', alignItems: 'center', flexWrap: 'wrap', gap: '8px', padding: '4px 8px', border: '1px solid var(--border-primary)', borderRadius: '6px' }}>
          <span style={{ fontSize: 'var(--font-size-sm)', fontWeight: 600, color: 'var(--text-secondary)' }}>Comments</span>
        <button
          onClick={() => setCommentsExpanded('none')}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              setCommentsExpanded('none');
            }
          }}
          className="btn-comments"
          aria-label="Collapse all comments"
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
          className="btn-comments"
          aria-label="Expand all comments"
          title="Expand all comments"
        >
          Expand All
        </button>
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
      </div>

        </div>
      ) : null}

      {focusedTaskId !== null && (
        <div style={{
          position: 'sticky',
          top: 0,
          background: 'var(--bg-current)',
          border: '1px solid var(--border-current)',
          borderRadius: '8px',
          padding: '6px 8px',
          marginBottom: '8px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          zIndex: 100,
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0, flex: 1 }}>
            <span style={{ fontSize: 'var(--font-size-base)' }}>🎯</span>
            <span style={{ fontSize: 'var(--font-size-base)', fontWeight: '600', color: 'var(--text-primary)' }}>Focus</span>
            <span style={{ fontSize: 'var(--font-size-sm)', color: 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', minWidth: 0 }}>
              {findTaskById(tasks, focusedTaskId)?.task}
            </span>
            <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{hiddenTaskCount} hidden</span>
            {currentTask && <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>📌 #{currentTask.id}</span>}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px', flexShrink: 0 }}>
            <button
              type="button"
              onClick={() => setShowFocusControls(!showFocusControls)}
              aria-label={showFocusControls ? "Hide view controls" : "Show view controls"}
              aria-expanded={showFocusControls}
              className="btn-comments"
              style={{ padding: '4px 8px', minHeight: '28px', color: 'var(--text-secondary)' }}
            >
              Controls
            </button>
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
                padding: '4px 8px',
                fontSize: '12px',
                background: 'var(--bg-secondary)',
                color: 'var(--text-primary)',
                border: '1px solid var(--border-primary)',
                borderRadius: '4px',
                cursor: 'pointer',
                fontWeight: '500',
                minHeight: '28px',
                minWidth: '28px'
              }}
            >
              ✕ Exit
            </button>
          </div>
        </div>
      )}

      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
      >
        <SortableContext
          items={tasks.map((t) => t.id)}
          strategy={verticalListSortingStrategy}
        >
          {/* Extra bottom padding keeps the floating "current task" pill from
              covering the last row. */}
          <div className="task-list" style={{ paddingBottom: '72px', display: 'flex', flexDirection: 'column', gap: '5px' }}>
            {hideCompleted && tasks.length === 0 && <p role="status" style={{ textAlign: 'center', color: 'var(--text-secondary)' }}>{focusedTaskId !== null ? 'No unfinished tasks in this focus.' : 'All tasks completed.'}</p>}
            {tasks.map((task) => (
              <SortableTaskItem
                key={task.id}
                task={task}
                disableReorder={hideCompleted}
                focusedTaskId={focusedTaskId}
                onToggle={onToggle}
                onEdit={onEdit}
                onDelete={onDelete}
                onAddChild={onAddChild}
                onReorder={onReorder}
                onSetCurrent={onSetCurrent}
                onFocusTask={onFocusTask}
                commentsExpanded={commentsExpanded}
                includeCompletedInExpand={includeCompletedInExpand}
                collapsedTaskIds={collapsedTaskIds}
                onToggleCollapse={onToggleCollapse}
              />
            ))}
          </div>
        </SortableContext>
      </DndContext>

      {/* Rendered into document.body on purpose: the list card uses
          `backdrop-filter`, which makes it the containing block for
          position: fixed descendants. Inside the card this button would be
          pinned to the card's bottom edge (far below the fold) instead of
          the viewport, so it has to escape via a portal. */}
      {currentTask && createPortal(
        <button
          onClick={scrollToCurrentTask}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              scrollToCurrentTask();
            }
          }}
          aria-label={`Go to current task: ${currentTask.task}`}
          style={{
            position: 'fixed',
            bottom: '20px',
            right: '20px',
            background: '#007bff',
            color: 'white',
            border: 'none',
            borderRadius: '999px',
            height: '44px',
            padding: '0 18px',
            maxWidth: '260px',
            fontSize: '14px',
            fontWeight: 600,
            fontFamily: 'inherit',
            cursor: 'pointer',
            boxShadow: '0 4px 12px var(--shadow)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '6px',
            zIndex: 1000,
            userSelect: 'none',
            touchAction: 'manipulation',
            whiteSpace: 'nowrap',
            overflow: 'hidden'
          }}
          title={`Go to current task: ${currentTask.task}`}
        >
          <span aria-hidden="true">📌</span>
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>
            #{currentTask.id} {currentTask.task}
          </span>
        </button>,
        document.body
      )}
    </>
  );
}
