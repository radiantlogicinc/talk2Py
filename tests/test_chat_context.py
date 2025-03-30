"""Tests for chat context functionality.

This module contains test cases focused on context management, context switching,
and interactions with the CHAT_CONTEXT global variable.
"""

# pylint: disable=unused-argument,redefined-outer-name

import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Generator, Type

import pytest

from talk2py import CHAT_CONTEXT, Action
from talk2py.chat_context import ChatContext
from talk2py.code_parsing_execution.command_executor import CommandExecutor
from talk2py.code_parsing_execution.command_registry import CommandRegistry
from talk2py.types import ConversationArtifacts, ConversationEntry

# import fixtures
# from .conftest import (
#     temp_todo_app, todolist_registry, todolist_executor, _chat_context_reset,
#     TMP_PATH_EXAMPLES
# )


def load_class_from_sysmodules(file_path: str, class_name: str) -> Type[Any]:
    """Dynamically load a class from sys.modules."""
    module_name = os.path.splitext(os.path.basename(file_path))[0]

    # the module should already exist in memory since CommandRegistry loaded it
    module: ModuleType = sys.modules[module_name]

    # Retrieve the class from the module
    if not hasattr(module, class_name):
        raise AttributeError(
            f"Module '{module_name}' does not define a class '{class_name}'"
        )

    return getattr(module, class_name)


def test_command_executor_with_context(
    temp_todo_app: dict[str, Path],
    todolist_executor: CommandExecutor,  # pylint: disable=redefined-outer-name
    _chat_context_reset: Generator[
        None, None, None
    ],  # pylint: disable=redefined-outer-name,unused-argument
) -> None:
    """Test executing commands with current object context.

    Args:
        temp_todo_app: Fixture providing test module paths
        executor_with_todo: Fixture providing configured CommandExecutor
        reset_global_context: Fixture to reset global context
    """
    # Initialize todo list (global context)
    app_path = str(temp_todo_app["module_dir"])
    CHAT_CONTEXT.register_app(app_path)
    module_file = str(temp_todo_app["module_file"])

    # Import the module and get the TodoList class directly
    todolist_class: Type[Any] = load_class_from_sysmodules(module_file, "TodoList")
    todo_list = todolist_class()

    CHAT_CONTEXT.current_object = todo_list

    # Add a todo (TodoList context)
    add_action = Action(
        app_folderpath=app_path,
        command_key="todo_list.TodoList.add_todo",
        parameters={"description": "Test todo"},
    )
    todo = todolist_executor.perform_action(add_action)
    assert todo is not None

    # Access the Todo by ID rather than the object directly
    todo_id = todo.id

    # Set current todo to the todo's ID (not the object)
    set_current_action = Action(
        app_folderpath=app_path,
        command_key="todo_list.TodoList.current_todo",
        parameters={"value": todo_id},
    )
    current_todo = todolist_executor.perform_action(set_current_action)
    assert current_todo == todo  # Should return the todo object
    assert CHAT_CONTEXT.current_object == todo_list  # Should still be todo_list

    # Close todo (Todo context)
    # First set the CHAT_CONTEXT.current_object to the todo
    CHAT_CONTEXT.current_object = todo

    close_action = Action(
        app_folderpath=app_path,
        command_key="todo_list.Todo.close",
        parameters={},
    )
    todolist_executor.perform_action(close_action)

    # Check todo state (Todo context)
    state_action = Action(
        app_folderpath=app_path,
        command_key="todo_list.Todo.state",
        parameters={},
    )
    state = todolist_executor.perform_action(state_action)
    assert str(state) == "TodoState.CLOSED"


