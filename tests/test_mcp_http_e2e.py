import asyncio
import os
import time
import unittest

from fastmcp import Client
from fastmcp.exceptions import ToolError


@unittest.skipUnless(os.environ.get("TASKMCP_HTTP_E2E") == "1", "set TASKMCP_HTTP_E2E=1 with TaskMCP server running")
class TaskMCPHttpE2E(unittest.TestCase):
    def test_agent_contract_end_to_end(self):
        async def run():
            url = os.environ.get("TASKMCP_MCP_URL", "http://127.0.0.1:8000/mcp")
            temp = f"mcp-e2e-{int(time.time())}"
            async with Client(url) as client:
                original = (await client.call_tool("get_current_workspace_name", {})).structured_content["workspace"]
                created = False
                try:
                    await client.call_tool("create_workspace", {"workspace_name": temp})
                    created = True
                    await client.call_tool("switch_workspace", {"workspace_name": temp})
                    parent = (await client.call_tool("add_task", {"task": "parent"})).structured_content["task"]
                    child = (await client.call_tool("add_task", {"task": "child", "parent_id": parent["id"]})).structured_content["task"]
                    grand = (await client.call_tool("add_task", {"task": "grand", "parent_id": child["id"]})).structured_content["task"]
                    with self.assertRaises(ToolError):
                        await client.call_tool("move_task_as_child", {"task_id": parent["id"], "as_child_of": grand["id"]})
                    await client.call_tool("set_current_task", {"task_id": child["id"]})
                    current = (await client.call_tool("get_current_task", {})).structured_content
                    self.assertEqual(current["task"]["id"], child["id"])
                    moved = (await client.call_tool("move_task_to_root", {"task_id": child["id"]})).structured_content
                    self.assertIsNone(moved["task"]["parent_id"])
                    again = (await client.call_tool("move_task_to_root", {"task_id": child["id"]})).structured_content
                    self.assertFalse(again["moved"])
                    await client.call_tool("delete_task", {"task_id": parent["id"]})
                    await client.call_tool("delete_task", {"task_id": child["id"]})
                finally:
                    current_ws = (await client.call_tool("get_current_workspace_name", {})).structured_content["workspace"]
                    if current_ws != original:
                        await client.call_tool("switch_workspace", {"workspace_name": original})
                    if created:
                        try:
                            await client.call_tool("delete_workspace", {"workspace_name": temp})
                        except ToolError as exc:
                            if "WORKSPACE_DELETE_BUSY" not in str(exc):
                                raise
        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
