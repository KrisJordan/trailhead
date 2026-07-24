# Pytest UI Support Plan

## Goal

When a user opens a Python module containing pytest tests, Trailhead should
present a dedicated Tests UI that:

- lists the tests pytest actually collects;
- runs one test or every test in the module;
- reports pass, fail, skip, xfail, xpass, collection, fixture, and internal
  error states in a structured, readable form;
- captures useful assertion details and standard output/error; and
- optionally reruns all tests after detected Python source changes.

## Existing foundations and constraints

Trailhead already has:

- static AST-based module inspection;
- one isolated Python child process per run WebSocket;
- portable process-tree cleanup on macOS, Windows, and Linux;
- a project-wide watchdog observer for Python file changes; and
- Redux middleware for application and run WebSockets.

The implementation must account for these constraints:

- pytest is currently a development-only dependency, so installed/student
  runtimes do not necessarily have it;
- the existing run protocol is unstructured stdout/stderr and cannot represent
  pytest collection and phase results cleanly;
- the current frontend reacts to every `file_modified` message by reloading the
  route, which conflates metadata refresh and process reruns;
- pytest collection imports test modules and may fail before any test runs; and
- parametrized cases require preserving opaque pytest node IDs rather than
  reconstructing selectors from function names.

## Recommended architecture

### Test-module detection

Extend static module metadata with `is_pytest_candidate`. A module is a
candidate when its filename follows standard pytest conventions or its AST
contains a top-level `test_*` function or `Test*` class with `test_*` methods.
This classification only selects the UI; an isolated pytest collection remains
the source of truth.

### Runtime and backend

Move a bounded pytest version into Trailhead's runtime dependencies. Add a
Trailhead pytest wrapper/plugin that calls `pytest.main()` in the existing child
process isolation boundary and reports normalized JSON events from public pytest
collection and reporting hooks.

Add a long-lived `/ws/{module}/tests` WebSocket with this command/event contract:

| Direction | Event | Purpose |
| --- | --- | --- |
| Client to server | `TEST_COLLECT` | Collect tests without running |
| Client to server | `TEST_RUN` | Run the module or selected collected node IDs |
| Client to server | `TEST_CANCEL` | Stop the active child process |
| Server to client | `TESTS_COLLECTED` | Collected node IDs and source metadata |
| Server to client | `TEST_RUN_STARTED` | Identify a new run |
| Server to client | `TEST_RESULT` | Report one normalized test result |
| Server to client | `TEST_RUN_FINISHED` | Report summary and pytest exit state |
| Server to client | `TEST_ERROR` | Report collection, usage, or internal errors |

Every command and response carries a client-generated `run_id`. The server
validates module paths and selected node IDs, passes arguments directly without
a shell, and limits large captured-output fields.

### Frontend

Add:

- a `tests` route and conditional Tests tab;
- Tests as the default tool for pytest candidates;
- a Redux test slice for collection, execution, results, errors, and autorun;
- dedicated test-socket middleware; and
- components for the toolbar, summary, test rows, failures, and captured output.

The Tests UI should keep Run and Interact available. It should display:

- Run All, per-test Run, and Cancel controls;
- per-test outcome and duration;
- setup, call, and teardown failure phases;
- a concise failure location/message and pytest assertion representation;
- collapsible captured stdout, stderr, and log output; and
- collection/internal errors separately from test failures.

### File changes and autorun

Replace route navigation on file-change messages with explicit Redux
`projectPythonChanged` actions. Normalize watcher paths to project-relative
POSIX paths.

Autorun should:

- be off by default and persisted in browser local storage;
- react to any project Python file change, since implementation modules matter;
- debounce save bursts;
- run all tests in the currently open test module;
- queue one rerun if a run is already active instead of killing pytest during
  fixture setup/teardown;
- ignore stale responses using `run_id`; and
- pause with a warning after repeated rapid reruns to prevent loops caused by
  tests that write Python files.

## Delivery sequence

1. Add candidate detection, pytest runtime support, child wrapper/plugin, typed
   messages, collection, run-all, run-one, and cancellation.
2. Add the Tests route, Redux state/middleware, collection list, controls,
   summaries, and failure/output rendering.
3. Refactor file-change handling and add debounced, queued, persistent autorun.
4. Harden collection/import errors, fixture phases, output limits, stale event
   handling, invalid selectors, and process cleanup.
5. Document supported behavior and verify server tests, Ruff, Pyright, client
   tests, TypeScript, and production client build.

## Acceptance criteria

- Opening a standard pytest module selects a Tests UI and lists collected cases,
  including parametrized cases.
- Run All executes only that module; Run executes only the selected opaque node
  ID.
- Test outcomes update without parsing terminal progress text.
- Assertion failures, exceptions, fixture failures, collection errors, and
  captured output are readable and distinguishable.
- Autorun is user-controlled, debounced, runs on relevant Python changes, and
  coalesces changes received during a run.
- A stale or cancelled run cannot overwrite a newer run.
- Missing modules and invalid/cross-module selectors fail closed.
- Child processes and descendants are cleaned up on cancel, disconnect, and
  server shutdown.
- Existing Run, Interact, and GUI behavior remains covered and functional.
- Full Python and client verification succeeds on the feature branch.
