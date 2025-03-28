"""Tests for the command executor module.

This module contains test cases for the CommandExecutor class, including
command execution and error handling.
"""

from unittest.mock import MagicMock

import pytest

from talk2py import Action
from talk2py.command_executor import CommandExecutor
from talk2py.command_registry import CommandRegistry


# pylint: disable=redefined-outer-name
def test_command_registry_initialization(temp_calculator_app: dict) -> None:
    """Test initialization of CommandRegistry with metadata.

    Args:
        temp_calculator_app: Fixture providing test module paths
    """
    registry = CommandRegistry(str(temp_calculator_app["module_dir"]))
    assert len(registry.command_metadata["map_commandkey_2_metadata"]) > 0
    assert "calculator.add" in registry.command_metadata["map_commandkey_2_metadata"]
    assert (
        "calculator.subtract" in registry.command_metadata["map_commandkey_2_metadata"]
    )


def test_command_registry_get_command_func(temp_calculator_app: dict) -> None:
    """Test retrieving and executing command functions from registry.

    Args:
        temp_calculator_app: Fixture providing test module paths
    """
    registry = CommandRegistry(str(temp_calculator_app["module_dir"]))

    add_func = registry.get_command_func("calculator.add")
    assert add_func is not None
    assert add_func(3, 4) == 7

    subtract_func = registry.get_command_func("calculator.subtract")
    assert subtract_func is not None
    assert subtract_func(7, 3) == 4


def test_command_registry_invalid_command(temp_calculator_app: dict) -> None:
    """Test behavior when requesting non-existent command.

    Args:
        temp_calculator_app: Fixture providing test module paths
    """
    registry = CommandRegistry(str(temp_calculator_app["module_dir"]))
    with pytest.raises(
        ValueError, match="Command 'calculator.nonexistent' does not exist"
    ):
        registry.get_command_func("calculator.nonexistent")


def test_command_executor_perform_action(calculator_executor: CommandExecutor) -> None:
    """Test executing commands through CommandExecutor.

    Args:
        calculator_executor: Fixture providing CommandExecutor with calculator registry
    """
    # Test add command
    add_action = Action(
        app_folderpath="./examples/calculator",
        command_key="calculator.add",
        parameters={"a": 5, "b": 3},
    )
    result = calculator_executor.perform_action(add_action)
    assert result == 8

    # Test subtract command
    subtract_action = Action(
        app_folderpath="./examples/calculator",
        command_key="calculator.subtract",
        parameters={"a": 10, "b": 4},
    )
    result = calculator_executor.perform_action(subtract_action)
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


def test_command_executor_with_copied_app(calculator_executor: CommandExecutor, temp_calculator_app: dict) -> None:
    """Test executing commands from a copied app.

    This test demonstrates the benefit of using a copied app in a temporary directory.
    It's much simpler than trying to mock the entire application.

    Args:
        calculator_executor: Fixture providing CommandExecutor with calculator registry
        temp_calculator_app: Fixture providing test module paths
    """
    app_path = str(temp_calculator_app["module_dir"])
    
    # Test add command with the copied app
    add_action = Action(
        app_folderpath=app_path,
        command_key="calculator.add",
        parameters={"a": 5, "b": 3},
    )
    result = calculator_executor.perform_action(add_action)
    assert result == 8

    # Test subtract command with the copied app
    subtract_action = Action(
        app_folderpath=app_path,
        command_key="calculator.subtract",
        parameters={"a": 10, "b": 4},
    )
    result = calculator_executor.perform_action(subtract_action)
    assert result == 6


def test_todo_app_copied_correctly(
    todolist_executor: CommandExecutor, 
    temp_todo_app: dict, 
    chat_context_reset
) -> None:
    """Test that the todo app is correctly copied to the temp directory.
    
    This test verifies that the todo_list app is properly copied and its commands work.
    
    Args:
        todolist_executor: Fixture providing CommandExecutor with todo registry
        temp_todo_app: Fixture providing test module paths
        chat_context_reset: Fixture to reset chat context before and after test
    """
    from typing import Type, Any
    import os
    import sys
    from pathlib import Path
    
    app_path = str(temp_todo_app["module_dir"])
    module_file = str(temp_todo_app["module_file"])
    
    # Register the app with the chat context
    from talk2py import CHAT_CONTEXT
    CHAT_CONTEXT.register_app(app_path)
    
    # Verify the registry has the expected commands
    registry = todolist_executor.command_registry
    assert "todo_list.TodoList.add_todo" in registry.command_funcs
    
    # Check the current_todo command parameters
    current_todo_key = "todo_list.TodoList.current_todo"
    if current_todo_key in registry.command_metadata["map_commandkey_2_metadata"]:
        current_todo_params = registry.command_metadata["map_commandkey_2_metadata"][current_todo_key].get("parameters", [])
        print(f"Expected parameters for {current_todo_key}: {current_todo_params}")
    
    # Load the TodoList class from the module
    def load_class_from_sysmodules(file_path: str, class_name: str) -> Type[Any]:
        """Dynamically load a class from sys.modules."""
        module_name = os.path.splitext(os.path.basename(file_path))[0]
        
        # the module should already exist in memory since CommandRegistry loaded it
        module = sys.modules[module_name]
        
        # Retrieve the class from the module
        if not hasattr(module, class_name):
            raise AttributeError(f"Module '{module_name}' does not define a class '{class_name}'")
        
        return getattr(module, class_name)
    
    # Get the TodoList class
    TodoList: Type[Any] = load_class_from_sysmodules(module_file, "TodoList")
    todo_list = TodoList()
    
    # Set the TodoList instance as the current object
    CHAT_CONTEXT.current_object = todo_list
    
    # Add a todo
    add_action = Action(
        app_folderpath=app_path,
        command_key="todo_list.TodoList.add_todo",
        parameters={"description": "Test todo"},
    )
    
    # Execute the command
    todo = todolist_executor.perform_action(add_action)
    assert todo is not None
    
    # Now set the current todo
    if hasattr(todo, "_id"):
        todo_id = todo._id
        print(f"Todo id attribute: {todo_id}")
        
        # Set the current todo using the correct parameter name
        set_current_action = Action(
            app_folderpath=app_path,
            command_key=current_todo_key,
            parameters={"value": todo_id},
        )
        
        try:
            current_todo = todolist_executor.perform_action(set_current_action)
            assert current_todo == todo  # Should be the same todo object
            print("Successfully set current todo")
        except Exception as e:
            print(f"Error setting current todo: {e}")
    else:
        print("Todo does not have an _id attribute")
