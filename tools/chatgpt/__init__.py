#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChatGPT Tools - Web search tool using ChatGPT endpoint

This module provides web search functionality using the ChatGPT endpoint.
"""

from tool_registry import register_tool

# Import ChatGPT client (with fallback)
try:
    from .client import search_web as _search_web_impl
    HAS_CHATGPT_CLIENT = True
except ImportError:
    HAS_CHATGPT_CLIENT = False
    def _search_web_impl(query: str, timeout: int = 60) -> str:
        return "Error: chatgpt_client module not available. Cannot perform web search."


@register_tool(
    name="chatgpt_web_search",
    description="Search the web or ask questions using ChatGPT endpoint. Use this when users ask about current events, need information from the internet, or want to search for something online.",
    category="web"
)
def chatgpt_web_search(query: str, timeout: int = 60) -> str:
    """Search the web using ChatGPT endpoint
    
    This tool calls the ChatGPT endpoint to perform web searches and get 
    information from the internet. It supports both synchronous and asynchronous 
    request modes.
    
    Args:
        query: Search query or question to ask ChatGPT
        timeout: Timeout in seconds for the request (default: 60)
    
    Returns:
        Response text from ChatGPT, or error message if request fails
    """
    if not HAS_CHATGPT_CLIENT:
        return "Error: chatgpt_client module not available. Cannot perform web search."
    
    return _search_web_impl(query, timeout)
