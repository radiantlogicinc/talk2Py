"""
talk2Py module provides utilities for creating Python commands
that can be called from natural language.
"""

import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Union

from talk2py.chat_context import ChatContext
from talk2py.command_registry import CommandRegistry

_env_vars: Dict[str, str] = {}  # Initialize the global variable with type annotation

# Global instance of ChatContext to be used throughout the application
CHAT_CONTEXT = ChatContext()


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

    This is a compatibility function that forwards to CHAT_CONTEXT.get_registry.

    Args:
        app_folderpath: Path to the application folder

    Returns:
        A CommandRegistry instance for the specified application folder
    """
    return CHAT_CONTEXT.get_registry(app_folderpath)


def get_env_var(
    var_name: str,
    var_type: type = str,
    default: Optional[Union[str, int, float, bool]] = None,
) -> Union[str, int, float, bool]:
    """get the environment variable"""
    value = _env_vars.get(var_name)
    if value is None:
        if default is not None:
            return default
        value = os.getenv(var_name)

    if value is None:
        raise ValueError(
            f"Environment variable '{var_name}' does not exist and no default value is provided."
        )

    try:
        if var_type is int:
            return int(value)
        if var_type is float:
            return float(value)
        if var_type is bool:
            if value.lower() in ("true", "1"):
                return True
            if value.lower() in ("false", "0"):
                return False
            raise ValueError(f"Cannot convert '{value}' to {var_type.__name__}.")
        return str(value)  # Default case for str
    except ValueError as e:
        raise ValueError(f"Cannot convert '{value}' to {var_type.__name__}.") from e
