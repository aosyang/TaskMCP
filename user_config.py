"""User configuration management for language preferences and other user settings"""
import os
import json
from typing import Optional

USER_CONFIG_DIR = 'user_configs'
USER_CONFIG_FILE = os.path.join(USER_CONFIG_DIR, 'user_config.json')

# Supported languages
SUPPORTED_LANGUAGES = {
    'zh': 'Chinese (简体中文)',
    'en': 'English',
    'ja': 'Japanese (日本語)',
    'ko': 'Korean (한국어)',
    'es': 'Spanish (Español)',
    'fr': 'French (Français)',
    'de': 'German (Deutsch)',
}

DEFAULT_LANGUAGE = None  # None means no language restriction (default to English without prompt)


def ensure_user_config_dir():
    """Ensure user config directory exists"""
    if not os.path.exists(USER_CONFIG_DIR):
        os.makedirs(USER_CONFIG_DIR)


def load_user_config():
    """Load user configuration from file
    
    Returns:
        Dictionary mapping user_id to config dict
    """
    ensure_user_config_dir()
    if os.path.exists(USER_CONFIG_FILE):
        try:
            with open(USER_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            # If file is corrupted, return empty dict
            return {}
    return {}


def save_user_config(config):
    """Save user configuration to file
    
    Args:
        config: Dictionary mapping user_id to config dict
    """
    ensure_user_config_dir()
    with open(USER_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def get_user_language(user_id: Optional[int] = None) -> Optional[str]:
    """Get language preference for a user
    
    Args:
        user_id: User ID (for Telegram bot) or None (for CLI)
        
    Returns:
        Language code (e.g., 'zh', 'en') or None if no language preference set
    """
    if user_id is None:
        # For CLI, check if there's a default language in config
        config = load_user_config()
        return config.get('_default_language', DEFAULT_LANGUAGE)
    
    config = load_user_config()
    user_config = config.get(str(user_id), {})
    # Return None if language is not set (use default behavior)
    return user_config.get('language', DEFAULT_LANGUAGE)


def set_user_language(user_id: Optional[int], language: str) -> bool:
    """Set language preference for a user
    
    Args:
        user_id: User ID (for Telegram bot) or None (for CLI default)
        language: Language code (e.g., 'zh', 'en')
        
    Returns:
        True if language is valid and set, False otherwise
    """
    if language not in SUPPORTED_LANGUAGES:
        return False
    
    config = load_user_config()
    
    if user_id is None:
        # For CLI, set default language
        config['_default_language'] = language
    else:
        # For Telegram bot, set user-specific language
        user_id_str = str(user_id)
        if user_id_str not in config:
            config[user_id_str] = {}
        config[user_id_str]['language'] = language
    
    save_user_config(config)
    return True


def get_language_prompt(language: Optional[str]) -> str:
    """Get language instruction for system prompt based on language code
    
    Args:
        language: Language code (e.g., 'zh', 'en') or None for no language restriction
        
    Returns:
        Language instruction string for system prompt, or empty string if language is None
    """
    if language is None:
        return ""  # No language restriction
    
    language_instructions = {
        'zh': "IMPORTANT: You must always respond in Chinese (简体中文). All your responses should be in Chinese, including explanations, confirmations, and error messages.",
        'en': "IMPORTANT: You must always respond in English. All your responses should be in English, including explanations, confirmations, and error messages.",
        'ja': "IMPORTANT: You must always respond in Japanese (日本語). All your responses should be in Japanese, including explanations, confirmations, and error messages.",
        'ko': "IMPORTANT: You must always respond in Korean (한국어). All your responses should be in Korean, including explanations, confirmations, and error messages.",
        'es': "IMPORTANT: You must always respond in Spanish (Español). All your responses should be in Spanish, including explanations, confirmations, and error messages.",
        'fr': "IMPORTANT: You must always respond in French (Français). All your responses should be in French, including explanations, confirmations, and error messages.",
        'de': "IMPORTANT: You must always respond in German (Deutsch). All your responses should be in German, including explanations, confirmations, and error messages.",
    }
    
    return language_instructions.get(language, "")


def list_supported_languages() -> str:
    """Get formatted list of supported languages
    
    Returns:
        Formatted string listing all supported languages
    """
    lines = ["Supported languages:"]
    for code, name in SUPPORTED_LANGUAGES.items():
        lines.append(f"  {code}: {name}")
    lines.append("  (default: English, no language restriction)")
    return "\n".join(lines)
