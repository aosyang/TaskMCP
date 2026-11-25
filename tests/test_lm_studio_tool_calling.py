#!/usr/bin/env python3
"""
Minimal test for LM Studio tool calling functionality

Tests tool calling via LM Studio provider.
Requires LM Studio to be running on localhost:1234 with a model loaded.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model_providers.lm_studio_provider import LMStudioProvider


# Simple test tools
def get_weather(location: str) -> str:
    """Get weather information for a location
    
    Args:
        location: The location to get weather for
        
    Returns:
        Weather information string
    """
    return f"Weather in {location}: Sunny, 25°C"


def calculate_sum(a: int, b: int) -> int:
    """Calculate the sum of two numbers
    
    Args:
        a: First number
        b: Second number
        
    Returns:
        Sum of a and b
    """
    return a + b


def get_current_time() -> str:
    """Get the current time
    
    Returns:
        Current time as string
    """
    from datetime import datetime
    return datetime.now().strftime('%H:%M:%S')


def test_tool_definition_format():
    """Test that tools are defined in correct format for LM Studio"""
    print("Test 1: Testing tool definition format...")
    
    # Define tools in OpenAI-compatible format
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather information for a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "The location to get weather for"
                        }
                    },
                    "required": ["location"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "calculate_sum",
                "description": "Calculate the sum of two numbers",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "a": {
                            "type": "integer",
                            "description": "First number"
                        },
                        "b": {
                            "type": "integer",
                            "description": "Second number"
                        }
                    },
                    "required": ["a", "b"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_current_time",
                "description": "Get the current time",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        }
    ]
    
    print(f"  ✓ Defined {len(tools)} tools")
    for tool in tools:
        print(f"    - {tool['function']['name']}")
    return tools


def test_tool_conversion(provider, tools):
    """Test converting tools using provider's convert_tools method"""
    print("\nTest 2: Testing tool conversion...")
    
    try:
        # Create tool dicts (Ollama format, compatible with OpenAI)
        tool_dicts = tools
        
        # Available functions mapping
        available_functions = {
            "get_weather": get_weather,
            "calculate_sum": calculate_sum,
            "get_current_time": get_current_time
        }
        
        # Convert tools using provider
        converted_tools = provider.convert_tools(tool_dicts, available_functions)
        
        print(f"  ✓ Converted {len(converted_tools)} tools")
        print(f"  - Tool format: {type(converted_tools[0]) if converted_tools else 'None'}")
        return converted_tools, available_functions
    except Exception as e:
        print(f"  ✗ Tool conversion failed: {e}")
        return None, None


def test_tool_calling(provider, tools, available_functions):
    """Test actual tool calling via LM Studio"""
    if not provider or not tools or not available_functions:
        print("\nTest 3: Skipped (prerequisites not met)")
        return
    
    print("\nTest 3: Testing tool calling...")
    
    try:
        # Send a message that should trigger a tool call
        messages = [
            {"role": "user", "content": "What is the weather in Tokyo?"}
        ]
        
        print("  Sending request with tools...")
        response = provider.chat(messages, tools=tools, max_tokens=100)
        
        print(f"  - Response content: {response.content or 'None'}")
        print(f"  - Has tool calls: {response.has_tool_calls()}")
        
        if response.has_tool_calls():
            print(f"  ✓ Tool calls detected: {len(response.tool_calls)}")
            for i, tool_call in enumerate(response.tool_calls):
                print(f"    Tool call {i+1}:")
                print(f"      - Name: {tool_call.function.name}")
                print(f"      - Arguments: {tool_call.function.arguments}")
                
                # Execute the tool
                if tool_call.function.name in available_functions:
                    func = available_functions[tool_call.function.name]
                    args = tool_call.function.arguments
                    result = func(**args)
                    print(f"      - Result: {result}")
                    print(f"      ✓ Tool executed successfully")
                else:
                    print(f"      ✗ Tool function not found: {tool_call.function.name}")
        else:
            print("  ⚠ No tool calls in response")
            print("  Note: The model may not have called tools. Try a different prompt.")
            
    except Exception as e:
        print(f"  ✗ Tool calling failed: {e}")
        print("  Note: Make sure LM Studio is running and the model supports tool calling")


