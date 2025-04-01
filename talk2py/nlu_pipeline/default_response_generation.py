"""Default implementation of response generation interface.

This module provides a basic implementation of the ResponseGenerationInterface
for generating human-readable responses in talk2py.
"""

import talk2py
from talk2py.nlu_pipeline.nlu_engine_interfaces import ResponseGenerationInterface
from typing import Optional
from talk2py.code_parsing.command_registry import CommandRegistry


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

        # Get current context from CHAT_CONTEXT, prioritizing it if the command is a class method
        current_context = None
        is_class_method = action.command_key in registry.command_classes

        if is_class_method:
            current_context = talk2py.CHAT_CONTEXT.current_object
            if current_context is None:
                # Raise error immediately if class method needs context but none is set
                raise ValueError(
                    f"Command '{action.command_key}' requires context, but CHAT_CONTEXT.current_object is None."
                )
        elif talk2py.CHAT_CONTEXT.current_app_folderpath == action.app_folderpath:
            # For global functions, only use context if app paths match (optional)
            current_context = talk2py.CHAT_CONTEXT.current_object

        try:
            # Get the callable function/method (potentially a lambda with processed params)
            command_func = registry.get_command_func(
                action.command_key, current_context, action.parameters
            )
            if command_func is not None:
                # Execute the command function (which now handles its own parameters)
                result = command_func()
            else:
                # Command function not found by the registry
                raise ValueError(
                    f"Command function could not be resolved for key '{action.command_key}'"
                )
        except ValueError as e:
            # Catch specific ValueErrors from get_command_func (context, instantiation)
            # or from command_func() execution itself (less common).
            raise ValueError(
                f"Error executing command '{action.command_key}' with params "
                f"{action.parameters}. Error: {e}"
            ) from e
        except Exception as e:
            # Catch any other unexpected errors (e.g., TypeError from execution, ImportError, etc.)
            raise RuntimeError(
                f"Unexpected error executing command '{action.command_key}'. Error: {e}"
            ) from e

        # Convert the result to dict[str, str]
        if result is None:
            return {"status": "success"}
        elif isinstance(result, dict):
            return {str(k): str(v) for k, v in result.items()}
        else:
            return {"result": str(result)}

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
