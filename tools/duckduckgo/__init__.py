#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DuckDuckGo Tools - Web search tool using DuckDuckGo

This module provides web search functionality using DuckDuckGo search.
"""

from tool_registry import register_tool

# Import DuckDuckGo client (with fallback)
try:
    from .client import search_web as _search_web_impl
    from .client import search_images as _search_images_impl
    HAS_DUCKDUCKGO = True
except ImportError:
    HAS_DUCKDUCKGO = False
    def _search_web_impl(query: str, max_results: int = 5) -> str:
        return "Error: ddgs module not available. Please install it with: pip install ddgs"
    def _search_images_impl(query: str, max_results: int = 5) -> str:
        return "Error: ddgs module not available. Please install it with: pip install ddgs"


@register_tool(
    name="duckduckgo_web_search",
    description="Search the web using DuckDuckGo search engine. Use this when you need to find current information, news, or search the internet. DuckDuckGo is a privacy-focused search engine that doesn't track users.",
    category="web"
)
def duckduckgo_web_search(query: str, max_results: int = 5) -> str:
    """Search the web using DuckDuckGo
    
    This tool uses DuckDuckGo to perform web searches and retrieve 
    information from the internet. DuckDuckGo is privacy-focused and 
    doesn't track users.
    
    Args:
        query: Search query string
        max_results: Maximum number of results to return (default: 5)
    
    Returns:
        Formatted search results with titles, URLs, and snippets, or error message if search fails
    """
    if not HAS_DUCKDUCKGO:
        return "Error: ddgs module not available. Please install it with: pip install ddgs"
    
    return _search_web_impl(query, max_results)


@register_tool(
    name="duckduckgo_image_search",
    description="Search for images using DuckDuckGo search engine. Use this when you need to find images, pictures, or visual content related to a query. DuckDuckGo is a privacy-focused search engine that doesn't track users.",
    category="web"
)
def duckduckgo_image_search(query: str, max_results: int = 5) -> str:
    """Search for images using DuckDuckGo
    
    This tool uses DuckDuckGo to perform image searches and retrieve 
    image results from the internet. DuckDuckGo is privacy-focused and 
    doesn't track users.
    
    Args:
        query: Search query string
        max_results: Maximum number of results to return (default: 5)
    
    Returns:
        Formatted image search results with titles, image URLs, thumbnails, and source URLs, or error message if search fails
    """
    if not HAS_DUCKDUCKGO:
        return "Error: ddgs module not available. Please install it with: pip install ddgs"
    
    return _search_images_impl(query, max_results)
