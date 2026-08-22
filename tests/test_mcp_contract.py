import asyncio
import unittest

from fastmcp import Client
import mcp_server


class TaskMCPContractTests(unittest.TestCase):
    def test_core_tool_contract(self):
        async def run():
            async with Client(mcp_server.mcp) as client:
                tools = await client.list_tools()
                by_name = {tool.name: tool for tool in tools}
                for name in (
                    "get_current_workspace_name", "list_tasks", "add_task",
                    "update_task", "get_task", "search_tasks",
                    "set_task_status", "delete_task", "switch_workspace",
                ):
                    self.assertIn(name, by_name)
                self.assertTrue(by_name["get_task"].annotations.readOnlyHint)
                self.assertTrue(by_name["delete_task"].annotations.destructiveHint)
                self.assertTrue(by_name["set_task_status"].annotations.idempotentHint)
                result = await client.call_tool("get_current_workspace_name", {})
                self.assertFalse(result.is_error)
                self.assertIsInstance(result.data, dict)
                self.assertIn("workspace", result.data)
        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
