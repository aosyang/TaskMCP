import os
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from notify import notify_tasks_updated, notify_workspace_changed
from workspace_manager import (
    get_current_workspace,
    set_current_workspace as set_workspace,
    list_workspaces,
    get_workspace_db_path,
    delete_workspace_db,
    validate_workspace_name,
    init_db,
    get_db
)

# Initialize FastMCP server
# Note: FastMCP should handle type coercion by default, but Cursor's MCP client
# may serialize integers as strings. The function implementations include
# string-to-int conversion as a fallback.
mcp = FastMCP(
    "Task Manager",
    version="2.0",
    instructions=(
        "Task management server with multiple workspaces. "
        "All task operations are scoped to the current workspace unless explicitly stated otherwise. "
        "When the target workspace is uncertain, inspect the current workspace before mutating tasks. "
        "Use search_tasks when a task ID is unknown. Prefer set_task_status over toggle_task. "
        "switch_workspace never creates a missing workspace; use create_workspace explicitly."
    ),
)

def set_current_workspace(workspace_name):
    """Set current workspace and notify without implicitly creating it."""
    set_workspace(workspace_name)
    notify_workspace_changed(workspace_name)

def _task_to_dict(task):
    if task is None:
        return None
    return {
        "id": int(task["id"]),
        "task": task["task"],
        "done": bool(task["done"]),
        "parent_id": task["parent_id"],
        "position": int(task["position"]),
        "comments": task["comments"] or "",
    }


def _get_task_record(task_id: int):
    task_id = int(task_id)
    conn = get_db()
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    if row is None:
        raise ToolError(f"TASK_NOT_FOUND: Task #{task_id} does not exist in the current workspace")
    return _task_to_dict(row)


# Workspace management tools
@mcp.tool(
    description="Return the current active workspace. Read-only; use this before mutations when the target workspace is uncertain.",
    annotations={"readOnlyHint": True, "openWorldHint": False},
)
def get_current_workspace_name() -> dict:
    return {"workspace": get_current_workspace()}

@mcp.tool(
    description="List all available workspaces with task counts and identify the current workspace. Read-only.",
    annotations={"readOnlyHint": True, "openWorldHint": False},
)
def list_all_workspaces() -> dict:
    workspaces = []
    current = get_current_workspace()
    for name in list_workspaces():
        try:
            conn = get_db(name)
            count = int(conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0])
            conn.close()
        except Exception:
            count = 0
        workspaces.append({"name": name, "task_count": count, "current": name == current})
    return {"current_workspace": current, "workspaces": workspaces}

