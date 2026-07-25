"""A pytest plugin that emits stable, structured Trailhead test events."""

from __future__ import annotations

from collections.abc import Callable
import json
from pathlib import Path
import re
import time
from typing import Any

import pytest

from .pytest_protocol import (
    MAX_METADATA_BYTES,
    MAX_NODE_ID_BYTES,
    limited_text,
)

EventEmitter = Callable[[str, dict[str, Any]], None]
MAX_COLLECTION_BYTES = 512 * 1024
MAX_MARKERS = 256
_TRACEBACK_FILE = re.compile(
    r'^(?:E\s+)?\s*File "(?P<path>.+)", line (?P<line>\d+)\s*$',
    re.MULTILINE,
)


def _portable_path(value: object) -> str:
    """Normalize a pytest path for a platform-independent browser payload."""

    path = Path(str(value))
    if path.is_absolute():
        try:
            path = path.resolve().relative_to(Path.cwd().resolve())
        except ValueError:
            pass
    return str(path).replace("\\", "/")


def _location(value: object) -> tuple[str | None, int | None]:
    """Extract a one-based source location from a pytest location tuple."""

    if not isinstance(value, tuple) or len(value) < 2:
        return None, None
    path = _portable_path(value[0])
    line = value[1]
    return path, line + 1 if isinstance(line, int) else None


def _project_source_path(value: str) -> tuple[Path, str] | None:
    """Resolve a traceback filename only when it belongs to this project."""

    project_root = Path.cwd().resolve()
    path = Path(value)
    candidate = path if path.is_absolute() else project_root / path
    try:
        resolved = candidate.resolve()
        relative = resolved.relative_to(project_root)
    except (OSError, ValueError):
        return None
    if not resolved.is_file():
        return None
    return resolved, relative.as_posix()


def _source_caret(source: str, column: int, end_column: int | None) -> str:
    """Build a caret that preserves tab alignment in the original source."""

    prefix = source[: max(column - 1, 0)]
    padding = "".join("\t" if character == "\t" else " " for character in prefix)
    width = max((end_column or column + 1) - column, 1)
    return f"{padding}{'^' * width}"


def _syntax_error_data(longrepr: str) -> dict[str, Any] | None:
    """Recover a concise, structured SyntaxError from a project source file."""

    file_matches = list(_TRACEBACK_FILE.finditer(longrepr))
    for match in reversed(file_matches):
        resolved_path = _project_source_path(match.group("path"))
        if resolved_path is None:
            continue
        source_path, display_path = resolved_path
        try:
            source_bytes = source_path.read_bytes()
            compile(source_bytes, str(source_path), "exec")
        except SyntaxError as error:
            line = error.lineno if isinstance(error.lineno, int) else None
            column = error.offset if isinstance(error.offset, int) else None
            end_column = error.end_offset if isinstance(error.end_offset, int) else None
            source = (error.text or "").rstrip("\r\n")
            message = f"{type(error).__name__}: {error.msg}"

            location = display_path
            if line is not None:
                location += f":{line}"
                if column is not None:
                    location += f":{column}"
            details_parts = [location]
            if source:
                details_parts.append(source)
                if column is not None:
                    details_parts.append(_source_caret(source, column, end_column))
            details_parts.append(message)

            bounded: dict[str, str] = {}
            truncated: list[str] = []
            for field, value in (
                ("message", message),
                ("path", display_path),
                ("source", source),
                ("details", "\n".join(details_parts)),
            ):
                bounded[field], was_truncated = limited_text(value)
                if was_truncated:
                    truncated.append(field)
            return {
                "kind": "collection",
                **bounded,
                "line": line,
                "column": column,
                "end_column": end_column,
                "truncated": truncated,
            }
        except OSError:
            continue
    return None


def _bounded_optional_text(
    value: object | None, limit: int = MAX_METADATA_BYTES
) -> tuple[str | None, bool]:
    """Bound optional browser metadata without changing a missing value."""

    if value is None:
        return None, False
    return limited_text(value, limit)


def _is_safe_node_id(node_id: object) -> bool:
    """Return whether an opaque node ID can be carried losslessly."""

    return (
        isinstance(node_id, str)
        and bool(node_id)
        and len(node_id.encode("utf-8", errors="replace")) <= MAX_NODE_ID_BYTES
    )


