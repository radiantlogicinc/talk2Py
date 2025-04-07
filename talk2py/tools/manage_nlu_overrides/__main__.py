"""
Main module for adding NLU interface overrides to talk2py applications.
"""

import argparse
import contextlib
import importlib.util
import json
import os
import sys
from dataclasses import dataclass
from typing import Optional, Set

from talk2py import get_registry
from talk2py.nlu_pipeline.nlu_engine_interfaces import (
    ParameterExtractionInterface,
    ResponseGenerationInterface,
)


@dataclass
class InvalidOverride:
    """Represents an invalid NLU interface override implementation."""

    command_key: str
    interface_type: str
    file_path: str
    error: str


class NLUOverridesManager:
    """Manages NLU interface overrides for talk2py applications."""

    INTERFACE_TYPES = {
        1: (
            "param_extraction_class",
            ParameterExtractionInterface,
            "param_extraction.py",
        ),
        2: (
            "response_generation_class",
            ResponseGenerationInterface,
            "response_generation.py",
        ),
    }

    def __init__(self, app_folder_path: str):
        """Initialize the NLU interface manager.

        Args:
            app_folder_path: Path to the application folder
        """
        self.app_folder_path = os.path.abspath(app_folder_path)
        self.command_registry = get_registry(app_folder_path)
        self.metadata_file = os.path.join(
            app_folder_path, "___command_info", "nlu_engine_metadata.json"
        )
        self.overrides_dir = os.path.join(app_folder_path, "nlu_interface_overrides")
        self.nlu_metadata: dict = self._load_or_create_metadata()
        self.invalid_overrides: list[InvalidOverride] = []

    def _load_or_create_metadata(self) -> dict:
        """Load existing metadata or create new if not exists/invalid."""
        with contextlib.suppress(json.JSONDecodeError, OSError):
            if os.path.exists(self.metadata_file):
                with open(self.metadata_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        # Create new metadata structure
        return {
            "map_commandkey_2_nluengine_metadata": {},
        }

    def _validate_override_implementation(
        self, module_path: str, interface_class: type
    ) -> tuple[bool, Optional[str]]:
        """Validate that a module contains a valid interface implementation.

        Args:
            module_path: Path to the module file
            interface_class: Expected interface class to implement

        Returns:
            tuple of (is_valid, error_message)
        """
        try:
            # Import the module
            spec = importlib.util.spec_from_file_location("temp_module", module_path)
            if not spec or not spec.loader:
                return False, f"Could not load module: {module_path}"

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Expected class names based on interface type
            if interface_class == ParameterExtractionInterface:
                expected_class_name = "DefaultParameterExtraction"
            elif interface_class == ResponseGenerationInterface:
                expected_class_name = "DefaultResponseGeneration"
            else:
                return False, f"Unknown interface class: {interface_class.__name__}"

            # Find implementation class
            impl_class = None
            if hasattr(module, expected_class_name):
                cls = getattr(module, expected_class_name)
                if isinstance(cls, type) and issubclass(cls, interface_class):
                    impl_class = cls

            if not impl_class:
                return (
                    False,
                    f"No valid implementation of {interface_class.__name__} found."
                    f"Expected class name: {expected_class_name}",
                )

            return True, None

        except Exception as e:  # pylint: disable=broad-exception-caught
            return False, str(e)

    # pylint: disable=too-many-branches,too-many-locals
    def _scan_existing_overrides(self) -> None:
        # sourcery skip: low-code-quality
        """Scan existing override implementations and update metadata."""
        if not os.path.exists(self.overrides_dir):
            return

        # Store existing metadata to preserve entries not found during scanning
        existing_metadata = self.nlu_metadata.get(
            "map_commandkey_2_nluengine_metadata", {}
        )

        # Initialize empty metadata dictionary without clearing existing entries
        scanned_metadata = {}
        self.invalid_overrides = []

        # Scan override directory
        for command_dir in os.listdir(self.overrides_dir):
            command_path = os.path.join(self.overrides_dir, command_dir)
            if not os.path.isdir(command_path):
                continue

            # Convert directory name to command key consistently with create_override
            command_key = ".".join(command_dir.split("_"))

            metadata = {}

            # Copy existing metadata for this command key if it exists
            if command_key in existing_metadata:
                metadata = existing_metadata[command_key].copy()

            # Check each interface type
            for _, (
                metadata_key,
                interface_class,
                filename,
            ) in self.INTERFACE_TYPES.items():
                impl_path = os.path.join(command_path, filename)
                if os.path.exists(impl_path):
                    is_valid, error = self._validate_override_implementation(
                        impl_path, interface_class
                    )
                    if is_valid:
                        # Determine the correct class name based on interface type
                        if metadata_key == "param_extraction_class":
                            class_name = "DefaultParameterExtraction"
                        elif metadata_key == "response_generation_class":
                            class_name = "DefaultResponseGeneration"
                        else:
                            class_name = "CustomImpl"  # Fallback

                        module_path = (
                            f"nlu_interface_overrides.{command_dir}.{filename[:-3]}"
                        )
                        metadata[metadata_key] = f"{module_path}.{class_name}"
                    else:
                        self.invalid_overrides.append(
                            InvalidOverride(
                                command_key,
                                metadata_key,
                                impl_path,
                                error or "Unknown error",
                            )
                        )

            if metadata:
                scanned_metadata[command_key] = metadata

        # Merge scanned metadata with existing metadata
        for command_key, metadata in existing_metadata.items():
            if command_key not in scanned_metadata:
                scanned_metadata[command_key] = metadata

        # Update the metadata dictionary
        self.nlu_metadata["map_commandkey_2_nluengine_metadata"] = scanned_metadata

    def _save_metadata(self) -> None:
        """Save the NLU engine metadata to file."""
        os.makedirs(os.path.dirname(self.metadata_file), exist_ok=True)
        with open(self.metadata_file, "w", encoding="utf-8") as f:
            json.dump(self.nlu_metadata, f, indent=4)

    def get_available_commands(self) -> list[str]:
        """Get list of commands that have non-overridden interfaces.

        Returns:
            list of command keys that can be overridden
        """
        all_commands = set(
            self.command_registry.command_metadata.get(
                "map_commandkey_2_metadata", {}
            ).keys()
        )
        metadata_map = self.nlu_metadata.get("map_commandkey_2_nluengine_metadata", {})
        fully_overridden = {
            cmd
            for cmd, meta in metadata_map.items()
            if len([key for key, value in meta.items() if value is not None])
            >= len(self.INTERFACE_TYPES)
        }
        return sorted(list(all_commands - fully_overridden))

    def get_non_overridden_interfaces(self, command_key: str) -> list[tuple[int, str]]:
        """Get list of non-overridden interfaces for a command.

        Args:
            command_key: The command key to check

        Returns:
            list of tuples (interface_number, interface_name)
        """
        current_metadata = self.nlu_metadata.get(
            "map_commandkey_2_nluengine_metadata", {}
        ).get(command_key, {})
        return [
            (num, name)
            for num, (name, _, _) in self.INTERFACE_TYPES.items()
            if name not in current_metadata or current_metadata[name] is None
        ]

    def _create_override_directory(self, command_dir: str) -> str:
        """Create and initialize the override directory for a command.

        Args:
            command_dir: Directory name for the command

        Returns:
            Path to the created directory
        """
        override_path = os.path.join(self.overrides_dir, command_dir)
        os.makedirs(override_path, exist_ok=True)

        # Create empty __init__.py
        init_file = os.path.join(override_path, "__init__.py")
        with open(init_file, "w", encoding="utf-8") as f:
            f.write('"""NLU interface implementations for the command."""\n')

        return override_path

    # pylint: disable=too-many-locals
    def _create_interface_implementation(
        self, command_key: str, command_dir: str, override_path: str, interface_num: int
    ) -> None:
        """Create implementation for a specific interface.

        Args:
            command_key: The command key
            command_dir: Directory name for the command
            override_path: Path to the override directory
            interface_num: Interface number to implement
        """
        metadata_key, _, filename = self.INTERFACE_TYPES[interface_num]
        impl_path = os.path.join(override_path, filename)

        # Determine the correct class name based on interface type
        if metadata_key == "param_extraction_class":
            class_name = "DefaultParameterExtraction"
        elif metadata_key == "response_generation_class":
            class_name = "DefaultResponseGeneration"
        else:
            class_name = (
                "CustomImpl"  # Fallback, should not happen with current implementation
            )

        # Check if implementation file already exists
        file_exists = os.path.exists(impl_path)

        # Create file only if it doesn't exist
        if not file_exists:
            # Create directory if it doesn't exist
            os.makedirs(override_path, exist_ok=True)

            # Copy default implementation from talk2py folder
            default_impl = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                f"default_{filename}",
            )
            try:
                if not os.path.exists(default_impl):
                    raise FileNotFoundError(
                        f"Default implementation file not found: {default_impl}"
                    )

                with open(default_impl, "r", encoding="utf-8") as src:
                    content = src.read()

                with open(impl_path, "w", encoding="utf-8") as dst:
                    dst.write(content)

                # Verify file was written successfully
                if not os.path.exists(impl_path):
                    raise IOError(f"Failed to write implementation file: {impl_path}")

            except Exception as e:
                # Raise an explicit exception instead of falling back to placeholder
                raise FileNotFoundError(
                    f"Could not find or copy default implementation file: {default_impl}"
                ) from e

        # Always update metadata, regardless of whether we created the file or it already existed
        module_path = f"nlu_interface_overrides.{command_dir}.{filename[:-3]}"
        self.nlu_metadata["map_commandkey_2_nluengine_metadata"][command_key][
            metadata_key
        ] = f"{module_path}.{class_name}"

    def create_override(self, command_key: str, interface_numbers: Set[int]) -> None:
        """Create override implementations for selected interfaces.

        Args:
            command_key: The command key to create overrides for
            interface_numbers: Set of interface numbers to override

        Raises:
            ValueError: If command key doesn't exist
            OSError: If file operations fail
            FileNotFoundError: If default implementation files can't be found
        """
        if command_key not in self.command_registry.command_metadata.get(
            "map_commandkey_2_metadata", {}
        ):
            raise ValueError(f"Command key '{command_key}' does not exist in registry")

        # Create override directory
        command_dir = command_key.replace(".", "_")
        override_path = self._create_override_directory(command_dir)

        # Update metadata for this command
        if command_key not in self.nlu_metadata["map_commandkey_2_nluengine_metadata"]:
            self.nlu_metadata["map_commandkey_2_nluengine_metadata"][command_key] = {}

        # Create selected interface implementations
        for interface_num in interface_numbers:
            self._create_interface_implementation(
                command_key, command_dir, override_path, interface_num
            )

        self._save_metadata()


