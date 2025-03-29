"""Tests for the session management functionality in ChatContext."""

import os
import shutil
from pathlib import Path
from typing import Any, Dict, Generator, Type

import pytest

from talk2py import CHAT_CONTEXT
from talk2py.types import ConversationArtifacts


def load_class_from_sysmodules(module_file: str, class_name: str) -> Type[Any]:
    """Helper function to load a class from a module.

    Args:
        module_file: Path to the module file
        class_name: Name of the class to load

    Returns:
        The class object
    """
    # Extract module name from file path
    module_name = os.path.basename(module_file).replace(".py", "")

    # Import the module
    module = __import__(module_name)

    # Get the class
    return getattr(module, class_name)


@pytest.fixture
def _temp_session_dir(temp_todo_app: Dict[str, Path]) -> Generator[Path, None, None]:
    """Create a temporary directory for session storage.

    Args:
        temp_todo_app: Fixture providing test module paths

    Returns:
        Path to the temporary session directory
    """
    app_path = temp_todo_app["module_dir"]
    session_dir = Path(app_path) / "___conversation_history"

    # Create directory if it doesn't exist
    if not session_dir.exists():
        session_dir.mkdir(parents=True)

    yield session_dir

    # Clean up after test
    if session_dir.exists():
        shutil.rmtree(session_dir)


def test_session_id_generation(
    temp_todo_app: Dict[str, Path], _chat_context_reset: None
) -> None:
    """Test deterministic session ID generation.

    Args:
        temp_todo_app: Fixture providing test module paths
        _chat_context_reset: Fixture providing clean ChatContext instance
    """
    app_path = str(temp_todo_app["module_dir"])
    CHAT_CONTEXT.register_app(app_path)

    # Default user_id should be "user_id"
    assert CHAT_CONTEXT.user_id == "user_id"

    # Get session ID
    session_id1 = CHAT_CONTEXT.current_session_id

    # Should get the same session ID for the same user and app
    session_id2 = CHAT_CONTEXT.current_session_id
    assert session_id1 == session_id2

    # Change user ID
    CHAT_CONTEXT.user_id = "different_user"

    # Should get a different session ID for a different user
    different_session_id = CHAT_CONTEXT.current_session_id
    assert different_session_id != session_id1

    # Using get_session_id_for_user with original user should match original ID
    original_user_id = CHAT_CONTEXT.get_session_id_for_user("user_id")
    assert original_user_id == session_id1


def test_conversation_history_save_load(
    temp_todo_app: Dict[str, Path], _temp_session_dir: Path, _chat_context_reset: None
) -> None:
    """Test saving and loading conversation history.

    Args:
        temp_todo_app: Fixture providing test module paths
        _temp_session_dir: Fixture providing session directory
        _chat_context_reset: Fixture providing clean ChatContext instance
    """
    app_path = str(temp_todo_app["module_dir"])
    CHAT_CONTEXT.register_app(app_path)

    # Add some conversations
    CHAT_CONTEXT.append_to_conversation_history("Q1", "R1")

    # Create artifacts with serializable data
    artifacts = ConversationArtifacts(data={"timestamp": 123456789})
    CHAT_CONTEXT.append_to_conversation_history("Q2", "R2", artifacts)

    # Save to disk
    history_path = CHAT_CONTEXT.save_conversation_history()

    # Verify file exists
    assert os.path.exists(history_path)

    # Clear conversation history
    CHAT_CONTEXT.clear_conversation_history()
    assert len(CHAT_CONTEXT.get_conversation_history()) == 0

    # Load from disk
    CHAT_CONTEXT.load_conversation_history()

    # Verify loaded history is correct
    history = CHAT_CONTEXT.get_conversation_history()
    assert len(history) == 2
    assert history[0][0] == "Q1"  # First query
    assert history[0][1] == "R1"  # First response
    assert history[0][2] is None  # First entry has no artifacts

    assert history[1][0] == "Q2"  # Second query
    assert history[1][1] == "R2"  # Second response
    assert history[1][2] is not None  # Second entry has artifacts
    assert history[1][2].data["timestamp"] == 123456789


def test_context_data_save_load(
    temp_todo_app: Dict[str, Path], _temp_session_dir: Path, _chat_context_reset: None
) -> None:
    """Test saving and loading context data.

    Args:
        temp_todo_app: Fixture providing test module paths
        _temp_session_dir: Fixture providing session directory
        _chat_context_reset: Fixture providing clean ChatContext instance
    """
    app_path = str(temp_todo_app["module_dir"])
    CHAT_CONTEXT.register_app(app_path)

    # Set up context data
    context_data = {
        "string_value": "test",
        "int_value": 42,
        "bool_value": True,
        "none_value": None,
    }
    CHAT_CONTEXT.app_context = context_data

    # Save to disk
    context_path = CHAT_CONTEXT.save_context_data()

    # Verify file exists
    assert os.path.exists(context_path)

    # Clear context data
    CHAT_CONTEXT.app_context = {}
    assert not CHAT_CONTEXT.app_context

    # Load from disk
    CHAT_CONTEXT.load_context_data()

    # Verify loaded context is correct
    loaded_context = CHAT_CONTEXT.app_context
    assert loaded_context["string_value"] == "test"
    assert loaded_context["int_value"] == 42
    assert loaded_context["bool_value"] is True
    assert loaded_context["none_value"] is None


