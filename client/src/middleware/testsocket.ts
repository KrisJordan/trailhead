import type { Middleware } from "@reduxjs/toolkit";
import {
    CapturedTestOutput,
    CollectedTest,
    TestFailure,
    TestOutcome,
    TestPhase,
    TestPhaseResult,
    TestResult,
    TestRunError,
    TestSummary,
    TestsState,
    endTestSession,
    pauseTestAutorun,
    projectPythonChanged,
    resumeTestAutorun,
    setAutorunPending,
    setTestAutorun,
    startTestSession,
    testCancelRequested,
    testCollectionRequested,
    testResultReceived,
    testRunFailed,
    testRunFinished,
    testRunRequested,
    testRunStarted,
    testsCollected,
    updateTestReadyState,
} from "../features/tests";
import { parseJsonMessage } from "../Message";
import { ReadyState, Socket } from "../utils/Socket";

const AutorunDebounceMs = 400;
const AutorunWindowMs = 10_000;
const MaxAutorunsPerWindow = 5;

interface TestSocketRootState {
    tests: TestsState;
}

let runIdSequence = 0;

export function createTestRunId(): string {
    runIdSequence += 1;
    return `${Date.now().toString(36)}-${runIdSequence.toString(36)}`;
}

function record(value: unknown): Record<string, unknown> {
    return typeof value === "object" && value !== null
        ? value as Record<string, unknown>
        : {};
}

function stringValue(value: unknown): string | undefined {
    return typeof value === "string" ? value : undefined;
}

function numberValue(value: unknown): number | undefined {
    return typeof value === "number" && Number.isFinite(value)
        ? value
        : undefined;
}

function printable(value: unknown): string | undefined {
    if (typeof value === "string") {
        return value;
    }
    if (value === undefined || value === null) {
        return undefined;
    }
    try {
        return JSON.stringify(value, null, 2);
    } catch {
        return String(value);
    }
}

function normalizeOutcome(value: unknown): TestOutcome {
    switch (value) {
        case "passed":
        case "failed":
        case "skipped":
        case "xfailed":
        case "xpassed":
        case "error":
        case "cancelled":
            return value;
        default:
            return "error";
    }
}

function normalizePhase(value: unknown): TestPhase | undefined {
    switch (value) {
        case "setup":
        case "call":
        case "teardown":
        case "collection":
            return value;
        default:
            return undefined;
    }
}

function normalizeMarkers(value: unknown): string[] | undefined {
    if (!Array.isArray(value)) {
        return undefined;
    }
    const markers = value
        .map((marker) => {
            if (typeof marker === "string") {
                return marker;
            }
            return stringValue(record(marker).name);
        })
        .filter((marker): marker is string => Boolean(marker));
    return markers.length > 0 ? markers : undefined;
}

function normalizeStringArray(value: unknown): string[] | undefined {
    if (!Array.isArray(value)) {
        return undefined;
    }
    const values = value.filter(
        (item): item is string => typeof item === "string",
    );
    return values.length > 0 ? values : undefined;
}

function normalizeCollectedTest(value: unknown): CollectedTest | null {
    const item = record(value);
    const nodeId = stringValue(item.node_id) ?? stringValue(item.nodeid);
    if (!nodeId) {
        return null;
    }

    const location = record(item.location);
    const nodeParts = nodeId.split("::");
    return {
        node_id: nodeId,
        name: stringValue(item.name)
            ?? stringValue(item.display_name)
            ?? nodeParts[nodeParts.length - 1],
        path: stringValue(item.path) ?? stringValue(location.path),
        line: numberValue(item.line) ?? numberValue(location.line),
        markers: normalizeMarkers(item.markers),
        truncated: normalizeStringArray(item.truncated),
    };
}

function normalizeCapturedOutput(
    value: Record<string, unknown>,
): CapturedTestOutput {
    const captured = record(value.captured);
    return {
        stdout: stringValue(value.stdout)
            ?? stringValue(value.captured_stdout)
            ?? stringValue(value.capstdout)
            ?? stringValue(captured.stdout),
        stderr: stringValue(value.stderr)
            ?? stringValue(value.captured_stderr)
            ?? stringValue(value.capstderr)
            ?? stringValue(captured.stderr),
        log: stringValue(value.log)
            ?? stringValue(value.captured_log)
            ?? stringValue(value.caplog)
            ?? stringValue(captured.log),
    };
}

