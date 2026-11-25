import React, { useState, useEffect } from 'react';
import ReactDOM from 'react-dom/client';
import { Task } from './utils';
import { ListView } from './list/ListView';
import { Outliner } from './list/Outliner';

function App() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [newTask, setNewTask] = useState('');
  const [workspaces, setWorkspaces] = useState<string[]>([]);
  const [currentWorkspace, setCurrentWorkspace] = useState<string>('');
  const [showWorkspaceManager, setShowWorkspaceManager] = useState(false);
  const [newWorkspaceName, setNewWorkspaceName] = useState('');
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    // Load theme from localStorage or default to light
    const saved = localStorage.getItem('theme');
    return (saved === 'dark' || saved === 'light') ? saved : 'light';
  });
  const [focusedTaskId, setFocusedTaskId] = useState<number | null>(null);
  const [hideCompleted, setHideCompleted] = useState(false);
  const [showOutliner, setShowOutliner] = useState(true);
  const [isMobile, setIsMobile] = useState(false);
  const [stickyOffset, setStickyOffset] = useState(10);
  const [showManageText, setShowManageText] = useState(true);
  const [isTaskInputFocused, setIsTaskInputFocused] = useState(false);
  const [showFocusAdd, setShowFocusAdd] = useState(false);
  const blurTimeoutRef = React.useRef<NodeJS.Timeout | null>(null);
  const [showToast, setShowToast] = useState(false);
  const [toastFadingOut, setToastFadingOut] = useState(false);
  const [toastTopOffset, setToastTopOffset] = useState(20);
  const [toastMessage, setToastMessage] = useState('Task added');
  const [collapsedTaskIds, setCollapsedTaskIds] = useState<Set<number>>(new Set());

  // Detect screen size and auto-hide outliner on mobile
  useEffect(() => {
    const checkScreenSize = () => {
      const mobile = window.innerWidth <= 768;
      setIsMobile(mobile);
      if (mobile) {
        setShowOutliner(false);
      } else {
        setShowOutliner(true);
      }
    };

    checkScreenSize();
    window.addEventListener('resize', checkScreenSize);
    return () => window.removeEventListener('resize', checkScreenSize);
  }, []);

  // Check if Manage button text should be hidden in compact mode
  useEffect(() => {
    const checkManageButtonSpace = () => {
      const mainContent = document.querySelector('#main-content');
      if (mainContent) {
        const buttonContainer = mainContent.querySelector('div[style*="display: flex"]') as HTMLElement;
        if (buttonContainer) {
          const containerWidth = buttonContainer.getBoundingClientRect().width;
          // Hide text if container width is less than 300px (compact mode)
          setShowManageText(containerWidth >= 300);
        }
      }
    };

    checkManageButtonSpace();
    window.addEventListener('resize', checkManageButtonSpace);
    // Also check after a short delay to ensure DOM is ready
    const timer = setTimeout(checkManageButtonSpace, 100);

    return () => {
      window.removeEventListener('resize', checkManageButtonSpace);
      clearTimeout(timer);
    };
  }, [tasks, workspaces]);

  const loadWorkspaces = async () => {
    const response = await fetch('/api/workspaces');
    const data = await response.json();
    setWorkspaces(data.workspaces);
    setCurrentWorkspace(data.current);
  };

  const loadTasks = async () => {
    const response = await fetch('/api/tasks');
    const data = await response.json();
    setTasks(data);
  };

  // Apply theme to document
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  useEffect(() => {
    loadWorkspaces();
    loadTasks();

    // Connect to WebSocket for real-time updates
    const script = document.createElement('script');
    script.src = 'https://cdn.socket.io/4.5.4/socket.io.min.js';
    script.onload = () => {
      const socket = (window as any).io();
      socket.on('tasks_updated', () => {
        loadTasks();
      });
      socket.on('workspace_changed', () => {
        loadWorkspaces();
        loadTasks();
      });
    };
    document.head.appendChild(script);

    return () => {
      script.remove();
    };
  }, []);


  const handleAdd = async () => {
    if (newTask.trim()) {
      const response = await fetch('/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task: newTask.trim(), parent_id: null }),
      });
      if (response.ok) {
        setNewTask('');
        // Show toast notification
        showToastNotification('Task added');
        // Remove focus from input to hide buttons
        const input = document.getElementById('new-task-input') as HTMLInputElement;
        if (input) {
          input.blur();
        }
      }
    }
  };

  const handleToggle = async (id: number) => {
    await fetch(`/toggle/${id}`);
  };

  const handleEdit = async (id: number, task?: string, comments?: string) => {
    const body: any = {};
    if (task !== undefined) body.task = task;
    if (comments !== undefined) body.comments = comments;

    await fetch(`/edit/${id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  };

  const showToastNotification = (message: string) => {
    setToastMessage(message);
    setShowToast(true);
    setToastFadingOut(false);
    setTimeout(() => {
      // Start fade out animation
      setToastFadingOut(true);
      // Hide after animation completes
      setTimeout(() => {
        setShowToast(false);
        setToastFadingOut(false);
      }, 300);
    }, 2000);
  };

  const handleDelete = async (id: number) => {
    if (confirm('Delete this task and all its subtasks?')) {
      const response = await fetch(`/delete/${id}`);
      if (response.ok) {
        showToastNotification('Task deleted');
      }
    }
  };

  const handleAddChild = async (parentId: number, task: string) => {
    const response = await fetch('/add', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task, parent_id: parentId }),
    });
    if (response.ok) {
      // Show toast notification
      showToastNotification('任务已添加');
    }
  };

  const handleReorder = async (updates: { id: number; position: number; parent_id: number | null }[]) => {
    await fetch('/reorder', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ updates }),
    });
  };

  const handleSetCurrent = async (id: number) => {
    const currentTask = findCurrentTask(tasks);
    if (currentTask && currentTask.id === id) {
      // If already current, clear it
      await fetch('/clear_current', { method: 'POST' });
    } else {
      // Set as current
      await fetch(`/set_current/${id}`, { method: 'POST' });
    }
  };


  // Find current task recursively
  const findCurrentTask = (tasks: Task[]): Task | null => {
    for (const task of tasks) {
      if (task.is_current) return task;
      if (task.children.length > 0) {
        const found = findCurrentTask(task.children);
        if (found) return found;
      }
    }
    return null;
  };

  const getStickyOffset = (): number => {
    const mainContent = document.querySelector('#main-content');
    if (!mainContent) return 10;

    let obstructionBottom = 0;
    const elements = mainContent.querySelectorAll<HTMLElement>('*');
    for (const element of elements) {
      const style = window.getComputedStyle(element);
      if (style.position !== 'sticky' || style.display === 'none' || style.visibility === 'hidden') continue;

      const rect = element.getBoundingClientRect();
      if (rect.height <= 0) continue;

      const stickyTop = Number.parseFloat(style.top);
      const top = Number.isFinite(stickyTop) ? stickyTop : 0;
      obstructionBottom = Math.max(obstructionBottom, top + rect.height);
    }

    return obstructionBottom + 10;
  };

  // Update sticky offset for button positioning
  useEffect(() => {
    const updateStickyOffset = () => {
      const mainContent = document.querySelector('#main-content');
      if (mainContent) {
        let maxBottom = 0;
        let toastOffset = 0;
        const allDivs = mainContent.querySelectorAll('div');

        // Find all sticky divs and check if they're actually "stuck" at the top
        for (const div of allDivs) {
          const style = window.getComputedStyle(div);
          if (style.position === 'sticky') {
            const rect = div.getBoundingClientRect();
            const stickyTop = parseInt(style.top) || 0;

            // Check if the sticky element is actually "stuck" (its top matches the sticky top value)
            // Allow a small tolerance (2px) for rounding
            const isStuck = Math.abs(rect.top - stickyTop) < 2;

            if (isStuck) {
              // Calculate bottom position: top + height
              const bottom = rect.top + rect.height;
              if (bottom > maxBottom) {
                maxBottom = bottom;
              }
            }

            // For toast, calculate offset based on all sticky elements (whether stuck or not)
            // This ensures toast doesn't overlap sticky elements even when they're not stuck
            if (div.textContent?.includes('Comments:') || div.textContent?.includes('Focus Mode')) {
              toastOffset += rect.height;
            }
          }
        }

        // Set offset to the bottom of the lowest stuck sticky element + padding
        // If no sticky elements are stuck, use default 10px
        if (maxBottom > 0) {
          setStickyOffset(maxBottom + 10); // Add 10px padding
        } else {
          setStickyOffset(10);
        }

        // Set toast offset (always consider sticky elements to avoid overlap)
        setToastTopOffset(Math.max(20, toastOffset + 10));
      } else {
        setStickyOffset(10);
        setToastTopOffset(20);
      }
    };

    updateStickyOffset();

    // Update on scroll and resize
    window.addEventListener('scroll', updateStickyOffset);
    window.addEventListener('resize', updateStickyOffset);

    // Also update when focusedTaskId changes or tasks update
    const timer = setTimeout(updateStickyOffset, 100);

    return () => {
      window.removeEventListener('scroll', updateStickyOffset);
      window.removeEventListener('resize', updateStickyOffset);
      clearTimeout(timer);
    };
  }, [focusedTaskId, tasks]);

  const scrollToCurrentTask = () => {
    const currentTask = findCurrentTask(tasks);
    if (!currentTask) return;
    const findPath = (nodes: Task[]): number[] | null => {
      for (const task of nodes) {
        if (task.id === currentTask.id) return [task.id];
        const child = findPath(task.children);
        if (child) return [task.id, ...child];
      }
      return null;
    };
    const path = findPath(tasks) || [];
    if (hideCompleted && currentTask.done) setTaskFilterPreference(false);
    if (focusedTaskId !== null && !path.includes(focusedTaskId)) setFocusedTaskId(null);
    setCollapsedTaskIds(prev => {
      const next = new Set(prev);
      path.slice(0, -1).forEach(id => next.delete(id));
      return next;
    });
    setTimeout(() => scrollToTask(currentTask.id), 100);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleAdd();
    }
  };

  // Collapse every finished branch and leave everything else alone: tasks that
  // are not done keep whatever open/closed state they already had, so this
  // never expands a branch the user (or an agent) had closed.
  const handleFoldCompleted = () => {
    const doneBranchIds: number[] = [];
    const walk = (list: Task[]) => {
      list.forEach((task) => {
        if (task.done && task.children && task.children.length > 0) {
          doneBranchIds.push(task.id);
        }
        if (task.children) {
          walk(task.children);
        }
      });
    };
    walk(tasks);
    if (doneBranchIds.length === 0) {
      showToastNotification('没有可折叠的已完成分支');
      return;
    }
    setCollapsedTaskIds((prev) => {
      const next = new Set(prev);
      doneBranchIds.forEach((id) => next.add(id));
      return next;
    });
    showToastNotification(`已折叠 ${doneBranchIds.length} 个已完成分支`);
  };

  const handleSwitchWorkspace = async (workspace: string) => {
    await fetch('/api/workspace/switch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workspace }),
    });
    await loadWorkspaces();
    await loadTasks();
  };

  const handleCreateWorkspace = async () => {
    if (newWorkspaceName.trim()) {
      const response = await fetch('/api/workspace/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workspace: newWorkspaceName.trim() }),
      });
      const data = await response.json();
      if (data.success) {
        setNewWorkspaceName('');
        await loadWorkspaces();
      } else {
        alert(data.error);
      }
    }
  };

  const handleDeleteWorkspace = async (workspace: string) => {
    if (confirm(`Delete workspace "${workspace}"? This cannot be undone.`)) {
      const response = await fetch('/api/workspace/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workspace }),
      });
      const data = await response.json();
      if (data.success) {
        await loadWorkspaces();
      } else {
        alert(data.error);
      }
    }
  };

  const handleRenameWorkspace = async (oldName: string) => {
    const newName = prompt(`Rename workspace "${oldName}" to:`, oldName);
    if (newName && newName !== oldName) {
      const response = await fetch('/api/workspace/rename', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ old_name: oldName, new_name: newName }),
      });
      const data = await response.json();
      if (data.success) {
        await loadWorkspaces();
      } else {
        alert(data.error);
      }
    }
  };

  const scrollToTask = (id: number) => {
    const element = document.querySelector(`[data-task-id="${id}"]`) as HTMLElement;
    if (!element) return;

    const correctFinalPosition = () => {
      const current = document.querySelector(`[data-task-id="${id}"]`) as HTMLElement;
      if (!current) return;

      const desiredTop = getStickyOffset();
      const actualTop = current.getBoundingClientRect().top;
      const delta = actualTop - desiredTop;

      if (Math.abs(delta) > 2) {
        window.scrollBy({ top: delta, behavior: 'auto' });
      }
    };

    element.style.scrollMarginTop = `${getStickyOffset()}px`;

    // Correct only after the browser reports the smooth scroll has ended, so
    // the correction cannot race the animation. The timeout is a fallback for
    // browsers that do not reliably emit scrollend.
    window.addEventListener('scrollend', correctFinalPosition, { once: true });
    window.setTimeout(correctFinalPosition, 900);

    element.scrollIntoView({
      behavior: 'smooth',
      block: 'start'
    });
  };

  const findTaskById = (tasks: Task[], id: number): Task | null => {
    for (const task of tasks) {
      if (task.id === id) return task;
      if (task.children.length > 0) {
        const found = findTaskById(task.children, id);
        if (found) return found;
      }
    }
    return null;
  };

  useEffect(() => {
    if (!currentWorkspace) return;
    const saved = localStorage.getItem('taskmcp.focusedTaskId:' + currentWorkspace);
    const parsed = saved ? Number(saved) : NaN;
    setFocusedTaskId(Number.isFinite(parsed) ? parsed : null);
  }, [currentWorkspace]);

  useEffect(() => {
    if (!currentWorkspace) return;
    const key = 'taskmcp.focusedTaskId:' + currentWorkspace;
    if (focusedTaskId === null) {
      localStorage.removeItem(key);
    } else {
      localStorage.setItem(key, String(focusedTaskId));
    }
  }, [currentWorkspace, focusedTaskId]);

  useEffect(() => {
    if (!currentWorkspace || focusedTaskId === null || tasks.length === 0) return;
    if (!findTaskById(tasks, focusedTaskId)) {
      setFocusedTaskId(null);
    }
  }, [currentWorkspace, focusedTaskId, tasks]);

  useEffect(() => {
    if (!currentWorkspace) return;
    const saved = localStorage.getItem('taskmcp.taskFilter:' + currentWorkspace);
    setHideCompleted(saved === 'open');
  }, [currentWorkspace]);

  const setTaskFilterPreference = (open: boolean) => {
    setHideCompleted(open);
    if (!currentWorkspace) return;
    localStorage.setItem('taskmcp.taskFilter:' + currentWorkspace, open ? 'open' : 'all');
  };

  const handleFocusTask = (id: number) => {
    setFocusedTaskId(id);
  };

  const handleUnfocus = () => {
    setFocusedTaskId(null);
  };

  const getScopedTasks = (): Task[] => {
    if (focusedTaskId === null) return tasks;
    const focusedTask = findTaskById(tasks, focusedTaskId);
    return focusedTask ? [focusedTask] : tasks;
  };

  const filterOpen = (nodes: Task[]): Task[] => nodes.flatMap(task => {
    const children = filterOpen(task.children);
    return !task.done || children.length > 0 || task.id === focusedTaskId
      ? [{ ...task, children }]
      : [];
  });

  const countTasks = (nodes: Task[]): { all: number; open: number } =>
    nodes.reduce((count, task) => {
      const child = countTasks(task.children);
      return { all: count.all + 1 + child.all, open: count.open + (task.done ? 0 : 1) + child.open };
    }, { all: 0, open: 0 });

  const scopedTasks = getScopedTasks();
  const visibleTasks = hideCompleted ? filterOpen(scopedTasks) : scopedTasks;
  const taskCounts = countTasks(scopedTasks);
  const allTaskCounts = countTasks(tasks);
  const hiddenTaskCount = focusedTaskId !== null
    ? Math.max(0, allTaskCounts.all - countTasks(scopedTasks).all)
    : 0;

  return (
    <>
      <style>{`
        @keyframes toastFadeIn {
          from {
            opacity: 0;
            transform: translate(-50%, -10px);
          }
          to {
            opacity: 1;
            transform: translate(-50%, 0);
          }
        }
        @keyframes toastFadeOut {
          from {
            opacity: 1;
            transform: translate(-50%, 0);
          }
          to {
            opacity: 0;
            transform: translate(-50%, -10px);
          }
        }
      `}</style>
      {showToast && (
        <div
          style={{
            position: 'fixed',
            top: `${toastTopOffset}px`,
            left: '50%',
            transform: 'translate(-50%, 0)',
            zIndex: 10000,
            background: 'var(--bg-secondary)',
            color: 'var(--text-primary)',
            padding: '12px 24px',
            borderRadius: '8px',
            boxShadow: '0 4px 12px var(--shadow-elevated)',
            border: '1px solid var(--border-primary)',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            fontSize: 'var(--font-size-base)',
            fontWeight: '500',
            opacity: 0,
            animation: toastFadingOut ? 'toastFadeOut 0.3s ease-out forwards' : 'toastFadeIn 0.3s ease-out forwards',
            maxWidth: '90%',
            wordBreak: 'break-word'
          }}
        >
          <span>✓</span>
          <span>{toastMessage}</span>
        </div>
      )}
      <a href="#main-content" className="skip-link">Skip to main content</a>
      <div style={{ display: 'flex', gap: '20px', minHeight: '100vh', position: 'relative' }}>
          {isMobile && (
            <button
              onClick={() => setShowOutliner(!showOutliner)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  setShowOutliner(!showOutliner);
                }
              }}
              className="theme-toggle"
              aria-label={showOutliner ? "Hide outline" : "Show outline"}
              aria-expanded={showOutliner}
              style={{
                position: 'fixed',
                left: showOutliner ? '270px' : '10px',
                top: `${stickyOffset}px`,
                zIndex: 1001,
                transition: 'left 0.3s ease',
                boxShadow: '0 2px 4px var(--shadow)'
              }}
              title={showOutliner ? "Hide outline" : "Show outline"}
            >
              {showOutliner ? '◀' : '☰'}
            </button>
          )}
          {isMobile && showOutliner && (
            <div
              onClick={() => setShowOutliner(false)}
              onKeyDown={(e) => {
                if (e.key === 'Escape') {
                  setShowOutliner(false);
                }
              }}
              style={{
                position: 'fixed',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                background: 'rgba(0, 0, 0, 0.5)',
                zIndex: 999,
                transition: 'opacity 0.3s ease',
                overscrollBehavior: 'contain'
              }}
              aria-label="Close outline"
              role="button"
              tabIndex={0}
            />
          )}
          <div
            style={{
              display: showOutliner || !isMobile ? 'block' : 'none',
              position: isMobile ? 'fixed' : 'relative',
              left: isMobile ? (showOutliner ? '0' : '-100%') : 'auto',
              top: isMobile ? '0' : 'auto',
              height: isMobile ? '100vh' : 'auto',
              zIndex: isMobile ? 1000 : 'auto',
              background: isMobile ? 'var(--bg-primary)' : 'transparent',
              transition: isMobile ? 'left 0.3s ease' : 'none',
              overflowY: isMobile ? 'auto' : 'visible',
              width: isMobile ? '250px' : 'auto',
              padding: isMobile ? '20px 0 0 0' : '0',
              overscrollBehavior: isMobile ? 'contain' : 'auto'
            }}
          >
            <Outliner
              tasks={visibleTasks}
              onScrollToTask={scrollToTask}
              findCurrentTask={findCurrentTask}
              collapsedTaskIds={collapsedTaskIds}
              onToggleCollapse={(id: number) => {
                setCollapsedTaskIds(prev => {
                  const next = new Set(prev);
                  if (next.has(id)) {
                    next.delete(id);
                  } else {
                    next.add(id);
                  }
                  return next;
                });
              }}
            />
          </div>
          <div id="main-content" style={{ flex: 1, minWidth: 0, maxWidth: 'none' }}>
          <div style={{
            display: isMobile ? 'block' : 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: focusedTaskId !== null ? '6px' : '10px',
            gap: focusedTaskId !== null ? '6px' : '10px',
            position: 'relative',
            zIndex: 101,
            opacity: focusedTaskId !== null ? 0.72 : 1
          }}>
            {focusedTaskId === null && (
              <h1 style={{
                textWrap: 'balance',
                marginBottom: isMobile ? '10px' : '0',
                textAlign: isMobile ? 'center' : 'left'
              }}>Task List</h1>
            )}
            <div style={{ display: 'flex', gap: focusedTaskId !== null ? '6px' : '10px', alignItems: 'center', width: isMobile ? '100%' : 'auto', flexShrink: 0, marginLeft: focusedTaskId !== null ? 'auto' : undefined }}>
              {focusedTaskId !== null && !showFocusAdd && (
                <button
                  type="button"
                  className="btn-comments"
                  onClick={() => setShowFocusAdd(true)}
                  aria-label="Add task"
                  title="Add task"
                  style={{ padding: '4px 8px', minHeight: '32px', color: 'var(--text-secondary)' }}
                >
                  ＋ Add task
                </button>
              )}
              <button
                onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    setTheme(theme === 'light' ? 'dark' : 'light');
                  }
                }}
                className="theme-toggle"
                aria-label={theme === 'light' ? 'Switch to dark theme' : 'Switch to light theme'}
                title={theme === 'light' ? 'Switch to dark theme' : 'Switch to light theme'}
                style={{ flexShrink: 0 }}
              >
                {theme === 'light' ? '🌙' : '☀️'}
              </button>
              <select
                className="workspace-select"
                value={currentWorkspace}
                onChange={(e) => handleSwitchWorkspace(e.target.value)}
                aria-label="Select workspace"
                style={{
                  flex: '1 1 0',
                  minWidth: 0
                }}
              >
                {workspaces.map(ws => (
                  <option key={ws} value={ws}>{ws}</option>
                ))}
              </select>
              <button
                onClick={() => setShowWorkspaceManager(!showWorkspaceManager)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    setShowWorkspaceManager(!showWorkspaceManager);
                  }
                }}
                className="theme-toggle"
                aria-label="Manage workspaces"
                aria-expanded={showWorkspaceManager}
                style={{ flexShrink: 0, whiteSpace: 'nowrap', opacity: focusedTaskId !== null ? 0.8 : 1 }}
              >
                ⚙️ {showManageText && ' Manage'}
              </button>
            </div>
          </div>

          {showWorkspaceManager && (
            <div style={{
              background: 'var(--bg-tertiary)',
              border: '1px solid var(--border-primary)',
              borderRadius: '8px',
              padding: '15px',
              marginBottom: '20px'
            }}>
              <h3>Workspace Manager</h3>

              <div style={{ marginBottom: '15px' }}>
                <div style={{ display: 'flex', gap: '8px', marginBottom: '10px' }}>
                  <label htmlFor="new-workspace-input" className="sr-only">New workspace name</label>
                  <input
                    id="new-workspace-input"
                    type="text"
                    name="workspace"
                    placeholder="New workspace name."
                    value={newWorkspaceName}
                    onChange={(e) => setNewWorkspaceName(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleCreateWorkspace()}
                    autoComplete="off"
                    aria-label="New workspace name"
                    className="workspace-select"
                    style={{
                      flex: 1,
                      minWidth: 0
                    }}
                  />
                  <button
                    onClick={handleCreateWorkspace}
                    className="btn btn-add"
                    aria-label="Create workspace"
                    style={{ minHeight: 'var(--control-height)', minWidth: 'var(--control-height)' }}
                  >
                    ➕ Create
                  </button>
                </div>
              </div>

              <div>
                <h4>All Workspaces:</h4>
                <ul style={{ listStyle: 'none', padding: 0 }}>
                  {workspaces.map(ws => (
                    <li key={ws} style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '8px',
                      background: ws === currentWorkspace ? 'var(--bg-current)' : 'var(--bg-secondary)',
                      marginBottom: '4px',
                      borderRadius: '8px'
                    }}>
                      <span style={{ fontWeight: ws === currentWorkspace ? 'bold' : 'normal' }}>
                        {ws} {ws === currentWorkspace && '(current)'}
                      </span>
                      <div style={{ display: 'flex', gap: '8px' }}>
                        {ws !== currentWorkspace && (
                          <button
                            onClick={() => handleSwitchWorkspace(ws)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter' || e.key === ' ') {
                                e.preventDefault();
                                handleSwitchWorkspace(ws);
                              }
                            }}
                            className="workspace-btn"
                            aria-label={`Switch to workspace ${ws}`}
                          >
                            Switch
                          </button>
                        )}
                        <button
                          onClick={() => handleRenameWorkspace(ws)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' || e.key === ' ') {
                              e.preventDefault();
                              handleRenameWorkspace(ws);
                            }
                          }}
                          className="workspace-btn"
                          aria-label={`Rename workspace ${ws}`}
                        >
                          Rename
                        </button>
                        {ws !== currentWorkspace && (
                          <button
                            onClick={() => handleDeleteWorkspace(ws)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter' || e.key === ' ') {
                                e.preventDefault();
                                handleDeleteWorkspace(ws);
                              }
                            }}
                            className="workspace-btn workspace-btn-delete"
                            aria-label={`Delete workspace ${ws}`}
                          >
                            Delete
                          </button>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          {(focusedTaskId === null || showFocusAdd) && (
            <div className="add-form" style={{ flexDirection: isMobile ? 'column' : 'row', marginBottom: focusedTaskId !== null ? '6px' : undefined }}>
              <label htmlFor="new-task-input" className="sr-only">Add a new task</label>
              <input
                id="new-task-input"
                type="text"
                name="task"
                placeholder="Add a new task."
                value={newTask}
                onChange={(e) => setNewTask(e.target.value)}
                onKeyDown={handleKeyDown}
                onFocus={() => {
                  if (blurTimeoutRef.current) {
                    clearTimeout(blurTimeoutRef.current);
                    blurTimeoutRef.current = null;
                  }
                  setIsTaskInputFocused(true);
                }}
                onBlur={(e) => {
                  blurTimeoutRef.current = setTimeout(() => {
                    const relatedTarget = e.relatedTarget as HTMLElement;
                    if (!relatedTarget || !relatedTarget.closest('.add-form button')) {
                      setIsTaskInputFocused(false);
                      if (focusedTaskId !== null && !newTask.trim()) setShowFocusAdd(false);
                    }
                  }, 150);
                }}
                autoComplete="off"
                aria-label="New task input"
                style={{ width: isMobile ? '100%' : 'auto' }}
              />
              {isMobile && isTaskInputFocused && (
                <div style={{ display: 'flex', gap: '10px', width: '100%' }}>
                  <button
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => {
                      setNewTask('');
                      const input = document.getElementById('new-task-input') as HTMLInputElement;
                      if (input) input.focus();
                    }}
                    className="btn-clear"
                    aria-label="Clear input"
                    style={{ flex: 1 }}
                  >
                    ❌ Clear
                  </button>
                  <button onMouseDown={(e) => e.preventDefault()} onClick={handleAdd} aria-label="Add task" style={{ flex: 1, width: 'auto' }}>
                    ➕ Add
                  </button>
                </div>
              )}
              {!isMobile && <button onClick={handleAdd} aria-label="Add task">➕ Add</button>}
            </div>
          )}

          <ListView
            tasks={visibleTasks}
            onToggle={handleToggle}
            onEdit={handleEdit}
            onDelete={handleDelete}
            onAddChild={handleAddChild}
            onReorder={handleReorder}
            onSetCurrent={handleSetCurrent}
            onFocusTask={handleFocusTask}
            findCurrentTask={findCurrentTask}
            scrollToCurrentTask={scrollToCurrentTask}
            focusedTaskId={focusedTaskId}
            handleUnfocus={handleUnfocus}
            findTaskById={findTaskById}
            collapsedTaskIds={collapsedTaskIds}
            onFoldCompleted={handleFoldCompleted}
            hideCompleted={hideCompleted}
            onSetHideCompleted={setTaskFilterPreference}
            taskCounts={taskCounts}
            currentTask={findCurrentTask(tasks)}
            hiddenTaskCount={hiddenTaskCount}
            onToggleCollapse={(id: number) => {
              setCollapsedTaskIds(prev => {
                const next = new Set(prev);
                if (next.has(id)) {
                  next.delete(id);
                } else {
                  next.add(id);
                }
                return next;
              });
            }}
          />
          </div>
    </div>
    </>
  );
}

const root = ReactDOM.createRoot(document.getElementById('app')!);
root.render(<App />);
