"""
Type definitions for talk2py.

This module contains custom type definitions, type aliases, and Pydantic models
used throughout the talk2py framework to ensure type consistency and reduce complexity
of nested type annotations.
"""

from typing import Any, Callable, Dict, Optional, Type, TypeAlias, Union

from pydantic import BaseModel

# Basic value types
ParamValue = Union[str, bool, int, float]
ExtendedParamValue = Union[str, bool, int, float, BaseModel]

# Command related type aliases
CommandMetadata: TypeAlias = Dict[str, Any]
CommandFunc: TypeAlias = Callable[..., Any]
CommandClass: TypeAlias = Type[Any]
PropertyFunc: TypeAlias = Callable[..., Any]

# Complex type models
class ContextData(BaseModel):
    """Model for storing context data values."""
    value: Optional[ParamValue] = None

class AppContext(BaseModel):
    """Model for storing application context data."""
    data: Dict[str, ContextData] = {}

class ConversationArtifacts(BaseModel):
    """Model for storing conversation artifacts."""
    data: Dict[str, Optional[ExtendedParamValue]] = {}

# Type aliases for common dictionary patterns
# RegistryCache: TypeAlias = Dict[str, 'CommandRegistry']  # type: ignore # noqa
# Instead of type alias, we'll use a forward reference to the actual class
from typing import ForwardRef
RegistryCache = ForwardRef('RegistryCache')

ObjectCache: TypeAlias = Dict[str, Optional[Any]]
AppContextCache: TypeAlias = Dict[str, Optional[Dict[str, Optional[ParamValue]]]]

# Type alias for conversation history entries
ConversationEntry: TypeAlias = tuple[str, str, Optional[ConversationArtifacts]]
ConversationHistory: TypeAlias = list[ConversationEntry]

__all__ = [
    'ParamValue', 'ExtendedParamValue', 
    'CommandMetadata', 'CommandFunc', 'CommandClass', 'PropertyFunc',
    'ContextData', 'AppContext', 'ConversationArtifacts',
    'RegistryCache', 'ObjectCache', 'AppContextCache',
    'ConversationEntry', 'ConversationHistory'
] 