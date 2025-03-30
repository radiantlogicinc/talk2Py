"""Default implementation of response generation interface.

This module provides a basic implementation of the ResponseGenerationInterface
for generating human-readable responses based on command execution in talk2py.
"""

import dspy  # type: ignore

import talk2py
from talk2py.nlu_pipeline.nlu_engine_interfaces import ResponseGenerationInterface


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
