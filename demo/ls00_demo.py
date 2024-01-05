class Point:
    def __init__(self, x: int, y: int):
        self.x: int = x
        self.y: int = y


def show_call(x: int, y: int) -> str:
    """Returns a string with the sum of the two given integers."""
    rv: str = f"{x} + {y} = {x + y}"
    return rv


def make_point(x: int, y: int) -> Point:
    """TODO: Support list/generic types."""
    return Point(x, y)


print("Done")
