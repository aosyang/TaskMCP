#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Example Tools - Demonstration of how to add new tools

This module shows examples of how to register new tools using the tool registry system.
"""

from tool_registry import register_tool
import random


# Example: Simple tool with auto-generated parameters
@register_tool(
    description="Generate a random number between min and max",
    category="random"
)
def random_number(min_val: int = 0, max_val: int = 100) -> int:
    """Generate a random number"""
    return random.randint(min_val, max_val)
