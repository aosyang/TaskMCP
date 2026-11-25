import os
from fastmcp import FastMCP
from notify import notify_tasks_updated, notify_workspace_changed
from workspace_manager import (
    get_current_workspace,
    set_current_workspace as set_workspace,
    list_workspaces,
    get_workspace_db_path,
    validate_workspace_name,
    init_db,
    get_db
)

# This text is returned during the MCP initialization handshake, so an agent can
# understand TaskMCP's workflow without access to this repository or README.
MCP_INSTRUCTIONS = """TaskMCP tracks focused work within a project as an arbitrarily deep task tree.
Treat each workspace as a project. Select one small, actionable task as the current focus.
If a task cannot be completed directly, use child tasks to break it down and repeat only as needed;
work from actionable leaf tasks, avoid unnecessary hierarchy, and record progress on the relevant task."""

MCP_PORT = 8010
MCP_HOST = "0.0.0.0"

# Initialize FastMCP server
# Note: FastMCP should handle type coercion by default, but Cursor's MCP client
# may serialize integers as strings. The function implementations include
# string-to-int conversion as a fallback.
mcp = FastMCP("TaskMCP", instructions=MCP_INSTRUCTIONS)

def set_current_workspace(workspace_name):
    """Set current workspace and notify"""
    set_workspace(workspace_name)
    init_db(workspace_name)
    notify_workspace_changed(workspace_name)

# Workspace management tools
@mcp.tool(output_schema=None)
def get_current_workspace_name() -> str:
    """Get the name of the current active workspace"""
    workspace = get_current_workspace()
    return f"Current workspace: {workspace}"

@mcp.tool(output_schema=None)
def list_all_workspaces() -> str:
    """List all available workspaces"""
    workspaces = list_workspaces()
    current = get_current_workspace()
    
    result = ["Available workspaces:"]
    for ws in workspaces:
        # Get task count for this workspace
        try:
            conn = get_db(ws)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM tasks")
            task_count = cursor.fetchone()[0]
            conn.close()
        except Exception:
            # If database doesn't exist or error, treat as empty
            task_count = 0
        
        # Build markers
        markers = []
        if ws == current:
            markers.append("current")
        if task_count == 0:
            markers.append("empty")
        else:
            markers.append(f"{task_count} task{'s' if task_count > 1 else ''}")
        
        marker_str = f" ({', '.join(markers)})" if markers else ""
        result.append(f"  - {ws}{marker_str}")
    
    return "\n".join(result)

@mcp.tool(output_schema=None)
def switch_workspace(workspace_name: str) -> str:
    """Switch to a different workspace
    
    Args:
        workspace_name: The name of the workspace to switch to
    """
    if not validate_workspace_name(workspace_name):
        return "Error: Invalid workspace name. Use only letters, numbers, underscore, and hyphen"
    
    # Check if workspace exists, if not create it
    db_path = get_workspace_db_path(workspace_name)
    if not os.path.exists(db_path):
        init_db(workspace_name)
    
    set_current_workspace(workspace_name)
    notify_tasks_updated()
    
    return f"Switched to workspace: {workspace_name}"

@mcp.tool(output_schema=None)
def create_workspace(workspace_name: str) -> str:
    """Create a new workspace
    
    Args:
        workspace_name: The name for the new workspace
    """
    if not validate_workspace_name(workspace_name):
        return "Error: Invalid workspace name. Use only letters, numbers, underscore, and hyphen"
    
    db_path = get_workspace_db_path(workspace_name)
    if os.path.exists(db_path):
        return f"Error: Workspace '{workspace_name}' already exists"
    
    init_db(workspace_name)
    
    return f"Created workspace: {workspace_name}"

@mcp.tool(output_schema=None)
def delete_workspace(workspace_name: str) -> str:
    """Delete a workspace
    
    Args:
        workspace_name: The name of the workspace to delete
    """
    current = get_current_workspace()
    if workspace_name == current:
        return f"Error: Cannot delete current workspace '{workspace_name}'. Switch to another workspace first"
    
    db_path = get_workspace_db_path(workspace_name)
    if not os.path.exists(db_path):
        return f"Error: Workspace '{workspace_name}' not found"
    
    os.remove(db_path)
    return f"Deleted workspace: {workspace_name}"

