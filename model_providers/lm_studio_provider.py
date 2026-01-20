#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LM Studio Model Provider Implementation

Implements LM Studio API using the OpenAI-compatible base class.
LM Studio uses OpenAI-compatible API, default port is 1234.
"""

from typing import Optional
from .openai_compatible_provider import OpenAICompatibleProvider


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
