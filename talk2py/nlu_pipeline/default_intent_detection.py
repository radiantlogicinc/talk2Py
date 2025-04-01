"""Default implementation of intent detection interface.

This module provides a basic implementation of the IntentDetectionInterface
for classifying and clarifying user intent from queries in talk2py.
"""

from typing import List, Optional, Tuple

from talk2py import CHAT_CONTEXT
from talk2py.nlu_pipeline.nlu_engine_interfaces import IntentDetectionInterface
from talk2py.utils.logging import logger


# pylint: disable=too-few-public-methods
class DefaultIntentDetection(IntentDetectionInterface):
    """Default implementation of intent detection functionality."""

    def _find_best_match(
        self, commands: list[str], user_input: str
    ) -> tuple[Optional[str], int]:
        """Finds the best command match based on user input.

        Args:
            commands: List of available command keys.
            user_input: The user's input string.

        Returns:
            A tuple containing the best matched command key (or None) and the match type
            (0=None, 1=Substring, 2=Exact/Word).
        """
        best_match_cmd: Optional[str] = None
        best_match_type: int = 0  # 0=None, 1=Substring, 2=Exact/Word

        user_input_lower = user_input.lower()
        user_input_lower_padded = f" {user_input_lower} "

        # First pass: Prioritize exact/word matches (type 2)
        for cmd in commands:
            command_name_parts = cmd.split(".")
            command_name_raw = command_name_parts[-1].lower()
            command_name_spaced = command_name_raw.replace("_", " ")

            if (
                f" {command_name_spaced} " in user_input_lower_padded
                or user_input_lower.startswith(f"{command_name_spaced} ")
                or user_input_lower.endswith(f" {command_name_spaced}")
                or user_input_lower == command_name_spaced
            ):
                # Found the best possible match type (spaced exact/word)
                return cmd, 2

            # Check raw version (e.g., "add_todo")
            is_raw_match = (
                f" {command_name_raw} " in user_input_lower_padded
                or user_input_lower.startswith(f"{command_name_raw} ")
                or user_input_lower.endswith(f" {command_name_raw}")
                or user_input_lower == command_name_raw
            )
            if is_raw_match and best_match_type < 2:
                # Found a type 2 raw match, store it but continue (prefer spaced)
                best_match_cmd = cmd
                best_match_type = 2

        # If we found a type 2 raw match in the first pass, return it
        if best_match_type == 2:
            return best_match_cmd, 2

        # Second pass: Find substring matches (type 1) if no type 2 found
        for cmd in commands:
            command_name_parts = cmd.split(".")
            command_name_raw = command_name_parts[-1].lower()
            command_name_spaced = command_name_raw.replace("_", " ")

            # Check for partial keyword matches in commands
            if "subtract" in command_name_raw and "subtract" in user_input_lower:
                return cmd, 1

            if "add" in command_name_raw and "add" in user_input_lower:
                return cmd, 1

            # General substring matches
            if command_name_spaced in user_input_lower:
                return cmd, 1

            if command_name_raw in user_input_lower:
                return cmd, 1

        # No match found
        return None, 0

    def categorize_user_message(self, user_message: str) -> str:
        """Default implementation: categorizes based on simple keywords."""
        user_message_lower = user_message.lower()

        if "abort" in user_message_lower:
            return "abort"

        feedback_keywords = [
            "instead",
            "not what i meant",
            "incorrect",
            "wrong",
            "that's not what i meant",
            "that is not what i meant",
        ]
        return next(
            (
                "feedback"
                for keyword in feedback_keywords
                if keyword in user_message_lower
            ),
            "query",
        )

    def classify_intent(
        self, user_input: str, excluded_intents: Optional[List[str]] = None
    ) -> Tuple[str, float]:
        """Default implementation using command registry."""
        logger.debug("Classifying intent for: %s", user_input)
        excluded = excluded_intents or []

        # Get registry from ChatContext
        app_folderpath = CHAT_CONTEXT.current_app_folderpath
        if app_folderpath is None:
            logger.warning("No app folderpath set in ChatContext")
            return "unknown", 0.0

        registry = CHAT_CONTEXT.get_registry(app_folderpath)
        # Correctly get command keys from the metadata dictionary
        all_commands = list(
            registry.command_metadata.get("map_commandkey_2_metadata", {}).keys()
        )
        if available_commands := [cmd for cmd in all_commands if cmd not in excluded]:
            matched_command, match_type = self._find_best_match(
                available_commands, user_input
            )

            if matched_command:
                intent = matched_command
                # Confidence based on match type
                confidence = 0.9 if match_type == 2 else 0.7
            else:
                intent = "unknown"
                confidence = 0.1

        else:
            intent = "unknown"
            confidence = 0.0
        logger.debug("Classified intent: %s with confidence %s", intent, confidence)
        return intent, confidence

    def clarify_intent(
        self, user_input: str, possible_intents: List[Tuple[str, float]]
    ) -> Optional[str]:
        """Default implementation: picks the highest confidence intent."""
        if not possible_intents:
            return None

        # Simple logic: pick highest confidence
        return sorted(possible_intents, key=lambda x: x[1], reverse=True)[0][0]
