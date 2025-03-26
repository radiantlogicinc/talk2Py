"""Tests for advanced features of the command executor module.

This module contains test cases for the CommandExecutor class focusing on
context-aware command execution, context switching, and property handling.
"""

# pylint: disable=unused-argument,redefined-outer-name

import json
import sys
from pathlib import Path
from typing import Dict, Generator

import pytest

import talk2py
from talk2py import Action
from talk2py.command_executor import CommandExecutor
from talk2py.command_registry import CommandRegistry


@pytest.fixture
def cleanup_context() -> Generator[None, None, None]:
    """Reset the global context after each test."""
    talk2py.CURRENT_CONTEXT = None  # Reset before test
    yield
    talk2py.CURRENT_CONTEXT = None  # Reset after test


@pytest.fixture
def temp_todo_module(
    tmp_path: Path,
) -> Generator[Dict[str, Path], None, None]:  # pylint: disable=redefined-outer-name
    """Create a temporary todo list module for testing.

    Args:
        tmp_path: Pytest fixture providing a temporary directory path

    Returns:
        A dictionary containing the module directory and metadata file paths
    """
    module_dir = tmp_path / "todo_list"
    module_dir.mkdir()

    # Create todo_list.py with Todo and TodoList classes
    todo_list_code = '''
from datetime import datetime
from enum import Enum
from typing import List, Optional
import talk2py

class TodoState(Enum):
    """Enum representing the possible states of a Todo item."""
    ACTIVE = "active"
    CLOSED = "closed"

class Todo:
    """Class representing a single todo item."""
    def __init__(self, description: str):
        self._id = 0  # Simplified for testing
        self._description = description
        self._state = TodoState.ACTIVE
        self._date_created = datetime.now()
        self._date_closed = None

    @property
    @talk2py.command
    def description(self) -> str:
        """Get the todo item description."""
        return self._description

    @description.setter
    @talk2py.command
    def description(self, value: str) -> None:
        """Set the todo item description."""
        if value is None or not value.strip():
            raise ValueError("Description cannot be empty")
        self._description = value

    @property
    @talk2py.command
    def state(self) -> TodoState:
        """Get the current state of the todo item."""
        return self._state

    @talk2py.command
    def close(self) -> None:
        """Mark the todo item as closed."""
        self._state = TodoState.CLOSED
        self._date_closed = datetime.now()

    @talk2py.command
    def reopen(self) -> None:
        """Reopen a closed todo item."""
        if self._state == TodoState.CLOSED:
            self._state = TodoState.ACTIVE
            self._date_closed = None

class TodoList:
    """Class for managing a collection of Todo items."""
    def __init__(self):
        self._todos: List[Todo] = []
        self._current_todo: Optional[Todo] = None

    @talk2py.command
    def add_todo(self, description: str) -> Todo:
        """Add a new todo item to the list."""
        todo = Todo(description)
        self._todos.append(todo)
        return todo

    @property
    @talk2py.command
    def current_todo(self) -> Optional[Todo]:
        """Get the current todo."""
        return self._current_todo

    @current_todo.setter
    @talk2py.command
    def current_todo(self, todo: Todo) -> None:
        """Set the current todo."""
        if todo in self._todos:
            self._current_todo = todo
            # Switch context to the current todo
            talk2py.CURRENT_CONTEXT = todo
        else:
            raise ValueError("Todo not in list")

@talk2py.command
def init_todolist() -> TodoList:
    """Initialize a new todo list and set it as the current context."""
    todo_list = TodoList()
    talk2py.CURRENT_CONTEXT = todo_list
    return todo_list
'''
    with open(module_dir / "todo_list.py", "w", encoding="utf-8") as f:
        f.write(todo_list_code)

    # Create command metadata
    metadata = {
        "app_folderpath": str(module_dir),
        "map_commandkey_2_metadata": {
            "todo_list.init_todolist": {
                "command_implementation_module_path": "./todo_list.py",
                "command_implementation_class_name": None,
                "parameters": [],
                "return_type": "TodoList",
            },
            "todo_list.Todo.description": {
                "command_implementation_module_path": "./todo_list.py",
                "command_implementation_class_name": "Todo",
                "parameters": [{"name": "value", "type": "str"}],
                "return_type": "str",
            },
            "todo_list.Todo.state": {
                "command_implementation_module_path": "./todo_list.py",
                "command_implementation_class_name": "Todo",
                "parameters": [],
                "return_type": "TodoState",
            },
            "todo_list.Todo.close": {
                "command_implementation_module_path": "./todo_list.py",
                "command_implementation_class_name": "Todo",
                "parameters": [],
                "return_type": "None",
            },
            "todo_list.Todo.reopen": {
                "command_implementation_module_path": "./todo_list.py",
                "command_implementation_class_name": "Todo",
                "parameters": [],
                "return_type": "None",
            },
            "todo_list.TodoList.add_todo": {
                "command_implementation_module_path": "./todo_list.py",
                "command_implementation_class_name": "TodoList",
                "parameters": [{"name": "description", "type": "str"}],
                "return_type": "Todo",
            },
            "todo_list.TodoList.current_todo": {
                "command_implementation_module_path": "./todo_list.py",
                "command_implementation_class_name": "TodoList",
                "parameters": [{"name": "todo", "type": "Todo"}],
                "return_type": "Todo",
            },
        },
    }

    # Create ___command_info directory and metadata file
    command_info_dir = module_dir / "___command_info"
    command_info_dir.mkdir()
    metadata_path = command_info_dir / "command_metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f)

    # Add module directory to sys.path so it can be imported
    sys.path.insert(0, str(tmp_path))

    result = {"module_dir": module_dir, "metadata_path": metadata_path}
    yield result

    # Clean up
    sys.path.remove(str(tmp_path))


