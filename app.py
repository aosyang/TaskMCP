from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO
import threading
import sys
import os

try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # Python < 3.11
    except ImportError:
        tomllib = None
        print("Warning: tomli not installed. Install it with: pip install tomli")

from workspace_manager import (
    get_current_workspace,
    set_current_workspace,
    list_workspaces,
    get_workspace_db_path,
    validate_workspace_name,
    init_db,
    get_db
)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'task-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

def build_tree(tasks, parent_id=None, current_task_id=None):
    """Build hierarchical tree structure from flat list"""
    tree = []
    for task in tasks:
        if task['parent_id'] == parent_id:
            children = build_tree(tasks, task['id'], current_task_id)
            tree.append({
                'id': task['id'],
                'task': task['task'],
                'done': bool(task['done']),
                'parent_id': task['parent_id'],
                'position': task['position'],
                'comments': task.get('comments', ''),
                'is_current': task['id'] == current_task_id,
                'children': children
            })
    return sorted(tree, key=lambda x: x['position'])

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/tasks')
def get_tasks():
    conn = get_db()
    cursor = conn.execute('SELECT * FROM tasks ORDER BY position')
    tasks = [dict(row) for row in cursor.fetchall()]
    
    # Get current task
    cursor = conn.execute('SELECT task_id FROM current_task WHERE id = 1')
    current = cursor.fetchone()
    current_task_id = current['task_id'] if current else None
    
    conn.close()
    tree = build_tree(tasks, None, current_task_id)
    return jsonify(tree)

