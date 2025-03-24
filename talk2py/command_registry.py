"""Command registry module for talk2py.

This module provides the CommandRegistry class which manages command metadata
and function loading for the talk2py framework.
"""

import importlib.util
import json
import os
import sys
from types import MethodType
from typing import Any, Callable, Dict, Optional, Type


class CommandRegistry:
    """Registry for managing command metadata and function loading.

    This class is responsible for loading command metadata from JSON files,
    dynamically importing command modules, and providing access to command
    functions.
    """

    def __init__(self, command_metadata_path: Optional[str] = None):
        """Initialize the CommandRegistry.

        Args:
            command_metadata_path: Optional path to a JSON file containing
                                command metadata.
        """
        self.command_metadata: Dict[str, Any] = {}
        self.command_funcs: Dict[str, Callable[..., Any]] = {}
        self.command_classes: Dict[str, Type[Any]] = {}
        self.metadata_dir: Optional[str] = None

        if command_metadata_path:
            self.load_command_metadata(command_metadata_path)

    def load_command_metadata(self, metadata_path: str) -> None:
        """Load command metadata from a JSON file.

        Args:
            metadata_path: Path to the JSON file containing command metadata.

        Raises:
            FileNotFoundError: If the metadata file does not exist.
        """
        if not os.path.exists(metadata_path):
            raise FileNotFoundError(f"Command metadata file not found: {metadata_path}")

        self.metadata_dir = os.path.dirname(os.path.abspath(metadata_path))

        with open(metadata_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.command_metadata = data

        # Pre-load all command functions
        for command_key, metadata in self.command_metadata.get(
            "map_commandkey_2_metadata", {}
        ).items():
            self._load_command_func(command_key, metadata)

    def _load_command_func(self, command_key: str, _: Dict[str, Any]) -> None:
        """Load a command function from its module path.

        Args:
            command_key: The command key in format 'path.to.module.Class.function'
                      or 'path.to.module.function'
            _: The command metadata (unused)

        Example command_keys:
            - calculator.add  # Global function
            - calculator.Calculator.multiply  # Class method

        Raises:
            ImportError: If the module cannot be loaded
            AttributeError: If the function or class is not found
        """
        app_folderpath = self.command_metadata.get("app_folderpath", "")

        # Split command key into parts
        parts = command_key.split(".")

        # Check if it's a class method (has at least 3 parts and second-to-last is capitalized)
        if len(parts) >= 3 and parts[-2][0].isupper():
            # For class methods: module_path = parts[:-2], class_name = parts[-2]
            module_parts = parts[:-2]
            class_name = parts[-2]
        else:
            # For global functions: module_path = parts[:-1]
            module_parts = parts[:-1]
            class_name = None
        func_name = parts[-1]

        # Construct module file path and module name
        module_file = os.path.normpath(
            f"{os.path.join(app_folderpath, *module_parts)}.py"
        )
        module_name = ".".join(module_parts)  # e.g., 'calculator' or 'subdir.module'

        try:
            # Import the module
            spec = importlib.util.spec_from_file_location(module_name, module_file)
            if not spec or not spec.loader:
                raise ImportError(f"Could not load module: {module_file}")

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module  # Register the module in sys.modules
            spec.loader.exec_module(module)
        except FileNotFoundError as e:
            raise ImportError(f"Module file not found: {module_file}") from e

        # Get the function
        if class_name:
            # Get class then function for class methods
            if not hasattr(module, class_name):
                raise AttributeError(
                    f"Class {class_name} not found in module {module_file}"
                )
            class_obj = getattr(module, class_name)
            if not hasattr(class_obj, func_name):
                raise AttributeError(
                    f"Method {func_name} not found in class {class_name}"
                )
            self.command_funcs[command_key] = getattr(class_obj, func_name)
            self.command_classes[command_key] = class_obj
        elif hasattr(module, func_name):
            self.command_funcs[command_key] = getattr(module, func_name)
        else:
            raise AttributeError(
                f"Function {func_name} not found in module {module_file}"
            )

    def get_command_func(
        self, command_key: str, obj: Optional[Any] = None
    ) -> Optional[Callable[..., Any]]:
        """Get the command function for a given command key.

        Args:
            command_key: The key identifying the command function
            obj: Optional instance to bind the method to if it's a class method

        Returns:
            The command function if found, None otherwise

        Raises:
            TypeError: If obj is provided but is not an instance of the expected class
        """
        func = self.command_funcs.get(command_key)
        if func is not None and obj is not None:
            # Check if the object is an instance of the expected class
            expected_class = self.command_classes.get(command_key)
            if expected_class:
                # Compare by module name and class name instead of direct class comparison
                obj_type = type(obj)
                if (obj_type.__module__, obj_type.__name__) != (
                    expected_class.__module__,
                    expected_class.__name__,
                ):
                    raise TypeError(
                        f"Object must be an instance of {expected_class.__name__}"
                    )
            # Use Python's method binding
            return MethodType(func, obj)
        return func


def how_to_use():
    """Example usage of the CommandRegistry class."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    examples_dir = os.path.join(os.path.dirname(current_dir), "examples")
    metadata_path = os.path.join(
        examples_dir, "calculator", "___command_info", "command_metadata.json"
    )

    registry = CommandRegistry(metadata_path)
    if add_func := registry.get_command_func("calculator.add"):
        result = add_func(a=5, b=3)
        print(f"5 + 3 = {result}")


if __name__ == "__main__":
    how_to_use()
