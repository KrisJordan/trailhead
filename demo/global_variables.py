"""A file with a function that demonstrates the difference between print vs return."""


def demo(name: str) -> str:
    """Print vs return."""
    # The following line is printed
    print(f"Hello, {name}. This value was printed to standard output.")
    # The following line returns a value to the call expression
    return f"Hi again {name}. This value was returned from the `demo` function call."


a: str = "Hello, world"
b: bool = True
c: int = 123
d: float = 123.456
d_0: float = 123.0
e: None = None
f: list[str] = ["Hello", "world", "this", "is", "a", "test"]
f_0: list[int] = [i for i in range(100)]
g: dict[str, int] = {"Hello": 123, "world": 456}
h: set[int] = {1, 2, 3}
i: range = range(10)
