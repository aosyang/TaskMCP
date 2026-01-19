#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TaskMCP Agent Core - Common functionality for CLI and Telegram bot interfaces

This module provides shared agent logic for natural language task management
using Ollama models with tool calling capabilities.
"""

import os
import sys
import inspect
from typing import Dict, Callable, Optional, Tuple, Any
from datetime import datetime

# TOML support
try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # Python < 3.11
    except ImportError:
        tomllib = None

from ollama import Client

# Import all tool functions from MCP server
import mcp_server


def load_agent_config():
    """Load agent configuration from agent_config.toml
    
    Raises:
        FileNotFoundError: If agent_config.toml does not exist
        ValueError: If model is not specified in configuration
    """
    config_file = 'agent_config.toml'
    
    if not os.path.exists(config_file):
        raise FileNotFoundError(
            f"Configuration file '{config_file}' not found. "
            "Please create it with [ollama] section and model setting."
        )
    
    if tomllib is None:
        raise ImportError(
            "tomli not installed. Install it with: pip install tomli"
        )
    
    try:
        with open(config_file, 'rb') as f:
            config = tomllib.load(f)
    except Exception as e:
        raise ValueError(f"Could not load agent config: {e}")
    
    if not config or 'ollama' not in config:
        raise ValueError(
            f"Configuration file '{config_file}' must contain [ollama] section."
        )
    
    if 'model' not in config['ollama'] or not config['ollama']['model']:
        raise ValueError(
            f"Configuration file '{config_file}' must specify 'model' in [ollama] section."
        )
    
    return config


def extract_function(tool_obj):
    """Extract original function from FastMCP FunctionTool object"""
    if hasattr(tool_obj, 'fn'):
        return tool_obj.fn
    return tool_obj


# Time/Date utility functions
def get_current_time() -> str:
    """Get the current time
    
    Returns:
        Current time as string (HH:MM:SS)
    """
    return datetime.now().strftime('%H:%M:%S')


def get_current_date() -> str:
    """Get the current date
    
    Returns:
        Current date as string (YYYY-MM-DD)
    """
    return datetime.now().strftime('%Y-%m-%d')


def get_current_datetime() -> str:
    """Get the current date and time
    
    Returns:
        Current date and time as string (YYYY-MM-DD HH:MM:SS)
    """
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def get_available_functions() -> Dict[str, Callable]:
    """Get dictionary of all available tool functions
    
    Returns:
        Dictionary mapping function names to callable functions
    """
    return {
        # Workspace management
        'get_current_workspace_name': extract_function(mcp_server.get_current_workspace_name),
        'list_all_workspaces': extract_function(mcp_server.list_all_workspaces),
        'switch_workspace': extract_function(mcp_server.switch_workspace),
        'create_workspace': extract_function(mcp_server.create_workspace),
        'delete_workspace': extract_function(mcp_server.delete_workspace),
        'rename_workspace': extract_function(mcp_server.rename_workspace),
        
        # Task management
        'list_tasks': extract_function(mcp_server.list_tasks),
        'add_task': extract_function(mcp_server.add_task),
        'add_task_with_parent': extract_function(mcp_server.add_task_with_parent),
        'update_task': extract_function(mcp_server.update_task),
        'update_task_comments_from_file': extract_function(mcp_server.update_task_comments_from_file),
        'toggle_task': extract_function(mcp_server.toggle_task),
        'delete_task': extract_function(mcp_server.delete_task),
        'get_task': extract_function(mcp_server.get_task),
        'set_color': extract_function(mcp_server.set_color),
        'search_tasks': extract_function(mcp_server.search_tasks),
        'set_current_task': extract_function(mcp_server.set_current_task),
        'clear_current_task': extract_function(mcp_server.clear_current_task),
        'get_current_task': extract_function(mcp_server.get_current_task),
        'move_task_as_child': extract_function(mcp_server.move_task_as_child),
        'move_task_after': extract_function(mcp_server.move_task_after),
        'move_task': extract_function(mcp_server.move_task),
        'find_dangling_tasks': extract_function(mcp_server.find_dangling_tasks),
        
        # Time/Date utilities
        'get_current_time': get_current_time,
        'get_current_date': get_current_date,
        'get_current_datetime': get_current_datetime,
    }


def process_tool_calls(
    response,
    messages: list,
    client: Client,
    available_functions: Dict[str, Callable],
    model: Optional[str] = None,
    max_iterations: int = 10,
    before_chat_callback: Optional[Callable[[], None]] = None,
    after_chat_callback: Optional[Callable[[], None]] = None,
    on_tool_call: Optional[Callable[[str, dict], None]] = None,
    on_tool_call_after: Optional[Callable[[str, dict, Any], None]] = None
):
    """Process tool calling loop
    
    Args:
        response: Initial response from model containing tool calls
        messages: Message history list
        client: Ollama client instance
        available_functions: Dictionary of available tool functions
        model: Model name (if None, will be loaded from config)
        max_iterations: Maximum number of tool call iterations
        before_chat_callback: Optional callback to call before each chat request
        after_chat_callback: Optional callback to call after each chat request
    
    Returns:
        Tuple of (final_response, updated_messages)
    """
    if model is None:
        config = load_agent_config()
        model = config['ollama']['model']
    
    iteration = 0
    
    while response.message.tool_calls and iteration < max_iterations:
        iteration += 1
        
        # Add the response message containing tool calls to history (only once)
        messages.append(response.message.model_dump())
        
        # Process all tool calls
        for tool in response.message.tool_calls:
            tool_name = tool.function.name
            args = tool.function.arguments
            
            # Call tool call callback if provided
            if on_tool_call:
                try:
                    on_tool_call(tool_name, args)
                except Exception as e:
                    # Don't let callback errors break tool execution
                    pass
            
            if function_to_call := available_functions.get(tool_name):
                try:
                    # Execute function
                    # Handle parameter type conversion (FastMCP may serialize int as string)
                    converted_args = {}
                    for key, value in args.items():
                        # Check function signature, if int type parameter, try to convert
                        sig = inspect.signature(function_to_call)
                        param_type = sig.parameters.get(key)
                        if param_type and param_type.annotation == int:
                            converted_args[key] = int(value) if isinstance(value, str) else value
                        else:
                            converted_args[key] = value
                    
                    output = function_to_call(**converted_args)
                    
                    # Call tool call after callback if provided
                    if on_tool_call_after:
                        try:
                            on_tool_call_after(tool_name, args, output)
                        except Exception as e:
                            # Don't let callback errors break tool execution
                            pass
                    
                    # Add tool call result back to messages
                    messages.append({
                        'role': 'tool',
                        'content': str(output),
                        'tool_name': tool_name
                    })
                except Exception as e:
                    error_output = f'Error: {str(e)}'
                    
                    # Call tool call after callback with error if provided
                    if on_tool_call_after:
                        try:
                            on_tool_call_after(tool_name, args, error_output)
                        except Exception:
                            pass
                    
                    messages.append({
                        'role': 'tool',
                        'content': error_output,
                        'tool_name': tool_name
                    })
            else:
                error_msg = f'Tool {tool_name} not found'
                
                # Call tool call after callback with error if provided
                if on_tool_call_after:
                    try:
                        on_tool_call_after(tool_name, args, error_msg)
                    except Exception:
                        pass
                
                messages.append({
                    'role': 'tool',
                    'content': error_msg,
                    'tool_name': tool_name
                })
        
        # Get model's final response
        if before_chat_callback:
            before_chat_callback()
        
        try:
            response = client.chat(
                model=model,
                messages=messages,
                tools=list(available_functions.values()),
            )
        except Exception as e:
            # If error occurs, add error message and break
            messages.append({
                'role': 'assistant',
                'content': f'Error during model call: {str(e)}'
            })
            break
        finally:
            if after_chat_callback:
                after_chat_callback()
    
    return response, messages


def run_agent(
    query: str,
    model: Optional[str] = None,
    no_think: bool = False,
    messages: Optional[list] = None,
    return_text: bool = True,
    before_chat_callback: Optional[Callable[[], None]] = None,
    after_chat_callback: Optional[Callable[[], None]] = None,
    on_tool_call: Optional[Callable[[str, dict], None]] = None,
    on_tool_call_after: Optional[Callable[[str, dict, Any], None]] = None,
    language: Optional[str] = None
) -> Tuple[Optional[str], list]:
    """Run agent to process query
    
    Args:
        query: User query
        model: Model to use (defaults to config file value)
        no_think: Whether to disable thinking mode
        messages: Optional conversation history message list. If provided, will use it and add user message; otherwise create new conversation.
        return_text: If True, returns (response_text, messages); if False, returns (None, messages) for CLI compatibility
        before_chat_callback: Optional callback to call before each chat request
        after_chat_callback: Optional callback to call after each chat request
        language: Language code (e.g., 'zh', 'en'). If None, defaults to None (no language restriction) or user's configured language preference.
    
    Returns:
        Tuple of (response_text or None, updated_message_list)
    """
    if model is None:
        config = load_agent_config()
        model = config['ollama']['model']
    
    client = Client()
    available_functions = get_available_functions()
    
    # Import user_config for language support
    import user_config
    
    # Get language preference (default to None for no language restriction)
    if language is None:
        language = user_config.get_user_language(None)  # Get from config, or None if not set
    
    # Build system prompt with language-specific instruction (only if language is set)
    language_instruction = user_config.get_language_prompt(language)
    
    # Build base system prompt
    system_prompt = """You are a task management assistant that can help users manage tasks and workspaces."""
    
    # Add language instruction only if language is explicitly set
    if language_instruction:
        system_prompt += f"\n\n{language_instruction}"
    
    system_prompt += """

