"""Shared workspace management utilities for both Flask and MCP server"""
import os
import json
import sqlite3

WORKSPACES_DIR = 'workspaces'
DEFAULT_WORKSPACE = 'default'
WORKSPACE_CONFIG_FILE = os.path.join(WORKSPACES_DIR, 'workspace_config.json')

def ensure_workspaces_dir():
    """Ensure workspaces directory exists"""
    if not os.path.exists(WORKSPACES_DIR):
        os.makedirs(WORKSPACES_DIR)

def get_workspace_db_path(workspace_name):
    """Get database path for a workspace"""
    ensure_workspaces_dir()
    return os.path.join(WORKSPACES_DIR, f'{workspace_name}.db')

def load_workspace_config():
    """Load workspace configuration"""
    ensure_workspaces_dir()
    # Check for old config file in root directory (migration)
    old_config_file = 'workspace_config.json'
    if os.path.exists(old_config_file) and not os.path.exists(WORKSPACE_CONFIG_FILE):
        # Migrate old config to workspaces directory
        with open(old_config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        save_workspace_config(config)
        # Optionally remove old file (comment out if you want to keep it as backup)
        # os.remove(old_config_file)
    
    if os.path.exists(WORKSPACE_CONFIG_FILE):
        with open(WORKSPACE_CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'current_workspace': DEFAULT_WORKSPACE}

def save_workspace_config(config):
    """Save workspace configuration"""
    ensure_workspaces_dir()
    with open(WORKSPACE_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)

def get_current_workspace():
    """Get current workspace name"""
    config = load_workspace_config()
    return config.get('current_workspace', DEFAULT_WORKSPACE)

def set_current_workspace(workspace_name):
    """Set current workspace"""
    config = load_workspace_config()
    config['current_workspace'] = workspace_name
    save_workspace_config(config)

def list_workspaces():
    """List all available workspaces"""
    ensure_workspaces_dir()
    workspaces = []
    for file in os.listdir(WORKSPACES_DIR):
        if file.endswith('.db'):
            workspaces.append(file[:-3])  # Remove .db extension
    if not workspaces:
        workspaces = [DEFAULT_WORKSPACE]
    return sorted(workspaces)

def validate_workspace_name(workspace_name):
    """Validate workspace name format
    
    Args:
        workspace_name: Name to validate
        
    Returns:
        True if valid, False otherwise
    """
    return workspace_name and all(c.isalnum() or c in ('_', '-') for c in workspace_name)

def init_db(workspace_name):
    """Initialize database for a workspace
    
    Args:
        workspace_name: Name of the workspace to initialize
    """
    db_path = get_workspace_db_path(workspace_name)
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task TEXT NOT NULL,
            done INTEGER DEFAULT 0,
            parent_id INTEGER,
            position INTEGER DEFAULT 0,
            comments TEXT DEFAULT '',
            color TEXT DEFAULT '',
            board_x REAL DEFAULT 0,
            board_y REAL DEFAULT 0,
            board_width REAL DEFAULT 240,
            board_height REAL DEFAULT 100,
            children_layout TEXT DEFAULT 'vertical',
            children_comment_display TEXT DEFAULT 'compact'
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS current_task (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            task_id INTEGER
        )
    ''')
    conn.commit()
    conn.close()

def get_db(workspace_name=None):
    """Get database connection for a workspace
    
    Args:
        workspace_name: Name of workspace, uses current if None
        
    Returns:
        sqlite3.Connection with row_factory set
    """
    if workspace_name is None:
        workspace_name = get_current_workspace()
    db_path = get_workspace_db_path(workspace_name)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn
