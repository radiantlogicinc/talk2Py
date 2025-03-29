"""Tests for the registry caching mechanism.

This module contains test cases for the registry caching functionality
in the ChatContext class.
"""

from talk2py import CHAT_CONTEXT


def test_registry_caching(_chat_context_reset, temp_todo_app):
    """Test that ChatContext caches CommandRegistry instances in app contexts."""
    # Use real app path from the fixture
    app_path = temp_todo_app["module_dir"]

    # Register the app
    CHAT_CONTEXT.register_app(app_path)

    # Get the registry for the same path twice
    registry1 = CHAT_CONTEXT.get_registry(app_path)
    registry2 = CHAT_CONTEXT.get_registry(app_path)

    # Verify that the same registry instance is returned
    assert registry1 is registry2
    # CommandRegistry does not have app_path attribute
    # Check metadata dictionary instead
    assert registry1.command_metadata.get("app_folderpath") == app_path


def test_registry_cache_persistence(_chat_context_reset, temp_todo_app):
    """Test that registry cache persists between calls."""
    # Use real app path from the fixture
    app_path = temp_todo_app["module_dir"]

    # Register an app and get its registry
    CHAT_CONTEXT.register_app(app_path)
    registry1 = CHAT_CONTEXT.get_registry(app_path)

    # Get registry again
    registry2 = CHAT_CONTEXT.get_registry(app_path)

    # Verify that the same registry instance is returned
    assert registry1 is registry2
    # CommandRegistry does not have app_path attribute
    # Check metadata dictionary instead
    assert registry1.command_metadata.get("app_folderpath") == app_path


def test_app_context_structure(_chat_context_reset, todolist_registry):
    """Test that the app context structure is properly maintained."""
    # Get the app path from the metadata instead
    app_path = todolist_registry.command_metadata.get("app_folderpath")

    # Register the app
    CHAT_CONTEXT.register_app(app_path)

    # Verify current_app_folderpath
    assert app_path == CHAT_CONTEXT.current_app_folderpath

    # Verify app_context is a dict
    app_context = CHAT_CONTEXT.app_context
    assert isinstance(app_context, dict)
    # Verify app_context is empty
    assert app_context == {}

    assert isinstance(CHAT_CONTEXT.get_registry(app_path), type(todolist_registry))
    assert CHAT_CONTEXT.current_object is None
