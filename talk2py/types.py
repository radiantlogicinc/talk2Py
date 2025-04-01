"""
Type definitions for talk2py.

This module contains custom type definitions, type aliases, and Pydantic models
used throughout the talk2py framework to ensure type consistency and reduce complexity
of nested type annotations.
"""

from typing import (
    Any,
    Callable,
    Optional,
    Type,
    TypeAlias,
    # dict, # Removed - built-in type
    # list, # Removed - built-in type
)

from pydantic import BaseModel, Field

# Basic value types
ParamValue = str | bool | int | float
ExtendedParamValue = str | bool | int | float | BaseModel | dict[str, Any] | list[Any]

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


# Define NLUArtifacts first
class NLUArtifacts(BaseModel):
    """Model for storing NLU pipeline artifacts."""

    state: Optional[str] = None
    intent: Optional[str] = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    excluded_intents: list[str] = Field(default_factory=list)
    confidence_score: float = 0.0
    is_reset: bool = False


class ConversationArtifacts(BaseModel):
    """Model for storing conversation artifacts."""

    data: dict[str, Optional[ExtendedParamValue]] = Field(default_factory=dict)
    nlu: Optional[NLUArtifacts] = None


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
