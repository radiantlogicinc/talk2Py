"""Tests for default response generation implementation."""

from unittest import mock

import pytest

import talk2py  # Required for CHAT_CONTEXT manipulation
from talk2py import Action
from talk2py.nlu_pipeline.default_response_generation import DefaultResponseGeneration
from talk2py.code_parsing.command_registry import CommandRegistry

# Assuming conftest.py provides these fixtures:
# - todolist_registry: A CommandRegistry instance loaded with todo_list metadata
# - temp_todo_app: A dict containing app_folderpath, todo_list_instance, todo1, etc.


def test_generate_response_text_success():
    """Test successful response generation text formatting."""
    response_gen = DefaultResponseGeneration()
    command_key = "todo_list.TodoList.add_todo"
    execution_results = {"status": "success", "message": "Added new todo"}

    response = response_gen.generate_response_text(command_key, execution_results)

    expected_response = (
        "Command 'todo_list.TodoList.add_todo' executed successfully. Added new todo"
    )
    assert response == expected_response


def test_generate_response_text_failure_with_message():
    """Test failure response generation text formatting with a specific message."""
    response_gen = DefaultResponseGeneration()
    command_key = "todo_list.TodoList.get_todo"
    execution_results = {"status": "error", "message": "Todo ID 99 not found"}

    response = response_gen.generate_response_text(command_key, execution_results)
    expected_response = (
        "Command 'todo_list.TodoList.get_todo' failed. Error: Todo ID 99 not found"
    )
    assert response == expected_response


def test_generate_response_text_failure_unknown_error():
    """Test failure response generation text formatting with no specific message."""
    response_gen = DefaultResponseGeneration()
    command_key = "unknown.command"
    execution_results = {"status": "error"}

    response = response_gen.generate_response_text(command_key, execution_results)
    expected_response = "Command 'unknown.command' failed. Error: Unknown error"
    assert response == expected_response


def test_get_supplementary_prompt_instructions():
    """Test getting supplementary prompt instructions (default is empty)."""
    response_gen = DefaultResponseGeneration()
    result = response_gen.get_supplementary_prompt_instructions("test.command")
    assert result == ""


# --- Tests for execute_code --- #


def test_execute_code_success_class_method(
    todolist_registry: CommandRegistry, temp_todo_app: dict
):
    """Test successful execution of a class method via execute_code."""
    response_gen = DefaultResponseGeneration(command_registry=todolist_registry)
    app_path = temp_todo_app["app_folderpath"]
    todo_list = temp_todo_app["todo_list_instance"]

    action = Action(
        app_folderpath=app_path,
        command_key="todo_list.TodoList.add_todo",
        parameters={"description": "Test via execute_code"},
    )

    # Set context
    talk2py.CHAT_CONTEXT.register_app(app_path)
    talk2py.CHAT_CONTEXT.current_object = todo_list

    result = response_gen.execute_code(action)

    # Result should be the new Todo object, converted to dict[str, str]
    assert "result" in result
    # Weak check as exact string conversion depends on Todo.__str__ or default repr
    assert "Test via execute_code" in result["result"]
    # Verify side effect
    assert any(t.description == "Test via execute_code" for t in todo_list._todos)


def test_execute_code_success_property_getter(
    todolist_registry: CommandRegistry, temp_todo_app: dict
):
    """Test successful execution of a property getter."""
    response_gen = DefaultResponseGeneration(command_registry=todolist_registry)
    app_path = temp_todo_app["app_folderpath"]
    todo1 = temp_todo_app["todo1"]

    action = Action(
        app_folderpath=app_path,
        command_key="todo_list.Todo.description",  # Get description property
        parameters={},
    )

    talk2py.CHAT_CONTEXT.register_app(app_path)
    talk2py.CHAT_CONTEXT.current_object = todo1  # Context is the specific todo

    result = response_gen.execute_code(action)

    assert result == {
        "result": todo1.description
    }  # Should return the description string


def test_execute_code_success_property_setter(
    todolist_registry: CommandRegistry, temp_todo_app: dict
):
    """Test successful execution of a property setter."""
    response_gen = DefaultResponseGeneration(command_registry=todolist_registry)
    app_path = temp_todo_app["app_folderpath"]
    todo1 = temp_todo_app["todo1"]
    original_desc = todo1.description

    action = Action(
        app_folderpath=app_path,
        command_key="todo_list.Todo.description",
        parameters={"value": "Updated Description via execute_code"},
    )

    talk2py.CHAT_CONTEXT.register_app(app_path)
    talk2py.CHAT_CONTEXT.current_object = todo1

    result = response_gen.execute_code(action)

    assert result == {"status": "success"}  # Setters return None -> success status
    assert todo1.description == "Updated Description via execute_code"

    # Cleanup: restore original description
    todo1.description = original_desc


