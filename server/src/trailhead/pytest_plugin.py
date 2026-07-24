"""A pytest plugin that emits stable, structured Trailhead test events."""

from __future__ import annotations

from collections.abc import Callable
import json
from pathlib import Path
import time
from typing import Any

import pytest

from .pytest_protocol import limited_text

EventEmitter = Callable[[str, dict[str, Any]], None]
MAX_COLLECTION_BYTES = 512 * 1024


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

    return {
        "phase": report.when,
        "outcome": _phase_outcome(report),
        "duration": report.duration,
        "message": normalized["message"],
        "longrepr": normalized["longrepr"],
        "path": path,
        "line": line,
        "reason": str(
            getattr(report, "wasxfail", "")
            or (normalized["message"] if report.skipped else "")
        ),
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

    def __init__(self, emit: EventEmitter, mode: str) -> None:
        self._emit = emit
        self._mode = mode
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
        self._internal_error = False

    @pytest.hookimpl
    def pytest_collection_finish(self, session: pytest.Session) -> None:
        tests: list[dict[str, Any]] = []
        encoded_size = 0
        for item in session.items:
            path, line = _location(item.location)
            test = {
                "node_id": item.nodeid,
                "name": item.name,
                "path": path,
                "line": line,
                "markers": sorted({mark.name for mark in item.iter_markers()}),
            }
            self._tests[item.nodeid] = test
            encoded_size += len(json.dumps(test, ensure_ascii=False).encode("utf-8"))
            if encoded_size > MAX_COLLECTION_BYTES:
                self._collection_truncated = True
                self._emit(
                    "TEST_ERROR",
                    {
                        "kind": "collection",
                        "message": (
                            "The collected test list is too large to display completely"
                        ),
                    },
                )
                break
            tests.append(test)
        self._summary["total"] = len(session.items)
        if self._mode == "collect":
            self._emit(
                "TESTS_COLLECTED",
                {
                    "tests": tests,
                    "total": len(session.items),
                    "truncated": self._collection_truncated,
                },
            )

    @pytest.hookimpl
    def pytest_collectreport(self, report: pytest.CollectReport) -> None:
        if not report.failed:
            return
        self._collection_errors += 1
        longrepr, was_truncated = limited_text(report.longrepr)
        path, line = _location(getattr(report, "location", None))
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
                "truncated": ["details"] if was_truncated else [],
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
        test = dict(
            self._tests.get(
                nodeid,
                {
                    "node_id": nodeid,
                    "name": nodeid.rsplit("::", 1)[-1],
                    "path": _location(location)[0],
                    "line": _location(location)[1],
                    "markers": [],
                },
            )
        )
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
        details, was_truncated = limited_text(excrepr)
        self._emit(
            "TEST_ERROR",
            {
                "kind": "internal",
                "message": str(excinfo.value),
                "details": details,
                "truncated": ["details"] if was_truncated else [],
            },
        )

    @pytest.hookimpl
    def pytest_sessionfinish(
        self, session: pytest.Session, exitstatus: int | pytest.ExitCode
    ) -> None:
        exit_code = int(exitstatus)
        if self._internal_error:
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
            },
        )
