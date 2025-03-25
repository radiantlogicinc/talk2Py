"""Tests for the command registry module.

This module contains test cases for the CommandRegistry class, including
metadata loading, function registration, and command execution.
"""

import importlib
import os
import sys
from pathlib import Path

import pytest

from talk2py.command_registry import CommandRegistry


def create_test_files(tmp_path: Path) -> Path:
    # sourcery skip: extract-duplicate-method, inline-immediately-returned-variable
    """Create test files and metadata for testing.

    Args:
        tmp_path: Pytest fixture providing a temporary directory path

    Returns:
        Path to the created metadata JSON file
    """
    # Create calculator module
    calculator_py = tmp_path / "calculator.py"
    calculator_py.write_text(
        """
from talk2py import command

@command
def add(a: int, b: int) -> int:
    return a + b

class Calculator:
    @command
    def multiply(self, a: int, b: int) -> int:
        return a * b

    @classmethod
    @command
    def from_config(cls, config: dict) -> 'Calculator':
        return cls()

    @staticmethod
    @command
    def validate(x: int) -> bool:
        return x > 0
"""
    )

    # Create nested module
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    helper_py = subdir / "helper.py"
    helper_py.write_text(
        """
from talk2py import command

@command
def subtract(a: int, b: int) -> int:
    return a - b

class MathHelper:
    @command
    def divide(self, a: int, b: int) -> int:
        return a // b
"""
    )

    # Create command metadata
    command_info_dir = tmp_path / "___command_info"
    command_info_dir.mkdir()
    metadata_json = command_info_dir / "command_metadata.json"
    metadata_json.write_text(
        """{
        "app_folderpath": ".",
        "map_commandkey_2_metadata": {
            "calculator.add": {
                "parameters": [
                    {"name": "a", "type": "int"},
                    {"name": "b", "type": "int"}
                ],
                "return_type": "int"
            },
            "calculator.Calculator.multiply": {
                "parameters": [
                    {"name": "a", "type": "int"},
                    {"name": "b", "type": "int"}
                ],
                "return_type": "int"
            },
            "calculator.Calculator.from_config": {
                "parameters": [
                    {"name": "config", "type": "dict"}
                ],
                "return_type": "Calculator"
            },
            "calculator.Calculator.validate": {
                "parameters": [
                    {"name": "x", "type": "int"}
                ],
                "return_type": "bool"
            },
            "subdir.helper.subtract": {
                "parameters": [
                    {"name": "a", "type": "int"},
                    {"name": "b", "type": "int"}
                ],
                "return_type": "int"
            },
            "subdir.helper.MathHelper.divide": {
                "parameters": [
                    {"name": "a", "type": "int"},
                    {"name": "b", "type": "int"}
                ],
                "return_type": "int"
            }
        }
    }"""
    )

    return metadata_json