def _bounded_markers(item: pytest.Item) -> tuple[list[str], bool]:
    """Return marker names with bounded count and combined serialized size."""

    markers: list[str] = []
    seen: set[str] = set()
    encoded_size = len(b"[]")
    truncated = False
    for index, mark in enumerate(item.iter_markers()):
        if index >= MAX_MARKERS:
            truncated = True
            break
        name, name_truncated = limited_text(mark.name, MAX_METADATA_BYTES)
        if name in seen:
            continue
        encoded_name = json.dumps(
            name, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        next_size = encoded_size + len(encoded_name) + (1 if markers else 0)
        if next_size > MAX_METADATA_BYTES:
            truncated = True
            break
        markers.append(name)
        seen.add(name)
        encoded_size = next_size
        if name_truncated:
            truncated = True
            break
    return sorted(markers), truncated


def _test_metadata(item: pytest.Item, node_id: str) -> dict[str, Any]:
    """Build bounded display metadata around an exact, safe node ID."""

    path, line = _location(item.location)
    name, name_truncated = limited_text(item.name, MAX_METADATA_BYTES)
    path, path_truncated = _bounded_optional_text(path)
    markers, markers_truncated = _bounded_markers(item)
    truncated = [
        field
        for field, was_truncated in (
            ("name", name_truncated),
            ("path", path_truncated),
            ("markers", markers_truncated),
        )
        if was_truncated
    ]
    return {
        "node_id": node_id,
        "name": name,
        "path": path,
        "line": line,
        "markers": markers,
        "truncated": truncated,
    }


def _fallback_test_metadata(
    node_id: str, location: tuple[str | Path, int, str]
) -> dict[str, Any]:
    """Build bounded metadata if pytest did not expose the item at collection."""

    path, line = _location(location)
    name, name_truncated = limited_text(node_id.rsplit("::", 1)[-1], MAX_METADATA_BYTES)
    path, path_truncated = _bounded_optional_text(path)
    return {
        "node_id": node_id,
        "name": name,
        "path": path,
        "line": line,
        "markers": [],
        "truncated": [
            field
            for field, was_truncated in (
                ("name", name_truncated),
                ("path", path_truncated),
            )
            if was_truncated
        ],
    }


def _longrepr_text(report: pytest.TestReport) -> str:
    if not report.longrepr:
        return ""
    try:
        return report.longreprtext
    except Exception:
        return str(report.longrepr)


def _failure_details(
    report: pytest.TestReport,
) -> tuple[str, str | None, int | None]:
    """Return a concise message and best failure location for one phase."""

    representation = report.longrepr
    crash = getattr(representation, "reprcrash", None)
    message = getattr(crash, "message", None)
    path = getattr(crash, "path", None)
    line = getattr(crash, "lineno", None)

    longrepr = _longrepr_text(report)
    if (
        report.skipped
        and isinstance(representation, tuple)
        and len(representation) >= 3
    ):
        path, line, message = representation[:3]
    if not message:
        message = next(
            (candidate for candidate in reversed(longrepr.splitlines()) if candidate),
            report.outcome,
        )
    if path is None or line is None:
        report_path, report_line = _location(report.location)
        path = path or report_path
        line = line or report_line
    return str(message), _portable_path(path) if path is not None else None, line


def _phase_outcome(report: pytest.TestReport) -> str:
    """Normalize pytest's outcome and wasxfail combination."""

    was_xfail = getattr(report, "wasxfail", None)
    if was_xfail:
        if report.skipped:
            return "xfailed"
        if report.passed:
            return "xpassed"

    # Strict XPASS is represented as a failed call rather than a passed one.
    if report.failed and _longrepr_text(report).startswith("[XPASS(strict)]"):
        return "xpassed"
    return report.outcome


def _phase(
    report: pytest.TestReport, previous_capture: dict[str, str]
) -> dict[str, Any]:
    """Normalize one public TestReport into a JSON-compatible phase."""

    message, path, line = _failure_details(report)
    capture = {
        "stdout": report.capstdout,
        "stderr": report.capstderr,
        "log": report.caplog,
    }
    for name, value in capture.items():
        previous = previous_capture[name]
        previous_capture[name] = value
        if previous and value.startswith(previous):
            capture[name] = value[len(previous) :]
    values = {
        "message": message if not report.passed else "",
        "longrepr": _longrepr_text(report),
        **capture,
    }
    truncated: list[str] = []
    normalized: dict[str, str] = {}
    for name, value in values.items():
        text, was_truncated = limited_text(value)
        normalized[name] = text
        if was_truncated:
            truncated.append(name)
    path, path_truncated = _bounded_optional_text(path)
    reason, reason_truncated = limited_text(
        getattr(report, "wasxfail", "")
        or (normalized["message"] if report.skipped else ""),
        MAX_METADATA_BYTES,
    )
    if path_truncated:
        truncated.append("path")
    if reason_truncated:
        truncated.append("reason")

    return {
        "phase": report.when,
        "outcome": _phase_outcome(report),
        "duration": report.duration,
        "message": normalized["message"],
        "longrepr": normalized["longrepr"],
        "path": path,
        "line": line,
        "reason": reason,
        "stdout": normalized["stdout"],
        "stderr": normalized["stderr"],
        "log": normalized["log"],
        "truncated": truncated,
    }


def _aggregate_outcome(phases: list[dict[str, Any]]) -> str:
    """Choose one display outcome after setup, call, and teardown complete."""

    for phase in phases:
        if phase["phase"] in {"setup", "teardown"} and phase["outcome"] == "failed":
            return "error"

    call = next((phase for phase in phases if phase["phase"] == "call"), None)
    if call is not None:
        return str(call["outcome"])

    for outcome in ("xfailed", "skipped"):
        if any(phase["outcome"] == outcome for phase in phases):
            return outcome
    return "error"


class TrailheadPytestPlugin:
    """Collect and publish pytest data without parsing terminal output."""

    def __init__(
        self,
        emit: EventEmitter,
        mode: str,
        *,
        emit_collection: bool | None = None,
    ) -> None:
        self._emit = emit
        self._mode = mode
        self._emit_collection = (
            mode == "collect" if emit_collection is None else emit_collection
        )
        self._started_at = time.monotonic()
        self._tests: dict[str, dict[str, Any]] = {}
        self._reports: dict[str, list[pytest.TestReport]] = {}
        self._summary = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "xfailed": 0,
            "xpassed": 0,
            "error": 0,
        }
        self._collection_errors = 0
        self._collection_truncated = False
        self._collection_display_truncated = False
        self._unsafe_node_id_diagnostic_emitted = False
        self._internal_error = False
        self._finished = False

    @pytest.hookimpl
    def pytest_collection_finish(self, session: pytest.Session) -> None:
        tests: list[dict[str, Any]] = []
        encoded_size = len(b"[]")
        display_budget_exhausted = False
        unsafe_node_ids = 0
        for item in session.items:
            node_id = item.nodeid
            if not _is_safe_node_id(node_id):
                unsafe_node_ids += 1
                self._collection_display_truncated = True
                continue

            test = _test_metadata(item, node_id)
            # Keep bounded metadata for every individually safe test so a run
            # result can still be displayed even when the collection list is
            # too large to send as one event.
            self._tests[node_id] = test
            if display_budget_exhausted:
                continue
            encoded_test = json.dumps(
                test, ensure_ascii=False, separators=(",", ":")
            ).encode("utf-8")
            next_size = encoded_size + len(encoded_test) + (1 if tests else 0)
            if next_size > MAX_COLLECTION_BYTES:
                self._collection_display_truncated = True
                display_budget_exhausted = True
                continue
            tests.append(test)
            encoded_size = next_size

        if unsafe_node_ids:
            noun = "test has" if unsafe_node_ids == 1 else "tests have"
            pronoun = "Its" if unsafe_node_ids == 1 else "Their"
            result_noun = "result" if unsafe_node_ids == 1 else "results"
            self._emit(
                "TEST_ERROR",
                {
                    "kind": "collection",
                    "message": (
                        f"{unsafe_node_ids} collected {noun} a node ID larger than "
                        f"the {MAX_NODE_ID_BYTES}-byte protocol limit. {pronoun} "
                        f"individual {result_noun} will be omitted."
                    ),
                },
            )
            self._unsafe_node_id_diagnostic_emitted = True
        if display_budget_exhausted:
            self._emit(
                "TEST_ERROR",
                {
                    "kind": "collection",
                    "message": (
                        "The collected test list is too large to display completely"
                    ),
                },
            )

        # Collection-only operations should surface display truncation as their
        # terminal status. A real run must retain pytest's passed/failed status.
        self._collection_truncated = (
            self._mode == "collect" and self._collection_display_truncated
        )
        self._summary["total"] = len(session.items)
        if self._emit_collection:
            self._emit(
                "TESTS_COLLECTED",
                {
                    "tests": tests,
                    "total": len(session.items),
                    "truncated": self._collection_display_truncated,
                },
            )

    @pytest.hookimpl
    def pytest_collectreport(self, report: pytest.CollectReport) -> None:
        if not report.failed:
            return
        self._collection_errors += 1
        raw_longrepr = str(report.longrepr)
        syntax_error = _syntax_error_data(raw_longrepr)
        if syntax_error is not None:
            self._emit("TEST_ERROR", syntax_error)
            return
        longrepr, was_truncated = limited_text(raw_longrepr)
        path, line = _location(getattr(report, "location", None))
        path, path_truncated = _bounded_optional_text(path)
        message = next(
            (candidate for candidate in reversed(longrepr.splitlines()) if candidate),
            "Unable to collect tests",
        )
        self._emit(
            "TEST_ERROR",
            {
                "kind": "collection",
                "message": message,
                "path": path,
                "line": line,
                "details": longrepr,
                "truncated": [
                    field
                    for field, truncated in (
                        ("details", was_truncated),
                        ("path", path_truncated),
                    )
                    if truncated
                ],
            },
        )

    @pytest.hookimpl
    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        if report.when not in {"setup", "call", "teardown"}:
            return
        self._reports.setdefault(report.nodeid, []).append(report)

    @pytest.hookimpl
    def pytest_runtest_logfinish(
        self, nodeid: str, location: tuple[str | Path, int, str]
    ) -> None:
        reports = self._reports.pop(nodeid, [])
        if not reports:
            return
        previous_capture = {"stdout": "", "stderr": "", "log": ""}
        phases = [_phase(report, previous_capture) for report in reports]
        outcome = _aggregate_outcome(phases)
        self._summary[outcome] += 1
        if not _is_safe_node_id(nodeid):
            if not self._unsafe_node_id_diagnostic_emitted:
                self._emit(
                    "TEST_ERROR",
                    {
                        "kind": "collection",
                        "message": (
                            "A pytest result was omitted because its node ID "
                            f"exceeds the {MAX_NODE_ID_BYTES}-byte protocol limit."
                        ),
                    },
                )
                self._unsafe_node_id_diagnostic_emitted = True
            return

        test = dict(self._tests.get(nodeid, _fallback_test_metadata(nodeid, location)))
        test.update(
            {
                "outcome": outcome,
                "duration": sum(report.duration for report in reports),
                "phases": phases,
            }
        )
        self._emit("TEST_RESULT", {"test": test})

    @pytest.hookimpl
    def pytest_internalerror(
        self,
        excrepr: Any,
        excinfo: pytest.ExceptionInfo[BaseException],
    ) -> None:
        self._internal_error = True
        details, details_truncated = limited_text(excrepr)
        message, message_truncated = limited_text(excinfo.value)
        self._emit(
            "TEST_ERROR",
            {
                "kind": "internal",
                "message": message,
                "details": details,
                "truncated": [
                    field
                    for field, truncated in (
                        ("message", message_truncated),
                        ("details", details_truncated),
                    )
                    if truncated
                ],
            },
        )

    def finish(self, exitstatus: int | pytest.ExitCode) -> None:
        """Emit the sole terminal event after ``pytest.main`` has returned."""

        if self._finished:
            return
        self._finished = True
        exit_code = int(exitstatus)
        if self._internal_error or exit_code == int(pytest.ExitCode.INTERNAL_ERROR):
            status = "internal_error"
        elif self._collection_errors:
            status = "collection_error"
        elif self._collection_truncated:
            status = "collection_truncated"
        elif exit_code == int(pytest.ExitCode.OK):
            status = "collected" if self._mode == "collect" else "passed"
        elif exit_code == int(pytest.ExitCode.TESTS_FAILED):
            status = "failed"
        elif exit_code == int(pytest.ExitCode.INTERRUPTED):
            status = "interrupted"
        elif exit_code == int(pytest.ExitCode.USAGE_ERROR):
            status = "usage_error"
        elif exit_code == int(pytest.ExitCode.NO_TESTS_COLLECTED):
            status = "no_tests"
        else:
            status = "error"
        self._emit(
            "TEST_RUN_FINISHED",
            {
                "exit_code": exit_code,
                "status": status,
                "duration": time.monotonic() - self._started_at,
                "summary": self._summary,
                "cancelled": False,
                "collection_truncated": self._collection_display_truncated,
            },
        )
