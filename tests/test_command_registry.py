"""Tests for the command registry module.

This module contains test cases for the CommandRegistry class, including
metadata loading, function registration, and command execution.
"""

import importlib
import os
import sys
from pathlib import Path
from typing import Any, Type

import pytest

from talk2py.code_parsing_execution.command_registry import CommandRegistry


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
        '''
from talk2py import command

@command
def add(a: int, b: int) -> int:
    """
    Add two numbers.

    Args:
        a: First number
        b: Second number

    Returns:
        Sum of the two numbers
    """
    return a + b

class Calculator:
    @command
    def multiply(self, a: int, b: int) -> int:
        """
        Multiply two numbers.

        Args:
            a: First number
            b: Second number

        Returns:
            Product of the two numbers
        """
        return a * b

    @classmethod
    @command
    def from_config(cls, config: dict) -> 'Calculator':
        """
        Create a Calculator instance from a configuration dictionary.

        Args:
            config: Configuration dictionary

        Returns:
            A new Calculator instance
        """
        return cls()

    @staticmethod
    @command
    def validate(x: int) -> bool:
        """
        Validate if a number is positive.

        Args:
            x: Number to validate

        Returns:
            True if the number is positive
        """
        return x > 0
'''
    )

    # Create nested module
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    helper_py = subdir / "helper.py"
    helper_py.write_text(
        '''
from talk2py import command

@command
def subtract(a: int, b: int) -> int:
    """
    Subtract two numbers.

    Args:
        a: First number
        b: Second number

    Returns:
        Difference of the two numbers
    """
    return a - b

class MathHelper:
    @command
    def divide(self, a: int, b: int) -> int:
        """
        Divide two numbers.

        Args:
            a: First number
            b: Second number

        Returns:
            Integer division result
        """
        return a // b
'''
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
                    "return_type": "int",
                    "docstring": "Add two numbers."
                },
                "calculator.Calculator.multiply": {
                    "parameters": [
                        {"name": "a", "type": "int"},
                        {"name": "b", "type": "int"}
                    ],
                    "return_type": "int",
                    "docstring": "Multiply two numbers."
                },
                "calculator.Calculator.from_config": {
                    "parameters": [
                        {"name": "config", "type": "dict"}
                    ],
                    "return_type": "Calculator",
                    "docstring": "Create a Calculator instance from a configuration dictionary."
                },
                "calculator.Calculator.validate": {
                    "parameters": [
                        {"name": "x", "type": "int"}
                    ],
                    "return_type": "bool",
                    "docstring": "Validate if a number is positive."
                },
                "subdir.helper.subtract": {
                    "parameters": [
                        {"name": "a", "type": "int"},
                        {"name": "b", "type": "int"}
                    ],
                    "return_type": "int",
                    "docstring": "Subtract two numbers."
                },
                "subdir.helper.MathHelper.divide": {
                    "parameters": [
                        {"name": "a", "type": "int"},
                        {"name": "b", "type": "int"}
                    ],
                    "return_type": "int",
                    "docstring": "Divide two numbers."
                }
            }
        }"""
    )

    return metadata_json


def load_class_from_sysmodules(file_path: str, class_name: str) -> Type[Any]:
    """Dynamically load a class from sys.modules."""
    module_name = os.path.splitext(os.path.basename(file_path))[0]

    # the module should already exist in memory since CommandRegistry loaded it
    module = sys.modules[module_name]

    # Retrieve the class from the module
    if not hasattr(module, class_name):
        raise AttributeError(
            f"Module '{module_name}' does not define a class '{class_name}'"
        )

    return getattr(module, class_name)


class TestCommandRegistry:
    """Test cases for the CommandRegistry class.

    This class contains tests that verify the functionality of the CommandRegistry,
    including initialization, metadata loading, and command execution.
    """

    def test_init_without_metadata(self) -> None:
        """Test initializing registry without metadata."""
        registry = CommandRegistry()
        assert registry.command_metadata == {}
        assert not registry.command_funcs
        assert registry.metadata_dir is None

    def test_load_nonexistent_metadata(self) -> None:
        """Test loading metadata from a nonexistent file."""
        with pytest.raises(FileNotFoundError):
            CommandRegistry(command_metadata_path="nonexistent.json")

    def test_load_nonexistent_app_folder(self) -> None:
        """Test loading metadata from a nonexistent app folder."""
        with pytest.raises(FileNotFoundError):
            CommandRegistry(app_folderpath="nonexistent_folder")

    def test_get_metadata_path(self, tmp_path: Path) -> None:
        """Test getting the correct metadata path.

        Args:
            tmp_path: Pytest fixture providing a temporary directory path
        """
        # Create a command_metadata.json file
        command_info_dir = tmp_path / "___command_info"
        command_info_dir.mkdir()
        metadata_json = command_info_dir / "command_metadata.json"
        metadata_json.write_text("{}")

        # Test with absolute path
        metadata_path = CommandRegistry.get_metadata_path(str(tmp_path))
        assert metadata_path == str(metadata_json)

        # Test with relative path
        os.chdir(tmp_path.parent)
        relative_path = tmp_path.name
        metadata_path = CommandRegistry.get_metadata_path(relative_path)

        # Compare the path components instead of the full path
        # This ensures we're checking the right structure without worrying about absolute vs relative paths
        expected_components = [
            relative_path,
            "___command_info",
            "command_metadata.json",
        ]
        path_components = metadata_path.split(os.sep)

        # Check if all expected components are in the path
        for component in expected_components:
            assert component in path_components

        # Verify that the components appear in the right order
        last_index = -1
        for component in expected_components:
            current_index = path_components.index(component)
            assert current_index > last_index
            last_index = current_index

    def test_load_metadata_and_functions(
        self, todolist_registry: CommandRegistry, temp_todo_app: dict
    ) -> None:
        """Test loading metadata and functions from files.

        Args:
            todolist_registry: Fixture providing CommandRegistry with todo commands
            temp_todo_app: Fixture providing test module paths
        """
        # We'll use the todo_list app which is already set up by the fixtures
        module_file = str(temp_todo_app["module_file"])

        # Check metadata was loaded
        assert "app_folderpath" in todolist_registry.command_metadata
        assert "map_commandkey_2_metadata" in todolist_registry.command_metadata

        # Get TodoList class
        todolist_class = load_class_from_sysmodules(module_file, "TodoList")
        todo_list = todolist_class()

        # Test TodoList.add_todo method
        add_todo_func = todolist_registry.get_command_func(
            "todo_list.TodoList.add_todo", todo_list
        )
        assert add_todo_func is not None
        todo = add_todo_func(description="Test Todo")
        assert todo is not None
        assert todo.description == "Test Todo"

        # Test Todo.description property
        description_func = todolist_registry.get_command_func(
            "todo_list.Todo.description", todo
        )
        assert description_func is not None
        assert description_func() == "Test Todo"

    def test_get_nonexistent_command(self, todolist_registry: CommandRegistry) -> None:
        """Test getting a command that doesn't exist.

        Args:
            todolist_registry: Fixture providing CommandRegistry with todo commands
        """
        with pytest.raises(ValueError) as exc_info:
            todolist_registry.get_command_func("nonexistent.command")
        assert "Command 'nonexistent.command' does not exist" in str(exc_info.value)

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
            CommandRegistry(app_folderpath=str(tmp_path))

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
            CommandRegistry(app_folderpath=str(tmp_path))

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
            CommandRegistry(app_folderpath=str(tmp_path))

    def test_get_command_func_for_object(self, tmp_path: Path) -> None:
        """Test getting command function bound to an object.

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
        # Test with different types of objects
        calculator_py = tmp_path / "calculator.py"
        calculator_py.write_text(calculator_code)

        # Set up a registry with metadata
        command_info_dir = tmp_path / "___command_info"
        command_info_dir.mkdir()
        metadata_json = command_info_dir / "command_metadata.json"
        metadata_json.write_text(
            """{
            "app_folderpath": ".",
            "map_commandkey_2_metadata": {
                "calculator.Calculator.multiply": {
                    "parameters": [{"name": "a", "type": "int"}, {"name": "b", "type": "int"}],
                    "return_type": "int"
                }
            }
        }"""
        )

        os.chdir(tmp_path)

        # Import the module
        spec = importlib.util.spec_from_file_location("calculator", calculator_py)
        if not spec or not spec.loader:
            raise ImportError("Could not load calculator module")
        module = importlib.util.module_from_spec(spec)
        sys.modules["calculator"] = module
        spec.loader.exec_module(module)

        # Create registry and test objects
        registry = CommandRegistry(app_folderpath=str(tmp_path))
        calc = module.Calculator()

        # Test with correct object
        func = registry.get_command_func("calculator.Calculator.multiply", calc)
        assert func is not None
        assert func(4, 2) == 8

        # pylint: disable=too-few-public-methods
        class WrongClass:
            """A different class that should not be compatible."""

            def multiply(self, a: int, b: int) -> int:
                """This method has the same signature but should not match."""
                return a * b + 1

        # Test with wrong object type
        wrong_obj = WrongClass()
        with pytest.raises(TypeError):
            registry.get_command_func("calculator.Calculator.multiply", wrong_obj)

    def test_get_commands_in_current_context(
        self, todolist_registry: CommandRegistry, temp_todo_app: dict
    ) -> None:
        """Test getting commands available in the current context.

        Args:
            todolist_registry: Fixture providing CommandRegistry with todo commands
            temp_todo_app: Fixture providing test module paths
        """
        # We'll use the todo_list app which is already set up by the fixtures
        module_file = str(temp_todo_app["module_file"])

        # Get TodoList class
        todolist_class = load_class_from_sysmodules(module_file, "TodoList")
        todo_list = todolist_class()

        # Create a todo
        todo = todo_list.add_todo("Test Todo")

        # Test getting TodoList commands
        todo_list_commands = todolist_registry.get_commands_in_current_context(
            todo_list
        )
        assert "todo_list.TodoList.add_todo" in todo_list_commands
        assert "todo_list.TodoList.current_todo" in todo_list_commands
        assert "todo_list.Todo.description" not in todo_list_commands

        # Test getting Todo commands
        todo_commands = todolist_registry.get_commands_in_current_context(todo)
        assert "todo_list.Todo.description" in todo_commands
        assert "todo_list.Todo.close" in todo_commands
        assert "todo_list.TodoList.add_todo" not in todo_commands

    def test_get_command_func_context_validation(
        self, todolist_registry: CommandRegistry, temp_todo_app: dict
    ) -> None:
        """Test command function context validation.

        Args:
            todolist_registry: Fixture providing CommandRegistry with todo commands
            temp_todo_app: Fixture providing test module paths
        """
        # We'll use the todo_list app which is already set up by the fixtures
        module_file = str(temp_todo_app["module_file"])

        # Get TodoList class
        todolist_class = load_class_from_sysmodules(module_file, "TodoList")
        todo_list = todolist_class()

        # Create a todo
        todo = todo_list.add_todo("Test Todo")

        # Test getting TodoList method in correct context
        add_todo_func = todolist_registry.get_command_func(
            "todo_list.TodoList.add_todo", todo_list
        )
        assert add_todo_func is not None
        new_todo = add_todo_func(description="Another Todo")
        assert new_todo is not None
        assert new_todo.description == "Another Todo"

        # Test getting Todo method in correct context
        description_func = todolist_registry.get_command_func(
            "todo_list.Todo.description", todo
        )
        assert description_func is not None
        assert description_func() == "Test Todo"

        # Test getting TodoList method with wrong context (using Todo object)
        with pytest.raises(TypeError, match="Object must be an instance of TodoList"):
            todolist_registry.get_command_func("todo_list.TodoList.add_todo", todo)

        # Test getting Todo method with wrong context (using TodoList object)
        with pytest.raises(
            TypeError,
            match="Object must be an instance of Todo",
        ):
            todolist_registry.get_command_func("todo_list.Todo.description", todo_list)

        # Test getting nonexistent command
        with pytest.raises(
            ValueError, match="Command 'nonexistent.command' does not exist"
        ):
            todolist_registry.get_command_func("nonexistent.command")