function normalizeFailure(
    value: Record<string, unknown>,
): TestFailure | undefined {
    const nested = record(value.failure);
    const source = Object.keys(nested).length > 0 ? nested : value;
    const location = record(source.location);
    const message = stringValue(source.message);
    const longrepr = printable(source.longrepr ?? value.longrepr);
    const traceback = printable(source.traceback);
    if (!message && !longrepr && !traceback) {
        return undefined;
    }
    const failure: TestFailure = {
        phase: normalizePhase(source.phase ?? value.phase),
        message,
        longrepr,
        traceback,
        path: stringValue(source.path) ?? stringValue(location.path),
        line: numberValue(source.line) ?? numberValue(location.line),
    };
    return failure;
}

function normalizePhaseResult(value: unknown): TestPhaseResult | null {
    const phase = record(value);
    const phaseName = normalizePhase(phase.phase ?? phase.when);
    if (!phaseName) {
        return null;
    }
    return {
        phase: phaseName,
        outcome: normalizeOutcome(phase.outcome),
        duration: numberValue(phase.duration),
        reason: stringValue(phase.reason),
        message: stringValue(phase.message),
        longrepr: printable(phase.longrepr),
        failure: normalizeFailure(phase),
        ...normalizeCapturedOutput(phase),
        truncated: normalizeStringArray(phase.truncated),
    };
}

function normalizeTestResult(value: unknown): TestResult | null {
    const result = record(value);
    const nodeId = stringValue(result.node_id) ?? stringValue(result.nodeid);
    if (!nodeId) {
        return null;
    }

    const phases = Array.isArray(result.phases)
        ? result.phases
            .map(normalizePhaseResult)
            .filter((phase): phase is TestPhaseResult => phase !== null)
        : undefined;

    return {
        node_id: nodeId,
        name: stringValue(result.name),
        path: stringValue(result.path),
        line: numberValue(result.line),
        markers: normalizeMarkers(result.markers),
        outcome: normalizeOutcome(result.outcome),
        duration: numberValue(result.duration),
        phase: normalizePhase(result.phase),
        phases,
        failure: normalizeFailure(result),
        longrepr: printable(result.longrepr),
        truncated: normalizeStringArray(result.truncated),
        ...normalizeCapturedOutput(result),
    };
}

function normalizeSummary(value: unknown): TestSummary | undefined {
    const source = record(value);
    const entries = Object.entries(source)
        .filter((entry): entry is [string, number] => (
            typeof entry[1] === "number"
            && Number.isFinite(entry[1])
        ));
    return entries.length > 0 ? Object.fromEntries(entries) : undefined;
}

function normalizeError(value: unknown): TestRunError {
    const payload = record(value);
    const nestedError = payload.error;
    if (typeof nestedError === "string") {
        return {
            kind: stringValue(payload.kind),
            message: nestedError,
            details: stringValue(payload.details),
            truncated: normalizeStringArray(payload.truncated),
        };
    }
    const source = Object.keys(record(nestedError)).length > 0
        ? record(nestedError)
        : payload;
    return {
        kind: stringValue(source.kind) ?? stringValue(payload.kind),
        message: stringValue(source.message)
            ?? stringValue(payload.message)
            ?? "pytest reported an unknown error.",
        details: stringValue(source.details) ?? stringValue(payload.details),
        phase: normalizePhase(source.phase),
        path: stringValue(source.path) ?? stringValue(payload.path),
        line: numberValue(source.line) ?? numberValue(payload.line),
        column: numberValue(source.column) ?? numberValue(payload.column),
        end_column: numberValue(source.end_column)
            ?? numberValue(payload.end_column),
        source: stringValue(source.source) ?? stringValue(payload.source),
        truncated: normalizeStringArray(
            source.truncated ?? payload.truncated,
        ),
    };
}

function runIdFrom(value: Record<string, unknown>): string | undefined {
    return stringValue(value.run_id) ?? stringValue(value.runId);
}

function isBusy(state: TestSocketRootState): boolean {
    return state.tests.status === "collecting"
        || state.tests.status === "running"
        || state.tests.status === "cancelling";
}

