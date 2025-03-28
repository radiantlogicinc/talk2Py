"""
Chat context module for talk2py.

This module provides the ChatContext class which manages the current application
context and registry caching for the talk2py framework.
"""

import sys
from typing import Any, Optional, TypeAlias
from dataclasses import dataclass, field

from talk2py.command_registry import CommandRegistry
from talk2py.types import (
    ConversationHistory, ConversationArtifacts,
    ConversationEntry
)

RegistryCache: TypeAlias = dict[str, CommandRegistry]

@dataclass
class AppContext:
    registry: CommandRegistry
    current_object: Optional[Any] = None
    context_data: dict[str, Any] = field(default_factory=dict)

class ConversationHistory:
    """Manages conversation history entries."""
    
    def __init__(self):
        self._history: list[ConversationEntry] = []
    
    def append(self, entry: ConversationEntry) -> None:
        """Append an entry to the history."""
        self._history.append(entry)
    
    def get_entries(self, last_n: int = -1) -> list[ConversationEntry]:
        """Get conversation entries.
        
        Args:
            last_n: Number of most recent entries to return. -1 returns all entries.
        """
        return self._history if last_n == -1 else self._history[-last_n:]
    
    def clear(self) -> None:
        """Clear all entries from history."""
        self._history.clear()
    
    def __len__(self) -> int:
        return len(self._history)

class ChatContext:
    """Manages the current application context and registry caching.

    This class provides centralized management of:
    1. The current application folder path
    2. The current context object
    3. A cache of CommandRegistry instances by app folder path
    """

    def __init__(self):
        self._current_app_folderpath: Optional[str] = None
        # Replace separate caches with a single app contexts dictionary
        self._app_contexts: dict[str, AppContext] = {}
        self._conversation_history_cache: ConversationHistory = ConversationHistory()

    @property
    def current_app_folderpath(self) -> Optional[str]:
        """Get the current application folder path."""
        return self._current_app_folderpath

    @current_app_folderpath.setter
    def current_app_folderpath(self, app_folderpath: str) -> None:
        """Set the current application folder path."""
        # Raise error if the app hasn't been registered
        if app_folderpath not in self._app_contexts:
            raise ValueError(
                f"App folder path '{app_folderpath}' has not been registered. Call register_app first."
            )

        # Remove the current app folder path from sys.path if it exists
        if self._current_app_folderpath and self._current_app_folderpath in sys.path:
            sys.path.remove(self._current_app_folderpath)

        # Set the new app folder path
        self._current_app_folderpath = app_folderpath

        # Add the new app folder path to sys.path
        if app_folderpath not in sys.path:
            sys.path.insert(0, app_folderpath)

    def register_app(self, app_folderpath: str) -> None:
        """Register an application folder path and initialize its registry."""
        # Initialize the app context if it doesn't exist
        if app_folderpath not in self._app_contexts:
            registry = CommandRegistry(app_folderpath)
            self._app_contexts[app_folderpath] = AppContext(registry=registry)

        self.current_app_folderpath = app_folderpath

    @property
    def app_context(self) -> dict[str, Any]:
        """Get the current application context dictionary."""
        if self._current_app_folderpath is None:
            raise ValueError("No current application folder path is set")
        
        return self._app_contexts[self._current_app_folderpath].context_data

    @app_context.setter
    def app_context(self, app_context_dict: dict[str, Any]) -> None:
        """Set the application context dictionary."""
        if self._current_app_folderpath is None:
            raise ValueError("No current application folder path is set")
        
        self._app_contexts[self._current_app_folderpath].context_data = app_context_dict

    @property
    def current_object(self) -> Optional[Any]:
        """Get the current context object."""
        if self._current_app_folderpath is None:
            raise ValueError("No current application folder path is set")
        
        return self._app_contexts[self._current_app_folderpath].current_object

    @current_object.setter
    def current_object(self, current_object: Any) -> None:
        """Set the current context object."""
        if self._current_app_folderpath is None:
            raise ValueError("No current application folder path is set")
        
        self._app_contexts[self._current_app_folderpath].current_object = current_object

    def get_registry(self, app_folderpath: str) -> CommandRegistry:
        """Get a CommandRegistry instance for the specified application folder."""
        # Check if app context exists
        if app_folderpath not in self._app_contexts:
            self.register_app(app_folderpath)
            
        return self._app_contexts[app_folderpath].registry

    def append_to_conversation_history(
        self,
        query: str,
        response: str,
        artifacts: Optional[ConversationArtifacts] = None,
    ) -> None:
        """Append a conversation entry to the history."""
        entry: ConversationEntry = (query, response, artifacts)
        self._conversation_history_cache.append(entry)

    def get_conversation_history(self, last_n: int = -1) -> list[ConversationEntry]:
        """Get the conversation history.
        
        Args:
            last_n: Number of most recent conversations to return. -1 returns all items.
        """
        return self._conversation_history_cache.get_entries(last_n)

    def clear_conversation_history(self) -> None:
        """Clear all entries from the conversation history."""
        self._conversation_history_cache.clear()

    def reset(self) -> None:
        """Reset all state in the ChatContext instance."""
        self._current_app_folderpath = None
        self._app_contexts.clear()
        self._conversation_history_cache.clear()
