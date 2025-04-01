"""
Chat context module for talk2py.

This module provides the ChatContext class which manages the current application
context and registry caching for the talk2py framework.
"""

import json
import importlib
import sys
import murmurhash  # type: ignore # Missing library stubs
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, TypeAlias

from speedict import Rdict  # pylint: disable=no-name-in-module

# Correct the import path
from talk2py.code_parsing.command_registry import CommandRegistry
from talk2py.types import (
    ContextDict,
    ContextValue,
    ConversationArtifacts,
    ConversationEntry,
)

RegistryCache: TypeAlias = dict[str, CommandRegistry]


@dataclass
class AppContext:
    """Represents the context of a specific application.

    This class holds the CommandRegistry, current object, and context data
    associated with a particular application within the ChatContext.
    """

    registry: CommandRegistry
    """The CommandRegistry instance for the application."""
    current_object: Optional[Any] = None
    """The current object in the application's context."""
    context_data: dict[str, Any] = field(default_factory=dict)
    """A dictionary to store arbitrary context data for the application."""


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


# pylint: disable=too-many-public-methods
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
        # Initialize user_id with default value
        self._user_id: str = "user_id"
        # Session ID will be generated as needed based on user_id and app_folderpath

    @property
    def user_id(self) -> str:
        """Get the current user ID."""
        return self._user_id

    @user_id.setter
    def user_id(self, user_id: str) -> None:
        """Set the current user ID."""
        self._user_id = user_id

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
        # Do not reset the user_id as it should persist across resets

    @property
    def current_session_id(self) -> str:
        """Get the current session ID.

        Session ID is deterministically generated based on user_id and app_folderpath.
        """
        if self._current_app_folderpath is None:
            raise ValueError("No current application folder path is set")

        # Generate session ID using murmurhash with the format '<app_folderpath>/<user_id>'
        session_key = f"{self._current_app_folderpath}/{self._user_id}"
        # Use murmurhash library directly
        hash_value = murmurhash.hash(session_key.encode())
        return hex(hash_value)

    def _get_session_storage_path(self, session_id: Optional[str] = None) -> Path:
        """Get the path to store session data.

        Args:
            session_id: Optional session ID to use. If None, uses current session ID.

        Returns:
            Path to session storage directory

        Raises:
            ValueError: If no current application folder path is set
        """
        if self._current_app_folderpath is None:
            raise ValueError("No current application folder path is set")

        session_id = session_id or self.current_session_id
        storage_path = (
            Path(self._current_app_folderpath) / "___conversation_history" / session_id
        )

        # Create the directory if it doesn't exist
        storage_path.mkdir(parents=True, exist_ok=True)

        return storage_path

    def save_conversation_history(self, session_id: Optional[str] = None) -> str:
        """Save conversation history to disk using Rdict.

        Args:
            session_id: Optional session ID to use. If None, uses current session ID.

        Returns:
            Path to the saved file

        Raises:
            ValueError: If no current application folder path is set
        """
        storage_path = self._get_session_storage_path(session_id)
        history_path = storage_path / "conversation_history.rdict"

        # Convert conversation history to a format that can be saved
        history_data = []
        for (
            query,
            response,
            artifacts,
        ) in self._conversation_history_cache.get_entries():
            entry_data = {
                "query": query,
                "response": response,
                "artifacts": artifacts.model_dump_json() if artifacts else None,
            }
            history_data.append(entry_data)

        # Create and save the Rdict
        history_rdict = Rdict(str(history_path))
        history_rdict["history"] = history_data

        return str(history_path)

    def load_conversation_history(self, session_id: Optional[str] = None) -> None:
        # sourcery skip: class-extract-method
        """Load conversation history from disk using Rdict.

        Args:
            session_id: Optional session ID to use. If None, uses current session ID.

        Raises:
            ValueError: If no current application folder path is set
            FileNotFoundError: If the conversation history file doesn't exist
        """
        storage_path = self._get_session_storage_path(session_id)
        history_path = storage_path / "conversation_history.rdict"

        if not history_path.exists():
            raise FileNotFoundError(
                f"Conversation history file not found: {history_path}"
            )

        # Open the Rdict
        history_rdict = Rdict(str(history_path))
        history_data = history_rdict.get("history", [])

        # Clear existing history and load from file
        self._conversation_history_cache.clear()

        # Add type check to avoid "object is not iterable" error
        if history_data is not None:
            for entry in history_data:
                query = entry["query"]
                response = entry["response"]
                artifacts_json = entry.get("artifacts")

                artifacts = None
                if artifacts_json:
                    # Use model_validate_json instead of parse_raw (Pydantic v2 compatible)
                    artifacts = ConversationArtifacts.model_validate_json(
                        artifacts_json
                    )

                self.append_to_conversation_history(query, response, artifacts)

    def save_context_data(self, session_id: Optional[str] = None) -> str:
        """Save context data to disk using Rdict.

        Args:
            session_id: Optional session ID to use. If None, uses current session ID.

        Returns:
            Path to the saved file

        Raises:
            ValueError: If no current application folder path is set
        """
        if self._current_app_folderpath is None:
            raise ValueError("No current application folder path is set")

        storage_path = self._get_session_storage_path(session_id)
        context_path = storage_path / "context_data.rdict"

        # Convert context data to a format that can be saved
        context_dict = ContextDict(
            data={
                key: ContextValue(value=value)
                for key, value in self.app_context.items()
                if isinstance(value, (str, bool, int, float)) or value is None
            }
        )

        # Create and save the Rdict
        context_rdict = Rdict(str(context_path))
        context_rdict["context"] = context_dict.model_dump()

        return str(context_path)

    def load_context_data(self, session_id: Optional[str] = None) -> None:
        """Load context data from disk using Rdict.

        Args:
            session_id: Optional session ID to use. If None, uses current session ID.

        Raises:
            ValueError: If no current application folder path is set
            FileNotFoundError: If the context data file doesn't exist
        """
        storage_path = self._get_session_storage_path(session_id)
        context_path = storage_path / "context_data.rdict"

        if not context_path.exists():
            raise FileNotFoundError(f"Context data file not found: {context_path}")

        # Open the Rdict
        context_rdict = Rdict(str(context_path))
        context_data_dict = context_rdict.get("context", {})
        context_data = (
            context_data_dict.get("data", {}) if context_data_dict is not None else {}
        )

        new_context = {
            key: value_dict["value"]
            for key, value_dict in context_data.items()
            if isinstance(value_dict, dict) and "value" in value_dict
        }
        # Set the application context
        self.app_context = new_context

    def save_current_object(self, session_id: Optional[str] = None) -> str:
        """Save current object's state to disk using JSON.

        Args:
            session_id: Optional session ID to use. If None, uses current session ID.

        Returns:
            Path to the saved JSON state file.

        Raises:
            ValueError: If no current application folder path is set or no current object.
            TypeError: If the current object's state cannot be serialized to JSON.
        """
        if self._current_app_folderpath is None:
            raise ValueError("No current application folder path is set")

        if self.current_object is None:
            raise ValueError("No current object to save")

        storage_path = self._get_session_storage_path(session_id)
        object_state_path = storage_path / "current_object_state.json"
        object_info_path = storage_path / "current_object_info.rdict"

        # Prepare object state for JSON serialization
        try:
            # Check if the object is a dictionary type
            if isinstance(self.current_object, dict):
                object_state = self.current_object
                object_class_name = "dict"
                object_module_name = "builtins"
            else:
                # Using vars() for objects with __dict__ attribute
                object_state = vars(self.current_object)
                object_class_name = self.current_object.__class__.__name__
                object_module_name = self.current_object.__class__.__module__

            # Ensure the state itself is JSON serializable
            json.dumps(object_state)
        except TypeError as e:
            raise TypeError(
                f"Current object state is not JSON serializable: {e}"
            ) from e

        # Save state using JSON
        with open(object_state_path, "w", encoding="utf-8") as f:
            json.dump(object_state, f, indent=4)

        # Save object class name and module for reconstruction
        # Create and save the Rdict for metadata
        object_info = Rdict(str(object_info_path))
        object_info["class_name"] = object_class_name
        object_info["module_name"] = object_module_name

        return str(object_state_path)

    def load_current_object(self, session_id: Optional[str] = None) -> None:
        """Load current object from disk using JSON state and class info.

        Args:
            session_id: Optional session ID to use. If None, uses current session ID.

        Raises:
            ValueError: If no current application folder path is set.
            FileNotFoundError: If the current object state or info file doesn't exist.
            ImportError: If the object's class cannot be imported.
            Exception: If object instantiation or state restoration fails.
        """
        storage_path = self._get_session_storage_path(session_id)
        object_state_path = storage_path / "current_object_state.json"
        object_info_path = storage_path / "current_object_info.rdict"

        if not object_state_path.exists():
            raise FileNotFoundError(
                f"Current object state file not found: {object_state_path}"
            )
        if not object_info_path.exists():
            raise FileNotFoundError(
                f"Current object info file not found: {object_info_path}"
            )

        # Load object metadata
        object_info = Rdict(str(object_info_path))
        class_name = object_info.get("class_name")
        module_name = object_info.get("module_name")

        if not class_name or not module_name:
            raise ValueError("Class name or module name missing in object info file.")

        # Load state using JSON
        with open(object_state_path, "r", encoding="utf-8") as f:
            object_state = json.load(f)

        # Special case for dictionary objects
        if class_name == "dict" and module_name == "builtins":
            self.current_object = object_state
            return

        try:
            # Dynamically import the module and get the class
            module = importlib.import_module(module_name)
            obj_class = getattr(module, class_name)
        except (ImportError, AttributeError) as e:
            raise ImportError(
                f"Failed to import class {class_name} from module {module_name}: {e}"
            ) from e

        try:
            # Instantiate the object (assuming a constructor that doesn't require arguments
            # or can be called without arguments for initial creation)
            # If the constructor needs args, this approach needs refinement.
            current_object = obj_class()

            # Restore the state by updating the object's __dict__
            # This might overwrite methods or properties if keys clash.
            # A safer approach might involve a dedicated `__setstate__` or update method.
            current_object.__dict__.update(object_state)

        except Exception as e:
            raise Exception(
                f"Failed to instantiate or restore state for object {class_name}: {e}"
            ) from e

        # Set as current object
        self.current_object = current_object

    def save_session(self, session_id: Optional[str] = None) -> Dict[str, str]:
        """Save all session data to disk.

        This saves conversation history, context data, and current object.

        Args:
            session_id: Optional session ID to use. If None, uses current session ID.

        Returns:
            Dictionary with paths to saved files

        Raises:
            ValueError: If no current application folder path is set
        """
        if self._current_app_folderpath is None:
            raise ValueError("No current application folder path is set")

        session_id = session_id or self.current_session_id
        paths = {"conversation_history": self.save_conversation_history(session_id)}

        # Save context data
        paths["context_data"] = self.save_context_data(session_id)

        # Save current object if it exists
        if self.current_object is not None:
            try:
                paths["current_object"] = self.save_current_object(session_id)
            except TypeError as e:
                print(
                    f"Warning: Could not save current object due to non-JSON serializable state: {e}"
                )
                if "current_object" in paths:
                    del paths["current_object"]

        # Save session info
        storage_path = self._get_session_storage_path(session_id)
        session_info_path = storage_path / "session_info.rdict"

        # Create and save the Rdict
        session_info = Rdict(str(session_info_path))
        session_info["app_folderpath"] = self._current_app_folderpath
        session_info["session_id"] = session_id
        session_info["user_id"] = self._user_id
        session_info["saved_components"] = list(paths.keys())

        paths["session_info"] = str(session_info_path)

        return paths

    def load_session(self, session_id: Optional[str] = None) -> Dict[str, bool]:
        """Load all session data from disk.

        This loads conversation history, context data, and current object.

        Args:
            session_id: Session ID to load. If None, uses the current session ID.

        Returns:
            Dictionary indicating success of loading each component

        Raises:
            ValueError: If no current application folder path is set
            FileNotFoundError: If the session info file doesn't exist
        """
        if self._current_app_folderpath is None:
            raise ValueError("No current application folder path is set")

        session_id = session_id or self.current_session_id
        storage_path = (
            Path(self._current_app_folderpath) / "___conversation_history" / session_id
        )
        session_info_path = storage_path / "session_info.rdict"

        if not session_info_path.exists():
            raise FileNotFoundError(f"Session info file not found: {session_info_path}")

        # Open the Rdict
        session_info = Rdict(str(session_info_path))
        app_folderpath = session_info.get("app_folderpath", "")

        # Make sure we're in the right application context
        if app_folderpath and app_folderpath != self._current_app_folderpath:
            self.register_app(app_folderpath)

        # Load the user_id from session info if available
        if "user_id" in session_info:
            self._user_id = session_info["user_id"]

        # Load conversation history
        self.load_conversation_history(session_id)
        # Load context data
        self.load_context_data(session_id)
        # Load current object
        self.load_current_object(session_id)

        results: Dict[str, bool] = {}

        # Load session info
        saved_components: List[Any]
        raw_saved_components = session_info.get("saved_components")
        if isinstance(raw_saved_components, list):
            saved_components = raw_saved_components
        else:
            # If not a list (or None), default to an empty list
            saved_components = []
            # Optionally log a warning if raw_saved_components was not None but also not a list

        # Load conversation history
        try:
            if "conversation_history" in saved_components:
                self.load_conversation_history(session_id)
                results["conversation_history"] = True
            else:
                results["conversation_history"] = False
        except FileNotFoundError:
            results["conversation_history"] = False
            print(
                f"Warning: Conversation history file not found for session {session_id}"
            )

        # Load context data
        try:
            if "context_data" in saved_components:
                self.load_context_data(session_id)
                results["context_data"] = True
            else:
                results["context_data"] = False
        except FileNotFoundError:
            results["context_data"] = False
            print(f"Warning: Context data file not found for session {session_id}")

        # Load current object
        try:
            if "current_object" in saved_components:
                self.load_current_object(session_id)
                results["current_object"] = True
            else:
                results["current_object"] = False
                self.current_object = None
        except (FileNotFoundError, ImportError, ValueError, Exception) as e:
            results["current_object"] = False
            print(
                f"Warning: Failed to load current object for session {session_id}: {e}"
            )
            self.current_object = None

        return results

    def list_sessions(self) -> List[str]:
        """List all available sessions for the current application.

        Returns:
            List of session IDs

        Raises:
            ValueError: If no current application folder path is set
        """
        if self._current_app_folderpath is None:
            raise ValueError("No current application folder path is set")

        history_dir = Path(self._current_app_folderpath) / "___conversation_history"

        if not history_dir.exists():
            return []

        return [d.name for d in history_dir.iterdir() if d.is_dir()]

    def get_session_id_for_user(self, user_id: str) -> str:
        """Generate a session ID for a specific user.

        Args:
            user_id: User ID to generate session ID for

        Returns:
            Session ID based on the current app_folderpath and the given user_id

        Raises:
            ValueError: If no current application folder path is set
        """
        if self._current_app_folderpath is None:
            raise ValueError("No current application folder path is set")

        # Generate session ID using murmurhash with the format '<app_folderpath>/<user_id>'
        session_key = f"{self._current_app_folderpath}/{user_id}"
        # Use murmurhash library directly
        hash_value = murmurhash.hash(session_key.encode())
        return hex(hash_value)
