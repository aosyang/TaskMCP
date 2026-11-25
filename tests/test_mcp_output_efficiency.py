import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import mcp_server


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

        self.assertIn("comments omitted", compact)
        self.assertIn("[notes]", compact)
        self.assertNotIn("detail detail", compact)
        self.assertIn("detail detail", detailed)

    def test_list_tasks_paginates_and_filters(self):
        first_page = mcp_server.list_tasks(limit=1)
        second_page = mcp_server.list_tasks(limit=1, cursor=1)
        completed = mcp_server.list_tasks(status="done")

        self.assertIn("Next cursor: 1", first_page)
        self.assertNotEqual(first_page, second_page)
        self.assertIn("#2 Completed task", completed)
        self.assertNotIn("#1 First MCP task", completed)

    def test_search_all_workspaces_is_compact_and_bounded(self):
        compact = json.loads(mcp_server.search_tasks_all_workspaces("MCP", limit=1))
        with_excerpt = json.loads(
            mcp_server.search_tasks_all_workspaces(
                "MCP",
                include_comment_snippet=True,
                limit=1,
            )
        )

        self.assertEqual(1, len(compact["items"]))
        self.assertNotIn("comments", compact["items"][0])
        self.assertNotIn("comment_excerpt", compact["items"][0])
        self.assertLessEqual(len(with_excerpt["items"][0]["comment_excerpt"]), 206)

    def test_empty_search_is_rejected(self):
        self.assertIn("must not be empty", mcp_server.search_tasks(" "))
        payload = json.loads(mcp_server.search_tasks_all_workspaces(" "))
        self.assertEqual("query must not be empty", payload["error"])

    def test_server_advertises_hierarchical_focus_workflow(self):
        instructions = mcp_server.mcp.instructions

        self.assertIn("workspace as a project", instructions)
        self.assertIn("current focus", instructions)
        self.assertIn("child tasks", instructions)
        self.assertIn("actionable leaf tasks", instructions)


if __name__ == "__main__":
    unittest.main()
