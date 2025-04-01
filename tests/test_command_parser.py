"""
Test commands for testing the command registry generator.
# nosec: B101 - Pytest tests legitimately use assert statements
"""

import ast
import os
from typing import Any, Optional

from talk2py import command
from talk2py.code_parsing_execution.command_parser import (
    extract_function_metadata,
    extract_type_annotation,
    is_command_decorated,
    normalize_type_annotation,
    parse_python_file,
    scan_directory_for_commands,
    should_include_function,
)


@command
def command_decorated_function(name: str, age: int) -> str:
    """
    An example function with a command decorator.

    Args:
        name: The person's name
        age: The person's age

    Returns:
        A greeting message
    """
    return f"Hello {name}, you are {age} years old!"


@command
def simple_function(a: int, b: int) -> int:
    """
    A simple function that adds two numbers.

    Args:
        a: First number
        b: Second number

    Returns:
        Sum of the two numbers
    """
    return a + b


@command
def function_with_complex_types(
    data: list[dict[str, Any]], threshold: Optional[float] = None
) -> dict[str, Any]:
    """
    Function with complex type annotations.

    Args:
        data: list of dictionaries
        threshold: Optional threshold for filtering

    Returns:
        Filtered data
    """
    result: dict[str, Any] = {"items": []}

    for item in data:
        if threshold is None or item.get("value", 0) > threshold:
            result["items"].append(item)

    return result


def _private_function() -> None:
    """This function should not be included in the registry."""


