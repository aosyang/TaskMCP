#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenAI Model Provider Implementation

Implements OpenAI API using the OpenAI-compatible base class.
"""

from typing import Optional
from .openai_compatible_provider import OpenAICompatibleProvider


class OpenAIProvider(OpenAICompatibleProvider):
    """OpenAI Model Provider Implementation"""
    
    def __init__(self, model: str, api_key: str, base_url: str = 'https://api.openai.com/v1', **kwargs):
        """Initialize OpenAI provider
        
        Args:
            model: Model name (e.g., 'gpt-4o', 'gpt-4o-mini')
            api_key: OpenAI API key (required)
            base_url: API base URL, defaults to https://api.openai.com/v1
            **kwargs: Other configuration parameters
        """
        if not api_key:
            raise ValueError("OpenAI API key is required")
        
        super().__init__(model=model, base_url=base_url, api_key=api_key, **kwargs)
    
    def _get_provider_name(self) -> str:
        """Get provider name for error messages"""
        return "OpenAI"
    
    def _create_client(self, api_key: Optional[str], base_url: str):
        """Create OpenAI client instance
        
        OpenAI requires API key, so we always use the provided api_key.
        
        Args:
            api_key: API key (required for OpenAI)
            base_url: API base URL
            
        Returns:
            OpenAI client instance
        """
        from openai import OpenAI
        return OpenAI(api_key=api_key, base_url=base_url)
