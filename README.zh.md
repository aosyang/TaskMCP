# TaskMCP

一个支持层级结构、拖拽排序、实时同步、多工作区的任务管理系统，同时提供MCP服务器让AI Agent能够通过自然语言操作任务。

## 功能特性

### Web界面 (http://localhost:5000)
- **多工作区支持** - 每个workspace对应独立的数据库，互不干扰
- 层级任务结构（支持无限层级子任务）
- 拖拽排序
- 任务标记完成/未完成
- 任务备注/评论（支持Markdown）
- 内联编辑任务名称
- WebSocket实时同步（多客户端实时更新）
- 两种视图模式：列表视图和画布视图

### MCP服务器 (http://localhost:8000)

**Workspace管理工具：**
- `get_current_workspace_name` - 获取当前工作区名称
- `list_all_workspaces` - 列出所有工作区
- `switch_workspace` - 切换工作区（自动创建不存在的工作区）
- `create_workspace` - 创建新工作区
- `delete_workspace` - 删除工作区
- `rename_workspace` - 重命名工作区

**Task管理工具：**
- `list_tasks` - 列出当前工作区的所有任务（层级显示）
- `add_task` - 添加新任务（可指定parent_id创建子任务）
- `update_task` - 更新任务描述或备注
- `toggle_task` - 切换完成状态
- `delete_task` - 删除任务及其子任务
- `get_task` - 获取任务详情
- `search_tasks` - 搜索任务
- `move_task` - 移动任务位置
- `set_current_task` - 设置当前工作任务
- `clear_current_task` - 清除当前工作任务
- `get_current_task` - 获取当前工作任务

## 技术栈

**后端：**
- Flask - Web框架
- Flask-SocketIO - WebSocket实时通信
- SQLite3 - 数据库
- FastMCP - MCP服务器框架

**前端：**
- React 18 + TypeScript
- @dnd-kit - 拖拽排序
- Socket.IO Client - 实时更新
- esbuild - 构建工具

## 安装运行

### 1. 安装依赖

```bash
# Python依赖
pip install flask flask-socketio fastmcp

# Python < 3.11 需要额外安装 TOML 支持
pip install tomli

# Node.js依赖
npm install
```

### 2. 配置服务器访问模式（可选）

编辑 `server_config.toml` 文件来配置服务器访问模式：

```toml
host = "localhost"
port = 5000
```

**配置说明：**
- `host`: 绑定地址（默认：`localhost`）
  - `localhost` 或 `127.0.0.1` - 只允许本机访问
  - `0.0.0.0` - 绑定到所有网络接口（允许局域网和其他设备访问）
- `port`: 服务器端口号（默认：5000）

**示例：**
- 只允许本机访问：`host = "localhost"`
- 允许局域网访问：`host = "0.0.0.0"`

**注意：** Python 3.11+ 内置支持 TOML，Python < 3.11 需要安装 tomli 库：`pip install tomli`

### 3. 启动服务器

```bash
# 一键启动（同时启动Web服务器和MCP服务器）
python app.py
```

服务器启动后：
- Web界面: 
  - 本地访问: http://localhost:5000
  - 局域网访问: http://<你的IP地址>:5000 (如果允许网络访问，启动时会显示)
- MCP服务器: http://localhost:8000/mcp

### 4. 配置MCP客户端

在VS Code中使用，配置文件 `.vscode/mcp.json`：

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

## 使用示例

### Workspace管理

在Web界面：
1. 点击右上角的workspace下拉菜单选择不同工作区
2. 点击"Manage"按钮打开工作区管理器
3. 可以创建、重命名、删除工作区

通过MCP/AI Agent：
- "当前是哪个workspace？"
- "列出所有workspace"
- "切换到project-a workspace"
- "创建一个新的workspace叫做personal"
- "把workspace dev重命名为development"
- "删除old-workspace"

### AI Agent自然语言操作

- "看一下我现在有哪些task要完成"
- "帮我添加一个任务：完成项目文档"
- "把任务#1标记为完成"
- "搜索包含'文档'的所有任务"
- "删除任务#5"
- "看看这个任务能不能拆解更多子任务"

### 实时同步

- Web界面或AI Agent的更改会立即同步
- 浏览器自动更新，无需刷新
- 多个浏览器窗口/标签页实时保持同步
- 工作区切换会在所有客户端之间同步
- 支持同一局域网内的多个设备

## 数据库结构

每个workspace对应一个独立的SQLite数据库文件，存储在 `workspaces/` 目录下：
- `workspaces/default.db` - 默认工作区
- `workspaces/project-a.db` - 自定义工作区
- `workspaces/personal.db` - 个人工作区
- ...

当前活动的workspace配置保存在 `workspaces/workspace_config.json` 文件中。

## 开发

### 修改前端代码

```bash
# 编辑 src/app.tsx 后重新构建
node build.js
```