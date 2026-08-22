#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tool Registry - Universal tool registration system for easy tool extension

This module provides a unified tool registration system that allows easy extension
of tools for model providers. Tools can be registered using decorators or manually,
and the system automatically generates tool definitions from function signatures.
"""

import inspect
import json
from typing import Dict, Callable, Optional, List, get_type_hints
from dataclasses import dataclass
from pydantic import TypeAdapter


@dataclass
class ToolDefinition:
    """Tool definition with metadata"""
    name: str
    function: Callable
    description: str
    parameters: dict
    category: Optional[str] = None  # Optional category for grouping tools


class ToolRegistry:
    """Universal tool registry for managing all available tools"""
    
    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}
        self._categories: Dict[str, List[str]] = {}  # category -> [tool_names]
    
    def register(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[str] = None
    ):
        """Decorator to register a tool
        
        Args:
            name: Tool name (defaults to function name)
            description: Tool description (defaults to function docstring)
            category: Optional category for grouping
        
        Example:
            @registry.register(description="Get current time", category="time")
            def get_current_time() -> str:
                return datetime.now().strftime('%H:%M:%S')
        """
        def decorator(func: Callable):
            tool_name = name or func.__name__
            tool_description = description or (func.__doc__ or "").strip()
            
            # Auto-generate parameters from function signature
            parameters = self._generate_parameters(func)
            
            tool_def = ToolDefinition(
                name=tool_name,
                function=func,
                description=tool_description,
                parameters=parameters,
                category=category
            )
            
            self._tools[tool_name] = tool_def
            
            # Track by category
            if category:
                if category not in self._categories:
                    self._categories[category] = []
                self._categories[category].append(tool_name)
            
            return func
        
        return decorator
    
    def register_manual(
        self,
        name: str,
        function: Callable,
        description: str,
        parameters: dict,
        category: Optional[str] = None
    ):
        """Manually register a tool with custom definition
        
        Args:
            name: Tool name
            function: Callable function
            description: Tool description
            parameters: Tool parameters schema (OpenAI format)
            category: Optional category
        
        Example:
            registry.register_manual(
                name="search_web",
                function=search_web,
                description="Search the web",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "timeout": {"type": "integer", "default": 60}
                    },
                    "required": ["query"]
                },
                category="web"
            )
        """
        tool_def = ToolDefinition(
            name=name,
            function=function,
            description=description,
            parameters=parameters,
            category=category
        )
        
        self._tools[name] = tool_def
        
        if category:
            if category not in self._categories:
                self._categories[category] = []
            self._categories[category].append(name)
    
    def _generate_parameters(self, func: Callable) -> dict:
        """Generate JSON Schema from Python annotations using Pydantic.

        Unions, Optional, Literal, collections, dataclasses, and Pydantic models
        remain machine-readable instead of degrading unknown annotations to strings.
        """
        sig = inspect.signature(func)
        try:
            hints = get_type_hints(func, include_extras=True)
        except Exception:
            hints = {}
        properties = {}
        required = []
        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue
            annotation = hints.get(param_name, param.annotation)
            if annotation is inspect.Parameter.empty:
                param_schema = self._schema_from_default(param.default)
            else:
                try:
                    param_schema = TypeAdapter(annotation).json_schema()
                except Exception:
                    param_schema = self._schema_from_default(param.default)
            if param.default == inspect.Parameter.empty:
                required.append(param_name)
            else:
                try:
                    json.dumps(param.default)
                    param_schema = dict(param_schema)
                    param_schema['default'] = param.default
                except (TypeError, ValueError):
                    pass
            properties[param_name] = param_schema
        return {'type': 'object', 'properties': properties, 'required': required}

    @staticmethod
    def _schema_from_default(default) -> dict:
        if default is inspect.Parameter.empty:
            return {}
        if default is None:
            return {'type': 'null'}
        mapping = {str: 'string', int: 'integer', float: 'number', bool: 'boolean', list: 'array', dict: 'object'}
        json_type = mapping.get(type(default))
        return {'type': json_type} if json_type else {}
    
    def _get_parameter_type(self, param: inspect.Parameter) -> str:
        """Backward-compatible simple type helper; full schemas use Pydantic."""
        annotation = param.annotation
        if annotation is not inspect.Parameter.empty:
            try:
                schema = TypeAdapter(annotation).json_schema()
                if isinstance(schema.get('type'), str):
                    return schema['type']
            except Exception:
                pass
        schema = self._schema_from_default(param.default)
        return schema.get('type', 'string')
    
    def get_tool_dicts(self) -> List[dict]:
        """Get all tools as dictionaries in OpenAI format
        
        Returns:
            List of tool dictionaries
        """
        tools = []
        for tool_def in self._tools.values():
            tools.append({
                'type': 'function',
                'function': {
                    'name': tool_def.name,
                    'description': tool_def.description,
                    'parameters': tool_def.parameters
                }
            })
        return tools
    
    def get_available_functions(self) -> Dict[str, Callable]:
        """Get dictionary mapping tool names to functions
        
        Returns:
            Dictionary of {tool_name: function}
        """
        return {name: tool_def.function for name, tool_def in self._tools.items()}
    
    def get_tools_by_category(self, category: str) -> List[str]:
        """Get tool names in a specific category
        
        Args:
            category: Category name
        
        Returns:
            List of tool names
        """
        return self._categories.get(category, [])
    
    def get_all_categories(self) -> List[str]:
        """Get all registered categories
        
        Returns:
            List of category names
        """
        return list(self._categories.keys())
    
    def has_tool(self, name: str) -> bool:
        """Check if a tool is registered
        
        Args:
            name: Tool name
        
        Returns:
            True if tool exists
        """
        return name in self._tools
    
    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """Get tool definition by name
        
        Args:
            name: Tool name
        
        Returns:
            ToolDefinition or None
        """
        return self._tools.get(name)
    
    def unregister(self, name: str) -> bool:
        """Unregister a tool
        
        Args:
            name: Tool name
        
        Returns:
            True if tool was removed, False if not found
        """
        if name not in self._tools:
            return False
        
        tool_def = self._tools[name]
        
        # Remove from category
        if tool_def.category and tool_def.category in self._categories:
            if name in self._categories[tool_def.category]:
                self._categories[tool_def.category].remove(name)
            if not self._categories[tool_def.category]:
                del self._categories[tool_def.category]
        
        del self._tools[name]
        return True
    
    def clear(self):
        """Clear all registered tools"""
        self._tools.clear()
        self._categories.clear()


# Global registry instance
_registry = ToolRegistry()


def get_registry() -> ToolRegistry:
    """Get the global tool registry instance
    
    Returns:
        ToolRegistry instance
    """
    return _registry


# Convenience functions for backward compatibility
def register_tool(name: Optional[str] = None, description: Optional[str] = None, category: Optional[str] = None):
    """Convenience decorator for registering tools
    
    Example:
        @register_tool(description="Get current time", category="time")
        def get_current_time() -> str:
            return datetime.now().strftime('%H:%M:%S')
    """
    return _registry.register(name=name, description=description, category=category)


def register_manual_tool(
    name: str,
    function: Callable,
    description: str,
    parameters: dict,
    category: Optional[str] = None
):
    """Convenience function for manually registering tools"""
    _registry.register_manual(name, function, description, parameters, category)