@app.route('/add', methods=['POST'])
def add_task():
    data = request.get_json()
    task = data.get('task', '')
    parent_id = data.get('parent_id')
    
    if not task:
        return jsonify({'error': 'Task is required'}), 400
    
    conn = get_db()
    
    # Validate parent_id exists if provided
    if parent_id is not None:
        cursor = conn.execute('SELECT id FROM tasks WHERE id = ?', (parent_id,))
        if cursor.fetchone() is None:
            conn.close()
            return jsonify({'error': f'Parent task #{parent_id} does not exist'}), 400
    
    # Get max position for this parent
    cursor = conn.execute(
        'SELECT MAX(position) as max_pos FROM tasks WHERE parent_id IS ?',
        (parent_id,)
    )
    result = cursor.fetchone()
    position = (result['max_pos'] or -1) + 1
    
    cursor = conn.execute(
        'INSERT INTO tasks (task, parent_id, position) VALUES (?, ?, ?)',
        (task, parent_id, position)
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    
    socketio.emit('tasks_updated')
    return jsonify({'id': new_id, 'success': True})

@app.route('/edit/<int:id>', methods=['POST'])
def edit_task(id):
    data = request.get_json()
    task = data.get('task')
    comments = data.get('comments')
    
    conn = get_db()
    
    if task is not None:
        conn.execute('UPDATE tasks SET task = ? WHERE id = ?', (task, id))
    
    if comments is not None:
        conn.execute('UPDATE tasks SET comments = ? WHERE id = ?', (comments, id))
    
    conn.commit()
    conn.close()
    
    socketio.emit('tasks_updated')
    return jsonify({'success': True})

@app.route('/toggle/<int:id>')
def toggle_task(id):
    conn = get_db()
    cursor = conn.execute('SELECT done FROM tasks WHERE id = ?', (id,))
    row = cursor.fetchone()
    
    if row:
        new_done = 0 if row['done'] else 1
        conn.execute('UPDATE tasks SET done = ? WHERE id = ?', (new_done, id))
        conn.commit()
    
    conn.close()
    socketio.emit('tasks_updated')
    return jsonify({'success': True})

@app.route('/delete/<int:id>')
def delete_task(id):
    conn = get_db()
    
    # Delete recursively (children first)
    def delete_recursive(task_id):
        cursor = conn.execute('SELECT id FROM tasks WHERE parent_id = ?', (task_id,))
        children = cursor.fetchall()
        for child in children:
            delete_recursive(child['id'])
        conn.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
    
    delete_recursive(id)
    conn.commit()
    conn.close()
    
    socketio.emit('tasks_updated')
    return jsonify({'success': True})

@app.route('/reorder', methods=['POST'])
def reorder_tasks():
    """Batch update positions after drag-and-drop"""
    data = request.get_json()
    updates = data.get('updates', [])
    
    conn = get_db()
    for update in updates:
        conn.execute(
            'UPDATE tasks SET position = ?, parent_id = ? WHERE id = ?',
            (update['position'], update.get('parent_id'), update['id'])
        )
    conn.commit()
    conn.close()
    
    socketio.emit('tasks_updated')
    return jsonify({'success': True})

@app.route('/set_current/<int:task_id>', methods=['POST'])
def set_current_task(task_id):
    conn = get_db()
    # Clear existing current task and set new one
    conn.execute('DELETE FROM current_task WHERE id = 1')
    conn.execute('INSERT INTO current_task (id, task_id) VALUES (1, ?)', (task_id,))
    conn.commit()
    conn.close()
    
    socketio.emit('tasks_updated')
    return jsonify({'success': True})

@app.route('/clear_current', methods=['POST'])
def clear_current_task():
    conn = get_db()
    conn.execute('DELETE FROM current_task WHERE id = 1')
    conn.commit()
    conn.close()
    
    socketio.emit('tasks_updated')
    return jsonify({'success': True})

@app.route('/api/current_task')
def get_current_task():
    conn = get_db()
    cursor = conn.execute('SELECT task_id FROM current_task WHERE id = 1')
    current = cursor.fetchone()
    conn.close()
    
    if current:
        return jsonify({'task_id': current['task_id']})
    return jsonify({'task_id': None})

@app.route('/api/notify_update', methods=['POST'])
def notify_update():
    """Internal endpoint for MCP server to trigger socketio broadcast"""
    socketio.emit('tasks_updated')
    return jsonify({'success': True})

@app.route('/api/notify_workspace_changed', methods=['POST'])
def notify_workspace_changed_endpoint():
    """Internal endpoint for MCP server to trigger workspace_changed broadcast"""
    data = request.get_json() or {}
    workspace = data.get('workspace', '')
    socketio.emit('workspace_changed', {'workspace': workspace})
    return jsonify({'success': True})

# Workspace management APIs
@app.route('/api/workspaces')
def get_workspaces():
    """Get list of all workspaces and current workspace"""
    workspaces = list_workspaces()
    current = get_current_workspace()
    return jsonify({
        'workspaces': workspaces,
        'current': current
    })

@app.route('/api/workspace/current')
def get_current_workspace_api():
    """Get current workspace name"""
    return jsonify({'workspace': get_current_workspace()})

@app.route('/api/workspace/switch', methods=['POST'])
def switch_workspace():
    """Switch to a different workspace"""
    data = request.get_json()
    workspace_name = data.get('workspace')
    
    if not workspace_name:
        return jsonify({'error': 'Workspace name is required'}), 400
    
    if not validate_workspace_name(workspace_name):
        return jsonify({'error': 'Invalid workspace name'}), 400
    
    set_current_workspace(workspace_name)
    init_db(workspace_name)
    socketio.emit('tasks_updated')
    socketio.emit('workspace_changed', {'workspace': workspace_name})
    
    return jsonify({
        'success': True,
        'workspace': workspace_name
    })

@app.route('/api/workspace/create', methods=['POST'])
def create_workspace():
    """Create a new workspace"""
    data = request.get_json()
    workspace_name = data.get('workspace')
    
    if not workspace_name:
        return jsonify({'error': 'Workspace name is required'}), 400
    
    if not validate_workspace_name(workspace_name):
        return jsonify({'error': 'Invalid workspace name. Use only letters, numbers, underscore, and hyphen'}), 400
    
    db_path = get_workspace_db_path(workspace_name)
    if os.path.exists(db_path):
        return jsonify({'error': 'Workspace already exists'}), 400
    
    # Create and initialize the new workspace
    init_db(workspace_name)
    
    return jsonify({
        'success': True,
        'workspace': workspace_name
    })

@app.route('/api/workspace/delete', methods=['POST'])
def delete_workspace():
    """Delete a workspace"""
    data = request.get_json()
    workspace_name = data.get('workspace')
    
    if not workspace_name:
        return jsonify({'error': 'Workspace name is required'}), 400
    
    if workspace_name == get_current_workspace():
        return jsonify({'error': 'Cannot delete current workspace. Switch to another workspace first'}), 400
    
    db_path = get_workspace_db_path(workspace_name)
    if not os.path.exists(db_path):
        return jsonify({'error': 'Workspace not found'}), 404
    
    # Delete the database file
    os.remove(db_path)
    
    return jsonify({
        'success': True,
        'workspace': workspace_name
    })

@app.route('/api/workspace/rename', methods=['POST'])
def rename_workspace():
    """Rename a workspace"""
    data = request.get_json()
    old_name = data.get('old_name')
    new_name = data.get('new_name')
    
    if not old_name or not new_name:
        return jsonify({'error': 'Both old_name and new_name are required'}), 400
    
    if not validate_workspace_name(new_name):
        return jsonify({'error': 'Invalid workspace name. Use only letters, numbers, underscore, and hyphen'}), 400
    
    old_path = get_workspace_db_path(old_name)
    new_path = get_workspace_db_path(new_name)
    
    if not os.path.exists(old_path):
        return jsonify({'error': 'Workspace not found'}), 404
    
    if os.path.exists(new_path):
        return jsonify({'error': 'New workspace name already exists'}), 400
    
    # Rename the database file
    os.rename(old_path, new_path)
    
    # Update current workspace if it was renamed
    if old_name == get_current_workspace():
        set_current_workspace(new_name)
    
    socketio.emit('workspace_changed', {'workspace': new_name})
    
    return jsonify({
        'success': True,
        'old_name': old_name,
        'new_name': new_name
    })

def start_mcp_server():
    """Start MCP server in background thread"""
    # Import mcp_server module and run it
    sys.path.insert(0, os.path.dirname(__file__))
    from mcp_server import mcp
    print("Starting MCP server on http://localhost:8000")
    mcp.run(transport="http")

def load_server_config():
    """Load server configuration from server_config.toml"""
    config_file = 'server_config.toml'
    default_config = {
        'host': 'localhost',
        'port': 5000
    }
    
    if os.path.exists(config_file):
        try:
            if tomllib is None:
                print("Warning: tomli not installed. Using default configuration.")
                print("Install it with: pip install tomli")
                return default_config
            
            with open(config_file, 'rb') as f:
                config = tomllib.load(f)
                if config:
                    # Merge with defaults to ensure all keys exist
                    default_config.update(config)
                return default_config
        except Exception as e:
            print(f"Warning: Could not load server config: {e}")
            print("Using default configuration")
    
    return default_config

if __name__ == '__main__':
    current_ws = get_current_workspace()
    init_db(current_ws)
    
    # Load server configuration
    server_config = load_server_config()
    host = server_config.get('host', 'localhost')
    port = server_config.get('port', 5000)
    
    # Start MCP server in background thread (only if not already running)
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', 8000))
        sock.close()
        
        if result != 0:
            # Port 8000 is not in use, start MCP server
            mcp_thread = threading.Thread(target=start_mcp_server, daemon=True)
            mcp_thread.start()
        else:
            print("MCP server already running on port 8000")
    except Exception as e:
        print(f"Could not check MCP server: {e}")
    
    import socket
    print("Starting Flask web server:")
    if host == '0.0.0.0':
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            print(f"  - Local: http://localhost:{port}")
            print(f"  - Network: http://{local_ip}:{port}")
            print(f"  - All interfaces: http://0.0.0.0:{port}")
        except Exception:
            print(f"  - Listening on all interfaces: http://0.0.0.0:{port}")
    else:
        print(f"  - Local only: http://localhost:{port}")
        print("  (Network access disabled)")
    
    socketio.run(app, host=host, debug=True, port=port, use_reloader=False, allow_unsafe_werkzeug=True)
