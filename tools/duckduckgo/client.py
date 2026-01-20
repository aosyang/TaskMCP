#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DuckDuckGo Search Client - Client for performing web searches using DuckDuckGo

This module provides functionality to search the web using DuckDuckGo search engine.
"""

try:
    from ddgs import DDGS
    HAS_DDGS = True
except ImportError:
    HAS_DDGS = False


def search_web(query: str, max_results: int = 5) -> str:
    """Search the web using DuckDuckGo
    
    This function uses DuckDuckGo to perform web searches and retrieve 
    information from the internet.
    
    Args:
        query: Search query string
        max_results: Maximum number of results to return (default: 5)
    
    Returns:
        Formatted search results with titles, URLs, and snippets, or error message if search fails
    """
    if not HAS_DDGS:
        return "Error: ddgs module not available. Please install it with: pip install ddgs"
    
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            
            if not results:
                return f"No results found for query: {query}"
            
            # Format results
            formatted_results = []
            for i, result in enumerate(results, 1):
                title = result.get('title', 'No title')
                url = result.get('href', 'No URL')
                body = result.get('body', 'No description')
                
                formatted_results.append(
                    f"{i}. {title}\n   URL: {url}\n   {body}"
                )
            
            return "\n\n".join(formatted_results)
    
    except Exception as e:
        return f"Error: Failed to search DuckDuckGo - {str(e)}"


def search_images(query: str, max_results: int = 5) -> str:
    """Search for images using DuckDuckGo
    
    This function uses DuckDuckGo to perform image searches and retrieve 
    image results from the internet.
    
    Args:
        query: Search query string
        max_results: Maximum number of results to return (default: 5)
    
    Returns:
        Formatted image search results with titles, image URLs, thumbnails, and source URLs, or error message if search fails
    """
    if not HAS_DDGS:
        return "Error: ddgs module not available. Please install it with: pip install ddgs"
    
    try:
        with DDGS() as ddgs:
            images = list(ddgs.images(query, max_results=max_results))
            
            if not images:
                return f"No images found for query: {query}"
            
            # Format results
            formatted_results = []
            for i, img in enumerate(images, 1):
                title = img.get('title', 'No title')
                image_url = img.get('image', 'No image URL')
                thumbnail = img.get('thumbnail', 'No thumbnail')
                url = img.get('url', 'No URL')
                
                formatted_results.append(
                    f"{i}. {title}\n   Image URL: {image_url}\n   Thumbnail: {thumbnail}\n   Source URL: {url}"
                )
            
            return "\n\n".join(formatted_results)
    
    except Exception as e:
        return f"Error: Failed to search DuckDuckGo images - {str(e)}"