def test_execute_code_success_with_instantiation(
    todolist_registry: CommandRegistry, temp_todo_app: dict
):
    """Test execute_code successfully instantiating a class parameter."""
    response_gen = DefaultResponseGeneration(command_registry=todolist_registry)
    app_path = temp_todo_app["app_folderpath"]
    todo_list = temp_todo_app["todo_list_instance"]

    # Load Todo class for type checking result
    # todo_module_path = os.path.join(app_path, "todo_list.py") # Now unused
    # TodoClass = load_class_from_sysmodules(todo_module_path, "Todo") # Removed unused variable

    todo_dict = {"description": "Instantiated Todo", "_state": "active"}
    action = Action(
        app_folderpath=app_path,
        command_key="todo_list.TodoList.add_todo_using_todo_obj",
        parameters={"todo_obj": todo_dict},
    )

    talk2py.CHAT_CONTEXT.register_app(app_path)
    talk2py.CHAT_CONTEXT.current_object = todo_list

    result = response_gen.execute_code(action)

    assert "result" in result
    # Check if the string representation matches an instantiated object
    # This is fragile, depends on Todo.__str__/repr
    assert "Instantiated Todo" in result["result"]
    # Verify side effect - a Todo with this description should be in the list
    assert any(t.description == "Instantiated Todo" for t in todo_list._todos)


def test_execute_code_error_no_command_func(
    todolist_registry: CommandRegistry, temp_todo_app: dict
):
    """Test execute_code raises ValueError when command function is not found."""
    response_gen = DefaultResponseGeneration(command_registry=todolist_registry)
    action = Action(
        app_folderpath=temp_todo_app["app_folderpath"],
        command_key="nonexistent.command",
        parameters={},
    )

    with pytest.raises(ValueError, match="Command function could not be resolved"):
        response_gen.execute_code(action)


def test_execute_code_error_needs_context(
    todolist_registry: CommandRegistry, temp_todo_app: dict
):
    """Test execute_code raises ValueError when class method called without context."""
    response_gen = DefaultResponseGeneration(command_registry=todolist_registry)
    app_path = temp_todo_app["app_folderpath"]
    action = Action(
        app_folderpath=app_path,
        command_key="todo_list.TodoList.add_todo",  # Class method needs context
        parameters={"description": "Test no context"},
    )

    talk2py.CHAT_CONTEXT.register_app(app_path)
    talk2py.CHAT_CONTEXT.current_object = None  # Explicitly no context

    with pytest.raises(ValueError, match="requires context"):
        response_gen.execute_code(action)


def test_execute_code_error_instantiation_failure(
    todolist_registry: CommandRegistry, temp_todo_app: dict
):
    """Test execute_code raises ValueError on parameter instantiation failure."""
    response_gen = DefaultResponseGeneration(command_registry=todolist_registry)
    app_path = temp_todo_app["app_folderpath"]
    todo_list = temp_todo_app["todo_list_instance"]

    bad_todo_dict = {"wrong_key": "Bad data"}
    action = Action(
        app_folderpath=app_path,
        command_key="todo_list.TodoList.add_todo_using_todo_obj",
        parameters={"todo_obj": bad_todo_dict},
    )

    talk2py.CHAT_CONTEXT.register_app(app_path)
    talk2py.CHAT_CONTEXT.current_object = todo_list

    with pytest.raises(ValueError, match="Failed to instantiate parameter"):
        response_gen.execute_code(action)


def test_execute_code_error_from_command(
    todolist_registry: CommandRegistry, temp_todo_app: dict
):
    """Test execute_code raises ValueError when the command itself raises ValueError."""
    response_gen = DefaultResponseGeneration(command_registry=todolist_registry)
    app_path = temp_todo_app["app_folderpath"]
    todo_list = temp_todo_app["todo_list_instance"]

    action = Action(
        app_folderpath=app_path,
        command_key="todo_list.TodoList.get_todo",  # This can raise ValueError
        parameters={"todo_id": 999},  # Non-existent ID
    )

    talk2py.CHAT_CONTEXT.register_app(app_path)
    talk2py.CHAT_CONTEXT.current_object = todo_list

    # Should catch the ValueError from get_todo and wrap it
    with pytest.raises(ValueError, match="Error executing command"):
        response_gen.execute_code(action)


# Optional: Test for unexpected runtime errors (requires mocking)
@mock.patch("talk2py.code_parsing.command_registry.CommandRegistry.get_command_func")
def test_execute_code_unexpected_runtime_error(
    mock_get_func, todolist_registry: CommandRegistry, temp_todo_app: dict
):
    """Test execute_code raises RuntimeError on unexpected errors during command execution."""
    # Configure the mock function returned by get_command_func to raise an error
    mock_command = mock.Mock()
    mock_command.side_effect = TypeError("Something unexpected broke")
    mock_get_func.return_value = mock_command

    # Use the real registry initially, but get_command_func is mocked
    response_gen = DefaultResponseGeneration(command_registry=todolist_registry)
    action = Action(
        app_folderpath=temp_todo_app["app_folderpath"],
        command_key="some.command",  # Key doesn't matter as get_command_func is mocked
        parameters={},
    )

    with pytest.raises(RuntimeError, match="Unexpected error executing command"):
        response_gen.execute_code(action)
