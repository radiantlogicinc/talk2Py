"""
Registry Cache module for talk2py.

This module provides the RegistryCache class which manages the caching and loading
of CommandRegistry instances to avoid redundant loading of command metadata.
"""

import logging
import os

from talk2py.command_registry import CommandRegistry


class RegistryCache:
    """Manages the caching and loading of CommandRegistry instances.

    This class provides static methods for loading and caching CommandRegistry
    instances to avoid redundant loading of command metadata.
    """

    # In-memory cache of CommandRegistry instances keyed by app_folderpath
    _cache: dict[str, CommandRegistry] = {}

    @classmethod
    def load_registry(cls, app_folderpath: str) -> CommandRegistry:
        """Load a CommandRegistry instance for the specified application folder.

        This method maintains a cache of registry instances to avoid
        redundant loading of command metadata.

        Args:
            app_folderpath: Path to the application folder

        Returns:
            A CommandRegistry instance for the specified application folder

        Raises:
            ValueError: If the app_folderpath is invalid
        """
        # Normalize path for caching
        abs_path = os.path.abspath(app_folderpath)

        # Return cached registry if available
        if abs_path in cls._cache:
            logging.debug("Using cached CommandRegistry for: %s", abs_path)
            return cls._cache[abs_path]

        # Ensure the path exists
        if not os.path.exists(abs_path):
            raise ValueError(f"Application folder path does not exist: {abs_path}")

        # Create a new registry instance
        logging.debug("Creating new CommandRegistry for: %s", abs_path)
        registry = CommandRegistry(abs_path)

        # Cache the registry
        cls._cache[abs_path] = registry

        return registry

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the registry cache."""
        cls._cache.clear()
        logging.debug("Registry cache cleared.")

    @classmethod
    def get_cached_registry(cls, app_folderpath: str) -> CommandRegistry:
        """Get a cached CommandRegistry instance if available, without loading.

        Args:
            app_folderpath: Path to the application folder

        Returns:
            A CommandRegistry instance for the specified application folder

        Raises:
            ValueError: If no registry exists for the given app_folderpath
        """
        abs_path = os.path.abspath(app_folderpath)
        if abs_path not in cls._cache:
            raise ValueError(f"No registry cached for app: {abs_path}")

        return cls._cache[abs_path]
