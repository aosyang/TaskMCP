#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tools Package - Tool registration and initialization

This module initializes all tools using the tool registry system.
Tools can be registered here or imported from other modules.
"""

from tool_registry import get_registry
from datetime import datetime

# Import MCP server tools
import mcp_server



def extract_function(tool_obj):
    """Extract original function from FastMCP FunctionTool object"""
    if hasattr(tool_obj, 'fn'):
        return tool_obj.fn
    return tool_obj


def initialize_tools():
    """Initialize and register all tools
    
    This function registers:
    1. FastMCP tools from mcp_server
    2. Built-in utility tools (time/date)
    3. Auto-discovered tools from tools/ directory
    """
    registry = get_registry()
    
    # Register FastMCP tools
    if hasattr(mcp_server.mcp, '_tool_manager'):
        tool_manager = mcp_server.mcp._tool_manager
        if hasattr(tool_manager, '_tools'):
            mcp_tools = tool_manager._tools
            
            for name, tool_obj in mcp_tools.items():
                if hasattr(tool_obj, 'name') and hasattr(tool_obj, 'description') and hasattr(tool_obj, 'parameters'):
                    # Register FastMCP tool
                    registry.register_manual(
                        name=tool_obj.name,
                        function=extract_function(tool_obj),
                        description=tool_obj.description,
                        parameters=tool_obj.parameters,
                        category="mcp"
                    )
    
    # Register time/date utility tools using decorator
    @registry.register(description="Get the current time\n\nReturns:\n    Current time as string (HH:MM:SS)", category="time")
    def get_current_time() -> str:
        """Get the current time"""
        return datetime.now().strftime('%H:%M:%S')
    
    @registry.register(description="Get the current date\n\nReturns:\n    Current date as string (YYYY-MM-DD)", category="time")
    def get_current_date() -> str:
        """Get the current date"""
        return datetime.now().strftime('%Y-%m-%d')
    
    @registry.register(description="Get the current date and time\n\nReturns:\n    Current date and time as string (YYYY-MM-DD HH:MM:SS)", category="time")
    def get_current_datetime() -> str:
        """Get the current date and time"""
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Auto-discover and import all tool modules in the tools/ directory
    # This allows tools to be automatically registered when added to the tools/ directory
    _auto_discover_tool_modules(registry)


def _auto_discover_tool_modules(registry):
    """Automatically discover and import all tool modules in the tools/ directory
    
    This function:
    1. Scans the tools/ directory for Python files (excluding __init__.py)
    2. Scans subdirectories for __init__.py files (package modules)
    3. Imports each module, which triggers @register_tool decorators
    4. Tools registered via decorators are automatically added to the registry
    
    To add a new tool:
    1. Create a new .py file in tools/ directory (e.g., tools/my_tools.py)
    2. Or create a subdirectory with __init__.py (e.g., tools/my_tools/__init__.py)
    3. Use @register_tool decorator to register tools
    4. The tool will be automatically discovered and registered on next import
    """
    import os
    import importlib
    import sys
    
    # Get the directory where this __init__.py file is located
    tools_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Get all Python files in the tools directory (excluding __init__.py)
    tool_modules = []
    for filename in os.listdir(tools_dir):
        filepath = os.path.join(tools_dir, filename)
        if os.path.isfile(filepath) and filename.endswith('.py') and filename != '__init__.py':
            module_name = filename[:-3]  # Remove .py extension
            tool_modules.append(module_name)
        elif os.path.isdir(filepath) and not filename.startswith('__'):
            # Check if it's a Python package (has __init__.py)
            init_file = os.path.join(filepath, '__init__.py')
            if os.path.exists(init_file):
                # It's a package, import it
                tool_modules.append(filename)
    
    # Import each module (this triggers @register_tool decorators)
    for module_name in tool_modules:
        try:
            # Import using relative import
            module = importlib.import_module(f'.{module_name}', package='tools')
            # Log successful import (optional, can be removed if too verbose)
            # logger.debug(f"Auto-discovered and imported tool module: {module_name}")
        except ImportError as e:
            # Log warning but don't fail - some modules might have optional dependencies
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Could not import tool module '{module_name}': {e}")
        except Exception as e:
            # Log other errors but continue
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Error importing tool module '{module_name}': {e}")


# Initialize tools when module is imported
initialize_tools()
