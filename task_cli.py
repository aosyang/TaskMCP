#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TaskMCP Agent CLI - Command-line agent using Qwen3 model for tool calling

Usage:
    python task_cli.py "List all tasks"
    python task_cli.py "Add a task: Complete project documentation"
    python task_cli.py --interactive  # Interactive mode
"""

import sys
import io
import argparse
import threading
import time
from typing import Optional

# Set output encoding to UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Import shared agent functionality
import task_agent

# Load configuration
try:
    _agent_config = task_agent.load_agent_config()
    _default_model = _agent_config['ollama']['model']
except (FileNotFoundError, ValueError, ImportError) as e:
    print(f"Error: {e}")
    sys.exit(1)


# Loading animation
class LoadingAnimation:
    """Display loading animation while waiting for model response"""
    def __init__(self):
        # Braille pattern dots animation sequence
        self.spinning_chars = ['⠶', '⠧', '⠏', '⠛', '⠹', '⠼']
        self.running = False
        self.thread = None
    
    def _animate(self):
        """Animation loop"""
        i = 0
        while self.running:
            sys.stdout.write(f'\r{self.spinning_chars[i % len(self.spinning_chars)]} Thinking...')
            sys.stdout.flush()
            time.sleep(0.1)
            i += 1
    
    def start(self):
        """Start the animation"""
        self.running = True
        self.thread = threading.Thread(target=self._animate, daemon=True)
        self.thread.start()
    
    def stop(self):
        """Stop the animation"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=0.2)
        sys.stdout.write('\r' + ' ' * 20 + '\r')  # Clear the line
        sys.stdout.flush()


def run_agent_with_ui(query: str, model: Optional[str] = None, no_think: bool = False, messages: Optional[list] = None):
    """Run agent with CLI-specific UI (loading animation and output formatting)
    
    Args:
        query: User query
        model: Model to use (defaults to config file value)
        no_think: Whether to disable thinking mode
        messages: Optional conversation history message list
    
    Returns:
        Updated message list
    """
    if model is None:
        model = _default_model
    
    # Create loading animation
    loader = LoadingAnimation()
    
    def before_chat():
        loader.start()
    
    def after_chat():
        loader.stop()
    
    # Call shared run_agent function
    # return_text=False means we handle output ourselves
    response_text, updated_messages = task_agent.run_agent(
        query=query,
        model=model,
        no_think=no_think,
        messages=messages,
        return_text=True,
        before_chat_callback=before_chat,
        after_chat_callback=after_chat
    )
    
    # Print response if available
    if response_text:
        print(f'Assistant: {response_text}')
    
    return updated_messages


def interactive_mode(model: Optional[str] = None, no_think: bool = False):
    """Interactive mode (with conversation history support)"""
    if model is None:
        model = _default_model
    print('=' * 60)
    print('TaskMCP Agent - Interactive Mode')
    print(f'Model: {model}')
    print('Type "exit" or "quit" to exit')
    print('Type "clear" or "reset" to clear conversation history')
    print('=' * 60)
    print()
    
    # Maintain conversation history
    messages = None
    
    while True:
        try:
            query = input('You: ').strip()
            if not query:
                continue
            
            if query.lower() in ['exit', 'quit', 'q']:
                print('Goodbye!')
                break
            
            # Clear conversation history
            if query.lower() in ['clear', 'reset']:
                messages = None
                print('\nConversation history cleared\n')
                continue
            
            print()
            # Run agent and update conversation history
            messages = run_agent_with_ui(query, model, no_think, messages)
            print()
        except KeyboardInterrupt:
            print('\n\nGoodbye!')
            break
        except Exception as e:
            print(f'\nError: {e}\n')


def main():
    parser = argparse.ArgumentParser(
        description='TaskMCP Agent - Command-line agent using Qwen3 model for task management',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python task_cli.py "List all tasks"
  python task_cli.py "Add a task: Complete project documentation"
  python task_cli.py "Search tasks containing 'documentation'"
  python task_cli.py --interactive
  python task_cli.py --interactive --no-think
        """
    )
    
    parser.add_argument(
        'query',
        nargs='?',
        help='Query to execute (not needed in interactive mode)'
    )
    parser.add_argument(
        '-i', '--interactive',
        action='store_true',
        help='Start interactive mode'
    )
    parser.add_argument(
        '-m', '--model',
        default=None,
        help=f'Model to use (default: from agent_config.toml, currently: {_default_model})'
    )
    parser.add_argument(
        '--no-think',
        action='store_true',
        help='Disable thinking mode (add /no_think to system prompt)'
    )
    
    args = parser.parse_args()
    
    # Use config default if model not specified
    model = args.model if args.model else _default_model
    
    if args.interactive:
        interactive_mode(model, args.no_think)
    elif args.query:
        run_agent_with_ui(args.query, model, args.no_think)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
