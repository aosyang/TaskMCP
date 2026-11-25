#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LM Studio Model Provider Implementation

Implements LM Studio API using the OpenAI-compatible base class.
LM Studio uses OpenAI-compatible API, default port is 1234.
"""

from typing import Optional, List, Dict, Any
from .openai_compatible_provider import OpenAICompatibleProvider
from .response import ModelResponse


class LMStudioProvider(OpenAICompatibleProvider):
    """LM Studio Model Provider Implementation
    
    LM Studio uses OpenAI-compatible API, so we can use the OpenAI client library.
    Default service address is http://localhost:1234/v1
    """
    
    def __init__(self, model: str, base_url: str = 'http://localhost:1234/v1', api_key: Optional[str] = None, **kwargs):
        """Initialize LM Studio provider
        
        Args:
            model: Model name (the model name loaded in LM Studio)
            base_url: API base URL, defaults to http://localhost:1234/v1
            api_key: API key (optional, LM Studio defaults to no API key required)
            **kwargs: Other configuration parameters
        """
        super().__init__(model=model, base_url=base_url, api_key=api_key, **kwargs)
    
    def _get_provider_name(self) -> str:
        """Get provider name for error messages"""
        return "LM Studio"
    
    def _create_client(self, api_key: Optional[str], base_url: str):
        """Create OpenAI client instance
        
        LM Studio defaults to no API key, so we use a placeholder if none is provided.
        
        Args:
            api_key: API key (optional for LM Studio)
            base_url: API base URL
            
        Returns:
            OpenAI client instance
        """
        from openai import OpenAI
        # If api_key is provided, use it; otherwise use a placeholder (LM Studio defaults to no API key)
        if api_key:
            return OpenAI(api_key=api_key, base_url=base_url)
        else:
            # LM Studio defaults to no API key, but OpenAI client may need a placeholder
            # Use a placeholder value
            return OpenAI(api_key="lm-studio", base_url=base_url)

    def _normalize_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalize messages for LM Studio template compatibility

        LM Studio's Jinja template checks for alternating user/assistant roles.
        When assistant messages have tool_calls but empty content, the template
        may incorrectly flag this as a violation. This method ensures assistant
        messages always have non-empty content (at least a space) when they have
        tool_calls.

        Args:
            messages: Original message list

        Returns:
            Normalized message list
        """
        normalized = []
        for msg in messages:
            msg_copy = msg.copy()

            # For assistant messages with tool_calls, ensure content is not empty
            if (msg_copy.get('role') == 'assistant' and
                msg_copy.get('tool_calls') and
                (not msg_copy.get('content') or msg_copy.get('content') == '')):
                # Set content to a space to ensure it's not empty
                # This helps the template validation pass while keeping the message structure
                msg_copy['content'] = ' '

            normalized.append(msg_copy)

        return normalized

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Any]] = None,
        **kwargs
    ) -> ModelResponse:
        """Call model for conversation with message normalization

        Overrides parent class to normalize messages before sending to LM Studio.
        This ensures compatibility with LM Studio's Jinja template validation.

        Args:
            messages: Message history list
            tools: Tool list (should be OpenAI-format tool dictionary list)
            **kwargs: Other parameters (e.g., temperature, max_tokens, etc.)

        Returns:
            ModelResponse: Unified response object
        """
        # Normalize messages for LM Studio template compatibility
        normalized_messages = self._normalize_messages(messages)

        # Call parent class method with normalized messages
        return super().chat(normalized_messages, tools=tools, **kwargs)
