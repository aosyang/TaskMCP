#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TaskMCP Agent Core - Common functionality for CLI and Telegram bot interfaces

This module provides shared agent logic for natural language task management
using various model providers (Ollama, OpenAI, etc.) with tool calling capabilities.
"""

import os
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

# Import model provider abstraction
from model_providers import create_provider, ModelProvider, ModelResponse

# Import all tool functions from MCP server
import mcp_server

# Import tool registry system (optional - for new tool registration)
try:
    from tool_registry import get_registry
    # Import tools module to trigger auto-registration of all tools
    import tools  # This triggers initialize_tools() which registers all tools
    TOOL_REGISTRY_AVAILABLE = True
except ImportError:
    TOOL_REGISTRY_AVAILABLE = False


def load_agent_config():
    """Load agent configuration from agent_config.toml
    
    Supports both old format ([ollama] only) and new format ([provider] + provider-specific sections).
    For backward compatibility, if [provider] section is not present, defaults to "ollama".
    
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
    
    # Determine provider type
    if 'provider' in config and 'type' in config['provider']:
        provider_type = config['provider']['type']
    else:
        # Backward compatibility: default to ollama if [provider] section not present
        provider_type = 'ollama'
    
    # Validate provider-specific configuration
    if provider_type == 'ollama':
        if 'ollama' not in config:
            raise ValueError(
                f"Configuration file '{config_file}' must contain [ollama] section when provider type is 'ollama'."
            )
        if 'model' not in config['ollama'] or not config['ollama']['model']:
            raise ValueError(
                f"Configuration file '{config_file}' must specify 'model' in [ollama] section."
            )
    elif provider_type == 'openai':
        if 'openai' not in config:
            raise ValueError(
                f"Configuration file '{config_file}' must contain [openai] section when provider type is 'openai'."
            )
        if 'model' not in config['openai'] or not config['openai']['model']:
            raise ValueError(
                f"Configuration file '{config_file}' must specify 'model' in [openai] section."
            )
    elif provider_type == 'lm_studio':
        if 'lm_studio' not in config:
            raise ValueError(
                f"Configuration file '{config_file}' must contain [lm_studio] section when provider type is 'lm_studio'."
            )
        if 'model' not in config['lm_studio'] or not config['lm_studio']['model']:
            raise ValueError(
                f"Configuration file '{config_file}' must specify 'model' in [lm_studio] section."
            )
    else:
        raise ValueError(
            f"Unsupported provider type '{provider_type}'. Supported types: 'ollama', 'openai', 'lm_studio'"
        )
    
    # Store provider type in config for easy access
    config['_provider_type'] = provider_type
    
    return config


def extract_function(tool_obj):
    """Extract original function from FastMCP FunctionTool object"""
    if hasattr(tool_obj, 'fn'):
        return tool_obj.fn
    return tool_obj


def build_tool_dict(tool_obj):
    """Build tool description dictionary from FastMCP tool object
    
    Args:
        tool_obj: FastMCP FunctionTool object
        
    Returns:
        Dictionary in standard tool format (compatible with Ollama and OpenAI) with name, description, and parameters
    """
    if hasattr(tool_obj, 'name') and hasattr(tool_obj, 'description') and hasattr(tool_obj, 'parameters'):
        # FastMCP tool object
        return {
            'type': 'function',
            'function': {
                'name': tool_obj.name,
                'description': tool_obj.description,
                'parameters': tool_obj.parameters
            }
        }
    return None


