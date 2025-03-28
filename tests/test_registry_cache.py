"""Tests for the registry caching mechanism.

This module contains test cases for the registry caching functionality
in the ChatContext class.
"""

import pytest
from unittest import mock

import talk2py
from talk2py import CHAT_CONTEXT
from talk2py.command_registry import CommandRegistry
from talk2py.chat_context import AppContext


def test_registry_caching(chat_context_reset):
    """Test that ChatContext caches CommandRegistry instances in app contexts."""
    # Mock CommandRegistry to avoid filesystem access
    mock_instance1 = mock.MagicMock()
    mock_instance2 = mock.MagicMock()
    mock_registry_class = mock.MagicMock()
    mock_registry_class.side_effect = [mock_instance1, mock_instance2]

    with (
        mock.patch("talk2py.chat_context.CommandRegistry", mock_registry_class),
        mock.patch("os.path.exists", return_value=True),
        mock.patch("builtins.open", mock.mock_open(read_data="{}")),
    ):
        # Register an app with a test path
        app_path = "/test/path"
        CHAT_CONTEXT.register_app(app_path)
        
        # Get the registry for the same path twice
        registry1 = CHAT_CONTEXT.get_registry(app_path)
        registry2 = CHAT_CONTEXT.get_registry(app_path)

        # Verify that only one instance was created
        assert registry1 == registry2
        mock_registry_class.assert_called_once_with(app_path)


def test_registry_cache_persistence(chat_context_reset):
    """Test that registry cache persists between calls."""
    # Mock CommandRegistry
    mock_instance = mock.MagicMock()
    mock_registry_class = mock.MagicMock(return_value=mock_instance)

    with (
        mock.patch("talk2py.chat_context.CommandRegistry", mock_registry_class),
        mock.patch("os.path.exists", return_value=True),
        mock.patch("builtins.open", mock.mock_open(read_data="{}")),
    ):
        # Register an app and get its registry
        app_path = "/test/path"
        CHAT_CONTEXT.register_app(app_path)
        registry1 = CHAT_CONTEXT.get_registry(app_path)

        # Clear the mock to verify no more instances are created
        mock_registry_class.reset_mock()

        # Get registry again
        registry2 = CHAT_CONTEXT.get_registry(app_path)

        # Verify that no new instance was created
        assert registry1 == registry2
        mock_registry_class.assert_not_called()


def test_app_context_structure(chat_context_reset):
    """Test that the app context structure is properly maintained."""
    # Set up a test app path
    app_path = "/test/app"
    
    # Create a mock registry
    mock_registry = mock.MagicMock(spec=CommandRegistry)
    
    with mock.patch("talk2py.chat_context.CommandRegistry", return_value=mock_registry):
        # Register the app
        CHAT_CONTEXT.register_app(app_path)
        
        # Verify app context was created with correct structure
        assert app_path in CHAT_CONTEXT._app_contexts
        app_context = CHAT_CONTEXT._app_contexts[app_path]
        
        # Verify it's an AppContext instance with expected attributes
        assert isinstance(app_context, AppContext)
        assert app_context.registry == mock_registry
        assert app_context.current_object is None
        assert isinstance(app_context.context_data, dict)