You can use the following tools to help users:
- Workspace management: view, switch, create, delete workspaces
- Task management: list, add, update, delete, search tasks
- Task operations: mark complete, set color, move tasks, etc.
- Time/Date utilities: get current time, date, or datetime

CRITICAL RULE - Task ID Verification:
When users refer to tasks by name or description (e.g., "Task 1", "Example task", "Project planning"), you MUST ALWAYS:
1. First use list_tasks or search_tasks to find the actual task IDs
2. Match the task names/descriptions to their corresponding database IDs
3. Only then use the correct task IDs for any operation

This rule applies to ALL operations that require task_id parameter:
- delete_task(task_id) - Delete a task
- update_task(task_id, ...) - Update task content/comments/color
- toggle_task(task_id) - Mark task as complete/incomplete
- set_color(task_id, color) - Set task background color
- get_task(task_id) - Get task details
- move_task(task_id, ...) - Move/reorder tasks
- move_task_as_child(task_id, as_child_of) - Move task as child
- move_task_after(task_id, after_task_id) - Move task after another
- set_current_task(task_id) - Set current working task

Task IDs are unique database identifiers, NOT sequential numbers or display order. 
A task named "Task 1" may have ID 41, not ID 1. 
A task named "Task 2" may have ID 42, not ID 2.
The task list display order does NOT correspond to task IDs.

