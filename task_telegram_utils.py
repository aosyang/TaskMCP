#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram Bot Utilities - Helper functions for Telegram bot formatting

This module provides utility functions for formatting text for Telegram,
specifically for MarkdownV2 compatibility.

Uses telegramify-markdown library for reliable MarkdownV2 conversion.
"""

import os
import json
from datetime import datetime
from typing import Optional, Dict, Any

try:
    import telegramify_markdown
    _HAS_TELEGRAMIFY = True
except ImportError:
    _HAS_TELEGRAMIFY = False
    import warnings
    warnings.warn(
        "telegramify-markdown not installed. Install it with: pip install telegramify-markdown\n"
        "Falling back to basic implementation (may have issues with complex markdown).",
        UserWarning
    )


def clean_markdownv2_text(text: str) -> str:
    """Clean text to ensure MarkdownV2 compatibility
    
    Converts Markdown text to Telegram MarkdownV2 compatible format.
    Uses telegramify-markdown library for reliable conversion.
    
    This function handles:
    - **bold** -> *bold*
    - # headings -> converted appropriately
    - > blockquotes -> converted appropriately
    - Code blocks and inline code
    - Links and images
    - Escapes special characters correctly
    
    Args:
        text: Text to clean
    
    Returns:
        Cleaned text compatible with MarkdownV2
    """
    # Use telegramify-markdown if available
    if _HAS_TELEGRAMIFY:
        try:
            return telegramify_markdown.markdownify(text)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"telegramify-markdown conversion failed: {e}, falling back to basic implementation")
    
    # Fallback to basic implementation if telegramify-markdown is not available
    # This is a simplified version that may not handle all edge cases
    import re
    
    # Protect code blocks first (they may contain any characters)
    # Use a unique placeholder that won't appear in normal text
    # Note: Code blocks may contain triple backticks inside them as content,
    # so we need to match properly. Use a simple but effective approach:
    # match from ``` to the next ``` that's at the start of a line
    code_blocks = []
    # Use regex to match code blocks: ``` followed by optional language,
    # then content (which may include ```), then closing ``` at line start
    # We'll use a simpler approach: match ```...``` but handle nested cases
    code_block_pattern = r'```[\s\S]*?```'
    # First, find all potential matches
    potential_matches = list(re.finditer(code_block_pattern, text))
    
    # Filter out matches that are inside other code blocks
    matches = []
    for i, match in enumerate(potential_matches):
        # Check if this match is inside any previous match
        is_inside = False
        for prev_match in matches:
            if prev_match.start() < match.start() < prev_match.end():
                is_inside = True
                break
        if not is_inside:
            matches.append(match)
    
    # Replace from end to start to preserve positions
    for i, match in enumerate(reversed(matches)):
        placeholder = f'__CODE_BLOCK_{len(matches) - 1 - i}__'
        code_blocks.insert(0, (match.group(), placeholder))
        text = text[:match.start()] + placeholder + text[match.end():]
    
    # Protect inline code (but not code blocks)
    inline_code = []
    inline_code_pattern = r'`[^`\n]+`'
    matches = list(re.finditer(inline_code_pattern, text))
    # Replace from end to start to preserve positions
    for i, match in enumerate(reversed(matches)):
        placeholder = f'__INLINE_CODE_{len(matches) - 1 - i}__'
        inline_code.insert(0, (match.group(), placeholder))
        text = text[:match.start()] + placeholder + text[match.end():]
    
    # Protect links [text](URL) and images ![text](URL)
    # Links must be protected before escaping special characters
    links = []
    # Match both regular links and image links
    link_pattern = r'!?\[([^\]]*)\]\(([^)]+)\)'
    matches = list(re.finditer(link_pattern, text))
    # Replace from end to start to preserve positions
    for i, match in enumerate(reversed(matches)):
        placeholder = f'__LINK_{len(matches) - 1 - i}__'
        links.insert(0, (match.group(), placeholder))
        text = text[:match.start()] + placeholder + text[match.end():]
    
    # Replace **text** with *text* (double asterisks to single)
    text = re.sub(r'\*\*([^*]+)\*\*', r'*\1*', text)
    
    # Remove markdown headers (# ## ### etc.) - convert to plain text
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        # Check if line starts with # (header)
        header_match = re.match(r'^(#{1,6})\s+(.+)$', line)
        if header_match:
            # Convert header to plain text (just the text part)
            cleaned_lines.append(header_match.group(2))
        else:
            cleaned_lines.append(line)
    text = '\n'.join(cleaned_lines)
    
    # Remove blockquotes (> at start of line)
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        # Remove > at start of line (blockquote)
        if re.match(r'^>\s*', line):
            # Remove > and leading space
            cleaned_line = re.sub(r'^>\s*', '', line)
            cleaned_lines.append(cleaned_line)
        else:
            cleaned_lines.append(line)
    text = '\n'.join(cleaned_lines)
    
    # Protect MarkdownV2 format markers before escaping
    # Format markers: *bold*, _italic_, __underline__, ~strikethrough~, ||spoiler||
    # Protect in order from most specific to least specific (e.g., __underline__ before _italic_)
    format_markers = []
    
    # Protect ||spoiler|| (most specific, contains |)
    spoiler_pattern = r'\|\|[^|\n]+\|\|'
    matches = list(re.finditer(spoiler_pattern, text))
    for i, match in enumerate(reversed(matches)):
        placeholder = f'__SPOILER_{len(matches) - 1 - i}__'
        format_markers.insert(0, (match.group(), placeholder))
        text = text[:match.start()] + placeholder + text[match.end():]
    
    # Protect __underline__ (contains double underscore, protect before _italic_)
    underline_pattern = r'__[^_\n]+__'
    matches = list(re.finditer(underline_pattern, text))
    for i, match in enumerate(reversed(matches)):
        placeholder = f'__UNDERLINE_{len(matches) - 1 - i}__'
        format_markers.insert(0, (match.group(), placeholder))
        text = text[:match.start()] + placeholder + text[match.end():]
    
    # Protect ~strikethrough~
    strikethrough_pattern = r'~[^~\n]+~'
    matches = list(re.finditer(strikethrough_pattern, text))
    for i, match in enumerate(reversed(matches)):
        placeholder = f'__STRIKETHROUGH_{len(matches) - 1 - i}__'
        format_markers.insert(0, (match.group(), placeholder))
        text = text[:match.start()] + placeholder + text[match.end():]
    
    # Protect *bold* (single asterisk, not double)
    bold_pattern = r'(?<!\*)\*[^*\n]+\*(?!\*)'
    matches = list(re.finditer(bold_pattern, text))
    for i, match in enumerate(reversed(matches)):
        placeholder = f'__BOLD_{len(matches) - 1 - i}__'
        format_markers.insert(0, (match.group(), placeholder))
        text = text[:match.start()] + placeholder + text[match.end():]
    
    # Protect _italic_ (single underscore, protect after __underline__)
    italic_pattern = r'(?<!_)_[^_\n]+_(?!_)'
    matches = list(re.finditer(italic_pattern, text))
    for i, match in enumerate(reversed(matches)):
        placeholder = f'__ITALIC_{len(matches) - 1 - i}__'
        format_markers.insert(0, (match.group(), placeholder))
        text = text[:match.start()] + placeholder + text[match.end():]
    
    # Protect all placeholders before escaping (to prevent escaping placeholder characters)
    # Placeholders have format: __XXX_YYY__ (e.g., __CODE_BLOCK_0__, __LINK_1__, etc.)
    placeholder_protection = []
    placeholder_pattern = r'__[A-Z_]+_\d+__'
    placeholder_matches = list(re.finditer(placeholder_pattern, text))
    # Replace from end to start to preserve positions
    for i, match in enumerate(reversed(placeholder_matches)):
        # Use a safe placeholder that doesn't contain any special characters that need escaping
        # Use only letters and numbers, with a unique prefix/suffix to avoid conflicts
        safe_placeholder = f'PLACEHOLDERSAFE{len(placeholder_matches) - 1 - i}SAFE'
        placeholder_protection.insert(0, (match.group(), safe_placeholder))
        text = text[:match.start()] + safe_placeholder + text[match.end():]
    
    # Now escape special characters in remaining plain text
    # MarkdownV2 reserved characters: _ * [ ] ( ) ~ ` > # + - = | { } . !
    # Escape them if not already escaped
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        # Escape if not already escaped (negative lookbehind for \)
        text = re.sub(r'(?<!\\)' + re.escape(char), '\\' + char, text)
    
    # Restore protected placeholders (before restoring other content)
    for original_placeholder, safe_placeholder in reversed(placeholder_protection):
        text = text.replace(safe_placeholder, original_placeholder)
    
    # Restore in reverse order of protection:
    # 1. Format markers (protected last, restore first)
    for marker, placeholder in reversed(format_markers):
        text = text.replace(placeholder, marker)
    
    # 2. Links
    for link, placeholder in reversed(links):
        text = text.replace(placeholder, link)
    
    # 3. Code blocks and inline code
    for code, placeholder in reversed(code_blocks):
        text = text.replace(placeholder, code)
    
    for code, placeholder in reversed(inline_code):
        text = text.replace(placeholder, code)
    
    return text


def dump_conversation_to_file(
    user_id: int,
    username: Optional[str],
    chat_id: int,
    conversation_history: Optional[list],
    output_dir: Optional[str] = None
) -> tuple[str, str]:
    """Dump conversation history to a JSON file
    
    The file will be saved in a 'dumps' subdirectory for easy access and debugging.
    
    Args:
        user_id: Telegram user ID
        username: Telegram username (optional)
        chat_id: Telegram chat ID
        conversation_history: Conversation history messages list
        output_dir: Base directory to save the file (default: same directory as this file)
                   Files will be saved in a 'dumps' subdirectory
    
    Returns:
        Tuple of (filepath, filename)
    """
    # Prepare dump data
    dump_data: Dict[str, Any] = {
        "user_id": user_id,
        "username": username,
        "chat_id": chat_id,
        "dump_timestamp": datetime.now().isoformat(),
        "conversation_history": conversation_history if conversation_history else None,
        "conversation_count": len(conversation_history) if conversation_history else 0
    }
    
    # Convert to JSON
    json_str = json.dumps(dump_data, ensure_ascii=False, indent=2)
    
    # Determine base output directory
    if output_dir is None:
        output_dir = os.path.dirname(__file__)
    
    # Create dumps subdirectory
    dumps_dir = os.path.join(output_dir, 'dumps')
    os.makedirs(dumps_dir, exist_ok=True)
    
    # Create file with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"conversation_dump_{chat_id}_{timestamp}.json"
    filepath = os.path.join(dumps_dir, filename)
    
    # Write to file
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(json_str)
    
    return filepath, filename
