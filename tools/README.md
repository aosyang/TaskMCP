# Tool Registration System

Universal tool registration system for easy extension of tools for model use.

## Architecture

### Core Components

1. **ToolRegistry** (`tool_registry.py`): Tool registration center
   - Unified management of all tools
   - Auto-generate tool definitions from function signatures
   - Support tool categorization

2. **Tools Package** (`tools/__init__.py`): Tool initialization
   - Auto-register all tools
   - Support FastMCP tools
   - Support custom tools

## Usage

### Method 1: Using Decorator Registration (Recommended)

The simplest way, suitable for most tools:

```python
from tool_registry import register_tool
from datetime import datetime

@register_tool(
    description="Get the current time",
    category="time"
)
def get_current_time() -> str:
    """Get the current time"""
    return datetime.now().strftime('%H:%M:%S')
```

### Method 2: Manual Registration

Suitable for tools that need custom parameter definitions:

```python
from tool_registry import get_registry

def search_web(query: str, timeout: int = 60) -> str:
    """Search the web"""
    # ... implementation ...
    return result

registry = get_registry()
registry.register_manual(
    name="search_web",
    function=search_web,
    description="Search the web or ask questions",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "timeout": {"type": "integer", "default": 60}
        },
        "required": ["query"]
    },
    category="web"
)
```

### Method 3: Create New Module in tools/ Directory (Auto-Discovery)

**Note:** Tools in the `tools/` directory are automatically discovered and registered. No manual import needed!

1. Create a new file `tools/my_tools.py`:

```python
from tool_registry import register_tool

@register_tool(description="Calculate sum of two numbers", category="math")
def add_numbers(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b

@register_tool(description="Get weather information", category="weather")
def get_weather(city: str) -> str:
    """Get weather for a city"""
    # ... implementation ...
    return f"Weather in {city}: Sunny"
```

2. **No import needed!** The tool will be automatically discovered and registered when the `tools` module is imported.

## Tool Categories

Tools can be grouped by category for easier management:

```python
# View all categories
registry = get_registry()
categories = registry.get_all_categories()
# ['mcp', 'time', 'web', 'math', 'weather']

# View tools in a specific category
time_tools = registry.get_tools_by_category('time')
# ['get_current_time', 'get_current_date', 'get_current_datetime']
```

## Auto Parameter Generation

The system automatically generates parameter definitions from function signatures:

```python
@register_tool(description="Process data")
def process_data(
    input_data: str,      # -> {"type": "string"}
    count: int,           # -> {"type": "integer"}
    enabled: bool = True,  # -> {"type": "boolean", "default": True}
    options: dict = None  # -> {"type": "object", "default": None}
) -> str:
    """Process data with options"""
    # ...
```

Supported types:
- `str` / `Optional[str]` → `"string"`
- `int` → `"integer"`
- `float` → `"number"`
- `bool` → `"boolean"`
- `list` / `List` → `"array"`
- `dict` / `Dict` → `"object"`

## Backward Compatibility

The system is fully backward compatible with existing code:

- If `tool_registry` is not available, automatically falls back to the old method
- Existing `get_tool_dicts()` and `get_available_functions()` continue to work
- Can gradually migrate to the new system

## Extension Examples

### Adding Calculator Tools

Create `tools/calculator.py`:

```python
from tool_registry import register_tool

@register_tool(description="Add two numbers", category="calculator")
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b

@register_tool(description="Multiply two numbers", category="calculator")
def multiply(a: int, b: int) -> int:
    """Multiply two numbers"""
    return a * b
```

**No import needed!** The tools will be automatically discovered.

### Adding File Operation Tools

Create `tools/file_ops.py`:

```python
from tool_registry import register_tool
import os

@register_tool(description="Read a file", category="file")
def read_file(filepath: str) -> str:
    """Read content from a file"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()

@register_tool(description="List files in directory", category="file")
def list_files(directory: str) -> str:
    """List all files in a directory"""
    files = os.listdir(directory)
    return '\n'.join(files)
```

**No import needed!** The tools will be automatically discovered.

## Advantages

1. **Unified Management**: All tools registered and managed in one place
2. **Auto-Generation**: Automatically generate tool definitions from function signatures
3. **Easy Extension**: Add new tools with just a few lines of code
4. **Type Safety**: Support type annotations with automatic type conversion
5. **Category Management**: Support tool categorization for better organization
6. **Backward Compatible**: Does not affect existing code
7. **Auto-Discovery**: Tools in `tools/` directory are automatically discovered and registered

## Notes

1. Tool functions must have docstrings (used for description)
2. Parameter type annotations help generate accurate parameter definitions
3. Complex parameters are recommended to use `register_manual` for manual definition
4. Tool functions should be pure functions or functions with controllable side effects
5. Tools in `tools/` directory are automatically discovered - no manual import needed!
