# Todo App - Implementation

## Stack
- Backend: Flask + SQLite3 + Flask-SocketIO
- MCP Server: FastMCP
- Frontend: React 18 + TypeScript + @dnd-kit/sortable
- Build: esbuild with custom plugin for React CDN mapping
- Real-time: Socket.IO for WebSocket communication

## Database Schema
```sql
-- Multiple workspace databases in workspaces/ directory
-- Each workspace has independent todos and current_task tables

todos (
  id, task, done, parent_id, position, 
  comments, color, 
  board_x, board_y, board_width, board_height,
  children_layout, children_comment_display
)

current_task (id, task_id)
```

## Workspace System
- **Multi-database architecture**: Each workspace = one SQLite file
- **Workspace directory**: `workspaces/`
- **Current workspace config**: `workspace_config.json`
- **Default workspace**: `default`
- **Auto-creation**: Switching to non-existent workspace creates it
- **Migration tool**: `migrate_to_workspace.py` for old data

## Key Features
- ✅ Multi-workspace support with independent databases
- ✅ CRUD operations on todos
- ✅ Hierarchical subtasks (recursive)
- ✅ Inline editing (double-click)
- ✅ Drag-and-drop reordering with @dnd-kit
- ✅ Toggle done status (checkbox + button)
- ✅ Visual drag handles (⋮⋮)
- ✅ Emoji-based UI buttons for compact interface
- ✅ Confirmation dialog for delete
- ✅ Comments/notes with Markdown support
- ✅ Color coding for tasks
- ✅ Two view modes: List View and Canvas View
- ✅ Real-time synchronization via WebSocket
- ✅ MCP server for AI agent integration
- ✅ Current task tracking

## Backend Routes

### Todo Management
- `/` - Serve HTML
- `/api/todos` - GET todos as JSON tree
- `/add` - POST new todo
- `/edit/<id>` - POST update task/comments/color
- `/toggle/<id>` - GET toggle done
- `/delete/<id>` - GET remove todo (recursive)
- `/reorder` - POST batch update positions
- `/update_board_position` - POST update canvas positions
- `/update_children_layout/<id>` - POST set layout (vertical/horizontal)
- `/update_children_comment_display/<id>` - POST set display mode
- `/set_current/<id>` - POST set current working task
- `/clear_current` - POST clear current task
- `/api/current_task` - GET current task
- `/api/notify_update` - POST trigger WebSocket broadcast

### Workspace Management
- `/api/workspaces` - GET list all workspaces and current
- `/api/workspace/current` - GET current workspace
- `/api/workspace/switch` - POST switch workspace
- `/api/workspace/create` - POST create new workspace
- `/api/workspace/delete` - POST delete workspace
- `/api/workspace/rename` - POST rename workspace

## Frontend Architecture
- React app renders to `#app` div
- TodoItem component renders recursively
- @dnd-kit for drag-and-drop functionality
- DndContext wraps sortable lists at each level
- SortableContext manages draggable items
- State updates via fetch + reload
- React loaded from CDN (unpkg.com)

## UI Elements
- 📝 App title
- ➕ Add todo / Add subtask
- ✅ Mark as done
- ↩️ Mark as undone
- 🗑️ Delete
- ⋮⋮ Drag handle
- ✓ Confirm
- ✕ Cancel

## Build Steps
```bash
npm install
npm run build    # TypeScript + React → static/app.js using custom esbuild plugin
python app.py
```

Open http://localhost:5000

## Files
- `app.py` - Flask server with SQLite CRUD operations
- `src/app.tsx` - React app + TodoItem component with drag-and-drop
- `templates/index.html` - Base template with React CDN links and styled UI
- `todos.db` - SQLite database (auto-created)
- `package.json` - Dependencies (@dnd-kit, React, TypeScript, esbuild)
- `tsconfig.json` - TypeScript config with JSX support
- `build.js` - Custom esbuild script with plugin to map React imports to window globals
- `static/app.js` - Compiled bundle (generated)
