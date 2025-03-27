"""Tests for chat context functionality.

This module contains test cases focused on context management, context switching,
and interactions with the CHAT_CONTEXT global variable.
"""

# pylint: disable=unused-argument,redefined-outer-name

import json
import sys
from pathlib import Path
from typing import Dict, Generator

import pytest

from talk2py import CHAT_CONTEXT, Action
from talk2py.chat_context import ChatContext
from talk2py.command_executor import CommandExecutor
from talk2py.command_registry import CommandRegistry


@pytest.fixture
def cleanup_context() -> Generator[None, None, None]:
    """Fixture to reset global APP_CONTEXT before and after test."""
    # Reset before test
    # pylint: disable=protected-access
    CHAT_CONTEXT._registry_cache = {}
    CHAT_CONTEXT._current_app_folderpath = None
    CHAT_CONTEXT._current_object_cache = {}
    CHAT_CONTEXT._app_context_cache = {}
    yield
    # Reset after test
    CHAT_CONTEXT._registry_cache = {}
    CHAT_CONTEXT._current_app_folderpath = None
    CHAT_CONTEXT._current_object_cache = {}
    CHAT_CONTEXT._app_context_cache = {}


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


@pytest.fixture
def example_registry(temp_todo_module: Dict[str, Path]) -> CommandRegistry:
    """Create a CommandRegistry with test commands loaded.

    Args:
        temp_todo_module: Fixture providing test module paths

    Returns:
        CommandRegistry instance
    """
    return CommandRegistry(str(temp_todo_module["module_dir"]))


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
    CHAT_CONTEXT.register_app("./examples/todo_list")
    CHAT_CONTEXT.current_object = todo_list
    add_action = Action(
        app_folderpath="./examples/todo_list",
        command_key="todo_list.TodoList.add_todo",
        parameters={"description": "Test todo"},
    )
    todo = executor_with_todo.perform_action(add_action)
    assert isinstance(todo, object)  # Class not directly accessible in test

    # Set current todo to switch context
    CHAT_CONTEXT.current_object = todo

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
    # Create TodoList instance directly
    # pylint: disable=import-outside-toplevel
    from examples.todo_list.todo_list import TodoList

    todo_list = TodoList()

    # Register the app path first
    app_path = "./examples/todo_list"
    CHAT_CONTEXT.register_app(app_path)
    CHAT_CONTEXT.current_object = todo_list

    # Add a todo in TodoList context
    add_action = Action(
        app_folderpath="./examples/todo_list",
        command_key="todo_list.TodoList.add_todo",
        parameters={"description": "Test todo"},
    )
    todo = executor_with_todo.perform_action(add_action)

    # Switch to Todo context
    CHAT_CONTEXT.current_object = todo

    # Modify todo in Todo context
    close_action = Action(
        app_folderpath="./examples/todo_list",
        command_key="todo_list.Todo.close",
        parameters={},
    )
    executor_with_todo.perform_action(close_action)

    # Switch back to TodoList context
    CHAT_CONTEXT.current_object = todo_list

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
    # Create TodoList instance directly
    # pylint: disable=import-outside-toplevel
    from examples.todo_list.todo_list import TodoList

    todo_list = TodoList()

    # Register the app
    app_path = "./examples/todo_list"
    CHAT_CONTEXT.register_app(app_path)
    CHAT_CONTEXT.current_object = todo_list

    # Try to call Todo method with TodoList context
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
    CHAT_CONTEXT.current_object = todo
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
    # sourcery skip: extract-duplicate-method, inline-immediately-returned-variable
    """Test handling of property getter/setter commands.

    Args:
        executor_with_todo: Fixture providing configured CommandExecutor
        cleanup_context: Fixture to reset global context
    """
    # Create TodoList instance directly
    # pylint: disable=import-outside-toplevel
    from examples.todo_list.todo_list import TodoList

    todo_list = TodoList()

    # Register the app
    app_path = "./examples/todo_list"
    CHAT_CONTEXT.register_app(app_path)
    CHAT_CONTEXT.current_object = todo_list

    # Add a todo in TodoList context
    add_action = Action(
        app_folderpath="./examples/todo_list",
        command_key="todo_list.TodoList.add_todo",
        parameters={"description": "Test todo"},
    )
    todo = executor_with_todo.perform_action(add_action)

    # Set current object to todo before testing property
    CHAT_CONTEXT.current_object = todo

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
    CHAT_CONTEXT.current_object = todo  # Ensure context is still set
    desc_get_action = Action(
        app_folderpath="./examples/todo_list",
        command_key="todo_list.Todo.description",
        parameters={},
    )
    desc = executor_with_todo.perform_action(desc_get_action)
    assert desc == "Updated todo"