def test_simple_calculation_tool(provider, tools, available_functions):
    """Test a simple calculation tool call"""
    if not provider or not tools or not available_functions:
        print("\nTest 4: Skipped (prerequisites not met)")
        return
    
    print("\nTest 4: Testing calculation tool...")
    
    try:
        messages = [
            {"role": "user", "content": "Calculate 15 + 27 using the calculate_sum tool"}
        ]
        
        print("  Sending calculation request...")
        response = provider.chat(messages, tools=tools, max_tokens=100)
        
        if response.has_tool_calls():
            print(f"  ✓ Tool call detected")
            for tool_call in response.tool_calls:
                if tool_call.function.name == "calculate_sum":
                    args = tool_call.function.arguments
                    result = calculate_sum(**args)
                    print(f"  - Calculation: {args.get('a', '?')} + {args.get('b', '?')} = {result}")
                    print(f"  ✓ Calculation tool works correctly")
                    return True
        else:
            print("  ⚠ No tool calls in response")
            
    except Exception as e:
        print(f"  ✗ Calculation tool test failed: {e}")
    
    return False


def test_time_tool(provider, tools, available_functions):
    """Test the get_current_time tool"""
    if not provider or not tools or not available_functions:
        print("\nTest 5: Skipped (prerequisites not met)")
        return
    
    print("\nTest 5: Testing time tool...")
    
    try:
        messages = [
            {"role": "user", "content": "What time is it now? Use the get_current_time tool."}
        ]
        
        print("  Sending time request...")
        response = provider.chat(messages, tools=tools, max_tokens=100)
        
        if response.has_tool_calls():
            print(f"  ✓ Tool call detected")
            for tool_call in response.tool_calls:
                if tool_call.function.name == "get_current_time":
                    result = get_current_time()
                    print(f"  - Current time: {result}")
                    print(f"  ✓ Time tool works correctly")
                    return True
        else:
            print("  ⚠ No tool calls in response")
            
    except Exception as e:
        print(f"  ✗ Time tool test failed: {e}")
    
    return False


def get_lm_studio_models(base_url: str = "http://localhost:1234/v1"):
    """Get available models from LM Studio
    
    Args:
        base_url: LM Studio API base URL
        
    Returns:
        List of model dictionaries, or None if failed
    """
    try:
        import requests
        response = requests.get(f"{base_url}/models", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if 'data' in data and data['data']:
                return data['data']
            else:
                return []
        else:
            print(f"  ⚠ Models endpoint returned status {response.status_code}")
            return None
    except requests.exceptions.ConnectionError:
        print("  ✗ Cannot connect to LM Studio")
        print("  Note: Make sure LM Studio is running on localhost:1234")
        return None
    except ImportError:
        print("  ⚠ requests library not available")
        return None
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return None


if __name__ == '__main__':
    print("=" * 60)
    print("LM Studio Tool Calling Minimal Test")
    print("=" * 60)
    print("\nPrerequisites:")
    print("  1. LM Studio must be running")
    print("  2. A model that supports tool calling must be loaded")
    print("  3. Server should be accessible at http://localhost:1234/v1")
    print("\n" + "=" * 60 + "\n")
    
    # Get available models from LM Studio
    print("Getting available models from LM Studio...")
    models = get_lm_studio_models()
    
    if models:
        print(f"  ✓ Found {len(models)} available model(s):")
        for i, model in enumerate(models, 1):
            model_id = model.get('id', 'unknown')
            print(f"    {i}. {model_id}")
        
        # Use first available model
        actual_model = models[0].get('id', 'test-model')
        print(f"\n  → Using model: {actual_model}\n")
    else:
        print("  ⚠ Could not get models, using default 'test-model'")
        print("  Note: Make sure LM Studio is running and a model is loaded\n")
        actual_model = "test-model"
    
    # Create provider
    try:
        provider = LMStudioProvider(
            model=actual_model,
            base_url="http://localhost:1234/v1"
        )
        print("✓ Provider created\n")
    except Exception as e:
        print(f"✗ Failed to create provider: {e}\n")
        sys.exit(1)
    
    # Test 1: Tool definition
    tools = test_tool_definition_format()
    
    # Test 2: Tool conversion
    converted_tools, available_functions = test_tool_conversion(provider, tools)
    
    # Test 3: Tool calling (weather)
    test_tool_calling(provider, converted_tools, available_functions)
    
    # Test 4: Calculation tool
    test_simple_calculation_tool(provider, converted_tools, available_functions)
    
    # Test 5: Time tool
    test_time_tool(provider, converted_tools, available_functions)
    
    print("\n" + "=" * 60)
    print("Tool calling test completed!")
    print("=" * 60)
    print("\nNote: If no tool calls were detected, the model may:")
    print("  1. Not support tool calling")
    print("  2. Need a more explicit prompt")
    print("  3. Require different tool definitions")