NEVER assume task IDs based on:
- Task names containing numbers (e.g., "Task 1" ≠ ID 1)
- Display order in list_tasks output
- Sequential numbering in task descriptions
- Position in hierarchical structure

ALWAYS verify task IDs by:
- Calling list_tasks first to see the full task structure with IDs
- Using search_tasks to find tasks by name/description
- Matching the exact task name/description to its ID before any operation

When users need to perform task management operations, use the appropriate tools.
When users ask about the current time or date, use the time/date utility tools."""
    
    if no_think:
        system_prompt += "\n/no_think"
    
    # Build messages: if history messages provided, use them; otherwise create new conversation
    if messages is None:
        messages = [
            {'role': 'system', 'content': system_prompt},
        ]
    else:
        # Ensure system prompt exists (if not in history messages)
        if not messages or messages[0].get('role') != 'system':
            messages.insert(0, {'role': 'system', 'content': system_prompt})
    
    # Add user message
    messages.append({'role': 'user', 'content': query})
    
    # Call model with all tools
    if before_chat_callback:
        before_chat_callback()
    
    try:
        response = client.chat(
            model=model,
            messages=messages,
            tools=list(available_functions.values()),
        )
    except Exception as e:
        error_msg = f"Error: Failed to call model: {str(e)}"
        if return_text:
            return error_msg, messages
        else:
            return None, messages
    finally:
        if after_chat_callback:
            after_chat_callback()
    
    # Process tool calls
    if response.message.tool_calls:
        final_response, updated_messages = process_tool_calls(
            response,
            messages,
            client,
            available_functions,
            model,
            before_chat_callback=before_chat_callback,
            after_chat_callback=after_chat_callback,
            on_tool_call=on_tool_call,
            on_tool_call_after=on_tool_call_after
        )
        
        # Add final response to message history
        updated_messages.append(final_response.message.model_dump())
        
        if return_text:
            response_text = final_response.message.content if final_response.message.content else "Task completed successfully."
            return response_text, updated_messages
        else:
            return None, updated_messages
    else:
        # No tool calls, directly add response to history
        messages.append(response.message.model_dump())
        
        if return_text:
            response_text = response.message.content if response.message.content else "I understand."
            return response_text, messages
        else:
            return None, messages
