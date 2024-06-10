"""GUI"""

__framework__: str = "./my_bundle.js"
__template__ = "https://example.com/"
x: int = 0


def my_func() -> list[str]:
    global x
    x += 1
    return ["hallo", "there", x]