def get_tool_dicts() -> list:
    """Get list of tool dictionaries from FastMCP tools
    
    Returns:
        List of tool dictionaries in standard format (compatible with Ollama and OpenAI)
    """
    # Use tool registry if available (new architecture)
    if TOOL_REGISTRY_AVAILABLE:
        try:
            registry = get_registry()
            return registry.get_tool_dicts()
        except Exception:
            # Fallback to old method if registry fails
            pass
    
    # Fallback to old method (backward compatibility)
    tools = []
    
    # Get FastMCP tools
    if hasattr(mcp_server.mcp, '_tool_manager'):
        tool_manager = mcp_server.mcp._tool_manager
        if hasattr(tool_manager, '_tools'):
            mcp_tools = tool_manager._tools
            
            for name, tool_obj in mcp_tools.items():
                tool_dict = build_tool_dict(tool_obj)
                if tool_dict:
                    tools.append(tool_dict)
    
    # Add manual tool definitions for non-FastMCP tools
    # Time/Date utilities
    time_tools = [
        {
            'type': 'function',
            'function': {
                'name': 'get_current_time',
                'description': 'Get the current time\n\nReturns:\n    Current time as string (HH:MM:SS)',
                'parameters': {
                    'type': 'object',
                    'properties': {},
                    'required': []
                }
            }
        },
        {
            'type': 'function',
            'function': {
                'name': 'get_current_date',
                'description': 'Get the current date\n\nReturns:\n    Current date as string (YYYY-MM-DD)',
                'parameters': {
                    'type': 'object',
                    'properties': {},
                    'required': []
                }
            }
        },
        {
            'type': 'function',
            'function': {
                'name': 'get_current_datetime',
                'description': 'Get the current date and time\n\nReturns:\n    Current date and time as string (YYYY-MM-DD HH:MM:SS)',
                'parameters': {
                    'type': 'object',
                    'properties': {},
                    'required': []
                }
            }
        }
    ]
    tools.extend(time_tools)
    
    return tools


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
    # Use tool registry if available (new architecture)
    if TOOL_REGISTRY_AVAILABLE:
        try:
            registry = get_registry()
            return registry.get_available_functions()
        except Exception:
            # Fallback to old method if registry fails
            pass
    
    # Fallback to old method (backward compatibility)
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
        'search_tasks': extract_function(mcp_server.search_tasks),
        'search_tasks_all_workspaces': extract_function(mcp_server.search_tasks_all_workspaces),
        'set_current_task': extract_function(mcp_server.set_current_task),
        'clear_current_task': extract_function(mcp_server.clear_current_task),
        'get_current_task': extract_function(mcp_server.get_current_task),
        'move_task_as_child': extract_function(mcp_server.move_task_as_child),
        'move_task_after': extract_function(mcp_server.move_task_after),
        'move_task_to_root': extract_function(mcp_server.move_task_to_root),
        'reorder_task': extract_function(mcp_server.reorder_task),
        'find_dangling_tasks': extract_function(mcp_server.find_dangling_tasks),
        
        # Time/Date utilities
        'get_current_time': get_current_time,
        'get_current_date': get_current_date,
        'get_current_datetime': get_current_datetime,
    }


