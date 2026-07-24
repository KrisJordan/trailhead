from __future__ import annotations

from pathlib import Path

import pytest

from trailhead.analysis.inspect import analyze_module


@pytest.mark.parametrize("line_ending", ["\n", "\r\n"])
def test_module_analysis_detects_main_guard(tmp_path: Path, line_ending: str) -> None:
    source = line_ending.join(
        [
            "def main():",
            '    print("hello")',
            "",
            'if __name__ == "__main__":',
            "    main()",
            "",
        ]
    )
    module_path = tmp_path / "guarded.py"
    module_path.write_bytes(source.encode("utf-8"))

    module = analyze_module(str(module_path))

    assert module.has_main_guard
    assert [function.name for function in module.top_level_functions] == ["main"]
    assert module.top_level_calls == []


def test_module_analysis_does_not_treat_other_conditionals_as_main_guard(
    tmp_path: Path,
) -> None:
    module_path = tmp_path / "conditional.py"
    module_path.write_text(
        "DEBUG = False\n\ndef main():\n    pass\n\nif DEBUG:\n    main()\n",
        encoding="utf-8",
    )

    module = analyze_module(str(module_path))

    assert not module.has_main_guard
    assert [function.name for function in module.top_level_functions] == ["main"]
    assert module.top_level_calls == []


def test_async_function_body_is_not_top_level_execution(tmp_path: Path) -> None:
    module_path = tmp_path / "async_definitions.py"
    module_path.write_text(
        'async def greet():\n    print("hello")\n',
        encoding="utf-8",
    )

    module = analyze_module(str(module_path))

    assert not module.has_main_guard
    assert [function.name for function in module.top_level_functions] == ["greet"]
    assert module.top_level_calls == []