def test_current_object_save_load(
    temp_todo_app: Dict[str, Path], _temp_session_dir: Path, _chat_context_reset: None
) -> None:
    """Test saving and loading current object.

    Args:
        temp_todo_app: Fixture providing test module paths
        _temp_session_dir: Fixture providing session directory
        _chat_context_reset: Fixture providing clean ChatContext instance
    """
    app_path = str(temp_todo_app["module_dir"])
    CHAT_CONTEXT.register_app(app_path)

    # Create a simple test object
    test_object = {"name": "Test Object", "value": 42}

    # Set as current object
    CHAT_CONTEXT.current_object = test_object

    # Save to disk
    object_path = CHAT_CONTEXT.save_current_object()

    # Verify file exists
    assert os.path.exists(object_path)

    # Clear current object
    CHAT_CONTEXT.current_object = None
    assert CHAT_CONTEXT.current_object is None

    # Load from disk
    CHAT_CONTEXT.load_current_object()

    # Verify loaded object is the test object
    assert CHAT_CONTEXT.current_object == test_object


def test_whole_session_save_load(
    temp_todo_app: Dict[str, Path], _temp_session_dir: Path, _chat_context_reset: None
) -> None:
    """Test saving and loading an entire session.

    Args:
        temp_todo_app: Fixture providing test module paths
        _temp_session_dir: Fixture providing session directory
        _chat_context_reset: Fixture providing clean ChatContext instance
    """
    app_path = str(temp_todo_app["module_dir"])
    CHAT_CONTEXT.register_app(app_path)

    # Set up context data
    CHAT_CONTEXT.app_context = {"key": "value"}

    # Add conversation history
    CHAT_CONTEXT.append_to_conversation_history("Question", "Answer")

    # Create a simple test object
    test_object = {"name": "Test Object", "value": 42}
    CHAT_CONTEXT.current_object = test_object

    # Save the entire session
    paths = CHAT_CONTEXT.save_session()

    # Verify files exist
    assert "conversation_history" in paths
    assert os.path.exists(paths["conversation_history"])
    assert "context_data" in paths
    assert os.path.exists(paths["context_data"])
    assert "current_object" in paths
    assert os.path.exists(paths["current_object"])

    # Clear everything
    CHAT_CONTEXT.app_context = {}
    CHAT_CONTEXT.clear_conversation_history()
    CHAT_CONTEXT.current_object = None

    # Load the entire session
    results = CHAT_CONTEXT.load_session()

    # Verify load was successful
    assert results["conversation_history"] is True
    assert results["context_data"] is True
    assert results["current_object"] is True

    # Verify conversation history was loaded
    history = CHAT_CONTEXT.get_conversation_history()
    assert len(history) == 1
    assert history[0][0] == "Question"
    assert history[0][1] == "Answer"

    # Verify context data was loaded
    assert CHAT_CONTEXT.app_context["key"] == "value"

    # Verify current object was loaded
    assert CHAT_CONTEXT.current_object == test_object


def test_list_sessions(
    temp_todo_app: Dict[str, Path], _temp_session_dir: Path, _chat_context_reset: None
) -> None:  # sourcery skip: extract-duplicate-method
    """Test listing available sessions.

    Args:
        temp_todo_app: Fixture providing test module paths
        _temp_session_dir: Fixture providing session directory
        _chat_context_reset: Fixture providing clean ChatContext instance
    """
    app_path = str(temp_todo_app["module_dir"])
    CHAT_CONTEXT.register_app(app_path)

    # Initially, no sessions exist
    sessions = CHAT_CONTEXT.list_sessions()
    assert len(sessions) == 0

    # Get session IDs we expect to create
    current_user_id = CHAT_CONTEXT.user_id
    current_session_id = CHAT_CONTEXT.current_session_id

    # Save a session for the current user
    CHAT_CONTEXT.save_session()

    # Set a different user ID and get its session ID
    CHAT_CONTEXT.user_id = "another_user"
    another_session_id = CHAT_CONTEXT.current_session_id

    # Save a session for the other user
    CHAT_CONTEXT.save_session()

    # Restore the original user for future tests
    CHAT_CONTEXT.user_id = current_user_id

    # List sessions
    sessions = CHAT_CONTEXT.list_sessions()
    assert len(sessions) == 2

    # Verify the two session IDs we saved are in the list
    assert current_session_id in sessions
    assert another_session_id in sessions


def test_error_handling_no_session(
    temp_todo_app: Dict[str, Path], _chat_context_reset: None
) -> None:
    """Test error handling when no session exists.

    Args:
        temp_todo_app: Fixture providing test module paths
        _chat_context_reset: Fixture providing clean ChatContext instance
    """
    app_path = str(temp_todo_app["module_dir"])
    CHAT_CONTEXT.register_app(app_path)

    # Try to load non-existent session
    non_existent_session = "non_existent_session"

    # Should raise FileNotFoundError for session operations
    with pytest.raises(FileNotFoundError):
        CHAT_CONTEXT.load_session(non_existent_session)

    with pytest.raises(FileNotFoundError):
        CHAT_CONTEXT.load_conversation_history(non_existent_session)

    with pytest.raises(FileNotFoundError):
        CHAT_CONTEXT.load_context_data(non_existent_session)

    with pytest.raises(FileNotFoundError):
        CHAT_CONTEXT.load_current_object(non_existent_session)
