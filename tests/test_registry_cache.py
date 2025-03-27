"""Tests for the registry caching mechanism.

This module contains test cases for the registry caching functionality
in talk2py.__init__.py.
"""

import unittest
from unittest import mock

import talk2py
from talk2py import CHAT_CONTEXT


class TestRegistryCache(unittest.TestCase):
    """Tests for the registry caching mechanism."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Clear the registry cache
        # pylint: disable=protected-access
        CHAT_CONTEXT._registry_cache.clear()

    def test_registry_caching(self):
        """Test that get_registry caches CommandRegistry instances."""
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
            # Call get_registry twice with the same path
            app_path = "/test/path"
            registry1 = talk2py.get_registry(app_path)
            registry2 = talk2py.get_registry(app_path)

            # Verify that only one instance was created
            self.assertEqual(registry1, registry2)
            mock_registry_class.assert_called_once_with(app_path)

    def test_registry_cache_persistence(self):
        """Test that registry cache persists between calls."""
        # Mock CommandRegistry
        mock_instance = mock.MagicMock()
        mock_registry_class = mock.MagicMock(return_value=mock_instance)

        with (
            mock.patch("talk2py.chat_context.CommandRegistry", mock_registry_class),
            mock.patch("os.path.exists", return_value=True),
            mock.patch("builtins.open", mock.mock_open(read_data="{}")),
        ):
            # Call get_registry
            app_path = "/test/path"
            registry1 = talk2py.get_registry(app_path)

            # Clear the mock to verify no more instances are created
            mock_registry_class.reset_mock()

            # Call get_registry again
            registry2 = talk2py.get_registry(app_path)

            # Verify that no new instance was created
            self.assertEqual(registry1, registry2)
            mock_registry_class.assert_not_called()


if __name__ == "__main__":
    unittest.main()
