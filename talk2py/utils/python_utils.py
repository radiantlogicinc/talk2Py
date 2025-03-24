"""
Utility module providing Python module-related helper functions.
"""

import importlib
import importlib.util
import os


def get_module(module_file_path: str, workflow_folderpath: str):
    """
    Import a Python module from a file path.

    Args:
        module_file_path: Path to the Python module file
        workflow_folderpath: Path to the workflow folder

    Returns:
        Imported module object or None if the module path is empty
    """
    if not module_file_path:
        return None

    def truncate_path(path):
        # Find the second occurrence of "fastworkflow" in the path
        first_index = path.find("fastworkflow")
        if first_index != -1:
            second_index = path.find("fastworkflow", first_index + 1)
            if second_index != -1:
                # Replace everything before the second "fastworkflow" with "./"
                return f"./{path[second_index:]}"
        return path

    # Truncate both paths
    workflow_folderpath = truncate_path(workflow_folderpath)
    module_file_path = truncate_path(module_file_path)

    module_file_path = module_file_path.removeprefix("./").removeprefix("/")
    # Strip '.py' and replace slashes
    module_pythonic_path = module_file_path.replace(os.sep, ".").rsplit(".py", 1)[0]

    # Split paths into components and find common prefix
    root_package_pythonic_path = workflow_folderpath.replace(os.sep, ".").lstrip(".")
    root_parts = root_package_pythonic_path.split(".")
    module_parts = module_pythonic_path.split(".")
    common_prefix = []
    r_start_index = 0  # Default value in case the for loop doesn't find a match
    for r_start_index, r in enumerate(root_parts):
        if r == module_parts[0]:
            break
    for offsetted_r, m in zip(root_parts[r_start_index:], module_parts):
        if offsetted_r != m:
            break
        common_prefix.append(offsetted_r)
    root_package_name = ".".join(common_prefix) if common_prefix else ""

    relative_module_name = (
        module_pythonic_path[len(root_package_name) :]
        if root_package_name
        else module_pythonic_path
    )
    spec = importlib.util.find_spec(relative_module_name, root_package_name)
    if spec is None:
        raise ImportError(f"Module {relative_module_name} not found")
    return importlib.import_module(relative_module_name, root_package_name)
