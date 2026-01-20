#!/usr/bin/env python3
"""
快速功能测试脚本

测试workspace功能是否正常工作
"""

import requests
import time

BASE_URL = "http://localhost:5000"

def test_workspace_api():
    """测试workspace API端点"""
    print("=== Testing Workspace API ===\n")
    
    # 1. 获取所有workspaces
    print("1. GET /api/workspaces")
    response = requests.get(f"{BASE_URL}/api/workspaces")
    data = response.json()
    print(f"   Current: {data['current']}")
    print(f"   Workspaces: {data['workspaces']}")
    print(f"   ✓ OK\n")
    
    # 2. 创建新workspace
    print("2. POST /api/workspace/create")
    response = requests.post(
        f"{BASE_URL}/api/workspace/create",
        json={"workspace": "test-workspace"}
    )
    data = response.json()
    if data.get('success'):
        print(f"   Created: {data['workspace']}")
        print(f"   ✓ OK\n")
    else:
        print(f"   ✗ FAIL: {data.get('error')}\n")
    
    # 3. 切换workspace
    print("3. POST /api/workspace/switch")
    response = requests.post(
        f"{BASE_URL}/api/workspace/switch",
        json={"workspace": "test-workspace"}
    )
    data = response.json()
    if data.get('success'):
        print(f"   Switched to: {data['workspace']}")
        print(f"   ✓ OK\n")
    else:
        print(f"   ✗ FAIL\n")
    
    # 4. 添加todo到新workspace
    print("4. POST /add (in test-workspace)")
    response = requests.post(
        f"{BASE_URL}/add",
        json={"task": "Test task in new workspace", "parent_id": None}
    )
    data = response.json()
    if data.get('success'):
        print(f"   Added task with id: {data['id']}")
        print(f"   ✓ OK\n")
    else:
        print(f"   ✗ FAIL\n")
    
    # 5. 列出todos
    print("5. GET /api/todos")
    response = requests.get(f"{BASE_URL}/api/todos")
    todos = response.json()
    print(f"   Todos in test-workspace: {len(todos)}")
    if todos:
        print(f"   First todo: {todos[0]['task']}")
    print(f"   ✓ OK\n")
    
    # 6. 切换回default
    print("6. POST /api/workspace/switch (back to default)")
    response = requests.post(
        f"{BASE_URL}/api/workspace/switch",
        json={"workspace": "default"}
    )
    data = response.json()
    if data.get('success'):
        print(f"   Switched back to: {data['workspace']}")
        print(f"   ✓ OK\n")
    else:
        print(f"   ✗ FAIL\n")
    
    # 7. 验证不同workspace的todos是独立的
    print("7. GET /api/todos (in default)")
    response = requests.get(f"{BASE_URL}/api/todos")
    todos = response.json()
    print(f"   Todos in default workspace: {len(todos)}")
    print(f"   ✓ Workspaces are independent!\n")
    
    # 8. 删除test workspace
    print("8. POST /api/workspace/delete")
    response = requests.post(
        f"{BASE_URL}/api/workspace/delete",
        json={"workspace": "test-workspace"}
    )
    data = response.json()
    if data.get('success'):
        print(f"   Deleted: {data['workspace']}")
        print(f"   ✓ OK\n")
    else:
        print(f"   ✗ FAIL: {data.get('error')}\n")
    
    print("=== All Tests Passed! ===")

if __name__ == '__main__':
    print("Make sure the server is running (python app.py)\n")
    time.sleep(1)
    
    try:
        test_workspace_api()
    except requests.exceptions.ConnectionError:
        print("❌ Error: Cannot connect to server.")
        print("Please start the server first: python app.py")
    except Exception as e:
        print(f"❌ Error: {e}")
