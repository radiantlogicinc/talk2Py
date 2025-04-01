"""Utility functions for the NLU pipeline."""

from enum import Enum


class MetaCommandType(Enum):
    """Types of meta-commands that bypass standard processing."""

    CANCEL = "cancel"
    RESET = "reset"
    HELP = "help"
    NONE = "none"  # Indicates no meta-command detected


def check_for_meta_commands(user_message: str) -> MetaCommandType:
    """Checks if the user input matches a known meta-command."""
    normalized_message = user_message.strip().lower()

    # Simple exact match for now, could use regex or fuzzy matching
    if normalized_message in ["cancel", "never mind", "nevermind", "stop", "abort"]:
        return MetaCommandType.CANCEL
    if normalized_message in ["reset", "start over"]:
        return MetaCommandType.RESET
    if normalized_message in ["help", "/help"]:
        return MetaCommandType.HELP

    # Add checks for other meta commands if needed

    return MetaCommandType.NONE


# Add other NLU utilities if this file is used for more
