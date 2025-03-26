"""Tests for the command executor module.

This module contains test cases for the CommandExecutor class, including
command execution and error handling.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from talk2py import Action
from talk2py.command_executor import CommandExecutor
from talk2py.command_registry import CommandRegistry


@pytest.fixture
def temp_calculator_module(tmp_path: Path) -> dict:
    """Create a temporary calculator module for testing.

    Args:
        tmp_path: Pytest fixture providing a temporary directory path

    Returns:
        A dictionary containing the module directory and metadata file paths
    """
    module_dir = tmp_path / "calculator"
    module_dir.mkdir()

    # Create calculator.py
    calculator_code = """
def add(a: int, b: int) -> int:
    return a + b

def subtract(a: int, b: int) -> int:
    return a - b
"""
    with open(module_dir / "calculator.py", "w", encoding="utf-8") as f:
        f.write(calculator_code)

    # Create command metadata
    metadata = {
        "app_folderpath": str(module_dir),
        "map_commandkey_2_metadata": {
            "calculator.add": {
                "command_implementation_module_path": "./calculator.py",
                "command_implementation_class_name": None,
                "parameters": [
                    {"name": "a", "type": "int"},
                    {"name": "b", "type": "int"},
                ],
                "return_type": "int",
            },
            "calculator.subtract": {
                "command_implementation_module_path": "./calculator.py",
                "command_implementation_class_name": None,
                "parameters": [
                    {"name": "a", "type": "int"},
                    {"name": "b", "type": "int"},
                ],
                "return_type": "int",
            },
        },
    }

    # Create ___command_info directory and metadata file
    command_info_dir = module_dir / "___command_info"
    command_info_dir.mkdir()
    metadata_path = command_info_dir / "command_metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f)

    return {"module_dir": module_dir, "metadata_path": metadata_path}


# pylint: disable=redefined-outer-name
def test_command_registry_initialization(temp_calculator_module: dict) -> None:
    """Test initialization of CommandRegistry with metadata.

    Args:
        temp_calculator_module: Fixture providing test module paths
    """
    registry = CommandRegistry(str(temp_calculator_module["module_dir"]))
    assert len(registry.command_metadata["map_commandkey_2_metadata"]) == 2
    assert "calculator.add" in registry.command_metadata["map_commandkey_2_metadata"]
    assert (
        "calculator.subtract" in registry.command_metadata["map_commandkey_2_metadata"]
    )


def test_command_registry_get_command_func(temp_calculator_module: dict) -> None:
    """Test retrieving and executing command functions from registry.

    Args:
        temp_calculator_module: Fixture providing test module paths
    """
    registry = CommandRegistry(str(temp_calculator_module["module_dir"]))

    add_func = registry.get_command_func("calculator.add")
    assert add_func is not None
    assert add_func(3, 4) == 7

    subtract_func = registry.get_command_func("calculator.subtract")
    assert subtract_func is not None
    assert subtract_func(7, 3) == 4


def test_command_registry_invalid_command(temp_calculator_module: dict) -> None:
    """Test behavior when requesting non-existent command.

    Args:
        temp_calculator_module: Fixture providing test module paths
    """
    registry = CommandRegistry(str(temp_calculator_module["module_dir"]))
    with pytest.raises(
        ValueError, match="Command 'calculator.nonexistent' does not exist"
    ):
        registry.get_command_func("calculator.nonexistent")


def test_command_executor_perform_action(temp_calculator_module: dict) -> None:
    """Test executing commands through CommandExecutor.

    Args:
        temp_calculator_module: Fixture providing test module paths
    """
    registry = CommandRegistry(str(temp_calculator_module["module_dir"]))
    executor = CommandExecutor(registry)

    # Test add command
    add_action = Action(
        app_folderpath="./examples/calculator",
        command_key="calculator.add",
        parameters={"a": 5, "b": 3},
    )
    result = executor.perform_action(add_action)
    assert result == 8

    # Test subtract command
    subtract_action = Action(
        app_folderpath="./examples/calculator",
        command_key="calculator.subtract",
        parameters={"a": 10, "b": 4},
    )
    result = executor.perform_action(subtract_action)
    assert result == 6


# pylint: enable=redefined-outer-name


def test_command_executor_invalid_command() -> None:
    """Test behavior when executing non-existent command."""
    executor = CommandExecutor(CommandRegistry())  # Initialize with empty registry
    invalid_action = Action(
        app_folderpath="./examples/calculator",
        command_key="calculator.nonexistent",
        parameters={},
    )

    with pytest.raises(
        ValueError, match="Command 'calculator.nonexistent' does not exist"
    ):
        executor.perform_action(invalid_action)


def test_command_executor_with_get_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test CommandExecutor using get_registry function.

    Args:
        monkeypatch: Pytest fixture for patching attributes
    """
    # Mock the get_registry function
    mock_registry = MagicMock()
    mock_registry.get_command_func.return_value = lambda x: f"Result: {x}"

    # Patch get_registry to return our mock registry
    monkeypatch.setattr("talk2py.get_registry", lambda app_path: mock_registry)

    # Create a CommandExecutor without providing a registry
    executor = CommandExecutor()

    # Create an action
    action = Action(
        app_folderpath="/mock/path",
        command_key="test.command",
        parameters={"x": "test"},
    )

    # Execute the action
    result = executor.perform_action(action)

    # Verify the action was executed with the registry from get_registry
    assert result == "Result: test"
    mock_registry.get_command_func.assert_called_once_with(
        "test.command", None, {"x": "test"}
    )
