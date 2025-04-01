"""Default implementation of response generation interface.

This module provides a basic implementation of the ResponseGenerationInterface
for generating human-readable responses in talk2py.
"""

import talk2py
from talk2py.nlu_pipeline.nlu_engine_interfaces import ResponseGenerationInterface
from typing import Optional
from talk2py.code_parsing_execution.command_registry import CommandRegistry


# pylint: disable=too-few-public-methods
class DefaultResponseGeneration(ResponseGenerationInterface):
    """Default implementation of response generation functionality."""

    command_registry: Optional[CommandRegistry] = None

    def __init__(self, command_registry: Optional[CommandRegistry] = None):
        """Initialize the DefaultResponseGeneration instance."""
        super().__init__()
        self.command_registry = command_registry

    def execute_code(self, action: talk2py.Action) -> dict[str, str]:
        """Execute the command specified by the action.

        Args:
            action: The Action object containing the command key and parameters.

        Returns:
            The result of executing the command.

        Raises:
            ValueError: If no command implementation is found for the command key.
        """
        # Use the provided registry or get one based on the action's app_folderpath
        registry = self.command_registry or talk2py.get_registry(action.app_folderpath)

        # Get current context from CHAT_CONTEXT
        current_context = None
        if talk2py.CHAT_CONTEXT.current_app_folderpath == action.app_folderpath:
            current_context = talk2py.CHAT_CONTEXT.current_object

        # Assign first, then check if None
        command_func = registry.get_command_func(
            action.command_key, current_context, action.parameters
        )
        if command_func is not None:
            result = command_func(**action.parameters)
            # Convert the result to dict[str, str]
            if result is None:
                parsed_result = {"status": "success"}
            elif isinstance(result, dict):
                parsed_result = {str(k): str(v) for k, v in result.items()}
            else:
                parsed_result = {"result": str(result)}
            return parsed_result
        else:  # Explicitly handle the None case
            raise ValueError(
                f"Command implementation function not found for command_key '{action.command_key}'"
            )

    def get_supplementary_prompt_instructions(self, command_key: str) -> str:
        """Return supplementary prompt instructions for aiding response text generation.

        Args:
            command_key: The key identifying the command.

        Returns:
            str: Supplementary instructions for response generation.
        """
        return ""

    def generate_response_text(
        self,
        command: str,
        execution_results: dict[str, str],
    ) -> str:
        """Default implementation: generates a basic success/error message."""
        status = execution_results.get("status")
        message = execution_results.get("message", "")

        if status == "success":
            return f"Command '{command}' executed successfully. {message}"
        return f"Command '{command}' failed. " f"Error: {message or 'Unknown error'}"
