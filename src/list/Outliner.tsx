import React, { useState } from 'react';
import { Task } from '../utils';

interface OutlinerProps {
  tasks: Task[];
  onScrollToTask: (id: number) => void;
  findCurrentTask: (tasks: Task[]) => Task | null;
}

export function Outliner({ tasks, onScrollToTask, findCurrentTask }: OutlinerProps) {
  const [collapsedNodes, setCollapsedNodes] = useState<Set<number>>(new Set());

  const toggleCollapse = (id: number) => {
    setCollapsedNodes(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const currentTask = findCurrentTask(tasks);

  const renderOutlineItem = (task: Task, depth: number = 0) => {
    const isCollapsed = collapsedNodes.has(task.id);
    const hasChildren = task.children.length > 0;
    const isCurrent = currentTask?.id === task.id;

    return (
      <div key={task.id}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            paddingLeft: `${depth * 16}px`,
            paddingRight: '8px',
            paddingTop: '4px',
            paddingBottom: '4px',
            cursor: 'pointer',
            fontSize: 'var(--font-size-base)',
            borderRadius: '8px',
            background: isCurrent ? 'var(--bg-current)' : 'transparent',
            transition: 'background 0.2s ease, transform 0.15s ease'
          }}
          onMouseEnter={(e) => {
            if (!isCurrent) {
              e.currentTarget.style.background = 'var(--bg-hover)';
              e.currentTarget.style.transform = 'translateX(4px)';
            }
          }}
          onMouseLeave={(e) => {
            if (!isCurrent) {
              e.currentTarget.style.background = 'transparent';
              e.currentTarget.style.transform = 'translateX(0)';
            }
          }}
        >
          {hasChildren ? (
            <button
              onClick={(e) => {
                e.stopPropagation();
                toggleCollapse(task.id);
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  e.stopPropagation();
                  toggleCollapse(task.id);
                }
              }}
              aria-label={isCollapsed ? `Expand ${task.task}` : `Collapse ${task.task}`}
              aria-expanded={!isCollapsed}
              style={{
                width: '14px',
                height: '14px',
                minWidth: '14px',
                minHeight: '14px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                marginRight: '4px',
                fontSize: '10px',
                color: 'var(--text-muted)',
                userSelect: 'none',
                background: 'transparent',
                border: 'none',
                cursor: 'pointer',
                padding: 0
              }}
            >
              {isCollapsed ? '▶' : '▼'}
            </button>
          ) : (
            <span style={{ width: '14px', marginRight: '4px' }} aria-hidden="true"></span>
          )}
          <button
            onClick={() => onScrollToTask(task.id)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onScrollToTask(task.id);
              }
            }}
            aria-label={`Go to task: ${task.task}`}
            style={{
              flex: 1,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              color: task.done ? 'var(--text-muted)' : 'var(--text-primary)',
              textDecoration: task.done ? 'line-through' : 'none',
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              textAlign: 'left',
              padding: 0,
              minHeight: '24px',
              touchAction: 'manipulation'
            }}
            title={task.task}
          >
            {isCurrent && <span style={{ marginRight: '4px' }} aria-label="Current task">▶️</span>}
            {task.task || '(Untitled task)'}
          </button>
        </div>
        {hasChildren && !isCollapsed && (
          <div>
            {task.children.map(child => renderOutlineItem(child, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div
      style={{
        width: '250px',
        maxWidth: '100vw',
        height: 'calc(100vh - 120px)',
        maxHeight: '100vh',
        position: 'sticky',
        top: '20px',
        background: 'var(--bg-tertiary)',
        border: '1px solid var(--border-primary)',
        borderRadius: '12px',
        padding: '16px',
        overflowY: 'auto',
        overflowX: 'hidden',
        boxShadow: '0 4px 16px var(--shadow-elevated)',
        boxSizing: 'border-box',
        margin: '0 auto',
        backdropFilter: 'blur(10px)'
      }}
    >
      <div
        style={{
          fontSize: 'var(--font-size-xs)',
          fontWeight: '700',
          color: 'var(--text-secondary)',
          marginBottom: '16px',
          paddingBottom: '12px',
          borderBottom: '2px solid var(--border-primary)',
          textTransform: 'uppercase',
          letterSpacing: '0.08em',
          fontFamily: 'var(--font-display)'
        }}
      >
        Outline
      </div>
      <div>
        {tasks.map(task => renderOutlineItem(task, 0))}
      </div>
    </div>
  );
}
