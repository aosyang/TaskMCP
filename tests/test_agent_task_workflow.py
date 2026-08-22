import os
import tempfile
import unittest
from unittest import mock

import mcp_server
import workspace_manager


class AgentTaskWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_cwd = os.getcwd()
        os.chdir(self.tmp.name)

    def tearDown(self):
        os.chdir(self.old_cwd)
        self.tmp.cleanup()

    def test_add_task_comments_batch_and_subtree(self):
        with mock.patch.object(mcp_server, "notify_tasks_updated") as notify:
            parent = mcp_server.add_task("Parent", comments="parent context")
            self.assertEqual(parent.task.comments, "parent context")
            batch = mcp_server.add_tasks(
                [
                    mcp_server.TaskCreateInput(task="Child A", comments="A context"),
                    mcp_server.TaskCreateInput(task="Child B", comments="B context"),
                ],
                parent_id=parent.task.id,
            )
            self.assertEqual(batch.count, 2)
            self.assertEqual([task.position for task in batch.tasks], [0, 1])
            self.assertEqual([task.comments for task in batch.tasks], ["A context", "B context"])
            nested = mcp_server.add_task("Nested", parent_id=batch.tasks[0].id, comments="nested context")
            subtree = mcp_server.get_task_subtree(parent.task.id)
            self.assertEqual(subtree.count, 4)
            self.assertEqual(
                [task.id for task in subtree.tasks],
                [parent.task.id, batch.tasks[0].id, nested.task.id, batch.tasks[1].id],
            )
            self.assertEqual(notify.call_count, 3)

    def test_add_task_rejects_blank_title(self):
        with mock.patch.object(mcp_server, "notify_tasks_updated"):
            with self.assertRaises(Exception):
                mcp_server.add_task("   ", comments="should not persist")
            conn = workspace_manager.get_db()
            try:
                count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            finally:
                conn.close()
            self.assertEqual(count, 0)

    def test_add_tasks_prevalidates_all_titles_atomically(self):
        with mock.patch.object(mcp_server, "notify_tasks_updated"):
            with self.assertRaises(Exception):
                mcp_server.add_tasks([
                    mcp_server.TaskCreateInput(task="Valid first"),
                    mcp_server.TaskCreateInput(task="   "),
                ])
            conn = workspace_manager.get_db()
            try:
                count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            finally:
                conn.close()
            self.assertEqual(count, 0)

    def test_add_tasks_is_atomic_when_parent_is_missing(self):
        with mock.patch.object(mcp_server, "notify_tasks_updated"):
            with self.assertRaises(Exception):
                mcp_server.add_tasks(
                    [mcp_server.TaskCreateInput(task="Should not persist")],
                    parent_id=999,
                )
            conn = workspace_manager.get_db()
            try:
                count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            finally:
                conn.close()
            self.assertEqual(count, 0)

    def test_current_workspace_repairs_missing_pointer(self):
        workspace_manager.ensure_workspaces_dir()
        workspace_manager.init_db("survivor")
        workspace_manager.save_workspace_config({"current_workspace": "missing"})
        self.assertEqual(workspace_manager.get_current_workspace(), "survivor")
        self.assertEqual(workspace_manager.load_workspace_config()["current_workspace"], "survivor")

    def test_current_workspace_creates_default_when_none_exist(self):
        workspace_manager.ensure_workspaces_dir()
        workspace_manager.save_workspace_config({"current_workspace": "missing"})
        self.assertEqual(workspace_manager.get_current_workspace(), "default")
        self.assertTrue(os.path.exists(workspace_manager.get_workspace_db_path("default")))


if __name__ == "__main__":
    unittest.main()
