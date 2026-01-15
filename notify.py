"""Shared notification system for database updates"""
import requests

FLASK_SOCKETIO_URL = "http://localhost:5000"

def notify_tasks_updated():
    """Notify Flask to broadcast tasks_updated event via SocketIO"""
    try:
        # Create a special endpoint to trigger socketio emit
        requests.post(f"{FLASK_SOCKETIO_URL}/api/notify_update", timeout=0.5)
    except:
        pass  # Fail silently if Flask is not running

def notify_workspace_changed(workspace_name):
    """Notify Flask to broadcast workspace_changed event via SocketIO"""
    try:
        requests.post(f"{FLASK_SOCKETIO_URL}/api/notify_workspace_changed", 
                     json={'workspace': workspace_name}, timeout=0.5)
    except:
        pass  # Fail silently if Flask is not running
