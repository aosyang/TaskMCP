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
    from telegram import Update, InputFile
    from telegram.constants import ChatAction
    from telegram.error import BadRequest
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
except ImportError:
    logger.error("python-telegram-bot not installed. Install it with: pip install python-telegram-bot")
    sys.exit(1)

# Import shared agent functionality
import task_agent
import user_config
from task_telegram_utils import clean_markdownv2_text, dump_conversation_to_file

# Load configuration
try:
    _agent_config = task_agent.load_agent_config()
    # Get provider type and model name
    if '_provider_type' in _agent_config:
        provider_type = _agent_config['_provider_type']
    elif 'provider' in _agent_config and 'type' in _agent_config['provider']:
        provider_type = _agent_config['provider']['type']
    else:
        provider_type = 'ollama'  # Default
    
    # Get model name based on provider type
    if provider_type == 'ollama':
        _default_model = _agent_config.get('ollama', {}).get('model', 'unknown')
    elif provider_type == 'openai':
        _default_model = _agent_config.get('openai', {}).get('model', 'unknown')
    else:
        _default_model = 'unknown'
    
    _provider_type = provider_type
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
                           tool_call_notifications: list = None, async_notify_callback = None, event_loop = None,
                           user_id: int = None, bot = None, chat_id: int = None):
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
        user_id: Telegram user ID for language preference lookup
    
    Returns:
        Tuple of (response_text, updated_message_list)
    """
    # Define batch tools that should be grouped together
    BATCH_TOOLS = {
        'add_task', 'add_task_with_parent', 'update_task', 
        'delete_task', 'toggle_task', 'set_color'
    }
    
    # Track batch operations
    batch_state = {
        'current_tool': None,
        'count': 0,
        'results': [],
        'started': False,
        'message_future': None  # Future for batch start message, to edit it when batch completes
    }
    
    # Track message futures for editing (tool_name -> future)
    tool_message_futures = {}
    
    def send_batch_notification():
        """Send notification for completed batch operation"""
        if batch_state['current_tool'] and batch_state['count'] > 0:
            tool_name = batch_state['current_tool']
            tool_display = tool_name.replace('_', ' ').title()
            count = batch_state['count']
            
            # Create summary notification with blockquote format
            notification_text = f"✅ Completed:\n> {tool_display} ({count} calls)"
            
            # Add summary of results (limit to first 3 for readability and to avoid message length issues)
            if batch_state['results']:
                summary_lines = []
                max_results_to_show = 3
                max_result_length = 80
                
                for i, result in enumerate(batch_state['results'][:max_results_to_show]):
                    result_str = str(result)
                    if len(result_str) > max_result_length:
                        result_str = result_str[:max_result_length] + "..."
                    summary_lines.append(f"• {result_str}")
                
                if count > max_results_to_show:
                    summary_lines.append(f"... and {count - max_results_to_show} more")
                
                summary_text = "\n".join(summary_lines)
                # Ensure total message doesn't exceed Telegram's limit (4096 chars)
                # Reserve some space for the header and formatting
                max_summary_length = 3500
                if len(notification_text) + len(summary_text) + 10 > max_summary_length:
                    # Truncate summary if needed
                    available_length = max_summary_length - len(notification_text) - 20
                    if available_length > 0:
                        summary_text = summary_text[:available_length] + "..."
                    else:
                        summary_text = ""
                
                if summary_text:
                    notification_text += "\n" + summary_text
            
            # Edit the original batch start message instead of sending a new one
            if batch_state['message_future'] and bot and chat_id:
                future = batch_state['message_future']
                try:
                    # Get message ID from future (with timeout)
                    message_id = future.result(timeout=10)
                    if message_id and event_loop:
                        # Edit the message
                        asyncio.run_coroutine_threadsafe(
                            safe_edit_message_text(bot, chat_id, message_id, notification_text),
                            event_loop
                        )
                    else:
                        # If we couldn't get message ID, fallback to send new message
                        if async_notify_callback and event_loop:
                            asyncio.run_coroutine_threadsafe(
                                async_notify_callback(notification_text),
                                event_loop
                            )
                except Exception as e:
                    logger.warning(f"Failed to edit batch notification: {e}")
                    # Fallback: send new message if edit fails
                    if async_notify_callback and event_loop:
                        try:
                            asyncio.run_coroutine_threadsafe(
                                async_notify_callback(notification_text),
                                event_loop
                            )
                        except Exception as e2:
                            logger.warning(f"Failed to send fallback batch notification: {e2}")
            elif async_notify_callback and event_loop:
                # Fallback: send new message if we don't have message future
                try:
                    asyncio.run_coroutine_threadsafe(
                        async_notify_callback(notification_text),
                        event_loop
                    )
                except Exception as e:
                    logger.warning(f"Failed to send batch notification: {e}")
            
            # Store in notifications list
            if tool_call_notifications is not None:
                tool_call_notifications.append(('batch_after', tool_name, None, batch_state['results']))
            
            # Reset batch state
            batch_state['current_tool'] = None
            batch_state['count'] = 0
            batch_state['results'] = []
            batch_state['started'] = False
            batch_state['message_future'] = None
    
    # Create tool call callback (before execution) to log and notify immediately
    def on_tool_call(tool_name: str, args: dict):
        """Callback before a tool is called"""
        # Log to console
        logger.info(f"Tool calling (before): {tool_name} with args: {args}")
        
        # Check if this is a batch tool
        is_batch_tool = tool_name in BATCH_TOOLS
        
        # If this is a different tool than current batch, send previous batch notification
        if batch_state['current_tool'] and batch_state['current_tool'] != tool_name:
            send_batch_notification()
        
        # Handle batch tools
        if is_batch_tool:
            # Start or continue batch
            if not batch_state['started']:
                batch_state['current_tool'] = tool_name
                batch_state['started'] = True
                batch_state['count'] = 0
                batch_state['results'] = []
                
                # Send batch start notification and save future for later editing
                tool_display = tool_name.replace('_', ' ').title()
                notification_text = f"🔧 Starting batch:\n> {tool_display}..."
                
                if async_notify_callback and event_loop:
                    try:
                        # Send notification and store future for later message ID retrieval
                        future = asyncio.run_coroutine_threadsafe(
                            async_notify_callback(notification_text),
                            event_loop
                        )
                        # Store future for later editing when batch completes
                        batch_state['message_future'] = future
                    except Exception as e:
                        logger.warning(f"Failed to send batch start notification: {e}")
            
            batch_state['count'] += 1
        else:
            # Non-batch tool: send previous batch notification if any
            if batch_state['current_tool']:
                send_batch_notification()
            
            # Send individual notification for non-batch tools
            tool_display = tool_name.replace('_', ' ').title()
            
            # Format arguments, each on separate line with blockquote
            args_lines = []
            if args:
                for key, value in args.items():
                    value_str = str(value)
                    if len(value_str) > 50:
                        value_str = value_str[:50] + "..."
                    args_lines.append(f"> {key}: {value_str}")
            
            # Build notification with MarkdownV2 format using blockquote
            # Tool name and arguments each on separate line with blockquote prefix
            notification_text = f"🔧 Calling tool:\n> {tool_display}"
            if args_lines:
                notification_text += "\n\nArguments:\n" + "\n".join(args_lines)
            
            # Immediately notify user if async callback is provided
            if async_notify_callback and event_loop:
                try:
                    # Send notification and store future for later message ID retrieval
                    future = asyncio.run_coroutine_threadsafe(
                        async_notify_callback(notification_text),
                        event_loop
                    )
                    # Store future for later editing
                    tool_message_futures[tool_name] = future
                except Exception as e:
                    logger.warning(f"Failed to schedule tool call notification: {e}")
            
            # Store notification for async handling (for after notifications)
            if tool_call_notifications is not None:
                tool_call_notifications.append(('before', tool_name, args, None))
    
    # Create tool call callback (after execution) to log and notify
    def on_tool_call_after(tool_name: str, args: dict, result: Any):
        """Callback after a tool is called - changes 'Calling' message to 'completed'"""
        # Log to console
        logger.info(f"Tool called (after): {tool_name} with args: {args}, result: {result}")
        
        # Check if this is a batch tool
        is_batch_tool = tool_name in BATCH_TOOLS
        
        if is_batch_tool:
            # Accumulate result for batch
            if batch_state['current_tool'] == tool_name:
                batch_state['results'].append(result)
        else:
            # Non-batch tool: send completion notification with same format as calling notification
            # Only change "Calling tool" to "Tool execution completed"
            tool_display = tool_name.replace('_', ' ').title()
            
            # Format arguments, each on separate line with blockquote (same as on_tool_call)
            args_lines = []
            if args:
                for key, value in args.items():
                    value_str = str(value)
                    if len(value_str) > 50:
                        value_str = value_str[:50] + "..."
                    args_lines.append(f"> {key}: {value_str}")
            
            # Build notification with same format as on_tool_call, just change prefix
            notification_text = f"✅ Tool execution completed:\n> {tool_display}"
            if args_lines:
                notification_text += "\n\nArguments:\n" + "\n".join(args_lines)
            
            # Edit the original message instead of sending a new one
            if tool_name in tool_message_futures and bot and chat_id:
                future = tool_message_futures[tool_name]
                try:
                    # Get message ID from future (with timeout)
                    message_id = future.result(timeout=10)
                    if message_id and event_loop:
                        # Edit the message
                        asyncio.run_coroutine_threadsafe(
                            safe_edit_message_text(bot, chat_id, message_id, notification_text),
                            event_loop
                        )
                        # Remove future after editing
                        del tool_message_futures[tool_name]
                    else:
                        # If we couldn't get message ID, fall through to send new message
                        if tool_name in tool_message_futures:
                            del tool_message_futures[tool_name]
                except Exception as e:
                    logger.warning(f"Failed to edit tool call notification: {e}")
                    # Remove future on error
                    if tool_name in tool_message_futures:
                        del tool_message_futures[tool_name]
                    # Fallback: send new message if edit fails
                    if async_notify_callback and event_loop:
                        try:
                            asyncio.run_coroutine_threadsafe(
                                async_notify_callback(notification_text),
                                event_loop
                            )
                        except Exception as e2:
                            logger.warning(f"Failed to send fallback notification: {e2}")
            elif async_notify_callback and event_loop:
                # Fallback: send new message if we don't have message future
                try:
                    asyncio.run_coroutine_threadsafe(
                        async_notify_callback(notification_text),
                        event_loop
                    )
                except Exception as e:
                    logger.warning(f"Failed to send tool call after notification: {e}")
            
            # Note: We don't add non-batch tool notifications to tool_call_notifications
            # because they are sent immediately via async_notify_callback above.
            # This prevents duplicate notifications in handle_message
    
    # Get user's language preference (None if not set, meaning no language restriction)
    language = user_config.get_user_language(user_id) if user_id is not None else None
    
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
        on_tool_call_after=on_tool_call_after,
        language=language
    )
    
    # Send any remaining batch notification before returning
    if batch_state['current_tool']:
        send_batch_notification()
    
    return response_text, updated_messages


async def safe_reply_text(update: Update, text: str, parse_mode: str = "MarkdownV2"):
    """Safely reply with text, falling back to plain text if MarkdownV2 parsing fails
    
    The text is automatically converted to MarkdownV2 format using telegramify-markdown
    library, which handles all Markdown formats correctly.
    
    Args:
        update: Telegram update object
        text: Text to send (can be any Markdown format)
        parse_mode: Parse mode to use (default: MarkdownV2)
    
    Returns:
        Message object from Telegram API
    """
    # Convert text to MarkdownV2 format using telegramify-markdown
    cleaned_text = clean_markdownv2_text(text)
    
    try:
        message = await update.message.reply_text(cleaned_text, parse_mode=parse_mode)
        return message
    except BadRequest as e:
        # If MarkdownV2 parsing fails, fall back to plain text
        if "Can't parse entities" in str(e) or "parse" in str(e).lower():
            logger.warning(f"MarkdownV2 parsing failed, falling back to plain text: {e}")
            message = await update.message.reply_text(cleaned_text)
            return message
        else:
            # Re-raise if it's a different BadRequest error
            raise


async def safe_edit_message_text(bot, chat_id: int, message_id: int, text: str, parse_mode: str = "MarkdownV2"):
    """Safely edit a message, falling back to plain text if MarkdownV2 parsing fails
    
    Args:
        bot: Telegram bot instance
        chat_id: Chat ID where the message is located
        message_id: ID of the message to edit
        text: New text content (can be any Markdown format)
        parse_mode: Parse mode to use (default: MarkdownV2)
    """
    # Convert text to MarkdownV2 format using telegramify-markdown
    cleaned_text = clean_markdownv2_text(text)
    
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=cleaned_text,
            parse_mode=parse_mode
        )
    except BadRequest as e:
        # If MarkdownV2 parsing fails, fall back to plain text
        if "Can't parse entities" in str(e) or "parse" in str(e).lower():
            logger.warning(f"MarkdownV2 parsing failed, falling back to plain text: {e}")
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=cleaned_text
            )
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
/dump - Export conversation history as JSON for debugging

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

Use /clear to reset conversation history.
Use /dump to export conversation history as JSON for debugging.
Use /language to set your language preference."""
    
    await safe_reply_text(update, help_text)


