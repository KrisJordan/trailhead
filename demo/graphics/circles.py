"""A program to generate some circles."""
from trailhead.graphics import Shape, Circle

__trailhead__ = "art"


def main() -> Shape:
    return Circle(x=0.0, y=0.0, radius=10.0)


if __name__ == "__main__":
    main()
