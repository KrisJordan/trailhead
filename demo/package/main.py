"""A demo that imports from a relative module in the package."""

import sys

from .module import a_function

if __name__ == "__main__":
    print(a_function())
    print("Goodbye from main.py!")
    sys.exit(0)
