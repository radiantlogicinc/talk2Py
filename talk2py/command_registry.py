"""Command registry module for talk2py.

This module provides the CommandRegistry class which manages command metadata
and function loading for the talk2py framework.
"""

import importlib.util
import json
import os
import sys
from types import MethodType
from typing import Any, Callable, Dict, List, Optional, Type, cast


class CommandRegistry:  # pylint: disable=too-many-instance-attributes
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
        # Store property setters in a separate dict for special handling
        self.property_setters: Dict[str, Callable[..., Any]] = {}
        # Track which keys are property getters
        self.property_getters: Dict[str, bool] = {}

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

    def _load_command_func(  # pylint: disable=too-many-branches
        self, command_key: str, metadata: Dict[str, Any]
    ) -> None:
        """Load a command function from its module path.

        Args:
            command_key: The command key in format 'path.to.module.Class.function'
                      or 'path.to.module.function'
            metadata: The command metadata

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
        module_name = ".".join(module_parts)

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
            attr = getattr(class_obj, func_name)
            # Handle property objects by getting the underlying getter/setter function
            if isinstance(attr, property):
                self.command_funcs[command_key] = cast(Callable[..., Any], attr.fget)
                self.property_getters[command_key] = True
                # Check if this is a property with a setter
                if attr.fset is not None and any(
                    param.get("name") == "value"
                    for param in metadata.get("parameters", [])
                ):
                    self.property_setters[command_key] = cast(
                        Callable[..., Any], attr.fset
                    )
            else:
                self.command_funcs[command_key] = attr
                self.property_getters[command_key] = False
            self.command_classes[command_key] = class_obj
        elif hasattr(module, func_name):
            attr = getattr(module, func_name)
            # Handle property objects by getting the underlying getter function
            if isinstance(attr, property):
                self.command_funcs[command_key] = cast(Callable[..., Any], attr.fget)
                self.property_getters[command_key] = True
                # Check if this is a property with a setter
                if attr.fset is not None and any(
                    param.get("name") == "value"
                    for param in metadata.get("parameters", [])
                ):
                    self.property_setters[command_key] = cast(
                        Callable[..., Any], attr.fset
                    )
            else:
                self.command_funcs[command_key] = attr
                self.property_getters[command_key] = False
        else:
            raise AttributeError(
                f"Function {func_name} not found in module {module_file}"
            )

    def get_command_func(
        self,
        command_key: str,
        obj: Optional[Any] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Callable[..., Any]:
        """Get the command function for a given command key.

        Args:
            command_key: The key identifying the command function
            obj: Optional instance to bind the method to if it's a class method
            params: Optional parameters to determine if this is a setter call

        Returns:
            The command function

        Raises:
            TypeError: If obj is provided but is not an instance of the expected class
            ValueError: If command_key does not exist or is not in commands exposed by obj
        """
        if command_key not in self.command_funcs:
            raise ValueError(f"Command '{command_key}' does not exist")

        # Check if command is a class method
        is_class_method = command_key in self.command_classes

        # Check if command is a property
        is_property = self.property_getters.get(command_key, False)

        # Check if command has a property setter
        has_setter = command_key in self.property_setters

        # Check if this is a setter call based on parameters
        is_setter_call = has_setter and params and "value" in params

        # If it's a class method, we need an object
        if is_class_method:
            if obj is None:
                raise ValueError(
                    f"Command '{command_key}' is not available in the current context"
                )

            expected_class = self.command_classes[command_key]
            obj_type = type(obj)

            # Check if object is of expected type
            if obj_type.__name__ != expected_class.__name__:
                raise TypeError(
                    f"Object must be an instance of {expected_class.__name__}"
                )

            # Handle property setter specially
            if is_setter_call:
                setter = self.property_setters[command_key]

                # Ensure the setter is properly typed for mypy
                def setter_wrapper(value: Any) -> Any:
                    assert setter is not None
                    return setter(obj, value)

                return setter_wrapper

            if is_property:
                # For property getters, bind the function and create a no-argument wrapper
                getter = self.command_funcs[command_key]

                # Ensure the getter is properly typed for mypy
                def getter_wrapper() -> Any:
                    assert getter is not None
                    return getter(obj)

                return getter_wrapper

            # For regular methods, use method binding
            return MethodType(self.command_funcs[command_key], obj)

        # For global functions, object should be None
        if obj is not None:
            raise ValueError(
                f"Command '{command_key}' is not available in the current context"
            )
        return self.command_funcs[command_key]

    def get_commands_in_current_context(
        self, current_context: Optional[Any] = None
    ) -> List[str]:
        """Get command keys available in the current context.

        Args:
            current_context: Optional object representing the current context.
                           If None, returns global command functions.
                           If provided, returns class methods for the object's class.

        Returns:
            List of command keys available in the current context.
        """
        if current_context is None:
            # Return global functions (those not in command_classes)
            return sorted(
                [key for key in self.command_funcs if key not in self.command_classes]
            )

        # Get the class of the current context
        context_class_name = type(current_context).__name__

        # Get all command keys that belong to this class
        context_commands = [
            key
            for key, class_type in self.command_classes.items()
            if class_type.__name__ == context_class_name
        ]

        return sorted(context_commands)


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
