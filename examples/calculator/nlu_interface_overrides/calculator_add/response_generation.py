"""Default implementation of response generation interface.

This module provides a basic implementation of the ResponseGenerationInterface
for generating human-readable responses based on command execution in talk2py.
"""

import dspy  # type: ignore

import talk2py

# Import the actual default class
from talk2py.nlu_pipeline.default_response_generation import (
    DefaultResponseGeneration as BaseDefaultResponseGeneration,
)


# pylint: disable=too-few-public-methods
# Inherit from the actual default class, aliased as BaseDefaultResponseGeneration
class DefaultResponseGeneration(BaseDefaultResponseGeneration):
    """Override for response generation for the calculator add command."""

    # No need to redefine execute_code if inheriting the base version
    # If execute_code needs specific overrides, define it here and potentially call super().execute_code()

    # Keep the overridden methods specific to this calculator command
    def get_supplementary_prompt_instructions(self, command_key: str) -> str:
        """Return supplementary prompt instructions for aiding response text generation.

        Args:
            command_key: The key identifying the command.

        Returns:
            str: Supplementary instructions for parameter extraction.
        """
        if "calculator.calc.add_numbers" in command_key:
            return "Emphasize the addition result in your response."
        return ""

    def generate_response_text(
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
