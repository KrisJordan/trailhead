"""Some simple function definitions without calls!"""


def hello() -> None:
    """Prints "Hello"."""
    print("Hello")


def single_param(x: int) -> None:
    """Prints the given parameter."""
    print(x)


def lifes_answer() -> int:
    """Returns the integer 42."""
    return 42


def add(x: int, y: int) -> int:
    """Returns the sum of the two given integers."""
    return x + y
