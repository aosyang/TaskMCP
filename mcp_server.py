from __future__ import annotations

import os
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import BaseModel
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
        "When the target workspace is uncertain, inspect it before mutating tasks. "
        "Use search_tasks when a task ID is unknown. Prefer idempotent setters such as set_task_status over toggle_task. "
        "switch_workspace never creates a missing workspace; use create_workspace explicitly. "
        "Tool results are structured and business failures are reported as MCP ToolError codes. "
        "Cross-workspace search reports unreadable workspaces in its issues array instead of silently omitting them."
    ),
)

def set_current_workspace(workspace_name):
    """Set current workspace and notify without implicitly creating it."""
    set_workspace(workspace_name)
    notify_workspace_changed(workspace_name)

def _task_to_record(task) -> TaskRecord | None:
    if task is None:
        return None
    return TaskRecord(
        id=int(task["id"]),
        task=task["task"],
        done=bool(task["done"]),
        parent_id=task["parent_id"],
        position=int(task["position"]),
        comments=task["comments"] or "",
    )


def _get_task_record(task_id: int) -> TaskRecord:
    task_id = int(task_id)
    conn = get_db()
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    if row is None:
        raise ToolError(f"TASK_NOT_FOUND: Task #{task_id} does not exist in the current workspace")
    return _task_to_record(row)


class TaskRecord(BaseModel):
    id: int
    task: str
    done: bool
    parent_id: int | None
    position: int
    comments: str


class WorkspaceSummary(BaseModel):
    name: str
    task_count: int
    current: bool


class WorkspaceNameResult(BaseModel):
    workspace: str


class WorkspaceListResult(BaseModel):
    current_workspace: str
    workspaces: list[WorkspaceSummary]


class WorkspaceCreatedResult(BaseModel):
    workspace: str
    created: bool
    current: bool


class WorkspaceDeletedResult(BaseModel):
    workspace: str
    deleted: bool


class WorkspaceSwitchResult(BaseModel):
    workspace: str
    switched: bool


class WorkspaceRenameResult(BaseModel):
    old_name: str
    new_name: str
    renamed: bool
    current: bool


class TaskListResult(BaseModel):
    workspace: str
    count: int
    current_task_id: int | None
    tasks: list[TaskRecord]


class TaskCreatedResult(BaseModel):
    workspace: str
    task: TaskRecord
    created: bool


class TaskUpdatedResult(BaseModel):
    workspace: str
    task: TaskRecord
    updated: bool


class TaskDeletedResult(BaseModel):
    workspace: str
    deleted: bool
    deleted_ids: list[int]
    deleted_count: int


class TaskResult(BaseModel):
    workspace: str
    task: TaskRecord


class TaskSearchResult(BaseModel):
    workspace: str
    query: str
    count: int
    tasks: list[TaskRecord]


class CrossWorkspaceTaskRecord(TaskRecord):
    workspace_name: str


class WorkspaceSearchIssue(BaseModel):
    workspace_name: str
    code: str


class CrossWorkspaceSearchResult(BaseModel):
    query: str
    count: int
    tasks: list[CrossWorkspaceTaskRecord]
    issues: list[WorkspaceSearchIssue]


class CurrentTaskResult(BaseModel):
    workspace: str
    current_task_id: int | None
    task: TaskRecord | None
    dangling: bool


class CurrentTaskMutationResult(BaseModel):
    workspace: str
    current_task_id: int | None
    task: TaskRecord | None
    updated: bool


class TaskMoveResult(BaseModel):
    workspace: str
    task: TaskRecord
    moved: bool
    previous_parent_id: int | None
    previous_position: int


class DanglingTaskRecord(BaseModel):
    id: int
    task: str
    done: bool
    invalid_parent_id: int


class DanglingTasksResult(BaseModel):
    workspace: str
    count: int
    tasks: list[DanglingTaskRecord]


class FixDanglingTasksResult(BaseModel):
    workspace: str
    fixed_count: int
    fixed_task_ids: list[int]


