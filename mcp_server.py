import sqlite3
import os
from typing import Optional
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

# Initialize FastMCP server
# Note: FastMCP should handle type coercion by default, but Cursor's MCP client
# may serialize integers as strings. The function implementations include
# string-to-int conversion as a fallback.
mcp = FastMCP("Task Manager")

def set_current_workspace(workspace_name):
    """Set current workspace and notify"""
    set_workspace(workspace_name)
    init_db(workspace_name)
    notify_workspace_changed(workspace_name)

# Workspace management tools
@mcp.tool()
def get_current_workspace_name() -> str:
    """Get the name of the current active workspace"""
    workspace = get_current_workspace()
    return f"Current workspace: {workspace}"

@mcp.tool()
def list_all_workspaces() -> str:
    """List all available workspaces"""
    workspaces = list_workspaces()
    current = get_current_workspace()
    
    result = ["Available workspaces:"]
    for ws in workspaces:
        marker = " (current)" if ws == current else ""
        result.append(f"  - {ws}{marker}")
    
    return "\n".join(result)

@mcp.tool()
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

@mcp.tool()
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

@mcp.tool()
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

@mcp.tool()
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
@mcp.tool()
def list_tasks() -> str:
    """List all tasks in the current workspace in hierarchical structure"""
    workspace = get_current_workspace()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks ORDER BY position")
    tasks = cursor.fetchall()
    conn.close()
    
    # Build hierarchy
    def format_tasks(parent_id=None, level=0):
        result = []
        for task in tasks:
            if task["parent_id"] == parent_id:
                indent = "  " * level
                status = "✓" if task["done"] else "☐"
                comments = f" [{task['comments']}]" if task["comments"] else ""
                result.append(f"{indent}{status} {task['task']}{comments}")
                # Recursively add children
                result.extend(format_tasks(task["id"], level + 1))
        return result
    
    result_lines = format_tasks()
    header = f"Tasks in workspace '{workspace}':\n"
    return header + "\n".join(result_lines) if result_lines else f"No tasks found in workspace '{workspace}'"

def _add_task_impl(task: str, parent_id: int | None, color: str) -> str:
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
        "INSERT INTO tasks (task, done, parent_id, position, comments, color) VALUES (?, 0, ?, ?, '', ?)",
        (task, parent_id, position, color)
    )
    conn.commit()
    task_id = cursor.lastrowid
    conn.close()
    
    notify_tasks_updated()
    return f"Added task #{task_id}: {task}"

@mcp.tool()
def add_task(task: str, color: str = '') -> str:
    """Add a new top-level task item to current workspace
    
    Args:
        task: The task description
        color: Optional background color (hex or color name)
    """
    return _add_task_impl(task, None, color)

@mcp.tool()
def add_task_with_parent(task: str, parent_id: int, color: str = '') -> str:
    """Add a new subtask item to current workspace
    
    Args:
        task: The task description
        parent_id: Parent task ID to create a subtask
        color: Optional background color (hex or color name)
    """
    return _add_task_impl(task, parent_id, color)

@mcp.tool()
def update_task(task_id: int, task: str | None = None, comments: str | None = None, color: str | None = None) -> str:
    """Update a task's description, comments, or color
    
    Args:
        task_id: The ID of the task to update
        task: New task description (optional)
        comments: New comments (optional, supports markdown: **bold**, *italic*, [links](url), lists, code, etc.)
        color: New background color (optional, hex or color name)
    
    Note:
        If updating task comments repeatedly fails, try using update_task_comments_from_file
        to update comments from a text file instead.
    """
    if task is None and comments is None and color is None:
        return "Error: Must provide task, comments, or color to update"
    
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
    if color is not None:
        updates.append("color = ?")
        params.append(color)
    params.append(task_id)
    
    cursor.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    conn.close()
    
    notify_tasks_updated()
    return f"Updated task #{task_id}"

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

@mcp.tool()
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

@mcp.tool()
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

@mcp.tool()
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
    
    status = "✓ Done" if task["done"] else "☐ Incomplete"
    parent = f"(subtask of #{task['parent_id']})" if task["parent_id"] else "(top-level)"
    comments = f"\nComments (markdown): {task['comments']}" if task["comments"] else ""
    
    return f"Task #{task['id']} {parent}\nStatus: {status}\nTask: {task['task']}{comments}"

@mcp.tool()
def set_color(task_id: int, color: str) -> str:
    """Set background color for a task item
    
    Args:
        task_id: The ID of the task to colorize
        color: Background color (hex like '#ff0000' or color name like 'lightblue')
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET color = ? WHERE id = ?", (color, task_id))
    conn.commit()
    conn.close()
    
    notify_tasks_updated()
    return f"Set color '{color}' for task #{task_id}"

@mcp.tool()
def search_tasks(query: str) -> str:
    """Search tasks by description or comments
    
    Args:
        query: Search term to find in task description or comments
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM tasks WHERE task LIKE ? OR comments LIKE ? ORDER BY position",
        (f"%{query}%", f"%{query}%")
    )
    tasks = cursor.fetchall()
    conn.close()
    
    if not tasks:
        return f"No tasks found matching '{query}'"
    
    result = []
    for task in tasks:
        status = "✓" if task["done"] else "☐"
        result.append(f"#{task['id']} {status} {task['task']}")
    
    return "\n".join(result)

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
    
    status = "✓ Done" if task["done"] else "☐ Incomplete"
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
def move_task(task_id: int, position: int) -> str:
    """Move a task to a specific position within its current parent
    
    Args:
        task_id: The ID of the task to move
        position: Specific position (0 for first) to reorder within same parent
    
    Examples:
        - move_task(5, 0) - "move task 5 to first position (in current parent)"
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
            status = "✓" if task["done"] else "☐"
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
        status = "✓" if task["done"] else "☐"
        result.append(f"{status} #{task['id']}: {task['task']}")
        result.append(f"   References non-existent parent #{task['invalid_parent_id']}")
    
    return "\n".join(result)

if __name__ == "__main__":
    mcp.run(transport="http")
