"""Evaluate a function call in a user's module."""

from __future__ import annotations

import importlib
import sys
from typing import Any

from ._traceback import emit_exception

if len(sys.argv) < 3:
    raise RuntimeError(
        "A module name and function call must be passed to this wrapper."
    )

module_name = sys.argv[1]


def audit_hook(event: str, args: tuple[Any, ...]) -> None:
    if event == "builtins.input":
        prompt_length = len(str(args[0]).encode("utf-8"))
        sys.stdout.buffer.write(b"\xff\xff\xff\xff" + f"{prompt_length}\n".encode())
        sys.stdout.flush()


sys.addaudithook(audit_hook)

try:
    module = importlib.import_module(module_name)
    function_call = sys.argv[2]
    print(eval(f"module.{function_call}"))
except Exception as error:
    emit_exception(error)
    raise SystemExit(1) from None
