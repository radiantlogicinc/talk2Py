"""Shared test fixtures for talk2py tests."""

import os
import shutil
import sys
from pathlib import Path
from typing import Generator, Union

import pytest

import talk2py
from talk2py.code_parsing_execution.command_executor import CommandExecutor
from talk2py.code_parsing_execution.command_registry import CommandRegistry
from talk2py.tools.create.__main__ import create_command_metadata, save_command_metadata

TMP_PATH_EXAMPLES: str = "./tests/tmp"


def _copy_directory(
    src_dir: Union[str, Path],
    dest_dir: Union[str, Path],
    exclude: list[str] | None = None,
) -> None:
    """Copy a directory to a destination.

    Args:
        src_dir: Source directory path
        dest_dir: Destination directory path
        exclude: list of file/directory names to exclude from copying
    """
    exclude = exclude or []
    src_path = Path(src_dir)
    dest_path = Path(dest_dir)

    if not dest_path.exists():
        dest_path.mkdir(parents=True)

    for item in src_path.iterdir():
        if item.name in exclude:
            continue

        if item.is_dir():
            _copy_directory(item, dest_path / item.name, exclude)
        else:
            shutil.copy2(item, dest_path / item.name)


def _copy_example_app(app_name: str, tmp_path: str) -> dict[str, str]:
    """Copy an example application to a temporary directory.

    Args:
        app_name: Name of the example application ('calculator' or 'todo_list')
        tmp_path: Pytest temporary directory path

    Returns:
        Dictionary with module_dir and metadata_path
    """
    src_dir = Path(
        os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "examples", app_name)
        )
    )
    if not src_dir.exists():
        raise ValueError(f"Example application {app_name} not found at {src_dir}")

    dest_dir = f"{tmp_path}/{app_name}"
    module_file = f"{dest_dir}/{app_name}.py"

    # Copy the application to the temporary directory
    _copy_directory(src_dir, dest_dir, exclude=["__pycache__"])

    # run talk2py.create to replace the command_metadata.json in ___command_info
    # Create and save the registry
    registry = create_command_metadata(dest_dir)
    _ = save_command_metadata(registry, dest_dir)

    # Return paths that are consistent with existing fixtures
    metadata_path = f"{dest_dir}/___command_info/command_metadata.json"
    return {
        "module_dir": dest_dir,
        "module_file": module_file,
        "metadata_path": metadata_path,
    }


@pytest.fixture
def temp_calculator_app() -> Generator[dict[str, str], None, None]:
    """Create a temporary copy of the calculator app for testing.

    Args:
        tmp_path: Pytest fixture providing a temporary directory path

    Returns:
        A dictionary containing the module directory and metadata file paths
    """
    # Add to sys.path only if not already there
    app_path = f"{TMP_PATH_EXAMPLES}/calculator"

    # Add to sys.path only if not already there
    if app_path not in sys.path:
        sys.path.insert(0, app_path)

    yield _copy_example_app("calculator", TMP_PATH_EXAMPLES)

    # Clean up - safely remove from sys.path if it's present
    if app_path in sys.path:
        sys.path.remove(app_path)


@pytest.fixture
def temp_todo_app() -> Generator[dict[str, str], None, None]:
    """Create a temporary todo app for testing.

    Args:
        tmpdir: pytest fixture for temporary directory

    Returns:
        Dictionary with module directory and metadata paths
    """
    app_path = f"{TMP_PATH_EXAMPLES}/todo_list"

    # Add to sys.path only if not already there
    if app_path not in sys.path:
        sys.path.insert(0, app_path)

    yield _copy_example_app("todo_list", TMP_PATH_EXAMPLES)

    # Clean up - safely remove from sys.path if it's present
    if app_path in sys.path:
        sys.path.remove(app_path)


@pytest.fixture
def calculator_registry(temp_calculator_app) -> CommandRegistry:
    """Create a CommandRegistry with calculator commands loaded.

    Args:
        temp_calculator_app: Fixture providing test module paths

    Returns:
        CommandRegistry instance
    """
    return CommandRegistry(str(temp_calculator_app["module_dir"]))


@pytest.fixture
def todolist_registry(temp_todo_app) -> CommandRegistry:
    """Create a CommandRegistry with todo_list commands loaded.

    Args:
        temp_todo_app: Fixture providing test module paths

    Returns:
        CommandRegistry instance
    """
    return CommandRegistry(str(temp_todo_app["module_dir"]))


@pytest.fixture
def calculator_executor(calculator_registry) -> CommandExecutor:
    """Create a CommandExecutor with calculator commands loaded.

    Args:
        calculator_registry: Fixture providing calculator registry

    Returns:
        Configured CommandExecutor instance
    """
    return CommandExecutor(calculator_registry)


@pytest.fixture
def todolist_executor(todolist_registry) -> CommandExecutor:
    """Create a CommandExecutor with todo_list commands loaded.

    Args:
        todo_registry: Fixture providing todo registry

    Returns:
        Configured CommandExecutor instance
    """
    return CommandExecutor(todolist_registry)


@pytest.fixture
def _chat_context_reset() -> Generator[None, None, None]:
    """Reset the CHAT_CONTEXT before and after each test."""
    talk2py.CHAT_CONTEXT.reset()
    yield
    talk2py.CHAT_CONTEXT.reset()
