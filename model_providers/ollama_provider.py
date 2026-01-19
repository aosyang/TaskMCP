#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ollama 模型提供者实现

将现有的 Ollama 逻辑封装为 ModelProvider 接口实现。
"""

from typing import List, Dict, Any, Optional, Callable
from ollama import Client
from .base import ModelProvider
from .response import ModelResponse, ToolCall


class OllamaProvider(ModelProvider):
    """Ollama 模型提供者实现"""
    
    def __init__(self, model: str, base_url: str = 'http://localhost:11434', **kwargs):
        """初始化 Ollama 提供者
        
        Args:
            model: 模型名称
            base_url: Ollama 服务地址，默认为 http://localhost:11434
            **kwargs: 其他配置参数
        """
        super().__init__(model, **kwargs)
        self.base_url = base_url
        self.client = Client(host=base_url)
    
    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Any]] = None,
        **kwargs
    ) -> ModelResponse:
        """调用 Ollama 模型进行对话
        
        Args:
            messages: 消息历史列表
            tools: 工具列表（可以是工具字典或函数对象）
            **kwargs: 其他参数（如 no_think 等）
        
        Returns:
            ModelResponse: 统一的响应对象
        """
        # 准备调用参数
        call_kwargs = {
            'model': self.model,
            'messages': messages,
        }
        
        # 如果提供了工具，添加到调用参数
        if tools is not None:
            call_kwargs['tools'] = tools
        
        # 添加其他参数（如 temperature 等）
        call_kwargs.update(kwargs)
        
        # 调用 Ollama
        try:
            # 首先尝试使用工具字典格式
            if tools is not None:
                try:
                    response = self.client.chat(**call_kwargs)
                except (TypeError, ValueError):
                    # 如果工具字典格式不支持，尝试使用函数对象
                    # 这种情况通常不会发生，但为了兼容性保留
                    if isinstance(tools, list) and tools:
                        # 如果 tools 是字典列表，尝试提取函数对象
                        # 这里假设 tools 可能包含函数对象
                        call_kwargs['tools'] = tools
                        response = self.client.chat(**call_kwargs)
                    else:
                        raise
            else:
                response = self.client.chat(**call_kwargs)
        except Exception as e:
            # 如果调用失败，返回错误响应
            return ModelResponse(
                content=f"Error: Failed to call Ollama model: {str(e)}"
            )
        
        # 转换响应格式
        return self._convert_response(response)
    
    def _convert_response(self, ollama_response) -> ModelResponse:
        """将 Ollama 响应转换为统一的 ModelResponse 格式
        
        Args:
            ollama_response: Ollama 客户端返回的响应对象
        
        Returns:
            ModelResponse: 统一的响应对象
        """
        # 提取内容
        content = ollama_response.message.content if hasattr(ollama_response.message, 'content') else None
        
        # 提取工具调用
        tool_calls = []
        if hasattr(ollama_response.message, 'tool_calls') and ollama_response.message.tool_calls:
            for tool_call in ollama_response.message.tool_calls:
                if hasattr(tool_call, 'function'):
                    # Ollama 工具调用格式
                    func = tool_call.function
                    tool_name = func.name if hasattr(func, 'name') else None
                    tool_args = func.arguments if hasattr(func, 'arguments') else {}
                    
                    if tool_name:
                        tool_calls.append(ToolCall(name=tool_name, arguments=tool_args))
                elif isinstance(tool_call, dict):
                    # 如果是字典格式
                    func = tool_call.get('function', {})
                    tool_name = func.get('name') if isinstance(func, dict) else None
                    tool_args = func.get('arguments', {}) if isinstance(func, dict) else {}
                    
                    if tool_name:
                        tool_calls.append(ToolCall(name=tool_name, arguments=tool_args))
        
        return ModelResponse(content=content, tool_calls=tool_calls)
    
    def convert_tools(
        self,
        tool_dicts: List[Dict[str, Any]],
        available_functions: Dict[str, Callable]
    ) -> List[Any]:
        """将工具字典转换为 Ollama 所需的格式
        
        Ollama 支持两种格式：
        1. 工具字典列表（推荐）
        2. 函数对象列表（向后兼容）
        
        Args:
            tool_dicts: 工具字典列表（Ollama格式）
            available_functions: 可用函数字典（用于向后兼容）
        
        Returns:
            工具列表，格式为工具字典列表或函数对象列表
        """
        # Ollama 可以直接使用工具字典格式
        # 如果 tool_dicts 为空，尝试从 available_functions 生成
        if not tool_dicts and available_functions:
            # 返回函数对象列表作为后备
            return list(available_functions.values())
        
        return tool_dicts
    
    def supports_no_think(self) -> bool:
        """Ollama 支持 no_think 模式"""
        return True
    
    def supports_streaming(self) -> bool:
        """Ollama 支持流式响应"""
        return True