async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /language command - Set or view language preference"""
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    # Check whitelist
    if not is_user_allowed(user_id, username):
        await safe_reply_text(update, "Sorry, you are not authorized to use this bot.")
        return
    
    # Get current language
    current_language = user_config.get_user_language(user_id)
    if current_language:
        current_language_name = user_config.SUPPORTED_LANGUAGES.get(current_language, current_language)
    else:
        current_language_name = "English (no restriction)"
    
    # Check if user provided a language code
    if context.args and len(context.args) > 0:
        language_code = context.args[0].lower()
        
        if language_code == 'clear':
            # Clear language setting (remove from config)
            config = user_config.load_user_config()
            user_id_str = str(user_id)
            if user_id_str in config and 'language' in config[user_id_str]:
                del config[user_id_str]['language']
                # Remove user entry if it's empty
                if not config[user_id_str]:
                    del config[user_id_str]
                user_config.save_user_config(config)
            await safe_reply_text(
                update,
                "Language restriction cleared. Using default (English, no restriction)."
            )
        elif language_code in user_config.SUPPORTED_LANGUAGES:
            if user_config.set_user_language(user_id, language_code):
                language_name = user_config.SUPPORTED_LANGUAGES[language_code]
                await safe_reply_text(
                    update,
                    f"Language preference set to: {language_name} ({language_code})\n\n"
                    f"The bot will now respond in {language_name}."
                )
            else:
                await safe_reply_text(update, "Failed to set language preference.")
        else:
            # Show supported languages
            lang_list = "\n".join([f"  {code}: {name}" for code, name in user_config.SUPPORTED_LANGUAGES.items()])
            await safe_reply_text(
                update,
                f"Invalid language code: {language_code}\n\n"
                f"Supported languages:\n{lang_list}\n\n"
                f"Usage: /language <code>\n"
                f"Example: /language en\n"
                f"Usage: /language clear (to remove language restriction)"
            )
    else:
        # Show current language and supported languages
        lang_list = "\n".join([f"  {code}: {name}" for code, name in user_config.SUPPORTED_LANGUAGES.items()])
        current_display = f"{current_language_name}"
        if current_language:
            current_display += f" ({current_language})"
        await safe_reply_text(
            update,
            f"Current language: {current_display}\n\n"
            f"Supported languages:\n{lang_list}\n\n"
            f"Usage: /language <code>\n"
            f"Example: /language en\n"
            f"Usage: /language clear (to remove language restriction)"
        )


async def dump_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /dump command - Export conversation history as JSON"""
    user_id = update.effective_user.id
    username = update.effective_user.username
    chat_id = update.effective_chat.id
    
    # Check whitelist
    if not is_user_allowed(user_id, username):
        await safe_reply_text(update, "Sorry, you are not authorized to use this bot.")
        return
    
    try:
        # Get conversation history
        messages = user_conversations.get(chat_id)
        
        # Dump conversation to file using utility function
        filepath, filename = dump_conversation_to_file(
            user_id=user_id,
            username=username,
            chat_id=chat_id,
            conversation_history=messages
        )
        
        # Get conversation count for caption
        conversation_count = len(messages) if messages else 0
        
        # Send file to user
        try:
            with open(filepath, 'rb') as f:
                document = InputFile(f, filename=filename)
                await update.message.reply_document(
                    document=document,
                    caption=f"Conversation history exported\nUser ID: {user_id}\nMessage count: {conversation_count}\nFile saved to local dumps/ folder"
                )
            
            # Log file location (file is kept for debugging)
            logger.info(f"Conversation dump saved: {filepath}")
        
        except Exception as e:
            logger.error(f"Failed to send dump file: {e}")
            await safe_reply_text(update, f"Export failed: {str(e)}")
    
    except Exception as e:
        logger.error(f"Error in dump_command: {e}")
        await safe_reply_text(update, f"Error exporting conversation history: {str(e)}")


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
        """Async callback to immediately send notification to user
        
        Returns:
            Message ID of the sent message, or None if failed
        """
        try:
            message = await safe_reply_text(update, notification_text)
            return message.message_id if message else None
        except Exception as e:
            logger.warning(f"Failed to send immediate tool call notification: {e}")
            return None
    
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
            loop,
            user_id,  # Pass user_id for language preference
            context.bot,  # Pass bot for message editing
            chat_id  # Pass chat_id for message editing
        )
        
        # Send tool call after notifications to user (before notifications are sent immediately during execution)
        # Note: 
        # - batch_after notifications are already sent via async_notify_callback, so we skip them here
        # - Non-batch tool 'after' notifications are also sent immediately via callback and not added to this list
        # - This loop now mainly handles 'before' notifications if needed in the future
        for notification_type, tool_name, args, result in tool_call_notifications:
            # Skip batch_after notifications (already sent via callback)
            if notification_type == 'batch_after':
                continue
            
            # Handle "after" notifications (should not occur for non-batch tools, but kept for compatibility)
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
    logger.info(f"Provider: {_provider_type}, Model: {_default_model}")
    
    # Create application
    application = Application.builder().token(_bot_token).build()
    
    # Register handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("dump", dump_command))
    application.add_handler(CommandHandler("language", language_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Start bot
    logger.info("Bot is running. Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