def test_command_executor_context_switching(
    temp_todo_app: dict[str, Path],
    todolist_executor: CommandExecutor,  # pylint: disable=redefined-outer-name
    _chat_context_reset: Generator[
        ChatContext, None, None
    ],  # pylint: disable=redefined-outer-name
) -> None:
    """Test switching between different contexts during command execution.

    Args:
        temp_todo_app: Fixture providing test module paths
        todolist_executor: Fixture providing configured CommandExecutor
        _chat_context_reset: Fixture providing clean ChatContext instance
    """
    # Initialize todo list (global context)
    app_path = str(temp_todo_app["module_dir"])
    CHAT_CONTEXT.register_app(app_path)
    module_file = str(temp_todo_app["module_file"])

    # Import the module and get the TodoList class directly
    todolist_class: Type[Any] = load_class_from_sysmodules(module_file, "TodoList")
    todo_list = todolist_class()

    CHAT_CONTEXT.current_object = todo_list

    # Add two todos
    add_action1 = Action(
        app_folderpath=app_path,
        command_key="todo_list.TodoList.add_todo",
        parameters={"description": "First todo"},
    )
    todo1 = todolist_executor.perform_action(add_action1)

    add_action2 = Action(
        app_folderpath=app_path,
        command_key="todo_list.TodoList.add_todo",
        parameters={"description": "Second todo"},
    )
    todo2 = todolist_executor.perform_action(add_action2)

    # Set current todo to first todo
    set_current_action = Action(
        app_folderpath=app_path,
        command_key="todo_list.TodoList.current_todo",
        parameters={"value": todo1.id},
    )
    current_todo = todolist_executor.perform_action(set_current_action)
    assert current_todo == todo1  # Should return the todo object

    # Manually set context to todo1 for Todo operations
    CHAT_CONTEXT.current_object = todo1
    assert CHAT_CONTEXT.current_object == todo1

    # Close first todo
    close_action = Action(
        app_folderpath=app_path,
        command_key="todo_list.Todo.close",
        parameters={},
    )
    todolist_executor.perform_action(close_action)

    # Switch to second todo
    CHAT_CONTEXT.current_object = todo_list  # Back to TodoList
    set_current_action = Action(
        app_folderpath=app_path,
        command_key="todo_list.TodoList.current_todo",
        parameters={"value": todo2.id},
    )
    current_todo = todolist_executor.perform_action(set_current_action)
    assert current_todo == todo2

    # Manually set context to todo2 for Todo operations
    CHAT_CONTEXT.current_object = todo2
    assert CHAT_CONTEXT.current_object == todo2

    # Update second todo
    update_action = Action(
        app_folderpath=app_path,
        command_key="todo_list.Todo.description",
        parameters={"value": "Updated second todo"},
    )
    todolist_executor.perform_action(update_action)


def test_command_executor_invalid_context(
    temp_todo_app: dict[str, Path],
    todolist_executor: CommandExecutor,
    _chat_context_reset: Generator[None, None, None],
) -> None:
    """Test error handling when executing commands with invalid contexts."""
    app_path = str(temp_todo_app["module_dir"])
    CHAT_CONTEXT.register_app(app_path)
    module_file = str(temp_todo_app["module_file"])

    # Try to execute a Todo command with no current object
    close_action = Action(
        app_folderpath=app_path,
        command_key="todo_list.Todo.close",
        parameters={},
    )

    print(f"Before action CHAT_CONTEXT.current_object: {CHAT_CONTEXT.current_object}")

    # Test first scenario - no current object should raise ValueError
    with pytest.raises(
        ValueError,
        match="Command 'todo_list.Todo.close' is not available in the current context",
    ):
        todolist_executor.perform_action(close_action)

    # Import the module and get the TodoList class directly
    todolist_class: Type[Any] = load_class_from_sysmodules(module_file, "TodoList")
    todo_list = todolist_class()

    # Test second scenario - wrong context type should raise TypeError
    CHAT_CONTEXT.current_object = todo_list
    with pytest.raises(TypeError):
        todolist_executor.perform_action(close_action)