class TestCommandRegistry:
    """Test cases for the CommandRegistry class.

    This class contains tests that verify the functionality of the CommandRegistry,
    including initialization, metadata loading, and command execution.
    """

    def test_init_without_metadata(self) -> None:
        """Test initializing registry without metadata."""
        registry = CommandRegistry()
        assert not registry.command_metadata
        assert not registry.command_funcs
        assert registry.metadata_dir is None

    def test_load_nonexistent_metadata(self) -> None:
        """Test loading metadata from a nonexistent file."""
        with pytest.raises(FileNotFoundError):
            CommandRegistry("nonexistent.json")

    def test_load_metadata_and_functions(self, tmp_path: Path) -> None:
        """Test loading metadata and functions from files.

        Args:
            tmp_path: Pytest fixture providing a temporary directory path
        """
        metadata_json = create_test_files(tmp_path)

        # Change to the temp directory for imports to work
        os.chdir(tmp_path)

        registry = CommandRegistry(str(metadata_json))

        # Check metadata was loaded
        assert "app_folderpath" in registry.command_metadata
        assert "map_commandkey_2_metadata" in registry.command_metadata

        # Test global function
        add_func = registry.get_command_func("calculator.add")
        assert add_func is not None
        assert add_func(5, 3) == 8

        # Test class method
        multiply_func = registry.get_command_func("calculator.Calculator.multiply")
        assert multiply_func is not None
        assert multiply_func(None, 4, 2) == 8  # None is self

        # Test nested module global function
        subtract_func = registry.get_command_func("subdir.helper.subtract")
        assert subtract_func is not None
        assert subtract_func(10, 4) == 6

        # Test nested module class method
        divide_func = registry.get_command_func("subdir.helper.MathHelper.divide")
        assert divide_func is not None
        assert divide_func(None, 10, 3) == 3  # None is self

    def test_get_nonexistent_command(self, tmp_path: Path) -> None:
        """Test getting a command that doesn't exist.

        Args:
            tmp_path: Pytest fixture providing a temporary directory path
        """
        metadata_json = create_test_files(tmp_path)
        os.chdir(tmp_path)

        registry = CommandRegistry(str(metadata_json))
        assert registry.get_command_func("nonexistent.command") is None

    def test_invalid_module_path(self, tmp_path: Path) -> None:
        """Test loading a command with an invalid module path.

        Args:
            tmp_path: Pytest fixture providing a temporary directory path
        """
        command_info_dir = tmp_path / "___command_info"
        command_info_dir.mkdir()
        metadata_json = command_info_dir / "command_metadata.json"
        metadata_json.write_text(
            """{
            "app_folderpath": ".",
            "map_commandkey_2_metadata": {
                "nonexistent.module.func": {
                    "parameters": [],
                    "return_type": "int"
                }
            }
        }"""
        )

        os.chdir(tmp_path)

        with pytest.raises(ImportError):
            CommandRegistry(str(metadata_json))

    def test_invalid_class_name(self, tmp_path: Path) -> None:
        """Test loading a command with an invalid class name.

        Args:
            tmp_path: Pytest fixture providing a temporary directory path
        """
        command_info_dir = tmp_path / "___command_info"
        command_info_dir.mkdir()
        metadata_json = command_info_dir / "command_metadata.json"

        # Create module but with wrong class name in metadata
        calculator_py = tmp_path / "calculator.py"
        calculator_py.write_text(
            """
from talk2py import command

class RealCalculator:
    @command
    def add(self, a: int, b: int) -> int:
        return a + b
"""
        )

        metadata_json.write_text(
            """{
            "app_folderpath": ".",
            "map_commandkey_2_metadata": {
                "calculator.WrongCalculator.add": {
                    "parameters": [
                        {"name": "a", "type": "int"},
                        {"name": "b", "type": "int"}
                    ],
                    "return_type": "int"
                }
            }
        }"""
        )

        os.chdir(tmp_path)

        with pytest.raises(AttributeError, match="Class WrongCalculator not found"):
            CommandRegistry(str(metadata_json))

    def test_invalid_function_name(self, tmp_path: Path) -> None:
        """Test loading a command with an invalid function name.

        Args:
            tmp_path: Pytest fixture providing a temporary directory path
        """
        command_info_dir = tmp_path / "___command_info"
        command_info_dir.mkdir()
        metadata_json = command_info_dir / "command_metadata.json"

        # Create module but with wrong function name in metadata
        calculator_py = tmp_path / "calculator.py"
        calculator_py.write_text(
            """
from talk2py import command

@command
def real_func():
    pass
"""
        )

        metadata_json.write_text(
            """{
            "app_folderpath": ".",
            "map_commandkey_2_metadata": {
                "calculator.wrong_func": {
                    "parameters": [],
                    "return_type": "None"
                }
            }
        }"""
        )

        os.chdir(tmp_path)

        with pytest.raises(AttributeError, match="Function wrong_func not found"):
            CommandRegistry(str(metadata_json))

    def test_get_command_func_for_object(self, tmp_path: Path) -> None:
        """Test getting a command function bound to an object.

        Args:
            tmp_path: Pytest fixture providing a temporary directory path
        """
        # Create test class and module
        calculator_code = """
class Calculator:
    def multiply(self, a: int, b: int) -> int:
        return a * b

    @classmethod
    def from_config(cls, config: dict) -> 'Calculator':
        return cls()

    @staticmethod
    def validate(x: int) -> bool:
        return x > 0
"""
        calculator_py = tmp_path / "calculator.py"
        calculator_py.write_text(calculator_code)

        # Create test object
        # pylint: disable=too-few-public-methods
        class WrongClass:
            """Test wrong class."""

            def multiply(self, a: int, b: int) -> int:
                """Multiply two numbers."""
                return a * b

        # Create registry with metadata
        command_info_dir = tmp_path / "___command_info"
        command_info_dir.mkdir()
        metadata_json = command_info_dir / "command_metadata.json"
        metadata_json.write_text(
            """{
            "app_folderpath": ".",
            "map_commandkey_2_metadata": {
                "calculator.Calculator.multiply": {
                    "parameters": [
                        {"name": "a", "type": "int"},
                        {"name": "b", "type": "int"}
                    ],
                    "return_type": "int"
                }
            }
        }"""
        )

        os.chdir(tmp_path)

        # Load the module and create objects
        spec = importlib.util.spec_from_file_location("calculator", calculator_py)
        if not spec or not spec.loader:
            raise ImportError("Could not load calculator module")
        module = importlib.util.module_from_spec(spec)
        sys.modules["calculator"] = module
        spec.loader.exec_module(module)

        calc = module.Calculator()
        wrong_obj = WrongClass()

        # Create registry and register command
        registry = CommandRegistry(str(metadata_json))

        # Debug logging to inspect types
        print("\nDebug type information:")
        print(f"calc type: {type(calc)}")
        print(f"calc type module: {type(calc).__module__}")
        print(f"calc memory address: {hex(id(calc))}")

        # Get the Calculator class from the registry's perspective
        command_func = registry.get_command_func("calculator.Calculator.multiply")
        print(f"command_func type: {type(command_func)}")
        print(f"command_func: {command_func}")

        # Test getting function for correct object
        func = registry.get_command_func("calculator.Calculator.multiply", calc)
        assert func is not None
        assert func(2, 3) == 6

        # Test getting function for wrong object type
        with pytest.raises(TypeError) as exc_info:
            registry.get_command_func("calculator.Calculator.multiply", wrong_obj)
        assert str(exc_info.value) == "Object must be an instance of Calculator"