@mcp.tool(output_schema=None)
def rename_workspace(old_name: str, new_name: str) -> str:
    """Rename a workspace
    
    Args:
        old_name: Current name of the workspace
        new_name: New name for the workspace
    """
    if not validate_workspace_name(new_name):
        return "Error: Invalid workspace name. Use only letters, numbers, underscore, and hyphen"
    
    old_path = get_workspace_db_path(old_name)
    new_path = get_workspace_db_path(new_name)
    
    if not os.path.exists(old_path):
        return f"Error: Workspace '{old_name}' not found"
    
    if os.path.exists(new_path):
        return f"Error: Workspace '{new_name}' already exists"
    
    os.rename(old_path, new_path)
    
    # Update current workspace if it was renamed
    if old_name == get_current_workspace():
        set_current_workspace(new_name)
    
    notify_tasks_updated()
    
    return f"Renamed workspace from '{old_name}' to '{new_name}'"

# Task management tools
def _pagination_values(limit, cursor):
    """Normalize pagination values supplied by MCP clients."""
    limit = int(limit) if isinstance(limit, str) else limit
    cursor = int(cursor) if isinstance(cursor, str) else cursor
    return max(1, min(limit, 100)), max(0, cursor)


def _as_bool(value):
    """Normalize boolean values supplied by MCP clients."""
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _comment_excerpt(comments, query, max_chars=200):
    """Return a bounded, single-line excerpt around a comment match."""
    normalized = " ".join((comments or "").split())
    if not normalized:
        return ""

    match_at = normalized.lower().find(query.lower())
    if match_at < 0:
        match_at = 0

    before = max_chars // 3
    start = max(0, match_at - before)
    end = min(len(normalized), start + max_chars)
    if end - start < max_chars:
        start = max(0, end - max_chars)

    excerpt = normalized[start:end]
    if start > 0:
        excerpt = "..." + excerpt
    if end < len(normalized):
        excerpt += "..."
    return excerpt


@mcp.tool(output_schema=None)
def list_tasks(
    include_comments: bool = False,
    status: str = "all",
    limit: int = 50,
    cursor: int = 0,
) -> str:
    """Inspect the current project's hierarchical task tree with compact, paginated output.

    Use this to find a suitable focus or understand parent/child context. Tasks may be
    nested to any depth; actionable leaf tasks are normally the units of execution.

    Args:
        include_comments: Include full comments. Defaults to false; use get_task for details.
        status: Filter by all, open, or done.
        limit: Maximum tasks to return (1-100).
        cursor: Zero-based offset for the next page.
    """
    include_comments = _as_bool(include_comments)
    limit, page_cursor = _pagination_values(limit, cursor)
    status = status.strip().lower()
    status_aliases = {"all": "all", "open": "open", "incomplete": "open", "done": "done", "completed": "done"}
    if status not in status_aliases:
        return "Error: status must be one of: all, open, done"
    status = status_aliases[status]

    workspace = get_current_workspace()
    conn = get_db()
    db_cursor = conn.cursor()
    db_cursor.execute("SELECT * FROM tasks ORDER BY position")
    tasks = db_cursor.fetchall()
    conn.close()

    flattened = []

    def flatten_tasks(parent_id=None, level=0):
        for task in tasks:
            if task["parent_id"] == parent_id:
                flattened.append((task, level))
                flatten_tasks(task["id"], level + 1)

    flatten_tasks()
    if status == "open":
        flattened = [item for item in flattened if not item[0]["done"]]
    elif status == "done":
        flattened = [item for item in flattened if item[0]["done"]]

    total = len(flattened)
    page = flattened[page_cursor:page_cursor + limit]
    if not page:
        return f"No tasks found in workspace '{workspace}' for status '{status}'"

    result_lines = []
    for task, level in page:
        indent = "  " * level
        task_status = "[x]" if task["done"] else "[ ]"
        if include_comments and task["comments"]:
            comments = f" [{task['comments']}]"
        elif task["comments"]:
            comments = " [notes]"
        else:
            comments = ""
        result_lines.append(f"{indent}{task_status} #{task['id']} {task['task']}{comments}")

    end = page_cursor + len(page)
    comment_mode = "included" if include_comments else "omitted; use get_task for full notes"
    header = (
        f"Tasks in workspace '{workspace}' "
        f"(showing {page_cursor + 1}-{end} of {total}; comments {comment_mode}):\n"
    )
    if end < total:
        result_lines.append(f"Next cursor: {end}")
    return header + "\n".join(result_lines)

def _add_task_impl(task: str, parent_id: int | None) -> str:
    """Internal implementation for adding a task"""
    # Convert string parameters to int if needed (FastMCP may serialize ints as strings)
    if parent_id is not None:
        parent_id = int(parent_id) if isinstance(parent_id, str) else parent_id
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Validate parent_id exists if provided
    if parent_id is not None:
        cursor.execute("SELECT id FROM tasks WHERE id = ?", (parent_id,))
        if cursor.fetchone() is None:
            conn.close()
            return f"Error: Parent task #{parent_id} does not exist"
    
    # Get max position for this parent
    cursor.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM tasks WHERE parent_id IS ?", (parent_id,))
    position = cursor.fetchone()[0]
    
    cursor.execute(
        "INSERT INTO tasks (task, done, parent_id, position, comments) VALUES (?, 0, ?, ?, '')",
        (task, parent_id, position)
    )
    conn.commit()
    task_id = cursor.lastrowid
    conn.close()
    
    notify_tasks_updated()
    return f"Added task #{task_id}: {task}"

