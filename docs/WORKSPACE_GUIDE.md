# Workspace功能使用指南

## 概述

Workspace（工作区）功能允许你创建多个独立的todo列表环境，每个workspace有自己独立的数据库。这对于分离不同项目、不同上下文的任务非常有用。

## 核心概念

- **独立数据库**：每个workspace对应一个独立的SQLite数据库文件（存储在 `workspaces/` 目录）
- **当前workspace**：同一时间只有一个workspace是活动的，所有操作都在当前workspace上进行
- **自动创建**：切换到不存在的workspace时会自动创建
- **默认workspace**：系统默认创建名为 `default` 的工作区

## 使用场景

### 场景1：分离工作和生活
```
workspaces/
  ├── work.db        # 工作相关任务
  ├── personal.db    # 个人生活任务
  └── learning.db    # 学习计划
```

### 场景2：多项目管理
```
workspaces/
  ├── project-a.db   # 项目A的任务
  ├── project-b.db   # 项目B的任务
  └── backlog.db     # 待规划的想法
```

### 场景3：临时实验
```
workspaces/
  ├── default.db     # 主工作区
  ├── temp.db        # 临时测试
  └── archive.db     # 已完成项目归档
```

## Web界面操作

### 1. 查看和切换Workspace

在页面右上角：
- 下拉菜单显示所有workspace
- 当前活动的workspace会被选中
- 点击选择其他workspace可立即切换

### 2. 管理Workspace

点击 "⚙️ Manage" 按钮打开管理器：

**创建新Workspace：**
1. 在输入框中输入名称（只能使用字母、数字、下划线和连字符）
2. 点击 "➕ Create" 或按Enter键

**切换Workspace：**
1. 在列表中找到目标workspace
2. 点击 "Switch" 按钮

**重命名Workspace：**
1. 点击 "Rename" 按钮
2. 在弹出对话框中输入新名称

**删除Workspace：**
1. 首先切换到其他workspace（不能删除当前workspace）
2. 点击要删除的workspace的 "Delete" 按钮
3. 确认删除操作

## MCP/AI Agent操作

### 基本操作

**查看当前workspace：**
```
"我现在在哪个workspace？"
"当前工作区是什么？"
```

**列出所有workspace：**
```
"列出所有workspace"
"有哪些工作区？"
"show me all workspaces"
```

**切换workspace：**
```
"切换到work workspace"
"switch to project-a"
"使用personal工作区"
```

**创建新workspace：**
```
"创建一个新workspace叫做testing"
"create workspace project-c"
```

**删除workspace：**
```
"删除temp workspace"
"delete workspace old-project"
```
注意：不能删除当前活动的workspace

**重命名workspace：**
```
"把workspace dev重命名为development"
"rename workspace temp to experimental"
```

### 工作流示例

#### 示例1：开始新项目
```
AI: "创建一个workspace叫做website-redesign"
AI: "切换到website-redesign"
AI: "添加任务：设计新的首页布局"
AI: "添加任务：优化移动端体验"
AI: "list my tasks"  # 只显示website-redesign的任务
```

#### 示例2：切换上下文
```
# 正在工作区work中
AI: "list tasks"  # 看到工作任务

# 切换到个人事务
AI: "切换到personal workspace"
AI: "list tasks"  # 现在看到的是个人任务
AI: "添加任务：周末去超市购物"
```

#### 示例3：清理和归档
```
AI: "列出所有workspace"
AI: "切换到default"
AI: "删除temp workspace"  # 删除不再需要的临时工作区
AI: "把completed重命名为archive-2024"  # 归档已完成的工作
```

## 技术细节

### 文件结构
```
TaskMCP/
├── workspaces/              # 所有workspace数据库
│   ├── default.db          
│   ├── work.db             
│   ├── personal.db         
│   └── workspace_config.json    # 当前workspace配置
├── app.py                   # Web服务器
└── mcp_server.py           # MCP服务器
```

### workspaces/workspace_config.json
```json
{
  "current_workspace": "work"
}
```

### API端点

- `GET /api/workspaces` - 获取所有workspace和当前workspace
- `GET /api/workspace/current` - 获取当前workspace
- `POST /api/workspace/switch` - 切换workspace
- `POST /api/workspace/create` - 创建workspace
- `POST /api/workspace/delete` - 删除workspace
- `POST /api/workspace/rename` - 重命名workspace

### MCP工具

- `get_current_workspace_name()` - 获取当前workspace
- `list_all_workspaces()` - 列出所有workspace
- `switch_workspace(workspace_name)` - 切换workspace
- `create_workspace(workspace_name)` - 创建workspace
- `delete_workspace(workspace_name)` - 删除workspace
- `rename_workspace(old_name, new_name)` - 重命名workspace
