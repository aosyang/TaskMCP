import asyncio
import unittest

from fastmcp import Client
import mcp_server


class TaskMCPContractTests(unittest.TestCase):
    def test_full_tool_contract(self):
        async def run():
            async with Client(mcp_server.mcp) as client:
                tools = await client.list_tools()
                by_name = {tool.name: tool for tool in tools}
                expected = {
                    "get_current_workspace_name", "list_all_workspaces", "switch_workspace",
                    "create_workspace", "delete_workspace", "rename_workspace", "list_tasks",
                    "add_task", "add_task_with_parent", "update_task",
                    "update_task_comments_from_file", "toggle_task", "set_task_status",
                    "delete_task", "get_task", "search_tasks", "search_tasks_all_workspaces",
                    "set_current_task", "clear_current_task", "get_current_task",
                    "move_task_as_child", "move_task_after", "reorder_task", "move_task_to_root",
                    "find_dangling_tasks", "fix_dangling_tasks",
                }
                self.assertEqual(expected, set(by_name))
                for name, tool in by_name.items():
                    self.assertIsNotNone(tool.annotations, name)
                    self.assertTrue(tool.description, name)
                    self.assertIsInstance(tool.outputSchema, dict, name)
                    self.assertEqual(tool.outputSchema.get("type"), "object", name)
                    self.assertTrue(tool.outputSchema.get("properties"), name)
                self.assertTrue(by_name["get_task"].annotations.readOnlyHint)
                self.assertTrue(by_name["delete_task"].annotations.destructiveHint)
                self.assertTrue(by_name["set_task_status"].annotations.idempotentHint)
                self.assertTrue(by_name["move_task_after"].annotations.idempotentHint)
                self.assertTrue(by_name["find_dangling_tasks"].annotations.readOnlyHint)
                self.assertTrue(by_name["fix_dangling_tasks"].annotations.idempotentHint)
                result = await client.call_tool("get_current_workspace_name", {})
                self.assertFalse(result.is_error)
                self.assertIsNotNone(result.data)
                self.assertIsInstance(result.structured_content, dict)
                self.assertIn("workspace", result.structured_content)
                self.assertIn("workspace", by_name["get_current_workspace_name"].outputSchema["properties"])
                self.assertIn("task", by_name["get_task"].outputSchema["properties"])
        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