class TestCommandParser:
    """
    Test cases for the command parser module.

    This class tests various functions from the command_parser module:
    - is_command_decorated: Tests detection of @command decorators
    - should_include_function: Tests function inclusion logic
    - normalize_type_annotation: Tests type annotation normalization
    - parse_python_file: Tests parsing Python files for command functions

    The tests verify that command-decorated functions are properly identified,
    their parameters and return types are correctly extracted, and private
    functions are excluded from the command registry.
    """

    def test_is_command_decorated(self):
        """Test if is_command_decorated correctly identifies decorated functions."""
        # Create a decorated function node
        code = "@command\ndef test_func():\n    pass"
        tree = ast.parse(code)
        func_def = tree.body[0]

        assert is_command_decorated(func_def)

        # Create a non-decorated function node
        code = "def test_func():\n    pass"
        tree = ast.parse(code)
        func_def = tree.body[0]

        assert not is_command_decorated(func_def)  # nosec B101

        # Test with a function that has a different decorator
        code = "@other_decorator\ndef test_func():\n    pass"
        tree = ast.parse(code)
        func_def = tree.body[0]

        assert not is_command_decorated(func_def)  # nosec B101

        # Test with a function that has the command decorator called as a function
        code = "@command()\ndef test_func():\n    pass"
        tree = ast.parse(code)
        func_def = tree.body[0]

        assert is_command_decorated(func_def)  # nosec B101

        # Test with @talk2py.command decorator
        code = "@talk2py.command\ndef test_func():\n    pass"
        tree = ast.parse(code)
        func_def = tree.body[0]

        assert is_command_decorated(func_def)  # nosec B101

        # Test with @talk2py.command() decorator call
        code = "@talk2py.command()\ndef test_func():\n    pass"
        tree = ast.parse(code)
        func_def = tree.body[0]

        assert is_command_decorated(func_def)  # nosec B101

        # Test with a different attribute decorator
        code = "@other.decorator\ndef test_func():\n    pass"
        tree = ast.parse(code)
        func_def = tree.body[0]

        assert not is_command_decorated(func_def)  # nosec B101

    def test_should_include_function(self):
        """Test if should_include_function correctly identifies functions to include."""
        # Create a decorated function node
        code = "@command\ndef test_func():\n    pass"
        tree = ast.parse(code)
        func_def = tree.body[0]

        assert should_include_function(func_def)

        # Create a non-decorated function node
        code = "def test_func():\n    pass"
        tree = ast.parse(code)
        func_def = tree.body[0]

        assert not should_include_function(func_def)

    def test_normalize_type_annotation(self):
        """Test if normalize_type_annotation correctly normalizes type strings."""
        assert normalize_type_annotation("str") == "str"
        assert normalize_type_annotation("int") == "int"
        assert normalize_type_annotation("float") == "float"
        assert normalize_type_annotation("INT") == "int"
        assert normalize_type_annotation("float", "calculator") == "int"
        assert normalize_type_annotation("CustomType") == "CustomType"

    def test_extract_type_annotation(self):
        """Test if extract_type_annotation correctly extracts type annotations."""
        # Test basic types
        code = "def test_func(a: int, b: str) -> bool: pass"
        tree = ast.parse(code)
        func_def = tree.body[0]

        int_annotation = func_def.args.args[0].annotation
        str_annotation = func_def.args.args[1].annotation
        bool_annotation = func_def.returns

        assert extract_type_annotation(int_annotation) == "int"
        assert extract_type_annotation(str_annotation) == "str"
        assert extract_type_annotation(bool_annotation) == "bool"

        # Test complex types
        code = "def test_func(a: list[int], b: dict[str, Any]) -> Optional[float]: pass"
        tree = ast.parse(code)
        func_def = tree.body[0]

        list_annotation = func_def.args.args[0].annotation
        dict_annotation = func_def.args.args[1].annotation
        optional_annotation = func_def.returns

        assert "list" in extract_type_annotation(list_annotation).lower()
        assert "dict" in extract_type_annotation(dict_annotation).lower()
        assert "optional" in extract_type_annotation(optional_annotation).lower()

        # Test None annotation
        assert extract_type_annotation(None) == "any"

    def test_extract_function_metadata(self):
        """Test if extract_function_metadata correctly extracts function metadata."""
        # Test basic function with docstring
        code = '''@command
def test_func(a: int, b: str) -> bool:
    """
    Test function docstring.
    """
    pass'''
        tree = ast.parse(code)
        func_def = tree.body[0]

        metadata = extract_function_metadata(func_def, "test_module")

        assert len(metadata["parameters"]) == 2
        assert metadata["parameters"][0]["name"] == "a"
        assert metadata["parameters"][0]["type"] == "int"
        assert metadata["parameters"][1]["name"] == "b"
        assert metadata["parameters"][1]["type"] == "str"
        assert metadata["return_type"] == "bool"
        assert metadata["docstring"] == "Test function docstring."

        # Test function with self parameter (should be skipped) and no docstring
        code = "@command\ndef method(self, a: int) -> None: pass"
        tree = ast.parse(code)
        func_def = tree.body[0]

        metadata = extract_function_metadata(func_def, "test_module")

        assert len(metadata["parameters"]) == 1
        assert metadata["parameters"][0]["name"] == "a"
        assert metadata["docstring"] == ""

    def test_parse_python_file(self, tmp_path):
        # sourcery skip: extract-duplicate-method
        """Test if parse_python_file correctly parses a Python file."""
        # Create a temporary Python file with test functions
        test_file = tmp_path / "test_module.py"
        test_file.write_text(
            '''
from talk2py import command

@command
def test_command(x: int, y: str) -> bool:
    """
    Test command function.

    Args:
        x: An integer parameter
        y: A string parameter

    Returns:
        A boolean result
    """
    return True

def not_a_command():
    pass

class Calculator:
    @command
    def add(self, a: int, b: int) -> int:
        """
        Add two numbers.

        Args:
            a: First number
            b: Second number

        Returns:
            Sum of the two numbers
        """
        return a + b
'''
        )

        commands = parse_python_file(str(test_file), str(tmp_path))

        assert len(commands) == 2
        # Check global function
        assert "test_module.test_command" in commands
        command_meta = commands["test_module.test_command"]
        assert len(command_meta["parameters"]) == 2
        assert command_meta["return_type"] == "bool"
        assert "Test command function" in command_meta["docstring"]

        # Check class method
        assert "test_module.Calculator.add" in commands
        command_meta = commands["test_module.Calculator.add"]
        assert len(command_meta["parameters"]) == 2
        assert command_meta["return_type"] == "int"
        assert "Add two numbers" in command_meta["docstring"]

    def test_scan_directory_for_commands(self, tmp_path):
        """Test if scan_directory_for_commands correctly scans a directory."""
        # Create a temporary directory with test files
        module1 = tmp_path / "module1.py"
        module1.write_text(
            """
from talk2py import command

@command
def command1(x: int) -> str:
    return "test"
"""
        )

        subdir = tmp_path / "subdir"
        subdir.mkdir()
        module2 = subdir / "module2.py"
        module2.write_text(
            """
from talk2py import command

class Helper:
    @command
    def command2(self, y: bool) -> int:
        return 42
"""
        )

        commands = scan_directory_for_commands(str(tmp_path))

        assert len(commands) == 2
        assert "module1.command1" in commands
        assert "subdir.module2.Helper.command2" in commands

    def test_current_file_parsing(self):
        """
        Test that the command parser correctly extracts metadata from the
        decorated functions in this file.
        """
        # Get the path to this file
        file_path = os.path.abspath(__file__)
        app_folder_path = os.path.dirname(file_path)  # project root

        # Parse this file
        commands = parse_python_file(file_path, app_folder_path)

        # There should be 3 commands in this file
        assert len(commands) == 3

        # Check command_decorated_function
        assert "test_command_parser.command_decorated_function" in commands
        function_meta = commands["test_command_parser.command_decorated_function"]
        assert len(function_meta["parameters"]) == 2
        assert function_meta["parameters"][0]["name"] == "name"
        assert function_meta["parameters"][0]["type"] == "str"
        assert function_meta["parameters"][1]["name"] == "age"
        assert function_meta["parameters"][1]["type"] == "int"
        assert function_meta["return_type"] == "str"
        assert (
            "An example function with a command decorator" in function_meta["docstring"]
        )

        # Check simple_function
        assert "test_command_parser.simple_function" in commands
        function_meta = commands["test_command_parser.simple_function"]
        assert len(function_meta["parameters"]) == 2
        assert function_meta["parameters"][0]["name"] == "a"
        assert function_meta["parameters"][0]["type"] == "int"
        assert function_meta["parameters"][1]["name"] == "b"
        assert function_meta["parameters"][1]["type"] == "int"
        assert function_meta["return_type"] == "int"
        assert "A simple function that adds two numbers" in function_meta["docstring"]

        # Check function_with_complex_types
        assert "test_command_parser.function_with_complex_types" in commands
        function_meta = commands["test_command_parser.function_with_complex_types"]
        assert len(function_meta["parameters"]) == 2
        assert function_meta["parameters"][0]["name"] == "data"
        assert "list" in function_meta["parameters"][0]["type"].lower()
        assert function_meta["parameters"][1]["name"] == "threshold"
        assert "optional" in function_meta["parameters"][1]["type"].lower()
        assert "dict" in function_meta["return_type"].lower()
        assert "Function with complex type annotations" in function_meta["docstring"]

        # Check that _private_function is not included
        assert "test_command_parser._private_function" not in commands

    def test_parse_inheritance_commands(self, tmp_path):
        """Test if parse_python_file correctly handles command inheritance between classes."""
        # Create a temporary Python file with a class hierarchy
        test_file = tmp_path / "test_inheritance.py"
        test_file.write_text(
            '''
from talk2py import command

class BaseClass:
    @command
    def base_method(self, x: int) -> str:
        """
        A method in the base class.

        Args:
            x: An integer parameter

        Returns:
            A string result
        """
        return f"Base: {x}"

    @command
    def shared_method(self, y: int) -> str:
        """
        A method that will be overridden in the child class.

        Args:
            y: An integer parameter

        Returns:
            A string result from the base class
        """
        return f"Base shared: {y}"

class ChildClass(BaseClass):
    @command
    def child_method(self, z: str) -> int:
        """
        A method in the child class.

        Args:
            z: A string parameter

        Returns:
            An integer result
        """
        return len(z)

    @command
    def shared_method(self, y: int) -> str:
        """
        Override of the shared method.

        Args:
            y: An integer parameter

        Returns:
            A string result from the child class
        """
        return f"Child shared: {y}"
'''
        )

        # Parse the file
        commands = parse_python_file(str(test_file), str(tmp_path))

        # Expected command keys
        base_method_key = "test_inheritance.BaseClass.base_method"
        base_shared_key = "test_inheritance.BaseClass.shared_method"
        child_method_key = "test_inheritance.ChildClass.child_method"
        child_shared_key = "test_inheritance.ChildClass.shared_method"
        child_inherited_key = "test_inheritance.ChildClass.base_method"

        # Assert base class methods are found
        assert base_method_key in commands, "Base class method not found"
        assert base_shared_key in commands, "Base class shared method not found"

        # Assert child class methods are found
        assert child_method_key in commands, "Child class method not found"
        assert child_shared_key in commands, "Child class shared method not found"

        # Assert the inherited method is found in the child class
        assert (
            child_inherited_key in commands
        ), "Inherited method not found in child class"

        # Check that the child's shared_method is its own implementation, not the base's
        assert (
            "Override of the shared method" in commands[child_shared_key]["docstring"]
        )

        # Check that the child's inherited method has the base class's docstring
        assert (
            "A method in the base class" in commands[child_inherited_key]["docstring"]
        )