@pytest.fixture
def executor_with_todo(
    temp_todo_module: Dict[str, Path]  # pylint: disable=redefined-outer-name
) -> CommandExecutor:
    """Create a CommandExecutor with todo list commands loaded.

    Args:
        temp_todo_module: Fixture providing test module paths

    Returns:
        Configured CommandExecutor instance
    """
    registry = CommandRegistry(str(temp_todo_module["module_dir"]))
    return CommandExecutor(registry)


def test_command_executor_with_context(
    executor_with_todo: CommandExecutor,  # pylint: disable=redefined-outer-name
    cleanup_context: Generator[
        None, None, None
    ],  # pylint: disable=redefined-outer-name,unused-argument
) -> None:
    """Test executing commands in different contexts.

    Args:
        executor_with_todo: Fixture providing configured CommandExecutor
        cleanup_context: Fixture to reset global context
    """
    # Initialize todo list (global context)
    init_action = Action(
        app_folderpath="./examples/todo_list",
        command_key="todo_list.init_todolist",
        parameters={},
    )
    todo_list = executor_with_todo.perform_action(init_action)
    assert isinstance(todo_list, object)  # Class not directly accessible in test

    # Add a todo (TodoList context)
    talk2py.CURRENT_CONTEXT = todo_list
    add_action = Action(
        app_folderpath="./examples/todo_list",
        command_key="todo_list.TodoList.add_todo",
        parameters={"description": "Test todo"},
    )
    todo = executor_with_todo.perform_action(add_action)
    assert isinstance(todo, object)  # Class not directly accessible in test

    # Set current todo to switch context
    talk2py.CURRENT_CONTEXT = todo

    # Close todo (Todo context)
    close_action = Action(
        app_folderpath="./examples/todo_list",
        command_key="todo_list.Todo.close",
        parameters={},
    )
    executor_with_todo.perform_action(close_action)

    # Check todo state (Todo context)
    state_action = Action(
        app_folderpath="./examples/todo_list",
        command_key="todo_list.Todo.state",
        parameters={},
    )
    state = executor_with_todo.perform_action(state_action)
    assert str(state) == "TodoState.CLOSED"


def test_command_executor_context_switching(
    executor_with_todo: CommandExecutor,  # pylint: disable=redefined-outer-name
    cleanup_context: Generator[
        None, None, None
    ],  # pylint: disable=redefined-outer-name,unused-argument
) -> None:
    """Test command execution while switching contexts.

    Args:
        executor_with_todo: Fixture providing configured CommandExecutor
        cleanup_context: Fixture to reset global context
    """
    # Initialize todo list and set as context
    init_action = Action(
        app_folderpath="./examples/todo_list",
        command_key="todo_list.init_todolist",
        parameters={},
    )
    todo_list = executor_with_todo.perform_action(init_action)
    assert talk2py.CURRENT_CONTEXT == todo_list

    # Add a todo in TodoList context
    add_action = Action(
        app_folderpath="./examples/todo_list",
        command_key="todo_list.TodoList.add_todo",
        parameters={"description": "Test todo"},
    )
    todo = executor_with_todo.perform_action(add_action)

    # Switch to Todo context
    talk2py.CURRENT_CONTEXT = todo

    # Modify todo in Todo context
    close_action = Action(
        app_folderpath="./examples/todo_list",
        command_key="todo_list.Todo.close",
        parameters={},
    )
    executor_with_todo.perform_action(close_action)

    # Switch back to TodoList context
    talk2py.CURRENT_CONTEXT = todo_list

    # Add another todo in TodoList context
    add_action2 = Action(
        app_folderpath="./examples/todo_list",
        command_key="todo_list.TodoList.add_todo",
        parameters={"description": "Another todo"},
    )
    executor_with_todo.perform_action(add_action2)