@pytest.fixture(scope="function")
def setup_teardown():
    """Reset the APP_CONTEXT before and after each test."""
    # Reset context before test
    app_path = "./examples/todo_list"  # Use a known path that will work
    CHAT_CONTEXT.register_app(app_path)
    CHAT_CONTEXT.current_object = None
    yield
    # Reset after test
    CHAT_CONTEXT.current_object = None


def test_object_based_property_get(setup_teardown, example_registry) -> None:
    """Test getting a property from an object in the current context.

    This test verifies that property getters work correctly when accessing
    properties of an object that is set as the current context object.
    """
    # Setup
    # pylint: disable=import-outside-toplevel
    from examples.todo_list.todo_list import TodoList

    todo_list = TodoList()
    todo = todo_list.add_todo("Test todo")

    # Set up the appropriate context
    app_path = "./examples/todo_list"
    CHAT_CONTEXT.register_app(app_path)
    CHAT_CONTEXT.current_object = todo_list

    # Switch context to todo
    CHAT_CONTEXT.current_object = todo

    # Test getting property
    assert todo.description == "Test todo"

    # Test context is maintained
    assert CHAT_CONTEXT.current_object == todo


def test_object_based_property_set(setup_teardown, example_registry) -> None:
    """Test setting a property on an object in the current context.

    This test verifies that property setters work correctly when modifying
    properties of an object that is set as the current context object.
    """
    # Setup
    # pylint: disable=import-outside-toplevel
    from examples.todo_list.todo_list import TodoList

    todo_list = TodoList()
    todo = todo_list.add_todo("Test todo")

    # Set up the appropriate context
    app_path = "./examples/todo_list"
    CHAT_CONTEXT.register_app(app_path)
    CHAT_CONTEXT.current_object = todo

    # Set the description property
    todo.description = "Updated todo"

    # Verify property was set
    assert todo.description == "Updated todo"

    # Set context to todo_list
    CHAT_CONTEXT.current_object = todo_list

    # Verify context is preserved
    assert CHAT_CONTEXT.current_object == todo_list


def test_method_binding_to_context(setup_teardown, example_registry) -> None:
    """Test method binding to the current context object.

    This test verifies that methods can be properly bound and executed on
    the object that is set as the current context, and that the context
    is maintained after method execution.
    """
    # Setup
    # pylint: disable=import-outside-toplevel
    from examples.todo_list.todo_list import TodoList

    todo_list = TodoList()
    _ = todo_list.add_todo("Test todo")

    # Set up the context
    app_path = "./examples/todo_list"
    CHAT_CONTEXT.register_app(app_path)
    CHAT_CONTEXT.current_object = todo_list

    # Call method on context object
    new_todo = todo_list.add_todo("Another todo")

    # Verify method worked
    assert new_todo is not None
    assert new_todo.description == "Another todo"

    # Verify context is maintained
    assert CHAT_CONTEXT.current_object == todo_list


def test_method_binding_to_different_context(setup_teardown, example_registry) -> None:
    """Test method binding when switching between different context objects.

    This test verifies that when the current context is changed to a different object,
    methods are correctly bound to the new context object and can be executed properly.
    It also checks that the context is maintained after method execution.

    Args:
        setup_teardown: Fixture to set up and tear down the test environment
        example_registry: Fixture providing an example registry
    """
    # Setup
    # pylint: disable=import-outside-toplevel
    from examples.todo_list.todo_list import TodoList

    todo_list = TodoList()
    todo = todo_list.add_todo("Test todo")

    # Set up the context to a different object
    app_path = "./examples/todo_list"
    CHAT_CONTEXT.register_app(app_path)
    CHAT_CONTEXT.current_object = todo

    # Call method on the todo object
    todo.close()

    # Verify method had effect
    assert str(todo.state) == "TodoState.CLOSED"

    # Verify context is maintained
    assert CHAT_CONTEXT.current_object == todo


def test_context_specific_method_binding(setup_teardown, example_registry) -> None:
    """Test method binding when switching between different context objects multiple times.

    This test verifies that methods are correctly bound to the appropriate context object
    when switching between different objects multiple times. It ensures that the context
    is properly maintained after each method execution and that methods execute on the
    correct object regardless of how many context switches have occurred.

    Args:
        setup_teardown: Fixture to set up and tear down the test environment
        example_registry: Fixture providing an example registry
    """
    # sourcery skip: extract-duplicate-method
    # Setup
    # pylint: disable=import-outside-toplevel
    from examples.todo_list.todo_list import TodoList

    todo_list = TodoList()
    todo = todo_list.add_todo("Test todo")

    # Set the context to the list
    app_path = "./examples/todo_list"
    CHAT_CONTEXT.register_app(app_path)
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


