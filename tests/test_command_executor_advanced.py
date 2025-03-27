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

from talk2py.command_executor import CommandExecutor
from talk2py.command_registry import CommandRegistry


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

    yield {"module_dir": module_dir, "metadata_path": metadata_path}
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


# Note: Tests related to context management have been moved to test_chat_context.py
