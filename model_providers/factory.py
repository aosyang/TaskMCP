#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模型提供者工厂函数

根据配置动态创建合适的模型提供者实例。
"""

import os
from typing import Dict, Any, Optional
from .base import ModelProvider


def create_provider(config: Dict[str, Any]) -> ModelProvider:
    """根据配置创建模型提供者实例
    
    Args:
        config: 配置字典，通常来自 load_agent_config()
    
    Returns:
        ModelProvider: 模型提供者实例
    
    Raises:
        ValueError: 如果提供者类型不支持或配置无效
        ImportError: 如果提供者所需的依赖未安装
    """
    # 获取提供者类型（支持新格式和向后兼容）
    if '_provider_type' in config:
        provider_type = config['_provider_type']
    elif 'provider' in config and 'type' in config['provider']:
        provider_type = config['provider']['type']
    else:
        # 向后兼容：默认使用 ollama
        provider_type = 'ollama'
    
    if provider_type == 'ollama':
        return _create_ollama_provider(config)
    elif provider_type == 'openai':
        return _create_openai_provider(config)
    else:
        raise ValueError(
            f"Unsupported provider type '{provider_type}'. "
            "Supported types: 'ollama', 'openai'"
        )


def _create_ollama_provider(config: Dict[str, Any]) -> ModelProvider:
    """创建 Ollama 提供者实例"""
    from .ollama_provider import OllamaProvider
    
    ollama_config = config.get('ollama', {})
    model = ollama_config.get('model')
    
    if not model:
        raise ValueError("Ollama model must be specified in [ollama] section")
    
    # 可选配置
    base_url = ollama_config.get('base_url', 'http://localhost:11434')
    
    return OllamaProvider(model=model, base_url=base_url)


def _create_openai_provider(config: Dict[str, Any]) -> ModelProvider:
    """创建 OpenAI 提供者实例"""
    from .openai_provider import OpenAIProvider
    
    openai_config = config.get('openai', {})
    model = openai_config.get('model')
    
    if not model:
        raise ValueError("OpenAI model must be specified in [openai] section")
    
    # API key 优先从环境变量获取（更安全），如果没有则从配置文件读取
    api_key = os.getenv('OPENAI_API_KEY') or openai_config.get('api_key')
    if not api_key:
        raise ValueError(
            "OpenAI API key must be specified in OPENAI_API_KEY environment variable or [openai].api_key"
        )
    
    # 可选配置
    base_url = openai_config.get('base_url', 'https://api.openai.com/v1')
    
    return OpenAIProvider(model=model, api_key=api_key, base_url=base_url)
