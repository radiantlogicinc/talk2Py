"""Default implementation of UtterancesInterface.

This module provides a default implementation of the UtterancesInterface
that generates function signatures and docstrings for commands.
"""

import os

from talk2py import get_registry
from talk2py.command_registry import CommandRegistry


class DefaultUtterancesImpl:  # pylint: disable=too-few-public-methods
    """Default implementation of UtterancesInterface.

    This class generates function signatures and docstrings for commands
    by looking up command metadata in the command registry.
    """

    def __init__(self, command_registry: CommandRegistry):
        """Initialize DefaultUtterancesImpl.

        Args:
            command_registry: The command registry containing command metadata
        """
        self.command_registry = command_registry

    def get_utterance_metadata(self, command_key: str) -> tuple[str, str]:
        """Generate function signature and docstring for a command.

        Args:
            command_key: The key identifying the command

        Returns:
            A tuple containing the function signature and docstring

        Raises:
            ValueError: If command_key does not exist in the registry
        """
        # Get the command metadata
        if not self.command_registry.command_metadata:
            raise ValueError("Command registry is empty")

        # Access the command metadata from the registry
        command_metadata = self.command_registry.command_metadata.get(
            "map_commandkey_2_metadata", {}
        ).get(command_key)

        if not command_metadata:
            raise ValueError(f"Command '{command_key}' does not exist in registry")

        # Extract docstring
        docstring = command_metadata.get("docstring", "")

        # Generate function signature
        # Start with function name (last part of command_key)
        func_name = command_key.split(".")[-1]

        # Add parameters
        params = command_metadata.get("parameters", [])
        params_str = ", ".join(
            [f"{p.get('name')}: {p.get('type', 'Any')}" for p in params]
        )

        # Add return type
        return_type = command_metadata.get("return_type", "None")

        # Construct the full signature
        function_signature = f"def {func_name}({params_str}) -> {return_type}"

        return function_signature, docstring


def how_to_use():
    """Example usage of the DefaultUtterancesImpl class."""
    # Get command registry
    current_dir = os.path.dirname(os.path.abspath(__file__))
    examples_dir = os.path.join(os.path.dirname(current_dir), "examples")
    app_folder_path = os.path.join(examples_dir, "calculator")

    # Get the registry using the cached version
    registry = get_registry(app_folder_path)

    # Create utterance generator
    utterance_gen = DefaultUtterancesImpl(registry)

    # Generate utterances for a command
    command_key = "calculator.add"
    signature, docstring = utterance_gen.get_utterance_metadata(command_key)

    print(f"Function Signature: {signature}")
    print(f"Docstring: {docstring}")


if __name__ == "__main__":
    how_to_use()
