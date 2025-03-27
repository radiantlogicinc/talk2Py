"""Tests for NLU overrides manager CLI."""

# pylint: disable=consider-using-with,too-many-instance-attributes

import json
import sys
import tempfile
from io import StringIO
from pathlib import Path
from unittest import TestCase, mock

from talk2py.manage_nlu_overrides.__main__ import main


# pylint: disable=too-many-instance-attributes
class TestNLUOverridesManagerCLI(TestCase):
    """Test cases for NLU overrides manager CLI."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for tests
        self._temp_dir = tempfile.TemporaryDirectory()
        self.app_folder = Path(self._temp_dir.name)

        # Create command metadata
        self.command_metadata = {
            "app_folderpath": str(self.app_folder),
            "map_commandkey_2_metadata": {
                "test.add": {
                    "parameters": [
                        {"name": "a", "type": "int"},
                        {"name": "b", "type": "int"},
                    ],
                    "return_type": "int",
                    "docstring": "Add two numbers.",
                },
                "test.subtract": {
                    "parameters": [
                        {"name": "a", "type": "int"},
                        {"name": "b", "type": "int"},
                    ],
                    "return_type": "int",
                    "docstring": "Subtract two numbers.",
                },
            },
        }

        # Create command info directory and metadata file
        self.command_info_dir = self.app_folder / "___command_info"
        self.command_info_dir.mkdir()
        self.command_metadata_file = self.command_info_dir / "command_metadata.json"
        self.command_metadata_file.write_text(json.dumps(self.command_metadata))

        # Create empty NLU metadata file
        self.nlu_metadata = {
            "app_folderpath": str(self.app_folder),
            "map_commandkey_2_nluengine_metadata": {},
        }
        self.nlu_metadata_file = self.command_info_dir / "nlu_engine_metadata.json"
        self.nlu_metadata_file.write_text(json.dumps(self.nlu_metadata))

        # Mock the command registry
        self.mock_registry = mock.MagicMock()
        self.mock_registry.command_metadata = self.command_metadata

        # Save original stdin/stdout
        self.original_stdin = sys.stdin
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr

    def tearDown(self):
        """Clean up test fixtures."""
        self._temp_dir.cleanup()
        # Restore original stdin/stdout
        sys.stdin = self.original_stdin
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr

    def test_cli_invalid_command(self):
        """Test CLI behavior with invalid command number."""
        # Mock user input
        user_input = StringIO(
            "99\n"  # Invalid command number
            "\n"  # Exit
        )
        sys.stdin = user_input

        # Capture output
        output = StringIO()
        sys.stdout = output

        # Run CLI
        with mock.patch(
            "talk2py.manage_nlu_overrides.__main__.get_registry",
            return_value=self.mock_registry,
        ):
            sys.argv = ["manage_nlu_overrides", str(self.app_folder)]
            main()

        # Check error message
        output_text = output.getvalue()
        self.assertIn("Error: '99' is not a valid command number", output_text)

    def test_cli_invalid_interface_numbers(self):
        """Test CLI behavior with invalid interface numbers."""
        # Mock user input
        user_input = StringIO(
            "1\n"  # Command number for test.add
            "4,5\n"  # Invalid interface numbers
            "\n"  # Exit
        )
        sys.stdin = user_input

        # Capture output
        output = StringIO()
        sys.stdout = output

        # Run CLI
        with mock.patch(
            "talk2py.manage_nlu_overrides.__main__.get_registry",
            return_value=self.mock_registry,
        ):
            sys.argv = ["manage_nlu_overrides", str(self.app_folder)]
            main()

        # Check error message
        output_text = output.getvalue()
        self.assertIn("No valid interfaces selected", output_text)

    def test_cli_scan_invalid_overrides(self):
        """Test CLI behavior when scanning invalid override implementations."""
        # Create an invalid override
        override_dir = self.app_folder / "nlu_interface_overrides" / "test_add"
        override_dir.mkdir(parents=True)
        (override_dir / "__init__.py").touch()
        (override_dir / "param_extraction.py").write_text("class WrongImpl: pass")

        # Mock user input to exit immediately
        user_input = StringIO("\n")  # Exit
        sys.stdin = user_input

        # Capture output
        output = StringIO()
        sys.stdout = output

        # Run CLI
        with mock.patch(
            "talk2py.manage_nlu_overrides.__main__.get_registry",
            return_value=self.mock_registry,
        ):
            sys.argv = ["manage_nlu_overrides", str(self.app_folder)]
            main()

        # Check warning message
        output_text = output.getvalue()
        self.assertIn("Warning: Found invalid override implementations", output_text)
        self.assertIn("test.add", output_text)
        self.assertIn("param_extraction_class", output_text)

    def test_cli_no_commands_available(self):
        """Test CLI behavior when no commands are available for override."""
        # Create metadata showing all interfaces are overridden
        self.nlu_metadata["map_commandkey_2_nluengine_metadata"] = {
            "test.add": {
                "param_extraction_class": "path.to.CustomImpl",
                "response_generation_class": "path.to.CustomImpl",
            },
            "test.subtract": {
                "param_extraction_class": "path.to.CustomImpl",
                "response_generation_class": "path.to.CustomImpl",
            },
        }
        self.nlu_metadata_file.write_text(json.dumps(self.nlu_metadata))

        # Capture output
        output = StringIO()
        sys.stdout = output

        # Run CLI
        with mock.patch(
            "talk2py.manage_nlu_overrides.__main__.get_registry",
            return_value=self.mock_registry,
        ):
            sys.argv = ["manage_nlu_overrides", str(self.app_folder)]
            main()

        # Check message
        output_text = output.getvalue()
        self.assertIn(
            "No more commands available for override customization", output_text
        )
