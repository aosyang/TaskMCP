#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenAI Compatible Provider Base Class

Base class for all OpenAI-compatible model providers (OpenAI, LM Studio, etc.).
Contains shared implementation for OpenAI-compatible APIs.
"""

import json
from abc import abstractmethod
from typing import List, Dict, Any, Optional, Callable
from .base import ModelProvider
from .response import ModelResponse, ToolCall

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None


class OpenAICompatibleProvider(ModelProvider):
    """Base class for OpenAI-compatible model providers
    
    This class contains the shared implementation for all providers that use
    OpenAI-compatible APIs. Subclasses only need to implement initialization
    and provider-specific configuration.
    """
    
    def __init__(self, model: str, base_url: str, api_key: Optional[str] = None, **kwargs):
        """Initialize OpenAI-compatible provider
        
        Args:
            model: Model name
            base_url: API base URL
            api_key: API key (optional, depends on provider)
            **kwargs: Other configuration parameters
        """
        if not OPENAI_AVAILABLE:
            raise ImportError(
                "OpenAI package not installed. Install it with: pip install openai"
            )
        
        super().__init__(model, **kwargs)
        self.api_key = api_key
        self.base_url = base_url
        
        # Create OpenAI client - subclasses can override _create_client if needed
        self.client = self._create_client(api_key, base_url)
    
    def _create_client(self, api_key: Optional[str], base_url: str):
        """Create OpenAI client instance
        
        Subclasses can override this to customize client creation.
        
        Args:
            api_key: API key (may be None for some providers)
            base_url: API base URL
            
        Returns:
            OpenAI client instance
        """
        # Default: use api_key if provided, otherwise use placeholder
        # Subclasses can override this behavior
        if api_key:
            return OpenAI(api_key=api_key, base_url=base_url)
        else:
            # Use placeholder for providers that don't require API key
            return OpenAI(api_key="openai-compatible", base_url=base_url)
    
    @abstractmethod
    def _get_provider_name(self) -> str:
        """Get provider name for error messages
        
        Returns:
            Provider name string (e.g., "OpenAI", "LM Studio")
        """
        pass
    
    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Any]] = None,
        **kwargs
    ) -> ModelResponse:
        """Call model for conversation
        
        Args:
            messages: Message history list
            tools: Tool list (should be OpenAI-format tool dictionary list)
            **kwargs: Other parameters (e.g., temperature, max_tokens, etc.)
        
        Returns:
            ModelResponse: Unified response object
        """
        # Prepare call parameters
        call_kwargs = {
            'model': self.model,
            'messages': messages,
        }
        
        # If tools are provided, add them to call parameters
        if tools is not None:
            call_kwargs['tools'] = tools
            # OpenAI-compatible API requires tool_choice to be specified (optional)
            # Default to let the model decide whether to use tools
            if 'tool_choice' not in kwargs:
                call_kwargs['tool_choice'] = 'auto'
        
        # Add other parameters (e.g., temperature, max_tokens, etc.)
        # Filter out tool_choice (already handled above)
        for key, value in kwargs.items():
            if key != 'tool_choice' or 'tool_choice' not in call_kwargs:
                call_kwargs[key] = value
        
        # Call API (using OpenAI-compatible interface)
        try:
            response = self.client.chat.completions.create(**call_kwargs)
        except Exception as e:
            # If call fails, return error response
            provider_name = self._get_provider_name()
            return ModelResponse(
                content=f"Error: Failed to call {provider_name} model: {str(e)}"
            )
        
        # Convert response format
        return self._convert_response(response)
    
    def _convert_response(self, api_response) -> ModelResponse:
        """Convert API response to unified ModelResponse format
        
        Args:
            api_response: Response object returned by API (OpenAI format)
        
        Returns:
            ModelResponse: Unified response object
        """
        provider_name = self._get_provider_name()
        
        # OpenAI-compatible response format: response.choices[0].message
        if not api_response.choices:
            return ModelResponse(content=f"Error: No response from {provider_name}")
        
        message = api_response.choices[0].message
        
        # Extract content
        content = message.content if hasattr(message, 'content') else None
        
        # Extract tool calls
        tool_calls = []
        if hasattr(message, 'tool_calls') and message.tool_calls:
            for tool_call in message.tool_calls:
                # OpenAI-compatible tool call format
                if hasattr(tool_call, 'function'):
                    func = tool_call.function
                    tool_name = func.name if hasattr(func, 'name') else None
                    # OpenAI-compatible API's arguments is a JSON string, needs parsing
                    tool_args_str = func.arguments if hasattr(func, 'arguments') else '{}'
                    
                    try:
                        # Try to parse JSON string
                        if isinstance(tool_args_str, str):
                            tool_args = json.loads(tool_args_str)
                        else:
                            tool_args = tool_args_str
                    except (json.JSONDecodeError, TypeError):
                        # If parsing fails, use empty dict
                        tool_args = {}
                    
                    # Extract tool_call_id (required by OpenAI-compatible API)
                    tool_call_id = tool_call.id if hasattr(tool_call, 'id') else None
                    
                    if tool_name:
                        tool_calls.append(ToolCall(name=tool_name, arguments=tool_args, tool_call_id=tool_call_id))
                elif isinstance(tool_call, dict):
                    # If it's a dict format (backward compatibility)
                    func = tool_call.get('function', {})
                    tool_name = func.get('name') if isinstance(func, dict) else None
                    tool_args_str = func.get('arguments', '{}') if isinstance(func, dict) else '{}'
                    
                    try:
                        if isinstance(tool_args_str, str):
                            tool_args = json.loads(tool_args_str)
                        else:
                            tool_args = tool_args_str
                    except (json.JSONDecodeError, TypeError):
                        tool_args = {}
                    
                    # Extract tool_call_id
                    tool_call_id = tool_call.get('id')
                    
                    if tool_name:
                        tool_calls.append(ToolCall(name=tool_name, arguments=tool_args, tool_call_id=tool_call_id))
        
        return ModelResponse(content=content, tool_calls=tool_calls)
    
    def convert_tools(
        self,
        tool_dicts: List[Dict[str, Any]],
        available_functions: Dict[str, Callable]
    ) -> List[Dict[str, Any]]:
        """Convert tool dictionaries to OpenAI-compatible format
        
        OpenAI-compatible APIs require JSON Schema format tool definitions.
        
        Args:
            tool_dicts: Tool dictionary list (Ollama format, should be compatible with OpenAI format)
            available_functions: Available functions dictionary (for generating tool definitions)
        
        Returns:
            OpenAI-compatible format tool list
        """
        # OpenAI-compatible tool format
        # Format: {"type": "function", "function": {"name": "...", "description": "...", "parameters": {...}}}
        
        if tool_dicts:
            # Validate and clean tool format
            compatible_tools = []
            for tool in tool_dicts:
                if isinstance(tool, dict):
                    # Ensure format is correct
                    if 'type' in tool and tool['type'] == 'function':
                        if 'function' in tool:
                            compatible_tools.append(tool)
                        else:
                            # If format is incorrect, try to fix it
                            # This shouldn't happen, but kept for robustness
                            compatible_tools.append({
                                'type': 'function',
                                'function': tool
                            })
                    else:
                        # If no type, assume the entire dict is a function definition
                        compatible_tools.append({
                            'type': 'function',
                            'function': tool
                        })
            return compatible_tools
        
        # If no tool dictionaries, try to generate from available_functions
        # This requires extracting information from function signatures, which is complex
        # For simplicity, return empty list (caller should provide tool dictionaries)
        return []
    
    def supports_no_think(self) -> bool:
        """OpenAI-compatible providers do not support no_think mode"""
        return False
    
    def supports_streaming(self) -> bool:
        """OpenAI-compatible providers support streaming responses"""
        return True
