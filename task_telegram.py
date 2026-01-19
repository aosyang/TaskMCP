#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TaskMCP Telegram Bot - Telegram bot interface using Ollama model for tool calling

Usage:
    python task_telegram.py

Configuration:
    Create .env file with:
    TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN
    TELEGRAM_ALLOWED_USER_IDS=123456789,987654321  # Optional: comma-separated user IDs
"""

import sys
import io
import os
import logging
import asyncio
from typing import Dict, Any

# Set output encoding to UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Configure logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Suppress HTTP-related logs
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('telegram').setLevel(logging.WARNING)
logging.getLogger('telegram.ext').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('urllib3.connectionpool').setLevel(logging.WARNING)

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    logger.warning("python-dotenv not installed. Install it with: pip install python-dotenv")
    logger.warning("Will try to read TELEGRAM_BOT_TOKEN from environment variables.")

# Telegram bot library
try:
    from telegram import Update
    from telegram.constants import ChatAction
    from telegram.error import BadRequest
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
except ImportError:
    logger.error("python-telegram-bot not installed. Install it with: pip install python-telegram-bot")
    sys.exit(1)

# Import shared agent functionality
import task_agent
from task_telegram_utils import clean_markdownv2_text

# Load configuration
try:
    _agent_config = task_agent.load_agent_config()
    _default_model = _agent_config['ollama']['model']
except (FileNotFoundError, ValueError, ImportError) as e:
    logger.error(f"Error: {e}")
    sys.exit(1)

# Load Telegram bot token from environment variable
_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
if not _bot_token:
    error_msg = (
        "TELEGRAM_BOT_TOKEN environment variable not set. "
        "Please create a .env file with TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN "
        "or set it as an environment variable."
    )
    logger.error(error_msg)
    raise ValueError(error_msg)

# Load allowed user IDs whitelist (optional)
_allowed_user_ids_str = os.getenv('TELEGRAM_ALLOWED_USER_IDS', '').strip()
if _allowed_user_ids_str:
    try:
        _allowed_user_ids = set(int(uid.strip()) for uid in _allowed_user_ids_str.split(',') if uid.strip())
        logger.info(f"Whitelist mode enabled. Allowed user IDs: {_allowed_user_ids}")
    except ValueError as e:
        logger.warning(f"Invalid TELEGRAM_ALLOWED_USER_IDS format: {e}. Whitelist disabled.")
        _allowed_user_ids = None
else:
    _allowed_user_ids = None
    logger.info("Whitelist mode disabled. All users are allowed.")

# Track non-whitelisted users who have been logged (to avoid spam)
_logged_non_whitelisted_users: set[int] = set()


def is_user_allowed(user_id: int, user_name: str = None) -> bool:
    """Check if a user is allowed to interact with the bot
    
    Logs non-whitelisted users on first encounter (user ID and username)
    to help identify users who should be added to the whitelist.
    Subsequent requests from the same user are not logged to avoid spam.
    
    Args:
        user_id: Telegram user ID
        user_name: Telegram username (optional, for logging purposes)
        
    Returns:
        True if user is allowed, False otherwise
    """
    if _allowed_user_ids is None:
        return True  # No whitelist, allow all users
    
    if user_id in _allowed_user_ids:
        return True
    
    # User is not in whitelist - log on first encounter only
    if user_id not in _logged_non_whitelisted_users:
        if user_name:
            username_display = f"@{user_name}"
        else:
            username_display = "(no username)"
        logger.warning(
            f"Non-whitelisted user attempted to access bot - "
            f"User ID: {user_id}, Username: {username_display} "
            f"(Consider adding to TELEGRAM_ALLOWED_USER_IDS)"
        )
        _logged_non_whitelisted_users.add(user_id)
    
    return False


# Store conversation history per user (chat_id -> messages)
user_conversations: Dict[int, list] = {}


def run_agent_for_telegram(query: str, model: str = None, no_think: bool = False, messages: list = None, 
                           tool_call_notifications: list = None, async_notify_callback = None, event_loop = None):
    """Run agent for Telegram bot
    
    This is a wrapper around task_agent.run_agent. The response will be automatically
    converted to Telegram MarkdownV2 format using telegramify-markdown library.
    
    Args:
        query: User query
        model: Model to use (defaults to config file value)
        no_think: Whether to disable thinking mode
        messages: Optional conversation history message list
        tool_call_notifications: Optional list to store tool call notifications (tool_name, args, result, is_before)
        async_notify_callback: Optional async callback function to immediately notify user (update, notification_text)
        event_loop: Optional event loop for async operations
    
    Returns:
        Tuple of (response_text, updated_message_list)
    """
    # Create tool call callback (before execution) to log and notify immediately
    def on_tool_call(tool_name: str, args: dict):
        """Callback before a tool is called"""
        # Log to console
        logger.info(f"Tool calling (before): {tool_name} with args: {args}")
        
        # Format notification message
        tool_display = tool_name.replace('_', ' ').title()
        args_str = ""
        if args:
            args_parts = []
            for key, value in args.items():
                value_str = str(value)
                if len(value_str) > 50:
                    value_str = value_str[:50] + "..."
                args_parts.append(f"{key}: {value_str}")
            args_str = ", ".join(args_parts)
            if len(args_str) > 150:
                args_str = args_str[:150] + "..."
        
        notification_text = f"🔧 Calling tool: *{tool_display}*"
        if args_str:
            notification_text += f"\nArguments: `{args_str}`"
        
        # Immediately notify user if async callback is provided
        if async_notify_callback and event_loop:
            try:
                # Schedule async notification in the event loop
                future = asyncio.run_coroutine_threadsafe(
                    async_notify_callback(notification_text),
                    event_loop
                )
                # Don't wait for completion to avoid blocking
            except Exception as e:
                logger.warning(f"Failed to schedule tool call notification: {e}")
        
        # Store notification for async handling (for after notifications)
        if tool_call_notifications is not None:
            tool_call_notifications.append(('before', tool_name, args, None))
    
    # Create tool call callback (after execution) to log and notify
    def on_tool_call_after(tool_name: str, args: dict, result: Any):
        """Callback after a tool is called"""
        # Log to console
        logger.info(f"Tool called (after): {tool_name} with args: {args}, result: {result}")
        
        # Store notification for async handling
        if tool_call_notifications is not None:
            tool_call_notifications.append(('after', tool_name, args, result))
    
    # Call the shared run_agent function
    # No need to add MarkdownV2 format requirements to prompt since telegramify-markdown
    # will automatically convert any Markdown format to MarkdownV2
    response_text, updated_messages = task_agent.run_agent(
        query=query,
        model=model,
        no_think=no_think,
        messages=messages,
        return_text=True,
        on_tool_call=on_tool_call,
        on_tool_call_after=on_tool_call_after
    )
    
    return response_text, updated_messages


async def safe_reply_text(update: Update, text: str, parse_mode: str = "MarkdownV2"):
    """Safely reply with text, falling back to plain text if MarkdownV2 parsing fails
    
    The text is automatically converted to MarkdownV2 format using telegramify-markdown
    library, which handles all Markdown formats correctly.
    
    Args:
        update: Telegram update object
        text: Text to send (can be any Markdown format)
        parse_mode: Parse mode to use (default: MarkdownV2)
    """
    # Convert text to MarkdownV2 format using telegramify-markdown
    cleaned_text = clean_markdownv2_text(text)
    
    try:
        await update.message.reply_text(cleaned_text, parse_mode=parse_mode)
    except BadRequest as e:
        # If MarkdownV2 parsing fails, fall back to plain text
        if "Can't parse entities" in str(e) or "parse" in str(e).lower():
            logger.warning(f"MarkdownV2 parsing failed, falling back to plain text: {e}")
            await update.message.reply_text(cleaned_text)
        else:
            # Re-raise if it's a different BadRequest error
            raise


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    # Check whitelist
    if not is_user_allowed(user_id, username):
        await safe_reply_text(update, "Sorry, you are not authorized to use this bot.")
        return
    
    welcome_message = """Welcome to TaskMCP Bot!