@mcp.tool(output_schema=None)
def add_task(task: str) -> str:
    """Add a new top-level task item to current workspace
    
    Args:
        task: The task description
    """
    return _add_task_impl(task, None)

@mcp.tool(output_schema=None)
def add_task_with_parent(task: str, parent_id: int) -> str:
    """Break down a task by adding one actionable child task.

    A child may itself receive children, allowing decomposition to any depth. Add
    children only when the parent cannot be completed directly; avoid needless hierarchy.
    
    Args:
        task: The task description
        parent_id: Parent task ID to create a subtask
    """
    return _add_task_impl(task, parent_id)

@mcp.tool(output_schema=None)
def update_task(task_id: int, task: str | None = None, comments: str | None = None) -> str:
    """Update a task's description or comments
    
    Args:
        task_id: The ID of the task to update
        task: New task description (optional)
        comments: New comments (optional, supports markdown: **bold**, *italic*, [links](url), lists, code, etc.)
    
    Note:
        If updating task comments repeatedly fails, try using update_task_comments_from_file
        to update comments from a text file instead.
    """
    if task is None and comments is None:
        return "Error: Must provide task or comments to update"
    
    conn = get_db()
    cursor = conn.cursor()
    
    updates = []
    params = []
    if task is not None:
        updates.append("task = ?")
        params.append(task)
    if comments is not None:
        updates.append("comments = ?")
        params.append(comments)
    params.append(task_id)
    
    cursor.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    conn.close()
    
    notify_tasks_updated()
    return f"Updated task #{task_id}"

@mcp.tool(output_schema=None)
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

@mcp.tool(output_schema=None)
def toggle_task(task_id: int) -> str:
    """Toggle a task's done status
    
    Args:
        task_id: The ID of the task to toggle
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET done = NOT done WHERE id = ?", (task_id,))
    cursor.execute("SELECT done FROM tasks WHERE id = ?", (task_id,))
    done = cursor.fetchone()[0]
    conn.commit()
    conn.close()
    
    notify_tasks_updated()
    status = "completed" if done else "incomplete"
    return f"Task #{task_id} marked as {status}"

@mcp.tool(output_schema=None)
def delete_task(task_id: int) -> str:
    """Delete a task and all its subtasks
    
    Args:
        task_id: The ID of the task to delete
    """
    conn = get_db()
    cursor = conn.cursor()
    
    # Delete subtasks first
    cursor.execute("DELETE FROM tasks WHERE parent_id = ?", (task_id,))
    # Delete the task
    cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    
    notify_tasks_updated()
    return f"Deleted task #{task_id} and its subtasks"

@mcp.tool(output_schema=None)
def get_task(task_id: int) -> str:
    """Get details of a specific task
    
    Args:
        task_id: The ID of the task to retrieve
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    task = cursor.fetchone()
    conn.close()
    
    if not task:
        return f"Task #{task_id} not found"
    
    status = "[x] Done" if task["done"] else "[ ] Incomplete"
    parent = f"(subtask of #{task['parent_id']})" if task["parent_id"] else "(top-level)"
    comments = f"\nComments (markdown): {task['comments']}" if task["comments"] else ""
    
    return f"Task #{task['id']} {parent}\nStatus: {status}\nTask: {task['task']}{comments}"