def test_command_executor_properties(
    temp_todo_app: dict[str, Path],
    todolist_executor: CommandExecutor,  # pylint: disable=redefined-outer-name
    _chat_context_reset: Generator[
        ChatContext, None, None
    ],  # pylint: disable=redefined-outer-name
) -> None:
    """Test handling of property getter and setter commands.

    Args:
        temp_todo_app: Fixture providing test module paths
        todolist_executor: Fixture providing configured CommandExecutor
        _chat_context_reset: Fixture providing clean ChatContext instance
    """
    # Initialize todo list (global context)
    app_path = str(temp_todo_app["module_dir"])
    CHAT_CONTEXT.register_app(app_path)
    module_file = str(temp_todo_app["module_file"])

    # Import the module and get the TodoList class directly
    todolist_class: Type[Any] = load_class_from_sysmodules(module_file, "TodoList")
    todo_list = todolist_class()

    CHAT_CONTEXT.current_object = todo_list

    # Add a todo
    add_action = Action(
        app_folderpath=app_path,
        command_key="todo_list.TodoList.add_todo",
        parameters={"description": "Property test"},
    )
    todo = todolist_executor.perform_action(add_action)

    # Set current todo to the new todo
    set_current_action = Action(
        app_folderpath=app_path,
        command_key="todo_list.TodoList.current_todo",
        parameters={"value": todo.id},
    )
    current_todo = todolist_executor.perform_action(set_current_action)
    assert current_todo == todo

    # Manually set context to todo for Todo operations
    CHAT_CONTEXT.current_object = todo
    assert CHAT_CONTEXT.current_object == todo

    # Get description (property getter)
    get_desc_action = Action(
        app_folderpath=app_path,
        command_key="todo_list.Todo.description",
        parameters={},
    )
    description = todolist_executor.perform_action(get_desc_action)
    assert description == "Property test"

    # Set description (property setter)
    set_desc_action = Action(
        app_folderpath=app_path,
        command_key="todo_list.Todo.description",
        parameters={"value": "Updated property"},
    )
    todolist_executor.perform_action(set_desc_action)

    # Get description again to verify update
    description = todolist_executor.perform_action(get_desc_action)
    assert description == "Updated property"


def test_object_based_property_get(
    temp_todo_app: dict[str, Path],
    todolist_registry: CommandRegistry,  # pylint: disable=redefined-outer-name
    _chat_context_reset: Generator[
        ChatContext, None, None
    ],  # pylint: disable=redefined-outer-name
) -> None:
    """Test getting a property from an object in the current context.

    This test verifies that property getters work correctly when accessing
    properties of an object that is set as the current context object.

    Args:
        temp_todo_app: Fixture providing test module paths
        todolist_registry: Fixture providing registry with todo commands
        _chat_context_reset: Fixture providing clean ChatContext instance
    """
    # Initialize todo list (global context)
    app_path = str(temp_todo_app["module_dir"])
    CHAT_CONTEXT.register_app(app_path)
    module_file = str(temp_todo_app["module_file"])

    # Import the module and get the TodoList class
    todolist_class: Type[Any] = load_class_from_sysmodules(module_file, "TodoList")
    todo_list = todolist_class()

    todo = todo_list.add_todo("Test todo")

    # Set up the appropriate context
    CHAT_CONTEXT.current_object = todo_list

    # Switch context to todo
    CHAT_CONTEXT.current_object = todo

    # Test getting property
    assert todo.description == "Test todo"

    # Test context is maintained
    assert CHAT_CONTEXT.current_object == todo


def test_object_based_property_set(
    temp_todo_app: dict[str, Path],
    todolist_registry: CommandRegistry,  # pylint: disable=redefined-outer-name
    _chat_context_reset: Generator[
        ChatContext, None, None
    ],  # pylint: disable=redefined-outer-name
) -> None:
    """Test setting a property on an object in the current context.

    This test verifies that property setters work correctly when modifying
    properties of an object that is set as the current context object.

    Args:
        temp_todo_app: Fixture providing test module paths
        todolist_registry: Fixture providing registry with todo commands
        _chat_context_reset: Fixture providing clean ChatContext instance
    """
    # Initialize todo list (global context)
    app_path = str(temp_todo_app["module_dir"])
    CHAT_CONTEXT.register_app(app_path)
    module_file = str(temp_todo_app["module_file"])

    # Import the module and get the TodoList class
    todolist_class: Type[Any] = load_class_from_sysmodules(module_file, "TodoList")
    todo_list = todolist_class()

    todo = todo_list.add_todo("Test todo")

    # Set up the appropriate context
    CHAT_CONTEXT.current_object = todo

    # Set the description property
    todo.description = "Updated todo"

    # Verify property was set
    assert todo.description == "Updated todo"

    # Set context to todo_list
    CHAT_CONTEXT.current_object = todo_list

    # Verify context is preserved
    assert CHAT_CONTEXT.current_object == todo_list


