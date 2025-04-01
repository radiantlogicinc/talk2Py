"""Command registry module for talk2py.

This module provides the CommandRegistry class which manages command metadata
and function loading for the talk2py framework.
"""

import importlib.util
import json
import os
import sys
from types import MethodType
from typing import Any, Callable, Optional, Type, cast


class CommandRegistry:  # pylint: disable=too-many-instance-attributes
    """Registry for managing command metadata and function loading.

    This class is responsible for loading command metadata from JSON files,
    dynamically importing command modules, and providing access to command
    functions.
    """

    def __init__(
        self,
        app_folderpath: Optional[str] = None,
        command_metadata_path: Optional[str] = None,
    ):
        """Initialize the CommandRegistry.

        Args:
            app_folderpath: Optional path to the application folder. If provided,
                            metadata path will be derived automatically using get_metadata_path.
            command_metadata_path: Optional path to a JSON file containing
                                command metadata. Deprecated, use app_folderpath instead.
        """
        self.command_metadata: dict[str, Any] = {}
        self.command_funcs: dict[str, Callable[..., Any]] = {}
        self.command_classes: dict[str, Type[Any]] = {}
        self.metadata_dir: Optional[str] = None
        # Store property setters in a separate dict for special handling
        self.property_setters: dict[str, Callable[..., Any]] = {}
        # Track which keys are property getters
        self.property_getters: dict[str, bool] = {}

        if app_folderpath:
            metadata_path = self.get_metadata_path(app_folderpath)
            self.load_command_metadata(metadata_path)
        elif command_metadata_path:
            self.load_command_metadata(command_metadata_path)

    @staticmethod
    def get_metadata_path(app_folderpath: str) -> str:
        """Get the path to the command metadata file for an application.

        Args:
            app_folderpath: Path to the application folder

        Returns:
            Path to the command metadata file

        Raises:
            FileNotFoundError: If the metadata file or directory does not exist
        """
        metadata_dir = os.path.join(app_folderpath, "___command_info")
        metadata_path = os.path.join(metadata_dir, "command_metadata.json")

        if not os.path.exists(metadata_path):
            raise FileNotFoundError(f"Command metadata file not found: {metadata_path}")

        return metadata_path

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

    def _load_command_func(self, command_key: str, metadata: dict[str, Any]) -> None:
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
        # Parse command key into components
        module_parts, class_name, func_name = self._parse_command_key(command_key)

        # Import the module
        module = self._import_module(module_parts)

        # Register command based on whether it's a class method or module function
        if class_name:
            self._register_class_method(
                command_key, module, class_name, func_name, metadata
            )
        else:
            self._register_module_function(command_key, module, func_name, metadata)

    def _parse_command_key(
        self, command_key: str
    ) -> tuple[list[str], Optional[str], str]:
        """Parse a command key into its components.

        Args:
            command_key: The command key to parse

        Returns:
            tuple containing:
            - module_parts: list of module path components
            - class_name: Optional class name (None for global functions)
            - func_name: Function name
        """
        parts = command_key.split(".")

        # Check if it's a class method (has at least 3 parts and second-to-last is capitalized)
        if len(parts) >= 3 and parts[-2][0].isupper():
            module_parts = parts[:-2]
            class_name = parts[-2]
        else:
            module_parts = parts[:-1]
            class_name = None

        func_name = parts[-1]
        return module_parts, class_name, func_name

    def _import_module(self, module_parts: list[str]) -> Any:
        """Import a module from its parts.

        Args:
            module_parts: list of module path components

        Returns:
            The imported module

        Raises:
            ImportError: If the module cannot be loaded
        """
        app_folderpath = self.command_metadata.get("app_folderpath", "")

        # Construct module file path and module name
        module_file = os.path.normpath(
            f"{os.path.join(app_folderpath, *module_parts)}.py"
        )
        module_name = ".".join(module_parts)

        try:
            return self.get_module(module_name, module_file)
        except FileNotFoundError as e:
            raise ImportError(f"Module file not found: {module_file}") from e

    def get_module(self, module_name, module_file):
        """Import a module by name and file path.

        Args:
            module_name: The name of the module to import
            module_file: The file path of the module

        Returns:
            The imported module

        Raises:
            ImportError: If the module cannot be loaded
        """
        if module_name in sys.modules:
            return sys.modules[module_name]

        # Import the module
        spec = importlib.util.spec_from_file_location(module_name, module_file)
        if not spec or not spec.loader:
            raise ImportError(f"Could not load module: {module_file}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module  # Register the module in sys.modules
        spec.loader.exec_module(module)
        return module

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def _register_class_method(
        self,
        command_key: str,
        module: Any,
        class_name: str,
        func_name: str,
        metadata: dict[str, Any],
    ) -> None:
        """Register a class method as a command.

        Args:
            command_key: The command key
            module: The imported module
            class_name: Name of the class
            func_name: Name of the function/method
            metadata: Command metadata

        Raises:
            AttributeError: If the class or method is not found
        """
        module_file = module.__file__ if hasattr(module, "__file__") else "unknown"

        # Validate class exists
        if not hasattr(module, class_name):
            raise AttributeError(
                f"Class {class_name} not found in module {module_file}"
            )

        # Get class and validate method exists
        class_obj = getattr(module, class_name)

        # Check if the method exists in the class or any of its parent classes
        method_found = False

        # First check directly in the class
        if hasattr(class_obj, func_name):
            method_found = True
            attr = getattr(class_obj, func_name)
            self._register_attribute(command_key, attr, metadata)
        else:
            # If not found directly, the method might be inherited from a parent class
            # but already included in the command metadata through the parsing process
            # We'll assume it's valid since it was found during parsing
            for base in getattr(class_obj, "__bases__", ()):
                if hasattr(base, func_name):
                    method_found = True
                    attr = getattr(base, func_name)
                    self._register_attribute(command_key, attr, metadata)
                    break

        if not method_found:
            raise AttributeError(
                f"Method {func_name} not found in class {class_name} or its parent classes"
            )

        # Store class for later use
        self.command_classes[command_key] = class_obj

    def _register_module_function(
        self, command_key: str, module: Any, func_name: str, metadata: dict[str, Any]
    ) -> None:
        """Register a module function as a command.

        Args:
            command_key: The command key
            module: The imported module
            func_name: Name of the function
            metadata: Command metadata

        Raises:
            AttributeError: If the function is not found
        """
        module_file = module.__file__ if hasattr(module, "__file__") else "unknown"

        # Validate function exists
        if not hasattr(module, func_name):
            raise AttributeError(
                f"Function {func_name} not found in module {module_file}"
            )

        # Get attribute and register it
        attr = getattr(module, func_name)
        self._register_attribute(command_key, attr, metadata)

    def _register_attribute(
        self, command_key: str, attr: Any, metadata: dict[str, Any]
    ) -> None:
        """Register an attribute (function or property) as a command.

        Args:
            command_key: The command key
            attr: The attribute to register
            metadata: Command metadata
        """
        if isinstance(attr, property):
            self._register_property(command_key, attr, metadata)
        else:
            self.command_funcs[command_key] = attr
            self.property_getters[command_key] = False

    def _register_property(
        self, command_key: str, prop: property, metadata: dict[str, Any]
    ) -> None:
        """Register a property as a command.

        Args:
            command_key: The command key
            prop: The property to register
            metadata: Command metadata
        """
        # Register getter
        self.command_funcs[command_key] = cast(Callable[..., Any], prop.fget)
        self.property_getters[command_key] = True

        # Check if this property has a setter and the metadata specifies a value parameter
        has_value_param = any(
            param.get("name") == "value" for param in metadata.get("parameters", [])
        )

        # Register setter if available and expected
        if prop.fset is not None and has_value_param:
            self.property_setters[command_key] = cast(Callable[..., Any], prop.fset)

    def get_command_func(
        self,
        command_key: str,
        obj: Optional[Any] = None,
        params: Optional[dict[str, Any]] = None,
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
    ) -> list[str]:
        """Get command keys available in the current context.

        Args:
            current_context: Optional object representing the current context.
                           If None, returns global command functions.
                           If provided, returns class methods for the object's class
                           and its parent classes.

        Returns:
            list of command keys available in the current context.
        """
        if current_context is None:
            # Return global functions (those not in command_classes)
            return sorted(
                [key for key in self.command_funcs if key not in self.command_classes]
            )

        # Get the class of the current context and its full class hierarchy
        context_class = type(current_context)
        context_class_names = []

        # Add the current class and all its parent classes to the list
        for cls in context_class.__mro__:
            # Skip 'object' class which is the ultimate parent
            if cls.__name__ != "object":
                context_class_names.append(cls.__name__)

        # Get all command keys that belong to any class in the inheritance hierarchy
        context_commands = []
        for key, class_type in self.command_classes.items():
            if class_type.__name__ in context_class_names:
                # Extract method name from command key (last part after the dot)
                method_name = key.split(".")[-1]
                # Check if the method is accessible from the current class
                if hasattr(context_class, method_name):
                    context_commands.append(key)

        return sorted(context_commands)
