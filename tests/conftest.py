"""Shared test fixtures for talk2py tests."""

import os
import shutil
import sys
from pathlib import Path
from typing import Generator, Union, Any
import importlib.util

import pytest

import talk2py
from talk2py.code_parsing.command_registry import CommandRegistry
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
def temp_todo_app(tmp_path: Path) -> Generator[dict[str, Any], None, None]:
    """Create a temporary todo app for testing, including instances.

    Args:
        tmpdir: pytest fixture for temporary directory

    Returns:
        Dictionary with paths and pre-initialized app instances.
    """
    app_name = "todo_list"
    app_base_path = tmp_path / app_name
    src_dir = Path(
        os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "examples", app_name)
        )
    )
    if not src_dir.exists():
        raise ValueError(f"Example application {app_name} not found at {src_dir}")

    _copy_directory(src_dir, app_base_path, exclude=["__pycache__"])

    app_folderpath = str(app_base_path)
    module_file = str(app_base_path / f"{app_name}.py")

    # Add to sys.path BEFORE creating metadata or importing
    if app_folderpath not in sys.path:
        sys.path.insert(0, app_folderpath)

    # Create and save command metadata
    registry_data = create_command_metadata(app_folderpath)
    metadata_path = save_command_metadata(registry_data, app_folderpath)

    # Dynamically import and initialize the app
    spec = importlib.util.spec_from_file_location(app_name, module_file)
    if not spec or not spec.loader:
        raise ImportError(f"Could not load spec for {module_file}")
    todo_module = importlib.util.module_from_spec(spec)
    sys.modules[app_name] = todo_module
    spec.loader.exec_module(todo_module)

    # Initialize app and get instances
    todo_list_instance = todo_module.init_todolist_app()
    todo1 = todo_list_instance.add_todo("Initial Todo 1")
    todo2 = todo_list_instance.add_todo("Initial Todo 2")
    todo1.close()  # Example state change

    app_data = {
        "app_folderpath": app_folderpath,
        "module_dir": app_folderpath,
        "module_file": module_file,
        "metadata_path": metadata_path,
        "todo_list_instance": todo_list_instance,
        "todo1": todo1,
        "todo2": todo2,
    }

    yield app_data

    # Clean up - safely remove from sys.path if it's present
    if app_folderpath in sys.path:
        try:
            sys.path.remove(app_folderpath)
        except ValueError:
            pass  # Ignore if already removed
    # Clean up sys.modules
    if app_name in sys.modules:
        del sys.modules[app_name]


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
    return CommandRegistry(str(temp_todo_app["app_folderpath"]))


@pytest.fixture
def _chat_context_reset() -> Generator[None, None, None]:
    """Reset the CHAT_CONTEXT before and after each test."""
    talk2py.CHAT_CONTEXT.reset()
    yield
    talk2py.CHAT_CONTEXT.reset()


# Helper function to load classes dynamically, used in various tests
def load_class_from_sysmodules(file_path: str, class_name: str) -> type:
    """Dynamically load a class from sys.modules."""
    # Derive module name from file path
    module_name_parts = Path(file_path).stem.split(os.sep)
    if not module_name_parts:
        raise ValueError(f"Could not determine module name from path: {file_path}")
    module_name = module_name_parts[-1]

    # Check if module is loaded
    if module_name not in sys.modules:
        # Attempt to load it if not found (basic case, might need refinement)
        try:
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
            else:
                raise ImportError(f"Could not create spec for module: {module_name}")
        except Exception as e:
            raise ImportError(
                f"Failed to load module '{module_name}' from {file_path}: {e}"
            ) from e

    module = sys.modules[module_name]

    # Retrieve the class from the module
    if not hasattr(module, class_name):
        raise AttributeError(
            f"Module '{module_name}' does not define a class '{class_name}'"
        )

    return getattr(module, class_name)
