import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import mcp_server


class MCPBehaviorRegressionTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tempdir.name, "tasks.db")
        conn = sqlite3.connect(self.db_path)
        conn.execute("CREATE TABLE tasks (id INTEGER PRIMARY KEY, task TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0, parent_id INTEGER, position INTEGER NOT NULL DEFAULT 0, comments TEXT NOT NULL DEFAULT '')")
        conn.execute("INSERT INTO tasks (id, task, done, parent_id, position, comments) VALUES (1, 'hello', 0, NULL, 0, 'old')")
        conn.commit()
        conn.close()

    def tearDown(self):
        self.tempdir.cleanup()

    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def test_update_task_comments_from_file_executes_real_update_path(self):
        note_path = os.path.join(self.tempdir.name, "note.md")
        with open(note_path, "w", encoding="utf-8") as handle:
            handle.write("new markdown comments")
        with patch.object(mcp_server, "get_db", side_effect=lambda *args, **kwargs: self.connect()),              patch.object(mcp_server, "get_current_workspace", return_value="test"),              patch.object(mcp_server, "notify_tasks_updated"):
            result = mcp_server.update_task_comments_from_file(1, note_path)
        self.assertEqual(result.task.comments, "new markdown comments")
        conn = self.connect()
        stored = conn.execute("SELECT comments FROM tasks WHERE id = 1").fetchone()[0]
        conn.close()
        self.assertEqual(stored, "new markdown comments")

    def test_list_workspaces_reports_unreadable_workspace(self):
        def get_db(name=None):
            if name == "bad":
                raise sqlite3.DatabaseError("broken")
            return self.connect()
        with patch.object(mcp_server, "list_workspaces", return_value=["good", "bad"]),              patch.object(mcp_server, "get_db", side_effect=get_db),              patch.object(mcp_server, "get_current_workspace", return_value="good"):
            result = mcp_server.list_all_workspaces()
        by_name = {item.name: item for item in result.workspaces}
        self.assertEqual(by_name["good"].task_count, 1)
        self.assertIsNone(by_name["bad"].task_count)
        self.assertEqual([(i.workspace_name, i.code) for i in result.issues], [("bad", "WORKSPACE_READ_FAILED")])

    def test_cross_workspace_search_closes_connection_on_read_failure(self):
        class BrokenConnection:
            def __init__(self):
                self.closed = False
            def execute(self, *args, **kwargs):
                raise sqlite3.DatabaseError("broken")
            def close(self):
                self.closed = True
        broken = BrokenConnection()
        with patch.object(mcp_server, "list_workspaces", return_value=["bad"]),              patch.object(mcp_server, "get_db", return_value=broken):
            result = mcp_server.search_tasks_all_workspaces("x")
        self.assertTrue(broken.closed)
        self.assertEqual(result.count, 0)
        self.assertEqual(result.issues[0].code, "WORKSPACE_READ_FAILED")


if __name__ == "__main__":
    unittest.main()
