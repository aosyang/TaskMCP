#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模型提供者抽象基类

定义所有模型提供者必须实现的接口，用于支持多种模型后端。
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Callable
from .response import ModelResponse


class ModelProvider(ABC):
    """模型提供者抽象基类
    
    所有模型提供者（Ollama、OpenAI等）必须实现此接口。
    """
    
    def __init__(self, model: str, **kwargs):
        """初始化模型提供者
        
        Args:
            model: 模型名称
            **kwargs: 提供者特定的配置参数
        """
        self.model = model
        self.config = kwargs
    
    @abstractmethod
    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Any]] = None,
        **kwargs
    ) -> ModelResponse:
        """调用模型进行对话
        
        Args:
            messages: 消息历史列表，格式为 [{'role': 'user', 'content': '...'}, ...]
            tools: 工具列表，格式由具体提供者决定（可能是函数对象或JSON Schema）
            **kwargs: 其他提供者特定的参数（如 temperature, max_tokens 等）
        
        Returns:
            ModelResponse: 统一的响应对象
        """
        pass
    
    @abstractmethod
    def convert_tools(
        self,
        tool_dicts: List[Dict[str, Any]],
        available_functions: Dict[str, Callable]
    ) -> List[Any]:
        """将工具字典转换为提供者所需的格式
        
        不同提供者对工具格式的要求不同：
        - Ollama: 可以直接使用函数对象或工具字典
        - OpenAI: 需要 JSON Schema 格式
        
        Args:
            tool_dicts: 工具字典列表（Ollama格式）
            available_functions: 可用函数字典，映射函数名到可调用对象
        
        Returns:
            转换后的工具列表，格式由具体提供者决定
        """
        pass
    
    def supports_no_think(self) -> bool:
        """检查提供者是否支持 no_think 模式
        
        Returns:
            True 如果支持，否则 False
        """
        return False
    
    def supports_streaming(self) -> bool:
        """检查提供者是否支持流式响应
        
        Returns:
            True 如果支持，否则 False
        """
        return False
