import unittest
from typing import Literal

from tool_registry import ToolRegistry


class ToolRegistrySchemaTests(unittest.TestCase):
    def test_complex_annotations_remain_structured(self):
        registry = ToolRegistry()

        @registry.register(description="schema probe")
        def probe(count: int, tags: list[str] | None = None, mode: Literal["a", "b"] = "a"):
            return None

        schema = registry.get_tool("probe").parameters
        self.assertEqual(schema["properties"]["count"]["type"], "integer")
        tags = schema["properties"]["tags"]
        self.assertIn("anyOf", tags)
        array_schema = next(item for item in tags["anyOf"] if item.get("type") == "array")
        self.assertEqual(array_schema["items"]["type"], "string")
        self.assertEqual(schema["properties"]["mode"]["enum"], ["a", "b"])
        self.assertEqual(schema["required"], ["count"])


if __name__ == "__main__":
    unittest.main()