def process_tool_calls(
    response: ModelResponse,
    messages: list,
    provider: ModelProvider,
    available_functions: Dict[str, Callable],
    tool_dicts: list,
    max_iterations: int = 10,
    before_chat_callback: Optional[Callable[[], None]] = None,
    after_chat_callback: Optional[Callable[[], None]] = None,
    on_tool_call: Optional[Callable[[str, dict], None]] = None,
    on_tool_call_after: Optional[Callable[[str, dict, Any], None]] = None
):
    """Process tool calling loop
    
    Args:
        response: Initial ModelResponse containing tool calls
        messages: Message history list
        provider: Model provider instance
        available_functions: Dictionary of available tool functions
        tool_dicts: List of tool dictionaries
        max_iterations: Maximum number of tool call iterations
        before_chat_callback: Optional callback to call before each chat request
        after_chat_callback: Optional callback to call after each chat request
    
    Returns:
        Tuple of (final_response, updated_messages)
    """
    iteration = 0
    
    while response.has_tool_calls() and iteration < max_iterations:
        iteration += 1
        
        # Add the response message containing tool calls to history (only once)
        messages.append(response.model_dump())
        
        # Process all tool calls
        for tool_call in response.tool_calls:
            tool_name = tool_call.function.name
            args = tool_call.function.arguments
            
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
                    # OpenAI requires tool_call_id, Ollama doesn't need it but it's harmless
                    tool_message = {
                        'role': 'tool',
                        'content': str(output),
                    }
                    if tool_call.id:
                        tool_message['tool_call_id'] = tool_call.id
                    messages.append(tool_message)
                except Exception as e:
                    error_output = f'Error: {str(e)}'
                    
                    # Call tool call after callback with error if provided
                    if on_tool_call_after:
                        try:
                            on_tool_call_after(tool_name, args, error_output)
                        except Exception:
                            pass
                    
                    # Add error result back to messages
                    tool_message = {
                        'role': 'tool',
                        'content': error_output,
                    }
                    if tool_call.id:
                        tool_message['tool_call_id'] = tool_call.id
                    messages.append(tool_message)
            else:
                error_msg = f'Tool {tool_name} not found'
                
                # Call tool call after callback with error if provided
                if on_tool_call_after:
                    try:
                        on_tool_call_after(tool_name, args, error_msg)
                    except Exception:
                        pass
                
                # Add error result back to messages
                tool_message = {
                    'role': 'tool',
                    'content': error_msg,
                }
                if tool_call.id:
                    tool_message['tool_call_id'] = tool_call.id
                messages.append(tool_message)
        
        # Get model's final response
        if before_chat_callback:
            before_chat_callback()
        
        # Convert tools to provider-specific format
        converted_tools = provider.convert_tools(tool_dicts, available_functions)
        
        try:
            # Call provider's chat method
            response = provider.chat(
                messages=messages,
                tools=converted_tools if converted_tools else None,
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
    # Load configuration and create provider
    config = load_agent_config()
    provider = create_provider(config)
    
    # Check no_think support
    if no_think and not provider.supports_no_think():
        # Warn but continue (no_think will be ignored)
        pass
    
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

You have access to various tools for task and workspace management. The tool definitions include complete parameter information (names, types, required/optional status) - use them exactly as specified.

CRITICAL RULE - Task ID Verification:
When users refer to tasks by name or description (e.g., "Task 1", "Example task", "Project planning"), you MUST ALWAYS:
1. First use list_tasks or search_tasks to find the actual task IDs
2. Match the task names/descriptions to their corresponding database IDs
3. Only then use the correct task IDs for any operation

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

Response Guidelines:
- When list_tasks is called, provide a concise summary of the task list. Do not add extensive operation suggestions unless the user explicitly asks for them.
- Keep responses focused and avoid unnecessary verbosity. Only provide additional suggestions if the user asks for help or guidance.
- When operations complete successfully, confirm briefly without repeating all available operations.

Cross-Workspace Search:
- Use search_tasks_all_workspaces(query) to search across all workspaces at once.
- For single workspace search, use search_tasks(query).

Use the appropriate tools based on user requests. All tool parameters are defined in the tool schemas - use them exactly as specified."""
    
    if no_think and provider.supports_no_think():
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
    
    # Get tool dictionaries (with structured parameters)
    tool_dicts = get_tool_dicts()
    
    # Convert tools to provider-specific format
    converted_tools = provider.convert_tools(tool_dicts, available_functions)
    
    try:
        # Call provider's chat method
        response = provider.chat(
            messages=messages,
            tools=converted_tools if converted_tools else None,
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
    if response.has_tool_calls():
        final_response, updated_messages = process_tool_calls(
            response,
            messages,
            provider,
            available_functions,
            tool_dicts,
            before_chat_callback=before_chat_callback,
            after_chat_callback=after_chat_callback,
            on_tool_call=on_tool_call,
            on_tool_call_after=on_tool_call_after
        )
        
        # Add final response to message history
        updated_messages.append(final_response.model_dump())
        
        if return_text:
            response_text = final_response.content if final_response.content else "Task completed successfully."
            return response_text, updated_messages
        else:
            return None, updated_messages
    else:
        # No tool calls, directly add response to history
        messages.append(response.model_dump())
        
        if return_text:
            response_text = response.content if response.content else "I understand."
            return response_text, messages
        else:
            return None, messages
