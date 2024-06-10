"""Tools for analyzing Python code."""

from _ast import AsyncFor
import argparse
import ast
from typing import Any, Dict
from pydantic import BaseModel


class Parameter(BaseModel):
    name: str
    type: str


class Function(BaseModel):
    name: str
    doc: str
    parameters: list[Parameter]
    return_type: str
    source: str


class Module(BaseModel):
    name: str
    doc: str
    top_level_functions: list[Function]
    top_level_calls: list[str]
    global_vars: Dict[str, Any]


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Python Code")
    parser.add_argument("filepath", help="The Python file to analyze")
    args = parser.parse_args()
    file = args.filepath
    tree = ast.parse(open(file).read())
    module = get_module(file, tree)
    print(module)


def analyze_module(file: str) -> Module:
    with open(file) as f:
        try:
            tree = ast.parse(f.read())
            return get_module(file, tree)
        except Exception as e:
            return Module(
                name=file,
                doc=f"{type(e).__name__} encountered when parsing",
                top_level_functions=[],
                top_level_calls=[],
                global_vars={},
            )


def get_module(path: str, tree: ast.Module) -> Module:
    return Module(
        name=path,
        doc=ast.get_docstring(tree) or "",
        top_level_functions=get_module_function_definitions(tree),
        top_level_calls=get_top_level_function_calls(tree),
        global_vars=extract_global_vars(tree),
    )


def extract_global_vars(tree: ast.Module) -> Dict[str, Any]:
    assignment_nodes = []
    for n in tree.body:
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name):
            assignment_nodes.append(n)
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            assignment_nodes.append(n)

    variable_dict = {}
    for node in assignment_nodes:

        if isinstance(node, ast.AnnAssign):
            ref = node.target.id
            value = node.value
        elif isinstance(node, ast.Assign):
            ref = node.targets[0].id
            value = node.value

        if isinstance(value, (ast.Constant, ast.List, ast.Tuple)):
            assignment_value = ast.literal_eval(value)
        elif isinstance(value, ast.Dict):
            assignment_value = {}
            for key, val in zip(value.keys, value.values):
                if isinstance(val, (ast.Constant, ast.List, ast.Tuple, ast.Dict)):
                    assignment_value[ast.literal_eval(key)] = ast.literal_eval(val)
                else:
                    assignment_value[ast.literal_eval(key)] = str(val)
        else:
            assignment_value = None

        variable_dict[ref] = assignment_value

    return variable_dict


def get_module_function_definitions(tree: ast.AST) -> list[Function]:
    class FunctionCollector(ast.NodeVisitor):
        def __init__(self):
            self.functions: list[Function] = []

        def visit_ClassDef(self, node: ast.ClassDef):
            # Not looking for method definitions
            ...

        def visit_FunctionDef(self, node: ast.FunctionDef):
            ast_params = node.args.args
            parameters = [
                Parameter(name=param.arg, type=self._get_param_type(param.annotation))
                for param in ast_params
            ]
            self.functions.append(
                Function(
                    name=node.name,
                    doc=ast.get_docstring(node) or "",
                    parameters=parameters,
                    return_type=self._get_return_type(node.returns),
                    source=ast.unparse(node),
                )
            )

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
            return self.visit_FunctionDef(node)  # type: ignore

        def _get_param_type(self, node: ast.expr | None) -> str:
            if node is None:
                return "Any"
            elif isinstance(node, ast.Name):
                return node.id
            elif isinstance(node, ast.Constant):
                return str(node.value)
            else:
                return "UnsupportedParamType"

        def _get_return_type(self, node: ast.expr | None) -> str:
            if isinstance(node, ast.Name):
                return node.id
            elif isinstance(node, ast.Constant):
                return str(node.value)
            else:
                return "UnsupportedReturnType"

    function_collector = FunctionCollector()
    function_collector.visit(tree)
    return function_collector.functions


def get_top_level_function_calls(tree: ast.AST) -> list[str]:
    class FunctionCallCollector(ast.NodeVisitor):
        def __init__(self):
            self.function_calls: list[str] = []

        def visit_Call(self, node: ast.Call):
            self.function_calls.append(ast.unparse(node.func))

        def visit_ClassDef(self, node: ast.ClassDef) -> Any:
            # Only looking for top-level function calls
            ...

        def visit_FunctionDef(self, node: ast.FunctionDef):
            # Only looking for top-level function calls
            ...

        def visit_For(self, node: ast.For):
            # Only looking for top-level function calls
            ...

        def visit_AsyncFor(self, node: AsyncFor) -> Any:
            # Only looking for top-level function calls
            ...

        def visit_If(self, node: ast.If):
            # Only looking for top-level function calls
            ...

        def visit_While(self, node: ast.While):
            # Only looking for top-level function calls
            ...

        def visit_AsyncWith(self, node: ast.AsyncWith):
            # Only looking for top-level function calls
            ...

        def visit_Match(self, node: ast.Match):
            # Only looking for top-level function calls
            ...

    function_call_collector = FunctionCallCollector()
    function_call_collector.visit(tree)
    return function_call_collector.function_calls


if __name__ == "__main__":
    main()
