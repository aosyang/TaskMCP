#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChatGPT Endpoint Client - Client for calling ChatGPT endpoint for web search

This module provides functionality to call the ChatGPT endpoint at http://192.168.1.168:5000
for web search and information retrieval.
"""

import requests
import time
from datetime import datetime


CHATGPT_ENDPOINT_URL = "http://192.168.1.168:5000/chat"
DEFAULT_TIMEOUT = 60
POLL_INTERVAL = 0.5


def search_web(query: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    """Search the web using ChatGPT endpoint
    
    This function calls the ChatGPT endpoint at http://192.168.1.168:5000/chat
    to perform web searches and get information from the internet.
    
    The endpoint supports both synchronous (200) and asynchronous (202) modes:
    - 200: Direct response, return immediately
    - 202: Async task, need to poll for status and get result
    
    Args:
        query: Search query or question to ask ChatGPT
        timeout: Timeout in seconds for the request (default: 60)
    
    Returns:
        Response text from ChatGPT, or error message if request fails
    """
    try:
        # Build message with system instruction requiring internet search
        # This ensures ChatGPT uses web search and verifies information online
        system_instruction = """IMPORTANT: You MUST search the internet and verify information online. 
You are required to:
1. Use web search to find current, accurate information
2. Verify details from reliable online sources
3. Confirm the information is up-to-date and accurate
4. Do NOT rely solely on your training data - you MUST access the internet to get the latest information

Please perform an internet search now and provide verified information."""
        
        # Combine system instruction with user query
        full_message = f"{system_instruction}\n\nUser query: {query}"
        
        # POST /chat to submit task
        payload = {
            "message": full_message,
            "timeout": timeout
        }
        
        response = requests.post(CHATGPT_ENDPOINT_URL, json=payload, timeout=timeout + 10)
        
        # Check if server supports async mode (202) or sync mode (200)
        if response.status_code == 200:
            # Sync mode - direct response
            data = response.json()
            if 'response' in data:
                return data['response']
            elif 'result' in data:
                return data['result']
            else:
                return str(data)
        
        elif response.status_code == 202:
            # Async mode - need to poll for status
            data = response.json()
            task_id = data.get('task_id')
            if not task_id:
                # Try to extract from raw_data
                raw_data = data.get('raw_data', {})
                task_id = raw_data.get('task_id')
            
            if not task_id:
                return f"Error: Could not get task_id from response: {data}"
            
            # Poll for task status
            status_url = f"http://192.168.1.168:5000/tasks/{task_id}/status"
            max_poll_time = timeout + 20
            start_time = datetime.now()
            
            while True:
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed > max_poll_time:
                    return f"Error: Polling timeout after {max_poll_time} seconds"
                
                try:
                    status_response = requests.get(status_url, timeout=5)
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        status = status_data.get('status', '').lower()
                        
                        if status == 'completed':
                            # Get result
                            result_url = f"http://192.168.1.168:5000/tasks/{task_id}/result"
                            result_response = requests.get(result_url, timeout=10)
                            if result_response.status_code == 200:
                                result_data = result_response.json()
                                if 'result' in result_data:
                                    return result_data['result']
                                elif 'response' in result_data:
                                    return result_data['response']
                                else:
                                    return str(result_data)
                            else:
                                return f"Error: Failed to get result: {result_response.status_code}"
                        
                        elif status == 'failed':
                            error = status_data.get('error', 'Unknown error')
                            return f"Error: Task failed - {error}"
                        
                        elif status in ['pending', 'running']:
                            # Continue polling
                            time.sleep(POLL_INTERVAL)
                            continue
                        else:
                            return f"Error: Unknown status: {status}"
                    else:
                        return f"Error: Failed to get status: {status_response.status_code}"
                
                except requests.exceptions.RequestException as e:
                    return f"Error: Network error during polling: {str(e)}"
        
        elif response.status_code == 429:
            return "Error: Rate limit exceeded. Another request is being processed. Please try again later."
        
        else:
            return f"Error: Request failed with status {response.status_code}: {response.text}"
    
    except requests.exceptions.Timeout:
        return f"Error: Request timeout after {timeout} seconds"
    
    except requests.exceptions.RequestException as e:
        return f"Error: Network error - {str(e)}"
    
    except Exception as e:
        return f"Error: Unexpected error - {str(e)}"
