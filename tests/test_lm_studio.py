#!/usr/bin/env python3
"""
Minimal test for LM Studio provider endpoint

Tests basic functionality of LM Studio provider.
Requires LM Studio to be running on localhost:1234 with a model loaded.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model_providers.lm_studio_provider import LMStudioProvider
from model_providers.factory import create_provider


def test_lm_studio_provider_creation():
    """Test creating LM Studio provider instance"""
    print("Test 1: Creating LM Studio provider...")
    try:
        provider = LMStudioProvider(
            model="test-model",
            base_url="http://localhost:1234/v1"
        )
        print("  ✓ Provider created successfully")
        print(f"  - Model: {provider.model}")
        print(f"  - Base URL: {provider.base_url}")
        return provider
    except Exception as e:
        print(f"  ✗ Failed to create provider: {e}")
        return None


def test_lm_studio_chat(provider):
    """Test basic chat functionality"""
    if not provider:
        print("\nTest 2: Skipped (provider not available)")
        return
    
    print("\nTest 2: Testing chat endpoint...")
    try:
        messages = [
            {"role": "user", "content": "Say 'Hello' in one word."}
        ]
        
        print("  Sending request to LM Studio...")
        response = provider.chat(messages, max_tokens=10)
        
        if response.content:
            print(f"  ✓ Response received: {response.content[:50]}...")
            print(f"  - Has tool calls: {response.has_tool_calls()}")
        else:
            print("  ⚠ Response received but content is empty")
            
    except Exception as e:
        print(f"  ✗ Chat failed: {e}")
        print("  Note: Make sure LM Studio is running on localhost:1234 with a model loaded")


def test_factory_creation():
    """Test creating provider via factory"""
    print("\nTest 3: Testing factory creation...")
    try:
        config = {
            'provider': {'type': 'lm_studio'},
            'lm_studio': {
                'model': 'test-model',
                'base_url': 'http://localhost:1234/v1'
            }
        }
        
        provider = create_provider(config)
        print("  ✓ Provider created via factory")
        print(f"  - Type: {type(provider).__name__}")
        return provider
    except Exception as e:
        print(f"  ✗ Factory creation failed: {e}")
        return None


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


def test_models_endpoint():
    """Test if LM Studio models endpoint is accessible and get models"""
    print("\nTest 4: Testing models endpoint and getting available models...")
    
    models = get_lm_studio_models()
    
    if models is None:
        print("  ✗ Failed to get models")
        return None
    
    if not models:
        print("  ⚠ No models found in LM Studio")
        print("  Note: Make sure you have loaded a model in LM Studio")
        return None
    
    print(f"  ✓ Models endpoint accessible")
    print(f"  - Available models: {len(models)}")
    print("\n  Available models:")
    for i, model in enumerate(models, 1):
        model_id = model.get('id', 'unknown')
        model_name = model.get('name', model_id)
        model_created = model.get('created', 'N/A')
        print(f"    {i}. {model_id}")
        if model.get('name') and model.get('name') != model_id:
            print(f"       Name: {model_name}")
        if model.get('created'):
            print(f"       Created: {model_created}")
    
    # Return first model ID for use in other tests
    if models:
        first_model = models[0].get('id', 'unknown')
        print(f"\n  → First available model: {first_model}")
        return first_model
    
    return None


if __name__ == '__main__':
    print("=" * 50)
    print("LM Studio Provider Minimal Test")
    print("=" * 50)
    print("\nPrerequisites:")
    print("  1. LM Studio must be running")
    print("  2. A model must be loaded in LM Studio")
    print("  3. Server should be accessible at http://localhost:1234/v1")
    print("\n" + "=" * 50 + "\n")
    
    # Test 4: Get available models first (to use actual model name)
    print("Getting available models from LM Studio...")
    actual_model = test_models_endpoint()
    
    # Test 1: Provider creation (use actual model if available)
    if actual_model:
        print(f"\nUsing model: {actual_model}")
        try:
            provider = LMStudioProvider(
                model=actual_model,
                base_url="http://localhost:1234/v1"
            )
            print("  ✓ Provider created with actual model")
        except Exception as e:
            print(f"  ✗ Failed to create provider: {e}")
            provider = None
    else:
        provider = test_lm_studio_provider_creation()
    
    # Test 2: Chat functionality
    test_lm_studio_chat(provider)
    
    # Test 3: Factory creation
    test_factory_creation()
    
    print("\n" + "=" * 50)
    print("Test completed!")
    print("=" * 50)