def test_method_binding_to_context(
    temp_todo_app: dict[str, Path],
    todolist_registry: CommandRegistry,  # pylint: disable=redefined-outer-name
    _chat_context_reset: Generator[
        ChatContext, None, None
    ],  # pylint: disable=redefined-outer-name
) -> None:
    """Test method binding to the current context object.

    This test verifies that methods can be properly bound and executed on
    the object that is set as the current context, and that the context
    is maintained after method execution.

    Args:
        temp_todo_app: Fixture providing test module paths
        todolist_registry: Fixture providing registry with todo commands
        _chat_context_reset: Fixture providing clean ChatContext instance
    """
    # Initialize todo list (global context)
    app_path = str(temp_todo_app["module_dir"])
    CHAT_CONTEXT.register_app(app_path)
    module_file = str(temp_todo_app["module_file"])

    # Import the module and get the TodoList class
    todolist_class: Type[Any] = load_class_from_sysmodules(module_file, "TodoList")
    todo_list = todolist_class()

    _ = todo_list.add_todo("Test todo")

    # Set up the context
    CHAT_CONTEXT.current_object = todo_list

    # Call method on context object
    new_todo = todo_list.add_todo("Another todo")

    # Verify method worked
    assert new_todo is not None
    assert new_todo.description == "Another todo"

    # Verify context is maintained
    assert CHAT_CONTEXT.current_object == todo_list


def test_method_binding_to_different_context(
    temp_todo_app: dict[str, Path],
    todolist_registry: CommandRegistry,  # pylint: disable=redefined-outer-name
    _chat_context_reset: Generator[
        ChatContext, None, None
    ],  # pylint: disable=redefined-outer-name
) -> None:
    """Test method binding when switching between different context objects.

    This test verifies that when the current context is changed to a different object,
    methods are correctly bound to the new context object and can be executed properly.
    It also checks that the context is maintained after method execution.

    Args:
        temp_todo_app: Fixture providing test module paths
        todolist_registry: Fixture providing registry with todo commands
        _chat_context_reset: Fixture providing clean ChatContext instance
    """
    # Initialize todo list (global context)
    app_path = str(temp_todo_app["module_dir"])
    CHAT_CONTEXT.register_app(app_path)
    module_file = str(temp_todo_app["module_file"])

    # Import the module and get the TodoList class
    todolist_class: Type[Any] = load_class_from_sysmodules(module_file, "TodoList")
    todo_list = todolist_class()

    todo = todo_list.add_todo("Test todo")

    # Set up the context to a different object
    CHAT_CONTEXT.current_object = todo

    # Call method on the todo object
    todo.close()

    # Verify method had effect
    assert str(todo.state) == "TodoState.CLOSED"

    # Verify context is maintained
    assert CHAT_CONTEXT.current_object == todo


def test_context_specific_method_binding(
    temp_todo_app: dict[str, Path],
    todolist_registry: CommandRegistry,  # pylint: disable=redefined-outer-name
    _chat_context_reset: Generator[
        ChatContext, None, None
    ],  # pylint: disable=redefined-outer-name
) -> None:
    # sourcery skip: extract-duplicate-method
    """Test method binding when switching between different context objects multiple times.

    This test verifies that methods are correctly bound to the appropriate context object
    when switching between different objects multiple times. It ensures that the context
    is properly maintained after each method execution and that methods execute on the
    correct object regardless of how many context switches have occurred.

    Args:
        temp_todo_app: Fixture providing test module paths
        todolist_registry: Fixture providing registry with todo commands
        _chat_context_reset: Fixture providing clean ChatContext instance
    """
    # Initialize todo list (global context)
    app_path = str(temp_todo_app["module_dir"])
    CHAT_CONTEXT.register_app(app_path)
    module_file = str(temp_todo_app["module_file"])

    # Import the module and get the TodoList class
    todolist_class: Type[Any] = load_class_from_sysmodules(module_file, "TodoList")
    todo_list = todolist_class()

    todo = todo_list.add_todo("Test todo")

    # Set the context to the list
    CHAT_CONTEXT.current_object = todo_list

    # Call method on todo_list
    new_todo = todo_list.add_todo("New context todo")
    assert new_todo.description == "New context todo"

    # Change context to the todo
    CHAT_CONTEXT.current_object = todo

    # Call method on todo
    todo.close()
    assert str(todo.state) == "TodoState.CLOSED"

    # Change back to list context
    CHAT_CONTEXT.current_object = todo_list

    # Call another method on todo_list
    third_todo = todo_list.add_todo("Third todo")
    assert third_todo.description == "Third todo"
    assert CHAT_CONTEXT.current_object == todo_list


