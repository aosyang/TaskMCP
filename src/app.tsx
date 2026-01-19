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
  const [showOutliner, setShowOutliner] = useState(true);
  const [isMobile, setIsMobile] = useState(false);
  const [stickyOffset, setStickyOffset] = useState(10);
  const [showManageText, setShowManageText] = useState(true);

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
      await fetch('/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task: newTask.trim(), parent_id: null }),
      });
      setNewTask('');
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

  const handleDelete = async (id: number) => {
    if (confirm('Delete this task and all its subtasks?')) {
      await fetch(`/delete/${id}`);
    }
  };

  const handleAddChild = async (parentId: number, task: string) => {
    await fetch('/add', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task, parent_id: parentId }),
    });
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
    // Calculate the total height of sticky divs (Comments + Focus Mode if exists)
    let offset = 0;
    
    // Find Comments div by searching for the div containing "Comments:" text
    const mainContent = document.querySelector('#main-content');
    if (mainContent) {
      const allDivs = mainContent.querySelectorAll('div');
      for (const div of allDivs) {
        const style = window.getComputedStyle(div);
        if (style.position === 'sticky' && div.textContent?.includes('Comments:')) {
          offset += div.getBoundingClientRect().height;
          break;
        }
      }
      
      // Find Focus Mode div by searching for the div containing "Focus Mode" text
      if (focusedTaskId !== null) {
        for (const div of allDivs) {
          const style = window.getComputedStyle(div);
          if (style.position === 'sticky' && div.textContent?.includes('Focus Mode')) {
            offset += div.getBoundingClientRect().height;
            break;
          }
        }
      }
    }
    
    return offset + 10; // Add 10px extra padding
  };

  // Update sticky offset for button positioning
  useEffect(() => {
    const updateStickyOffset = () => {
      const mainContent = document.querySelector('#main-content');
      if (mainContent) {
        let maxBottom = 0;
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
          }
        }
        
        // Set offset to the bottom of the lowest stuck sticky element + padding
        // If no sticky elements are stuck, use default 10px
        if (maxBottom > 0) {
          setStickyOffset(maxBottom + 10); // Add 10px padding
        } else {
          setStickyOffset(10);
        }
      } else {
        setStickyOffset(10);
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
    if (currentTask) {
      const element = document.querySelector(`[data-task-id="${currentTask.id}"]`) as HTMLElement;
      if (element) {
        const offset = getStickyOffset();
        const elementTop = element.getBoundingClientRect().top + window.pageYOffset;
        const offsetPosition = elementTop - offset;
        
        window.scrollTo({
          top: offsetPosition,
          behavior: 'smooth'
        });
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleAdd();
    }
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
    if (element) {
      const offset = getStickyOffset();
      const elementTop = element.getBoundingClientRect().top + window.pageYOffset;
      const offsetPosition = elementTop - offset;
      
      window.scrollTo({
        top: offsetPosition,
        behavior: 'smooth'
      });
    }
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

  const handleFocusTask = (id: number) => {
    setFocusedTaskId(id);
  };

  const handleUnfocus = () => {
    setFocusedTaskId(null);
  };

  const getFilteredTasks = (): Task[] => {
    if (focusedTaskId === null) return tasks;
    const focusedTask = findTaskById(tasks, focusedTaskId);
    return focusedTask ? [focusedTask] : tasks;
  };

  return (
    <>
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
              aria-label={showOutliner ? "Hide outline" : "Show outline"}
              aria-expanded={showOutliner}
              style={{
                position: 'fixed',
                left: showOutliner ? '270px' : '10px',
                top: `${stickyOffset}px`,
                zIndex: 1001,
                padding: '8px 12px',
                fontSize: '14px',
                background: 'var(--bg-secondary)',
                color: 'var(--text-primary)',
                border: '1px solid var(--border-primary)',
                borderRadius: '4px',
                cursor: 'pointer',
                boxShadow: '0 2px 4px var(--shadow)',
                minHeight: '44px',
                minWidth: '44px',
                transition: 'left 0.3s ease',
                touchAction: 'manipulation'
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
              tasks={getFilteredTasks()} 
              onScrollToTask={scrollToTask} 
              findCurrentTask={findCurrentTask}
            />
          </div>
          <div id="main-content" style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: isMobile ? 'block' : 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px', gap: '10px' }}>
            <h1 style={{ textWrap: 'balance', marginBottom: isMobile ? '10px' : '0' }}>📝 Task List</h1>
            <div style={{ display: 'flex', gap: '10px', alignItems: 'center', width: isMobile ? '100%' : 'auto', flexShrink: 0 }}>
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
                value={currentWorkspace} 
                onChange={(e) => handleSwitchWorkspace(e.target.value)}
                aria-label="Select workspace"
                style={{
                  padding: '8px 12px',
                  fontSize: '14px',
                  borderRadius: '4px',
                  border: '1px solid var(--border-primary)',
                  background: 'var(--bg-secondary)',
                  color: 'var(--text-primary)',
                  cursor: 'pointer',
                  minHeight: '44px',
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
                aria-label="Manage workspaces"
                aria-expanded={showWorkspaceManager}
                style={{
                  padding: '8px 12px',
                  fontSize: '14px',
                  cursor: 'pointer',
                  background: 'var(--bg-tertiary)',
                  border: '1px solid var(--border-primary)',
                  borderRadius: '4px',
                  color: 'var(--text-primary)',
                  minHeight: '44px',
                  minWidth: '44px',
                  flexShrink: 0,
                  whiteSpace: 'nowrap'
                }}
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
                    style={{ 
                      flex: 1, 
                      padding: '8px', 
                      fontSize: '16px',
                      background: 'var(--bg-secondary)',
                      color: 'var(--text-primary)',
                      border: '1px solid var(--border-primary)',
                      borderRadius: '4px',
                      minHeight: '44px'
                    }}
                  />
                  <button 
                    onClick={handleCreateWorkspace} 
                    className="btn btn-add" 
                    aria-label="Create workspace"
                    style={{ padding: '8px 16px', minHeight: '44px', minWidth: '44px' }}
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
                      borderRadius: '4px'
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
                            style={{ padding: '4px 8px', fontSize: '12px', minHeight: '24px', minWidth: '24px' }}
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
                          style={{ padding: '4px 8px', fontSize: '12px', minHeight: '24px', minWidth: '24px' }}
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
                            style={{ 
                              padding: '4px 8px', 
                              fontSize: '12px',
                              minHeight: '24px',
                              minWidth: '24px'
                            }}
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

          <div className="add-form">
            <label htmlFor="new-task-input" className="sr-only">Add a new task</label>
            <input
              id="new-task-input"
              type="text"
              name="task"
              placeholder="Add a new task."
              value={newTask}
              onChange={(e) => setNewTask(e.target.value)}
              onKeyDown={handleKeyDown}
              autoComplete="off"
              aria-label="New task input"
            />
            <button 
              onClick={handleAdd}
              aria-label="Add task"
            >
              ➕ Add
            </button>
          </div>

          <ListView
            tasks={getFilteredTasks()}
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
          />
          </div>
    </div>
    </>
  );
}

const root = ReactDOM.createRoot(document.getElementById('app')!);
root.render(<App />);
