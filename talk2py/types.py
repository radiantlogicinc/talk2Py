"""
Type definitions for talk2py.

This module contains custom type definitions, type aliases, and Pydantic models
used throughout the talk2py framework to ensure type consistency and reduce complexity
of nested type annotations.
"""

from typing import TYPE_CHECKING, Any, Callable, Optional, Type, TypeAlias, Union

from pydantic import BaseModel

if TYPE_CHECKING:
    from talk2py.command_registry import CommandRegistry

# Basic value types
ParamValue = Union[str, bool, int, float]
ExtendedParamValue = Union[str, bool, int, float, BaseModel]

# Command related type aliases
CommandMetadata: TypeAlias = dict[str, Any]
CommandFunc: TypeAlias = Callable[..., Any]
CommandClass: TypeAlias = Type[Any]
PropertyFunc: TypeAlias = Callable[..., Any]


# Complex type models
class ContextValue(BaseModel):
    """Model for storing context data values."""

    value: Optional[ParamValue] = None


class ContextDict(BaseModel):
    """Model for storing application context data structure."""

    data: dict[str, ContextValue] = {}


class ConversationArtifacts(BaseModel):
    """Model for storing conversation artifacts."""

    data: dict[str, Optional[ExtendedParamValue]] = {}


# Type aliases for common dictionary patterns
ObjectCache: TypeAlias = dict[str, Optional[Any]]
AppContextCache: TypeAlias = dict[str, Optional[dict[str, Optional[ParamValue]]]]

# Type alias for conversation history entries
ConversationEntry: TypeAlias = tuple[str, str, Optional[ConversationArtifacts]]
ConversationHistory: TypeAlias = list[ConversationEntry]

__all__ = [
    "ParamValue",
    "ExtendedParamValue",
    "CommandMetadata",
    "CommandFunc",
    "CommandClass",
    "PropertyFunc",
    "ContextDict",
    "ConversationArtifacts",
    "ObjectCache",
    "AppContextCache",
    "ConversationEntry",
    "ConversationHistory",
]