@mcp.tool(output_schema=None)
def search_tasks(
    query: str,
    include_comment_snippet: bool = False,
    limit: int = 20,
    cursor: int = 0,
) -> str:
    """Search tasks by description or comments

    Args:
        query: Search term to find in task description or comments
        include_comment_snippet: Include a bounded excerpt when the comment matched.
        limit: Maximum matches to return (1-100).
        cursor: Zero-based offset for the next page.
    """
    query = query.strip()
    if not query:
        return "Error: query must not be empty"
    include_comment_snippet = _as_bool(include_comment_snippet)
    limit, page_cursor = _pagination_values(limit, cursor)

    conn = get_db()
    db_cursor = conn.cursor()
    pattern = f"%{query}%"
    db_cursor.execute(
        "SELECT COUNT(*) FROM tasks WHERE task LIKE ? OR comments LIKE ?",
        (pattern, pattern)
    )
    total = db_cursor.fetchone()[0]
    db_cursor.execute(
        "SELECT * FROM tasks WHERE task LIKE ? OR comments LIKE ? ORDER BY position LIMIT ? OFFSET ?",
        (pattern, pattern, limit, page_cursor)
    )
    tasks = db_cursor.fetchall()
    conn.close()

    if not tasks:
        return f"No tasks found matching '{query}'"

    result = [f"Matches for '{query}' (showing {page_cursor + 1}-{page_cursor + len(tasks)} of {total}):"]
    for task in tasks:
        task_status = "[x]" if task["done"] else "[ ]"
        title_match = query.lower() in task["task"].lower()
        comment_match = query.lower() in (task["comments"] or "").lower()
        match_source = "title+notes" if title_match and comment_match else "title" if title_match else "notes"
        result.append(f"#{task['id']} {task_status} {task['task']} [match: {match_source}]")
        if include_comment_snippet and comment_match:
            result.append(f"  Note excerpt: {_comment_excerpt(task['comments'], query)}")

    end = page_cursor + len(tasks)
    if end < total:
        result.append(f"Next cursor: {end}")
    return "\n".join(result)

@mcp.tool(output_schema=None)
def search_tasks_all_workspaces(
    query: str,
    include_comment_snippet: bool = False,
    limit: int = 20,
    cursor: int = 0,
) -> str:
    """Search tasks across all workspaces

    Args:
        query: Search term to find in task description or comments
        include_comment_snippet: Include a bounded excerpt when the comment matched.
        limit: Maximum matches to return (1-100).
        cursor: Zero-based offset for the next page.
    """
    import json
    query = query.strip()
    if not query:
        return json.dumps({"error": "query must not be empty"})
    include_comment_snippet = _as_bool(include_comment_snippet)
    limit, page_cursor = _pagination_values(limit, cursor)

    results = []
    workspaces = list_workspaces()
    pattern = f"%{query}%"

    for workspace_name in workspaces:
        try:
            conn = get_db(workspace_name)
            db_cursor = conn.cursor()
            db_cursor.execute(
                "SELECT id, task, done, comments FROM tasks WHERE task LIKE ? OR comments LIKE ? ORDER BY position",
                (pattern, pattern)
            )
            tasks = db_cursor.fetchall()
            conn.close()

            for task in tasks:
                comments = task["comments"] or ""
                title_match = query.lower() in task["task"].lower()
                comment_match = query.lower() in comments.lower()
                item = {
                    "task_id": task["id"],
                    "task": task["task"],
                    "workspace_name": workspace_name,
                    "done": bool(task["done"]),
                    "matched_in": "title+notes" if title_match and comment_match else "title" if title_match else "notes",
                    "has_comments": bool(comments)
                }
                if include_comment_snippet and comment_match:
                    item["comment_excerpt"] = _comment_excerpt(comments, query)
                results.append(item)
        except Exception:
            # Skip workspaces with errors (e.g., corrupted database)
            continue

    if not results:
        return json.dumps({"query": query, "total": 0, "items": []}, ensure_ascii=False, separators=(",", ":"))

    total = len(results)
    page = results[page_cursor:page_cursor + limit]
    payload = {
        "query": query,
        "total": total,
        "cursor": page_cursor,
        "limit": limit,
        "next_cursor": page_cursor + len(page) if page_cursor + len(page) < total else None,
        "items": page
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

@mcp.tool(output_schema=None)
def set_current_task(task_id: int) -> str:
    """Set the one small, actionable task the agent is currently working on.

    Prefer an executable leaf task. If the selected task is still too broad, create
    child tasks and move the current focus to the appropriate child.
    
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

@mcp.tool(output_schema=None)
def clear_current_task() -> str:
    """Clear the current working task"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM current_task WHERE id = 1")
    conn.commit()
    conn.close()
    
    notify_tasks_updated()
    return "Cleared current task"

@mcp.tool(output_schema=None)
def get_current_task(include_comments: bool = False) -> str:
    """Get the current focused task; full comments are opt-in.

    Use this at the start of a work session to resume the project's active unit of work.
    """
    include_comments = _as_bool(include_comments)
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
    if include_comments and task["comments"]:
        comments = f"\nComments (markdown): {task['comments']}"
    elif task["comments"]:
        comments = "\nComments: available via get_task or include_comments=true"
    else:
        comments = ""
    
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

@mcp.tool(output_schema=None)
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

@mcp.tool(output_schema=None)
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

@mcp.tool(output_schema=None)
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

@mcp.tool(output_schema=None)
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

@mcp.tool(output_schema=None)
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

@mcp.tool(output_schema=None)
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
    mcp.run(transport="http", host=MCP_HOST, port=MCP_PORT)
