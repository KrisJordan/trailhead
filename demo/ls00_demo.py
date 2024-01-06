"""Simple Point class defined with a factory."""


class Point:
    def __init__(self, x: int, y: int):
        self.x: int = x
        self.y: int = y


def point_factory(x: int, y: int) -> Point:
    """TODO: Support list/generic types in params and return type."""
    return Point(x, y)
