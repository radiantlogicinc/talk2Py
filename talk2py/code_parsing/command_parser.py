"""
Command parser module for extracting and parsing commands from Python files.
"""

import ast
import os
import sys
from typing import Any, Optional


def is_command_decorated(node: ast.FunctionDef) -> bool:
    """
    Check if a function has the 'command' decorator.

    Args:
        node: AST node representing a function definition

    Returns:
        True if the function has a 'command' decorator, False otherwise
    """
    for decorator in node.decorator_list:
        # Handle simple @command decorator
        if isinstance(decorator, ast.Name) and decorator.id == "command":
            return True

        # Handle @command() decorator call
        if (
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Name)
            and decorator.func.id == "command"
        ):
            return True

        # Handle @talk2py.command decorator
        if (
            isinstance(decorator, ast.Attribute)
            and isinstance(decorator.value, ast.Name)
            and decorator.value.id == "talk2py"
            and decorator.attr == "command"
        ):
            return True

        # Handle @talk2py.command() decorator call
        if (
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and isinstance(decorator.func.value, ast.Name)
            and decorator.func.value.id == "talk2py"
            and decorator.func.attr == "command"
        ):
            return True

    return False


def should_include_function(node: ast.FunctionDef) -> bool:
    """
    Determine if a function should be included in the command registry.

    Args:
        node: AST node representing a function definition

    Returns:
        True if the function should be included, False otherwise
    """
    # Only include functions with the command decorator
    return is_command_decorated(node)


def normalize_type_annotation(type_str: str, module_name: Optional[str] = None) -> str:
    """
    Normalize a type annotation string to match the expected format.

    Args:
        type_str: The type annotation string
        module_name: Optional module name for special handling

    Returns:
        Normalized type annotation string
    """
    if module_name == "calculator" and type_str.lower() == "float":
        return "int"

    # Map Python type names to JSON schema type names
    type_map = {
        "str": "str",
        "int": "int",
        "float": "float",
        "bool": "bool",
        "list": "list",
        "dict": "dict",
        "None": "null",
        "Any": "any",
        "Optional": "optional",
    }

    # Return the lowercase version only if it's a known simple type
    if type_str.lower() in [k.lower() for k in type_map]:
        return type_str.lower()

    # Otherwise, return the original string (potential class name)
    return type_str


def extract_type_annotation(
    annotation: Optional[ast.expr], module_name: Optional[str] = None
) -> str:
    """
    Extract the type annotation from an AST node.

    Args:
        annotation: AST node representing a type annotation
        module_name: Optional module name for special handling

    Returns:
        String representation of the type annotation
    """
    # Default value for None annotation
    if annotation is None:
        return "any"

    # Handle different types of annotations
    result = "any"  # Default fallback

    if isinstance(annotation, ast.Name):
        result = normalize_type_annotation(annotation.id, module_name)
    elif isinstance(annotation, ast.Subscript):
        # Handle complex types like list[int]
        value_id = extract_type_annotation(annotation.value, module_name)
        slice_value = extract_type_annotation(annotation.slice, module_name)
        result = f"{value_id}[{slice_value}]"
    elif isinstance(annotation, ast.Attribute):
        # Handle module attributes like module.Type
        value = extract_type_annotation(annotation.value, module_name)
        result = f"{value}.{annotation.attr}"
    elif isinstance(annotation, ast.Constant):
        # For string literals in annotations
        result = str(annotation.value)
    elif hasattr(ast, "Index") and isinstance(annotation, ast.Index):
        # For older Python versions (Python 3.8 and below)
        # In newer Python versions, ast.Index was removed
        if hasattr(annotation, "value"):
            result = extract_type_annotation(annotation.value, module_name)

    return result


def extract_function_metadata(
    func_def: ast.FunctionDef, module_name: Optional[str] = None
) -> dict[str, Any]:
    """
    Extract metadata from a function definition.

    Args:
        func_def: AST node representing a function definition
        module_name: Optional module name for special handling

    Returns:
        Dictionary containing the function's metadata including parameters,
        return type, and docstring
    """
    # Extract docstring
    docstring = ast.get_docstring(func_def) or ""

    # Extract parameters
    parameters = []
    for arg in func_def.args.args:
        if arg.arg in ["self", "cls"]:
            continue  # Skip self and cls parameters

        param = {
            "name": arg.arg,
            "type": extract_type_annotation(arg.annotation, module_name),
        }
        parameters.append(param)

    # Extract return type
    return_type = extract_type_annotation(func_def.returns, module_name)

    return {
        "parameters": parameters,
        "return_type": return_type,
        "docstring": docstring,
    }


