"""
A todolist app demonstrating:
1. exposing class methods as commands and
2. switching conversation context among class instances
"""

import os
from datetime import datetime
from enum import Enum
from typing import Optional

import talk2py
from talk2py import CHAT_CONTEXT


class TodoState(Enum):
    """Enum representing the possible states of a Todo item."""

    ACTIVE = "active"
    CLOSED = "closed"


# Initialize the global counter for todo IDs
NEXT_ID = -1


def get_next_todo_id() -> int:
    """return the next todo id"""
    global NEXT_ID  # pylint: disable=global-statement
    NEXT_ID += 1
    return NEXT_ID


class Todo:
    """Class representing a single todo item."""

    def __init__(self, description: str):
        """Initialize a new Todo item.

        Args:
            description: The description of the todo item
        """
        self._id = get_next_todo_id()
        self._description = description
        self._state = TodoState.ACTIVE
        self._date_created = datetime.now()
        self._date_closed: Optional[datetime] = None

    @property
    @talk2py.command
    def id(self) -> int:
        """Get the todo item id."""
        return self._id

    @property
    @talk2py.command
    def description(self) -> str:
        """Get the todo item description."""
        return self._description

    @description.setter
    @talk2py.command
    def description(self, value: str) -> None:
        """Set the todo item description.

        Args:
            value: The new description
        """
        if not value.strip():
            raise ValueError("Description cannot be empty")
        self._description = value

    @property
    @talk2py.command
    def state(self) -> TodoState:
        """Get the current state of the todo item."""
        return self._state

    @property
    @talk2py.command
    def date_created(self) -> datetime:
        """Get the creation date of the todo item."""
        return self._date_created

    @property
    @talk2py.command
    def date_closed(self) -> Optional[datetime]:
        """Get the closing date of the todo item if it's closed."""
        return self._date_closed

    @talk2py.command
    def close(self) -> None:
        """Mark the todo item as closed."""
        if self._state == TodoState.ACTIVE:
            self._state = TodoState.CLOSED
            self._date_closed = datetime.now()

    @talk2py.command
    def reopen(self) -> None:
        """Reopen a closed todo item."""
        if self._state == TodoState.CLOSED:
            self._state = TodoState.ACTIVE
            self._date_closed = None

    @talk2py.command
    def __str__(self) -> str:
        """Return a string representation of the todo item."""
        status = "✓" if self.state == TodoState.CLOSED else "☐"
        return f"{status} {self.id}: {self.description}"


class TodoList:
    """Class for managing a collection of Todo items."""

    def __init__(self) -> None:
        """Initialize an empty todo list."""
        self._todos: list[Todo] = []
        self._current_todo: Optional[Todo] = None

    @talk2py.command
    def add_todo(self, description: str) -> Todo:
        """Add a new todo item to the list.

        Args:
            description: The description of the new todo item

        Returns:
            The newly created Todo instance
        """
        todo = Todo(description)
        self._todos.append(todo)
        return todo

    @talk2py.command
    def get_todo(self, todo_id: int) -> Todo:
        """Get a todo item by its ID.

        Args:
            todo_id: The ID of the todo item to retrieve

        Returns:
            The Todo instance with the specified ID

        Raises:
            ValueError: If no todo item with the specified ID exists
        """
        for todo in self._todos:
            if todo.id == todo_id:
                return todo
        raise ValueError(f"No todo item found with ID {todo_id}")

    @talk2py.command
    def remove_todo(self, todo_id: int) -> None:
        """Remove a todo item from the list.

        Args:
            todo: The Todo instance to remove

        Raises:
            ValueError: If the todo item is not in the list
        """
        try:
            todo_id_to_remove = self.get_todo(todo_id)
            self._todos.remove(todo_id_to_remove)
        except ValueError as e:
            raise ValueError("Todo item not found in the list") from e

    @talk2py.command
    def get_active_todos(self) -> list[Todo]:
        """Get all active todo items.

        Returns:
            A list of active Todo instances
        """
        return [todo for todo in self._todos if todo.state == TodoState.ACTIVE]

    @talk2py.command
    def get_closed_todos(self) -> list[Todo]:
        """Get all closed todo items.

        Returns:
            A list of closed Todo instances
        """
        return [todo for todo in self._todos if todo.state == TodoState.CLOSED]

    @property
    @talk2py.command
    def current_todo(self) -> Optional[Todo]:
        """Get the current todo."""
        return self._current_todo

    @current_todo.setter
    @talk2py.command
    def current_todo(self, value: int) -> Optional[Todo]:
        """Set the current todo.

        Args:
            value: The id of the todo that should be set as current
        """
        if value < 0:
            self._current_todo = None
        else:
            todo = self.get_todo(value)
            self._current_todo = todo

        return self._current_todo

    @talk2py.command
    def next_todo(self) -> Optional[Todo]:
        """Get the next todo item in the list.

        Returns:
            The next Todo instance or None if there are no active todos
        """
        active_todos = self.get_active_todos()
        if not active_todos:
            self.current_todo = -1
            return None

        if self.current_todo is None:
            # If no current todo, return the first active todo
            self.current_todo = active_todos[0].id
            return self.current_todo

        # Find the current todo in the active list
        try:
            current_index = active_todos.index(self._current_todo)
            # Get the next todo, wrapping around to the beginning if needed
            next_index = (current_index + 1) % len(active_todos)
            self.current_todo = active_todos[next_index].id
            return self.current_todo
        except ValueError:
            # Current todo is not in active list (might be completed)
            self.current_todo = active_todos[0].id
            return self.current_todo


# Initialize the global TodoList object
TODO_LIST: Optional[TodoList] = None


@talk2py.command
def init_todolist_app() -> TodoList:
    """Initialize the todolist app and set the initial conversation context."""
    global TODO_LIST  # pylint: disable=global-statement

    if not TODO_LIST:
        TODO_LIST = TodoList()

        # Set the current application folder path
        app_path = os.path.dirname(os.path.abspath(__file__))
        CHAT_CONTEXT.register_app(app_path)

        # focus starts out on the todolist
        CHAT_CONTEXT.current_object = TODO_LIST

    return TODO_LIST


def how_to_use() -> None:
    """Example usage of the TodoList and Todo classes."""
    # Create a new todo list
    todo_list = init_todolist_app()

    # Add some todos
    todo1 = todo_list.add_todo("Complete the project documentation")
    _ = todo_list.add_todo("Review pull requests")
    _ = todo_list.add_todo("Update dependencies")

    # Mark some todos as complete
    todo1.close()

    # Print all todos
    print("All todos:")
    print(todo_list)

    # Print active todos
    print("\nActive todos:")
    for todo in todo_list.get_active_todos():
        print(todo)

    # Print closed todos
    print("\nClosed todos:")
    for todo in todo_list.get_closed_todos():
        print(todo)


if __name__ == "__main__":
    how_to_use()
