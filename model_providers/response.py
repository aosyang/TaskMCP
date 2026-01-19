#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一响应对象接口

定义模型提供者返回的统一响应格式，用于抽象不同提供者的响应差异。
"""

import json
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field


@dataclass
class ToolCallFunction:
    """工具调用函数信息"""
    name: str
    arguments: Dict[str, Any]


@dataclass
class ToolCall:
    """工具调用对象"""
    function: ToolCallFunction
    id: Optional[str] = None  # OpenAI requires tool_call_id
    type: str = "function"  # OpenAI requires type field
    
    def __init__(self, name: str, arguments: Dict[str, Any], tool_call_id: Optional[str] = None):
        self.function = ToolCallFunction(name=name, arguments=arguments)
        self.id = tool_call_id
        self.type = "function"


@dataclass
class ModelResponse:
    """统一的模型响应对象
    
    用于抽象不同模型提供者（Ollama、OpenAI等）的响应格式差异。
    """
    content: Optional[str] = None
    tool_calls: List[ToolCall] = field(default_factory=list)
    
    def model_dump(self) -> Dict[str, Any]:
        """将响应转换为字典格式，用于添加到消息历史
        
        Returns:
            包含 role 和 content 的字典，如果存在工具调用则包含 tool_calls
        """
        result = {
            'role': 'assistant',
            'content': self.content or ''
        }
        
        if self.tool_calls:
            result['tool_calls'] = [
                {
                    'id': tc.id or f"call_{i}",  # Generate ID if not provided
                    'type': tc.type,
                    'function': {
                        'name': tc.function.name,
                        'arguments': tc.function.arguments if isinstance(tc.function.arguments, str) else json.dumps(tc.function.arguments)
                    }
                }
                for i, tc in enumerate(self.tool_calls)
            ]
        
        return result
    
    def has_tool_calls(self) -> bool:
        """检查响应是否包含工具调用
        
        Returns:
            True 如果包含工具调用，否则 False
        """
        return len(self.tool_calls) > 0
