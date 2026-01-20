#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenAI 模型提供者实现

实现 OpenAI API 的 ModelProvider 接口，支持工具调用功能。
"""

import json
from typing import List, Dict, Any, Optional, Callable
from .base import ModelProvider
from .response import ModelResponse, ToolCall

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None


class OpenAIProvider(ModelProvider):
    """OpenAI 模型提供者实现"""
    
    def __init__(self, model: str, api_key: str, base_url: str = 'https://api.openai.com/v1', **kwargs):
        """初始化 OpenAI 提供者
        
        Args:
            model: 模型名称（如 'gpt-4o', 'gpt-4o-mini'）
            api_key: OpenAI API 密钥
            base_url: API 基础 URL，默认为 https://api.openai.com/v1
            **kwargs: 其他配置参数
        """
        if not OPENAI_AVAILABLE:
            raise ImportError(
                "OpenAI package not installed. Install it with: pip install openai"
            )
        
        super().__init__(model, **kwargs)
        self.api_key = api_key
        self.base_url = base_url
        self.client = OpenAI(api_key=api_key, base_url=base_url)
    
    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Any]] = None,
        **kwargs
    ) -> ModelResponse:
        """调用 OpenAI 模型进行对话
        
        Args:
            messages: 消息历史列表
            tools: 工具列表（应该是 OpenAI 格式的工具字典列表）
            **kwargs: 其他参数（如 temperature, max_tokens 等）
        
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
            # OpenAI 需要指定 tool_choice（可选）
            # 默认让模型决定是否使用工具
            if 'tool_choice' not in kwargs:
                call_kwargs['tool_choice'] = 'auto'
        
        # 添加其他参数（如 temperature, max_tokens 等）
        # 过滤掉 tool_choice（已经在上面处理了）
        for key, value in kwargs.items():
            if key != 'tool_choice' or 'tool_choice' not in call_kwargs:
                call_kwargs[key] = value
        
        # 调用 OpenAI API
        try:
            response = self.client.chat.completions.create(**call_kwargs)
        except Exception as e:
            # 如果调用失败，返回错误响应
            return ModelResponse(
                content=f"Error: Failed to call OpenAI model: {str(e)}"
            )
        
        # 转换响应格式
        return self._convert_response(response)
    
    def _convert_response(self, openai_response) -> ModelResponse:
        """将 OpenAI 响应转换为统一的 ModelResponse 格式
        
        Args:
            openai_response: OpenAI API 返回的响应对象
        
        Returns:
            ModelResponse: 统一的响应对象
        """
        # OpenAI 响应格式：response.choices[0].message
        if not openai_response.choices:
            return ModelResponse(content="Error: No response from OpenAI")
        
        message = openai_response.choices[0].message
        
        # 提取内容
        content = message.content if hasattr(message, 'content') else None
        
        # 提取工具调用
        tool_calls = []
        if hasattr(message, 'tool_calls') and message.tool_calls:
            for tool_call in message.tool_calls:
                # OpenAI 工具调用格式
                if hasattr(tool_call, 'function'):
                    func = tool_call.function
                    tool_name = func.name if hasattr(func, 'name') else None
                    # OpenAI 的 arguments 是 JSON 字符串，需要解析
                    tool_args_str = func.arguments if hasattr(func, 'arguments') else '{}'
                    
                    try:
                        # 尝试解析 JSON 字符串
                        if isinstance(tool_args_str, str):
                            tool_args = json.loads(tool_args_str)
                        else:
                            tool_args = tool_args_str
                    except (json.JSONDecodeError, TypeError):
                        # 如果解析失败，使用空字典
                        tool_args = {}
                    
                    # 提取 tool_call_id (OpenAI 要求)
                    tool_call_id = tool_call.id if hasattr(tool_call, 'id') else None
                    
                    if tool_name:
                        tool_calls.append(ToolCall(name=tool_name, arguments=tool_args, tool_call_id=tool_call_id))
                elif isinstance(tool_call, dict):
                    # 如果是字典格式（向后兼容）
                    func = tool_call.get('function', {})
                    tool_name = func.get('name') if isinstance(func, dict) else None
                    tool_args_str = func.get('arguments', '{}') if isinstance(func, dict) else '{}'
                    
                    try:
                        if isinstance(tool_args_str, str):
                            tool_args = json.loads(tool_args_str)
                        else:
                            tool_args = tool_args_str
                    except (json.JSONDecodeError, TypeError):
                        tool_args = {}
                    
                    # 提取 tool_call_id
                    tool_call_id = tool_call.get('id')
                    
                    if tool_name:
                        tool_calls.append(ToolCall(name=tool_name, arguments=tool_args, tool_call_id=tool_call_id))
        
        return ModelResponse(content=content, tool_calls=tool_calls)
    
    def convert_tools(
        self,
        tool_dicts: List[Dict[str, Any]],
        available_functions: Dict[str, Callable]
    ) -> List[Dict[str, Any]]:
        """将工具字典转换为 OpenAI 所需的格式
        
        OpenAI 需要 JSON Schema 格式的工具定义。
        Ollama 工具格式和 OpenAI 工具格式基本相同，但需要确保格式正确。
        
        Args:
            tool_dicts: 工具字典列表（Ollama格式，应该与 OpenAI 格式兼容）
            available_functions: 可用函数字典（用于生成工具定义）
        
        Returns:
            OpenAI 格式的工具列表
        """
        # OpenAI 工具格式与 Ollama 工具格式基本相同
        # 格式：{"type": "function", "function": {"name": "...", "description": "...", "parameters": {...}}}
        
        if tool_dicts:
            # 验证并清理工具格式
            openai_tools = []
            for tool in tool_dicts:
                if isinstance(tool, dict):
                    # 确保格式正确
                    if 'type' in tool and tool['type'] == 'function':
                        if 'function' in tool:
                            openai_tools.append(tool)
                        else:
                            # 如果格式不对，尝试修复
                            # 这种情况不应该发生，但为了健壮性保留
                            openai_tools.append({
                                'type': 'function',
                                'function': tool
                            })
                    else:
                        # 如果没有 type，假设整个字典是 function 定义
                        openai_tools.append({
                            'type': 'function',
                            'function': tool
                        })
            return openai_tools
        
        # 如果没有工具字典，尝试从 available_functions 生成
        # 这需要从函数签名提取信息，比较复杂
        # 为了简化，返回空列表（调用者应该提供工具字典）
        return []
    
    def supports_no_think(self) -> bool:
        """OpenAI 不支持 no_think 模式"""
        return False
    
    def supports_streaming(self) -> bool:
        """OpenAI 支持流式响应"""
        return True