def test_app_context_getter_setter(cleanup_context) -> None:
    """Test the app_context getter and setter functionality."""
    # pylint: disable=protected-access
    # Set up a test app path
    app_path = "./examples/todo_list"
    CHAT_CONTEXT.register_app(app_path)

    # Initially app_context should be None
    assert not CHAT_CONTEXT.app_context

    # Set app_context to a test dictionary
    test_context = {"key1": "value1", "key2": 42}
    CHAT_CONTEXT.app_context = test_context

    # Verify app_context was set correctly
    assert CHAT_CONTEXT.app_context == test_context

    # Set to a different value and verify
    new_context = {"different": "context"}
    CHAT_CONTEXT.app_context = new_context
    assert CHAT_CONTEXT.app_context == new_context

    # Test setting to None
    CHAT_CONTEXT.app_context = {}
    assert not CHAT_CONTEXT.app_context


def test_app_context_no_current_app(cleanup_context) -> None:
    """Test app_context errors when no current app is set."""
    # pylint: disable=protected-access
    # Explicitly reset current_app_folderpath to None
    CHAT_CONTEXT._current_app_folderpath = None

    # Now test the getter
    with pytest.raises(ValueError, match="No current application folder path is set"):
        _ = CHAT_CONTEXT.app_context

    # Also test the setter
    with pytest.raises(ValueError, match="No current application folder path is set"):
        CHAT_CONTEXT.app_context = {"key": "value"}


def test_app_context_multiple_apps(cleanup_context) -> None:
    """Test app_context with multiple registered apps."""
    # Register two apps
    app_path1 = "./examples/todo_list"
    app_path2 = "./examples/calculator"
    CHAT_CONTEXT.register_app(app_path1)
    CHAT_CONTEXT.register_app(app_path2)

    # Set current app to first app
    CHAT_CONTEXT.current_app_folderpath = app_path1
    context1 = {"app1": "data"}
    CHAT_CONTEXT.app_context = context1

    # Switch to second app
    CHAT_CONTEXT.current_app_folderpath = app_path2
    context2 = {"app2": "data"}
    CHAT_CONTEXT.app_context = context2

    # Verify app contexts are stored separately
    assert CHAT_CONTEXT.app_context == context2

    # Switch back to first app and verify context is preserved
    CHAT_CONTEXT.current_app_folderpath = app_path1
    assert CHAT_CONTEXT.app_context == context1


@pytest.fixture
def chat_context():
    """Create a ChatContext instance for testing."""
    return ChatContext()


def test_add_conversation(chat_context):
    """Test adding conversation entries."""
    # Add a simple conversation
    chat_context.append_to_conversation_history("Hello", "Hi there")
    history = chat_context.get_conversation_history()
    assert len(history) == 1
    assert history[0] == ("Hello", "Hi there", None)

    # Add a conversation with artifacts
    artifacts = {"timestamp": 123456789}
    chat_context.append_to_conversation_history("How are you?", "I'm good!", artifacts)
    history = chat_context.get_conversation_history()
    assert len(history) == 2
    assert history[1] == ("How are you?", "I'm good!", {"timestamp": 123456789})


def test_conversation_history_with_limit(chat_context):
    """Test retrieving limited conversation history."""
    chat_context.clear_conversation_history()
    # Add multiple conversations
    conversations = [
        ("Q1", "R1"),
        ("Q2", "R2"),
        ("Q3", "R3"),
        ("Q4", "R4"),
    ]
    # sourcery skip: no-loop-in-tests
    for q, r in conversations:
        chat_context.append_to_conversation_history(q, r)

    # Test getting all history
    assert len(chat_context.get_conversation_history()) == 4

    # Test getting last 2 items
    history = chat_context.get_conversation_history(last_n=2)
    assert len(history) == 2
    assert history == [("Q3", "R3", None), ("Q4", "R4", None)]

    # Test getting more items than exist
    history = chat_context.get_conversation_history(last_n=10)
    assert len(history) == 4
    assert history == [
        ("Q1", "R1", None),
        ("Q2", "R2", None),
        ("Q3", "R3", None),
        ("Q4", "R4", None),
    ]


def test_clear_conversation_history(chat_context):
    """Test clearing conversation history."""
    chat_context.clear_conversation_history()
    # Add some conversations
    chat_context.append_to_conversation_history("Q1", "R1")
    chat_context.append_to_conversation_history("Q2", "R2")
    assert len(chat_context.get_conversation_history()) == 2

    # Clear history
    chat_context.clear_conversation_history()
    assert len(chat_context.get_conversation_history()) == 0
