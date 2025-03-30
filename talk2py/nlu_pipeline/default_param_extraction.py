"""Default implementation of parameter extraction interface.

This module provides a basic implementation of the ParameterExtractionInterface
for extracting and validating command parameters in talk2py.
"""

from typing import Optional, Dict, Any

from pydantic import BaseModel

from talk2py.nlu_pipeline.nlu_engine_interfaces import ParameterExtractionInterface


class DefaultParameterExtraction(ParameterExtractionInterface):
    """Default implementation of parameter extraction functionality."""

    def get_supplementary_prompt_instructions(self, command_key: str) -> str:
        """Return supplementary prompt instructions for aiding parameter extraction.

        Args:
            command_key: The key identifying the command.

        Returns:
            str: Supplementary instructions for parameter extraction.

        Raises:
            NotImplementedError: This is a placeholder implementation.
        """
        return ""

    def validate_parameters(
        self, intent: str, parameters: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """Validate the command parameters.

        Args:
            intent: The classified intent string.
            parameters: The currently identified parameters.

        Returns:
            A tuple containing:
                - bool: True if parameters are valid, False otherwise
                - Optional[str]: Error message if validation fails, None if successful

        Raises:
            NotImplementedError: This is a placeholder implementation.
        """
        return (True, "")

    def identify_parameters(
        self, user_input: str, intent: str
    ) -> Dict[str, Any]:
        """Default implementation: returns empty parameters."""
        return {}
