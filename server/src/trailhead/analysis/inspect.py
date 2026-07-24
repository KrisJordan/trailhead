"""Tools for analyzing Python code."""

from _ast import AsyncFor
import argparse
import ast
from pathlib import Path
import tokenize
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
    has_main_guard: bool = False
    is_pytest_candidate: bool = False


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Python Code")
    parser.add_argument("filepath", help="The Python file to analyze")
    args = parser.parse_args()
    file = args.filepath
    with tokenize.open(file) as source:
        tree = ast.parse(source.read())
    module = get_module(file, tree)
    print(module)


def analyze_module(file: str) -> Module:
    with tokenize.open(file) as source:
        try:
            tree = ast.parse(source.read())
            return get_module(file, tree)
        except Exception as e:
            return Module(
                name=file,
                doc=f"{type(e).__name__} encountered when parsing",
                top_level_functions=[],
                top_level_calls=[],
                global_vars={},
                has_main_guard=False,
                is_pytest_candidate=is_pytest_filename(file),
            )


def get_module(path: str, tree: ast.Module) -> Module:
    return Module(
        name=path,
        doc=ast.get_docstring(tree) or "",
        top_level_functions=get_module_function_definitions(tree),
        top_level_calls=get_top_level_function_calls(tree),
        global_vars=extract_global_vars(tree),
        has_main_guard=module_has_main_guard(tree),
        is_pytest_candidate=is_pytest_filename(path) or tree_has_pytest_tests(tree),
    )


def is_pytest_filename(path: str) -> bool:
    """Return whether a path follows pytest's default test-module conventions."""

    filename = Path(path).name
    return (filename.startswith("test_") or filename.endswith("_test.py")) and (
        filename.endswith(".py")
    )


def tree_has_pytest_tests(tree: ast.Module) -> bool:
    """Return whether an AST contains conventional top-level pytest tests."""

    for statement in tree.body:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if statement.name.startswith("test_"):
                return True
        elif isinstance(statement, ast.ClassDef) and statement.name.startswith("Test"):
            if any(
                isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
                and member.name.startswith("test_")
                for member in statement.body
            ):
                return True
    return False


def module_has_main_guard(tree: ast.Module) -> bool:
    """Return whether the module has a top-level ``__main__`` guard."""

    def is_name(node: ast.expr) -> bool:
        return isinstance(node, ast.Name) and node.id == "__name__"

    def is_main(node: ast.expr) -> bool:
        return isinstance(node, ast.Constant) and node.value == "__main__"

    for statement in tree.body:
        if not isinstance(statement, ast.If):
            continue
        test = statement.test
        if (
            isinstance(test, ast.Compare)
            and len(test.ops) == 1
            and isinstance(test.ops[0], ast.Eq)
            and len(test.comparators) == 1
            and (
                (is_name(test.left) and is_main(test.comparators[0]))
                or (is_main(test.left) and is_name(test.comparators[0]))
            )
        ):
            return True
    return False


def extract_global_vars(tree: ast.Module) -> Dict[str, Any]:
    assignment_nodes: list[ast.Assign | ast.AnnAssign] = []
    for n in tree.body:
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name):
            assignment_nodes.append(n)
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            assignment_nodes.append(n)

    variable_dict = {}
    for node in assignment_nodes:
        if isinstance(node, ast.AnnAssign):
            if not isinstance(node.target, ast.Name):
                continue
            ref = node.target.id
            value = node.value
        else:
            target = node.targets[0]
            if not isinstance(target, ast.Name):
                continue
            ref = target.id
            value = node.value

        if isinstance(value, (ast.Constant, ast.List, ast.Tuple)):
            assignment_value = ast.literal_eval(value)
        elif isinstance(value, ast.Dict):
            assignment_value = {}
            for key, val in zip(value.keys, value.values):
                if key is None:
                    continue
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

        def visit_FunctionDef(
            self, node: ast.FunctionDef | ast.AsyncFunctionDef
        ) -> None:
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

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self.visit_FunctionDef(node)

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

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
            # Async function bodies are definitions too, not top-level execution.
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
