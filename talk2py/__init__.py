"""
talk2Py module provides utilities for creating Python commands
that can be called from natural language.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Union

from pydantic import BaseModel


@dataclass
class Action:
    """Represents a command action to be executed.

    This class encapsulates a command key and its associated parameters,
    providing a structured way to represent command invocations.

    Attributes:
        command_key: The unique identifier for the command to execute
        parameters: Dictionary of parameters for the command
    """

    command_key: str
    parameters: Dict[str, Any] = field(default_factory=dict)


def command(func):
    """
    Decorator to mark a function as a command.
    """
    return func
