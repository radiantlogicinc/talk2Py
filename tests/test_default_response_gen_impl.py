"""Tests for default response generation implementation."""

import os
from unittest import mock

import pytest

from talk2py import Action
from talk2py.nlu_pipeline.default_response_generation import DefaultResponseGeneration


@pytest.fixture
def mock_env_vars():
    """Fixture to mock environment variables (if needed, otherwise remove)."""
    with mock.patch.dict(os.environ, {"TEST_VAR": "test_value"}):
        yield


# Fixture for mocking dspy.Predict (removed as dspy isn't used)
# @pytest.fixture
# def mock_dspy_predict():
#     """Fixture to mock dspy.Predict."""
#     with mock.patch("dspy.Predict") as mock_predict:
#         # Configure mock behavior if needed (e.g., return value)
#         mock_predict.return_value.return_value = mock.Mock(generated_response="Generated response")
#         yield mock_predict


def test_generate_response_text_success():
    """Test successful response generation."""
    response_gen = DefaultResponseGeneration()
    command = "add 2 and 3"
    execution_results = {"status": "success", "message": "Result is 5"}

    response = response_gen.generate_response_text(command, execution_results)

    expected_response = "Command 'add 2 and 3' executed successfully. Result is 5"
    assert response == expected_response


def test_generate_response_text_failure_with_message():
    """Test failure response generation with a specific message."""
    response_gen = DefaultResponseGeneration()
    command = "divide by zero"
    execution_results = {"status": "error", "message": "Division by zero"}

    response = response_gen.generate_response_text(command, execution_results)
    expected_response = "Command 'divide by zero' failed. Error: Division by zero"
    assert response == expected_response


def test_generate_response_text_failure_unknown_error():
    """Test failure response generation with no specific message."""
    response_gen = DefaultResponseGeneration()
    command = "unknown command"
    execution_results = {"status": "error"}

    response = response_gen.generate_response_text(command, execution_results)
    expected_response = "Command 'unknown command' failed. Error: Unknown error"
    assert response == expected_response


def test_get_supplementary_prompt_instructions():
    """Test getting supplementary prompt instructions."""
    response_gen = DefaultResponseGeneration()
    result = response_gen.get_supplementary_prompt_instructions("test.command")

    # Default implementation returns an empty string
    assert result == ""


@pytest.fixture
def mock_registry():
    """Create a mock registry for testing."""
    registry = mock.MagicMock()
    command_func = mock.MagicMock()
    command_func.return_value = {"result": "command executed"}
    registry.get_command_func.return_value = command_func
    return registry


def test_execute_code_success(mock_registry):
    """Test successful execution of a command."""
    response_gen = DefaultResponseGeneration()
    response_gen.command_registry = mock_registry

    action = mock.MagicMock(spec=Action)
    action.command_key = "test.command"
    action.parameters = {"param1": "value1"}
    action.app_folderpath = "/mock/app/path"

    result = response_gen.execute_code(action)

    assert result == {"result": "command executed"}
    mock_registry.get_command_func.assert_called_once_with(
        action.command_key, None, action.parameters
    )


def test_execute_code_no_command_func():
    """Test execute_code when no command function is found."""
    response_gen = DefaultResponseGeneration()
    mock_registry = mock.MagicMock()
    mock_registry.get_command_func.return_value = None
    response_gen.command_registry = mock_registry

    action = mock.MagicMock(spec=Action)
    action.command_key = "test.command"
    action.parameters = {"param1": "value1"}
    action.app_folderpath = "/mock/app/path"

    with pytest.raises(ValueError, match="Command implementation function not found"):
        response_gen.execute_code(action)


def test_execute_code_none_result():
    """Test execute_code when command function returns None."""
    response_gen = DefaultResponseGeneration()
    mock_registry = mock.MagicMock()
    command_func = mock.MagicMock()
    command_func.return_value = None
    mock_registry.get_command_func.return_value = command_func
    response_gen.command_registry = mock_registry

    action = mock.MagicMock(spec=Action)
    action.command_key = "test.command"
    action.parameters = {"param1": "value1"}
    action.app_folderpath = "/mock/app/path"

    result = response_gen.execute_code(action)

    assert result == {"status": "success"}
