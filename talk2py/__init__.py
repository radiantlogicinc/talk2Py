"""
talk2Py module provides utilities for creating Python commands
that can be called from natural language.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from talk2py.command_registry import CommandRegistry

# The object currently in focus. This determines the commands that will be exposed
CURRENT_CONTEXT: Optional[Any] = None

# Registry cache for storing CommandRegistry instances keyed by app_folderpath
_REGISTRY_CACHE: Dict[str, CommandRegistry] = {}


@dataclass
class Action:
    """Represents a command action to be executed.

    This class encapsulates a command key and its associated parameters,
    providing a structured way to represent command invocations.

    Attributes:
        command_key: The unique identifier for the command to execute
        parameters: Dictionary of parameters for the command
    """

    app_folderpath: str
    command_key: str
    parameters: Dict[str, Any] = field(default_factory=dict)


def command(func):
    """
    Decorator to mark a function as a command.
    """
    return func


def get_registry(app_folderpath: str) -> CommandRegistry:
    """Get a CommandRegistry instance for the specified application folder.

    This function maintains a cache of registry instances to avoid
    redundant loading of command metadata.

    Args:
        app_folderpath: Path to the application folder

    Returns:
        A CommandRegistry instance for the specified application folder
    """
    # Check if a registry exists in the cache
    if app_folderpath not in _REGISTRY_CACHE:
        # Create a new registry and add it to the cache
        _REGISTRY_CACHE[app_folderpath] = CommandRegistry(app_folderpath)

    return _REGISTRY_CACHE[app_folderpath]
