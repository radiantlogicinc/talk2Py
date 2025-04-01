"""Tests for default intent detection implementation."""

from unittest import mock

import pytest

from talk2py.nlu_pipeline.default_intent_detection import DefaultIntentDetection


def test_categorize_user_message():
    """Test categorization of user messages."""
    detector = DefaultIntentDetection()

    # Test abort detection
    assert detector.categorize_user_message("Abort this operation") == "abort"
    assert detector.categorize_user_message("abort") == "abort"

    # Test feedback detection
    assert detector.categorize_user_message("That's not what I meant") == "feedback"
    assert detector.categorize_user_message("This is incorrect") == "feedback"
    assert detector.categorize_user_message("Try instead doing this") == "feedback"
    assert detector.categorize_user_message("That's wrong") == "feedback"

    # Test query detection (default)
    assert detector.categorize_user_message("What time is it?") == "query"
    assert detector.categorize_user_message("Help me with this") == "query"
    assert detector.categorize_user_message("") == "query"


def test_find_best_match():
    """Test the _find_best_match method for different matching scenarios."""
    detector = DefaultIntentDetection()
    commands = [
        "calculator.calc.add_numbers",
        "calculator.calc.subtract_numbers",
        "todo_list.TodoList.add_todo",
        "todo_list.TodoList.get_todos",
    ]

    # Test exact/word matches (prioritize spaced version)
    # pylint: disable=protected-access
    match, match_type = detector._find_best_match(commands, "add numbers please")
    assert match == "calculator.calc.add_numbers"
    assert match_type == 2

    # Test raw word match
    # pylint: disable=protected-access
    match, match_type = detector._find_best_match(
        commands, "add_numbers to my calculator"
    )
    assert match == "calculator.calc.add_numbers"
    assert match_type == 2

    # Test substring match (fall back when no word match)
    # pylint: disable=protected-access
    match, match_type = detector._find_best_match(
        commands, "I want to use the subtract function"
    )
    assert match == "calculator.calc.subtract_numbers"
    assert match_type == 1

    # Test no match
    # pylint: disable=protected-access
    match, match_type = detector._find_best_match(commands, "hello world")
    assert match is None
    assert match_type == 0


@pytest.fixture
def mock_registry():
    """Create a mock registry for testing."""
    registry = mock.MagicMock()
    registry.command_metadata = {
        "map_commandkey_2_metadata": {
            "calculator.calc.add_numbers": {},
            "calculator.calc.subtract_numbers": {},
            "todo_list.TodoList.add_todo": {},
            "todo_list.TodoList.get_todos": {},
        }
    }
    return registry


@pytest.fixture
def mock_chat_context(mock_registry):
    """Create a mock chat context for testing."""
    with mock.patch(
        "talk2py.nlu_pipeline.default_intent_detection.CHAT_CONTEXT"
    ) as mock_context:
        mock_context.get_registry.return_value = mock_registry
        mock_context.current_app_folderpath = "/mock/app/path"
        yield mock_context


# pylint: disable=unused-argument
def test_classify_intent(mock_chat_context):
    """Test intent classification with various inputs."""
    detector = DefaultIntentDetection()

    # Test exact word match (high confidence)
    intent, confidence = detector.classify_intent("add numbers 5 and 3")
    assert intent == "calculator.calc.add_numbers"
    assert confidence == 0.9

    # Test substring match (medium confidence)
    intent, confidence = detector.classify_intent("I need to subtract some values")
    assert intent == "calculator.calc.subtract_numbers"
    assert confidence == 0.7

    # Test no match (low confidence)
    intent, confidence = detector.classify_intent("Tell me a joke")
    assert intent == "unknown"
    assert confidence == 0.1

    # Test with excluded intents
    intent, confidence = detector.classify_intent(
        "add numbers 5 and 3", excluded_intents=["calculator.calc.add_numbers"]
    )
    assert intent != "calculator.calc.add_numbers"


def test_clarify_intent():
    """Test intent clarification logic."""
    detector = DefaultIntentDetection()

    # Test with multiple intents (should pick highest confidence)
    possible_intents = [
        ("calculator.calc.add_numbers", 0.7),
        ("calculator.calc.subtract_numbers", 0.8),
        ("todo_list.TodoList.add_todo", 0.5),
    ]
    assert (
        detector.clarify_intent("user input", possible_intents)
        == "calculator.calc.subtract_numbers"
    )

    # Test with empty list
    assert detector.clarify_intent("user input", []) is None
