import sqlite3
import tempfile
import unittest
from pathlib import Path

import mcp_server
from fastmcp.exceptions import ToolError


class MCPOutputEfficiencyTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY,
                task TEXT NOT NULL,
                done INTEGER NOT NULL DEFAULT 0,
                parent_id INTEGER,
                position INTEGER NOT NULL,
                comments TEXT NOT NULL DEFAULT ''
            )
            """
        )
        conn.execute("CREATE TABLE current_task (id INTEGER PRIMARY KEY, task_id INTEGER)")
        conn.execute("INSERT INTO current_task VALUES (1, 1)")
        conn.executemany(
            "INSERT INTO tasks (id, task, done, parent_id, position, comments) VALUES (?, ?, ?, ?, ?, ?)",
            [
                (1, "First MCP task", 0, None, 0, "MCP " + "detail " * 80),
                (2, "Completed task", 1, None, 1, "private notes"),
                (3, "Child task", 0, 1, 0, "child notes"),
            ],
        )
        conn.commit()
        conn.close()

        self.original_get_db = mcp_server.get_db
        self.original_get_current_workspace = mcp_server.get_current_workspace
        self.original_list_workspaces = mcp_server.list_workspaces

        def get_db(_workspace_name=None):
            connection = sqlite3.connect(self.db_path)
            connection.row_factory = sqlite3.Row
            return connection

        mcp_server.get_db = get_db
        mcp_server.get_current_workspace = lambda: "test"
        mcp_server.list_workspaces = lambda: ["test"]

    def tearDown(self):
        mcp_server.get_db = self.original_get_db
        mcp_server.get_current_workspace = self.original_get_current_workspace
        mcp_server.list_workspaces = self.original_list_workspaces
        self.temp_dir.cleanup()

    def test_list_tasks_omits_comments_by_default(self):
        compact = mcp_server.list_tasks()
        detailed = mcp_server.list_tasks(include_comments=True)
        self.assertIsNone(compact.tasks[0].comments)
        self.assertTrue(compact.tasks[0].has_comments)
        self.assertNotIn("detail detail", compact.model_dump_json())
        self.assertIn("detail detail", detailed.tasks[0].comments)
        self.assertIn("detail detail", mcp_server.get_task(1).task.comments)

    def test_list_tasks_paginates_and_filters(self):
        first = mcp_server.list_tasks(limit=1)
        second = mcp_server.list_tasks(limit=1, cursor=first.next_cursor)
        self.assertEqual(first.total, 3)
        self.assertEqual(first.count, 1)
        self.assertNotEqual(first.tasks[0].id, second.tasks[0].id)
        self.assertEqual([t.id for t in mcp_server.list_tasks(status="done").tasks], [2])
        self.assertEqual([t.id for t in mcp_server.list_tasks(status="open").tasks], [1, 3])
        exhausted = mcp_server.list_tasks(cursor=100)
        self.assertEqual(exhausted.count, 0)
        self.assertIsNone(exhausted.next_cursor)
        with self.assertRaises(ToolError):
            mcp_server.list_tasks(status="invalid")

    def test_search_is_compact_and_bounded(self):
        for search in [mcp_server.search_tasks, mcp_server.search_tasks_all_workspaces]:
            compact = search("MCP", limit=1)
            detailed = search("MCP", include_comment_snippet=True, limit=1)
            self.assertEqual(compact.count, 1)
            self.assertIsNone(compact.tasks[0].comments)
            self.assertIsNone(compact.tasks[0].comment_excerpt)
            self.assertEqual(compact.tasks[0].matched_in, "title+notes")
            self.assertLessEqual(len(detailed.tasks[0].comment_excerpt), 206)

    def test_search_pagination_and_note_only_match(self):
        for search in [mcp_server.search_tasks, mcp_server.search_tasks_all_workspaces]:
            first = search("task", limit=1)
            seen = [first.tasks[0].id]
            while first.next_cursor is not None:
                first = search("task", limit=1, cursor=first.next_cursor)
                seen.extend(t.id for t in first.tasks)
            self.assertEqual(len(set(seen)), 3)
            notes = search("private", include_comment_snippet=True)
            self.assertEqual(notes.tasks[0].matched_in, "notes")
            self.assertEqual(notes.tasks[0].comment_excerpt, "private notes")

    def test_cross_workspace_pagination(self):
        mcp_server.list_workspaces = lambda: ["second", "first"]
        first = mcp_server.search_tasks_all_workspaces("task", limit=3)
        second = mcp_server.search_tasks_all_workspaces("task", limit=3, cursor=first.next_cursor)
        self.assertEqual(first.total, 6)
        self.assertEqual({t.workspace_name for t in first.tasks}, {"first"})
        self.assertEqual({t.workspace_name for t in second.tasks}, {"second"})
        self.assertIsNone(second.next_cursor)

    def test_current_task_notes_are_opt_in(self):
        self.assertIsNone(mcp_server.get_current_task().task.comments)
        self.assertIn("detail detail", mcp_server.get_current_task(include_comments=True).task.comments)

    def test_empty_search_is_rejected(self):
        for search in [mcp_server.search_tasks, mcp_server.search_tasks_all_workspaces]:
            with self.assertRaises(ToolError):
                search(" ")

    def test_server_advertises_hierarchical_focus_workflow(self):
        instructions = mcp_server.mcp.instructions
        for phrase in ["workspace as a project", "current focus", "child tasks", "actionable leaf tasks", "next_cursor"]:
            self.assertIn(phrase, instructions)


if __name__ == "__main__":
    unittest.main()