def test_add_conversation(_chat_context_reset: None) -> None:
    """Test adding conversation entries."""
    # Add a simple conversation
    CHAT_CONTEXT.append_to_conversation_history("Hello", "Hi there")
    history = CHAT_CONTEXT.get_conversation_history()
    assert len(history) == 1
    entry: ConversationEntry = ("Hello", "Hi there", None)
    assert history[0] == entry

    # Add a conversation with artifacts
    artifacts = ConversationArtifacts(data={"timestamp": 123456789})
    CHAT_CONTEXT.append_to_conversation_history("How are you?", "I'm good!", artifacts)
    history = CHAT_CONTEXT.get_conversation_history()
    assert len(history) == 2
    entry_with_artifacts: ConversationEntry = ("How are you?", "I'm good!", artifacts)
    assert history[1] == entry_with_artifacts


def test_conversation_history_with_limit(_chat_context_reset: None) -> None:
    """Test retrieving limited conversation history."""
    # Add multiple conversations
    conversations: list[tuple[str, str]] = [
        ("Q1", "R1"),
        ("Q2", "R2"),
        ("Q3", "R3"),
        ("Q4", "R4"),
    ]
    for q, r in conversations:
        CHAT_CONTEXT.append_to_conversation_history(q, r)

    # Test getting all history
    history: list[ConversationEntry] = CHAT_CONTEXT.get_conversation_history()
    assert len(history) == 4

    # Test getting last 2 items
    history = CHAT_CONTEXT.get_conversation_history(last_n=2)
    assert len(history) == 2
    expected: list[ConversationEntry] = [("Q3", "R3", None), ("Q4", "R4", None)]
    assert history == expected


def test_clear_conversation_history(_chat_context_reset: ChatContext) -> None:
    """Test clearing conversation history.

    Args:
        _chat_context_reset: Fixture providing clean ChatContext instance
    """
    context = ChatContext()

    # Add some conversations
    context.append_to_conversation_history("Q1", "R1")
    context.append_to_conversation_history("Q2", "R2")
    assert len(context.get_conversation_history()) == 2

    # Clear history
    context.clear_conversation_history()
    assert len(context.get_conversation_history()) == 0


def test_app_context_getter_setter(
    temp_todo_app: dict[str, Path], _chat_context_reset: None
) -> None:
    """Test the app_context getter and setter functionality."""
    app_path = str(temp_todo_app["module_dir"])
    CHAT_CONTEXT.register_app(app_path)

    # Initially app_context should be empty
    assert not CHAT_CONTEXT.app_context

    # Set app_context to a test dictionary
    test_context = {"key1": "value1", "key2": 42}
    CHAT_CONTEXT.app_context = test_context

    # Get the AppContext instance
    app_ctx = CHAT_CONTEXT.app_context
    assert isinstance(app_ctx, dict)
    assert app_ctx == test_context


def test_app_context_no_current_app(
    _chat_context_reset: Generator[
        ChatContext, None, None
    ]  # pylint: disable=redefined-outer-name
) -> None:
    """Test app_context errors when no current app is set.

    Args:
        _chat_context_reset: Fixture providing clean ChatContext instance
    """
    context = ChatContext()

    # Explicitly reset current_app_folderpath to None
    # pylint: disable=protected-access
    context._current_app_folderpath = None

    # Test the getter
    with pytest.raises(ValueError, match="No current application folder path is set"):
        _ = context.app_context

    # Test the setter
    with pytest.raises(ValueError, match="No current application folder path is set"):
        context.app_context = {"key": "value"}


def test_app_context_multiple_apps(
    _chat_context_reset: Generator[
        ChatContext, None, None
    ]  # pylint: disable=redefined-outer-name
) -> None:
    """Test app_context with multiple registered apps.

    Args:
        _chat_context_reset: Fixture providing clean ChatContext instance
    """
    context = ChatContext()

    # Register two apps
    app_path1 = "./examples/todo_list"
    app_path2 = "./examples/calculator"
    context.register_app(app_path1)
    context.register_app(app_path2)

    # Set current app to first app
    context.current_app_folderpath = app_path1
    context1 = {"app1": "data"}
    context.app_context = context1

    # Switch to second app
    context.current_app_folderpath = app_path2
    context2 = {"app2": "data"}
    context.app_context = context2

    # Verify app contexts are stored separately
    assert context.app_context == context2

    # Switch back to first app and verify context is preserved
    context.current_app_folderpath = app_path1
    assert context.app_context == context1