I can help you manage tasks and workspaces using natural language.

Commands:
/start - Show this welcome message
/clear - Clear conversation history
/help - Show help information

Just send me a message and I'll help you manage your tasks!"""
    
    await safe_reply_text(update, welcome_message)


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /clear command"""
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    # Check whitelist
    if not is_user_allowed(user_id, username):
        await safe_reply_text(update, "Sorry, you are not authorized to use this bot.")
        return
    
    chat_id = update.effective_chat.id
    if chat_id in user_conversations:
        del user_conversations[chat_id]
    await safe_reply_text(update, "Conversation history cleared.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    # Check whitelist
    if not is_user_allowed(user_id, username):
        await safe_reply_text(update, "Sorry, you are not authorized to use this bot.")
        return
    
    help_text = """TaskMCP Bot Help

I can help you:
- List, add, update, delete tasks
- Manage workspaces
- Search tasks
- Get current time/date

Examples:
- "List all tasks"
- "Add a task: Complete project documentation"
- "What is the current workspace?"
- "Mark task #1 as done"

Use /clear to reset conversation history."""
    
    await safe_reply_text(update, help_text)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular text messages"""
    user_id = update.effective_user.id
    username = update.effective_user.username
    chat_id = update.effective_chat.id
    user_message = update.message.text
    
    if not user_message:
        return
    
    # Check whitelist
    if not is_user_allowed(user_id, username):
        await safe_reply_text(update, "Sorry, you are not authorized to use this bot.")
        return
    
    # Get or create conversation history for this user
    if chat_id not in user_conversations:
        user_conversations[chat_id] = None
    
    # Send typing indicator
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    
    # List to store tool call notifications (for after notifications)
    tool_call_notifications = []
    
    # Create async callback for immediate notifications
    async def async_notify(notification_text: str):
        """Async callback to immediately send notification to user"""
        try:
            await safe_reply_text(update, notification_text)
        except Exception as e:
            logger.warning(f"Failed to send immediate tool call notification: {e}")
    
    # Get event loop for async operations
    loop = asyncio.get_event_loop()
    
    try:
        # Run agent with user's conversation history (in executor to avoid blocking)
        response_text, updated_messages = await loop.run_in_executor(
            None,
            run_agent_for_telegram,
            user_message,
            _default_model,
            False,
            user_conversations[chat_id],
            tool_call_notifications,
            async_notify,
            loop
        )
        
        # Send tool call after notifications to user (before notifications are sent immediately during execution)
        for notification_type, tool_name, args, result in tool_call_notifications:
            # Only send "after" notifications here (before notifications are sent immediately)
            if notification_type == 'after':
                # Format tool name for display (replace underscores with spaces, capitalize)
                tool_display = tool_name.replace('_', ' ').title()
                
                # After tool call notification
                notification_text = f"✅ Tool execution completed: *{tool_display}*"
                if result is not None:
                    result_str = str(result)
                    if len(result_str) > 200:
                        result_str = result_str[:200] + "..."
                    notification_text += f"\nResult: `{result_str}`"
                
                try:
                    await safe_reply_text(update, notification_text)
                except Exception as e:
                    logger.warning(f"Failed to send tool call after notification: {e}")
        
        # Update conversation history
        user_conversations[chat_id] = updated_messages
        
        # Send response (Telegram has 4096 character limit, so we may need to split)
        if len(response_text) > 4096:
            # Split into chunks
            chunks = [response_text[i:i+4096] for i in range(0, len(response_text), 4096)]
            for chunk in chunks:
                await safe_reply_text(update, chunk)
        else:
            await safe_reply_text(update, response_text)
    
    except Exception as e:
        error_message = f"Error processing your request: {str(e)}"
        await safe_reply_text(update, error_message)


def main():
    """Start the Telegram bot"""
    import warnings
    
    # Suppress the deprecation warning from python-telegram-bot
    # This is a known issue in the library and will be fixed in future versions
    warnings.filterwarnings("ignore", category=DeprecationWarning, module="telegram")
    
    logger.info("Starting TaskMCP Telegram Bot...")
    logger.info(f"Model: {_default_model}")
    
    # Create application
    application = Application.builder().token(_bot_token).build()
    
    # Register handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Start bot
    logger.info("Bot is running. Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