@mcp.tool(
    description="Switch to an existing workspace. This never creates a workspace; call create_workspace explicitly when needed.",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
def switch_workspace(workspace_name: str) -> dict:
    if not validate_workspace_name(workspace_name):
        raise ToolError("INVALID_WORKSPACE_NAME: Use only letters, numbers, underscore, and hyphen")
    db_path = get_workspace_db_path(workspace_name)
    if not os.path.exists(db_path):
        raise ToolError(f"WORKSPACE_NOT_FOUND: Workspace '{workspace_name}' does not exist")
    set_current_workspace(workspace_name)
    notify_tasks_updated()
    return {"workspace": workspace_name, "switched": True}

@mcp.tool(
    description="Create a new workspace without switching to it.",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
)
def create_workspace(workspace_name: str) -> dict:
    if not validate_workspace_name(workspace_name):
        raise ToolError("INVALID_WORKSPACE_NAME: Use only letters, numbers, underscore, and hyphen")
    db_path = get_workspace_db_path(workspace_name)
    if os.path.exists(db_path):
        raise ToolError(f"WORKSPACE_ALREADY_EXISTS: Workspace '{workspace_name}' already exists")
    init_db(workspace_name)
    return {"workspace": workspace_name, "created": True, "current": workspace_name == get_current_workspace()}

@mcp.tool(
    description="Delete a non-current workspace database. Destructive operation. A freshly modified Dropbox-synced database may briefly report WORKSPACE_DELETE_BUSY; retry the same call later.",
    annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": False},
)
def delete_workspace(workspace_name: str) -> dict:
    current = get_current_workspace()
    if workspace_name == current:
        raise ToolError(f"CURRENT_WORKSPACE_DELETE_FORBIDDEN: Switch away from '{workspace_name}' first")
    db_path = get_workspace_db_path(workspace_name)
    if not os.path.exists(db_path):
        raise ToolError(f"WORKSPACE_NOT_FOUND: Workspace '{workspace_name}' does not exist")
    try:
        delete_workspace_db(workspace_name)
    except PermissionError as exc:
        raise ToolError(
            f"WORKSPACE_DELETE_BUSY: Workspace '{workspace_name}' is temporarily locked by another process; retry this deletion shortly"
        ) from exc
    return {"workspace": workspace_name, "deleted": True}

@mcp.tool(
    description="Rename an existing workspace. If it is current, the current-workspace pointer is updated.",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
)
def rename_workspace(old_name: str, new_name: str) -> dict:
    if not validate_workspace_name(new_name):
        raise ToolError("INVALID_WORKSPACE_NAME: Use only letters, numbers, underscore, and hyphen")
    old_path = get_workspace_db_path(old_name)
    new_path = get_workspace_db_path(new_name)
    if not os.path.exists(old_path):
        raise ToolError(f"WORKSPACE_NOT_FOUND: Workspace '{old_name}' does not exist")
    if os.path.exists(new_path):
        raise ToolError(f"WORKSPACE_ALREADY_EXISTS: Workspace '{new_name}' already exists")
    os.rename(old_path, new_path)
    was_current = old_name == get_current_workspace()
    if was_current:
        set_current_workspace(new_name)
    notify_tasks_updated()
    return {"old_name": old_name, "new_name": new_name, "renamed": True, "current": was_current}

# Task management tools
@mcp.tool(
    description="List canonical task records in the current workspace. Read-only. Each record includes ID, status, parent, position, and comments.",
    annotations={"readOnlyHint": True, "openWorldHint": False},
)
def list_tasks() -> dict:
    workspace = get_current_workspace()
    conn = get_db()
    rows = conn.execute("SELECT * FROM tasks ORDER BY parent_id, position, id").fetchall()
    current = conn.execute("SELECT task_id FROM current_task WHERE id = 1").fetchone()
    conn.close()
    tasks = [_task_to_dict(row) for row in rows]
    return {
        "workspace": workspace,
        "count": len(tasks),
        "current_task_id": current["task_id"] if current else None,
        "tasks": tasks,
    }

def _add_task_impl(task: str, parent_id: int | None) -> dict:
    if not task or not task.strip():
        raise ToolError("INVALID_ARGUMENT: task must be non-empty")
    if parent_id is not None:
        parent_id = int(parent_id)
    conn = get_db()
    cursor = conn.cursor()
    if parent_id is not None:
        cursor.execute("SELECT id FROM tasks WHERE id = ?", (parent_id,))
        if cursor.fetchone() is None:
            conn.close()
            raise ToolError(f"PARENT_TASK_NOT_FOUND: Parent task #{parent_id} does not exist")
    cursor.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM tasks WHERE parent_id IS ?", (parent_id,))
    position = int(cursor.fetchone()[0])
    cursor.execute(
        "INSERT INTO tasks (task, done, parent_id, position, comments) VALUES (?, 0, ?, ?, '')",
        (task, parent_id, position),
    )
    task_id = int(cursor.lastrowid)
    conn.commit()
    row = cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    notify_tasks_updated()
    return {"workspace": get_current_workspace(), "task": _task_to_dict(row), "created": True}

@mcp.tool(
    description="Create a task in the current workspace. Omit parent_id for a top-level task; provide an existing task ID to create a subtask.",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
)
def add_task(task: str, parent_id: int | None = None) -> dict:
    return _add_task_impl(task, parent_id)

@mcp.tool(
    description="Compatibility alias for add_task(task, parent_id). Prefer add_task for new clients.",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
)
def add_task_with_parent(task: str, parent_id: int) -> dict:
    return _add_task_impl(task, parent_id)

@mcp.tool(
    description="Update the description and/or Markdown comments of an existing task, then return the canonical updated task record.",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
def update_task(task_id: int, task: str | None = None, comments: str | None = None) -> dict:
    task_id = int(task_id)
    if task is None and comments is None:
        raise ToolError("INVALID_ARGUMENT: provide task and/or comments")
    conn = get_db()
    cursor = conn.cursor()
    if cursor.execute("SELECT id FROM tasks WHERE id = ?", (task_id,)).fetchone() is None:
        conn.close()
        raise ToolError(f"TASK_NOT_FOUND: Task #{task_id} does not exist")
    updates, params = [], []
    if task is not None:
        updates.append("task = ?")
        params.append(task)
    if comments is not None:
        updates.append("comments = ?")
        params.append(comments)
    params.append(task_id)
    cursor.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    row = cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    notify_tasks_updated()
    return {"workspace": get_current_workspace(), "task": _task_to_dict(row), "updated": True}

@mcp.tool()
def update_task_comments_from_file(task_id: int, file_path: str) -> str:
    """Update a task's comments from a text file
    
    Args:
        task_id: The ID of the task to update
        file_path: Path to the text file containing the comments (supports markdown)
    
    Examples:
        - update_task_comments_from_file(10, "comments.md") - Update task #10's comments from comments.md
        - update_task_comments_from_file(5, "path/to/notes.txt") - Update task #5's comments from notes.txt
    
    IMPORTANT: If using a temporary file, you MUST wait 1 second after calling this function
    before deleting the temporary file. This ensures the file is fully read before deletion.
    Failure to wait may result in update failures due to race conditions.
    """
    # Convert string to int if needed
    task_id = int(task_id) if isinstance(task_id, str) else task_id
    
    # Check if file exists
    if not os.path.exists(file_path):
        return f"Error: File '{file_path}' not found"
    
    # Read file content
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            comments = f.read()
    except Exception as e:
        return f"Error: Failed to read file '{file_path}': {str(e)}"
    
    # Validate task exists
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM tasks WHERE id = ?", (task_id,))
    if cursor.fetchone() is None:
        conn.close()
        return f"Error: Task #{task_id} not found"
    
    # Update task comments
    cursor.execute("UPDATE tasks SET comments = ? WHERE id = ?", (comments, task_id))
    conn.commit()
    conn.close()
    
    notify_tasks_updated()
    return f"Updated task #{task_id} comments from file '{file_path}'"

@mcp.tool(
    description="Compatibility toggle for task completion. Non-idempotent; prefer set_task_status for agent workflows and retries.",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
)
def toggle_task(task_id: int) -> dict:
    task_id = int(task_id)
    conn = get_db()
    cursor = conn.cursor()
    row = cursor.execute("SELECT done FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        conn.close()
        raise ToolError(f"TASK_NOT_FOUND: Task #{task_id} does not exist")
    done = not bool(row["done"])
    cursor.execute("UPDATE tasks SET done = ? WHERE id = ?", (1 if done else 0, task_id))
    conn.commit()
    updated = cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    notify_tasks_updated()
    return {"workspace": get_current_workspace(), "task": _task_to_dict(updated), "updated": True}


@mcp.tool(
    description="Set an existing task's completion state explicitly. Safe to retry with the same arguments.",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
def set_task_status(task_id: int, done: bool) -> dict:
    task_id = int(task_id)
    conn = get_db()
    cursor = conn.cursor()
    if cursor.execute("SELECT id FROM tasks WHERE id = ?", (task_id,)).fetchone() is None:
        conn.close()
        raise ToolError(f"TASK_NOT_FOUND: Task #{task_id} does not exist")
    cursor.execute("UPDATE tasks SET done = ? WHERE id = ?", (1 if done else 0, task_id))
    conn.commit()
    row = cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    notify_tasks_updated()
    return {"workspace": get_current_workspace(), "task": _task_to_dict(row), "updated": True}

@mcp.tool(
    description="Delete a task and all descendants recursively from the current workspace. Destructive operation.",
    annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": False},
)
def delete_task(task_id: int) -> dict:
    task_id = int(task_id)
    conn = get_db()
    cursor = conn.cursor()
    if cursor.execute("SELECT id FROM tasks WHERE id = ?", (task_id,)).fetchone() is None:
        conn.close()
        raise ToolError(f"TASK_NOT_FOUND: Task #{task_id} does not exist")
    deleted_ids = []
    def collect(node_id):
        children = cursor.execute("SELECT id FROM tasks WHERE parent_id = ?", (node_id,)).fetchall()
        for child in children:
            collect(int(child["id"]))
        deleted_ids.append(int(node_id))
    collect(task_id)
    cursor.execute("DELETE FROM current_task WHERE task_id IN (%s)" % ','.join('?' * len(deleted_ids)), deleted_ids)
    cursor.executemany("DELETE FROM tasks WHERE id = ?", [(i,) for i in deleted_ids])
    conn.commit()
    conn.close()
    notify_tasks_updated()
    return {"workspace": get_current_workspace(), "deleted": True, "deleted_ids": deleted_ids, "deleted_count": len(deleted_ids)}

@mcp.tool(
    description="Retrieve one canonical task record by numeric task ID in the current workspace. Read-only.",
    annotations={"readOnlyHint": True, "openWorldHint": False},
)
def get_task(task_id: int) -> dict:
    return {"workspace": get_current_workspace(), "task": _get_task_record(task_id)}

@mcp.tool(
    description="Search task descriptions and comments in the current workspace. Use this when the task ID is unknown. Read-only.",
    annotations={"readOnlyHint": True, "openWorldHint": False},
)
def search_tasks(query: str) -> dict:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE task LIKE ? OR comments LIKE ? ORDER BY position, id",
        (f"%{query}%", f"%{query}%"),
    ).fetchall()
    conn.close()
    tasks = [_task_to_dict(row) for row in rows]
    return {"workspace": get_current_workspace(), "query": query, "count": len(tasks), "tasks": tasks}

@mcp.tool()
def search_tasks_all_workspaces(query: str) -> str:
    """Search tasks across all workspaces
    
    Args:
        query: Search term to find in task description or comments
    
    Returns:
        JSON string containing array of tasks with workspace information.
        Each task object contains: task_id, task (description), workspace_name, done (status), and optionally comments.
    """
    import json
    results = []
    workspaces = list_workspaces()
    
    for workspace_name in workspaces:
        try:
            conn = get_db(workspace_name)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, task, done, comments FROM tasks WHERE task LIKE ? OR comments LIKE ? ORDER BY position",
                (f"%{query}%", f"%{query}%")
            )
            tasks = cursor.fetchall()
            conn.close()
            
            for task in tasks:
                comments = task["comments"] if task["comments"] else ""
                results.append({
                    "task_id": task["id"],
                    "task": task["task"],
                    "workspace_name": workspace_name,
                    "done": bool(task["done"]),
                    "comments": comments
                })
        except Exception as e:
            # Skip workspaces with errors (e.g., corrupted database)
            continue
    
    if not results:
        return json.dumps([])
    
    return json.dumps(results, ensure_ascii=False)

@mcp.tool()
def set_current_task(task_id: int) -> str:
    """Set a task as the current working task
    
    Args:
        task_id: The ID of the task to set as current
    """
    conn = get_db()
    cursor = conn.cursor()
    
    # Check if task exists
    cursor.execute("SELECT task FROM tasks WHERE id = ?", (task_id,))
    task = cursor.fetchone()
    if not task:
        conn.close()
        return f"Error: Task #{task_id} not found"
    
    # Clear existing current task and set new one
    cursor.execute("DELETE FROM current_task WHERE id = 1")
    cursor.execute("INSERT INTO current_task (id, task_id) VALUES (1, ?)", (task_id,))
    conn.commit()
    conn.close()
    
    notify_tasks_updated()
    return f"Set task #{task_id} as current task: {task['task']}"

@mcp.tool()
def clear_current_task() -> str:
    """Clear the current working task"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM current_task WHERE id = 1")
    conn.commit()
    conn.close()
    
    notify_tasks_updated()
    return "Cleared current task"

@mcp.tool()
def get_current_task() -> str:
    """Get the current working task"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT task_id FROM current_task WHERE id = 1")
    current = cursor.fetchone()
    
    if not current:
        conn.close()
        return "No current task set"
    
    task_id = current["task_id"]
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    task = cursor.fetchone()
    conn.close()
    
    if not task:
        return f"Current task #{task_id} not found (may have been deleted)"
    
    status = "[x] Done" if task["done"] else "[ ] Incomplete"
    parent = f"(subtask of #{task['parent_id']})" if task["parent_id"] else "(top-level)"
    comments = f"\nComments (markdown): {task['comments']}" if task["comments"] else ""
    
    return f"Current Task: #{task['id']} {parent}\nStatus: {status}\nTask: {task['task']}{comments}"

# Helper functions for task movement operations
def _convert_to_int(value):
    """Convert string to int if needed (FastMCP may serialize ints as strings)"""
    return int(value) if isinstance(value, str) else value

def _get_task_info(cursor, task_id):
    """Get task information and validate it exists"""
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    task = cursor.fetchone()
    if not task:
        return None
    return task

def _shift_positions_for_move(cursor, old_parent_id, old_position, new_parent_id, new_position):
    """Shift positions when moving a task within same parent or to different parent"""
    if old_parent_id == new_parent_id:
        # Moving within same parent
        if new_position > old_position:
            # Moving down: shift items between old and new position up
            cursor.execute(
                "UPDATE tasks SET position = position - 1 WHERE parent_id IS ? AND position > ? AND position <= ?",
                (old_parent_id, old_position, new_position)
            )
            new_position -= 1  # Adjust for the gap we just closed
        elif new_position < old_position:
            # Moving up: shift items between new and old position down
            cursor.execute(
                "UPDATE tasks SET position = position + 1 WHERE parent_id IS ? AND position >= ? AND position < ?",
                (old_parent_id, new_position, old_position)
            )
    else:
        # Moving to different parent
        # Close gap in old parent
        cursor.execute(
            "UPDATE tasks SET position = position - 1 WHERE parent_id IS ? AND position > ?",
            (old_parent_id, old_position)
        )
        # Make space in new parent
        cursor.execute(
            "UPDATE tasks SET position = position + 1 WHERE parent_id IS ? AND position >= ?",
            (new_parent_id, new_position)
        )
    return new_position

def _update_task_position(cursor, task_id, new_parent_id, new_position):
    """Update task's parent_id and position"""
    cursor.execute(
        "UPDATE tasks SET parent_id = ?, position = ? WHERE id = ?",
        (new_parent_id, new_position, task_id)
    )

def _finalize_move(conn, task_id, new_position, new_parent_id):
    """Commit transaction, close connection, and notify updates"""
    conn.commit()
    conn.close()
    notify_tasks_updated()
    parent_desc = f"child of #{new_parent_id}" if new_parent_id else "top-level"
    return f"Moved task #{task_id} to position {new_position} as {parent_desc}"

@mcp.tool()
def move_task_as_child(task_id: int, as_child_of: int) -> str:
    """Move a task to be a child of another task
    
    Args:
        task_id: The ID of the task to move
        as_child_of: The ID of the parent task (required, not nullable)
    
    Examples:
        - move_task_as_child(5, 3) - "move task 5 to be child of task 3"
    """
    task_id = _convert_to_int(task_id)
    as_child_of = _convert_to_int(as_child_of)
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Get the task being moved
    task = _get_task_info(cursor, task_id)
    if not task:
        conn.close()
        return f"Error: Task #{task_id} not found"
    
    old_parent_id = task["parent_id"]
    old_position = task["position"]
    
    # Validate parent task
    if as_child_of == task_id:
        conn.close()
        return f"Error: Cannot move task #{task_id} to be its own child"
    
    cursor.execute("SELECT id FROM tasks WHERE id = ?", (as_child_of,))
    if not cursor.fetchone():
        conn.close()
        return f"Error: Parent task #{as_child_of} not found"
    
    new_parent_id = as_child_of
    
    # Get position for new parent
    cursor.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM tasks WHERE parent_id IS ?", (new_parent_id,))
    new_position = cursor.fetchone()[0]
    
    # Shift positions in old location (close the gap)
    new_position = _shift_positions_for_move(cursor, old_parent_id, old_position, new_parent_id, new_position)
    
    # Update the moved task
    _update_task_position(cursor, task_id, new_parent_id, new_position)
    
    result = _finalize_move(conn, task_id, new_position, new_parent_id)
    return f"Moved task #{task_id} to be child of task #{as_child_of}"

@mcp.tool()
def move_task_after(task_id: int, after_task_id: int) -> str:
    """Move a task to be after another task (same parent)
    
    Args:
        task_id: The ID of the task to move
        after_task_id: Move after this task (same parent), e.g., "move xxx after yyy"
    
    Examples:
        - move_task_after(5, 7) - "move task 5 after task 7"
    """
    task_id = _convert_to_int(task_id)
    after_task_id = _convert_to_int(after_task_id)
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Get the task being moved
    task = _get_task_info(cursor, task_id)
    if not task:
        conn.close()
        return f"Error: Task #{task_id} not found"
    
    old_parent_id = task["parent_id"]
    old_position = task["position"]
    
    # Move after another task (inherits its parent)
    target = _get_task_info(cursor, after_task_id)
    if not target:
        conn.close()
        return f"Error: Task #{after_task_id} not found"
    
    new_parent_id = target["parent_id"]
    new_position = target["position"] + 1
    
    # Shift positions in old location (close the gap)
    new_position = _shift_positions_for_move(cursor, old_parent_id, old_position, new_parent_id, new_position)
    
    # Update the moved task
    _update_task_position(cursor, task_id, new_parent_id, new_position)
    
    conn.commit()
    conn.close()
    notify_tasks_updated()
    
    parent_desc = f"child of #{new_parent_id}" if new_parent_id else "top-level"
    return f"Moved task #{task_id} to position {new_position} after task #{after_task_id} as {parent_desc}"

@mcp.tool()
def reorder_task(task_id: int, position: int) -> str:
    """Reorder a task to a specific position within its current parent
    
    Reorders a task within the same parent without changing its parent relationship.
    The task will be moved to the specified position (0-based) among its siblings.
    
    Args:
        task_id: The ID of the task to reorder
        position: Specific position (0 for first) to reorder within same parent
    
    Examples:
        - reorder_task(5, 0) - "reorder task 5 to first position (in current parent)"
        - reorder_task(3, 2) - "reorder task 3 to position 2 (in current parent)"
    """
    task_id = _convert_to_int(task_id)
    position = _convert_to_int(position)
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Get the task being moved
    task = _get_task_info(cursor, task_id)
    if not task:
        conn.close()
        return f"Error: Task #{task_id} not found"
    
    old_parent_id = task["parent_id"]
    old_position = task["position"]
    
    # Move within same parent to specific position
    new_parent_id = old_parent_id
    new_position = position
    
    # Shift positions in old location (close the gap)
    new_position = _shift_positions_for_move(cursor, old_parent_id, old_position, new_parent_id, new_position)
    
    # Update the moved task
    _update_task_position(cursor, task_id, new_parent_id, new_position)
    
    return _finalize_move(conn, task_id, new_position, new_parent_id)

@mcp.tool()
def move_task_to_root(task_id: int) -> str:
    """Move a task to root level (make it a top-level task)
    
    Moves a task from being a child of another task to being a root-level task.
    The task will be placed at the end of all root-level tasks.
    
    Args:
        task_id: The ID of the task to move to root level
    
    Examples:
        - move_task_to_root(17) - "move task 17 to root level"
        - move_task_to_root(5) - "make task 5 a top-level task"
    
    Returns:
        Success message with new position, or error message if task not found
    """
    task_id = _convert_to_int(task_id)
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Get the task being moved
    task = _get_task_info(cursor, task_id)
    if not task:
        conn.close()
        return f"Error: Task #{task_id} not found"
    
    old_parent_id = task["parent_id"]
    old_position = task["position"]
    
    # Check if already at root level
    if old_parent_id is None:
        conn.close()
        return f"Task #{task_id} is already at root level"
    
    # Move to root level
    new_parent_id = None
    
    # Get position for root level tasks
    cursor.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM tasks WHERE parent_id IS NULL")
    new_position = cursor.fetchone()[0]
    
    # Shift positions in old location (close the gap)
    new_position = _shift_positions_for_move(cursor, old_parent_id, old_position, new_parent_id, new_position)
    
    # Update the moved task
    _update_task_position(cursor, task_id, new_parent_id, new_position)
    
    return _finalize_move(conn, task_id, new_position, new_parent_id)

@mcp.tool()
def find_dangling_tasks() -> str:
    """Find all dangling tasks under current workspace
    
    Dangling tasks are tasks that reference a parent_id that doesn't exist in the database.
    This can happen if a parent task was deleted but its children weren't properly cleaned up.
    """
    workspace = get_current_workspace()
    conn = get_db()
    cursor = conn.cursor()
    
    # Get all tasks with parent_id
    cursor.execute("SELECT id, task, parent_id, done FROM tasks WHERE parent_id IS NOT NULL")
    tasks_with_parents = cursor.fetchall()
    
    # Get all valid task IDs
    cursor.execute("SELECT id FROM tasks")
    valid_ids = {row["id"] for row in cursor.fetchall()}
    
    conn.close()
    
    # Find dangling tasks
    dangling = []
    for task in tasks_with_parents:
        if task["parent_id"] not in valid_ids:
            status = "[x]" if task["done"] else "[ ]"
            dangling.append({
                "id": task["id"],
                "task": task["task"],
                "invalid_parent_id": task["parent_id"],
                "done": bool(task["done"])
            })
    
    if not dangling:
        return f"No dangling tasks found in workspace '{workspace}'"
    
    # Format output
    result = [f"Found {len(dangling)} dangling task(s) in workspace '{workspace}':\n"]
    for task in dangling:
        status = "[x]" if task["done"] else "[ ]"
        result.append(f"{status} #{task['id']}: {task['task']}")
        result.append(f"   References non-existent parent #{task['invalid_parent_id']}")
    
    return "\n".join(result)

@mcp.tool()
def fix_dangling_tasks() -> str:
    """Fix dangling tasks by converting them to root (top-level) tasks
    
    Dangling tasks are tasks that reference a parent_id that doesn't exist.
    This function will set their parent_id to NULL and adjust their positions.
    """
    workspace = get_current_workspace()
    conn = get_db()
    cursor = conn.cursor()
    
    # Get all tasks with parent_id
    cursor.execute("SELECT id, task, parent_id, position FROM tasks WHERE parent_id IS NOT NULL")
    tasks_with_parents = cursor.fetchall()
    
    # Get all valid task IDs
    cursor.execute("SELECT id FROM tasks")
    valid_ids = {row["id"] for row in cursor.fetchall()}
    
    # Find dangling tasks
    dangling = []
    for task in tasks_with_parents:
        if task["parent_id"] not in valid_ids:
            dangling.append({
                "id": task["id"],
                "task": task["task"],
                "invalid_parent_id": task["parent_id"],
                "position": task["position"]
            })
    
    if not dangling:
        conn.close()
        return f"No dangling tasks found in workspace '{workspace}'"
    
    # Get max position for top-level tasks
    cursor.execute("SELECT COALESCE(MAX(position), -1) FROM tasks WHERE parent_id IS NULL")
    max_position = cursor.fetchone()[0]
    
    # Fix each dangling task: set parent_id to NULL and update position
    fixed_count = 0
    for task in dangling:
        new_position = max_position + 1 + fixed_count
        cursor.execute(
            "UPDATE tasks SET parent_id = NULL, position = ? WHERE id = ?",
            (new_position, task["id"])
        )
        fixed_count += 1
    
    conn.commit()
    conn.close()
    
    notify_tasks_updated()
    
    result = [f"Fixed {fixed_count} dangling task(s) in workspace '{workspace}':\n"]
    for task in dangling:
        result.append(f"  - Task #{task['id']}: {task['task'][:50]}... (was parent_id={task['invalid_parent_id']}, now top-level)")
    
    return "\n".join(result)

if __name__ == "__main__":
    mcp.run(transport="http")
