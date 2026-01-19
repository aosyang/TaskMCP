# TaskMCP

A multi-workspace task management system with hierarchical structure, drag-and-drop sorting, real-time synchronization, and MCP server integration for AI agents to manage tasks through natural language.

## Features

### Web Interface (http://localhost:5000)
- **Multi-workspace support** - Each workspace has an independent database
- Hierarchical task structure (unlimited nested subtasks)
- Drag-and-drop sorting
- Task completion toggle
- Task comments/notes (Markdown support)
- Inline task editing
- WebSocket real-time synchronization (multi-client updates)
- Two view modes: List view and Canvas view

### MCP Server (http://localhost:8000)

**Workspace Management Tools:**
- `get_current_workspace_name` - Get current workspace name
- `list_all_workspaces` - List all workspaces
- `switch_workspace` - Switch workspace (auto-creates if not exists)
- `create_workspace` - Create new workspace
- `delete_workspace` - Delete workspace
- `rename_workspace` - Rename workspace

**Task Management Tools:**
- `list_tasks` - List all tasks in current workspace (hierarchical display)
- `add_task` - Add new task (can specify parent_id for subtasks)
- `update_task` - Update task description or comments
- `toggle_task` - Toggle completion status
- `delete_task` - Delete task and all subtasks
- `get_task` - Get task details
- `search_tasks` - Search tasks
- `move_task` - Move task position
- `set_current_task` - Set current working task
- `clear_current_task` - Clear current working task
- `get_current_task` - Get current working task

## Tech Stack

**Backend:**
- Flask - Web framework
- Flask-SocketIO - WebSocket real-time communication
- SQLite3 - Database
- FastMCP - MCP server framework
- Model Provider Abstraction - Support for multiple LLM backends (Ollama, OpenAI)

**Frontend:**
- React 18 + TypeScript
- @dnd-kit - Drag and drop sorting
- Socket.IO Client - Real-time updates
- esbuild - Build tool

**AI/LLM Integration:**
- Ollama - Local LLM support (default)
- OpenAI API - Cloud LLM support
- Model Provider Abstraction Layer - Easy to add new providers

## Installation & Setup

### 1. Install Dependencies

```bash
# Core dependencies (required for Web interface and MCP server)
pip install -r requirements.txt

# For CLI (optional)
pip install -r requirements-cli.txt

# For Telegram bot (optional)
pip install -r requirements-telegram.txt

# Or install manually:
# Core dependencies (Web interface and MCP server)
pip install flask flask-socketio fastmcp requests

# Python < 3.11 requires TOML support
pip install tomli

# For CLI (optional)
pip install ollama

# For Telegram bot (optional)
pip install ollama python-telegram-bot python-dotenv telegramify-markdown

# Node.js dependencies
npm install
```

**Note:** 
- Core dependencies (`requirements.txt`) are required for Web interface and MCP server
- CLI (`task_cli.py`) requires `ollama` - install `requirements-cli.txt`
- Telegram bot (`task_telegram.py`) requires `ollama` and Telegram libraries - install `requirements-telegram.txt`

### 2. Configure Server Access Mode (Optional)

Edit `server_config.toml` to configure server access:

```toml
host = "localhost"
port = 5000
```

**Configuration:**
- `host`: Bind address (default: `localhost`)
  - `localhost` or `127.0.0.1` - Local access only
  - `0.0.0.0` - Bind to all network interfaces (allow LAN and other devices)
- `port`: Server port number (default: 5000)

**Examples:**
- Local access only: `host = "localhost"`
- Allow LAN access: `host = "0.0.0.0"`

**Note:** Python 3.11+ has built-in TOML support. Python < 3.11 requires: `pip install tomli`

### 3. Configure Model Provider (for CLI and Telegram Bot)

Edit `agent_config.toml` to configure the model provider:

#### Using Ollama (Default)

```toml
[provider]
type = "ollama"

[ollama]
model = "qwen3:14b"
# base_url = "http://localhost:11434"  # Optional, defaults to http://localhost:11434
```

#### Using OpenAI

