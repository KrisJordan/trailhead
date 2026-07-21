"""Execute a user's module and report structured exceptions."""

from __future__ import annotations

import runpy
import sys
from typing import Any

from ._traceback import emit_exception

if len(sys.argv) < 2:
    raise RuntimeError(
        "The module name must be passed as first argument to this wrapper."
    )

module_name = sys.argv[1]


def audit_hook(event: str, args: tuple[Any, ...]) -> None:
    if event == "builtins.input":
        prompt_length = len(str(args[0]).encode("utf-8"))
        sys.stdout.buffer.write(b"\xff\xff\xff\xff" + f"{prompt_length}\n".encode())
        sys.stdout.flush()


sys.addaudithook(audit_hook)

try:
    runpy.run_module(module_name, run_name="__main__", alter_sys=True)
except Exception as error:
    emit_exception(error, root_module=module_name)
    raise SystemExit(1) from None
