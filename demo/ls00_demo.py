class Point:
    def __init__(self, x: int, y: int):
        self.x: int = x
        self.y: int = y


def show_call(x: int, y: int) -> str:
    """Returns a string with the sum of the two given integers."""
    rv: str = f"{x} + {y} = {x + y}"
    return rv


def point_factory(x: int, y: int) -> Point:
    """TODO: Support list/generic types in params and return type."""
    return Point(x, y)


print("Done")
