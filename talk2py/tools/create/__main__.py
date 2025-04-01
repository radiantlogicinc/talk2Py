"""
Main module for creating command registries from Python files.
"""

import argparse
import json
import os
import sys

from talk2py.code_parsing.command_parser import scan_directory_for_commands


def create_command_metadata(app_folder_path: str) -> dict:
    """
    Create a command registry for an application.

    Args:
        app_folder_path: Path to the application folder

    Returns:
        A dictionary containing the command registry
    """
    # Normalize the path
    app_folder_path = os.path.normpath(app_folder_path)

    # Scan the directory for commands
    commands = scan_directory_for_commands(app_folder_path)

    return {
        "app_folderpath": f"./{os.path.relpath(app_folder_path)}",
        "map_commandkey_2_metadata": commands,
    }


def save_command_metadata(registry: dict, app_folder_path: str) -> str:
    """
    Save the command registry to a JSON file.

    Args:
        registry: The command registry dictionary
        app_folder_path: Path to the application folder

    Returns:
        Path to the saved registry file
    """
    # Create the output directory if it doesn't exist
    output_dir = os.path.join(app_folder_path, "___command_info")
    os.makedirs(output_dir, exist_ok=True)

    # Save the registry to a JSON file
    output_file = os.path.join(output_dir, "command_metadata.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=4)

    return output_file


def main():
    """
    Main function for creating a command registry.
    """
    parser = argparse.ArgumentParser(
        description="Create a command registry for an application"
    )
    parser.add_argument("app_folder_path", help="Path to the application folder")
    args = parser.parse_args()

    # Check if the folder exists
    if not os.path.isdir(args.app_folder_path):
        print(
            f"Error: The folder '{args.app_folder_path}' does not exist or is not a directory."
        )
        sys.exit(1)

    print(f"Creating command registry for application at: {args.app_folder_path}")

    # Create the registry
    registry = create_command_metadata(args.app_folder_path)

    # Save the registry
    output_file = save_command_metadata(registry, args.app_folder_path)

    print(f"Command registry created and saved to: {output_file}")

    # Pretty print the registry
    print("\nCommand Registry:")
    print(json.dumps(registry, indent=4))


if __name__ == "__main__":
    main()
