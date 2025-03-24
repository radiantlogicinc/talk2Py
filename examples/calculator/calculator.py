"""
Simple calculator module with basic arithmetic operations.
"""

from talk2py import command


@command
def add(a: int, b: int) -> int:
    """
    Add two numbers together.

    Args:
        a: First number
        b: Second number

    Returns:
        Sum of the two numbers
    """
    return a + b


@command
def subtract(a: int, b: int) -> int:
    """
    Subtract the second number from the first.

    Args:
        a: First number
        b: Second number

    Returns:
        Difference between the two numbers
    """
    return a - b


@command
def multiply(a: float, b: float) -> float:
    """
    Multiply two numbers together.

    Args:
        a: First number
        b: Second number

    Returns:
        Product of the two numbers
    """
    return a * b


@command
def divide(a: float, b: float) -> float:
    """
    Divide the first number by the second.

    Args:
        a: First number
        b: Second number

    Returns:
        Quotient of the division

    Raises:
        ZeroDivisionError: If the second number is zero
    """
    if b == 0:
        raise ZeroDivisionError("Cannot divide by zero")
    return a / b


def how_to_use():
    """
    Demonstrates how to use the calculator functions.
    """
    # Test the calculator functions
    print(f"Addition: 5 + 3 = {add(5, 3)}")
    print(f"Subtraction: 10 - 4 = {subtract(10, 4)}")
    print(f"Multiplication: 6 * 7 = {multiply(6, 7)}")

    try:
        print(f"Division: 15 / 3 = {divide(15, 3)}")
        print(f"Division by zero: 10 / 0 = {divide(10, 0)}")
    except ZeroDivisionError as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    how_to_use()