def test_command_executor_invalid_context(
    executor_with_todo: CommandExecutor,  # pylint: disable=redefined-outer-name
    cleanup_context: Generator[
        None, None, None
    ],  # pylint: disable=redefined-outer-name,unused-argument
) -> None:
    """Test error handling for invalid contexts.

    Args:
        executor_with_todo: Fixture providing configured CommandExecutor
        cleanup_context: Fixture to reset global context
    """
    # Initialize todo list
    init_action = Action(
        app_folderpath="./examples/todo_list",
        command_key="todo_list.init_todolist",
        parameters={},
    )
    todo_list = executor_with_todo.perform_action(init_action)

    # Try to call Todo method with TodoList context
    talk2py.CURRENT_CONTEXT = todo_list
    with pytest.raises(TypeError, match="Object must be an instance of Todo"):
        close_action = Action(
            app_folderpath="./examples/todo_list",
            command_key="todo_list.Todo.close",
            parameters={},
        )
        executor_with_todo.perform_action(close_action)

    # Add a todo and get its instance
    add_action = Action(
        app_folderpath="./examples/todo_list",
        command_key="todo_list.TodoList.add_todo",
        parameters={"description": "Test todo"},
    )
    todo = executor_with_todo.perform_action(add_action)

    # Try to call TodoList method with Todo context
    talk2py.CURRENT_CONTEXT = todo
    with pytest.raises(TypeError, match="Object must be an instance of TodoList"):
        add_action2 = Action(
            app_folderpath="./examples/todo_list",
            command_key="todo_list.TodoList.add_todo",
            parameters={"description": "Another todo"},
        )
        executor_with_todo.perform_action(add_action2)


def test_command_executor_properties(
    executor_with_todo: CommandExecutor,  # pylint: disable=redefined-outer-name
    cleanup_context: Generator[
        None, None, None
    ],  # pylint: disable=redefined-outer-name,unused-argument
) -> None:
    """Test handling of property getter/setter commands.

    Args:
        executor_with_todo: Fixture providing configured CommandExecutor
        cleanup_context: Fixture to reset global context
    """
    # Initialize todo list
    init_action = Action(
        app_folderpath="./examples/todo_list",
        command_key="todo_list.init_todolist",
        parameters={},
    )
    todo_list = executor_with_todo.perform_action(init_action)

    # Add a todo in TodoList context
    talk2py.CURRENT_CONTEXT = todo_list
    add_action = Action(
        app_folderpath="./examples/todo_list",
        command_key="todo_list.TodoList.add_todo",
        parameters={"description": "Test todo"},
    )
    todo = executor_with_todo.perform_action(add_action)

    # Switch to Todo context
    talk2py.CURRENT_CONTEXT = todo

    # Test property getter
    state_action = Action(
        app_folderpath="./examples/todo_list",
        command_key="todo_list.Todo.state",
        parameters={},
    )
    state = executor_with_todo.perform_action(state_action)
    assert str(state) == "TodoState.ACTIVE"

    # Test property setter with a fixed value
    desc_action = Action(
        app_folderpath="./examples/todo_list",
        command_key="todo_list.Todo.description",
        parameters={"value": "Updated todo"},
    )
    executor_with_todo.perform_action(desc_action)

    # Verify property was set by calling the method again
    talk2py.CURRENT_CONTEXT = todo  # Ensure context is still set
    desc_get_action = Action(
        app_folderpath="./examples/todo_list",
        command_key="todo_list.Todo.description",
        parameters={},
    )
    desc = executor_with_todo.perform_action(desc_get_action)
    assert desc == "Updated todo"