def _print_invalid_overrides(invalid_overrides: list[InvalidOverride]) -> None:
    """Print information about invalid override implementations.

    Args:
        invalid_overrides: list of invalid override implementations
    """
    if invalid_overrides:
        print("\nWarning: Found invalid override implementations:")
        for invalid in invalid_overrides:
            print(
                f"- {invalid.command_key} ({invalid.interface_type}): {invalid.error}"
            )
        print()


def _get_command_selection(available_commands: list[str]) -> Optional[str]:
    """Get command selection from user.

    Args:
        available_commands: list of available commands

    Returns:
        Selected command key or None if user wants to exit
    """
    print(f"\nAvailable commands ({len(available_commands)} remaining):")
    for i, cmd in enumerate(available_commands, 1):
        print(f"{i}. {cmd}")

    command_input = input("\nEnter command number (or press Enter to exit): ").strip()

    if not command_input:
        return None

    # Check if input is a valid number
    if command_input.isdigit():
        index = int(command_input) - 1
        if 0 <= index < len(available_commands):
            return available_commands[index]

    print(f"Error: '{command_input}' is not a valid command number")
    return None


def _get_interface_selection(interfaces: list[tuple[int, str]]) -> Set[int]:
    """Get interface selection from user.

    Args:
        interfaces: list of available interfaces

    Returns:
        Set of selected interface numbers
    """
    print("\nAvailable interfaces:")
    for num, name in interfaces:
        print(f"{num}. {name}")

    selection = input(
        "\nEnter interface numbers to override (comma-separated): "
    ).strip()

    try:
        interface_numbers = {
            int(num.strip()) for num in selection.split(",") if num.strip().isdigit()
        }
        return {num for num in interface_numbers if num in dict(interfaces)}
    except ValueError:
        print("Error: Invalid interface selection")
        return set()


