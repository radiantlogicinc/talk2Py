"""Command registry module for talk2py.

This module provides the CommandRegistry class which manages command metadata
and function loading for the talk2py framework.
"""

import importlib.util
import inspect
import json
import logging
import os
import sys
from typing import Any, Callable, Optional, Type, cast

# Basic types that don't need special instantiation
BASIC_TYPES = {"str", "int", "float", "bool", "list", "dict", "any", "optional", "null"}


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
            Absolute path to the command metadata file

        Raises:
            FileNotFoundError: If the metadata file or directory does not exist
        """
        # Ensure app_folderpath is absolute for consistent behavior
        absolute_app_folderpath = os.path.abspath(app_folderpath)
        metadata_dir = os.path.join(absolute_app_folderpath, "___command_info")
        metadata_path = os.path.join(metadata_dir, "command_metadata.json")

        if not os.path.exists(metadata_path):
            # Try finding relative to current script if not found via absolute path
            # This can help in scenarios where app_folderpath is relative to script location
            script_dir = os.path.dirname(os.path.abspath(__file__))
            relative_metadata_dir = os.path.join(
                script_dir, app_folderpath, "___command_info"
            )
            relative_metadata_path = os.path.join(
                relative_metadata_dir, "command_metadata.json"
            )
            if os.path.exists(relative_metadata_path):
                metadata_path = relative_metadata_path
            else:
                raise FileNotFoundError(
                    f"Command metadata file not found in {metadata_dir} or {relative_metadata_dir}"
                )

        return os.path.abspath(metadata_path)  # Always return absolute path

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
        # Ensure metadata_dir is set (should happen during load_command_metadata)
        if not self.metadata_dir:
            raise RuntimeError(
                "CommandRegistry.metadata_dir is not set. Load metadata first."
            )

        # metadata_dir is the absolute path to the ___command_info directory
        # app_folderpath_in_metadata is relative *from* the application root (parent of ___command_info)
        # to where the modules reside.
        app_folderpath_in_metadata = self.command_metadata.get("app_folderpath", ".")

        # Calculate the application root directory (parent of metadata_dir)
        app_root_dir = os.path.dirname(self.metadata_dir)

        # Construct the absolute path to the base directory for modules
        # This joins the app root with the relative path specified in metadata
        module_base_dir = os.path.abspath(
            os.path.join(app_root_dir, app_folderpath_in_metadata)
        )

        # Construct the absolute path to the specific module file
        module_file_path_parts = [module_base_dir] + module_parts
        absolute_module_path = os.path.join(*module_file_path_parts)
        module_file = f"{absolute_module_path}.py"

        # Module name remains the same relative structure
        module_name = ".".join(module_parts)

        # Debugging log
        # logging.debug(f"Attempting to import module: name={module_name}, "
        #               f"file={module_file}, app_root={app_root_dir}, "
        #               f"module_base={module_base_dir}")

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
        self, command_key: str, current_context: Any, parameters: dict[str, Any]
    ) -> Optional[Callable[..., Any]]:
        """Get the command function or method, handling class instantiation.

        Args:
            command_key: The command key (e.g., 'module.func' or 'module.Class.method')
            current_context: The current object context (for class methods)
            parameters: The parameters provided for the command call

        Returns:
            Callable function or bound method, or None if not found.
        """
        func = self.command_funcs.get(command_key)
        setter = self.property_setters.get(command_key)
        is_getter = (
            command_key in self.property_getters and self.property_getters[command_key]
        )  # Explicit check for True flag

        # Determine intended operation: getter, setter, or regular function/method
        intended_operation = "unknown"

        if is_getter and setter:  # Property with both getter and setter
            if len(parameters) == 0:
                intended_operation = "getter"
            elif len(parameters) == 1:
                intended_operation = "setter"
            else:
                raise ValueError(
                    f"Invalid parameters for property '{command_key}'. Provide 0 parameters to get, or 1 to set."
                )
        elif (
            is_getter
        ):  # Getter-only property (or property where setter wasn't registered/detected)
            if len(parameters) == 0:
                intended_operation = "getter"
            else:
                # If a func exists but is_getter is True, it means it was registered via _register_property.
                # Such funcs (property getters) MUST take 0 args.
                raise ValueError(
                    f"Invalid parameters for property getter '{command_key}'. Getters take 0 parameters."
                )
        elif (
            setter
        ):  # Setter-only property (less common, but possible if getter fails registration)
            if len(parameters) == 1:
                intended_operation = "setter"
            else:
                raise ValueError(
                    f"Invalid parameters for property setter '{command_key}'. Setters take exactly 1 parameter."
                )
        elif func:  # Must be a regular method/function (not a getter or setter)
            # No parameter count check here; rely on _process_parameters and the actual call
            intended_operation = "method/function"
        else:  # Neither func nor setter found
            return None  # Command not found

        # --- Handle Setter ---
        if intended_operation == "setter":
            if current_context is None:
                raise ValueError(
                    "Cannot call property setter without an object context."
                )

            # Process the single parameter
            processed_params = self._process_parameters(command_key, parameters)
            if len(processed_params) != 1:
                raise ValueError(
                    "Internal error: Parameter processing for setter yielded unexpected number of parameters."
                )
            value = next(iter(processed_params.values()))

            # Bind and return lambda for setter
            assert setter is not None  # Explicit check for mypy
            bound_setter = setter.__get__(current_context, type(current_context))
            return lambda: bound_setter(value)

        # --- Handle Getter or Regular Method/Function ---
        elif intended_operation in ["getter", "method/function"]:
            if (
                not func
            ):  # Safety check: should always have a func if getter or method/function
                # This indicates an internal logic error if reached
                raise ValueError(
                    f"Internal error: Command function could not be resolved "
                    f"for key '{command_key}' despite intended operation "
                    f"being '{intended_operation}'"
                )
            assert func is not None  # Added assertion for mypy

            # Process parameters (will be empty for getters)
            processed_params = self._process_parameters(command_key, parameters)

            if command_key in self.command_classes:
                # Needs binding (Class method, property getter)
                if current_context is None:
                    raise ValueError(f"Command '{command_key}' requires context.")

                # Context type validation
                expected_class = self.command_classes[command_key]
                actual_class = type(current_context)

                # --- MODIFIED CHECK with Fallback ---
                # 1. Try matching class name and module name
                is_compatible = (
                    actual_class.__name__ == expected_class.__name__
                    and getattr(actual_class, "__module__", None)
                    == getattr(expected_class, "__module__", None)
                )

                # 2. If module names differ, fallback to comparing only class names
                #    This is less strict but handles cases of differing import paths for the same class.
                if (
                    not is_compatible
                    and actual_class.__name__ == expected_class.__name__
                ):
                    logging.warning(
                        f"Context class '{actual_class.__name__}' matched expected class name but not module "
                        f"('{getattr(actual_class, '__module__', 'N/A')}' vs '{getattr(expected_class, '__module__', 'N/A')}'). "
                        f"Proceeding with caution for command '{command_key}'."
                    )
                    is_compatible = True  # Allow proceeding if class names match

                if not is_compatible:
                    # --- END MODIFIED CHECK with Fallback ---
                    # Original error raising logic if neither check passes
                    raise TypeError(
                        f"Context object type '{actual_class.__name__}' "
                        f"(module: {getattr(actual_class, '__module__', 'N/A')}) "
                        f"is not compatible with expected class '{expected_class.__name__}' "
                        f"(module: {getattr(expected_class, '__module__', 'N/A')}) "
                        f"for command '{command_key}'."
                    )

                # Bind and return lambda
                bound_method = func.__get__(current_context, type(current_context))
                return lambda: bound_method(**processed_params)
            else:
                # Global function
                return lambda: func(**processed_params)

        # --- Command Not Found or Ambiguous ---
        # All valid cases should be handled above. If intended_operation is still "unknown",
        # it implies a logic error or an edge case not covered.
        # The initial check `if not func and not setter` returning None should handle 'not found'.
        # Property parameter errors are raised explicitly above.
        # If we reach here, it's likely an internal error.
        if intended_operation == "unknown":
            # This path should ideally not be reached if logic above is sound.
            # Consider logging a warning or raising an internal error.
            # For now, let's be safe and indicate the command couldn't be resolved.
            logging.warning(
                f"Command resolution failed unexpectedly for key '{command_key}' "
                f"with params {parameters}. Flags: is_getter={is_getter}, "
                f"setter_exists={setter is not None}, func_exists={func is not None}"
            )
            return None

        # Fallback return (should not be reached)
        return None

    def _process_parameters(
        self, command_key: str, parameters: dict[str, Any]
    ) -> dict[str, Any]:
        """Process parameters, instantiating class types if necessary."""
        metadata = self.command_metadata.get("map_commandkey_2_metadata", {}).get(
            command_key
        )
        if not metadata or "parameters" not in metadata:
            # No metadata or parameters defined, return original params
            return parameters

        processed_params = parameters.copy()
        param_metadata_map = {p["name"]: p for p in metadata["parameters"]}

        for param_name, param_value in parameters.items():
            param_meta = param_metadata_map.get(param_name)
            if not param_meta:
                continue  # Parameter not defined in metadata, skip processing

            param_type_str = param_meta.get("type", "any")

            # Check if it's a potential class type and the value is a dict
            if param_type_str not in BASIC_TYPES and isinstance(param_value, dict):
                try:
                    # Attempt to import the class and instantiate it
                    module_parts, class_name_in_key, _ = self._parse_command_key(
                        command_key
                    )
                    # The actual class name comes from the type annotation string
                    class_name = param_type_str

                    # Handle module.Class format if present in type string
                    if "." in class_name:
                        module_name_from_type, class_name = class_name.rsplit(".", 1)
                        # TODO: Potentially refine module path based on type string
                        # For now, assume the class is in the same module as the command

                    module = self._import_module(module_parts)

                    if hasattr(module, class_name):
                        class_obj = getattr(module, class_name)
                        # Check if it's actually a class
                        if inspect.isclass(class_obj):
                            # Filter param_value to only include keys accepted by __init__
                            init_sig = inspect.signature(class_obj.__init__)
                            valid_keys = {
                                p for p in init_sig.parameters if p != "self"
                            }  # Exclude 'self'
                            valid_params = {
                                k: v for k, v in param_value.items() if k in valid_keys
                            }
                            instance = class_obj(**valid_params)  # Use filtered params
                            processed_params[param_name] = instance
                        else:
                            # Log or raise warning? For now, just skip conversion
                            pass
                    else:
                        # Class not found in the expected module - revert to original error message for test
                        raise ValueError(
                            f"Failed to instantiate parameter '{param_name}' of type "
                            f"'{param_type_str}' for command '{command_key}'. "
                            f"Reason: Class '{class_name}' not found in module {module.__name__}."
                        )

                except (ImportError, AttributeError, TypeError) as e:
                    # ImportError/AttributeError: Class/Module not found
                    # TypeError: Instantiation failed (e.g., wrong args, validation error)
                    raise ValueError(
                        f"Failed to instantiate parameter '{param_name}' of type "
                        f"'{param_type_str}' for command '{command_key}'. "
                        f"Value: {param_value}. Error: {e}"
                    ) from e
                except Exception as e:  # Catch any other instantiation errors
                    raise ValueError(
                        f"Unexpected error instantiating parameter '{param_name}' of type "
                        f"'{param_type_str}' for command '{command_key}'. "
                        f"Value: {param_value}. Error: {e}"
                    ) from e

        return processed_params

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
