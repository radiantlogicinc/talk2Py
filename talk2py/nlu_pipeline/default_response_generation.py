"""Default implementation of response generation interface.

This module provides a basic implementation of the ResponseGenerationInterface
for generating human-readable responses based on command execution in talk2py.
"""

import dspy  # type: ignore
from typing import Dict, Any, Optional, List, Tuple # Added Any, Optional, List, Tuple

import talk2py
from talk2py.nlu_pipeline.nlu_engine_interfaces import ResponseGenerationInterface
from talk2py import CHAT_CONTEXT # Added CHAT_CONTEXT
from talk2py.utils.logging import logger # Added logger


# pylint: disable=too-few-public-methods
class DefaultResponseGeneration(ResponseGenerationInterface):
    """Default implementation of response generation functionality."""

    def generate_response(
        self,
        command: str,
        execution_results: dict[str, str],
    ) -> str:
        """Generate a human readable response based on command execution results.

        Args:
            command: The natural language command.
            execution_results: Dictionary containing results obtained by executing the command.

        Returns:
            str: A human readable response describing the execution results.
        """
        lm = dspy.LM(
            model=talk2py.get_env_var("LLM"),
            api_key=talk2py.get_env_var("LITELLM_API_KEY"),
        )
        with dspy.context(lm=lm):
            return dspy.Predict("command, execution_results -> result_summary")(
                command=command, execution_results=execution_results
            ).result_summary

    def categorize_user_message(
        self, user_message: str
    ) -> str:
        """Default implementation: categorizes based on simple keywords."""
        if "abort" in user_message.lower():
            return "abort"

        feedback_keywords = ["instead", "not what I meant", "incorrect", "wrong"]
        if any(keyword in user_message.lower() for keyword in feedback_keywords):
            return "feedback"

        return "query"

    def classify_intent(
        self, user_input: str, excluded_intents: Optional[List[str]] = None
    ) -> Tuple[str, float]:
        """Default implementation using command registry."""
        logger.debug(f"Classifying intent for: {user_input}")
        excluded = excluded_intents or []

        # Get registry from ChatContext
        registry = CHAT_CONTEXT.get_registry(CHAT_CONTEXT.current_app_folderpath)
        # Correctly get command keys from the metadata dictionary
        available_commands = list(registry.command_metadata.get("map_commandkey_2_metadata", {}).keys())

        # Filter out excluded intents
        available_commands = [cmd for cmd in available_commands if cmd not in excluded]

        if available_commands:
            matched_command = None
            best_match_type = 0 # 0=None, 1=Substring, 2=Exact/Word

            for cmd in available_commands:
                command_name_parts = cmd.split('.')
                # Use the last part, and also consider a version with underscores replaced by spaces
                command_name_raw = command_name_parts[-1].lower()
                command_name_spaced = command_name_raw.replace('_', ' ')
                
                # Check for exact match or match as whole word(s)
                # Use regex boundary \b for better word matching
                # Need to escape command name for regex if using re.search
                # Simplified check for now:
                user_input_lower_padded = f' {user_input.lower()} '
                
                # Check spaced version first (e.g., "add todo")
                if f' {command_name_spaced} ' in user_input_lower_padded or user_input.lower().startswith(f'{command_name_spaced} ') or user_input.lower().endswith(f' {command_name_spaced}') or user_input.lower() == command_name_spaced:
                    matched_command = cmd
                    best_match_type = 2
                    break # Prefer first whole word match (spaced)
                # Check raw version (e.g., "add_todo")
                elif f' {command_name_raw} ' in user_input_lower_padded or user_input.lower().startswith(f'{command_name_raw} ') or user_input.lower().endswith(f' {command_name_raw}') or user_input.lower() == command_name_raw:
                    if best_match_type < 2:
                         matched_command = cmd
                         best_match_type = 2
                         # Don't break yet, prefer spaced version if found later
                         
            # If no whole word match, check substrings as fallback
            if best_match_type < 2:
                 for cmd in available_commands:
                      command_name_raw = cmd.split('.')[-1].lower()
                      command_name_spaced = command_name_raw.replace('_', ' ')
                      if command_name_spaced in user_input.lower() or command_name_raw in user_input.lower():
                           if best_match_type < 1:
                                matched_command = cmd
                                best_match_type = 1
                                # Keep first substring match

            if matched_command:
                intent = matched_command
                confidence = 0.9 if best_match_type == 2 else 0.7 
            else:
                intent = "unknown"
                confidence = 0.1
        else:
            intent = "unknown"
            confidence = 0.0

        logger.debug(f"Classified intent: {intent} with confidence {confidence}")
        return intent, confidence

    def clarify_intent(
        self, user_input: str, possible_intents: List[Tuple[str, float]]
    ) -> Optional[str]:
        """Default implementation: picks the highest confidence intent."""
        if not possible_intents:
            return None

        # Simple logic: pick highest confidence
        return sorted(possible_intents, key=lambda x: x[1], reverse=True)[0][0]