export const testsocketMiddlewareFactory =
    (): Middleware<object, TestSocketRootState> => {
    let socket: Socket | null = null;
    let autorunTimer: ReturnType<typeof setTimeout> | null = null;
    let autorunHistory: number[] = [];

    const cancelAutorunTimer = () => {
        if (autorunTimer !== null) {
            globalThis.clearTimeout(autorunTimer);
            autorunTimer = null;
        }
    };

    return (params) => {
        const { dispatch, getState } = params;

        const sendCollection = () => {
            if (
                !socket
                || getState().tests.readyState !== ReadyState.OPEN
                || isBusy(getState())
            ) {
                return;
            }
            const runId = createTestRunId();
            dispatch(testCollectionRequested({ run_id: runId }));
            socket.send({
                type: "TEST_COLLECT",
                data: { run_id: runId },
            });
        };

        const sendRun = (
            nodeIds?: string[],
            source: "manual" | "autorun" = "manual",
        ) => {
            const state = getState();
            if (
                !socket
                || state.tests.readyState !== ReadyState.OPEN
                || isBusy(state)
            ) {
                return;
            }

            if (source === "autorun") {
                const now = Date.now();
                autorunHistory = autorunHistory.filter(
                    (timestamp) => now - timestamp < AutorunWindowMs,
                );
                if (autorunHistory.length >= MaxAutorunsPerWindow) {
                    dispatch(pauseTestAutorun(
                        "Autorun paused after repeated rapid changes. "
                        + "Resume it when the files have settled.",
                    ));
                    return;
                }
                autorunHistory.push(now);
            } else {
                cancelAutorunTimer();
            }

            const runId = createTestRunId();
            const data = nodeIds && nodeIds.length > 0
                ? { run_id: runId, node_ids: nodeIds }
                : { run_id: runId };
            dispatch(testRunRequested({
                run_id: runId,
                node_ids: nodeIds && nodeIds.length > 0
                    ? nodeIds
                    : undefined,
            }));
            socket.send({ type: "TEST_RUN", data });
        };

        const runPendingAutorun = () => {
            const state = getState();
            if (
                autorunTimer === null
                && state.tests.autorunPending
                && state.tests.autorun
                && !state.tests.autorunPaused
                && state.tests.readyState === ReadyState.OPEN
                && !isBusy(state)
            ) {
                dispatch(setAutorunPending(false));
                sendRun(undefined, "autorun");
            }
        };

        return (next) => (action) => {
            if (
                typeof action !== "object"
                || action === null
                || !("type" in action)
                || typeof action.type !== "string"
            ) {
                return next(action);
            }
            const typedAction = action as {
                type: string;
                payload?: unknown;
            };
            const type = typedAction.type;

            if (type === setTestAutorun.type) {
                const result = next(typedAction);
                try {
                    globalThis.localStorage?.setItem(
                        "trailhead.pytest.autorun",
                        typedAction.payload ? "true" : "false",
                    );
                } catch {
                    // Storage can be unavailable in privacy-restricted browsers.
                }
                if (!typedAction.payload) {
                    cancelAutorunTimer();
                    autorunHistory = [];
                }
                return result;
            }

            if (type === resumeTestAutorun.type) {
                autorunHistory = [];
                return next(typedAction);
            }

            if (type === projectPythonChanged.type) {
                const result = next(typedAction);
                cancelAutorunTimer();
                const state = getState();
                if (
                    !state.tests.autorun
                    || state.tests.autorunPaused
                    || !state.tests.module
                ) {
                    return result;
                }
                autorunTimer = globalThis.setTimeout(() => {
                    autorunTimer = null;
                    const latestState = getState();
                    if (
                        !latestState.tests.autorun
                        || latestState.tests.autorunPaused
                        || !latestState.tests.module
                    ) {
                        return;
                    }
                    if (
                        isBusy(latestState)
                        || latestState.tests.readyState !== ReadyState.OPEN
                    ) {
                        dispatch(setAutorunPending(true));
                    } else {
                        sendRun(undefined, "autorun");
                    }
                }, AutorunDebounceMs);
                return result;
            }

            if (!type.startsWith("testsocket/")) {
                return next(action);
            }

            const payload = record(typedAction.payload);
            switch (type) {
                case "testsocket/connect": {
                    cancelAutorunTimer();
                    autorunHistory = [];
                    socket?.disconnect();

                    const module = stringValue(payload.module);
                    const endpoint = stringValue(payload.endpoint);
                    if (!module || !endpoint) {
                        break;
                    }

                    socket = new Socket(endpoint, 1000);
                    dispatch(startTestSession({ module }));
                    socket.connect();

                    socket.on("open", () => {
                        dispatch(updateTestReadyState(ReadyState.OPEN));
                        sendCollection();
                    });
                    socket.on("close", () => {
                        dispatch(updateTestReadyState(ReadyState.CLOSED));
                    });
                    socket.on("error", () => {
                        dispatch(updateTestReadyState(ReadyState.CLOSED));
                    });
                    socket.on("message", (event: MessageEvent) => {
                        let message;
                        try {
                            message = parseJsonMessage(event);
                        } catch {
                            return;
                        }
                        if (!message) {
                            return;
                        }

                        const data = record(message.data);
                        const runId = runIdFrom(data);
                        if (!runId) {
                            return;
                        }

                        const currentRunId =
                            getState().tests.activeRunId;
                        const isCurrentRun = currentRunId === runId;

                        switch (message.type) {
                            case "TEST_RUN_STARTED":
                                dispatch(testRunStarted({
                                    run_id: runId,
                                    node_ids: Array.isArray(data.node_ids)
                                        ? data.node_ids.filter(
                                            (nodeId): nodeId is string =>
                                                typeof nodeId === "string",
                                        )
                                        : undefined,
                                    mode: data.mode === "collect"
                                        ? "collect"
                                        : "run",
                                }));
                                break;
                            case "TESTS_COLLECTED": {
                                const rawTests = Array.isArray(data.tests)
                                    ? data.tests
                                    : [];
                                dispatch(testsCollected({
                                    run_id: runId,
                                    tests: rawTests
                                        .map(normalizeCollectedTest)
                                        .filter(
                                            (test): test is CollectedTest =>
                                                test !== null,
                                        ),
                                }));
                                break;
                            }
                            case "TEST_RESULT": {
                                const result = normalizeTestResult(
                                    data.test ?? data.result ?? data,
                                );
                                if (result) {
                                    dispatch(testResultReceived({
                                        run_id: runId,
                                        result,
                                    }));
                                }
                                break;
                            }
                            case "TEST_RUN_FINISHED":
                                dispatch(testRunFinished({
                                    run_id: runId,
                                    summary: normalizeSummary(data.summary),
                                    duration: numberValue(data.duration),
                                    exit_code: data.exit_code === null
                                        ? null
                                        : numberValue(data.exit_code),
                                    status: stringValue(data.status),
                                    cancelled: data.cancelled === true,
                                }));
                                if (isCurrentRun) {
                                    runPendingAutorun();
                                }
                                break;
                            case "TEST_ERROR":
                                dispatch(testRunFailed({
                                    run_id: runId,
                                    error: normalizeError(data),
                                }));
                                break;
                        }
                    });
                    break;
                }
                case "testsocket/collect":
                    cancelAutorunTimer();
                    dispatch(setAutorunPending(false));
                    sendCollection();
                    break;
                case "testsocket/run": {
                    const nodeIds = Array.isArray(payload.node_ids)
                        ? payload.node_ids.filter(
                            (nodeId): nodeId is string =>
                                typeof nodeId === "string",
                        )
                        : undefined;
                    sendRun(
                        nodeIds,
                        payload.source === "autorun" ? "autorun" : "manual",
                    );
                    break;
                }
                case "testsocket/cancel": {
                    cancelAutorunTimer();
                    const runId =
                        getState().tests.activeRunId;
                    if (socket && runId) {
                        dispatch(testCancelRequested());
                        socket.send({
                            type: "TEST_CANCEL",
                            data: { run_id: runId },
                        });
                    }
                    break;
                }
                case "testsocket/disconnect":
                    cancelAutorunTimer();
                    socket?.disconnect();
                    socket = null;
                    dispatch(endTestSession());
                    break;
            }

            return next(typedAction);
        };
    };
};