**Recommended: Use environment variable for API key (more secure)**

1. Set the environment variable:
   ```bash
   # Windows (PowerShell)
   $env:OPENAI_API_KEY="sk-..."
   
   # Windows (CMD)
   set OPENAI_API_KEY=sk-...
   
   # Linux/Mac
   export OPENAI_API_KEY=sk-...
   ```
   
   Or create a `.env` file (copy from `.env.example`):
   ```
   OPENAI_API_KEY=sk-...
   ```

2. Configure `agent_config.toml`:
   ```toml
   [provider]
   type = "openai"
   
   [openai]
   model = "gpt-4o"
   # api_key is optional if OPENAI_API_KEY environment variable is set
   # base_url = "https://api.openai.com/v1"  # Optional, supports custom endpoints
   ```

**Alternative: Set API key in config file (less secure)**
```toml
[provider]
type = "openai"

[openai]
model = "gpt-4o"
api_key = "sk-..."  # Not recommended for production
# base_url = "https://api.openai.com/v1"  # Optional, supports custom endpoints
```

**Backward Compatibility:**
- If `[provider]` section is not present, the system defaults to Ollama
- Existing configurations with only `[ollama]` section will continue to work

**Requirements:**
- For Ollama: `pip install ollama` (included in `requirements-cli.txt`)
- For OpenAI: `pip install openai`

### 4. Start Server

```bash
# Start both Web server and MCP server
python app.py
```

After starting:
- Web Interface: 
  - Local: http://localhost:5000
  - Network: http://<your-ip>:5000 (shown on startup if network access enabled)
- MCP Server: http://localhost:8000/mcp

### 5. Configure MCP Client

For VS Code, configure `.vscode/mcp.json`:

```json
{
  "servers": {
    "fastmcp-http": {
      "type": "http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

## Usage Examples

### Workspace Management

In Web Interface:
1. Click workspace dropdown in top-right corner
2. Click "Manage" to open workspace manager
3. Create, rename, or delete workspaces

Via MCP/AI Agent:
- "What is the current workspace?"
- "List all workspaces"
- "Switch to project-a workspace"
- "Create a new workspace called personal"
- "Rename workspace dev to development"
- "Delete old-workspace"

### AI Agent Natural Language Operations

- "Show me what tasks I need to complete"
- "Add a task: Complete project documentation"
- "Mark task #1 as done"
- "Search for all tasks containing 'documentation'"
- "Delete task #5"
- "Can this task be broken down into more subtasks?"

### Real-time Synchronization

- Changes made in Web interface or via AI Agent are instantly synchronized
- Browser updates automatically without refresh
- Multiple browser windows/tabs stay in sync in real-time
- Workspace switches are synchronized across all clients
- Works with multiple devices on the same LAN

## Database Structure

Each workspace corresponds to an independent SQLite database file in the `workspaces/` directory:
- `workspaces/default.db` - Default workspace
- `workspaces/project-a.db` - Custom workspace
- `workspaces/personal.db` - Personal workspace
- ...

Current active workspace is saved in `workspaces/workspace_config.json`.

## Model Provider Architecture

The system uses a model provider abstraction layer that supports multiple LLM backends:

### Supported Providers

1. **Ollama** (Default)
   - Local LLM support
   - Supports `no_think` mode
   - Supports streaming responses

2. **OpenAI**
   - Cloud-based LLM support
   - Supports custom endpoints (e.g., Azure OpenAI)
   - Supports streaming responses

### Adding New Providers

To add a new model provider:

1. Create a new provider class in `model_providers/` implementing `ModelProvider` interface
2. Implement required methods: `chat()`, `convert_tools()`
3. Add provider creation logic in `model_providers/factory.py`
4. Update `agent_config.toml` validation in `task_agent.py`

See `model_providers/base.py` for the interface definition.

## Development

### Modify Frontend Code

```bash
# Edit src/app.tsx then rebuild
node build.js
```

### Running Tests

```bash
# Run model provider unit tests
python tests/test_model_providers.py

# Run integration tests
python tests/test_provider_integration.py
```
