"""Tests for advanced features of the command executor module.

This module contains test cases for the CommandExecutor class focusing on
context-aware command execution, context switching, and property handling.
"""

# pylint: disable=unused-argument,redefined-outer-name

import typing
import pytest
from talk2py import Action, CHAT_CONTEXT
from talk2py.command_executor import CommandExecutor


def test_command_executor_with_context(
    todolist_executor: CommandExecutor,
    temp_todo_app: dict[str, typing.Any],
    chat_context_reset,
) -> None:
    """Test that CommandExecutor works with context.
    
    Args:
        todolist_executor: Fixture providing CommandExecutor with todo registry
        temp_todo_app: Fixture providing test module paths
        chat_context_reset: Fixture to reset chat context before and after test
    """
    # Test running commands on an app.
    app_path = str(temp_todo_app["module_dir"])
    
    # Register app with chat context
    CHAT_CONTEXT.register_app(app_path)
    
    # Import and create necessary objects to use as context
    module_file = str(temp_todo_app["module_file"])
    
    # Import the module and get the TodoList class directly
    import os
    import sys
    module_name = os.path.splitext(os.path.basename(module_file))[0]
    todo_list_module = sys.modules[module_name]
    TodoList = getattr(todo_list_module, "TodoList")
    
    # Create a TodoList instance and set as current object
    todo_list = TodoList()
    CHAT_CONTEXT.current_object = todo_list
    
    # First create a todo.
    todo_action = Action(
        app_folderpath=app_path,
        command_key="todo_list.TodoList.add_todo",
        parameters={"description": "Test todo"},
    )
    todo = todolist_executor.perform_action(todo_action)

    assert todo is not None

    # Set the current todo.
    current_todo_action = Action(
        app_folderpath=app_path,
        command_key="todo_list.TodoList.current_todo",
        parameters={"value": todo._id},  # Using 'value' instead of 'todo'
    )
    current_todo = todolist_executor.perform_action(current_todo_action)
    assert current_todo == todo

    # Get the todo's description (using an existing property)
    # First set the current object to the todo for property access
    CHAT_CONTEXT.current_object = todo
    description_action = Action(
        app_folderpath=app_path,
        command_key="todo_list.Todo.description",
        parameters={},
    )
    description = todolist_executor.perform_action(description_action)
    assert description == "Test todo"