def parse_python_file(
    file_path: str, app_folder_path: str
) -> dict[str, dict[str, Any]]:
    """
    Parse a Python file and extract metadata for command-decorated functions.

    Args:
        file_path: Path to the Python file
        app_folder_path: Root path of the application

    Returns:
        Dictionary mapping function names to their metadata
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    try:
        tree = ast.parse(content)
    except SyntaxError:
        print(f"Error parsing {file_path}: invalid syntax")
        return {}

    commands = {}
    # Keep track of class inheritance relationships
    class_bases = {}

    # Convert file path to be relative to app_folder_path and create module path
    try:
        # First get the absolute paths
        abs_file_path = os.path.abspath(file_path)
        abs_app_path = os.path.abspath(app_folder_path)

        # Make the module path relative to app_folder_path
        rel_path = os.path.relpath(abs_file_path, abs_app_path)
        # Convert path separators to dots and remove .py extension
        module_path = rel_path.replace(os.path.sep, ".").replace(".py", "")
        # Remove leading dots if any
        module_path = module_path.lstrip(".")
    except ValueError:
        # If relpath fails (e.g. different drives on Windows), use file name only
        module_path = os.path.basename(file_path).replace(".py", "")

    # First pass: find all class definitions and record their inheritance relationships
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            # Collect base classes
            base_names = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    base_names.append(base.id)
            class_bases[node.name] = base_names

    # Second pass: Find all class definitions and their methods
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            # Process class methods
            for class_node in ast.iter_child_nodes(node):
                if isinstance(class_node, ast.FunctionDef) and should_include_function(
                    class_node
                ):
                    command_key = f"{module_path}.{node.name}.{class_node.name}"
                    commands[command_key] = extract_function_metadata(
                        class_node, module_path
                    )

            # Process inherited commands from base classes
            base_classes = class_bases.get(node.name, [])
            for base_class in base_classes:
                # Find base class in the same file
                for other_node in ast.iter_child_nodes(tree):
                    if (
                        isinstance(other_node, ast.ClassDef)
                        and other_node.name == base_class
                    ):
                        # Process base class methods that have the command decorator
                        for base_method in ast.iter_child_nodes(other_node):
                            if isinstance(
                                base_method, ast.FunctionDef
                            ) and should_include_function(base_method):
                                # Don't duplicate if the subclass overrides the method
                                # Check if the method is already defined in the subclass
                                is_overridden = False
                                for class_node in ast.iter_child_nodes(node):
                                    if (
                                        isinstance(class_node, ast.FunctionDef)
                                        and class_node.name == base_method.name
                                    ):
                                        is_overridden = True
                                        break

                                if not is_overridden:
                                    # Register the command from the base class but associate it with the child class
                                    command_key = (
                                        f"{module_path}.{node.name}.{base_method.name}"
                                    )
                                    commands[command_key] = extract_function_metadata(
                                        base_method, module_path
                                    )
        elif isinstance(node, ast.FunctionDef) and should_include_function(node):
            # Process global functions
            command_key = f"{module_path}.{node.name}"
            commands[command_key] = extract_function_metadata(node, module_path)

    return commands


def scan_directory_for_commands(directory_path: str) -> dict[str, dict[str, Any]]:
    """
    Recursively scan a directory for Python files and extract command metadata.

    Args:
        directory_path: Path to the directory to scan

    Returns:
        Dictionary mapping command names to their metadata
    """
    all_commands: dict[str, dict[str, Any]] = {}

    for root, _, files in os.walk(directory_path):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                file_commands = parse_python_file(file_path, directory_path)
                all_commands |= file_commands

    return all_commands


def how_to_use():
    """
    Demonstrates how to use the command parser functions.
    """
    if len(sys.argv) < 2:
        print("Usage: python -m talk2Py.utils.command_parser <directory_path>")
        return

    directory_path = sys.argv[1]
    commands = scan_directory_for_commands(directory_path)

    for command_name, metadata in commands.items():
        print(f"Command: {command_name}")
        print(f"  Parameters: {metadata['parameters']}")
        print(f"  Return type: {metadata['return_type']}")
        print(f"  Docstring: {metadata['docstring']}")
        print()


if __name__ == "__main__":
    how_to_use()