# Workspace management tools
@mcp.tool(
    description="Return the current active workspace. Read-only; use this before mutations when the target workspace is uncertain.",
    annotations={"readOnlyHint": True, "openWorldHint": False},
)
def get_current_workspace_name() -> WorkspaceNameResult:
    return WorkspaceNameResult(workspace=get_current_workspace())

@mcp.tool(
    description="List all available workspaces with task counts and identify the current workspace. Read-only.",
    annotations={"readOnlyHint": True, "openWorldHint": False},
)
def list_all_workspaces() -> WorkspaceListResult:
    workspaces = []
    current = get_current_workspace()
    for name in list_workspaces():
        try:
            conn = get_db(name)
            count = int(conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0])
            conn.close()
        except Exception:
            count = 0
        workspaces.append(WorkspaceSummary(name=name, task_count=count, current=name == current))
    return WorkspaceListResult(current_workspace=current, workspaces=workspaces)

@mcp.tool(
    description="Switch to an existing workspace. This never creates a workspace; call create_workspace explicitly when needed.",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
def switch_workspace(workspace_name: str) -> WorkspaceSwitchResult:
    if not validate_workspace_name(workspace_name):
        raise ToolError("INVALID_WORKSPACE_NAME: Use only letters, numbers, underscore, and hyphen")
    db_path = get_workspace_db_path(workspace_name)
    if not os.path.exists(db_path):
        raise ToolError(f"WORKSPACE_NOT_FOUND: Workspace '{workspace_name}' does not exist")
    set_current_workspace(workspace_name)
    notify_tasks_updated()
    return WorkspaceSwitchResult(workspace=workspace_name, switched=True)

@mcp.tool(
    description="Create a new workspace without switching to it.",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
)
def create_workspace(workspace_name: str) -> WorkspaceCreatedResult:
    if not validate_workspace_name(workspace_name):
        raise ToolError("INVALID_WORKSPACE_NAME: Use only letters, numbers, underscore, and hyphen")
    db_path = get_workspace_db_path(workspace_name)
    if os.path.exists(db_path):
        raise ToolError(f"WORKSPACE_ALREADY_EXISTS: Workspace '{workspace_name}' already exists")
    init_db(workspace_name)
    return WorkspaceCreatedResult(workspace=workspace_name, created=True, current=workspace_name == get_current_workspace())

@mcp.tool(
    description="Delete a non-current workspace database. Destructive operation. A freshly modified Dropbox-synced database may briefly report WORKSPACE_DELETE_BUSY; retry the same call later.",
    annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": False},
)
def delete_workspace(workspace_name: str) -> WorkspaceDeletedResult:
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
    return WorkspaceDeletedResult(workspace=workspace_name, deleted=True)

@mcp.tool(
    description="Rename an existing workspace. If it is current, the current-workspace pointer is updated.",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
)
def rename_workspace(old_name: str, new_name: str) -> WorkspaceRenameResult:
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
    return WorkspaceRenameResult(old_name=old_name, new_name=new_name, renamed=True, current=was_current)

# Task management tools
@mcp.tool(
    description="List canonical task records in the current workspace. Read-only. Each record includes ID, status, parent, position, and comments.",
    annotations={"readOnlyHint": True, "openWorldHint": False},
)
def list_tasks() -> TaskListResult:
    workspace = get_current_workspace()
    conn = get_db()
    rows = conn.execute("SELECT * FROM tasks ORDER BY parent_id, position, id").fetchall()
    current = conn.execute("SELECT task_id FROM current_task WHERE id = 1").fetchone()
    conn.close()
    tasks = [_task_to_record(row) for row in rows]
    return TaskListResult(
        workspace=workspace,
        count=len(tasks),
        current_task_id=current["task_id"] if current else None,
        tasks=tasks,
    )

def _add_task_impl(task: str, parent_id: int | None) -> TaskCreatedResult:
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
    return TaskCreatedResult(workspace=get_current_workspace(), task=_task_to_record(row), created=True)

@mcp.tool(
    description="Create a task in the current workspace. Omit parent_id for a top-level task; provide an existing task ID to create a subtask.",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
)
def add_task(task: str, parent_id: int | None = None) -> TaskCreatedResult:
    return _add_task_impl(task, parent_id)

@mcp.tool(
    description="Compatibility alias for add_task(task, parent_id). Prefer add_task for new clients.",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
)
def add_task_with_parent(task: str, parent_id: int) -> TaskCreatedResult:
    return _add_task_impl(task, parent_id)

def _update_task_fields(task_id: int, task: str | None = None, comments: str | None = None) -> TaskUpdatedResult:
    return _update_task_fields(task_id, task=task, comments=comments)


@mcp.tool(
    description="Update the description and/or Markdown comments of an existing task, then return the canonical updated task record.",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
def update_task(task_id: int, task: str | None = None, comments: str | None = None) -> TaskUpdatedResult:
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
    return TaskUpdatedResult(workspace=get_current_workspace(), task=_task_to_record(row), updated=True)

@mcp.tool(
    description="Legacy compatibility tool: replace a task's comments with UTF-8 text read synchronously from a local server file. Prefer update_task(comments=...) for agent workflows.",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
def update_task_comments_from_file(task_id: int, file_path: str) -> TaskUpdatedResult:
    task_id = int(task_id)
    if not os.path.isfile(file_path):
        raise ToolError(f"FILE_NOT_FOUND: Local text file '{file_path}' does not exist")
    try:
        with open(file_path, 'r', encoding='utf-8') as handle:
            comments = handle.read()
    except (OSError, UnicodeError) as exc:
        raise ToolError(f"FILE_READ_FAILED: Could not read UTF-8 text from '{file_path}'") from exc
    return _update_task_fields(task_id, comments=comments)

@mcp.tool(
    description="Compatibility toggle for task completion. Non-idempotent; prefer set_task_status for agent workflows and retries.",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
)
def toggle_task(task_id: int) -> TaskUpdatedResult:
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
    return TaskUpdatedResult(workspace=get_current_workspace(), task=_task_to_record(updated), updated=True)


@mcp.tool(
    description="Set an existing task's completion state explicitly. Safe to retry with the same arguments.",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
def set_task_status(task_id: int, done: bool) -> TaskUpdatedResult:
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
    return TaskUpdatedResult(workspace=get_current_workspace(), task=_task_to_record(row), updated=True)

@mcp.tool(
    description="Delete a task and all descendants recursively from the current workspace. Destructive operation.",
    annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": False},
)
def delete_task(task_id: int) -> TaskDeletedResult:
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
    return TaskDeletedResult(
        workspace=get_current_workspace(), deleted=True, deleted_ids=deleted_ids, deleted_count=len(deleted_ids)
    )

@mcp.tool(
    description="Retrieve one canonical task record by numeric task ID in the current workspace. Read-only.",
    annotations={"readOnlyHint": True, "openWorldHint": False},
)
def get_task(task_id: int) -> TaskResult:
    return TaskResult(workspace=get_current_workspace(), task=_get_task_record(task_id))

@mcp.tool(
    description="Search task descriptions and comments in the current workspace. Use this when the task ID is unknown. Read-only.",
    annotations={"readOnlyHint": True, "openWorldHint": False},
)
def search_tasks(query: str) -> TaskSearchResult:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE task LIKE ? OR comments LIKE ? ORDER BY position, id",
        (f"%{query}%", f"%{query}%"),
    ).fetchall()
    conn.close()
    tasks = [_task_to_record(row) for row in rows]
    return TaskSearchResult(workspace=get_current_workspace(), query=query, count=len(tasks), tasks=tasks)

@mcp.tool(
    description="Search task descriptions and comments across every workspace. Read-only. The issues array reports workspaces that could not be read so results are never silently incomplete.",
    annotations={"readOnlyHint": True, "openWorldHint": False},
)
def search_tasks_all_workspaces(query: str) -> CrossWorkspaceSearchResult:
    results = []
    issues = []
    for workspace_name in list_workspaces():
        try:
            conn = get_db(workspace_name)
            rows = conn.execute(
                "SELECT * FROM tasks WHERE task LIKE ? OR comments LIKE ? ORDER BY position, id",
                (f"%{query}%", f"%{query}%"),
            ).fetchall()
            conn.close()
            for row in rows:
                record = _task_to_record(row)
                results.append(CrossWorkspaceTaskRecord(workspace_name=workspace_name, **record.model_dump()))
        except Exception:
            issues.append(WorkspaceSearchIssue(workspace_name=workspace_name, code="WORKSPACE_READ_FAILED"))
    return CrossWorkspaceSearchResult(query=query, count=len(results), tasks=results, issues=issues)

@mcp.tool(
    description="Set an existing task as the current working task in the current workspace. Safe to retry with the same task ID.",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
def set_current_task(task_id: int) -> CurrentTaskMutationResult:
    task_id = int(task_id)
    task = _get_task_record(task_id)
    conn = get_db()
    conn.execute("INSERT INTO current_task (id, task_id) VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET task_id = excluded.task_id", (task_id,))
    conn.commit()
    conn.close()
    notify_tasks_updated()
    return CurrentTaskMutationResult(
        workspace=get_current_workspace(), current_task_id=task_id, task=task, updated=True
    )

@mcp.tool(
    description="Clear the current working-task pointer. Safe to retry.",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
def clear_current_task() -> CurrentTaskMutationResult:
    conn = get_db()
    conn.execute("DELETE FROM current_task WHERE id = 1")
    conn.commit()
    conn.close()
    notify_tasks_updated()
    return CurrentTaskMutationResult(
        workspace=get_current_workspace(), current_task_id=None, task=None, updated=True
    )

@mcp.tool(
    description="Return the current working task and its canonical record. Read-only. If the pointer is stale, dangling=true and task is null.",
    annotations={"readOnlyHint": True, "openWorldHint": False},
)
def get_current_task() -> CurrentTaskResult:
    conn = get_db()
    current = conn.execute("SELECT task_id FROM current_task WHERE id = 1").fetchone()
    if not current:
        conn.close()
        return CurrentTaskResult(workspace=get_current_workspace(), current_task_id=None, task=None, dangling=False)
    task_id = int(current["task_id"])
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    return CurrentTaskResult(
        workspace=get_current_workspace(),
        current_task_id=task_id,
        task=_task_to_record(row),
        dangling=row is None,
    )

# Helper functions for task movement operations
def _convert_to_int(value):
    return int(value) if isinstance(value, str) else value


def _get_task_info(cursor, task_id):
    return cursor.execute("SELECT * FROM tasks WHERE id = ?", (int(task_id),)).fetchone()


def _normalize_positions(cursor, parent_id):
    rows = cursor.execute(
        "SELECT id FROM tasks WHERE parent_id IS ? ORDER BY position, id", (parent_id,)
    ).fetchall()
    for position, row in enumerate(rows):
        cursor.execute("UPDATE tasks SET position = ? WHERE id = ?", (position, int(row["id"])))


def _would_create_cycle(cursor, task_id: int, new_parent_id: int | None) -> bool:
    current = new_parent_id
    seen = set()
    while current is not None:
        current = int(current)
        if current == task_id or current in seen:
            return True
        seen.add(current)
        row = cursor.execute("SELECT parent_id FROM tasks WHERE id = ?", (current,)).fetchone()
        if row is None:
            return False
        current = row["parent_id"]
    return False


def _move_task(task_id: int, new_parent_id: int | None, new_position: int) -> TaskMoveResult:
    task_id = int(task_id)
    if new_parent_id is not None:
        new_parent_id = int(new_parent_id)
    new_position = int(new_position)
    conn = get_db()
    cursor = conn.cursor()
    task = _get_task_info(cursor, task_id)
    if task is None:
        conn.close()
        raise ToolError(f"TASK_NOT_FOUND: Task #{task_id} does not exist")
    if new_parent_id is not None:
        if _get_task_info(cursor, new_parent_id) is None:
            conn.close()
            raise ToolError(f"PARENT_TASK_NOT_FOUND: Parent task #{new_parent_id} does not exist")
        if _would_create_cycle(cursor, task_id, new_parent_id):
            conn.close()
            raise ToolError(f"TASK_CYCLE_FORBIDDEN: Moving task #{task_id} under task #{new_parent_id} would create a cycle")

    old_parent_id = task["parent_id"]
    old_position = int(task["position"])
    target_rows = cursor.execute(
        "SELECT id FROM tasks WHERE parent_id IS ? AND id != ? ORDER BY position, id",
        (new_parent_id, task_id),
    ).fetchall()
    target_ids = [int(row["id"]) for row in target_rows]
    if new_position < 0 or new_position > len(target_ids):
        conn.close()
        raise ToolError(
            f"POSITION_OUT_OF_RANGE: position must be between 0 and {len(target_ids)} for the target parent"
        )
    target_ids.insert(new_position, task_id)

    cursor.execute("UPDATE tasks SET parent_id = ? WHERE id = ?", (new_parent_id, task_id))
    if old_parent_id != new_parent_id:
        _normalize_positions(cursor, old_parent_id)
    for position, sibling_id in enumerate(target_ids):
        cursor.execute("UPDATE tasks SET position = ? WHERE id = ?", (position, sibling_id))
    conn.commit()
    updated = cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    notify_tasks_updated()
    return TaskMoveResult(
        workspace=get_current_workspace(),
        task=_task_to_record(updated),
        moved=(old_parent_id != new_parent_id or old_position != int(updated["position"])),
        previous_parent_id=old_parent_id,
        previous_position=old_position,
    )


@mcp.tool(
    description="Move a task to the end of another task's child list. Rejects self-parenting and descendant cycles.",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
)
def move_task_as_child(task_id: int, as_child_of: int) -> TaskMoveResult:
    task_id = int(task_id)
    as_child_of = int(as_child_of)
    conn = get_db()
    if _get_task_info(conn.cursor(), task_id) is None:
        conn.close()
        raise ToolError(f"TASK_NOT_FOUND: Task #{task_id} does not exist")
    if _get_task_info(conn.cursor(), as_child_of) is None:
        conn.close()
        raise ToolError(f"PARENT_TASK_NOT_FOUND: Parent task #{as_child_of} does not exist")
    count = int(conn.execute("SELECT COUNT(*) FROM tasks WHERE parent_id IS ? AND id != ?", (as_child_of, task_id)).fetchone()[0])
    conn.close()
    return _move_task(task_id, as_child_of, count)

@mcp.tool(
    description="Move a task immediately after another task, inheriting the target task's parent. Rejects hierarchy cycles.",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
def move_task_after(task_id: int, after_task_id: int) -> TaskMoveResult:
    task_id = int(task_id)
    after_task_id = int(after_task_id)
    if task_id == after_task_id:
        raise ToolError("INVALID_ARGUMENT: task_id and after_task_id must be different")
    conn = get_db()
    cursor = conn.cursor()
    task = _get_task_info(cursor, task_id)
    target = _get_task_info(cursor, after_task_id)
    if task is None:
        conn.close()
        raise ToolError(f"TASK_NOT_FOUND: Task #{task_id} does not exist")
    if target is None:
        conn.close()
        raise ToolError(f"TARGET_TASK_NOT_FOUND: Task #{after_task_id} does not exist")
    new_parent_id = target["parent_id"]
    siblings = cursor.execute(
        "SELECT id FROM tasks WHERE parent_id IS ? AND id != ? ORDER BY position, id", (new_parent_id, task_id)
    ).fetchall()
    sibling_ids = [int(row["id"]) for row in siblings]
    conn.close()
    if after_task_id not in sibling_ids:
        raise ToolError(f"TARGET_TASK_NOT_FOUND: Task #{after_task_id} is not available in the target sibling list")
    return _move_task(task_id, new_parent_id, sibling_ids.index(after_task_id) + 1)

@mcp.tool(
    description="Move a task to an explicit zero-based position among siblings without changing its parent. Safe to retry with the same position.",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
def reorder_task(task_id: int, position: int) -> TaskMoveResult:
    task_id = int(task_id)
    position = int(position)
    conn = get_db()
    task = _get_task_info(conn.cursor(), task_id)
    if task is None:
        conn.close()
        raise ToolError(f"TASK_NOT_FOUND: Task #{task_id} does not exist")
    parent_id = task["parent_id"]
    sibling_count = int(conn.execute("SELECT COUNT(*) FROM tasks WHERE parent_id IS ?", (parent_id,)).fetchone()[0])
    conn.close()
    max_position = max(0, sibling_count - 1)
    if position < 0 or position > max_position:
        raise ToolError(f"POSITION_OUT_OF_RANGE: position must be between 0 and {max_position}")
    return _move_task(task_id, parent_id, position)

@mcp.tool(
    description="Move a task to root level at the end of the root list. If already root-level, return it unchanged. Safe to retry.",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
def move_task_to_root(task_id: int) -> TaskMoveResult:
    task_id = int(task_id)
    conn = get_db()
    task = _get_task_info(conn.cursor(), task_id)
    if task is None:
        conn.close()
        raise ToolError(f"TASK_NOT_FOUND: Task #{task_id} does not exist")
    if task["parent_id"] is None:
        record = _task_to_record(task)
        conn.close()
        return TaskMoveResult(
            workspace=get_current_workspace(), task=record, moved=False,
            previous_parent_id=None, previous_position=int(task["position"])
        )
    count = int(conn.execute("SELECT COUNT(*) FROM tasks WHERE parent_id IS NULL AND id != ?", (task_id,)).fetchone()[0])
    conn.close()
    return _move_task(task_id, None, count)

@mcp.tool(
    description="Find tasks whose parent_id references a missing task in the current workspace. Read-only.",
    annotations={"readOnlyHint": True, "openWorldHint": False},
)
def find_dangling_tasks() -> DanglingTasksResult:
    workspace = get_current_workspace()
    conn = get_db()
    rows = conn.execute(
        "SELECT id, task, parent_id, done FROM tasks WHERE parent_id IS NOT NULL ORDER BY position, id"
    ).fetchall()
    valid_ids = {int(row["id"]) for row in conn.execute("SELECT id FROM tasks").fetchall()}
    conn.close()
    dangling = [
        DanglingTaskRecord(
            id=int(row["id"]), task=row["task"], done=bool(row["done"]), invalid_parent_id=int(row["parent_id"])
        )
        for row in rows if int(row["parent_id"]) not in valid_ids
    ]
    return DanglingTasksResult(workspace=workspace, count=len(dangling), tasks=dangling)

@mcp.tool(
    description="Repair dangling parent references by moving affected tasks to the end of the root list. Safe to retry.",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
def fix_dangling_tasks() -> FixDanglingTasksResult:
    workspace = get_current_workspace()
    conn = get_db()
    cursor = conn.cursor()
    rows = cursor.execute(
        "SELECT id, parent_id FROM tasks WHERE parent_id IS NOT NULL ORDER BY position, id"
    ).fetchall()
    valid_ids = {int(row["id"]) for row in cursor.execute("SELECT id FROM tasks").fetchall()}
    dangling_ids = [int(row["id"]) for row in rows if int(row["parent_id"]) not in valid_ids]
    if dangling_ids:
        root_count = int(cursor.execute("SELECT COUNT(*) FROM tasks WHERE parent_id IS NULL").fetchone()[0])
        for offset, task_id in enumerate(dangling_ids):
            cursor.execute("UPDATE tasks SET parent_id = NULL, position = ? WHERE id = ?", (root_count + offset, task_id))
        _normalize_positions(cursor, None)
        conn.commit()
    conn.close()
    if dangling_ids:
        notify_tasks_updated()
    return FixDanglingTasksResult(workspace=workspace, fixed_count=len(dangling_ids), fixed_task_ids=dangling_ids)

if __name__ == "__main__":
    mcp.run(transport="http")
