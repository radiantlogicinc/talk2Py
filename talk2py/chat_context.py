"""
Chat context module for talk2py.

This module provides the ChatContext class which manages the current application
context and registry caching for the talk2py framework.
"""

import sys
from typing import Any, Dict, Optional, Union

from pydantic import BaseModel

from talk2py.command_registry import CommandRegistry


class ChatContext:
    """Manages the current application context and registry caching.

    This class provides centralized management of:
    1. The current application folder path
    2. The current context object
    3. A cache of CommandRegistry instances by app folder path
    """

    _current_app_folderpath: Optional[str] = None
    # Registry cache for storing CommandRegistry instances keyed by app_folderpath
    _registry_cache: Dict[str, CommandRegistry] = {}
    # Cache for storing current object keyed by app_folderpath
    _current_object_cache: Dict[str, Optional[Any]] = {}
    # Cache for storing app_context_dictionary keyed by app_folderpath
    _app_context_cache: Dict[
        str, Optional[Dict[str, Optional[Union[str, bool, int, float]]]]
    ] = {}
    # Cache for storing conversation history keyed by app_folderpath
    _conversation_history_cache: list[
        tuple[
            str,
            str,
            Optional[Dict[str, Optional[Union[str, bool, int, float, BaseModel]]]],
        ]
    ] = []

    @property
    def current_app_folderpath(self) -> Optional[str]:
        """Get the current application folder path."""
        return self._current_app_folderpath

    @current_app_folderpath.setter
    def current_app_folderpath(self, app_folderpath: str) -> None:
        """Set the current application folder path.

        Args:
            app_folderpath: Path to the application folder

        Raises:
            ValueError: If the app_folderpath has not been registered
        """
        # Raise error if the app hasn't been registered
        if app_folderpath not in self._registry_cache:
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
        """Register an application folder path and initialize its registry.

        Args:
            app_folderpath: Path to the application folder
        """
        # Initialize the registry for this app if it doesn't exist
        if app_folderpath not in self._registry_cache:
            # Create a new registry and add it to the cache
            self._registry_cache[app_folderpath] = CommandRegistry(app_folderpath)

        # Initialize the context cache entry if it doesn't exist
        if app_folderpath not in self._current_object_cache:
            self._current_object_cache[app_folderpath] = None

        self.current_app_folderpath = app_folderpath

    @property
    def app_context(self) -> Dict[str, Any]:
        """Get the current application context dictionary."""
        if self._current_app_folderpath is None:
            raise ValueError("No current application folder path is set")

        # Get the context Dict or return an empty Dict if None
        return self._app_context_cache.get(self._current_app_folderpath) or {}

    @app_context.setter
    def app_context(self, app_context_dict: Dict[str, Any]) -> None:
        """Set the application context dictionary.

        Args:
            app_context: Dictionary containing application context data
        """
        if self._current_app_folderpath is None:
            raise ValueError("No current application folder path is set")

        self._app_context_cache[self._current_app_folderpath] = app_context_dict

    @property
    def current_object(self) -> Optional[Any]:
        """Get the current context object.

        Returns:
            The current context object, or None if not set or if no app path is set
        """
        if self._current_app_folderpath is None:
            raise ValueError("No current application folder path is set")

        return self._current_object_cache.get(self._current_app_folderpath)

    @current_object.setter
    def current_object(self, current_object: Any) -> None:
        """Set the current context object.

        Args:
            context_object: The object to set as the current context

        Raises:
            ValueError: If no current application folder path is set
        """
        if self._current_app_folderpath is None:
            raise ValueError("No current application folder path is set")

        self._current_object_cache[self._current_app_folderpath] = current_object

    def get_registry(self, app_folderpath: str) -> CommandRegistry:
        """Get a CommandRegistry instance for the specified application folder.

        This function maintains a cache of registry instances to avoid
        redundant loading of command metadata.

        Args:
            app_folderpath: Path to the application folder

        Returns:
            A CommandRegistry instance for the specified application folder
        """
        # Check if a registry exists in the cache
        if app_folderpath not in self._registry_cache:
            # Create a new registry and add it to the cache
            self._registry_cache[app_folderpath] = CommandRegistry(app_folderpath)

        return self._registry_cache[app_folderpath]

    def append_to_conversation_history(
        self,
        query: str,
        response: str,
        artifacts: Optional[
            Dict[str, Optional[Union[str, bool, int, float, BaseModel]]]
        ] = None,
    ) -> None:
        """Append a conversation entry to the history.

        Args:
            query: The user's query
            response: The system's response
            artifacts: Optional dictionary of additional data related to the conversation
        """
        self._conversation_history_cache.append((query, response, artifacts))

    def get_conversation_history(self, last_n: int = -1) -> list[
        tuple[
            str,
            str,
            Optional[Dict[str, Optional[Union[str, bool, int, float, BaseModel]]]],
        ]
    ]:
        """Get the conversation history.

        Args:
            last_n: Number of most recent conversations to return. -1 returns all items.

        Returns:
            List of (query, response) tuples from the conversation history
        """
        return (
            self._conversation_history_cache
            if last_n == -1
            else self._conversation_history_cache[-last_n:]
        )

    def clear_conversation_history(self) -> None:
        """Clear all entries from the conversation history."""
        self._conversation_history_cache.clear()
