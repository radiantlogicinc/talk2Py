"""Command executor module for talk2py.

This module provides the CommandExecutor class which is responsible for
executing commands based on the provided action and command registry.
"""

from typing import Any, Optional

import talk2py
from talk2py import CHAT_CONTEXT
from talk2py.command_registry import CommandRegistry

# from fastworkflow.command_interfaces import CommandExecutorInterface
# from fastworkflow.command_routing_definition import ModuleType as CommandModuleType


# pylint: disable=too-few-public-methods
class CommandExecutor:
    """Executes commands based on the provided action and command registry.

    This class is responsible for executing commands by looking up the
    appropriate command function in the command registry and calling it
    with the provided parameters.
    """

    def __init__(self, command_registry: Optional[CommandRegistry] = None):
        """Initialize the CommandExecutor.

        Args:
            command_registry: Optional CommandRegistry instance. If not provided,
                            a registry will be obtained from the action's app_folderpath.
        """
        self.command_registry = command_registry

    def perform_action(self, action: talk2py.Action) -> Any:
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
        if CHAT_CONTEXT.current_app_folderpath == action.app_folderpath:
            current_context = CHAT_CONTEXT.current_object

        command_func = registry.get_command_func(
            action.command_key, current_context, action.parameters
        )
        if command_func is not None:
            return command_func(**action.parameters)

        raise ValueError(
            f"Command implementation function not found for command_key '{action.command_key}'"
        )
