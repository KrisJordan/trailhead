"""Execute a Trailhead wrapper without using Python's ``-m`` switch."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main() -> None:
    """Restore the wrapper's argv and execute it with ``-m`` semantics."""

    wrapper = sys.argv.pop(1)
    sys.argv[0] = wrapper
    # Filename-based debuggers can replace sys.path[0] with this script's
    # directory. Restore the trusted package parent without weakening ``-P``.
    import_root = str(Path(__file__).resolve().parents[1])
    if not sys.path or sys.path[0] != import_root:
        try:
            sys.path.remove(import_root)
        except ValueError:
            pass
        sys.path.insert(0, import_root)
    runpy.run_module(wrapper, run_name="__main__", alter_sys=True)


if __name__ == "__main__":
    main()
