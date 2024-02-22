import sys
import traceback
import json
import ast
import inspect
from pydantic import BaseModel, RootModel, SerializeAsAny
from typing import Any
from types import FunctionType

if len(sys.argv) < 2:
    raise Exception("The module name must be passed as first argument to this wrapper.")

module_name = sys.argv[1]


def audit_hook(event: str, args: tuple[Any, ...]):
    if event == "builtins.input":
        sys.stdout.buffer.write(b"\xff\xff\xff\xff")
        sys.stdout.write(f"{len(args[0])}\n")


sys.addaudithook(audit_hook)

ValueList = RootModel[list[SerializeAsAny[BaseModel]]]
ValueDict = RootModel[dict[str, SerializeAsAny[BaseModel]]]


class NoneValue(BaseModel):
    type: str = "none"


class IntValue(BaseModel):
    type: str = "int"
    value: int


class FloatValue(BaseModel):
    type: str = "float"
    value: float


class StringValue(BaseModel):
    type: str = "str"
    value: str


class BoolValue(BaseModel):
    type: str = "bool"
    value: bool


class Parameter(BaseModel):
    name: str
    type: str
    default_value: Any | None


class Function(BaseModel):
    type: str = "function"
    name: str
    doc: str
    parameters: list[Parameter]
    return_type: str
    source: str


class ListValue(BaseModel):
    type: str = "list"
    items: list[SerializeAsAny[BaseModel]]


class DictValue(BaseModel):
    type: str = "dict"
    keys: list[SerializeAsAny[BaseModel]]
    values: list[SerializeAsAny[BaseModel]]


class UnknownValue(BaseModel):
    type: str = "unknown"
    python_type: str
    value: str


class Context(BaseModel):
    type: str = "context"
    values: dict[str, SerializeAsAny[BaseModel]]


def bundle_globals(kvs: dict[str, Any]) -> Context:
    filtered = {k: v for k, v in kvs.items() if not k.startswith("_")}
    results = {}
    for k, v in filtered.items():
        results[k] = decompose_value(v)
    return Context(values=results)


def decompose_value(value: Any) -> BaseModel:
    if isinstance(value, bool):
        return BoolValue(value=value)
    elif isinstance(value, int):
        return IntValue(value=value)
    elif isinstance(value, float):
        return FloatValue(value=value)
    elif isinstance(value, str):
        return StringValue(value=value)
    elif value is None:
        return NoneValue()
    elif isinstance(value, FunctionType):
        return decompose_function(value)
    elif isinstance(value, list):
        return ListValue(items=[decompose_value(v) for v in value])
    elif isinstance(value, dict):
        return DictValue(
            keys=[decompose_value(k) for k in value.keys()],
            values=[decompose_value(v) for v in value.values()],
        )
    else:
        return UnknownValue(python_type=type(value).__name__, value=repr(value))


def decompose_function(value: FunctionType) -> Function:
    parameters = []
    signature = inspect.signature(value)
    for name, param in signature.parameters.items():
        parameters.append(
            Parameter(
                name=name,
                type=getattr(param.annotation, "__name__", str(param.annotation))
                if param.annotation != inspect._empty
                else "Any",
                default_value=None
                if param.default is inspect._empty
                else param.default,
            )
        )
    return Function(
        type="function",
        name=value.__name__,
        doc=value.__doc__ or "",
        parameters=parameters,
        return_type=getattr(
            signature.return_annotation, "__name__", str(signature.return_annotation)
        ),
        source=inspect.getsource(value),
    )


def print_context(context: dict[str, Any]):
    filtered_globals = bundle_globals(context)
    sys.stderr.write(str(filtered_globals.model_dump_json()))
    sys.stderr.write("\n")
    sys.stderr.flush()


def exec_callback(result: Any, globals: dict[str, Any], statement_ast: ast.Module):
    # TODO: Interesting things in the event of statements such as:
    # 1. Assignment Statement - Print the value of the assigned variable and
    # name of variable
    # print(ast.dump(statement_ast))

    if result is not None:
        sys.stderr.write(f'{{"type": "expr_eval", "value": {decompose_value(result).model_dump_json()}}}')
        sys.stderr.write("\n")
        sys.stderr.flush()

    print_context(globals)


try:
    import importlib
    from .interact.repl import InteractiveConsole

    module = importlib.import_module(module_name)
    local_scope = vars(module).copy()
    console = InteractiveConsole(locals=local_scope, exec_callback=exec_callback)
    print_context(local_scope)
    console.interact(banner="")

except Exception as e:
    tb_info = traceback.extract_tb(e.__traceback__)
    frames = inspect.getinnerframes(e.__traceback__)  # type: ignore

    stack_trace: list[dict[str, Any]] = []

    info_frames = [frame for frame in tb_info]
    stack_frames = [frame for frame in frames]

    for i in range(len(info_frames)):
        frame = info_frames[i]
        stack_frame = stack_frames[i]

        if (
            frame.filename.startswith("/workspace/server")
            or frame.filename.startswith("/usr/lib")
            or frame.filename.startswith("<frozen importlib")
        ):
            continue

        arguments = inspect.getargvalues(stack_frame.frame)

        locals: dict[str, Any] = {}
        for local in stack_frame.frame.f_locals:
            value = stack_frame.frame.f_locals[local]
            try:
                json.dumps(value)
                locals[local] = value
                # except (TypeError, OverflowError):
                #     try:
                #         value_type = type(value)

                #             attributes = [
                #                 attr for attr in dir(value) if not attr.startswith("_")
                #             ]
                #             simple_object: dict[str, Any] = {}

                #             for attr in attributes:
                #                 simple_object[attr] = getattr(value, attr)

                #             locals[local] = {
                #                 "type": type(value).__name__,
                #                 "repr": attributes,
                #             }
                #         else:
                #             locals[local] = repr(value)
            except (TypeError, OverflowError):
                locals[local] = "[See value in Debugger]"
                continue

        stack_trace.append(
            {
                "filename": frame.filename.replace("/workspace/", ""),
                "lineno": frame.lineno,
                "name": frame.name,
                "line": "".join(stack_frame.code_context),  # type: ignore
                "end_lineno": frame.end_lineno,
                "colno": frame.colno,
                "end_colno": frame.end_colno,
                "locals": locals,
            }
        )

    error_info = {
        "type": type(e).__name__,
        "message": str(e),
        "stack_trace": stack_trace,
    }

    json_error_info = json.dumps(error_info)

    sys.stderr.write(f"{json_error_info}\n")
    sys.exit(1)
