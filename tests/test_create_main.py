"""
Tests for the talk2py.create.__main__ module.

This module contains test cases for the command registry creation functionality,
including creating and saving command metadata.
"""

import json
import os
import shutil
import tempfile
from unittest import mock

import pytest

from talk2py.create.__main__ import create_command_metadata, main, save_command_metadata


# pylint: disable=attribute-defined-outside-init
class TestCreateCommandRegistry:
    """Test cases for the create_command_metadata function.

    This class contains tests that verify the correct creation and structure
    of command metadata for the application.
    """

    def setup_method(self):
        """Set up test environment before each test method.

        Creates a temporary directory to use as the test app folder.
        """
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Clean up test environment after each test method.

        Removes the temporary directory and all its contents.
        """
        shutil.rmtree(self.temp_dir)

    def test_create_command_metadata_returns_correct_structure(self):
        """Test that create_command_metadata returns the expected structure.

        Verifies that the command metadata dictionary contains the required keys
        and that the command mapping matches the mocked scan results.
        """
        # Mock scan_directory_for_commands to return a known value
        with mock.patch(
            "talk2py.create.__main__.scan_directory_for_commands"
        ) as mock_scan:
            mock_scan.return_value = {"command1": {"description": "Test command"}}

            registry = create_command_metadata(self.temp_dir)

            assert "app_folderpath" in registry
            assert "map_commandkey_2_metadata" in registry
            assert registry["map_commandkey_2_metadata"] == {
                "command1": {"description": "Test command"}
            }

    def test_app_folderpath_uses_relative_path(self):
        """Test that app_folderpath correctly uses a relative path.

        Ensures that the app_folderpath in the registry is properly
        formatted as a relative path starting with './'.
        """
        # Mock scan_directory_for_commands to return an empty dict
        with mock.patch(
            "talk2py.create.__main__.scan_directory_for_commands"
        ) as mock_scan:
            mock_scan.return_value = {}

            # Get the relative path that should be used
            expected_rel_path = os.path.relpath(self.temp_dir)

            registry = create_command_metadata(self.temp_dir)

            assert registry["app_folderpath"] == f"./{expected_rel_path}"


class TestSaveCommandRegistry:
    """Test cases for the save_command_metadata function.

    This class contains tests that verify the correct saving of command
    metadata to the filesystem.
    """

    def setup_method(self):
        """Set up test environment before each test method.

        Creates a temporary directory and initializes test registry data.
        """
        self.temp_dir = tempfile.mkdtemp()
        self.test_registry = {
            "app_folderpath": "./test_app",
            "map_commandkey_2_metadata": {
                "test_command": {"description": "Test command"}
            },
        }

    def teardown_method(self):
        """Clean up test environment after each test method.

        Removes the temporary directory and all its contents.
        """
        shutil.rmtree(self.temp_dir)

    def test_save_command_metadata_creates_file(self):
        """Test that save_command_metadata creates the expected file.

        Verifies that the command metadata is saved to the correct location
        with the expected directory structure.
        """
        output_file = save_command_metadata(self.test_registry, self.temp_dir)

        # Check that the output file exists
        assert os.path.exists(output_file)

        # Check that the directory structure is as expected
        expected_dir = os.path.join(self.temp_dir, "___command_info")
        expected_file = os.path.join(expected_dir, "command_metadata.json")
        assert output_file == expected_file

    def test_save_command_metadata_writes_correct_content(self):
        """Test that save_command_metadata writes the correct content to the file.

        Ensures that the saved JSON file contains exactly the same content
        as the input registry dictionary.
        """
        output_file = save_command_metadata(self.test_registry, self.temp_dir)

        # Read the content of the file
        with open(output_file, "r", encoding="utf-8") as f:
            saved_content = json.load(f)

        # Check that the content matches the input registry
        assert saved_content == self.test_registry


class TestMain:
    """Test cases for the main function.

    This class contains tests that verify the behavior of the main entry point
    for command registry creation.
    """

    def setup_method(self):
        """Set up test environment before each test method.

        Creates a temporary directory to use as the test app folder.
        """
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Clean up test environment after each test method.

        Removes the temporary directory and all its contents.
        """
        shutil.rmtree(self.temp_dir)

    def test_main_exits_on_nonexistent_directory(self, monkeypatch, capsys):
        """Test that main exits when given a non-existent directory.

        Verifies that the program exits with status code 1 and displays
        an appropriate error message when given a non-existent directory.
        """
        # Use a non-existent directory
        nonexistent_dir = os.path.join(self.temp_dir, "nonexistent")

        # Mock sys.argv and sys.exit
        monkeypatch.setattr("sys.argv", ["talk2py.create", nonexistent_dir])
        with pytest.raises(SystemExit) as e:
            main()

        # Check exit code
        assert e.value.code == 1

        # Check error message
        captured = capsys.readouterr()
        assert f"Error: The folder '{nonexistent_dir}' does not exist" in captured.out

    def test_main_creates_registry_and_saves_file(self, monkeypatch, capsys):
        """Test that main creates a registry and saves it to a file.

        Verifies that the main function successfully creates a command registry
        and saves it to the expected location with the correct content.
        """
        # Mock sys.argv
        monkeypatch.setattr("sys.argv", ["talk2py.create", self.temp_dir])

        # Mock create_command_metadata to return a known value
        test_registry = {
            "app_folderpath": f"./{os.path.relpath(self.temp_dir)}",
            "map_commandkey_2_metadata": {
                "test_command": {"description": "Test command"}
            },
        }

        with mock.patch(
            "talk2py.create.__main__.create_command_metadata"
        ) as mock_create:
            mock_create.return_value = test_registry

            # Run main
            main()

            # Check that create_command_metadata was called
            mock_create.assert_called_once_with(self.temp_dir)

        # Check that the command registry file exists
        registry_file = os.path.join(
            self.temp_dir, "___command_info", "command_metadata.json"
        )
        assert os.path.exists(registry_file)

        # Check output messages
        captured = capsys.readouterr()
        assert (
            f"Creating command registry for application at: {self.temp_dir}"
            in captured.out
        )
        assert "Command registry created and saved to:" in captured.out
