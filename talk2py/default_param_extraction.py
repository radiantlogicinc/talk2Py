"""Default implementation of parameter extraction interface.

This module provides a basic implementation of the ParameterExtractionInterface
for extracting and validating command parameters in talk2py.
"""

from typing import Optional, Tuple

from pydantic import BaseModel

from talk2py.nlu_engine_interfaces import ParameterExtractionInterface


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
        self, cmd_parameters: BaseModel
    ) -> Tuple[bool, Optional[str]]:
        """Validate the command parameters.

        Args:
            cmd_parameters: The parameters to validate as a Pydantic model.

        Returns:
            A tuple containing:
                - bool: True if parameters are valid, False otherwise
                - Optional[str]: Error message if validation fails, None if successful

        Raises:
            NotImplementedError: This is a placeholder implementation.
        """
        return (True, "")