def _print_summary(nlu_metadata: dict) -> None:
    """Print summary of NLU interface overrides.

    Args:
        nlu_metadata: NLU metadata dictionary
    """
    print("\nSummary of NLU interface overrides:")
    for cmd, meta in nlu_metadata.get(
        "map_commandkey_2_nluengine_metadata", {}
    ).items():
        print(f"\n{cmd}:")
        for key, value in meta.items():
            print(f"  {key}: {value}")


def main():
    """Main entry point for adding NLU interface overrides."""
    parser = argparse.ArgumentParser(
        description="Add NLU interface overrides to talk2py applications"
    )
    parser.add_argument("app_folder_path", help="Path to the application folder")
    args = parser.parse_args()

    try:
        manager = NLUOverridesManager(args.app_folder_path)
        manager._scan_existing_overrides()  # pylint: disable=protected-access
        _print_invalid_overrides(manager.invalid_overrides)

        while True:
            available_commands = manager.get_available_commands()
            if not available_commands:
                print("No more commands available for override customization.")
                break

            command_key = _get_command_selection(available_commands)
            if not command_key:
                break

            interfaces = manager.get_non_overridden_interfaces(command_key)
            if not interfaces:
                print(f"No interfaces available to override for {command_key}")
                continue

            interface_numbers = _get_interface_selection(interfaces)
            if not interface_numbers:
                print("No valid interfaces selected")
                continue

            try:
                manager.create_override(command_key, interface_numbers)
                print(f"\nSuccessfully created overrides for {command_key}")
            except (ValueError, OSError) as e:
                print(f"Error creating overrides: {e}")
                continue

            response = input(
                "\nIs there another command_key you would like to customize for NLU? (y/N): "
            )
            if response.lower() != "y":
                break

        _print_summary(manager.nlu_metadata)
        print("\nNLU interface customization completed successfully.")

    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
