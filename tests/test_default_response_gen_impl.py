"""Tests for default response generation implementation."""

import os
from unittest import mock

import pytest

from talk2py.default_response_generation import DefaultResponseGeneration


@pytest.fixture
def mock_env_vars():
    """Set up mock environment variables for testing."""
    with mock.patch.dict(
        os.environ, {"LLM": "openai/gpt-3.5-turbo", "LITELLM_API_KEY": "test-key"}
    ):
        yield


@pytest.fixture
def mock_dspy_predict():
    """Mock DSPy's Predict class."""
    with mock.patch("dspy.Predict") as mock_predict:
        # Configure the mock to return a prediction object
        prediction = mock.MagicMock()
        prediction.result_summary = "Generated response"
        mock_predict.return_value.return_value = prediction
        yield mock_predict


# pylint: disable=redefined-outer-name
def test_generate_response_success(
    mock_env_vars, mock_dspy_predict
):  # pylint: disable=unused-argument
    """Test successful response generation."""
    response_gen = DefaultResponseGeneration()
    command = "add 2 and 3"
    execution_results = {"result": "5"}

    response = response_gen.generate_response(command, execution_results)

    assert response == "Generated response"
    mock_dspy_predict.assert_called_once_with(
        "command, execution_results -> result_summary"
    )
    mock_dspy_predict.return_value.assert_called_once_with(
        command=command, execution_results=execution_results
    )


def test_generate_response_missing_env_vars():
    """Test response generation with missing environment variables."""
    response_gen = DefaultResponseGeneration()
    command = "add 2 and 3"
    execution_results = {"result": "5"}

    with mock.patch.dict(os.environ, {}, clear=True):  # Clear all env vars
        with pytest.raises(Exception):
            response_gen.generate_response(command, execution_results)


# pylint: disable=redefined-outer-name
def test_generate_response_dspy_error(mock_env_vars):  # pylint: disable=unused-argument
    """Test handling of DSPy errors."""
    response_gen = DefaultResponseGeneration()
    command = "add 2 and 3"
    execution_results = {"result": "5"}

    with mock.patch("dspy.Predict", side_effect=Exception("DSPy error")):
        with pytest.raises(Exception, match="DSPy error"):
            response_gen.generate_response(command, execution_results)
