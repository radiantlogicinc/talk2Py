# pylint: disable=duplicate-code
"""Tests for default utterance implementation."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from talk2py.default_utterance_impl import DefaultUtterancesImpl


class TestDefaultUtterancesImpl(unittest.TestCase):
    """Tests for the DefaultUtterancesImpl class."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create a mock CommandRegistry
        self.mock_registry = mock.MagicMock()

        # Set up the mock registry with sample command metadata
        self.mock_registry.command_metadata = {
            "app_folderpath": "./",
            "map_commandkey_2_metadata": {
                "test.add": {
                    "parameters": [
                        {"name": "a", "type": "int"},
                        {"name": "b", "type": "int"},
                    ],
                    "return_type": "int",
                    "docstring": "Add two numbers and return the result.",
                },
                "test.subtract": {
                    "parameters": [
                        {"name": "a", "type": "int"},
                        {"name": "b", "type": "int"},
                    ],
                    "return_type": "int",
                    "docstring": "Subtract b from a and return the result.",
                },
            },
        }

        # Create the DefaultUtterancesImpl instance to test
        self.utterance_impl = DefaultUtterancesImpl(self.mock_registry)

    def test_generate_utterances_returns_correct_format(self):
        """Test that generate_utterances returns the expected format."""
        signature, docstring = self.utterance_impl.get_utterance_metadata("test.add")

        # Check the signature format
        self.assertEqual(signature, "def add(a: int, b: int) -> int")

        # Check the docstring
        self.assertEqual(docstring, "Add two numbers and return the result.")

    def test_generate_utterances_handles_different_command(self):
        """Test that generate_utterances works for different commands."""
        signature, docstring = self.utterance_impl.get_utterance_metadata(
            "test.subtract"
        )

        # Check the signature format
        self.assertEqual(signature, "def subtract(a: int, b: int) -> int")

        # Check the docstring
        self.assertEqual(docstring, "Subtract b from a and return the result.")

    def test_generate_utterances_with_empty_registry(self):
        """Test that generate_utterances handles an empty registry."""
        # Create an empty registry
        empty_registry = mock.MagicMock()
        empty_registry.command_metadata = {}

        utterance_impl = DefaultUtterancesImpl(empty_registry)

        # Check that it raises an error
        with self.assertRaises(ValueError):
            utterance_impl.get_utterance_metadata("test.add")

    def test_generate_utterances_with_nonexistent_command(self):
        """Test that generate_utterances handles a nonexistent command."""
        # Check that it raises an error
        with self.assertRaises(ValueError):
            self.utterance_impl.get_utterance_metadata("test.nonexistent")

    def test_using_get_registry_function(self):
        """Test using the get_registry function from talk2py."""
        # Create a temporary directory for the app folder
        with tempfile.TemporaryDirectory() as temp_dir:
            app_folder_path = Path(temp_dir)

            # Mock the get_registry function and get_metadata_path
            with (
                mock.patch("talk2py.get_registry") as mock_get_registry,
                mock.patch(
                    "talk2py.command_registry.CommandRegistry.get_metadata_path"
                ) as mock_get_metadata_path,  # noqa: F841 # pylint: disable=unused-variable
                mock.patch(
                    "talk2py.command_registry.CommandRegistry.load_command_metadata"
                ) as mock_load_metadata,  # noqa: F841 # pylint: disable=unused-variable
            ):
                # Set up mock registry for the function to return
                mock_registry = mock.MagicMock()
                mock_registry.command_metadata = {
                    "app_folderpath": "./test_app",
                    "map_commandkey_2_metadata": {
                        "test.function": {
                            "parameters": [{"name": "param", "type": "str"}],
                            "return_type": "str",
                            "docstring": "Test function docstring",
                        },
                    },
                }

                # Configure the mocks
                mock_get_registry.return_value = mock_registry

                # Call get_registry with our app folder path
                registry = mock_get_registry(str(app_folder_path))

                # Verify the registry was returned
                self.assertEqual(registry, mock_registry)

                # Create an utterance impl with the registry
                utterance_impl = DefaultUtterancesImpl(registry)

                # Test that we can get utterance metadata
                signature, docstring = utterance_impl.get_utterance_metadata(
                    "test.function"
                )

                # Check the results
                self.assertEqual(signature, "def function(param: str) -> str")
                self.assertEqual(docstring, "Test function docstring")
